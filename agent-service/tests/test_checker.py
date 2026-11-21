"""
test_checker.py - Unit tests for Deterministic Code-Based Compatibility Checker

Covers:
- PASS, FAIL, UNKNOWN for each of the 8 compatibility rules.
- Testing EVERY case type in the catalogue, verifying ATX boards FAIL in MicroATX Mid Tower.
- Strict exact/alias matching for GPU TDP (RX 7600 XT is 190W not 165W, RTX 3060 Ti LHR is 200W, RTX 3060 8GB is 115W).
- Unresolved string IDs returned explicitly in 'unresolved' list.
- Exact name/ID matching for cases and coolers (no fuzzy substring inheriting).
- 'checkable' flag calculation on components.
- Golden test: 100% verdict match with compat.py across all 30 baseline builds in eval/results.jsonl.
"""

import json
from pathlib import Path
import pytest

from checker import (
    check_all_categories,
    check_socket_match,
    check_ram_generation,
    check_psu_headroom,
    check_formfactor_fit,
    check_gpu_length,
    check_cooler_height,
    check_within_budget,
    check_build,
    is_part_checkable,
)

BASE_DIR = Path(__file__).resolve().parent.parent


# ─── 1. ALL CATEGORIES RULE & UNRESOLVED IDS ──────────────────────────────────
def test_all_categories_pass_fail():
    complete_build = [
        {"category": "processor", "name": "CPU"},
        {"category": "motherboard", "name": "Motherboard"},
        {"category": "gpu", "name": "GPU"},
        {"category": "ram", "name": "RAM"},
        {"category": "ps", "name": "SSD"},
        {"category": "ss", "name": "HDD"},
        {"category": "psu", "name": "PSU"},
        {"category": "cabinet", "name": "Case"},
        {"category": "cooling", "name": "Cooler"},
    ]
    v_pass, m_pass = check_all_categories(complete_build)
    assert v_pass == "PASS"

    # Missing cooling
    incomplete = [p for p in complete_build if p["category"] != "cooling"]
    v_fail, m_fail = check_all_categories(incomplete)
    assert v_fail == "FAIL"
    assert "cooling" in m_fail


def test_unresolved_string_ids_returned_in_list():
    """Unknown string IDs must not vanish silently; returned in 'unresolved'."""
    res = check_build(["gpu_unknown_999", "cpu_unknown_888"])
    assert res["valid"] is False
    assert len(res["unresolved"]) == 2
    assert "gpu_unknown_999" in res["unresolved"]
    assert "cpu_unknown_888" in res["unresolved"]
    assert "Unresolved part identifiers" in res["rules"]["all_categories"]["message"]


# ─── 2. SOCKET MATCH RULE ─────────────────────────────────────────────────────
def test_socket_match_pass_fail_unknown():
    # PASS
    parts_pass = [
        {"category": "processor", "socket": "AM5"},
        {"category": "motherboard", "socket": "AM5"},
    ]
    v, _ = check_socket_match(parts_pass)
    assert v == "PASS"

    # FAIL
    parts_fail = [
        {"category": "processor", "socket": "AM5"},
        {"category": "motherboard", "socket": "LGA1700"},
    ]
    v, _ = check_socket_match(parts_fail)
    assert v == "FAIL"

    # UNKNOWN (missing socket data)
    parts_unk1 = [
        {"category": "processor", "socket": None},
        {"category": "motherboard", "socket": "AM5"},
    ]
    v, _ = check_socket_match(parts_unk1)
    assert v == "UNKNOWN"

    # UNKNOWN (missing motherboard in build)
    parts_unk2 = [{"category": "processor", "socket": "AM5"}]
    v, _ = check_socket_match(parts_unk2)
    assert v == "UNKNOWN"


