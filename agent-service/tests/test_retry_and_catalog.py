import pytest
from fastapi.testclient import TestClient
from llm import BaseLLM, Raw, LLMValidationError
from schemas import DraftBuild
from catalog import check_build
import main
from main import app


class Fake(BaseLLM):
    provider, model = "fake", "fake"

    def __init__(self, *texts):
        self.texts = list(texts)

    def _complete(self, system, user, schema):
        return Raw(self.texts.pop(0), 10, 5)


GOOD = '{"reply":"ok","build":[{"category":"gpu","id":"g1"}]}'
BAD = '{"reply":"ok","build":[{"category":"monitor","id":"x"}]}'


def test_retry_succeeds_second_time():
    r = Fake(BAD, GOOD).generate("s", "u", DraftBuild)
    assert r.attempts == 2 and r.prompt_tokens == 20  # tokens summed


def test_gives_up_after_three_attempts_retains_cost():
    with pytest.raises(LLMValidationError) as exc_info:
        Fake(BAD, BAD, BAD).generate("s", "u", DraftBuild)
    err = exc_info.value
    assert err.attempts == 3
    assert err.prompt_tokens == 30
    assert err.output_tokens == 15
    assert err.seconds >= 0


def test_retry_recovers_from_empty_text():
    r = Fake("", GOOD).generate("s", "u", DraftBuild)
    assert r.attempts == 2
    assert r.parsed.build[0].id == "g1"


def test_catalog_check_rejects_unknown_id():
    UNKNOWN_ID = '{"reply":"ok","build":[{"category":"gpu","id":"g99"}]}'
    fake = Fake(UNKNOWN_ID, GOOD)
    r = fake.generate("s", "u", DraftBuild, check=check_build)
    assert r.attempts == 2
    assert r.parsed.build[0].id == "g1"


def test_catalog_check_rejects_category_mismatch():
    # p1 is processor in ALL_SPECS, not gpu
    MISMATCH = '{"reply":"ok","build":[{"category":"gpu","id":"p1"}]}'
    fake = Fake(MISMATCH, GOOD)
    r = fake.generate("s", "u", DraftBuild, check=check_build)
    assert r.attempts == 2
    assert r.parsed.build[0].id == "g1"


def test_endpoint_returns_422_on_duplicate_ids(monkeypatch):
    DUP_IDS = '{"reply":"ok","build":[{"category":"gpu","id":"g1"},{"category":"gpu","id":"g1"}]}'
    fake = Fake(DUP_IDS, DUP_IDS, DUP_IDS)
    monkeypatch.setattr(main, "get_current_llm", lambda: fake)
    client = TestClient(app)
    response = client.post("/debug/draft-build", json={"message": "Build me a PC"})
    assert response.status_code == 422
    data = response.json()
    assert data["detail"]["error"] == "LLMValidationError"
    assert any("the same part id appears twice" in p for p in data["detail"]["problems"])
    assert data["detail"]["attempts"] == 3


def test_endpoint_connection_error_returns_503(monkeypatch):
    class BrokenConn(BaseLLM):
        provider = "ollama"
        def _complete(self, system, user, schema):
            raise ConnectionError("Ollama daemon is offline")

    monkeypatch.setattr(main, "get_current_llm", lambda: BrokenConn())
    client = TestClient(app)
    response = client.post("/debug/draft-build", json={"message": "Build me a PC"})
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "ServiceUnavailable"


def test_health_endpoint_closed_port_returns_503(monkeypatch):
    class UnhealthyLLM(BaseLLM):
        provider = "ollama"
        def check_health(self):
            raise ConnectionError("Connection refused on 11434")

    monkeypatch.setattr(main, "get_current_llm", lambda: UnhealthyLLM())
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert "Connection refused" in data["error"]


def test_catalog_check_rejects_empty_build():
    EMPTY_BUILD = DraftBuild(reply="I recommend nothing", build=[])
    problems = check_build(EMPTY_BUILD)
    assert any("build is empty" in p for p in problems)


