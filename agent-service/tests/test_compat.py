"""
Tests for compat.py, the standalone 6-rule judge used by eval/run_eval.py.

Project rule: missing or unrecognised data must give UNKNOWN, never a guess.
These tests add fake parts to the judge's lookup tables (with monkeypatch,
so the real catalogue is untouched after each test).
"""
import os
import subprocess
import sys

import pytest

import compat


@pytest.fixture
def add_part(monkeypatch):
    """Register a fake part under an id so find_spec() can see it."""
    def _add(part_id, **spec):
        spec.setdefault("name", f"Fake {part_id}")
        monkeypatch.setitem(compat.SPEC_BY_ID, part_id.lower(), spec)
        monkeypatch.setitem(compat.SPEC_BY_NAME, spec["name"].lower(), spec)
        return part_id
    return _add


# ─── Rule 6: budget ──────────────────────────────────────────────────────────
def test_budget_unknown_when_a_part_has_no_price(add_part):
    # Before the fix, a missing price counted as Rs.0, so this PASSed.
    add_part("gpu_noprice", category="gpu")
    verdict, reason = compat.rule_within_budget(["p1", "gpu_noprice"], budget=1_000_000)
    assert verdict == "UNKNOWN"
    assert "gpu_noprice" in reason or "Fake gpu_noprice" in reason


def test_budget_unknown_when_price_is_null(add_part):
    add_part("gpu_nullprice", category="gpu", price=None)
    verdict, _ = compat.rule_within_budget(["p1", "gpu_nullprice"], budget=1_000_000)
    assert verdict == "UNKNOWN"


def test_budget_still_passes_and_fails_with_real_prices():
    # p1 = 10500, g1 = 25000 -> total 35500
    assert compat.rule_within_budget(["p1", "g1"], budget=40000)[0] == "PASS"
    assert compat.rule_within_budget(["p1", "g1"], budget=30000)[0] == "FAIL"


# ─── Rule 5: form factor ─────────────────────────────────────────────────────
def test_formfactor_unknown_for_unrecognised_case(add_part):
    # Before the fix, an unknown case size gave allowed=[] -> FAIL (a guess).
    add_part("cab_eatx", category="cabinet", formFactor="E-ATX")
    verdict, _ = compat.rule_formfactor_fit(["m1", "cab_eatx"])
    assert verdict == "UNKNOWN"


def test_formfactor_unknown_for_unrecognised_motherboard(add_part):
    add_part("mobo_weird", category="motherboard", formFactor="SSI-CEB")
    verdict, _ = compat.rule_formfactor_fit(["mobo_weird", "cab2"])
    assert verdict == "UNKNOWN"


@pytest.mark.parametrize("case_ff", ["Micro-ATX", "micro atx", "mATX", "MATX", "uATX"])
def test_formfactor_spelling_variants_are_equivalent(add_part, case_ff):
    # m1 is an "mATX" board; every spelling of micro-ATX case should fit it.
    add_part("cab_var", category="cabinet", formFactor=case_ff)
    verdict, _ = compat.rule_formfactor_fit(["m1", "cab_var"])
    assert verdict == "PASS"


def test_formfactor_real_mismatch_still_fails(add_part):
    add_part("mobo_atx", category="motherboard", formFactor="ATX")
    # cab1 is an mATX case: a full ATX board does not fit.
    assert compat.rule_formfactor_fit(["mobo_atx", "cab1"])[0] == "FAIL"
    add_part("cab_itx", category="cabinet", formFactor="Mini-ITX")
    assert compat.rule_formfactor_fit(["m1", "cab_itx"])[0] == "FAIL"


# ─── Rule 2: socket ──────────────────────────────────────────────────────────
def test_socket_comparison_ignores_case_and_spacing(add_part):
    add_part("cpu_lc", category="processor", socket="lga 1700")
    verdict, _ = compat.rule_socket_match(["cpu_lc", "m1"])  # m1 socket "LGA1700"
    assert verdict == "PASS"


def test_socket_real_mismatch_still_fails():
    assert compat.rule_socket_match(["p3", "m1"])[0] == "FAIL"  # AM4 vs LGA1700


# ─── Rule 3: RAM type ────────────────────────────────────────────────────────
def test_ram_type_comparison_ignores_case(add_part):
    add_part("ram_lc", category="ram", ramType="ddr4")
    verdict, _ = compat.rule_ram_type_match(["ram_lc", "m2", "p1"])  # m2 DDR4, p1 DDR4/DDR5
    assert verdict == "PASS"


def test_ram_type_real_mismatch_still_fails():
    assert compat.rule_ram_type_match(["r1", "m1"])[0] == "FAIL"  # DDR4 RAM, DDR5 board


# ─── Self-test still runs as a script ────────────────────────────────────────
def test_script_self_test_good_passes_bad_fails():
    script = os.path.join(os.path.dirname(compat.__file__), "compat.py")
    out = subprocess.run(
        [sys.executable, script], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout
    good, bad = out.split("BAD BUILD")
    assert "OVERALL: PASS" in good
    assert "OVERALL: FAIL" in bad
