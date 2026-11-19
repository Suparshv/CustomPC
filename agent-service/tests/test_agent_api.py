"""
POST /agent/build - the HTTP door to the Day 10 agent (needed for Day 12's Approve button).
Written BEFORE the endpoint existed. The agent itself is faked: these tests check the HTTP layer.
"""

from fastapi.testclient import TestClient

import main
from agent_config import AgentConfig

client = TestClient(main.app)


def _fake_agent(status="valid"):
    seen = {}

    def run_agent(message, llm, config, **kwargs):
        seen["message"], seen["config"] = message, config
        return {"status": status, "reply": "ok", "picks": {}, "total_price": 70000.0}

    return run_agent, seen


def test_agent_endpoint_returns_the_agent_result(monkeypatch):
    fake, seen = _fake_agent()
    monkeypatch.setattr(main, "run_agent", fake)
    monkeypatch.setattr(main, "get_current_llm", lambda: object())

    r = client.post("/agent/build", json={"message": "Gaming PC under 75000"})
    assert r.status_code == 200
    assert r.json()["status"] == "valid"
    assert seen["message"] == "Gaming PC under 75000"
    assert isinstance(seen["config"], AgentConfig)


def test_agent_endpoint_applies_switch_overrides(monkeypatch):
    fake, seen = _fake_agent()
    monkeypatch.setattr(main, "run_agent", fake)
    monkeypatch.setattr(main, "get_current_llm", lambda: object())

    client.post("/agent/build", json={"message": "Gaming PC", "overrides": {"use_checker": False, "repair_loops": 0}})
    assert seen["config"].use_checker is False and seen["config"].repair_loops == 0


def test_agent_endpoint_rejects_bad_switches(monkeypatch):
    monkeypatch.setattr(main, "get_current_llm", lambda: object())
    r = client.post("/agent/build", json={"message": "Gaming PC", "overrides": {"repair_loops": 5}})
    assert r.status_code == 422
    r = client.post("/agent/build", json={"message": "Gaming PC", "overrides": {"turbo": True}})
    assert r.status_code == 422


def test_honest_no_valid_build_is_a_normal_200_answer(monkeypatch):
    fake, _ = _fake_agent(status="no_valid_build")
    monkeypatch.setattr(main, "run_agent", fake)
    monkeypatch.setattr(main, "get_current_llm", lambda: object())
    r = client.post("/agent/build", json={"message": "RTX 5080 PC for 15000"})
    assert r.status_code == 200
    assert r.json()["status"] == "no_valid_build"


def test_a_service_failure_is_503_with_the_details(monkeypatch):
    fake, _ = _fake_agent(status="error")
    monkeypatch.setattr(main, "run_agent", fake)
    monkeypatch.setattr(main, "get_current_llm", lambda: object())
    r = client.post("/agent/build", json={"message": "Gaming PC"})
    assert r.status_code == 503
    assert r.json()["status"] == "error"


def test_llm_not_configured_is_503(monkeypatch):
    def no_llm():
        raise ValueError("GEMINI_API_KEY environment variable is missing")
    monkeypatch.setattr(main, "get_current_llm", no_llm)
    r = client.post("/agent/build", json={"message": "Gaming PC"})
    assert r.status_code == 503


def test_message_is_length_capped():
    assert client.post("/agent/build", json={"message": "x" * 501}).status_code == 422


def test_answer_says_which_ai_model_produced_it(monkeypatch):
    from types import SimpleNamespace
    fake, _ = _fake_agent()
    monkeypatch.setattr(main, "run_agent", fake)
    monkeypatch.setattr(main, "get_current_llm", lambda: SimpleNamespace(provider="ollama", model="llama3.1:8b"))
    body = client.post("/agent/build", json={"message": "Gaming PC"}).json()
    assert (body["provider"], body["model"]) == ("ollama", "llama3.1:8b")