# ─── 3. RAM GENERATION RULE ───────────────────────────────────────────────────
def test_ram_generation_pass_fail_unknown():
    # PASS (DDR5 on AM5 motherboard and CPU)
    parts_pass = [
        {"category": "ram", "ram_type": "DDR5"},
        {"category": "motherboard", "ram_type": "DDR5"},
        {"category": "processor", "socket": "AM5", "ram_type": "DDR5"},
    ]
    v, _ = check_ram_generation(parts_pass)
    assert v == "PASS"

    # FAIL: Motherboard expects DDR5, got DDR4
    parts_fail_mobo = [
        {"category": "ram", "ram_type": "DDR4"},
        {"category": "motherboard", "ram_type": "DDR5"},
        {"category": "processor", "socket": "AM5"},
    ]
    v, _ = check_ram_generation(parts_fail_mobo)
    assert v == "FAIL"

    # FAIL: CPU socket AM5 does not support DDR4
    parts_fail_cpu = [
        {"category": "ram", "ram_type": "DDR4"},
        {"category": "motherboard", "ram_type": "DDR4"},
        {"category": "processor", "socket": "AM5"},
    ]
    v, _ = check_ram_generation(parts_fail_cpu)
    assert v == "FAIL"

    # UNKNOWN: RAM type missing
    parts_unk = [
        {"category": "ram", "ram_type": None},
        {"category": "motherboard", "ram_type": "DDR5"},
    ]
    v, _ = check_ram_generation(parts_unk)
    assert v == "UNKNOWN"


# ─── 4. PSU HEADROOM & STRICT GPU LOOKUP ─────────────────────────────────────
def test_psu_headroom_pass_fail_unknown():
    # PASS: CPU 65W, GPU 115W, Overhead 80W -> (65+115+80)*1.4 = 364W <= 550W PSU
    parts_pass = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "chipset": "GeForce RTX 4060", "tdp": 115},
        {"category": "psu", "wattage": 550},
    ]
    v, _ = check_psu_headroom(parts_pass)
    assert v == "PASS"

    # FAIL: CPU 170W, GPU 450W (RTX 4090), Overhead 80W -> (170+450+80)*1.4 = 980W > 650W PSU
    parts_fail = [
        {"category": "processor", "tdp": 170},
        {"category": "gpu", "chipset": "GeForce RTX 4090", "tdp": 450},
        {"category": "psu", "wattage": 650},
    ]
    v, _ = check_psu_headroom(parts_fail)
    assert v == "FAIL"


def test_gpu_tdp_exact_matching_no_fuzzy_leak():
    """
    Verify GPU TDP lookup does not use fuzzy substring matching.
    RX 7600 XT must get 190W (not 165W from RX 7600).
    RTX 3060 Ti LHR must get 200W (not 170W from RTX 3060).
    RTX 3060 8GB must get 115W (not 170W from RTX 3060 12GB).
    Uncurated variant must return UNKNOWN.
    """
    # RX 7600 XT: 190W. With 65W CPU: (65 + 190 + 80) * 1.4 = 469W.
    # If it wrongly got 165W: (65 + 165 + 80) * 1.4 = 434W.
    # A 450W PSU must FAIL with 190W (450 < 469), but would pass with 165W (450 > 434)!
    parts_rx7600xt = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "chipset": "Radeon RX 7600 XT", "tdp": None},
        {"category": "psu", "wattage": 450},
    ]
    v1, m1 = check_psu_headroom(parts_rx7600xt)
    assert v1 == "FAIL", f"Expected FAIL with 190W GPU, got {v1} ({m1})"
    assert "469W" in m1

    # RTX 3060 Ti LHR: 200W. (65 + 200 + 80) * 1.4 = 483W.
    # A 475W PSU must FAIL!
    parts_3060ti = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "chipset": "GeForce RTX 3060 Ti LHR", "tdp": None},
        {"category": "psu", "wattage": 475},
    ]
    v2, m2 = check_psu_headroom(parts_3060ti)
    assert v2 == "FAIL"
    assert "483W" in m2

    # RTX 3060 8GB: 115W. (65 + 115 + 80) * 1.4 = 364W.
    # A 400W PSU passes!
    parts_3060_8gb = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "chipset": "GeForce RTX 3060 8GB", "tdp": None},
        {"category": "psu", "wattage": 400},
    ]
    v3, m3 = check_psu_headroom(parts_3060_8gb)
    assert v3 == "PASS"

    # Completely uncurated GPU: Must return UNKNOWN, not fuzzy match any known card!
    parts_uncurated = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "chipset": "GeForce RTX 3060 Ultra Custom Special Edition", "tdp": None},
        {"category": "psu", "wattage": 650},
    ]
    v4, _ = check_psu_headroom(parts_uncurated)
    assert v4 == "UNKNOWN"


