import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx
from google.genai import errors

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Request
from pydantic import StrictBool

from agent_config import AgentConfig
from agent_graph import run_agent, warm_up
from approvals import ApprovalStore, claim_cart, verdict_of
from chat import open_checkpointer, resume_chat, start_chat
from llm import get_llm, LLMError, LLMValidationError
from repo import RepoUnavailableError, get_repo
from safety import RateLimiter, clean_text
from schemas import DraftBuild
from catalog import check_build
from prompts import ARCHITECT_SYSTEM, format_architect_user_prompt
from tools import run_tool

logger = logging.getLogger("agent-service")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load the slow parts (Chroma, Ollama embedding model, keyword index, reranker) once at
    # start-up, so no user request pays the 9-33 s cold start. AGENT_WARMUP=0 turns it off.
    if os.getenv("AGENT_WARMUP", "1").strip().lower() not in ("0", "false", "no", "off"):
        try:
            llm = get_current_llm()          # Ollama: its chat model gets loaded too
        except Exception as e:               # e.g. no API key: the requests will report it
            logger.warning("Warm-up: LLM not available (%s)", e)
            llm = None
        logger.info("Warm-up: %s", warm_up(AgentConfig.from_env(), llm=llm))
    yield


app = FastAPI(title="PC Builder agent service", lifespan=lifespan)

# Lazy LLM loader so importing main.py does not crash if API keys/environment are missing
_llm = None


def get_current_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


class Ask(BaseModel):
    message: str = Field(min_length=1, max_length=500, description="User request (max 500 characters)")


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500, description="User request (max 500 characters)")
    overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Switches for this request only, e.g. {\"use_checker\": false, \"repair_loops\": 0}",
    )


@app.post("/agent/build")
def agent_build(req: AgentRequest):
    """
    Run the Day 10 agent on one request.
    200: the agent answered (valid, no_valid_build, unverified, refused, comparison, step_limit...).
    422: bad request or bad switch values.  503: the AI or a data service is unavailable.
    """
    try:
        config = AgentConfig.from_env().with_overrides(req.overrides)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail={"error": "InvalidSwitches", "message": str(e)})
    try:
        llm = get_current_llm()
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "error": f"LLM not available: {e}"})

    result = run_agent(req.message, llm, config)   # never raises: failures come back as status "error"
    # Say which AI produced the answer, so eval reports describe the system that actually ran.
    result["provider"] = getattr(llm, "provider", None)
    result["model"] = getattr(llm, "model", None)
    if result.get("status") == "error":
        return JSONResponse(status_code=503, content=result)
    return result


# ─── Day 12: chat with human approval, the cart rule, the fail-safe checker ─────
THREAD_ID_PATTERN = r"^[A-Za-z0-9._@:-]{1,128}$"
BUILD_HASH_PATTERN = r"^[0-9a-f]{64}$"
DB_PATH = os.getenv("AGENT_DB_PATH", str(Path(__file__).resolve().parent / "data" / "agent_state.sqlite"))

# A simple abuse guard: each AI chat message can cost thousands of tokens.
chat_limiter = RateLimiter(max_calls=int(os.getenv("AGENT_CHAT_PER_MINUTE", "10")), per_seconds=60)

_chat_backend = None
_chat_backend_lock = threading.Lock()


def get_chat_backend():
    """(checkpointer, approval store), both in one SQLite file, opened once."""
    global _chat_backend
    with _chat_backend_lock:
        if _chat_backend is None:
            _chat_backend = (open_checkpointer(DB_PATH), ApprovalStore(DB_PATH))
        return _chat_backend


def get_part_repo():
    return get_repo()   # MongoDB; raises RepoUnavailableError when it is down


def _client_key(request: Request) -> str:
    # Express forwards the browser's IP; a direct caller is keyed by its own address.
    return request.headers.get("x-client-ip") or (request.client.host if request.client else "unknown")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500, description="User message (max 500 characters)")
    thread_id: str = Field(pattern=THREAD_ID_PATTERN, description="One id per chat session")
    # No switch overrides here: a public chat must not be able to raise the step or repair caps.


class ApproveRequest(BaseModel):
    thread_id: str = Field(pattern=THREAD_ID_PATTERN)
    build_hash: str = Field(pattern=BUILD_HASH_PATTERN)
    approved: StrictBool      # a real true/false, never "yes"


class CartRequest(BaseModel):
    thread_id: str = Field(pattern=THREAD_ID_PATTERN)
    build_hash: str = Field(pattern=BUILD_HASH_PATTERN)


class CheckRequest(BaseModel):
    part_ids: List[str] = Field(min_length=1, max_length=12)
    partial: bool = False


APPROVE_CODES = {"approved": 200, "rejected": 200, "hash_mismatch": 409, "no_pending_approval": 409,
                 "expired": 410}
CART_CODES = {"added": 200, "not_approved": 403, "expired": 410, "already_used": 409, "build_changed": 409,
              "out_of_stock": 409}


