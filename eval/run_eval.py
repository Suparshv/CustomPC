"""
run_eval.py - The Resilient Evaluation Runner

Features:
  1. Auto-Resume: Saves after every request to eval/results.jsonl. If stopped, resumes seamlessly.
  2. Rate-Limit Backoff: If a 429 / rate limit / 500 error occurs, pauses with progressive backoff (50s, 65s...) and retries automatically.
  3. Paced Timing: Paces requests (~16s) to safely stay under Gemini's 15 Requests-Per-Minute free-tier cap.
  4. Robust Spec Lookup: Supports matching parts by both database ID (e.g. 'p1') and full product name.
  5. Accurate Metrics: Follows exact eval instructions (no FAIL + all 9 categories = valid build; success rate = valid + within budget).

Usage:
  1. Make sure backend is running on port 5000: cd backend && npm start
  2. Make sure ChromaDB is running on port 8000: docker run -p 8000:8000 chromadb/chroma
  3. Run: python eval/run_eval.py
"""

import json
import os
import sys
import time
import uuid
import datetime

# Force UTF-8 encoding on Windows to prevent console Unicode crashes
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Add parent dir so we can import compat.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent-service"))
from compat import judge_build, find_spec, ALL_SPECS, REQUIRED_CATEGORIES

try:
    import requests as http_requests
except ImportError:
    print("ERROR: 'requests' library not found. Install it with: pip install requests")
    sys.exit(1)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def pct(num, denom):
    """Safe percentage. Returns measured number only, no rounding up."""
    if denom == 0:
        return "N/A"
    return f"{round((num / denom) * 100, 1)}%"


# ─── Config ───────────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:5000/api/chat/builder"
REQUESTS_PATH = os.path.join(os.path.dirname(__file__), "requests.jsonl")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.jsonl")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
EVAL_MD_PATH = os.path.join(DOCS_DIR, "eval-v1.md")

# 1 build request triggers up to 4 agents (Supervisor + Architect + Critic + Reviewer).
# 16s wait ensures we stay safely below Gemini's 15 Requests-Per-Minute limit.
WAIT_SECONDS = 16
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 50


# ─── Load Existing Results (For Resume Support) ──────────────────────────────
completed_results = {}
if os.path.exists(RESULTS_PATH):
    try:
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    # Only treat as completed if it was actually successful
                    if item.get("success") is True and not item.get("score", {}).get("errored"):
                        completed_results[item["id"]] = item
        if completed_results:
            print(f" Resuming! Found {len(completed_results)} previously successful test requests in results.jsonl")
    except Exception as e:
        print(f"Notice: Could not parse existing results.jsonl ({e}), starting fresh.")
        completed_results = {}


# ─── Load the 30 requests ────────────────────────────────────────────────────
with open(REQUESTS_PATH, "r", encoding="utf-8") as f:
    test_requests = [json.loads(line) for line in f if line.strip()]

print(f"\n{'='*60}")
print(f"  EVALUATION RUNNER - {len(test_requests)} requests total")
print(f"  Backend: {BACKEND_URL}")
print(f"  Pacing: {WAIT_SECONDS}s wait between requests (avoids 15 RPM cap)")
print(f"{'='*60}\n")


def execute_request_with_retries(req_text, base_session_id):
    """
    Executes a request to backend, automatically retrying if rate limits occur.
    Uses unique session ID per attempt to prevent conversation state pollution.
    """
    start_time = time.time()
    for attempt in range(1, MAX_RETRIES + 1):
        session_id = f"{base_session_id}-try{attempt}"
        try:
            resp = http_requests.post(
                BACKEND_URL,
                json={"message": req_text, "sessionId": session_id},
                timeout=120,
            )
            elapsed = round(time.time() - start_time, 2)

            # Safely parse JSON
            try:
                data = resp.json()
            except Exception:
                data = {"error": f"Invalid JSON response (HTTP {resp.status_code}): {resp.text[:100]}"}

            # If backend returned an error
            if resp.status_code != 200 or "error" in data:
                err_msg = data.get("error", f"HTTP {resp.status_code}")
                print(f"    [Warning] Server returned error: {err_msg}")

                # If it's a permanent route/auth error (e.g. 404 Not Found), don't waste time retrying
                if resp.status_code in [400, 401, 403, 404]:
                    return False, f"Permanent error {err_msg}", elapsed, data

                if attempt < MAX_RETRIES:
                    backoff = BASE_BACKOFF_SECONDS + (attempt - 1) * 15
                    print(f"    Rate limit or server busy. Waiting {backoff}s for window reset before retry #{attempt+1}...")
                    time.sleep(backoff)
                    continue
                return False, err_msg, elapsed, data

            return True, None, elapsed, data
        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            if attempt < MAX_RETRIES:
                backoff = BASE_BACKOFF_SECONDS + (attempt - 1) * 15
                print(f"    [Network/Timeout Error]: {e}. Waiting {backoff}s before retry #{attempt+1}...")
                time.sleep(backoff)
            else:
                return False, str(e), elapsed, {}
    return False, "Max retries exceeded", round(time.time() - start_time, 2), {}


