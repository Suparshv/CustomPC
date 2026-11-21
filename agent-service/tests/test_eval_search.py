"""
test_eval_search.py - Tests for the retrieval evaluation.

They check that the evaluation itself is honest:
- a card is only "correct" when the rule can actually be confirmed (missing data != pass),
- Precision@5 always divides by 5, even if a strategy returns fewer cards,
- the report's conclusions and corpus size come from the measured numbers, not hard-coded text.
"""

from eval_search import build_takeaways, evaluate_card, score_cards, write_markdown_report


# ─── Grading rules ─────────────────────────────────────────────────────────────
def test_gpu_with_unknown_length_is_not_graded_correct():
    """'GPU under 250mm': a GPU whose length we don't know is unconfirmed, not correct."""
    ok, reasons = evaluate_card({"name": "Mystery GPU", "category": "gpu"}, {"max_length": 250.0})
    assert ok is False
    assert any("could not confirm" in r for r in reasons)


def test_non_numeric_tdp_does_not_crash_the_evaluation():
    ok, reasons = evaluate_card(
        {"name": "Odd CPU", "category": "processor", "raw": {"tdp": "65 W"}},
        {"max_tdp": 65.0},
    )
    assert ok is False
    assert reasons


def test_known_short_gpu_is_correct():
    ok, _ = evaluate_card({"name": "Short GPU", "category": "gpu", "length_mm": 240.0}, {"max_length": 250.0})
    assert ok is True


# ─── Metrics ───────────────────────────────────────────────────────────────────
def test_precision_at_5_divides_by_5_not_by_cards_returned():
    """Returning 1 correct card is 1/5 precision, not 100%."""
    one_good_card = [{"name": "Short GPU", "category": "gpu", "length_mm": 200.0}]
    s = score_cards(one_good_card, {"max_length": 250.0}, top_k=5)
    assert s["hit"] == 1
    assert s["precision"] == 0.2


def test_no_cards_scores_zero():
    s = score_cards([], {"max_length": 250.0}, top_k=5)
    assert s == {"n_correct": 0, "hit": 0, "precision": 0.0, "reasons": []}


# ─── Report text must follow the data ──────────────────────────────────────────
def _summary(vec_hit, hyb_hit, rer_hit, per_query=None, corpus_size=2820):
    def strat(hit, prec, lat):
        return {
            "hit_at_5": hit, "precision_at_5": prec, "avg_latency_ms": lat,
            "fail_count": 0, "failing_queries": [],
            "group_breakdown": {g: {"hit_at_5": hit, "precision_at_5": prec}
                                for g in ["exact", "attribute", "descriptive"]},
        }
    return {
        "corpus_size": corpus_size,
        "n_queries": 30,
        "strategies": {
            "vector": strat(vec_hit, 60.0, 100.0),
            "hybrid": strat(hyb_hit, 66.0, 104.0),
            "hybrid_rerank": strat(rer_hit, 71.0, 180.0),
        },
        "per_query": per_query or {},
    }


def test_takeaways_recommend_the_measured_winner():
    """The old report always said hybrid was best, even when the table showed otherwise."""
    text = build_takeaways(_summary(vec_hit=90.0, hyb_hit=83.3, rer_hit=86.7))
    assert "Vector-only" in text.split("Recommendation")[1]
    assert "highest accuracy gains" not in text


def test_takeaways_list_queries_hybrid_fixed_and_broke():
    per_query = {
        "q12": {"query": "1TB NVMe", "vector": 1, "hybrid": 0, "hybrid_rerank": 1},
        "q23": {"query": "budget 6-core gaming CPU", "vector": 0, "hybrid": 1, "hybrid_rerank": 1},
    }
    text = build_takeaways(_summary(83.3, 83.3, 90.0, per_query=per_query))
    assert "q23" in text.split("fixed")[1].split("\n")[0]
    assert "q12" in text.split("broke")[1].split("\n")[0]


def test_takeaways_latency_comes_from_measurements():
    text = build_takeaways(_summary(83.3, 83.3, 90.0))
    assert "+4.0 ms" in text      # hybrid 104.0 vs vector 100.0
    assert "+76.0 ms" in text     # rerank 180.0 vs hybrid 104.0
    assert "2-5ms" not in text


def test_report_uses_measured_corpus_size(tmp_path):
    out = tmp_path / "report.md"
    write_markdown_report(_summary(83.3, 83.3, 90.0, corpus_size=1234), out)
    content = out.read_text(encoding="utf-8")
    assert "1,234" in content
    assert "2,820" not in content
