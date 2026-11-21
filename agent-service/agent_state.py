"""
agent_state.py - What the agent remembers while it works.

LangGraph passes this dictionary from box to box (node to node). Each node returns
only the keys it changes; LangGraph merges them into the state.
"""

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    request: str                         # the user's message, unchanged
    budget: Optional[float]              # read from the request by CODE (catalog.extract_budget)
    route: str                           # "build" | "compare" | "refuse"

    picks: Dict[str, Dict[str, Any]]     # category -> chosen part card (from search_parts)
    exclude: Dict[str, List[str]]        # category -> part ids a repair ruled out
    constraints: Dict[str, Dict[str, Any]]  # category -> extra search filters set by a repair

    steps: int                           # AI pick calls so far (the step cap counts these)
    repairs: int                         # repair rounds so far
    check: Optional[Dict[str, Any]]      # last check_compatibility result
    total_price: Optional[float]         # computed by code, never by the AI

    # Set when the run must stop early. None while everything is fine.
    #   no_valid_build | step_limit | token_limit | error | could_not_verify
    # Chat mode adds: approved | rejected (after the approval pause)
    status: Optional[str]
    failure_reasons: List[str]

    reply: str                           # final text shown to the user
    history: List[Dict[str, Any]]        # one entry per step, for tests, debugging and tracing
    tokens: Dict[str, int]               # {"prompt": n, "output": n} over all AI calls
    comparison: Optional[Dict[str, Any]] # comparator table {"headers", "rows"}, built by code

    # Human approval (chat mode only)
    approval_requested_at: Optional[float]  # set by finalize; the approval expires 15 min later
    approval: Optional[Dict[str, Any]]      # {"build_hash", "decision": approved|rejected} once decided
