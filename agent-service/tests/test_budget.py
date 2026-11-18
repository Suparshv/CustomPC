"""
Tests for the code-side budget (catalog.extract_budget) and how llm.generate uses it.

Project rule: code decides the budget. A number is a budget only when the user
clearly wrote money; part model numbers (RTX 4060, Ryzen 5 5600, i5-12400) and
resolutions (4K, 1440p) are never money. No budget in the text -> None.
"""
import json
import os

import pytest

from catalog import extract_budget
from llm import BaseLLM, Raw
from prompts import ARCHITECT_SYSTEM, format_architect_user_prompt
from schemas import DraftBuild

REQUESTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "requests.jsonl")


# ─── Cases that were wrong before the fix ─────────────────────────────────────
@pytest.mark.parametrize("text, expected", [
    ("Build me a 4K gaming PC with RTX 5080 for 15000 rupees", 15000),   # was 4000
    ("Build me a high end 4K gaming PC, no budget limit", None),         # was 4000
    ("RTX 4060 build under 80000", 80000),                               # was 4060
    ("₹1,20,000 build", 120000),                                         # was 20000
    ("Ryzen 5 5600 with an LGA1700 motherboard", None),                  # was 5600
])
def test_previously_wrong_budgets(text, expected):
    assert extract_budget(text) == expected


# ─── Formats that must keep working ───────────────────────────────────────────
@pytest.mark.parametrize("text, expected", [
    ("80k build", 80000),
    ("1.5 lakh gaming pc", 150000),
    ("1.5L", 150000),
    ("75k", 75000),
    ("1 lakh", 100000),
    ("60,000", 60000),
    ("Rs. 50000", 50000),
    ("Rs.50000", 50000),
    ("under ₹45,000", 45000),
    ("budget 70000", 70000),
    ("₹60000", 60000),
    ("Gaming PC under 75000 INR", 75000),
    ("Workstation under 1.5 lakhs", 150000),
    ("my budget is 65000", 65000),
    ("70000 budget gaming pc", 70000),
])
def test_supported_budget_formats(text, expected):
    assert extract_budget(text) == expected


# ─── Things that look like numbers but are not money ──────────────────────────
@pytest.mark.parametrize("text", [
    "I want a PC for 4K gaming",
    "Build a 8K editing rig",
    "1440p gaming build with RTX tier GPU",
    "Build me a gaming PC for 1080p gaming",
    "i5-12400 with B550 and 7800X3D",
    "RTX 5070Ti and a 550W PSU",
    "16GB DDR4 3200MHz RAM",
    "Build a PC for 2 monitors",
    "Compare RTX 4060 vs RTX 3060",
])
def test_part_numbers_and_resolutions_are_not_budgets(text):
    assert extract_budget(text) is None


def test_model_number_next_to_a_real_budget():
    assert extract_budget("I want RTX 5080 and Intel i5 12400 together in a 50k build") == 50000
    assert extract_budget("4K gaming under 2 lakh with RTX 5080") == 200000


# ─── The eval request set ─────────────────────────────────────────────────────
# requests.jsonl's "budget" field is the budget the eval ASSUMES for scoring. For
# these ids the text itself states no budget, so code must return None
# (never guess). For every other id the text states the budget and must match exactly.
ASSUMED_NOT_STATED = {1, 3, 4, 5, 6, 7, 8, 10, 19, 20}


def load_requests():
    with open(REQUESTS_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.mark.parametrize("req", load_requests(), ids=lambda r: f"id{r['id']}")
def test_eval_requests(req):
    expected = None if req["id"] in ASSUMED_NOT_STATED else req["budget"]
    assert extract_budget(req["text"]) == expected


def test_assumed_budget_list_is_honest():
    """Every id listed as "assumed" really has a budget field in requests.jsonl."""
    by_id = {r["id"]: r for r in load_requests()}
    for i in ASSUMED_NOT_STATED:
        assert by_id[i]["budget"] is not None


# ─── The catalogue listing must never be read as a budget ─────────────────────
def test_parts_listing_is_never_scanned_for_a_budget():
    # The architect prompt contains every part with its price ("Rs.10500").
    # Only the user's own words may set the budget.
    assert extract_budget(format_architect_user_prompt("Build me a gaming PC")) is None
    assert extract_budget(format_architect_user_prompt("Build me a PC under 80k")) == 80000


# ─── llm.generate: code is the source of truth for the budget ─────────────────
class Fake(BaseLLM):
    provider, model = "fake", "fake"

    def __init__(self, *texts):
        self.texts = list(texts)

    def _complete(self, system, user, schema):
        return Raw(self.texts.pop(0), 10, 5)


GUESSED = '{"reply":"ok","build":[{"category":"gpu","id":"g1"}],"budget":75000}'


def test_model_guessed_budget_is_dropped_when_user_gave_none():
    r = Fake(GUESSED).generate("s", "Build me a gaming PC", DraftBuild)
    assert r.parsed.budget is None


def test_code_budget_overrides_model_budget():
    r = Fake(GUESSED).generate("s", "Build me a gaming PC under 60k", DraftBuild)
    assert r.parsed.budget == 60000


def test_budget_source_is_the_raw_request():
    # The prompt sent to the model contains the parts list with prices;
    # budget_source is the user's request only.
    prompt = format_architect_user_prompt("Build me a gaming PC")
    r = Fake(GUESSED).generate("s", prompt, DraftBuild, budget_source="Build me a gaming PC")
    assert r.parsed.budget is None
    r = Fake(GUESSED).generate("s", prompt, DraftBuild, budget_source="gaming PC for 90000 rupees")
    assert r.parsed.budget == 90000


def test_endpoint_uses_the_raw_message_for_budget(monkeypatch):
    from fastapi.testclient import TestClient
    import main

    seen = {}

    class Spy(Fake):
        def generate(self, system, user, schema, check=None, max_retries=2, budget_source=None):
            seen["budget_source"] = budget_source
            return super().generate(system, user, schema, check=None, budget_source=budget_source)

    monkeypatch.setattr(main, "get_current_llm", lambda: Spy(GUESSED))
    resp = TestClient(main.app).post("/debug/draft-build", json={"message": "PC for 4K gaming"})
    assert resp.status_code == 200
    assert seen["budget_source"] == "PC for 4K gaming"
    assert resp.json()["result"]["budget"] is None


def test_prompt_example_does_not_show_a_budget_number():
    # A concrete number in the example invites the model to copy it.
    assert "75000" not in ARCHITECT_SYSTEM
    assert '"budget": null' in ARCHITECT_SYSTEM