# ─── Run Requests ────────────────────────────────────────────────────────────
results = []

for i, req in enumerate(test_requests):
    req_id = req["id"]
    req_text = req["text"]
    req_budget = req.get("budget")
    req_type = req["type"]

    # If already done successfully previously, reuse existing result
    if req_id in completed_results:
        print(f"[{i+1}/{len(test_requests)}] id={req_id} [CACHED] Skipping.")
        results.append(completed_results[req_id])
        continue

    base_session_id = f"eval-{uuid.uuid4().hex[:8]}"
    print(f"[{i+1}/{len(test_requests)}] id={req_id} type={req_type}")
    print(f"  Prompt: \"{req_text}\"")

    success, error_msg, elapsed, data = execute_request_with_retries(req_text, base_session_id)

    reply = data.get("reply", "")
    build = data.get("build", None)
    critique = data.get("critique", None)
    reviews = data.get("reviews", None)
    comparison_data = data.get("comparisonData", None)
    token_log = data.get("tokenLog", [])

    # Calculate token totals safely
    total_prompt_tokens = 0
    total_candidate_tokens = 0
    for entry in token_log:
        if isinstance(entry, dict):
            tokens = entry.get("tokens") or {}
            if isinstance(tokens, dict):
                total_prompt_tokens += tokens.get("promptTokenCount") or 0
                total_candidate_tokens += tokens.get("candidatesTokenCount") or 0
    total_tokens = total_prompt_tokens + total_candidate_tokens

    # Score
    score = {}

    if not success:
        score["errored"] = True
        score["valid"] = False
        print(f"  [Skip scoring] Request failed after {MAX_RETRIES} retries. Error: {error_msg}")

    elif req_type == "normal_build":
        if build and isinstance(build, list) and len(build) > 0:
            part_names = []
            for item in build:
                part_id = item.get("id", "") if isinstance(item, dict) else str(item)
                spec = find_spec(part_id)
                if spec:
                    part_names.append(spec["name"])

            judge_results = judge_build(part_names, req_budget)

            has_all_9 = judge_results.get("1_all_categories", ("", ""))[0] == "PASS"
            has_fail = any(v[0] == "FAIL" for v in judge_results.values())
            has_unknown = any(v[0] == "UNKNOWN" for v in judge_results.values())

            # Rule: Valid-build % = replies with no FAIL and all 9 categories
            is_valid = has_all_9 and not has_fail

            score["produced_build"] = True
            score["valid"] = is_valid
            score["has_fail"] = has_fail
            score["has_unknown"] = has_unknown
            score["judge_details"] = {k: v[0] for k, v in judge_results.items()}
        else:
            score["produced_build"] = False
            score["valid"] = False
            score["refused"] = True

    elif req_type == "comparison":
        score["handled_correctly"] = bool(comparison_data is not None or (reply and "compar" in reply.lower()))

    elif req_type == "impossible":
        # Handled correctly if refused, or if critique flagged fatal issues, or warning in reply
        reply_lower = reply.lower() if reply else ""
        has_warning = any(w in reply_lower for w in ["cannot", "exceed", "impossible", "not compatible", "too low", "budget", "mismatch", "incompatible"])
        if build and isinstance(build, list) and len(build) > 0:
            critic_flagged = bool(critique and critique.get("approved") is False)
            score["handled_correctly"] = critic_flagged or has_warning
        else:
            score["handled_correctly"] = True

    elif req_type == "off_topic":
        # Handled correctly if no PC build was produced
        score["handled_correctly"] = bool(build is None or (isinstance(build, list) and len(build) == 0))

    elif req_type == "vague":
        # Correct if the AI replied with a coherent message or suggested build
        score["handled_correctly"] = bool(reply and len(reply.strip()) > 20)

    result = {
        "id": req_id,
        "type": req_type,
        "text": req_text,
        "budget": req_budget,
        "success": success,
        "error": error_msg,
        "elapsed_s": elapsed,
        "reply_preview": reply[:200] if reply else "",
        "build_count": len(build) if (build and isinstance(build, list)) else 0,
        "total_tokens": total_tokens,
        "prompt_tokens": total_prompt_tokens,
        "candidate_tokens": total_candidate_tokens,
        "score": score,
    }
    results.append(result)

    # Append incrementally to disk so progress is NEVER lost
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    status_str = "PASS" if score.get("valid") or score.get("handled_correctly") else "FAIL"
    print(f"  -> {elapsed}s | {total_tokens} tokens | {status_str}")
    print()

    # Rate limit pacing wait
    if i < len(test_requests) - 1:
        print(f"  Pacing wait {WAIT_SECONDS}s to respect 15 RPM limit...")
        time.sleep(WAIT_SECONDS)


