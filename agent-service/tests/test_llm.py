import pytest
from llm import get_llm, OllamaLLM, GeminiLLM, LLMError


def test_get_llm_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic_claude")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER 'anthropic_claude'"):
        get_llm()


def test_get_llm_ollama_stub(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    llm = get_llm()
    assert isinstance(llm, OllamaLLM)
    assert llm.provider == "ollama"

    with pytest.raises(NotImplementedError, match="Ollama is added on Day 4"):
        llm.generate("system prompt", "user query", None)


def test_gemini_missing_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is missing"):
        get_llm()
