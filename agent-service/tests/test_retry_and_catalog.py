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


def test_gives_up_after_three_attempts():
    with pytest.raises(LLMValidationError):
        Fake(BAD, BAD, BAD).generate("s", "u", DraftBuild)


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
