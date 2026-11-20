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
  3. Make sure MongoDB is running (scoring reads part data from it)
  4. Run: python eval/run_eval.py

  Re-score saved replies with today's rules, without sending any requests:
     python eval/run_eval.py --rescore
  A separate run for the 20 Nov comparison (keep each run in its own files):
     python eval/run_eval.py --results eval/results-v2-gemini.jsonl --report docs/eval-v2-gemini.md --title "v2 upgrades on, Gemini"
  Give every run its own hand-grades file (requests 16-20), so grades never overwrite each other:
     ... --grades eval/grades-v2-on-gemini.json
  Every new row saves the git commit it ran on (and any uncommitted files) as "code_version".
  The combined before/after table: python eval/combine_eval.py (see docs/eval.md).

The scoring logic lives in small functions so tests (tests/test_run_eval.py) can
import this file without sending any requests. Everything that touches the
network or writes files runs only inside main().
"""

import hashlib
import json
import statistics
import os
import re
import subprocess
import sys
import time
import uuid
import datetime

# Add agent-service so we can import the checker
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent-service"))
# The judge is checker.py: the SAME code the new system's check_compatibility tool uses.
# (It used to be compat.py, which only knows the original 24 parts. Scoring the old and the
#  new system with different judges would not be a fair comparison, and compat.py would
#  have called every new-catalogue part "unknown".)
from checker import check_build
from catalog import extract_budget   # the same budget reader the agent uses


# ─── Helpers ──────────────────────────────────────────────────────────────────
def pct(num, denom):
    """Safe percentage. Returns measured number only, no rounding up."""
    if denom == 0:
        return "N/A"
    return f"{round((num / denom) * 100, 1)}%"


# ─── Config ───────────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:5000/api/chat/builder"          # old v1 system (Node backend)
AGENT_URL = "http://127.0.0.1:8001/agent/build"                 # new Day 10 agent (agent-service)
REQUESTS_PATH = os.path.join(os.path.dirname(__file__), "requests.jsonl")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.jsonl")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
EVAL_MD_PATH = os.path.join(DOCS_DIR, "eval-v1.md")
MANUAL_GRADES_PATH = os.path.join(os.path.dirname(__file__), "manual_grades.json")

WAIT_SECONDS = 16
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 50

VALID_GRADES = ("correct", "partial", "incorrect")

# Specific conflict keywords for evaluating impossible requests
CONFLICT_PHRASES = [
    "cannot", "impossible", "incompatible", "not compatible",
    "exceeds budget", "exceeds the budget", "exceeds your budget",
    "over budget", "too low for", "socket mismatch", "mismatch",
    "underpowered", "insufficient wattage", "not enough power",
    "requires at least", "requires a higher", "conflict"
]


# ─── Code version (Day 13) ────────────────────────────────────────────────────
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


def git_state(run=None):
    """
    The code version a run used: {"commit": short hash, "uncommitted": [changed tracked files]}.
    Saved on every result row, so anyone can check out the exact code that produced it.
    If git can't tell us, both are None (unknown, never guessed).
    """
    run = run or subprocess.run
    try:
        opts = {"capture_output": True, "text": True, "cwd": REPO_ROOT, "check": True}
        commit = run(["git", "rev-parse", "--short", "HEAD"], **opts).stdout.strip()
        changed = run(["git", "diff", "--name-only", "HEAD"], **opts).stdout
    except Exception:
        return {"commit": None, "uncommitted": None}
    return {"commit": commit or None, "uncommitted": [f.strip() for f in changed.splitlines() if f.strip()]}


def code_version_text(results):
    """One line for the report header: which code version(s) produced these rows."""
    versions, missing = [], 0
    for r in results:
        v = r.get("code_version")
        if not v:
            missing += 1
            continue
        commit = f"`{v['commit']}`" if v.get("commit") else "unknown commit"
        changed = v.get("uncommitted")
        if changed is None:
            text = f"{commit} (uncommitted changes unknown)"
        elif changed:
            text = f"{commit} + uncommitted changes in {', '.join(changed)}"
        else:
            text = f"{commit} (clean)"
        if text not in versions:
            versions.append(text)
    if not versions:
        return "not recorded by the runner"
    out = "; ".join(versions)
    if missing:
        out += f"; not recorded for {missing} row(s)"
    return out


# ─── Loading files ────────────────────────────────────────────────────────────
def load_completed_results(path):
    """Results from an earlier run that succeeded, keyed by id (for resume support)."""
    completed = {}
    if not os.path.exists(path):
        return completed
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    if item.get("success") is True and not item.get("score", {}).get("errored"):
                        completed[item["id"]] = item
    except Exception as e:
        print(f"Notice: Could not parse existing results.jsonl ({e}), starting fresh.")
        return {}
    return completed


def load_requests(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ─── Sending a request ────────────────────────────────────────────────────────
def execute_request_with_retries(req_text, base_session_id, post=None, sleep=time.sleep, clock=time.perf_counter,
                                 url=BACKEND_URL, extra_payload=None):
    """
    Executes a request to backend, automatically retrying if rate limits occur.
    Uses unique session ID per attempt to prevent conversation state pollution.

    `post`, `sleep` and `clock` can be replaced in tests so no real request is made.
    Returns (success, error_msg, elapsed_s, data, retry_info).

    elapsed_s is the time of the LAST attempt only (the one whose answer we keep).
    Backoff sleeps are our own waiting, not the system's response time, so they
    are reported separately in retry_info = {"retries": n, "backoff_s": seconds}.
    """
    if post is None:
        import requests as http_requests
        post = http_requests.post

    retry_info = {"retries": 0, "backoff_s": 0}

    def wait_before_retry(attempt, reason):
        backoff = BASE_BACKOFF_SECONDS + (attempt - 1) * 15
        print(f"    {reason}. Waiting {backoff}s before retry #{attempt+1}...")
        retry_info["retries"] += 1
        retry_info["backoff_s"] += backoff
        sleep(backoff)

    elapsed = 0.0
    for attempt in range(1, MAX_RETRIES + 1):
        session_id = f"{base_session_id}-try{attempt}"
        start_time = clock()  # restarted for every attempt
        try:
            resp = post(
                url,
                json={"message": req_text, "sessionId": session_id, **(extra_payload or {})},
                timeout=300,   # a full agent build (9 picks + up to 2 repairs) can take minutes
            )
            elapsed = round(clock() - start_time, 2)

            try:
                data = resp.json()
            except Exception:
                data = {"error": f"Invalid JSON response (HTTP {resp.status_code}): {resp.text[:100]}"}

            if resp.status_code != 200 or "error" in data:
                err_msg = data.get("error", f"HTTP {resp.status_code}")
                print(f"    [Warning] Server returned error: {err_msg}")

                if resp.status_code in [400, 401, 403, 404]:
                    return False, f"Permanent error {err_msg}", elapsed, data, retry_info

                if attempt < MAX_RETRIES:
                    wait_before_retry(attempt, "Rate limit or server busy")
                    continue
                return False, err_msg, elapsed, data, retry_info

            return True, None, elapsed, data, retry_info
        except Exception as e:
            elapsed = round(clock() - start_time, 2)
            if attempt < MAX_RETRIES:
                wait_before_retry(attempt, f"[Network/Timeout Error]: {e}")
            else:
                return False, str(e), elapsed, {}, retry_info
    return False, "Max retries exceeded", elapsed, {}, retry_info


# ─── Reading the response ─────────────────────────────────────────────────────
def sum_tokens(token_log):
    """Return (prompt_tokens, candidate_tokens) summed over every agent call."""
    total_prompt_tokens = 0
    total_candidate_tokens = 0
    for entry in token_log or []:
        if isinstance(entry, dict):
            tokens = entry.get("tokens") or {}
            if isinstance(tokens, dict):
                total_prompt_tokens += tokens.get("promptTokenCount") or 0
                total_candidate_tokens += tokens.get("candidatesTokenCount") or 0
    return total_prompt_tokens, total_candidate_tokens


def extract_part_ids(build):
    build_part_ids = []
    if build and isinstance(build, list):
        for item in build:
            if isinstance(item, dict):
                build_part_ids.append(item.get("id", ""))
            else:
                build_part_ids.append(str(item))
    return build_part_ids


# ─── Scoring ──────────────────────────────────────────────────────────────────
def judge_part_ids(build_part_ids, budget, part_lookup=None):
    """
    Run the checker.py judge on a list of part ids.

    part_lookup: {part_id: part document}, normally loaded from MongoDB (see
    build_part_lookup), so the old 24 parts and the ~3,000 new parts are judged on
    the same data. Without it, the checker only knows the original 24 parts.

    ALL ids go to the judge. An id the judge cannot find is "unresolved": the
    build is then never valid, because we cannot vouch for a part we know nothing about.
    """
    res = check_build(build_part_ids, budget=budget, part_lookup=part_lookup)
    judge_results = {name: (r["verdict"], r["message"]) for name, r in res["rules"].items()}
    unknown_ids = list(res["unresolved"])
    has_all_9 = res["rules"]["all_categories"]["verdict"] == "PASS"
    has_fail = bool(res["fails"])
    return {
        "judge_results": judge_results,
        "unknown_ids": unknown_ids,
        "has_all_9": has_all_9,
        "has_fail": has_fail,
        "has_unknown": bool(unknown_ids) or bool(res["unknowns"]),
        "valid": has_all_9 and not has_fail and not unknown_ids,
        # Every rule PASS: nothing failed AND nothing was left unchecked.
        "fully_verified": bool(res["fully_verified"]),
    }


def score_normal_build(build_part_ids, budget, part_lookup=None):
    score = {}
    if build_part_ids:
        j = judge_part_ids(build_part_ids, budget, part_lookup)
        score["produced_build"] = True
        score["valid"] = j["valid"]
        score["fully_verified"] = j["fully_verified"]
        score["has_fail"] = j["has_fail"]
        score["has_unknown"] = j["has_unknown"]
        score["unknown_ids"] = j["unknown_ids"]
        score["judge_details"] = {k: v[0] for k, v in j["judge_results"].items()}
    else:
        score["produced_build"] = False
        score["valid"] = False
        score["refused"] = True
    return score


# Replies that decline the request (the off-topic guard answers "I cannot assist with that request.").
REFUSAL_PHRASES = ("cannot assist", "can't assist", "cannot help", "can't help", "unable to assist", "unable to help")

# A "?" counts as a question only when it ends a sentence: followed by a space,
# the end of the text, or a closing quote/bracket. "shop.com/?id=5" is not a question.
QUESTION_RE = re.compile(r"\?(?=\s|$|[\"')\]])")


def is_refusal(reply):
    reply_lower = (reply or "").lower()
    return any(p in reply_lower for p in REFUSAL_PHRASES)


def asks_question(reply):
    return bool(QUESTION_RE.search(reply or ""))


def has_comparison_table(comparison_data):
    """True if the Comparator returned a real table (at least 2 columns and 1 row)."""
    return (
        isinstance(comparison_data, dict)
        and len(comparison_data.get("headers") or []) >= 2
        and bool(comparison_data.get("rows"))
    )


def score_comparison(reply, comparison_data, build_part_ids):
    """
    Correct if the Comparator returned a comparison table, or (no table) the reply
    is a real text answer: not empty, not a refusal, and not a PC build.
    An earlier version passed any reply containing the letters "compar".
    """
    if has_comparison_table(comparison_data):
        return {"handled_correctly": True, "sub_result": "Comparison table returned"}
    if build_part_ids:
        return {"handled_correctly": False, "sub_result": "Produced a build instead of a comparison"}
    if not (reply or "").strip() or is_refusal(reply):
        return {"handled_correctly": False, "sub_result": "Empty reply or refusal"}
    return {"handled_correctly": True, "sub_result": "Answered in text (no table)"}


def score_impossible(reply, build_part_ids, critique):
    # Strict rule: correct only if it refuses or states the conflict
    score = {}
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
    return score


def score_off_topic(build_part_ids):
    # Correct only if no PC build was produced
    return {"handled_correctly": not bool(build_part_ids)}


def score_vague(reply, build_part_ids, part_lookup=None):
    """
    Strict rule: correct if it asks a clarifying question (and does not also hand
    over a full build), OR its build passes the checker.

    A full 9-part build is judged on its own merits: tacking a "?" onto a reply
    does not rescue a build that fails the checker.
    """
    score = {}
    asked_question = asks_question(reply)

    full_build = False
    build_passes = False
    if build_part_ids:
        j = judge_part_ids(build_part_ids, None, part_lookup)
        full_build = j["has_all_9"]
        build_passes = j["valid"]
    question_counts = asked_question and not full_build

    score["asked_question"] = asked_question
    score["build_passes"] = build_passes
    score["handled_correctly"] = bool(question_counts or build_passes)
    if build_passes:
        score["sub_result"] = "Build passed compatibility checker"
    elif question_counts:
        score["sub_result"] = "Asked clarifying question"
    elif asked_question:
        score["sub_result"] = "Asked a question but also gave a full build that failed the checker"
    else:
        score["sub_result"] = "Build failed compatibility checker & no question asked"
    return score


def score_result(req_type, success, reply, build_part_ids, critique, comparison_data, budget, part_lookup=None):
    """Score one response. Returns the `score` dict stored in results.jsonl."""
    if not success:
        return {"errored": True, "valid": False}
    if req_type == "normal_build":
        return score_normal_build(build_part_ids, budget, part_lookup)
    if req_type == "comparison":
        return score_comparison(reply, comparison_data, build_part_ids)
    if req_type == "impossible":
        return score_impossible(reply, build_part_ids, critique)
    if req_type == "off_topic":
        return score_off_topic(build_part_ids)
    if req_type == "vague":
        return score_vague(reply, build_part_ids, part_lookup)
    return {}


def judged_budget(row):
    """
    The budget a build is judged against: the one the request TEXT states, read by code.

    Rule decided on Day 10: 9 of the 10 build requests state no budget in their text; their
    test-file "budget" was never shown to either system, so judging against it measured
    guessing, not building. A request that states no budget has no price limit to break.
    (The frozen test file is not edited; its budget field is just not used for judging.)
    """
    return extract_budget(row.get("text") or "")


def rescore_results(results, part_lookup=None):
    """
    Score saved replies again with the CURRENT scorer and judge. No requests are sent.

    This is how an old run (e.g. the 8 Nov baseline) is put on the same footing as a
    new run: same 30 requests, same saved replies, same rules. Returns new row dicts;
    the input rows are not changed.
    """
    rescored = []
    for r in results:
        new = dict(r)
        new["score"] = score_result(
            r["type"], r.get("success", True), r.get("reply", "") or "", r.get("build_part_ids") or [],
            r.get("critique"), r.get("comparison_data"), judged_budget(r), part_lookup,
        )
        rescored.append(new)
    return rescored


def build_part_lookup(results):
    """
    {part_id: document} for every part id in the results, read from MongoDB through the
    same repo the agent tools use. Raises RepoUnavailableError if MongoDB is down: scoring
    without it would judge old and new parts on different data.
    """
    from repo import get_repo
    ids = sorted({pid for r in results for pid in (r.get("build_part_ids") or []) if pid})
    lookup = {}
    for doc in get_repo().get_many(ids):
        lookup[str(doc.get("id") or doc.get("_id"))] = doc
    return lookup


# ─── Manual grades (hand-graded impossible requests) ─────────────────────────
def load_manual_grades(path):
    manual_grades = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for g in json.load(f).get("grades", []):
                if g["grade"] not in VALID_GRADES:
                    raise ValueError(f"manual_grades.json: id {g['id']} has invalid grade '{g['grade']}'")
                manual_grades[g["id"]] = g
    return manual_grades


def reply_fingerprint(reply, build_part_ids):
    """
    sha256 of exactly what a hand grader looked at: the reply text AND the part ids.
    Both matter: a grade like "the reply contradicts the build" is about the pair.
    If a new run gives a different reply or build, the fingerprint changes.
    """
    payload = json.dumps(
        {"reply": reply or "", "build_part_ids": list(build_part_ids or [])},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_manual_grades(results, manual_grades):
    """
    Replace automatic scores with hand grades. Changes `results` in place.

    A hand grade is about one specific reply. It is applied only when the stored
    fingerprint matches this run's reply + build and the request did not error.
    Otherwise (new run, changed reply, old grade with no fingerprint) the automatic
    score is kept and the result is marked "needs_hand_grade".
    """
    for r in results:
        if r["type"] != "impossible":
            continue
        if r["score"].get("errored") or not r.get("success"):
            continue  # nothing to grade; errored requests are left out of the rates
        g = manual_grades.get(r["id"])
        fingerprint = reply_fingerprint(r.get("reply"), r.get("build_part_ids"))
        if g and g.get("fingerprint") == fingerprint:
            r["score"] = {
                **r["score"],
                "auto_handled_correctly": r["score"].get("handled_correctly"),
                "manual_grade": g["grade"],
                "handled_correctly": g["grade"] == "correct",
                "sub_result": f"Hand-graded: {g['grade']}",
            }
        else:
            auto = r["score"].get("sub_result", "")
            r["score"] = {
                **r["score"],
                "needs_hand_grade": True,
                "sub_result": f"Needs hand grade (automatic: {auto})" if auto else "Needs hand grade",
            }


# ─── Aggregate scores ─────────────────────────────────────────────────────────
def compute_metrics(results):
    """
    Count everything the scorecard needs. Each rate is stored as (numerator, denominator).
    """
    # Errored requests (no answer after all retries) say nothing about answer
    # quality, so they are left out of BOTH the numerator and the denominator of
    # every rate, and counted separately in m["errored"].
    types = ("normal_build", "comparison", "impossible", "off_topic", "vague")
    all_by_type = {t: [r for r in results if r["type"] == t] for t in types}
    by_type = {t: [r for r in rs if not r["score"].get("errored")] for t, rs in all_by_type.items()}
    errored = {t: len(all_by_type[t]) - len(by_type[t]) for t in types}

    build_requests_scored = by_type["normal_build"]

    builds_produced = [r for r in build_requests_scored if r["score"].get("produced_build")]
    builds_valid = [r for r in build_requests_scored if r["score"].get("valid")]
    builds_with_budget = [r for r in builds_produced if judged_budget(r) is not None]
    builds_budget_pass = [r for r in builds_with_budget
                          if r["score"].get("judge_details", {}).get("within_budget") == "PASS"]
    builds_refused = [r for r in build_requests_scored if r["score"].get("refused")]
    builds_unknown = [r for r in build_requests_scored if r["score"].get("has_unknown")]
    builds_fully_verified = [r for r in build_requests_scored if r["score"].get("fully_verified")]
    # Success rate = valid AND within budget (or no budget constraint)
    builds_successful = [
        r for r in build_requests_scored
        if r["score"].get("valid") and (judged_budget(r) is None or r["score"].get("judge_details", {}).get("within_budget") == "PASS")
    ]

    def correct(rs):
        return len([r for r in rs if r["score"].get("handled_correctly")])

    n_builds = len(build_requests_scored)
    m = {
        "build_requests": len(all_by_type["normal_build"]),
        "builds_produced": len(builds_produced),
        "valid": (len(builds_valid), n_builds),
        "within_budget": (len(builds_budget_pass), len(builds_with_budget)),
        "success": (len(builds_successful), n_builds),
        "refused": (len(builds_refused), n_builds),
        "unknown": (len(builds_unknown), n_builds),
        "fully_verified": (len(builds_fully_verified), n_builds),
        "comparison": (correct(by_type["comparison"]), len(by_type["comparison"])),
        "impossible": (correct(by_type["impossible"]), len(by_type["impossible"])),
        "off_topic": (correct(by_type["off_topic"]), len(by_type["off_topic"])),
        "vague": (correct(by_type["vague"]), len(by_type["vague"])),
        "errored": {t: n for t, n in errored.items() if n},
        "errored_total": sum(errored.values()),
    }

    impossible = by_type["impossible"]
    counts = {k: sum(1 for r in impossible if r["score"].get("manual_grade") == k) for k in VALID_GRADES}
    n_graded = sum(counts.values())
    graded_text = (f"{counts['correct']} correct, {counts['partial']} partial, "
                   f"{counts['incorrect']} incorrect (hand-graded)")
    if not impossible or n_graded == 0:
        m["impossible_label"] = f"{m['impossible'][0]}/{m['impossible'][1]} (automatic scorer only)"
    elif n_graded == len(impossible):
        m["impossible_label"] = graded_text
    else:
        m["impossible_label"] = (f"{graded_text}; {len(impossible) - n_graded} need a hand grade "
                                 f"(automatic score used)")

    total_time = sum(r["elapsed_s"] for r in results)
    m["avg_time"] = round(total_time / len(results), 2) if results else 0
    # Median = the middle value. A few very slow requests (or, in the 8 Nov run, time
    # spent waiting before a retry) pull the average up but barely move the median.
    m["median_time"] = round(statistics.median(r["elapsed_s"] for r in results), 2) if results else 0
    m["total_tokens"] = sum(r["total_tokens"] for r in results)
    m["avg_tokens"] = round(m["total_tokens"] / len(results)) if results else 0
    return m


def errored_text(m):
    """'0', or '2 (normal_build: 1, comparison: 1)'."""
    if not m["errored_total"]:
        return "0"
    parts = ", ".join(f"{t}: {n}" for t, n in m["errored"].items())
    return f"{m['errored_total']} ({parts})"


def rate(m, key):
    """'40.0% (4/10)' style text for one rate in the metrics dict."""
    num, denom = m[key]
    return f"{pct(num, denom)} ({num}/{denom})"


# ─── Output ───────────────────────────────────────────────────────────────────
def print_scorecard(m):
    print(f"\n{'='*60}")
    print(f"  FINAL SCORECARD (v1-baseline)")
    print(f"{'='*60}")
    print(f"  Errored (not scored):  {errored_text(m)}")
    print(f"  Build requests:        {m['build_requests']}")
    print(f"    Produced a build:    {m['builds_produced']}")
    print(f"    Valid builds:        {m['valid'][0]} ({pct(*m['valid'])})")
    print(f"    Within budget:       {m['within_budget'][0]}/{m['within_budget'][1]} ({pct(*m['within_budget'])})")
    print(f"    Success rate:        {m['success'][0]}/{m['success'][1]} ({pct(*m['success'])})")
    print(f"    Refused:             {m['refused'][0]} ({pct(*m['refused'])})")
    print(f"    Had UNKNOWN checks:  {m['unknown'][0]} ({pct(*m['unknown'])})")
    print(f"    Fully verified:      {m['fully_verified'][0]} ({pct(*m['fully_verified'])})")
    print(f"  Comparisons correct:  {m['comparison'][0]}/{m['comparison'][1]} ({pct(*m['comparison'])})")
    print(f"  Impossible correct:    {m['impossible'][0]}/{m['impossible'][1]} ({pct(*m['impossible'])}) strict")
    print(f"  Impossible breakdown:  {m['impossible_label']}")
    print(f"  Off-topic correct:     {m['off_topic'][0]}/{m['off_topic'][1]} ({pct(*m['off_topic'])})")
    print(f"  Vague correct:         {m['vague'][0]}/{m['vague'][1]} ({pct(*m['vague'])})")
    print(f"  Avg time/request:      {m['avg_time']}s")
    print(f"  Median time/request:   {m['median_time']}s")
    print(f"  Avg tokens/request:    {m['avg_tokens']}")
    print(f"{'='*60}")


def system_notes(results):
    """Describe the system that ACTUALLY produced these results (old v1 backend or the Day 10 agent)."""
    agent_rows = [r for r in results if r.get("target") == "agent"]
    if not agent_rows:
        return (
            "- **Model**: Gemini 3.5 Flash Lite via `@google/genai` SDK\n"
            "- **Architecture**: LangGraph multi-agent (Supervisor, Architect, Critic, Reviewer, Comparator)\n"
            "- **RAG**: ChromaDB vector database (Docker)\n"
            "- **Function Calling**: Strict mode (`toolConfig.functionCallingConfig.mode: \"ANY\"`)\n"
            f"- **Pacing**: {WAIT_SECONDS}s wait between requests to stay under 15 RPM"
        )
    models = sorted({r.get("model") or "unknown" for r in agent_rows})
    switches = agent_rows[0].get("overrides")
    return (
        "- **System**: Day 10 agent (`agent-service`, `POST /agent/build`): rule-based router, step-by-step "
        "part picks with code filters, code compatibility checker with repairs, price and verdict written by code\n"
        f"- **Model**: {', '.join(models)}\n"
        f"- **Switches**: {json.dumps(switches) if switches else 'defaults (all upgrades on)'}\n"
        "- **Search**: ChromaDB + BM25 keyword index (Day 9), retriever set by the switches"
    )


def render_eval_md(results, m, n_requests, timestamp, title="v1-baseline", preface=""):
    eval_md = f"""# Evaluation Report: {title}

