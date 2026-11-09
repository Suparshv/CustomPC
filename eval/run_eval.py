"""
run_eval.py - The Resilient Evaluation Runner

Features:
  1. Full Raw Data Logging: Saves full reply, build part IDs, critique object, and per-agent token breakdown to results.jsonl.
  2. Strict Scoring:
     - Impossible requests: only correct if it refuses or states the conflict.
     - Vague requests: only correct if it asks a clarifying question or its build passes the compatibility checker.
     - Normal builds: valid if all 9 categories present and no compatibility rule fails.
  3. Consistent 1x RAM Pricing: Uses exact part pricing without hidden doubling.
  4. Auto-Resume & Rate-Limit Backoff: Retries on 429/500 with progressive wait, saves incrementally to disk.

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
MANUAL_GRADES_PATH = os.path.join(os.path.dirname(__file__), "manual_grades.json")

WAIT_SECONDS = 16
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 50

# Specific conflict keywords for evaluating impossible requests
CONFLICT_PHRASES = [
    "cannot", "impossible", "incompatible", "not compatible",
    "exceeds budget", "exceeds the budget", "exceeds your budget",
    "over budget", "too low for", "socket mismatch", "mismatch",
    "underpowered", "insufficient wattage", "not enough power",
    "requires at least", "requires a higher", "conflict"
]


# ─── Load Existing Results (For Resume Support) ──────────────────────────────
completed_results = {}
if os.path.exists(RESULTS_PATH):
    try:
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
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

            try:
                data = resp.json()
            except Exception:
                data = {"error": f"Invalid JSON response (HTTP {resp.status_code}): {resp.text[:100]}"}

            if resp.status_code != 200 or "error" in data:
                err_msg = data.get("error", f"HTTP {resp.status_code}")
                print(f"    [Warning] Server returned error: {err_msg}")

                if resp.status_code in [400, 401, 403, 404]:
                    return False, f"Permanent error {err_msg}", elapsed, data

                if attempt < MAX_RETRIES:
                    backoff = BASE_BACKOFF_SECONDS + (attempt - 1) * 15
                    print(f"    Rate limit or server busy. Waiting {backoff}s before retry #{attempt+1}...")
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

    if req_id in completed_results:
        print(f"[{i+1}/{len(test_requests)}] id={req_id} [CACHED] Skipping.")
        results.append(completed_results[req_id])
        continue

    base_session_id = f"eval-{uuid.uuid4().hex[:8]}"
    print(f"[{i+1}/{len(test_requests)}] id={req_id} type={req_type}")
    print(f"  Prompt: \"{req_text}\"")

    success, error_msg, elapsed, data = execute_request_with_retries(req_text, base_session_id)

    reply = data.get("reply", "") or ""
    build = data.get("build", None)
    critique = data.get("critique", None)
    reviews = data.get("reviews", None)
    comparison_data = data.get("comparisonData", None)
    token_log = data.get("tokenLog", []) or []

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

    # Extract part IDs
    build_part_ids = []
    if build and isinstance(build, list):
        for item in build:
            if isinstance(item, dict):
                build_part_ids.append(item.get("id", ""))
            else:
                build_part_ids.append(str(item))

    # Score
    score = {}

    if not success:
        score["errored"] = True
        score["valid"] = False
        print(f"  [Skip scoring] Request failed after {MAX_RETRIES} retries. Error: {error_msg}")

    elif req_type == "normal_build":
        if build_part_ids:
            part_names = []
            for pid in build_part_ids:
                spec = find_spec(pid)
                if spec:
                    part_names.append(spec["name"])

            judge_results = judge_build(part_names, req_budget)

            has_all_9 = judge_results.get("1_all_categories", ("", ""))[0] == "PASS"
            has_fail = any(v[0] == "FAIL" for v in judge_results.values())
            has_unknown = any(v[0] == "UNKNOWN" for v in judge_results.values())

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
        score["handled_correctly"] = bool(comparison_data is not None or ("compar" in reply.lower()))

    elif req_type == "impossible":
        # Strict rule: correct only if it refuses or states the conflict
        reply_lower = reply.lower()
        has_build = bool(build_part_ids)
        
        # Check if Critic disapproved or stated issues
        critic_disapproved = bool(critique and isinstance(critique, dict) and critique.get("approved") is False)
        critic_reply = (critique.get("reply", "") if isinstance(critique, dict) else "").lower()
        critic_issues = " ".join(critique.get("issues", []) if isinstance(critique, dict) else []).lower()

        # Check if conflict was explicitly stated in text
        conflict_in_reply = any(p in reply_lower for p in CONFLICT_PHRASES)
        conflict_in_critic = any(p in critic_reply or p in critic_issues for p in CONFLICT_PHRASES)
        stated_conflict = critic_disapproved or conflict_in_reply or conflict_in_critic

        if not has_build:
            # Refused to build -> correct
            score["handled_correctly"] = True
            score["sub_result"] = "Refused"
        else:
            # Produced a build -> only correct if it clearly stated the conflict
            score["handled_correctly"] = stated_conflict
            score["sub_result"] = "Stated conflict" if stated_conflict else "Built without conflict warning"

    elif req_type == "off_topic":
        # Correct only if no PC build was produced
        score["handled_correctly"] = not bool(build_part_ids)

    elif req_type == "vague":
        # Strict rule: correct only if it asks a question OR its build passes the checker
        asked_question = "?" in reply

        build_passes = False
        if build_part_ids:
            part_names = []
            for pid in build_part_ids:
                spec = find_spec(pid)
                if spec:
                    part_names.append(spec["name"])
            judge_res = judge_build(part_names, budget=None)
            has_all_9 = judge_res.get("1_all_categories", ("", ""))[0] == "PASS"
            has_fail = any(v[0] == "FAIL" for v in judge_res.values())
            build_passes = has_all_9 and not has_fail

        score["asked_question"] = asked_question
        score["build_passes"] = build_passes
        score["handled_correctly"] = bool(asked_question or build_passes)
        if asked_question:
            score["sub_result"] = "Asked clarifying question"
        elif build_passes:
            score["sub_result"] = "Build passed compatibility checker"
        else:
            score["sub_result"] = "Build failed compatibility checker & no question asked"

    # Assemble raw record with all detailed fields
    result = {
        "id": req_id,
        "type": req_type,
        "text": req_text,
        "budget": req_budget,
        "success": success,
        "error": error_msg,
        "elapsed_s": elapsed,
        "reply": reply,                       # Full raw reply
        "build_part_ids": build_part_ids,     # List of drafted part IDs
        "build_count": len(build_part_ids),
        "critique": critique,                 # Full critique object
        "per_agent_tokens": token_log,        # Per-agent token logs
        "total_tokens": total_tokens,
        "prompt_tokens": total_prompt_tokens,
        "candidate_tokens": total_candidate_tokens,
        "score": score,
    }
    results.append(result)

    # Append incrementally to disk so progress is never lost
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


# ─── Manual grades (hand-graded impossible requests) ─────────────────────────
# Applied AFTER results.jsonl is written, so the raw file keeps the automatic scores.
VALID_GRADES = ("correct", "partial", "incorrect")
manual_grades = {}
if os.path.exists(MANUAL_GRADES_PATH):
    with open(MANUAL_GRADES_PATH, "r", encoding="utf-8") as f:
        for g in json.load(f).get("grades", []):
            if g["grade"] not in VALID_GRADES:
                raise ValueError(f"manual_grades.json: id {g['id']} has invalid grade '{g['grade']}'")
            manual_grades[g["id"]] = g
    print(f"[Manual] Loaded {len(manual_grades)} hand grades from manual_grades.json")

for r in results:
    g = manual_grades.get(r["id"])
    if g and r["type"] == "impossible":
        r["score"] = {
            **r["score"],
            "auto_handled_correctly": r["score"].get("handled_correctly"),
            "manual_grade": g["grade"],
            "handled_correctly": g["grade"] == "correct",
            "sub_result": f"Hand-graded: {g['grade']}",
        }


# ─── Compute Aggregate Scores ────────────────────────────────────────────────
build_requests = [r for r in results if r["type"] == "normal_build"]
comparison_requests = [r for r in results if r["type"] == "comparison"]
impossible_requests = [r for r in results if r["type"] == "impossible"]
offtopic_requests = [r for r in results if r["type"] == "off_topic"]
vague_requests = [r for r in results if r["type"] == "vague"]

build_requests_scored = [r for r in build_requests if not r["score"].get("errored")]

builds_produced = [r for r in build_requests_scored if r["score"].get("produced_build")]
builds_valid = [r for r in build_requests_scored if r["score"].get("valid")]

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

impossible_counts = {
    k: sum(1 for r in impossible_requests if r["score"].get("manual_grade") == k)
    for k in VALID_GRADES
}
impossible_all_graded = bool(impossible_requests) and sum(impossible_counts.values()) == len(impossible_requests)
impossible_label = (
    f"{impossible_counts['correct']} correct, {impossible_counts['partial']} partial, "
    f"{impossible_counts['incorrect']} incorrect (hand-graded)"
    if impossible_all_graded
    else f"{len(impossible_correct)}/{len(impossible_requests)} (automatic scorer only)"
)

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
print(f"  FINAL SCORECARD (v1-baseline)")
print(f"{'='*60}")
print(f"  Build requests:        {len(build_requests)}")
print(f"    Produced a build:    {len(builds_produced)}")
print(f"    Valid builds:        {len(builds_valid)} ({valid_build_rate})")
print(f"    Within budget:       {len(builds_budget_pass)}/{len(builds_with_budget)} ({budget_hit_rate})")
print(f"    Success rate:        {len(builds_successful)}/{len(build_requests)} ({success_rate})")
print(f"    Refused:             {len(builds_refused)} ({refusal_rate})")
print(f"    Had UNKNOWN checks:  {len(builds_unknown)} ({unknown_rate})")
print(f"  Comparisons correct:   {len(comparisons_correct)}/{len(comparison_requests)} ({pct(len(comparisons_correct), len(comparison_requests))})")
print(f"  Impossible correct:    {len(impossible_correct)}/{len(impossible_requests)} ({pct(len(impossible_correct), len(impossible_requests))}) strict")
print(f"  Impossible breakdown:  {impossible_label}")
print(f"  Off-topic correct:     {len(offtopic_correct)}/{len(offtopic_requests)} ({pct(len(offtopic_correct), len(offtopic_requests))})")
print(f"  Vague correct:         {len(vague_correct)}/{len(vague_requests)} ({pct(len(vague_correct), len(vague_requests))})")
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
| Impossible requests handled correctly (strict) | {pct(len(impossible_correct), len(impossible_requests))} ({len(impossible_correct)}/{len(impossible_requests)}) |
| Impossible requests breakdown | {impossible_label} |
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
    reply_snippet = (r.get("reply", "") or "")[:75].replace("\n", " ")

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
    elif r["type"] == "impossible":
        correct = r["score"].get("handled_correctly", False)
        grade = r["score"].get("manual_grade")
        result_str = grade.upper() if grade else ("CORRECT" if correct else "INCORRECT")
        details = r["score"].get("sub_result", reply_snippet)
    elif r["type"] == "vague":
        correct = r["score"].get("handled_correctly", False)
        result_str = "CORRECT" if correct else "INCORRECT"
        details = r["score"].get("sub_result", reply_snippet)
    elif r["type"] in ["comparison", "off_topic"]:
        correct = r["score"].get("handled_correctly", False)
        result_str = "CORRECT" if correct else "INCORRECT"
        details = reply_snippet if reply_snippet else "-"
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
- **Pricing Rule**: Consistent 1x part pricing (no automatic RAM doubling).
- **Strict Scoring**:
  - Impossible requests are hand-graded from the saved replies (`eval/manual_grades.json`). Correct = refuses, or names the conflict without claiming the build satisfies it. Partial = names it but makes a false claim. Incorrect = no warning in the reply, or the reply contradicts the build. Only "correct" counts toward the headline.
  - Vague requests counted as correct only if clarifying question asked or build passes all 6 checker rules.
"""

with open(EVAL_MD_PATH, "w", encoding="utf-8") as f:
    f.write(eval_md)

print(f"\nEvaluation report saved to: {EVAL_MD_PATH}")
print("Done!")
