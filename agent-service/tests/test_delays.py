"""
Fixes for the slow first request (measured: the first search took 9-33 s, all later ones ~0.3 s).
No network, no real model, no real Gemini.

1. Load the reranker from the local cache first (no online "is there an update?" check).
2. Warm everything up once when the service starts, so no user request pays the cold start.
3. On Gemini "429 too many requests", wait as long as Gemini asks (free tier: 15 calls/min),
   instead of 2 s and 4 s and then failing the whole request.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.genai import errors
from google.genai import types as genai_types

import hybrid_search
import llm as llm_mod
from llm import GeminiLLM
from schemas import RouteDecision


# ─── 1. Reranker: local cache first ────────────────────────────────────────────
def _fake_cross_encoder(monkeypatch, cached: bool):
    calls = []

    class FakeCrossEncoder:
        def __init__(self, name, **kwargs):
            calls.append(kwargs)
            if kwargs.get("local_files_only") and not cached:
                raise OSError("model not in the local cache")

    import sentence_transformers
    monkeypatch.setattr(sentence_transformers, "CrossEncoder", FakeCrossEncoder)
    return calls


def test_reranker_loads_from_the_local_cache_without_going_online(monkeypatch):
    calls = _fake_cross_encoder(monkeypatch, cached=True)
    hybrid_search.CrossEncoderReranker().model
    assert calls == [{"local_files_only": True}]


def test_reranker_downloads_only_when_not_cached_yet(monkeypatch):
    calls = _fake_cross_encoder(monkeypatch, cached=False)
    hybrid_search.CrossEncoderReranker().model
    assert calls == [{"local_files_only": True}, {}]


# ─── 2. Warm-up at service start ───────────────────────────────────────────────
def test_warm_up_loads_every_slow_part_and_reports_times(monkeypatch):
    import agent_graph
    from agent_config import AgentConfig

    loaded = []
    monkeypatch.setattr(agent_graph, "_warm_steps", lambda cfg: [
        ("chroma", lambda: loaded.append("chroma")),
        ("embeddings", lambda: loaded.append("embeddings")),
        ("reranker", lambda: loaded.append("reranker")),
    ])
    report = agent_graph.warm_up(AgentConfig())
    assert loaded == ["chroma", "embeddings", "reranker"]
    assert set(report) == {"chroma", "embeddings", "reranker"}
    assert all(isinstance(v, float) for v in report.values())


def test_warm_up_never_crashes_when_a_service_is_down(monkeypatch):
    import agent_graph
    from agent_config import AgentConfig

    def ollama_down():
        raise ConnectionError("Ollama is not running")

    monkeypatch.setattr(agent_graph, "_warm_steps", lambda cfg: [("embeddings", ollama_down)])
    report = agent_graph.warm_up(AgentConfig())
    assert report["embeddings"].startswith("failed: ConnectionError")


def test_warm_up_skips_the_reranker_when_it_is_not_used():
    import agent_graph
    from agent_config import AgentConfig

    names = [name for name, _ in agent_graph._warm_steps(AgentConfig(retriever="vector"))]
    assert "reranker" not in names and "keyword_index" not in names
    names = [name for name, _ in agent_graph._warm_steps(AgentConfig(retriever="hybrid_rerank"))]
    assert {"chroma", "embeddings", "keyword_index", "reranker"} <= set(names)


def test_the_service_warms_up_when_it_starts(monkeypatch):
    import main

    started = []
    monkeypatch.setattr(main, "get_current_llm", lambda: None)
    monkeypatch.setattr(main, "warm_up", lambda cfg, llm=None: started.append(cfg) or {})
    monkeypatch.delenv("AGENT_WARMUP", raising=False)
    with TestClient(main.app):          # entering the client runs the startup code
        pass
    assert len(started) == 1


def test_warm_up_can_be_switched_off(monkeypatch):
    import main

    started = []
    monkeypatch.setattr(main, "get_current_llm", lambda: None)
    monkeypatch.setattr(main, "warm_up", lambda cfg, llm=None: started.append(cfg) or {})
    monkeypatch.setenv("AGENT_WARMUP", "0")
    with TestClient(main.app):
        pass
    assert started == []


# ─── 3. Gemini "429 too many requests" ─────────────────────────────────────────
class _Models:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _gemini(*outcomes):
    g = object.__new__(GeminiLLM)
    g.model = "fake-gemini"
    g.client = SimpleNamespace(models=_Models(*outcomes))
    return g


def _ok():
    return genai_types.GenerateContentResponse(candidates=[genai_types.Candidate(
        content=genai_types.Content(role="model", parts=[genai_types.Part(text='{"route": "ARCHITECT"}')]),
        finish_reason=genai_types.FinishReason.STOP)])


def _rate_limited(retry_delay=None):
    details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}] if retry_delay else []
    return errors.APIError(429, {"error": {"code": 429, "message": "Resource exhausted",
                                           "status": "RESOURCE_EXHAUSTED", "details": details}})


@pytest.fixture
def waits(monkeypatch):
    slept = []
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: slept.append(s))
    return slept


def test_429_waits_as_long_as_gemini_asks(waits):
    g = _gemini(_rate_limited("37s"), _ok())
    assert g.generate("s", "u", RouteDecision).parsed.route == "ARCHITECT"
    assert waits == [37]


def test_429_without_a_hint_waits_long_enough_for_the_per_minute_limit(waits):
    g = _gemini(_rate_limited(), _rate_limited(), _ok())
    g.generate("s", "u", RouteDecision)
    assert waits == [30, 60]


def test_429_wait_is_capped_at_one_minute(waits):
    g = _gemini(_rate_limited("300s"), _ok())
    g.generate("s", "u", RouteDecision)
    assert waits == [60]


def test_503_overloaded_still_uses_short_waits(waits):
    g = _gemini(errors.APIError(503, {"error": {"code": 503, "message": "overloaded"}}), _ok())
    g.generate("s", "u", RouteDecision)
    assert waits == [2]


# ─── Found in the live check: the first request's Ollama /api/chat returned 500 once. ───
# The chat model was not part of the warm-up, so its (slow, sometimes failing) first load
# happened inside a user's request.
def test_warm_up_preloads_a_local_chat_model(monkeypatch):
    import agent_graph
    from agent_config import AgentConfig

    monkeypatch.setattr(agent_graph, "_warm_steps", lambda cfg: [])
    loaded = []
    report = agent_graph.warm_up(AgentConfig(), llm=SimpleNamespace(preload=lambda: loaded.append(1)))
    assert loaded == [1]
    assert "chat_model" in report


def test_warm_up_never_calls_gemini(monkeypatch):
    """Gemini has nothing to load, and a warm-up call would spend free-tier quota."""
    import agent_graph
    from agent_config import AgentConfig

    monkeypatch.setattr(agent_graph, "_warm_steps", lambda cfg: [])
    report = agent_graph.warm_up(AgentConfig(), llm=object.__new__(GeminiLLM))
    assert "chat_model" not in report


def test_ollama_preload_loads_the_model_without_generating_text():
    calls = []
    o = object.__new__(llm_mod.OllamaLLM)
    o.model = "llama3.1:8b"
    o.client = SimpleNamespace(generate=lambda **kw: calls.append(kw))
    o.preload()
    assert calls[0]["model"] == "llama3.1:8b" and calls[0]["prompt"] == ""


def test_the_service_warms_up_the_chat_model_too(monkeypatch):
    import main

    seen = []
    sentinel = object()
    monkeypatch.setattr(main, "get_current_llm", lambda: sentinel)
    monkeypatch.setattr(main, "warm_up", lambda cfg, llm=None: seen.append(llm) or {})
    monkeypatch.delenv("AGENT_WARMUP", raising=False)
    with TestClient(main.app):
        pass
    assert seen == [sentinel]