# ─── 5. FORM FACTOR FIT & EVERY CASE TYPE TEST ────────────────────────────────
def test_formfactor_microatx_mid_tower_rejects_atx():
    """An ATX board in a 'MicroATX Mid Tower' case must return FAIL!"""
    parts = [
        {"category": "motherboard", "form_factor": "ATX"},
        {"category": "cabinet", "case_type": "MicroATX Mid Tower"},
    ]
    v, m = check_formfactor_fit(parts)
    assert v == "FAIL", f"Expected FAIL for ATX board in MicroATX Mid Tower, got {v} ({m})"


def test_formfactor_fit_all_catalogue_case_types():
    """
    Test EVERY case type in the catalogue against all motherboard form factors.
    Catalogue case types:
    - 'ATX Full Tower'
    - 'ATX Mid Tower'
    - 'ATX Desktop'
    - 'MicroATX Mid Tower'
    - 'MicroATX Mini Tower'
    - 'MicroATX Desktop'
    - 'Mini ITX Tower'
    - 'Mini ITX Desktop'
    - 'HTPC'
    """
    case_types = [
        "ATX Full Tower",
        "ATX Mid Tower",
        "ATX Desktop",
        "MicroATX Mid Tower",
        "MicroATX Mini Tower",
        "MicroATX Desktop",
        "Mini ITX Tower",
        "Mini ITX Desktop",
        "HTPC",
    ]

    for ctype in case_types:
        cab = [{"category": "cabinet", "case_type": ctype}]

        # 1. HTPC always returns UNKNOWN
        if ctype == "HTPC":
            for mb_ff in ["ATX", "Micro ATX", "Mini ITX", "EATX"]:
                v, _ = check_formfactor_fit([{"category": "motherboard", "form_factor": mb_ff}] + cab)
                assert v == "UNKNOWN"
            continue

        # 2. EATX: Only passes in Full Tower
        v_eatx, _ = check_formfactor_fit([{"category": "motherboard", "form_factor": "EATX"}] + cab)
        if ctype == "ATX Full Tower":
            assert v_eatx == "PASS"
        else:
            assert v_eatx == "FAIL"

        # 3. ATX: Passes in Full Tower, Mid Tower, and ATX Desktop; FAILS in all MicroATX and Mini ITX cases!
        v_atx, _ = check_formfactor_fit([{"category": "motherboard", "form_factor": "ATX"}] + cab)
        if ctype in ("ATX Full Tower", "ATX Mid Tower", "ATX Desktop"):
            assert v_atx == "PASS"
        else:
            assert v_atx == "FAIL", f"ATX should FAIL in {ctype}, but got {v_atx}"

        # 4. Micro ATX: Passes in Full Tower, Mid Tower, ATX Desktop, and MicroATX cases; FAILS in Mini ITX cases!
        v_matx, _ = check_formfactor_fit([{"category": "motherboard", "form_factor": "Micro ATX"}] + cab)
        if ctype in ("Mini ITX Tower", "Mini ITX Desktop"):
            assert v_matx == "FAIL", f"Micro ATX should FAIL in {ctype}, but got {v_matx}"
        else:
            assert v_matx == "PASS", f"Micro ATX should PASS in {ctype}, but got {v_matx}"

        # 5. Mini ITX: Fits in ALL non-HTPC cases!
        v_mitx, _ = check_formfactor_fit([{"category": "motherboard", "form_factor": "Mini ITX"}] + cab)
        assert v_mitx == "PASS", f"Mini ITX should PASS in {ctype}, but got {v_mitx}"


# ─── 6. GPU LENGTH RULE & NO FUZZY NAME LEAK ──────────────────────────────────
def test_gpu_length_pass_fail_unknown():
    # PASS: 192 mm GPU in cab1 (Deepcool Macube 110, limit 320 mm)
    parts_pass = [
        {"category": "gpu", "length": 192, "name": "Gigabyte RTX 4060"},
        {"category": "cabinet", "id": "cab1", "name": "Deepcool Macube 110"},
    ]
    v, _ = check_gpu_length(parts_pass)
    assert v == "PASS"

    # FAIL: 340 mm GPU in cab1 (limit 320 mm)
    parts_fail = [
        {"category": "gpu", "length": 340, "name": "Gigabyte RTX 4090"},
        {"category": "cabinet", "id": "cab1", "name": "Deepcool Macube 110"},
    ]
    v, _ = check_gpu_length(parts_fail)
    assert v == "FAIL"