> Measured on {n_requests} fixed test requests on {timestamp}.
> This is a small sample. Results describe this specific test set, not general accuracy.
> Code version: {code_version_text(results)}
{preface}
## Summary Table

| Metric | Value |
|--------|-------|
| Valid builds (no FAIL, all 9 categories) | {rate(m, 'valid')} |
| Within budget (among budgeted builds) | {rate(m, 'within_budget')} |
| Refusal rate (build requests declined) | {rate(m, 'refused')} |
| Unknown rate (a check could not run: missing data) | {rate(m, 'unknown')} |
| Fully verified builds (every rule PASS) | {rate(m, 'fully_verified')} |
| Comparisons handled correctly | {rate(m, 'comparison')} |
| Impossible requests handled correctly (strict) | {rate(m, 'impossible')} |
| Impossible requests breakdown | {m['impossible_label']} |
| Off-topic requests handled correctly | {rate(m, 'off_topic')} |
| Vague requests handled correctly | {rate(m, 'vague')} |
| Avg time per request | {m['avg_time']}s |
| Median time per request | {m['median_time']}s |
| Avg tokens per request | {m['avg_tokens']} |
| Total tokens used | {m['total_tokens']} |
| Errored requests (left out of every rate) | {errored_text(m)} |

## Three Key Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Success rate** | {pct(*m['success'])} | Valid and compatible builds within budget, out of all build requests |
| **Refusal rate** | {pct(*m['refused'])} | How often the system declined a build request |
| **Unknown rate** | {pct(*m['unknown'])} | Checks that could not run due to missing spec data |

