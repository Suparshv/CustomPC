"""
combine_eval.py - Day 13: one combined results table for every row of the plan.

Every number comes from the SAVED results files, re-scored with today's rules by the same
code as run_eval.py (checker.py + MongoDB part data), with each run's own hand grades.
Nothing is typed by hand, and a row that has not run shows "not run yet", never a number.

Usage (from the repo root, MongoDB running):
    python eval/combine_eval.py
It prints the tables and writes them between the markers in docs/eval.md and README.md:
    <!-- combined:start -->  ...  <!-- combined:end -->
"""

import importlib.util
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

_spec = importlib.util.spec_from_file_location("run_eval", os.path.join(HERE, "run_eval.py"))
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)

START, END = "<!-- combined:start -->", "<!-- combined:end -->"

# Paid-tier (Standard) price of gemini-3.5-flash-lite, USD per 1M tokens, read from Google's
# pricing page (aistudio.google.com/docs/pricing) on 20 Nov 2026. Output includes thinking
# tokens; our calls use none (checked on one call: thoughts_token_count was empty).
GEMINI_PRICE = {"input_per_m": 0.30, "output_per_m": 2.50}

# The frozen plan (docs/eval.md). Row B was skipped by decision on 20 Nov 2026.
ROWS = [
    {"key": "A", "label": "Old Node system, Gemini", "results": "eval/results.jsonl",
     "grades": "eval/manual_grades.json", "price": GEMINI_PRICE,
     "version_note": "a4ed31e (8 Nov, from the baseline notes)"},
    {"key": "C", "label": "New, upgrades off, Gemini", "results": "eval/results-v2-off-gemini.jsonl",
     "grades": "eval/grades-v2-off-gemini.json", "price": GEMINI_PRICE},
    {"key": "D", "label": "New, upgrades on, Gemini", "results": "eval/results-v2-on-gemini.jsonl",
     "grades": "eval/grades-v2-on-gemini.json", "price": GEMINI_PRICE},
    {"key": "E", "label": "New, upgrades off, Llama 3.1 8B", "results": "eval/results-v2-off-llama.jsonl",
     "grades": "eval/grades-v2-off-llama.json", "price": None},
    {"key": "F", "label": "New, upgrades on, Llama 3.1 8B", "results": "eval/results-v2-on-llama.jsonl",
     "grades": "eval/grades-v2-on-llama.json", "price": None},
]


def paid_equivalent_usd(prompt_tokens, output_tokens, price):
    """What these tokens would cost on the paid tier. None when there is no per-token price (Ollama)."""
    if price is None:
        return None
    return prompt_tokens / 1e6 * price["input_per_m"] + output_tokens / 1e6 * price["output_per_m"]


def summarize(results, price):
    """The numbers for one row, from scored (and hand-graded) results."""
    m = run_eval.compute_metrics(results)
    costs = [paid_equivalent_usd(r.get("prompt_tokens", 0) or 0, r.get("candidate_tokens", 0) or 0, price)
             for r in results]
    versions = []
    for r in results:
        v = r.get("code_version") or {}
        if v.get("commit"):
            text = v["commit"] + ("+uncommitted" if v.get("uncommitted") else "")
            if text not in versions:
                versions.append(text)
    return {
        **{k: m[k] for k in ("valid", "within_budget", "success", "refused", "unknown", "fully_verified",
                             "comparison", "impossible", "off_topic", "vague")},
        "needs_hand_grade": sum(1 for r in results if r["type"] == "impossible"
                                and r["score"].get("needs_hand_grade")),
        "median_s": statistics.median(r["elapsed_s"] for r in results) if results else None,
        "avg_tokens": round(sum(r["total_tokens"] for r in results) / len(results)) if results else None,
        "usd_per_request": (sum(costs) / len(costs)) if results and price is not None else None,
        "errored": m["errored_total"],
        "code_versions": versions,
    }


def count_cell(pair):
    """(7, 10) -> '7/10 (70%)'. With nothing to count -> 'n/a'."""
    num, denom = pair
    if not denom:
        return "n/a"
    p = 100 * num / denom
    return f"{num}/{denom} ({p:.0f}%)" if p == int(p) else f"{num}/{denom} ({p:.1f}%)"


def render_tables(rows):
    """Two markdown tables: build requests, then the other request types + time, tokens and cost."""
    t1 = ["| Row | System | Valid builds | Within budget | Success | Refused | Unknown | Fully verified |",
          "|---|---|---|---|---|---|---|---|"]
    t2 = ["| Row | System | Comparisons | Impossible (hand-graded) | Off-topic | Vague | Median s | "
          "Avg tokens | Paid-equivalent $/request | Errored | Code version |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        s = row.get("summary")
        head = f"| {row['key']} | {row['label']} |"
        if s is None:
            t1.append(head + " not run yet |" * 6)
            t2.append(head + " not run yet |" * 9)
            continue
        t1.append(head + " " + " | ".join(count_cell(s[k]) for k in
                                          ("valid", "within_budget", "success", "refused", "unknown",
                                           "fully_verified")) + " |")
        impossible = count_cell(s["impossible"])
        if s["needs_hand_grade"]:
            impossible += f", {s['needs_hand_grade']} need a hand grade"
        cost = f"${s['usd_per_request']:.5f}" if s["usd_per_request"] is not None else "no per-token price"
        version = ", ".join(s["code_versions"]) or row.get("version_note") or "not recorded"
        t2.append(f"{head} {count_cell(s['comparison'])} | {impossible} | {count_cell(s['off_topic'])} | "
                  f"{count_cell(s['vague'])} | {s['median_s']:.1f} | {s['avg_tokens']:,} | {cost} | "
                  f"{s['errored']} | {version} |")
    return "\n".join(["**Build requests** (10 per run)", "", *t1, "",
                      "**Other requests, time, tokens and cost** (all 30 requests)", "", *t2])


def replace_between_markers(text, table):
    """Put `table` between the combined-table markers; the rest of the file is kept as it is."""
    start, end = text.find(START), text.find(END)
    if start < 0 or end < start:
        raise ValueError(f"The file has no {START} ... {END} markers.")
    return text[:start + len(START)] + "\n" + table + "\n" + text[end:]


def load_rows(path):
    """All saved rows of a run (errored ones too: they are counted, not hidden)."""
    with open(path, encoding="utf-8") as f:
        return sorted((json.loads(line) for line in f if line.strip()), key=lambda r: r["id"])


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    rows = []
    for spec in ROWS:
        path = os.path.join(ROOT, spec["results"])
        summary = None
        if os.path.exists(path):
            results = load_rows(path)
            lookup = run_eval.load_part_lookup_or_exit(results)
            results = run_eval.rescore_results(results, part_lookup=lookup)
            run_eval.apply_manual_grades(results, run_eval.load_manual_grades(os.path.join(ROOT, spec["grades"])))
            summary = summarize(results, spec["price"])
        rows.append({**spec, "summary": summary})

    table = render_tables(rows)
    print(table)
    for name in ("docs/eval.md", "README.md"):
        path = os.path.join(ROOT, name)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(replace_between_markers(text, table))
        print(f"Updated {name}")


if __name__ == "__main__":
    main()