def test_case_no_fuzzy_name_matching():
    """'Corsair 4000D' must NOT inherit 'Corsair 4000D Airflow' limits via substring."""
    parts = [
        {"category": "gpu", "length": 350, "name": "RTX 4080"},
        {"category": "cabinet", "id": "cab_uncured_diff", "name": "Corsair 4000D"},
    ]
    v, _ = check_gpu_length(parts)
    assert v == "UNKNOWN"


# ─── 7. COOLER HEIGHT RULE & NO FUZZY MATCH ───────────────────────────────────
def test_cooler_height_pass_fail_unknown():
    # PASS: Air cooler 154 mm in cab1 (limit 165 mm)
    parts_pass = [
        {"category": "cooling", "cooler_kind": "air", "id": "cool_70af1a5d8ce2", "name": "Thermalright Phantom Spirit 120 SE", "height": 154},
        {"category": "cabinet", "id": "cab1", "name": "Deepcool Macube 110"},
    ]
    v, _ = check_cooler_height(parts_pass)
    assert v == "PASS"

    # FAIL: Air cooler 170 mm in cab2 (GALAX Revolution-06, limit 160 mm)
    parts_fail = [
        {"category": "cooling", "cooler_kind": "air", "height": 170, "name": "Gigantic Air Cooler"},
        {"category": "cabinet", "id": "cab2", "name": "GALAX Revolution-06 Mesh RGB"},
    ]
    v, _ = check_cooler_height(parts_fail)
    assert v == "FAIL"

    # UNKNOWN: Liquid (AIO) coolers return UNKNOWN
    parts_liquid = [
        {"category": "cooling", "cooler_kind": "liquid", "name": "Cooler Master Liquid 240L"},
        {"category": "cabinet", "id": "cab1", "name": "Deepcool Macube 110"},
    ]
    v_liq, _ = check_cooler_height(parts_liquid)
    assert v_liq == "UNKNOWN"


# ─── 8. WITHIN BUDGET RULE ────────────────────────────────────────────────────
def test_within_budget_pass_fail_unknown():
    parts = [
        {"category": "processor", "name": "CPU", "price": 15000},
        {"category": "gpu", "name": "GPU", "price": 25000},
    ]

    # PASS: 40,000 <= 50,000
    v_pass, _ = check_within_budget(parts, budget=50000)
    assert v_pass == "PASS"

    # FAIL: 40,000 > 35,000
    v_fail, _ = check_within_budget(parts, budget=35000)
    assert v_fail == "FAIL"

    # UNKNOWN: No budget provided
    v_unk_nobudget, _ = check_within_budget(parts, budget=None)
    assert v_unk_nobudget == "UNKNOWN"


# ─── 9. CHECKABLE PARTS INSPECTOR ─────────────────────────────────────────────
def test_is_part_checkable_flag():
    """Verify 'checkable' flag detects parts with sufficient data."""
    # Checkable CPU
    cpu = {"category": "processor", "socket": "AM5", "tdp": 65}
    assert is_part_checkable(cpu) is True

    # Uncheckable GPU (missing length and uncurated)
    gpu_bad = {"category": "gpu", "chipset": "Unknown 999", "length": None}
    assert is_part_checkable(gpu_bad) is False

    # Checkable GPU
    gpu_good = {"category": "gpu", "chipset": "GeForce RTX 4060", "length": 192}
    assert is_part_checkable(gpu_good) is True

    # AIO Cooler is not checkable for air clearance
    aio = {"category": "cooling", "cooler_kind": "liquid"}
    assert is_part_checkable(aio) is False

    # Air Cooler with curated height
    air = {"category": "cooling", "cooler_kind": "air", "id": "cool_70af1a5d8ce2"}
    assert is_part_checkable(air) is True