def test_catalog_check_catches_hidden_ids_in_reply():
    from schemas import BuildItem
    # Mentions p1 and g1 in reply, but only includes p1 in build
    draft = DraftBuild(
        reply="I recommend p1 and g1 for your system.",
        build=[BuildItem(category="processor", id="p1")],
    )
    problems = check_build(draft)
    assert any("part id 'g1' was mentioned in reply but missing from build list" in p for p in problems)
    assert not any("part id 'p1'" in p for p in problems)


def test_extract_budget_various_formats():
    from catalog import extract_budget
    assert extract_budget("Gaming PC under 75000 INR") == 75000.0
    assert extract_budget("Video editing under 1 lakh") == 100000.0
    assert extract_budget("Workstation under 1.5 lakhs") == 150000.0
    assert extract_budget("Budget 50k") == 50000.0
    assert extract_budget("Setup for 60,000 rupees") == 60000.0
    assert extract_budget("No budget specified") is None


def test_model_matches_exact_tag_rejection():
    from llm import _model_matches
    assert _model_matches("llama3.1:8b", "llama3.1:8b") is True
    assert _model_matches("llama3.1:8b", "llama3.1:8b:latest") is True
    assert _model_matches("llama3.1:8b:latest", "llama3.1:8b") is True
    assert _model_matches("llama3.1:8b", "llama3.1:8b-instruct-q4_0") is False
    assert _model_matches("llama3.1:8b", "llama3.1:70b") is False



# ─── Provider blocks raise LLMError (not retried as "empty text") ─────────────
# Fakes only: no real Gemini/Ollama calls. object.__new__ skips __init__, which
# would need an API key or a running Ollama.
from types import SimpleNamespace
from google.genai import types as genai_types
import ollama
from llm import GeminiLLM, OllamaLLM, LLMError


class FakeGeminiModels:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def fake_gemini(*responses):
    llm = object.__new__(GeminiLLM)
    llm.model = "fake-gemini"
    llm.client = SimpleNamespace(models=FakeGeminiModels(*responses))
    return llm


def gemini_response(text=None, finish_reason=None, block_reason=None):
    parts = [genai_types.Part(text=text)] if text else None
    return genai_types.GenerateContentResponse(
        candidates=[genai_types.Candidate(
            content=genai_types.Content(role="model", parts=parts) if parts else None,
            finish_reason=finish_reason,
        )] if finish_reason or text else None,
        prompt_feedback=genai_types.GenerateContentResponsePromptFeedback(block_reason=block_reason)
        if block_reason else None,
    )


def test_gemini_safety_block_raises_llm_error_without_retry():
    llm = fake_gemini(gemini_response(finish_reason=genai_types.FinishReason.SAFETY))
    with pytest.raises(LLMError, match="SAFETY"):
        llm.generate("s", "u", DraftBuild)
    assert llm.client.models.calls == 1  # a block is final; retrying the same prompt is pointless


def test_gemini_prompt_block_raises_llm_error():
    llm = fake_gemini(gemini_response(block_reason=genai_types.BlockedReason.PROHIBITED_CONTENT))
    with pytest.raises(LLMError, match="PROHIBITED_CONTENT"):
        llm.generate("s", "u", DraftBuild)


def test_gemini_max_tokens_empty_is_still_retried():
    llm = fake_gemini(
        gemini_response(finish_reason=genai_types.FinishReason.MAX_TOKENS),
        gemini_response(text=GOOD, finish_reason=genai_types.FinishReason.STOP),
    )
    r = llm.generate("s", "u", DraftBuild)
    assert r.attempts == 2 and r.parsed.build[0].id == "g1"


def test_ollama_response_error_becomes_llm_error():
    def chat(**kwargs):
        raise ollama.ResponseError("model 'llama3.1:8b' not found", 404)

    llm = object.__new__(OllamaLLM)
    llm.model, llm.num_ctx = "llama3.1:8b", 8192
    llm.client = SimpleNamespace(chat=chat)
    with pytest.raises(LLMError, match="not found"):
        llm.generate("s", "u", DraftBuild)


def test_endpoint_maps_llm_error_to_502(monkeypatch):
    llm = fake_gemini(gemini_response(finish_reason=genai_types.FinishReason.SAFETY))
    monkeypatch.setattr(main, "get_current_llm", lambda: llm)
    response = TestClient(app).post("/debug/draft-build", json={"message": "Build me a PC"})
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "LLMError"
