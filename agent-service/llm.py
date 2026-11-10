import os
import time
from dataclasses import dataclass
from dotenv import load_dotenv
from google import genai
from ollama import Client
from pydantic import BaseModel, ValidationError

load_dotenv()


class LLMError(Exception):
    """Provider problem: blocked, empty, server down."""
    pass


class LLMValidationError(Exception):
    """Still invalid after all retries."""
    def __init__(self, problems: list[str], attempts: int):
        super().__init__(f"AI answer invalid after {attempts} attempts")
        self.problems = problems
        self.attempts = attempts


@dataclass
class Raw:
    text: str
    prompt_tokens: int
    output_tokens: int


@dataclass
class LLMResult:
    parsed: BaseModel
    provider: str
    model: str
    prompt_tokens: int  # summed over ALL attempts
    output_tokens: int
    seconds: float
    attempts: int = 1


class BaseLLM:
    provider = "base"
    model = ""

    def _complete(self, system: str, user: str, schema: type[BaseModel]) -> Raw:
        # Each provider implements this
        raise NotImplementedError

    def generate(self, system: str, user: str, schema: type[BaseModel], check=None, max_retries: int = 2) -> LLMResult:
        start = time.perf_counter()
        tok_in, tok_out = 0, 0
        prompt = user
        for attempt in range(1, max_retries + 2):
            raw = self._complete(system, prompt, schema)
            tok_in += raw.prompt_tokens
            tok_out += raw.output_tokens
            parsed = None
            try:
                parsed = schema.model_validate_json(raw.text)
                problems = check(parsed) if check else []
            except ValidationError as e:
                problems = [
                    f"{'.'.join(map(str, x['loc']))}: {x['msg']}"
                    for x in e.errors(include_url=False, include_context=False)
                ]
            if not problems:
                return LLMResult(
                    parsed=parsed,
                    provider=self.provider,
                    model=self.model,
                    prompt_tokens=tok_in,
                    output_tokens=tok_out,
                    seconds=round(time.perf_counter() - start, 2),
                    attempts=attempt,
                )
            prompt = (
                f"{user}\n\nYour previous answer was rejected:\n- "
                + "\n- ".join(problems)
                + f"\n\nPrevious answer:\n{raw.text[:1500]}\n\nReturn a corrected JSON answer."
            )
        raise LLMValidationError(problems, max_retries + 1)


class GeminiLLM(BaseLLM):
    provider = "gemini"

    def __init__(self):
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable is missing")
        self.client = genai.Client(api_key=key)

    def _complete(self, system: str, user: str, schema: type[BaseModel]) -> Raw:
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
            finish_reason = "UNKNOWN"
            try:
                if resp.candidates and len(resp.candidates) > 0:
                    finish_reason = getattr(resp.candidates[0], "finish_reason", "UNKNOWN")
            except Exception:
                pass
            raise LLMError(f"Gemini returned no text (blocked or cut off). Finish reason: {finish_reason}")

        u = resp.usage_metadata
        return Raw(
            text=resp.text,
            prompt_tokens=getattr(u, "prompt_token_count", 0) or 0,
            output_tokens=getattr(u, "candidates_token_count", 0) or 0,
        )


class OllamaLLM(BaseLLM):
    provider = "ollama"

    def __init__(self):
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
        self.client = Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))

    def _complete(self, system: str, user: str, schema: type[BaseModel]) -> Raw:
        try:
            resp = self.client.chat(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                format=schema.model_json_schema(),
                think=False,
                options={"temperature": 0, "num_ctx": self.num_ctx},
            )
        except TypeError:
            resp = self.client.chat(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                format=schema.model_json_schema(),
                options={"temperature": 0, "num_ctx": self.num_ctx},
            )
        if not resp.message or not resp.message.content:
            raise LLMError("Ollama returned no text")
        return Raw(
            text=resp.message.content,
            prompt_tokens=resp.prompt_eval_count or 0,
            output_tokens=resp.eval_count or 0,
        )


def get_llm():
    name = os.getenv("LLM_PROVIDER", "gemini").lower()
    if name == "gemini":
        return GeminiLLM()
    if name == "ollama":
        return OllamaLLM()
    raise ValueError(f"Unknown LLM_PROVIDER '{name}' (use gemini or ollama)")