# ─── Deduplicate and rewrite results.jsonl clean ──────────────────────────────
with open(RESULTS_PATH, "w", encoding="utf-8") as f:
    for r in sorted(results, key=lambda x: x["id"]):
        f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ─── Compute Aggregate Scores ────────────────────────────────────────────────
build_requests = [r for r in results if r["type"] == "normal_build"]
comparison_requests = [r for r in results if r["type"] == "comparison"]
impossible_requests = [r for r in results if r["type"] == "impossible"]
offtopic_requests = [r for r in results if r["type"] == "off_topic"]
vague_requests = [r for r in results if r["type"] == "vague"]

# Exclude hard-errored results from scoring (API failure != refusal)
build_requests_scored = [r for r in build_requests if not r["score"].get("errored")]

builds_produced = [r for r in build_requests_scored if r["score"].get("produced_build")]
builds_valid = [r for r in build_requests_scored if r["score"].get("valid")]

# Builds with a budget specified
builds_with_budget = [r for r in builds_produced if r.get("budget") is not None]
builds_budget_pass = [r for r in builds_with_budget if r["score"].get("judge_details", {}).get("6_within_budget") == "PASS"]

builds_refused = [r for r in build_requests_scored if r["score"].get("refused")]
builds_unknown = [r for r in build_requests_scored if r["score"].get("has_unknown")]

# Success rate = valid AND within budget (or no budget constraint), out of all build requests
builds_successful = [
    r for r in build_requests_scored
    if r["score"].get("valid") and (r.get("budget") is None or r["score"].get("judge_details", {}).get("6_within_budget") == "PASS")
]

comparisons_correct = [r for r in comparison_requests if r["score"].get("handled_correctly")]
impossible_correct = [r for r in impossible_requests if r["score"].get("handled_correctly")]
offtopic_correct = [r for r in offtopic_requests if r["score"].get("handled_correctly")]
vague_correct = [r for r in vague_requests if r["score"].get("handled_correctly")]

total_time = sum(r["elapsed_s"] for r in results)
avg_time = round(total_time / len(results), 2) if results else 0
total_all_tokens = sum(r["total_tokens"] for r in results)
avg_tokens = round(total_all_tokens / len(results)) if results else 0

valid_build_rate = pct(len(builds_valid), len(build_requests))
budget_hit_rate = pct(len(builds_budget_pass), len(builds_with_budget))
success_rate = pct(len(builds_successful), len(build_requests))
refusal_rate = pct(len(builds_refused), len(build_requests))
unknown_rate = pct(len(builds_unknown), len(build_requests))


# ─── Print scorecard ─────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  FINAL SCORECARD")
print(f"{'='*60}")
print(f"  Build requests:        {len(build_requests)}")
print(f"    Produced a build:    {len(builds_produced)}")
print(f"    Valid builds:        {len(builds_valid)} ({valid_build_rate})")
print(f"    Within budget:       {len(builds_budget_pass)}/{len(builds_with_budget)} ({budget_hit_rate})")
print(f"    Success rate:        {len(builds_successful)}/{len(build_requests)} ({success_rate})")
print(f"    Refused:             {len(builds_refused)} ({refusal_rate})")
print(f"    Had UNKNOWN checks:  {len(builds_unknown)} ({unknown_rate})")
print(f"  Comparisons correct:   {len(comparisons_correct)}/{len(comparison_requests)}")
print(f"  Impossible correct:    {len(impossible_correct)}/{len(impossible_requests)}")
print(f"  Off-topic correct:     {len(offtopic_correct)}/{len(offtopic_requests)}")
print(f"  Vague correct:         {len(vague_correct)}/{len(vague_requests)}")
print(f"  Avg time/request:      {avg_time}s")
print(f"  Avg tokens/request:    {avg_tokens}")
print(f"{'='*60}")