## Per-Request Breakdown

| ID | Type | Budget | Time | Tokens | Result | Details |
|----|------|--------|------|--------|--------|---------|
"""

    for r in results:
        stated = judged_budget(r)
        budget_str = f"Rs.{int(stated):,}" if stated else "- (not stated)"
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
                details = (r.get("error") or "API request failed")[:60]
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

{system_notes(results)}
- **Pricing Rule**: Consistent 1x part pricing (no automatic RAM doubling).
- **Strict Scoring**:
  - Impossible requests are hand-graded from the saved replies (`eval/manual_grades.json`). Correct = refuses, or names the conflict without claiming the build satisfies it. Partial = names it but makes a false claim. Incorrect = no warning in the reply, or the reply contradicts the build. Only "correct" counts toward the headline.
  - Hand grades are tied to the reply they were made for (sha256 `fingerprint` of reply + build ids). If a run's reply differs, the automatic score is used and the request is marked "Needs hand grade".
  - Vague requests counted as correct only if a clarifying question is asked without handing over a full build, or the build passes the checker (`checker.py`, 9 rules).
  - Comparisons counted as correct only if a comparison table is returned, or the reply is a text answer (not empty, not a refusal, not a build).
  - Builds with a part id that is not in the catalogue are never valid.
  - Requests that errored after all retries are left out of every rate and counted separately. Time per request is the successful attempt only (retry waits not included).
"""
    return eval_md


