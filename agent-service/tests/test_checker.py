"""
test_checker.py - Unit tests for Deterministic Code-Based Compatibility Checker (Day 7)

Covers:
- PASS, FAIL, UNKNOWN for each of the 8 compatibility rules.
- Catalogue quirks (EATX requiring Full Tower, Mini DTX and HTPC returning UNKNOWN).
- Distinguishing 'valid' (no FAILs) from 'fully_verified' (all PASS).
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
)
from normalize import normalize_build

BASE_DIR = Path(__file__).resolve().parent.parent


# ─── 1. ALL CATEGORIES RULE ───────────────────────────────────────────────────
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


# ─── 4. PSU HEADROOM RULE ─────────────────────────────────────────────────────
def test_psu_headroom_pass_fail_unknown():
    # PASS: CPU 65W, GPU 115W, Overhead 80W -> (65+115+80)*1.4 = 364W <= 550W PSU
    parts_pass = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "chipset": "GeForce RTX 4060", "tdp": 115},
        {"category": "psu", "wattage": 550},
    ]
    v, _ = check_psu_headroom(parts_pass)
    assert v == "PASS"

    # Curated table resolution: GPU without tdp resolves via chipset "GeForce RTX 4060" -> 115W
    parts_curated = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "chipset": "GeForce RTX 4060", "tdp": None},
        {"category": "psu", "wattage": 550},
    ]
    v, _ = check_psu_headroom(parts_curated)
    assert v == "PASS"

    # FAIL: CPU 170W, GPU 450W (RTX 4090), Overhead 80W -> (170+450+80)*1.4 = 980W > 650W PSU
    parts_fail = [
        {"category": "processor", "tdp": 170},
        {"category": "gpu", "chipset": "GeForce RTX 4090", "tdp": 450},
        {"category": "psu", "wattage": 650},
    ]
    v, _ = check_psu_headroom(parts_fail)
    assert v == "FAIL"

    # UNKNOWN: Uncurated GPU chipset
    parts_unk = [
        {"category": "processor", "tdp": 65},
        {"category": "gpu", "chipset": "Obscure Unknown GPU 9999", "tdp": None},
        {"category": "psu", "wattage": 650},
    ]
    v, _ = check_psu_headroom(parts_unk)
    assert v == "UNKNOWN"


# ─── 5. FORM FACTOR FIT RULE (INCLUDING QUIRKS) ──────────────────────────────
def test_formfactor_fit_pass_fail_unknown():
    # PASS: Micro ATX board in MicroATX Mini Tower
    parts_pass1 = [
        {"category": "motherboard", "form_factor": "Micro ATX"},
        {"category": "cabinet", "case_type": "MicroATX Mini Tower"},
    ]
    v, _ = check_formfactor_fit(parts_pass1)
    assert v == "PASS"

    # PASS: ATX board in ATX Mid Tower
    parts_pass2 = [
        {"category": "motherboard", "form_factor": "ATX"},
        {"category": "cabinet", "case_type": "ATX Mid Tower"},
    ]
    v, _ = check_formfactor_fit(parts_pass2)
    assert v == "PASS"

    # FAIL: ATX board does NOT fit in MicroATX Mini Tower
    parts_fail = [
        {"category": "motherboard", "form_factor": "ATX"},
        {"category": "cabinet", "case_type": "MicroATX Mini Tower"},
    ]
    v, _ = check_formfactor_fit(parts_fail)
    assert v == "FAIL"

    # Catalogue Quirk 1: EATX board requires Full Tower (FAIL in Mid Tower, PASS in Full Tower)
    parts_eatx_mid = [
        {"category": "motherboard", "form_factor": "EATX"},
        {"category": "cabinet", "case_type": "ATX Mid Tower"},
    ]
    v_mid, _ = check_formfactor_fit(parts_eatx_mid)
    assert v_mid == "FAIL"

    parts_eatx_full = [
        {"category": "motherboard", "form_factor": "EATX"},
        {"category": "cabinet", "case_type": "ATX Full Tower"},
    ]
    v_full, _ = check_formfactor_fit(parts_eatx_full)
    assert v_full == "PASS"

    # Catalogue Quirk 2: Mini DTX returns UNKNOWN
    parts_dtx = [
        {"category": "motherboard", "form_factor": "Mini DTX"},
        {"category": "cabinet", "case_type": "ATX Mid Tower"},
    ]
    v_dtx, _ = check_formfactor_fit(parts_dtx)
    assert v_dtx == "UNKNOWN"

    # Catalogue Quirk 3: HTPC case returns UNKNOWN
    parts_htpc = [
        {"category": "motherboard", "form_factor": "Micro ATX"},
        {"category": "cabinet", "case_type": "HTPC"},
    ]
    v_htpc, _ = check_formfactor_fit(parts_htpc)
    assert v_htpc == "UNKNOWN"


# ─── 6. GPU LENGTH RULE ───────────────────────────────────────────────────────
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

    # UNKNOWN: GPU missing length
    parts_unk1 = [
        {"category": "gpu", "length": None, "name": "Custom GPU"},
        {"category": "cabinet", "id": "cab1", "name": "Deepcool Macube 110"},
    ]
    v, _ = check_gpu_length(parts_unk1)
    assert v == "UNKNOWN"

    # UNKNOWN: Case missing curated limit
    parts_unk2 = [
        {"category": "gpu", "length": 250, "name": "RTX 4060"},
        {"category": "cabinet", "id": "cab_uncurated_xyz", "name": "Unknown Generic Case"},
    ]
    v, _ = check_gpu_length(parts_unk2)
    assert v == "UNKNOWN"


# ─── 7. COOLER HEIGHT RULE ────────────────────────────────────────────────────
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

    # UNKNOWN: Liquid (AIO) coolers return UNKNOWN (radiator mounting clearance requires radiator check)
    parts_liquid = [
        {"category": "cooling", "cooler_kind": "liquid", "name": "Cooler Master Liquid 240L"},
        {"category": "cabinet", "id": "cab1", "name": "Deepcool Macube 110"},
    ]
    v_liq, _ = check_cooler_height(parts_liquid)
    assert v_liq == "UNKNOWN"

    # UNKNOWN: Uncurated air cooler height
    parts_unk = [
        {"category": "cooling", "cooler_kind": "air", "height": None, "id": "cool_uncurated", "name": "Generic Cooler"},
        {"category": "cabinet", "id": "cab1", "name": "Deepcool Macube 110"},
    ]
    v, _ = check_cooler_height(parts_unk)
    assert v == "UNKNOWN"


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

    # UNKNOWN: Part missing price
    parts_missing_price = [
        {"category": "processor", "name": "CPU", "price": 15000},
        {"category": "gpu", "name": "GPU", "price": None},
    ]
    v_unk_price, _ = check_within_budget(parts_missing_price, budget=50000)
    assert v_unk_price == "UNKNOWN"


# ─── 9. CHECK_BUILD ORCHESTRATOR (VALID VS FULLY VERIFIED) ────────────────────
def test_check_build_valid_and_fully_verified():
    # Build with all data present satisfying every rule
    fully_valid_build = [
        {"category": "processor", "name": "AMD Ryzen 5 7600", "socket": "AM5", "ram_type": "DDR5", "tdp": 65, "price": 18000},
        {"category": "motherboard", "name": "MSI B650M Gaming", "socket": "AM5", "ram_type": "DDR5", "form_factor": "Micro ATX", "price": 12000},
        {"category": "gpu", "name": "Gigabyte RTX 4060", "chipset": "GeForce RTX 4060", "tdp": 115, "length": 192, "price": 25000},
        {"category": "ram", "name": "Corsair DDR5 32GB", "ram_type": "DDR5", "price": 8000},
        {"category": "ps", "name": "Crucial 1TB SSD", "price": 5000},
        {"category": "ss", "name": "WD 1TB HDD", "price": 3000},
        {"category": "psu", "name": "Corsair 650W", "wattage": 650, "price": 6000},
        {"category": "cabinet", "id": "cab1", "name": "Deepcool Macube 110", "case_type": "MicroATX Mini Tower", "price": 4000},
        {"category": "cooling", "id": "cool_70af1a5d8ce2", "name": "Thermalright Phantom Spirit 120 SE", "cooler_kind": "air", "height": 154, "price": 3500},
    ]

    res = check_build(fully_valid_build, budget=90000)
    assert res["valid"] is True
    assert res["fully_verified"] is True
    assert len(res["fails"]) == 0
    assert len(res["unknowns"]) == 0

    # Build with uncurated case clearance -> valid=True (no FAILs), but fully_verified=False (has UNKNOWN)
    build_with_unknown = list(fully_valid_build)
    build_with_unknown[7] = {
        "category": "cabinet",
        "id": "cab_uncurated_test",
        "name": "Generic Case Uncurated",
        "case_type": "MicroATX Mini Tower",
        "price": 4000,
    }

    res_unk = check_build(build_with_unknown, budget=90000)
    assert res_unk["valid"] is True
    assert res_unk["fully_verified"] is False
    assert "gpu_length" in res_unk["unknowns"]
    assert len(res_unk["fails"]) == 0


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

        # 2. Day 7 checker.py verdict on shared rules
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
