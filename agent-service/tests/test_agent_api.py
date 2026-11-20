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


# ═══ Day 12: chat with approval, approve, cart, check (written BEFORE the endpoints) ═══
import pytest

from repo import RepoUnavailableError
from safety import RateLimiter

HASH = "a" * 64


@pytest.fixture
def chat_env(monkeypatch):
    """Fake chat backend: the real flow is tested in test_approval.py."""
    seen = {}
    monkeypatch.setattr(main, "get_current_llm", lambda: object())
    monkeypatch.setattr(main, "get_chat_backend", lambda: ("checkpointer", "store"))
    monkeypatch.setattr(main, "chat_limiter", RateLimiter(max_calls=100, per_seconds=60))

    def start_chat(thread_id, message, llm, config, **kw):
        seen["start"] = (thread_id, message)
        return seen.get("start_result", {"status": "awaiting_approval", "thread_id": thread_id, "reply": "ok",
                                          "approval": {"build_hash": HASH, "can_approve": True}})

    def resume_chat(thread_id, build_hash, approved, llm, config, **kw):
        seen["resume"] = (thread_id, build_hash, approved)
        return {"status": seen.get("resume_status", "approved"), "reply": "ok"}

    monkeypatch.setattr(main, "start_chat", start_chat)
    monkeypatch.setattr(main, "resume_chat", resume_chat)
    return seen


def test_chat_returns_awaiting_approval_with_the_payload(chat_env):
    r = client.post("/agent/chat", json={"message": "Gaming PC under 75000", "thread_id": "abc-123"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "awaiting_approval" and body["approval"]["build_hash"] == HASH
    assert chat_env["start"] == ("abc-123", "Gaming PC under 75000")


def test_chat_cleans_the_message_before_the_agent_sees_it(chat_env):
    client.post("/agent/chat", json={"message": "Gaming\x00 PC https://evil.example", "thread_id": "t1"})
    assert chat_env["start"][1] == "Gaming PC [link removed]"


@pytest.mark.parametrize("body", [
    {"message": "x" * 501, "thread_id": "t1"},               # message cap
    {"message": "Gaming PC", "thread_id": "has spaces"},       # thread id format
    {"message": "Gaming PC", "thread_id": "t" * 129},          # thread id cap
    {"message": "\x00\x01 \u200b", "thread_id": "t1"},          # nothing left after cleaning
])
def test_chat_rejects_bad_input(chat_env, body):
    assert client.post("/agent/chat", json=body).status_code == 422


def test_chat_service_failure_is_503(chat_env):
    chat_env["start_result"] = {"status": "error", "reply": "Ollama is down"}
    assert client.post("/agent/chat", json={"message": "Gaming PC", "thread_id": "t1"}).status_code == 503


def test_chat_is_rate_limited(chat_env, monkeypatch):
    monkeypatch.setattr(main, "chat_limiter", RateLimiter(max_calls=2, per_seconds=60))
    codes = [client.post("/agent/chat", json={"message": "Gaming PC", "thread_id": "t1"}).status_code
             for _ in range(3)]
    assert codes == [200, 200, 429]


@pytest.mark.parametrize("status,code", [
    ("approved", 200), ("rejected", 200), ("hash_mismatch", 409), ("no_pending_approval", 409), ("expired", 410),
])
def test_approve_maps_each_outcome_to_an_http_code(chat_env, status, code):
    chat_env["resume_status"] = status
    r = client.post("/agent/approve", json={"thread_id": "t1", "build_hash": HASH, "approved": True})
    assert r.status_code == code
    assert r.json()["status"] == status
    assert chat_env["resume"] == ("t1", HASH, True)


@pytest.mark.parametrize("body", [
    {"thread_id": "t1", "build_hash": "not-a-hash", "approved": True},
    {"thread_id": "t1", "build_hash": HASH},                               # approved is required
    {"thread_id": "t1", "build_hash": HASH, "approved": "yes please"},      # must be a real boolean
])
def test_approve_rejects_bad_input(chat_env, body):
    assert client.post("/agent/approve", json=body).status_code == 422


@pytest.mark.parametrize("status,code", [
    ("added", 200), ("not_approved", 403), ("expired", 410),
    ("already_used", 409), ("build_changed", 409), ("out_of_stock", 409),
])
def test_cart_maps_each_outcome_to_an_http_code(chat_env, monkeypatch, status, code):
    monkeypatch.setattr(main, "get_part_repo", lambda: "repo")
    monkeypatch.setattr(main, "claim_cart", lambda store, repo, thread_id, build_hash: {"status": status})
    r = client.post("/agent/cart", json={"thread_id": "t1", "build_hash": HASH})
    assert r.status_code == code and r.json()["status"] == status


def test_cart_database_outage_is_503_not_added(chat_env, monkeypatch):
    def down():
        raise RepoUnavailableError("MongoDB is unavailable")
    monkeypatch.setattr(main, "get_part_repo", down)
    r = client.post("/agent/cart", json={"thread_id": "t1", "build_hash": HASH})
    assert r.status_code == 503 and r.json()["status"] == "error"


def test_check_returns_the_code_verdict(monkeypatch):
    fake = {"valid": True, "fully_verified": False, "fails": [], "unknowns": ["psu_headroom"], "unresolved": [],
            "rules": {"socket_match": {"verdict": "PASS", "message": "ok"}}, "total_price": 1.0}
    seen = {}

    def run_tool(name, args):
        seen["call"] = (name, args)
        return fake
    monkeypatch.setattr(main, "run_tool", run_tool)
    r = client.post("/agent/check", json={"part_ids": ["p1", "m1"], "partial": True})
    assert r.status_code == 200
    assert r.json()["verdict"]["status"] == "compatible"
    assert seen["call"] == ("check_compatibility", {"part_ids": ["p1", "m1"], "partial": True})


def test_check_fails_safe_when_the_checker_breaks(monkeypatch):
    monkeypatch.setattr(main, "run_tool", lambda name, args: {"error": "the parts database is unavailable"})
    r = client.post("/agent/check", json={"part_ids": ["p1"], "partial": True})
    assert r.status_code == 503
    assert r.json()["verdict"]["status"] == "could_not_verify"


def test_check_caps_the_number_of_parts():
    assert client.post("/agent/check", json={"part_ids": [f"p{i}" for i in range(30)]}).status_code == 422
