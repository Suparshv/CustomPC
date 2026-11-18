"""
test_embeddings.py - Ollama connection tests (no real Ollama needed).

Why these exist (found 18 Nov from the Day 9 eval run): every search opened a NEW
connection to "localhost". On Windows, "localhost" tries IPv6 (::1) first; Ollama
only listens on IPv4, so each new connection waited ~2 s before falling back.
Measured: ~2,100 ms per embedding via localhost vs ~50 ms via 127.0.0.1.
"""

import pytest

import embeddings
import llm


class _FakeOllamaClient:
    """Stands in for ollama.Client and records every connection that gets created."""
    created = []

    def __init__(self, host=None, **kwargs):
        self.host = host
        _FakeOllamaClient.created.append(host)

    def embed(self, model, input, keep_alive=None):
        return {"embeddings": [[0.1, 0.2] for _ in input]}


@pytest.fixture
def fake_ollama(monkeypatch):
    _FakeOllamaClient.created = []
    monkeypatch.setattr(embeddings.ollama, "Client", _FakeOllamaClient)
    # Start every test with an empty connection cache.
    monkeypatch.setattr(embeddings, "_CLIENTS", {}, raising=False)
    return _FakeOllamaClient


def test_many_searches_reuse_one_connection(fake_ollama, monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    for q in ["B650", "B550", "RTX 4060"]:
        embeddings.embed_query(q)
    assert len(fake_ollama.created) == 1


def test_default_ollama_host_is_ipv4(fake_ollama, monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    embeddings.embed_query("B650")
    assert fake_ollama.created == ["http://127.0.0.1:11434"]


def test_ollama_host_from_env_is_still_respected(fake_ollama, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://10.0.0.5:11434")
    embeddings.embed_query("B650")
    assert fake_ollama.created == ["http://10.0.0.5:11434"]


def test_chat_model_default_host_is_ipv4(monkeypatch):
    """The Ollama chat model (llm.py) had the same 'localhost' default."""
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr(llm, "Client", _FakeOllamaClient)
    _FakeOllamaClient.created = []
    llm.OllamaLLM()
    assert _FakeOllamaClient.created == ["http://127.0.0.1:11434"]
