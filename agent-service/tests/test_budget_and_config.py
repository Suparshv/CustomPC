"""
Tests for the budget planner and the agent switches.
"""

import pytest

from agent_config import AgentConfig
from budget import BUDGET_SHARES, PICK_ORDER, category_cap


# ─── Budget planner ────────────────────────────────────────────────────────────
def test_every_category_has_a_share_and_shares_sum_to_one():
    assert sorted(BUDGET_SHARES) == sorted(PICK_ORDER)
    assert abs(sum(BUDGET_SHARES.values()) - 1.0) < 1e-9
    assert len(PICK_ORDER) == 9


def test_first_cap_is_the_category_share_of_the_budget():
    assert category_cap("processor", 100000, spent=0, picked=[]) == pytest.approx(100000 * BUDGET_SHARES["processor"])


def test_unspent_money_carries_forward():
    """CPU share is 17,000 of 100,000. Spending only 9,000 leaves more for the next parts."""
    frugal = category_cap("motherboard", 100000, spent=9000, picked=["processor"])
    exact = category_cap("motherboard", 100000, spent=100000 * BUDGET_SHARES["processor"], picked=["processor"])
    assert frugal > exact
    # The motherboard gets its share of what is LEFT, among the categories still to pick.
    remaining_shares = sum(BUDGET_SHARES[c] for c in PICK_ORDER if c != "processor")
    assert frugal == pytest.approx((100000 - 9000) * BUDGET_SHARES["motherboard"] / remaining_shares)


def test_last_category_may_use_everything_left():
    picked = [c for c in PICK_ORDER if c != "ss"]
    assert category_cap("ss", 100000, spent=96000, picked=picked) == pytest.approx(4000)


def test_no_budget_means_no_cap():
    assert category_cap("gpu", None, spent=0, picked=[]) is None


def test_overspent_budget_gives_zero_cap_not_negative():
    assert category_cap("gpu", 50000, spent=60000, picked=["processor"]) == 0


# ─── Switches (config) ─────────────────────────────────────────────────────────
def test_defaults_are_all_upgrades_on():
    cfg = AgentConfig()
    assert cfg.use_tools and cfg.use_checker
    assert cfg.repair_loops == 2
    assert cfg.retriever == "hybrid_rerank"


def test_config_reads_environment_variables():
    cfg = AgentConfig.from_env({
        "AGENT_RETRIEVER": "vector",
        "AGENT_USE_TOOLS": "0",
        "AGENT_USE_CHECKER": "false",
        "AGENT_REPAIR_LOOPS": "0",
        "AGENT_MAX_STEPS": "12",
    })
    assert (cfg.retriever, cfg.use_tools, cfg.use_checker, cfg.repair_loops, cfg.max_steps) == \
        ("vector", False, False, 0, 12)


def test_a_request_can_override_the_config():
    """The eval runs the same code with different switches per run."""
    base = AgentConfig()
    off = base.with_overrides({"use_checker": False, "repair_loops": 0})
    assert off.use_checker is False and off.repair_loops == 0
    assert base.use_checker is True  # the original is not changed


@pytest.mark.parametrize("bad", [{"repair_loops": 3}, {"repair_loops": -1}, {"retriever": "magic"}, {"max_steps": 0}])
def test_invalid_switch_values_are_rejected(bad):
    with pytest.raises(ValueError):
        AgentConfig().with_overrides(bad)
