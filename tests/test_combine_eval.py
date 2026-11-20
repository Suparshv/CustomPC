"""
Tests for eval/combine_eval.py: the combined Day 13 results table.
Written BEFORE the script existed. Offline: no MongoDB, no requests.

The table must be built from the saved results files only (no hand-typed numbers),
show counts AND percentages, and never invent a number for a row that has not run.
"""
import importlib.util
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
_spec = importlib.util.spec_from_file_location("combine_eval", os.path.join(ROOT, "eval", "combine_eval.py"))
combine_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(combine_eval)

PRICE = {"input_per_m": 0.30, "output_per_m": 2.50}   # Gemini 3.5 Flash-Lite, read 20 Nov 2026


def _row(id_, type_, score, elapsed=10.0, prompt=1000, output=100, version=None):
    return {"id": id_, "type": type_, "success": True, "elapsed_s": elapsed, "reply": "r",
            "build_part_ids": [], "total_tokens": prompt + output, "prompt_tokens": prompt,
            "candidate_tokens": output, "score": score, "budget": None, "text": "t",
            "code_version": version}


def test_paid_equivalent_cost_uses_the_price_list():
    # 1,000,000 input tokens at $0.30 + 100,000 output tokens at $2.50 = $0.30 + $0.25
    assert combine_eval.paid_equivalent_usd(1_000_000, 100_000, PRICE) == pytest.approx(0.55)


def test_no_price_means_no_cost():
    assert combine_eval.paid_equivalent_usd(1000, 100, None) is None


def test_summary_counts_cost_and_median():
    rows = [
        _row(1, "normal_build", {"valid": True, "produced_build": True}, elapsed=10),
        _row(2, "normal_build", {"valid": False, "produced_build": True}, elapsed=30),
        _row(3, "off_topic", {"handled_correctly": True}, elapsed=2),
    ]
    s = combine_eval.summarize(rows, PRICE)
    assert s["valid"] == (1, 2)
    assert s["median_s"] == 10
    assert s["avg_tokens"] == 1100
    # 3 requests x (1000 in, 100 out) -> per request $0.0003 + $0.00025
    assert s["usd_per_request"] == pytest.approx(0.00055)


def test_summary_counts_impossible_requests_still_needing_a_hand_grade():
    rows = [_row(16, "impossible", {"handled_correctly": False, "needs_hand_grade": True}),
            _row(17, "impossible", {"handled_correctly": True, "manual_grade": "correct"})]
    assert combine_eval.summarize(rows, None)["needs_hand_grade"] == 1


def test_summary_collects_code_versions():
    v = {"commit": "abc1234", "uncommitted": []}
    rows = [_row(1, "off_topic", {"handled_correctly": True}, version=v),
            _row(2, "off_topic", {"handled_correctly": True}, version=v)]
    assert combine_eval.summarize(rows, None)["code_versions"] == ["abc1234"]


def test_count_cell_shows_count_and_percent():
    assert combine_eval.count_cell((7, 10)) == "7/10 (70%)"
    assert combine_eval.count_cell((0, 0)) == "n/a"


def test_a_row_that_has_not_run_is_marked_not_numbered():
    table = combine_eval.render_tables([{"key": "E", "label": "v2 off, Llama", "summary": None}])
    lines = [l for l in table.splitlines() if l.startswith("| E ")]
    assert lines and all("not run yet" in l and "%" not in l for l in lines)


def test_rendered_table_has_counts_seconds_tokens_and_cost():
    rows = [_row(1, "normal_build", {"valid": True, "produced_build": True})]
    table = combine_eval.render_tables([{"key": "D", "label": "v2 on, Gemini",
                                         "summary": combine_eval.summarize(rows, PRICE)}])
    text = "\n".join(l for l in table.splitlines() if l.startswith("| D "))
    assert "1/1 (100%)" in text and "10.0" in text and "1,100" in text and "$0.00055" in text


def test_replace_between_markers_keeps_the_rest_of_the_file():
    doc = "intro\n<!-- combined:start -->\nold\n<!-- combined:end -->\noutro\n"
    out = combine_eval.replace_between_markers(doc, "NEW")
    assert out == "intro\n<!-- combined:start -->\nNEW\n<!-- combined:end -->\noutro\n"


def test_replace_between_markers_refuses_a_file_without_markers():
    with pytest.raises(ValueError):
        combine_eval.replace_between_markers("no markers here", "NEW")