# ─── Generate docs/eval-v1.md ────────────────────────────────────────────────
os.makedirs(DOCS_DIR, exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

eval_md = f"""# Evaluation Report: v1-baseline

> Measured on {len(test_requests)} fixed test requests on {timestamp}.
> This is a small sample. Results describe this specific test set, not general accuracy.

## Summary Table

| Metric | Value |
|--------|-------|
| Valid builds (no FAIL, all 9 categories) | {valid_build_rate} ({len(builds_valid)}/{len(build_requests)}) |
| Within budget (among budgeted builds) | {budget_hit_rate} ({len(builds_budget_pass)}/{len(builds_with_budget)}) |
| Refusal rate (build requests declined) | {refusal_rate} ({len(builds_refused)}/{len(build_requests)}) |
| Unknown rate (missing data for checks) | {unknown_rate} ({len(builds_unknown)}/{len(build_requests)}) |
| Comparisons handled correctly | {pct(len(comparisons_correct), len(comparison_requests))} ({len(comparisons_correct)}/{len(comparison_requests)}) |
| Impossible requests handled correctly | {pct(len(impossible_correct), len(impossible_requests))} ({len(impossible_correct)}/{len(impossible_requests)}) |
| Off-topic requests handled correctly | {pct(len(offtopic_correct), len(offtopic_requests))} ({len(offtopic_correct)}/{len(offtopic_requests)}) |
| Vague requests handled correctly | {pct(len(vague_correct), len(vague_requests))} ({len(vague_correct)}/{len(vague_requests)}) |
| Avg time per request | {avg_time}s |
| Avg tokens per request | {avg_tokens} |
| Total tokens used | {total_all_tokens} |

## Three Key Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Success rate** | {success_rate} | Valid and compatible builds within budget, out of all build requests |
| **Refusal rate** | {refusal_rate} | How often the system declined a build request |
| **Unknown rate** | {unknown_rate} | Checks that could not run due to missing spec data |

## Per-Request Breakdown

| ID | Type | Budget | Time | Tokens | Result | Details |
|----|------|--------|------|--------|--------|---------|
"""

for r in results:
    budget_str = f"Rs.{r['budget']:,}" if r.get("budget") else "-"

    if r["type"] == "normal_build":
        if r["score"].get("valid"):
            result_str = "PASS"
            details = "All categories present, no compatibility failures"
        elif r["score"].get("refused"):
            result_str = "REFUSED"
            details = "No build produced"
        elif r["score"].get("errored"):
            result_str = "ERROR"
            details = r.get("error", "API request failed")[:60]
        else:
            fails = [k for k, v in r["score"].get("judge_details", {}).items() if v == "FAIL"]
            result_str = "FAIL"
            details = ", ".join(fails) if fails else "Build produced but invalid"
    elif r["type"] in ["comparison", "impossible", "off_topic", "vague"]:
        correct = r["score"].get("handled_correctly", False)
        result_str = "CORRECT" if correct else "INCORRECT"
        details = r["reply_preview"][:80] if r["reply_preview"] else "-"
    else:
        result_str = "?"
        details = "-"

    eval_md += f"| {r['id']} | {r['type']} | {budget_str} | {r['elapsed_s']}s | {r['total_tokens']} | {result_str} | {details} |\n"

eval_md += f"""
## Notes

- **Model**: Gemini 3.5 Flash Lite via `@google/genai` SDK
- **Architecture**: LangGraph multi-agent (Supervisor, Architect, Critic, Reviewer, Comparator)
- **RAG**: ChromaDB vector database (Docker)
- **Function Calling**: Strict mode (`toolConfig.functionCallingConfig.mode: "ANY"`)
- **Pacing**: {WAIT_SECONDS}s wait between requests to stay under 15 RPM
- **Resilience**: Auto-backoff retry and incremental disk saving enabled.
"""

with open(EVAL_MD_PATH, "w", encoding="utf-8") as f:
    f.write(eval_md)

print(f"\nEvaluation report saved to: {EVAL_MD_PATH}")
print("Done!")