# ─── 10. GOLDEN TEST: 100% AGREEMENT WITH COMPAT.PY ACROSS 30 BASELINE BUILDS ──
def test_golden_baseline_evaluation_matches_compat_py():
    """
    Load the 30 baseline builds from eval/results.jsonl and check that the new
    checker's valid/invalid verdict and failure reasons match compat.py on the 6 shared rules.
    """
    import sys
    sys.path.insert(0, str(BASE_DIR))
    import compat

    eval_path = BASE_DIR.parent / "eval" / "results.jsonl"
    assert eval_path.exists(), f"eval/results.jsonl not found at {eval_path}"

    with open(eval_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    assert len(records) == 30, f"Expected 30 baseline builds, found {len(records)}"

    shared_rule_map = {
        "1_all_categories": "all_categories",
        "2_socket_match": "socket_match",
        "3_ram_type_match": "ram_type_match",
        "4_psu_sufficient": "psu_headroom",
        "5_formfactor_fit": "formfactor_fit",
        "6_within_budget": "within_budget",
    }

    for rec in records:
        build_id = rec.get("id")
        parts = rec.get("build_part_ids")
        budget = rec.get("budget")

        # 1. Baseline compat.py verdict
        compat_results = compat.judge_build(parts, budget=budget)
        compat_fails = {r for r, (v, _) in compat_results.items() if v == "FAIL"}
        compat_valid = len(compat_fails) == 0

        # 2. checker.py verdict on shared rules
        checker_res = check_build(parts, budget=budget)
        checker_shared_fails = {
            old_name for old_name, new_name in shared_rule_map.items()
            if checker_res["rules"][new_name]["verdict"] == "FAIL"
        }
        checker_shared_valid = len(checker_shared_fails) == 0

        # Must agree 100% on valid/invalid
        assert compat_valid == checker_shared_valid, (
            f"Build #{build_id} valid mismatch: compat={compat_valid}, checker={checker_shared_valid}"
        )

        # Must agree 100% on exact shared rule failures
        assert compat_fails == checker_shared_fails, (
            f"Build #{build_id} fail mismatch: compat={compat_fails}, checker={checker_shared_fails}"
        )


# ─── Every part is checked, unknown totals are UNKNOWN ─────────────────────────────
# Builds with two RAM kits, GPUs or CPUs, unknown prices, and partial (step-by-step) builds.

def test_ram_rule_checks_every_ram_kit():
    """A second, incompatible RAM kit must not hide behind the first one."""
    parts = [
        {"category": "processor", "socket": "AM5", "ram_type": "DDR5"},
        {"category": "motherboard", "socket": "AM5", "ram_type": "DDR5"},
        {"category": "ram", "name": "Good DDR5 kit", "ram_type": "DDR5"},
        {"category": "ram", "name": "Wrong DDR4 kit", "ram_type": "DDR4"},
    ]
    v, msg = check_ram_generation(parts)
    assert v == "FAIL"
    assert "DDR4" in msg


def test_psu_rule_counts_every_gpu():
    """Two GPUs draw power together: (65 + 100 + 450 + 80) * 1.4 = 973 W > 550 W."""
    parts = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "name": "Small GPU", "tdp": 100},
        {"category": "gpu", "name": "Big GPU", "tdp": 450},
        {"category": "psu", "wattage": 550},
    ]
    v, msg = check_psu_headroom(parts)
    assert v == "FAIL"
    assert "973" in msg


def test_gpu_length_rule_checks_every_gpu():
    parts = [
        {"category": "gpu", "name": "Short GPU", "length": 200},
        {"category": "gpu", "name": "Long GPU", "length": 340},
        {"category": "cabinet", "name": "Small Case", "raw": {"max_gpu_length_mm": 300}},
    ]
    v, msg = check_gpu_length(parts)
    assert v == "FAIL"
    assert "Long GPU" in msg


def test_two_cpus_fail_one_per_slot_rule():
    """A PC has one CPU socket, one board, one PSU, one case and one CPU cooler."""
    res = check_build([
        {"category": "processor", "name": "CPU A", "socket": "AM5"},
        {"category": "processor", "name": "CPU B", "socket": "AM5"},
        {"category": "motherboard", "name": "Board", "socket": "AM5"},
    ])
    assert res["rules"]["one_per_slot"]["verdict"] == "FAIL"
    assert "processor" in res["rules"]["one_per_slot"]["message"]
    assert res["valid"] is False