# ─── Main ─────────────────────────────────────────────────────────────────────
def agent_to_backend_shape(data):
    """
    Convert a POST /agent/build answer into the shape the scorer already reads
    (the old backend's: reply, build, critique, comparisonData, tokenLog).

    Only a build the agent OFFERS counts as a build: status "valid", or "unverified"
    (checker switched off). With "no_valid_build" the agent lists a best attempt that it
    clearly marks NOT valid; that is a refusal, not an invalid build.
    """
    status = data.get("status")
    picks = data.get("picks") or {}
    offered = status in ("valid", "unverified")
    tokens = data.get("tokens") or {}
    comparison = data.get("comparison")
    return {
        "reply": data.get("reply", "") or "",
        "build": [{"id": card["id"], "category": cat} for cat, card in picks.items()] if offered else [],
        "critique": None,                      # the critic is code now; its verdict is in the reply
        "comparisonData": comparison if comparison and comparison.get("rows") else None,
        "tokenLog": [{"agent": "agent-service", "tokens": {
            "promptTokenCount": tokens.get("prompt", 0), "candidatesTokenCount": tokens.get("output", 0)}}],
        "agentStatus": status,
        "model": " / ".join(x for x in (data.get("provider"), data.get("model")) if x) or None,
    }


def run_one_request(req, target="backend", overrides=None, agent_url=AGENT_URL, code_version=None):
    """Send one test request and return the full raw record for results.jsonl."""
    req_id = req["id"]
    req_text = req["text"]
    req_budget = req.get("budget")
    req_type = req["type"]

    base_session_id = f"eval-{uuid.uuid4().hex[:8]}"
    if target == "agent":
        success, error_msg, elapsed, data, retry_info = execute_request_with_retries(
            req_text, base_session_id, url=agent_url,
            extra_payload={"overrides": overrides} if overrides else None)
        if success:
            data = agent_to_backend_shape(data)
    else:
        success, error_msg, elapsed, data, retry_info = execute_request_with_retries(req_text, base_session_id)

    reply = data.get("reply", "") or ""
    build = data.get("build", None)
    critique = data.get("critique", None)
    comparison_data = data.get("comparisonData", None)
    token_log = data.get("tokenLog", []) or []

    total_prompt_tokens, total_candidate_tokens = sum_tokens(token_log)
    build_part_ids = extract_part_ids(build)

    if not success:
        print(f"  [Skip scoring] Request failed after {MAX_RETRIES} retries. Error: {error_msg}")
    score = score_result(req_type, success, reply, build_part_ids, critique, comparison_data,
                         judged_budget(req))

    # Assemble raw record with all detailed fields
    return {
        "id": req_id,
        "type": req_type,
        "text": req_text,
        "budget": req_budget,
        "success": success,
        "error": error_msg,
        "elapsed_s": elapsed,                 # Time of the attempt we kept (no backoff sleeps)
        "retries": retry_info["retries"],     # How many times we had to retry
        "backoff_s": retry_info["backoff_s"], # Total seconds spent waiting between retries
        "reply": reply,                       # Full raw reply
        "build_part_ids": build_part_ids,     # List of drafted part IDs
        "build_count": len(build_part_ids),
        "critique": critique,                 # Full critique object
        "comparison_data": comparison_data,   # Comparator table, saved so comparisons can be re-scored later
        "per_agent_tokens": token_log,        # Per-agent token logs
        "total_tokens": total_prompt_tokens + total_candidate_tokens,
        "prompt_tokens": total_prompt_tokens,
        "candidate_tokens": total_candidate_tokens,
        "target": target,                     # backend (v1) or agent (Day 10)
        "agent_status": data.get("agentStatus"),  # valid / no_valid_build / refused ... (agent only)
        "model": data.get("model"),           # e.g. "ollama / llama3.1:8b" (agent only)
        "overrides": overrides,               # the agent switches used for this run
        "code_version": code_version,         # git commit + uncommitted files this row ran on
        "score": score,
    }


