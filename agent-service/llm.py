import os
import time
from dataclasses import dataclass
from dotenv import load_dotenv
from google import genai
from google.genai import errors
from ollama import Client, ResponseError
from pydantic import BaseModel, ValidationError
from catalog import extract_budget

load_dotenv()


class LLMError(Exception):
    """Provider problem: blocked, empty, server down."""
    pass


class LLMValidationError(Exception):
    """Still invalid after all retries."""
    def __init__(
        self,
        problems: list[str],
        attempts: int,
        prompt_tokens: int = 0,
        output_tokens: int = 0,
        seconds: float = 0.0,
    ):
        super().__init__(f"AI answer invalid after {attempts} attempts")
        self.problems = problems
        self.attempts = attempts
        self.prompt_tokens = prompt_tokens
        self.output_tokens = output_tokens
        self.seconds = seconds


@dataclass
class Raw:
    text: str
    prompt_tokens: int
    output_tokens: int
    finish_reason: str | None = None


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

    def check_health(self) -> dict:
        raise NotImplementedError

    def generate(
        self,
        system: str,
        user: str,
        schema: type[BaseModel],
        check=None,
        max_retries: int = 2,
        budget_source: str | None = None,
    ) -> LLMResult:
        """
        budget_source: the user's raw request, used ONLY to read the budget with code.
        `user` is often the full prompt (parts list with prices + the request), so it is
        a bad place to look for the budget. If budget_source is None, `user` is used.
        """
        start = time.perf_counter()
        budget_text = budget_source if budget_source is not None else user
        tok_in, tok_out = 0, 0
        prompt = user
        problems = []

        for attempt in range(1, max_retries + 2):
            raw = self._complete(system, prompt, schema)
            tok_in += raw.prompt_tokens
            tok_out += raw.output_tokens
            parsed = None

            if not raw.text or not raw.text.strip():
                # Finding E: Include finish reason in error problem message
                reason_str = f" (finish reason: {raw.finish_reason})" if raw.finish_reason else ""
                problems = [f"Provider returned empty response (no text){reason_str}"]
            else:
                try:
                    parsed = schema.model_validate_json(raw.text)
                    # Finding A: code, not the model, decides the budget.
                    # If the user's words contain no budget, the answer is None even
                    # when the model filled one in: a guessed number must not survive.
                    if hasattr(parsed, "budget"):
                        parsed.budget = extract_budget(budget_text)

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

        # Carry all spent tokens and total elapsed time into the exception
        raise LLMValidationError(
            problems=problems,
            attempts=max_retries + 1,
            prompt_tokens=tok_in,
            output_tokens=tok_out,
            seconds=round(time.perf_counter() - start, 2),
        )


# Gemini finish reasons that mean "the provider refused", not "try again".
GEMINI_BLOCK_FINISH_REASONS = {
    "SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION",
    "IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT",
}


def _enum_name(value) -> str | None:
    """FinishReason.SAFETY -> 'SAFETY'; plain strings pass through; None stays None."""
    if value is None:
        return None
    return getattr(value, "name", None) or str(value).split(".")[-1]


class GeminiLLM(BaseLLM):
    provider = "gemini"

    def __init__(self):
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable is missing")
        self.client = genai.Client(api_key=key)

    def check_health(self) -> dict:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable is missing")
        return {"status": "ok", "provider": self.provider, "model": self.model}

    def _complete(self, system: str, user: str, schema: type[BaseModel]) -> Raw:
        # Finding B: Short retry with backoff for transient 503 / 429 overloads
        resp = None
        for retry_attempt in range(3):
            try:
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
                break
            except errors.APIError as e:
                if e.code in (503, 429) and retry_attempt < 2:
                    wait_time = (retry_attempt + 1) * 2  # 2s, 4s
                    time.sleep(wait_time)
                    continue
                raise

        u = getattr(resp, "usage_metadata", None)
        prompt_tokens = getattr(u, "prompt_token_count", 0) or 0
        output_tokens = getattr(u, "candidates_token_count", 0) or 0

        # A blocked prompt or answer is final: sending the same prompt again gets
        # blocked again, so raise LLMError instead of returning "" to be retried.
        # (An empty answer cut off by MAX_TOKENS is different: that one IS retried.)
        block_reason = _enum_name(getattr(getattr(resp, "prompt_feedback", None), "block_reason", None))
        if block_reason and block_reason != "BLOCKED_REASON_UNSPECIFIED":
            raise LLMError(f"Gemini blocked the prompt (block_reason: {block_reason})")

        finish_reason = "STOP"
        try:
            if resp and resp.candidates and len(resp.candidates) > 0:
                finish_reason = _enum_name(getattr(resp.candidates[0], "finish_reason", None)) or "STOP"
        except Exception:
            pass
        if finish_reason in GEMINI_BLOCK_FINISH_REASONS:
            raise LLMError(f"Gemini blocked the answer (finish_reason: {finish_reason})")

        if not resp or not resp.text:
            return Raw(
                text="",
                prompt_tokens=prompt_tokens,
                output_tokens=output_tokens,
                finish_reason=str(finish_reason),
            )

        return Raw(
            text=resp.text,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            finish_reason=str(finish_reason),
        )


def _normalize_tag(name: str) -> str:
    """Normalize model tag: 'llama3.1:8b:latest' or 'llama3.1:8b'."""
    return name[:-7] if name.endswith(":latest") else name


def _model_matches(configured: str, candidate: str) -> bool:
    """Check exact match, allowing :latest tag variance."""
    if configured == candidate:
        return True
    return _normalize_tag(configured) == _normalize_tag(candidate)


class OllamaLLM(BaseLLM):
    provider = "ollama"

    def __init__(self):
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
        self.client = Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))

    def check_health(self) -> dict:
        # Finding D: Compare exact names, allowing :latest
        models_info = self.client.list()
        pulled = [m.model for m in getattr(models_info, "models", [])]
        found = any(_model_matches(self.model, name) for name in pulled)
        if not found:
            raise ValueError(f"Model '{self.model}' is not pulled in Ollama. Available: {pulled}")
        return {"status": "ok", "provider": self.provider, "model": self.model}

    def _complete(self, system: str, user: str, schema: type[BaseModel]) -> Raw:
        try:
            resp = self.client.chat(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                format=schema.model_json_schema(),
                options={"temperature": 0, "num_ctx": self.num_ctx},
            )
        except ResponseError as e:
            # Ollama answered with an error (e.g. model not pulled). Connection
            # failures are a different exception and still map to 503 in main.py.
            raise LLMError(f"Ollama error (status {e.status_code}): {e.error}") from e
        if not resp.message or not resp.message.content:
            return Raw(
                text="",
                prompt_tokens=resp.prompt_eval_count or 0,
                output_tokens=resp.eval_count or 0,
            )
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
