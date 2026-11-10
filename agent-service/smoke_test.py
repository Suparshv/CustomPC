import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure agent-service directory is in pythonpath
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

load_dotenv()

from llm import get_llm, LLMError, LLMValidationError
from schemas import DraftBuild
from catalog import check_build
from prompts import ARCHITECT_SYSTEM, format_architect_user_prompt


def run_smoke_test(prompts_path: Path = None):
    if prompts_path is None:
        prompts_path = current_dir / "tests" / "smoke_prompts.txt"
        if not prompts_path.exists():
            prompts_path = Path("agent-service") / "tests" / "smoke_prompts.txt"

    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts = [line.strip() for line in f if line.strip()]

    llm = get_llm()
    provider = llm.provider
    model = getattr(llm, "model", "unknown")

    print("=" * 60)
    print(f"Running Smoke Test: Provider={provider}, Model={model}")
    print(f"Total Prompts: {len(prompts)}")
    print("=" * 60)

    total_prompts = len(prompts)
    valid_count = 0
    first_try_valid_count = 0
    total_tokens = 0
    total_seconds = 0.0
    total_attempts = 0

    results = []

    for i, prompt in enumerate(prompts, start=1):
        print(f"[{i:02d}/{total_prompts:02d}] \"{prompt[:45]}...\"", end=" ", flush=True)
        user_prompt = format_architect_user_prompt(prompt)
        start_time = time.perf_counter()
        is_valid = False
        first_try = False
        attempts = 1
        tokens = 0
        error_msg = None

        try:
            res = llm.generate(
                ARCHITECT_SYSTEM,
                user_prompt,
                DraftBuild,
                check=check_build,
            )
            is_valid = True
            attempts = res.attempts
            first_try = (attempts == 1)
            tokens = res.prompt_tokens + res.output_tokens
            elapsed = res.seconds
            print(f"-> VALID (attempts: {attempts}, tokens: {tokens}, time: {elapsed}s)")
        except LLMValidationError as e:
            elapsed = round(time.perf_counter() - start_time, 2)
            attempts = e.attempts
            error_msg = f"Validation failed after {e.attempts} attempts: {e.problems}"
            print(f"-> FAILED (attempts: {attempts}, error: {e.problems[:1]})")
        except LLMError as e:
            elapsed = round(time.perf_counter() - start_time, 2)
            error_msg = f"LLM Error: {str(e)}"
            print(f"-> LLM ERROR: {str(e)[:40]}")
        except Exception as e:
            elapsed = round(time.perf_counter() - start_time, 2)
            error_msg = f"Unexpected Error: {str(e)}"
            print(f"-> UNEXPECTED ERROR: {str(e)[:40]}")

        if is_valid:
            valid_count += 1
            if first_try:
                first_try_valid_count += 1

        total_attempts += attempts
        total_tokens += tokens
        total_seconds += elapsed

        results.append({
            "id": i,
            "prompt": prompt,
            "valid": is_valid,
            "first_try_valid": first_try,
            "attempts": attempts,
            "tokens": tokens,
            "seconds": elapsed,
            "error": error_msg,
        })

        # Gemini rate pacing
        if provider == "gemini" and i < total_prompts:
            time.sleep(8)
        elif provider == "ollama" and i < total_prompts:
            time.sleep(0.5)

    valid_rate = (valid_count / total_prompts) * 100
    first_try_rate = (first_try_valid_count / total_prompts) * 100
    avg_attempts = total_attempts / total_prompts
    avg_tokens = total_tokens / total_prompts
    avg_seconds = total_seconds / total_prompts

    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    print(f"Provider:                {provider}")
    print(f"Model:                   {model}")
    print(f"Valid Build Rate:        {valid_count}/{total_prompts} ({valid_rate:.1f}%)")
    print(f"First-Try Valid Rate:    {first_try_valid_count}/{total_prompts} ({first_try_rate:.1f}%)")
    print(f"Average Attempts:        {avg_attempts:.2f}")
    print(f"Total Tokens:            {total_tokens} (avg {avg_tokens:.1f}/req)")
    print(f"Total Elapsed Time:      {total_seconds:.2f}s (avg {avg_seconds:.2f}s/req)")
    print("=" * 60)

    return {
        "provider": provider,
        "model": model,
        "total_prompts": total_prompts,
        "valid_count": valid_count,
        "valid_rate": valid_rate,
        "first_try_valid_count": first_try_valid_count,
        "first_try_rate": first_try_rate,
        "avg_attempts": avg_attempts,
        "total_tokens": total_tokens,
        "avg_tokens": avg_tokens,
        "total_seconds": total_seconds,
        "avg_seconds": avg_seconds,
        "results": results,
    }


if __name__ == "__main__":
    run_smoke_test()