BASELINE_PREFACE = """
> **Re-scored for the before/after comparison** (re-scored on project Day 10). No requests were
> re-run: these are the saved 8 Nov replies (`eval/results.jsonl`, Gemini 3.5 Flash Lite, commit
> `a4ed31e`) scored again with the CURRENT scorer and judge, so the old and the new system are
> measured the same way.
>
> - **Judge:** `agent-service/checker.py` with parts read from MongoDB, the same code the new
>   system's `check_compatibility` tool uses. The 8 Nov report used `compat.py` (6 rules, 24 parts),
>   which cannot judge the new ~3,000-part catalogue. `checker.py` agrees with `compat.py` on every
>   saved build.
> - **Budget rule (changed on Day 10):** a build is judged against the budget the request TEXT
>   states (read by code), and only then. 9 of the 10 build requests state no budget; the 8 Nov
>   scoring judged them against a hidden budget in the test file that the system never saw. With no
>   stated budget there is no price limit to break, so any compatible build is valid. The test file
>   is not edited; its `budget` field is no longer used for judging. Only request #2 ("under 1 lakh")
>   states a budget, so "within budget" rests on 1 build: compare **valid builds** first.
> - **Old rule -> new rule:** valid builds 4/10 -> **6/10**, within budget 5/9 -> **1/1**,
>   success 4/10 -> **6/10**.
> - **Unchanged:** refusals 0/10, comparisons 5/5, impossible 1/5 (hand-graded), off-topic 4/5,
>   vague 4/5.
> - **New judge, more rules:** the unknown rate was 1/10 and is now 10/10, because the new judge also
>   checks cooler height and the old parts have no cooler-height data. For the same reason 0/10 old
>   builds are "fully verified" (every rule PASS).
> - **Time:** the 8 Nov times include any time the runner spent waiting before a retry (it did not
>   record retries then). Ids 17 and 18 (about 60 s) probably include such a wait. Compare the
>   **median** time; new runs record retry waits separately.
"""