def test_within_budget_unknown_when_a_part_is_unresolved():
    """If a part could not be found, its price is unknown, so the total is unknown."""
    res = check_build(["p3", "ghost_gpu_123"], budget=20000)
    assert res["rules"]["within_budget"]["verdict"] == "UNKNOWN"
    assert res["total_price"] is None


def test_partial_build_mode_reports_missing_categories_as_unknown():
    """While an agent builds step by step, missing categories are 'not chosen yet', not a failure."""
    full = check_build(["p3", "m3", "r2"])
    assert full["rules"]["all_categories"]["verdict"] == "FAIL"

    partial = check_build(["p3", "m3", "r2"], partial=True)
    assert partial["rules"]["all_categories"]["verdict"] == "UNKNOWN"
    assert partial["rules"]["socket_match"]["verdict"] == "PASS"
    assert partial["valid"] is True
    assert partial["fully_verified"] is False


def test_partial_build_mode_still_fails_on_unresolved_ids():
    partial = check_build(["p3", "ghost_board_1"], partial=True)
    assert partial["valid"] is False
    assert "ghost_board_1" in partial["unresolved"]


# ─── Numbers as data, not only text ─────────────────────────────────────────────
# The agent needs the required PSU watts as a NUMBER
# (to filter PSUs, and to repair a too-weak PSU), even before a PSU is chosen.
def test_check_build_returns_required_psu_watts_as_data():
    res = check_build([
        {"category": "processor", "name": "CPU", "tdp": 65},
        {"category": "gpu", "name": "GPU", "tdp": 115},
    ], partial=True)
    assert res["required_psu_watts"] == 364   # ceil((65 + 115 + 80) * 1.4)


def test_required_psu_watts_is_none_when_a_tdp_is_unknown():
    res = check_build([
        {"category": "processor", "name": "CPU", "tdp": 65},
        {"category": "gpu", "name": "Mystery GPU"},
    ], partial=True)
    assert res["required_psu_watts"] is None


# ─── GPU power ratings for the 17 catalogue models that had none ─────────────────
# Before these ratings were added, 75 of 313 catalogue GPUs had no TDP, so the
# PSU rule was UNKNOWN for them and the agent could not filter PSUs by watts.
import json as _json
import pytest as _pytest
from checker import _resolve_gpu_tdp

CONFIRMED_GPU_TDP = {   # reference-design values from nvidia.com / amd.com (sources in the JSON)
    "GeForce RTX 5050": 130, "GeForce RTX 5060": 145, "GeForce RTX 5060 Ti": 180,
    "Radeon RX 9060 XT": 160, "Radeon RX 9070": 220, "Radeon RX 9070 XT": 304,
    "Radeon RX 6950 XT": 335, "GeForce RTX 2060": 160, "GeForce RTX 2060 12GB": 185,
    "GeForce RTX 2060 SUPER": 175, "GeForce RTX 2070": 175, "GeForce RTX 2070 SUPER": 215,
    "GeForce RTX 2080": 215, "GeForce RTX 2080 SUPER": 250, "GeForce RTX 2080 Ti": 250,
}


@_pytest.mark.parametrize("chipset,watts", sorted(CONFIRMED_GPU_TDP.items()))
def test_catalogue_gpu_models_have_a_sourced_tdp(chipset, watts):
    assert _resolve_gpu_tdp({"chipset": chipset, "name": "Some partner card"}) == watts


# RX 6500 XT / RX 6400: checked by hand on AMD's pages (the research agent could not open them).
# The table holds one value per chip, so the RX 6500 XT uses the higher of 4 GB 107 W / 8 GB 113 W.
@_pytest.mark.parametrize("chipset,watts", [("Radeon RX 6500 XT", 113), ("Radeon RX 6400", 53)])
def test_hand_checked_amd_gpu_tdp(chipset, watts):
    assert _resolve_gpu_tdp({"chipset": chipset, "name": "Some partner card"}) == watts


def test_every_gpu_tdp_entry_has_a_source():
    table = _json.load(open(BASE_DIR / "data" / "curated" / "gpu_tdp.json", encoding="utf-8"))
    for chipset, info in table.items():
        assert info.get("source_url", "").startswith("https://"), chipset
