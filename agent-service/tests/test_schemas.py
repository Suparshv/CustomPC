import pytest
from pydantic import ValidationError
from schemas import (
    RouteDecision,
    BuildItem,
    Critique,
    ComparisonData,
    DraftBuild,
    ComponentReview,
    Reviews,
    Comparison,
)


def test_route_rejects_unknown_value():
    with pytest.raises(ValidationError):
        RouteDecision(route="BANANA")


def test_build_item_rejects_unknown_category():
    with pytest.raises(ValidationError):
        BuildItem(category="monitor", id="p1")


def test_rejection_needs_an_issue():
    with pytest.raises(ValidationError):
        Critique(approved=False, issues=[], reply="Bad build")


def test_comparison_rows_match_headers():
    with pytest.raises(ValidationError):
        ComparisonData(headers=["Spec", "A", "B"], rows=[["Cores", "6"]], verdict="A")


def test_valid_draft_build_parses():
    d = DraftBuild.model_validate_json(
        '{"reply":"ok","build":[{"category":"gpu","id":"g1"}],"budget":60000}'
    )
    assert d.build[0].id == "g1"


# Additional edge-case tests
def test_draft_build_rejects_duplicate_ids():
    with pytest.raises(ValidationError, match="the same part id appears twice"):
        DraftBuild(
            reply="Build drafted",
            build=[
                BuildItem(category="gpu", id="g1"),
                BuildItem(category="gpu", id="g1"),
            ],
            budget=50000,
        )


def test_draft_build_rejects_negative_budget():
    with pytest.raises(ValidationError):
        DraftBuild(
            reply="Build drafted",
            build=[BuildItem(category="gpu", id="g1")],
            budget=-500,
        )


def test_draft_build_rejects_empty_reply():
    with pytest.raises(ValidationError):
        DraftBuild(
            reply="",
            build=[BuildItem(category="gpu", id="g1")],
            budget=50000,
        )


def test_build_item_rejects_missing_field():
    with pytest.raises(ValidationError):
        BuildItem(category="processor")  # Missing id


def test_valid_critique_approved_without_issues():
    c = Critique(approved=True, issues=[], reply="Build is completely compatible!")
    assert c.approved is True
    assert len(c.issues) == 0


def test_comparison_valid_matches_headers():
    comp = ComparisonData(
        headers=["Spec", "RTX 4060", "RTX 3060"],
        rows=[
            ["VRAM", "8GB", "12GB"],
            ["TDP", "115W", "170W"],
        ],
        verdict="RTX 4060 is more efficient.",
    )
    assert len(comp.rows) == 2
    assert comp.verdict.startswith("RTX 4060")


def test_valid_reviews_parses():
    rev = Reviews(
        reviews=[
            ComponentReview(
                component="Intel Core i5-13600K",
                rating="4.5/5",
                pros=["Great gaming performance", "Strong multicore"],
                cons=["Runs warm under load"],
                summary="Solid mid-range CPU for gaming and workstation tasks.",
            )
        ]
    )
    assert len(rev.reviews) == 1
    assert rev.reviews[0].component == "Intel Core i5-13600K"


def test_component_review_rejects_missing_field():
    with pytest.raises(ValidationError):
        ComponentReview(
            component="RTX 4070",
            rating="4/5",
            # missing pros, cons, summary
        )


def test_valid_comparison_parses():
    comp = Comparison(
        comparisonData=ComparisonData(
            headers=["Feature", "RTX 4060", "RX 7600"],
            rows=[["VRAM", "8GB", "8GB"], ["Price", "₹28,000", "₹26,000"]],
            verdict="RTX 4060 has better power efficiency and DLSS support.",
        ),
        reply="Here is the side-by-side comparison you requested.",
    )
    assert comp.reply.startswith("Here is")
    assert len(comp.comparisonData.rows) == 2


def test_comparison_rejects_mismatched_row_counts():
    with pytest.raises(ValidationError):
        Comparison(
            comparisonData=ComparisonData(
                headers=["Feature", "A", "B"],
                rows=[["OnlyOneColumn"]],
                verdict="A",
            ),
            reply="Comparison result",
        )

