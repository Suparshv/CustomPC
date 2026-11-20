"""
chat.py -: the agent in a chat, with a human approval step before add-to-cart.

One chat session = one LangGraph thread_id. The graph state of each thread is saved in
SQLite (the checkpointer), so a build that is waiting for approval survives a restart.

  start_chat   run one message. A valid build ends PAUSED: status "awaiting_approval"
               with the payload the Approve/Reject buttons show.
  resume_chat  continue a paused thread with the human's decision, but ONLY after code
               checked that the thread really is waiting, the build hash matches, and the
               request has not expired. (Resuming a thread that is not paused would restart
               the graph from the beginning, so we never let that happen.)
"""

import sqlite3
import threading
import time
from typing import Any, Callable, Dict, Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent_config import AgentConfig
from agent_graph import ToolRunner, build_agent, fresh_state, run_config, stream_run, summarize

# Resuming is quick (no AI call). One at a time, so two clicks can't both resume the same pause.
_resume_lock = threading.Lock()


def open_checkpointer(path: str) -> SqliteSaver:
    """LangGraph's SQLite saver on `path`. The in-memory saver would forget everything on restart."""
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))


def pending_approval(app: Any, conf: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The approval payload this thread is paused on, or None if it is not waiting."""
    snapshot = app.get_state(conf)
    for task in snapshot.tasks:
        for intr in task.interrupts:
            if isinstance(intr.value, dict) and intr.value.get("type") == "approve_build":
                return intr.value
    return None


def start_chat(thread_id: str, message: str, llm: Any, config: Optional[AgentConfig] = None, *,
               checkpointer: Any, store: Any, tool_runner: Optional[ToolRunner] = None,
               clock: Callable[[], float] = time.time) -> Dict[str, Any]:
    """Run one chat message. A new message always starts fresh: any build still waiting is dropped."""
    cfg = config or AgentConfig()
    app = build_agent(llm, cfg, tool_runner, checkpointer=checkpointer, approvals=store, clock=clock)
    conf = run_config(cfg, thread_id=thread_id)
    start = time.perf_counter()
    state = stream_run(app, fresh_state(message), conf)
    result = summarize(state, cfg, start)
    result["thread_id"] = thread_id
    result["approval"] = None
    if result["status"] != "error":
        pending = pending_approval(app, conf)
        if pending:
            result["status"] = "awaiting_approval"
            result["approval"] = pending
    return result


def resume_chat(thread_id: str, build_hash: str, approved: bool, llm: Any,
                config: Optional[AgentConfig] = None, *, checkpointer: Any, store: Any,
                tool_runner: Optional[ToolRunner] = None,
                clock: Callable[[], float] = time.time) -> Dict[str, Any]:
    """
    Approve or reject the build this thread is waiting on. Returns a status:
      approved | rejected                     the decision was applied (or already was: already_decided)
      no_pending_approval | hash_mismatch | expired   nothing was resumed, nothing approved
    """
    cfg = config or AgentConfig()
    app = build_agent(llm, cfg, tool_runner, checkpointer=checkpointer, approvals=store, clock=clock)
    conf = run_config(cfg, thread_id=thread_id)
    base = {"thread_id": thread_id, "build_hash": build_hash}

    with _resume_lock:
        pending = pending_approval(app, conf)
        if pending is None:
            # Safe to call twice: the same decision on the same build is reported again, not redone.
            values = app.get_state(conf).values or {}
            previous = values.get("approval") or {}
            if previous.get("build_hash") == build_hash:
                return {**base, "status": previous["decision"], "already_decided": True,
                        "reply": values.get("reply", "")}
            return {**base, "status": "no_pending_approval",
                    "reply": "There is no build waiting for approval in this chat."}
        if pending["build_hash"] != build_hash:
            return {**base, "status": "hash_mismatch",
                    "reply": "That is not the build waiting for approval. Nothing was approved."}
        if clock() > pending["expires_at"]:
            return {**base, "status": "expired",
                    "reply": "This build waited too long for approval. Ask for it again to get fresh prices."}

        state = stream_run(app, Command(resume={"approved": bool(approved), "build_hash": build_hash}), conf)

    status = state.get("status")
    result = {**base, "status": status if status in ("approved", "rejected") else "error",
              "reply": state.get("reply", ""), "already_decided": False}
    if result["status"] == "approved":
        result["expires_at"] = (store.get(thread_id, build_hash) or {}).get("expires_at")
    return result