def parse_args(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Run (or re-score) the 30-request evaluation.")
    ap.add_argument("--rescore", action="store_true",
                    help="Do not send requests: re-score the saved replies in --results and write --report.")
    ap.add_argument("--results", default=RESULTS_PATH, help="results .jsonl file (default: eval/results.jsonl)")
    ap.add_argument("--report", default=EVAL_MD_PATH, help="markdown report to write (default: docs/eval-v1.md)")
    ap.add_argument("--title", default="v1-baseline", help="report title, e.g. 'v2 upgrades on, Gemini'")
    ap.add_argument("--target", choices=["backend", "agent"], default="backend",
                    help="backend = old v1 Node system (port 5000); agent = new Day 10 agent (POST /agent/build)")
    ap.add_argument("--agent-url", default=AGENT_URL, help=f"agent endpoint (default {AGENT_URL})")
    ap.add_argument("--overrides", type=json.loads, default=None,
                    help='agent switches as JSON, e.g. \'{"use_tools": false, "use_checker": false, "repair_loops": 0}\'')
    ap.add_argument("--grades", default=MANUAL_GRADES_PATH,
                    help="hand grades for THIS run's impossible requests (default: eval/manual_grades.json, "
                         "the baseline's). Give every run its own file so grades never overwrite each other.")
    ap.add_argument("--wait", type=float, default=WAIT_SECONDS,
                    help=f"seconds between requests (default {WAIT_SECONDS} for Gemini's free tier; 0 is fine for Ollama)")
    return ap.parse_args(argv)


def load_part_lookup_or_exit(results):
    """MongoDB part lookup for scoring, or stop with a clear message."""
    from repo import RepoUnavailableError
    try:
        lookup = build_part_lookup(results)
    except RepoUnavailableError as exc:
        print(f"ERROR: {exc}")
        print("Scoring needs MongoDB, so the old and new systems are judged on the same part data.")
        sys.exit(1)
    print(f"[Judge] checker.py with {len(lookup)} parts loaded from MongoDB")
    return lookup


def write_report(results, args, n_requests, timestamp, preface=""):
    manual_grades = load_manual_grades(args.grades)
    if manual_grades:
        print(f"[Manual] Loaded {len(manual_grades)} hand grades from {args.grades}")
    apply_manual_grades(results, manual_grades)

    m = compute_metrics(results)
    print_scorecard(m)

    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(render_eval_md(results, m, n_requests, timestamp, title=args.title, preface=preface))
    print(f"\nEvaluation report saved to: {args.report}")


def main(argv=None):
    # Force UTF-8 encoding on Windows to prevent console Unicode crashes
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    args = parse_args(argv)

    # ─── Re-score only: no requests, saved replies judged with today's rules ──
    if args.rescore:
        saved = sorted(load_completed_results(args.results).values(), key=lambda r: r["id"])
        if not saved:
            print(f"ERROR: no saved results in {args.results}")
            sys.exit(1)
        lookup = load_part_lookup_or_exit(saved)
        results = rescore_results(saved, part_lookup=lookup)
        is_baseline = os.path.abspath(args.results) == os.path.abspath(RESULTS_PATH)
        # The saved results file is NOT rewritten: it is the raw record of that run.
        write_report(results, args, len(results), "2026-11-08 21:41 (re-scored 2026-11-17)" if is_baseline
                     else datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + " (re-scored)",
                     preface=BASELINE_PREFACE if is_baseline else "")
        return

    try:
        import requests  # noqa: F401  (only checking it is installed)
    except ImportError:
        print("ERROR: 'requests' library not found. Install it with: pip install requests")
        sys.exit(1)

    completed_results = load_completed_results(args.results)
    if completed_results:
        print(f" Resuming! Found {len(completed_results)} previously successful test requests in {args.results}")

    test_requests = load_requests(REQUESTS_PATH)

    print(f"\n{'='*60}")
    print(f"  EVALUATION RUNNER - {len(test_requests)} requests total")
    url = args.agent_url if args.target == "agent" else BACKEND_URL
    code_version = git_state()
    print(f"  Code version: {code_version}")
    print(f"  Target: {args.target} ({url})" + (f" | switches: {args.overrides}" if args.overrides else ""))
    print(f"  Pacing: {args.wait}s wait between requests")
    print(f"{'='*60}\n")

    # ─── Run Requests ────────────────────────────────────────────────────────
    results = []
    for i, req in enumerate(test_requests):
        if req["id"] in completed_results:
            print(f"[{i+1}/{len(test_requests)}] id={req['id']} [CACHED] Skipping.")
            results.append(completed_results[req["id"]])
            continue

        print(f"[{i+1}/{len(test_requests)}] id={req['id']} type={req['type']}")
        print(f"  Prompt: \"{req['text']}\"")
        result = run_one_request(req, target=args.target, overrides=args.overrides, agent_url=args.agent_url,
                                 code_version=code_version)
        results.append(result)

        # Append incrementally to disk so progress is never lost
        with open(args.results, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

        score = result["score"]
        status_str = "PASS" if score.get("valid") or score.get("handled_correctly") else "FAIL"
        print(f"  -> {result['elapsed_s']}s | {result['total_tokens']} tokens | {status_str} (provisional)")
        print()

        # Rate limit pacing wait
        if i < len(test_requests) - 1:
            if args.wait > 0:
                print(f"  Pacing wait {args.wait}s...")
                time.sleep(args.wait)

    # ─── Final scores: every row (cached or new) judged by checker.py + MongoDB ──
    # Scores printed during the run are provisional: they were judged before the
    # MongoDB lookup was loaded, so new-catalogue parts may have shown as unknown.
    lookup = load_part_lookup_or_exit(results)
    results = rescore_results(results, part_lookup=lookup)

    # ─── Deduplicate and rewrite the results file clean ──────────────────────
    with open(args.results, "w", encoding="utf-8") as f:
        for r in sorted(results, key=lambda x: x["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Hand grades are applied AFTER the results file is written, so it keeps the automatic scores.
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    write_report(results, args, len(test_requests), timestamp)
    print("Done!")


if __name__ == "__main__":
    main()