@app.post("/agent/chat")
def agent_chat(req: ChatRequest, request: Request):
    """
    One chat message. 200: an answer, or status "awaiting_approval" with the build to approve.
    422: bad input. 429: too many messages. 503: the AI or a data service is down.
    """
    if not chat_limiter.allow(_client_key(request)):
        return JSONResponse(status_code=429, headers={"Retry-After": "60"},
                            content={"status": "rate_limited", "reply": "Too many messages. Please wait a minute."})
    message = clean_text(req.message)
    if not message:
        raise HTTPException(status_code=422, detail={"error": "EmptyMessage",
                                                     "message": "The message is empty after cleaning."})
    try:
        llm = get_current_llm()
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "error": f"LLM not available: {e}"})
    try:
        checkpointer, store = get_chat_backend()
        result = start_chat(req.thread_id, message, llm, AgentConfig.from_env(),
                            checkpointer=checkpointer, store=store)
    except Exception as e:
        logger.exception("Chat failed")
        return JSONResponse(status_code=503, content={"status": "error", "error": f"Chat storage failed: {e}"})
    result["provider"] = getattr(llm, "provider", None)
    result["model"] = getattr(llm, "model", None)
    if result.get("status") == "error":
        return JSONResponse(status_code=503, content=result)
    return result


@app.post("/agent/approve")
def agent_approve(req: ApproveRequest):
    """Approve or reject the build a chat thread is waiting on. Safe to call twice."""
    try:
        checkpointer, store = get_chat_backend()
        # No AI is needed: the approval step only checks and records.
        result = resume_chat(req.thread_id, req.build_hash, req.approved, None, AgentConfig.from_env(),
                             checkpointer=checkpointer, store=store)
    except Exception as e:
        logger.exception("Approve failed")
        return JSONResponse(status_code=503, content={"status": "error", "error": f"Approval failed: {e}"})
    return JSONResponse(status_code=APPROVE_CODES.get(result.get("status"), 503), content=result)


@app.post("/agent/cart")
def agent_cart(req: CartRequest):
    """The cart rule: only an approved, unexpired, unchanged, in-stock build. Never 'added' on an outage."""
    try:
        _, store = get_chat_backend()
        result = claim_cart(store, get_part_repo(), req.thread_id, req.build_hash)
    except RepoUnavailableError as e:
        return JSONResponse(status_code=503, content={"status": "error", "error": str(e)})
    except Exception as e:
        logger.exception("Cart check failed")
        return JSONResponse(status_code=503, content={"status": "error", "error": f"Cart check failed: {e}"})
    return JSONResponse(status_code=CART_CODES.get(result.get("status"), 503), content=result)


@app.post("/agent/check")
def agent_check(req: CheckRequest):
    """The code checker over HTTP (for Express). A broken check is 503 + could_not_verify, never compatible."""
    result = run_tool("check_compatibility", {"part_ids": req.part_ids, "partial": req.partial})
    verdict = verdict_of(result)
    if "error" in result:
        return JSONResponse(status_code=503, content={"error": result["error"], "verdict": verdict})
    return {**result, "verdict": verdict}


@app.get("/health")
def health():
    # Finding E: Clean single Exception handler covering all connection/readiness errors
    try:
        llm = get_current_llm()
        health_info = llm.check_health()
        return health_info
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "provider": getattr(_llm, "provider", "unknown") if _llm else "unknown",
                "error": str(e),
            },
        )


@app.post("/debug/draft-build")
def draft_build(ask: Ask):
    try:
        llm = get_current_llm()
        user_prompt = format_architect_user_prompt(ask.message)
        r = llm.generate(
            ARCHITECT_SYSTEM,
            user_prompt,
            DraftBuild,
            check=check_build,
            budget_source=ask.message,  # read the budget from the request only, not the price list
        )
        return {
            "result": r.parsed,
            "provider": r.provider,
            "model": r.model,
            "tokens": r.prompt_tokens + r.output_tokens,
            "seconds": r.seconds,
            "attempts": r.attempts,
        }
    except LLMValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "LLMValidationError",
                "problems": e.problems,
                "attempts": e.attempts,
            },
        )
    except errors.APIError as e:
        # Finding B: Map Google API 503/429 to HTTP 503 with retry-after hint
        if getattr(e, "code", None) in (503, 429):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "ServiceUnavailable",
                    "message": f"Gemini API is temporarily overloaded ({e.code}). Please retry.",
                    "code": e.code,
                },
                headers={"Retry-After": "5"},
            )
        raise HTTPException(
            status_code=502,
            detail={"error": "LLMProviderError", "message": str(e)},
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError) as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "ServiceUnavailable", "message": f"Cannot connect to LLM provider: {str(e)}"},
        )
    except LLMError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "LLMError", "message": str(e)},
        )
    except Exception as e:
        # Finding C: Log unexpected errors so server logs preserve stack traces
        logger.exception("Unexpected error in draft_build: %s", e)
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalServerError", "message": "An unexpected server error occurred."},
        )
