"""
agent_config.py - The agent's on/off switches.

The same code runs with upgrades on or off, so before/after numbers are a fair
comparison (the eval's results table). Defaults = all upgrades on.

Environment variables (a request can still override them, see with_overrides):
  AGENT_RETRIEVER     vector | hybrid | hybrid_rerank   (search method)
  AGENT_USE_TOOLS     1/0  on: code-filtered step-by-step picks; off: one AI call picks everything (v1 style)
  AGENT_USE_CHECKER   1/0  on: code checks the finished build; off: no check, answer says "not checked"
  AGENT_REPAIR_LOOPS  0..2 how many times a failed build may be repaired
  AGENT_MAX_STEPS     step cap (AI pick calls) so a bad loop can never run forever
  AGENT_MAX_TOKENS    token cap for one request (prompt + output, all AI calls)
"""

import os
from dataclasses import dataclass, fields, replace
from typing import Any, Dict, Mapping, Optional

RETRIEVERS = ("vector", "hybrid", "hybrid_rerank")
MAX_REPAIR_LOOPS = 2


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class AgentConfig:
    retriever: str = "hybrid_rerank"   # best recall in the search eval
    use_tools: bool = True
    use_checker: bool = True
    repair_loops: int = MAX_REPAIR_LOOPS
    max_steps: int = 30                # 9 picks + up to 2 repairs x 9 re-picks fits easily
    candidates_per_pick: int = 8       # the AI sees a few good choices, never 3,000
    # Measured: one full pass used 6,295 tokens (5,687 in + 608 out). Two full repairs
    # re-pick everything twice more (about 3 x 6,295 = 19k), so 25,000 leaves room for that, no more.
    max_tokens: int = 25_000

    def __post_init__(self):
        if self.retriever not in RETRIEVERS:
            raise ValueError(f"retriever must be one of {RETRIEVERS}, got {self.retriever!r}")
        if not 0 <= self.repair_loops <= MAX_REPAIR_LOOPS:
            raise ValueError(f"repair_loops must be 0..{MAX_REPAIR_LOOPS}, got {self.repair_loops}")
        if self.max_steps < 1:
            raise ValueError(f"max_steps must be at least 1, got {self.max_steps}")
        if self.candidates_per_pick < 1:
            raise ValueError("candidates_per_pick must be at least 1")
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be at least 1, got {self.max_tokens}")

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "AgentConfig":
        env = os.environ if env is None else env
        values: Dict[str, Any] = {}
        if "AGENT_RETRIEVER" in env:
            values["retriever"] = env["AGENT_RETRIEVER"].strip()
        if "AGENT_USE_TOOLS" in env:
            values["use_tools"] = _as_bool(env["AGENT_USE_TOOLS"])
        if "AGENT_USE_CHECKER" in env:
            values["use_checker"] = _as_bool(env["AGENT_USE_CHECKER"])
        if "AGENT_REPAIR_LOOPS" in env:
            values["repair_loops"] = int(env["AGENT_REPAIR_LOOPS"])
        if "AGENT_MAX_STEPS" in env:
            values["max_steps"] = int(env["AGENT_MAX_STEPS"])
        if "AGENT_MAX_TOKENS" in env:
            values["max_tokens"] = int(env["AGENT_MAX_TOKENS"])
        return cls(**values)

    def with_overrides(self, overrides: Optional[Mapping[str, Any]]) -> "AgentConfig":
        """A NEW config with some switches changed (validated). The original is not changed."""
        if not overrides:
            return self
        known = {f.name for f in fields(self)}
        unknown = set(overrides) - known
        if unknown:
            raise ValueError(f"Unknown agent switches: {sorted(unknown)}")
        return replace(self, **overrides)
