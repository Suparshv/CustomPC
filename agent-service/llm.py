import os
import time
from dataclasses import dataclass
from typing import TypeVar
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

load_dotenv()
T = TypeVar("T", bound=BaseModel)

class LLMError(Exception):
    pass

@dataclass
class LLMResult:
    parsed: BaseModel
    provider: str
    model: str
    prompt_tokens: int
    output_tokens: int
    seconds: float

class GeminiLLM:
    provider = "gemini"

    def __init__(self):
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing")
        self.client = genai.Client(api_key=api_key)

    def generate(self, system: str, user: str, schema: type[T]) -> LLMResult:
        start = time.perf_counter()
        resp = self.client.models.generate_content(
            model=self.model,
            contents=user,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0,
            },
        )
        if not resp.text:
            raise LLMError("Gemini returned no text (blocked or cut off)")

        parsed = schema.model_validate_json(resp.text)  # runs YOUR validators
        u = resp.usage_metadata
        prompt_tokens = getattr(u, "prompt_token_count", 0) or 0
        output_tokens = getattr(u, "candidates_token_count", 0) or 0

        return LLMResult(
            parsed=parsed,
            provider=self.provider,
            model=self.model,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            seconds=round(time.perf_counter() - start, 2),
        )

class OllamaLLM:
    provider = "ollama"

    def generate(self, system, user, schema):
        raise NotImplementedError("Ollama is added on Day 4")

def get_llm():
    name = os.getenv("LLM_PROVIDER", "gemini").lower()
    if name == "gemini":
        return GeminiLLM()
    if name == "ollama":
        return OllamaLLM()
    raise ValueError(f"Unknown LLM_PROVIDER '{name}' (use gemini or ollama)")
