"""
test_tools.py - Comprehensive Unit Tests for Day 8 Deterministic Tools

Tests:
1. build_chroma_where: Single filter gives single dict; multiple filters give $and.
2. Case translation: Motherboard form factor translates into allowed case_type values.
3. Spelling variants: LGA 1700, AM 5, DDR 5, DDR-5, 5, m-ATX normalized properly.
4. Validation: Bad categories (including 'os') and over-limit limits return clean errors.
5. Reporting: Unknown IDs are reported in price_total and check_compatibility.
6. Arithmetic: price_total sums correctly and accurately handles repeated IDs (e.g. 2x RAM).
7. Verification: check_compatibility returns valid=True on a matching build and valid=False on mismatch.
8. Soft Boost: Exact semantic matches win over poor matches; checkable tie-breaks close matches.
9. Rich Cards: Cards include case_type, radiator_size, gpu_memory, speed_mhz, capacity_gb.
10. Safety: Tools operate in strict read-only mode and sanitize execution errors.
"""

from typing import Any, Dict
from unittest.mock import MagicMock
import pytest

from repo import InMemoryPartRepo
from tool_models import CheckCompatibilityInput, PriceTotalInput, SearchPartsInput
from tools import (
    TOOLS,
    build_chroma_where,
    check_compatibility,
    get_tool_definitions,
    price_total,
    run_tool,
    search_parts,
)


@pytest.fixture
def mock_parts_repo() -> InMemoryPartRepo:
    """Fixture providing in-memory catalog parts for offline test verification."""
    data = [
        # CPU: AM5, 65W TDP
        {
            "_id": "cpu_am5_1",
            "name": "AMD Ryzen 5 7600",
            "category": "processor",
            "price": 18500.0,
            "socket": "AM5",
            "tdp": 65.0,
            "ram_type": "DDR5",
            "in_stock": True,
        },
        # CPU: LGA1700, 125W TDP
        {
            "_id": "cpu_intel_1",
            "name": "Intel Core i5-13600K",
            "category": "processor",
            "price": 27000.0,
            "socket": "LGA1700",
            "tdp": 125.0,
            "ram_type": "DDR5",
            "in_stock": True,
        },
        # Motherboard: AM5, DDR5, ATX
        {
            "_id": "mb_am5_1",
            "name": "MSI B650 Gaming Plus WiFi",
            "category": "motherboard",
            "price": 16000.0,
            "socket": "AM5",
            "ram_type": "DDR5",
            "form_factor": "ATX",
            "in_stock": True,
        },
        # Motherboard: LGA1700, DDR4, ATX
        {
            "_id": "mb_intel_1",
            "name": "MSI PRO Z790-P",
            "category": "motherboard",
            "price": 19000.0,
            "socket": "LGA1700",
            "ram_type": "DDR4",
            "form_factor": "ATX",
            "in_stock": True,
        },
        # RAM: DDR5 16GB
        {
            "_id": "ram_ddr5_1",
            "name": "Corsair Vengeance 16GB DDR5-5600",
            "category": "ram",
            "price": 4500.0,
            "ram_type": "DDR5",
            "speed_mhz": 5600,
            "capacity_gb": 16,
            "in_stock": True,
        },
        # GPU: RTX 4070 (200W, 242mm)
        {
            "_id": "gpu_4070_1",
            "name": "Gigabyte GeForce RTX 4070 Windforce",
            "category": "gpu",
            "price": 54000.0,
            "chipset": "GeForce RTX 4070",
            "tdp": 200.0,
            "length": 242.0,
            "gpu_memory": 12,
            "in_stock": True,
        },
        # PSU: 750W Gold
        {
            "_id": "psu_750_1",
            "name": "Corsair RM750e 750W Gold",
            "category": "psu",
            "price": 8500.0,
            "wattage": 750.0,
            "in_stock": True,
        },
        # PSU: 450W Bronze (too small for heavy GPU)
        {
            "_id": "psu_450_1",
            "name": "EVGA 450 BR 450W",
            "category": "psu",
            "price": 3200.0,
            "wattage": 450.0,
            "in_stock": True,
        },
        # Case: Corsair 4000D Airflow (fits ATX, 360mm GPU, 170mm cooler)
        {
            "_id": "case_4000d",
            "name": "Corsair 4000D Airflow",
            "category": "cabinet",
            "price": 7500.0,
            "form_factor": "ATX",
            "case_type": "ATX Mid Tower",
            "max_gpu_length": 360.0,
            "max_cooler_height": 170.0,
            "in_stock": True,
        },
        # Cooler: Peerless Assassin 120 (157mm height)
        {
            "_id": "cooler_pa120",
            "name": "Thermalright Peerless Assassin 120 SE",
            "category": "cooling",
            "price": 3800.0,
            "cooler_kind": "air",
            "height": 157.0,
            "in_stock": True,
        },
        # Primary Storage (SSD): 1TB NVMe SSD
        {
            "_id": "ssd_1tb_1",
            "name": "Samsung 980 Pro 1TB NVMe SSD",
            "category": "ps",
            "price": 8200.0,
            "capacity": 1000,
            "in_stock": True,
        },
        # Secondary Storage (HDD): 2TB HDD
        {
            "_id": "hdd_2tb_1",
            "name": "Seagate Barracuda 2TB HDD",
            "category": "ss",
            "price": 4500.0,
            "capacity": 2000,
            "in_stock": True,
        },
        # Part with missing price
        {
            "_id": "part_noprice",
            "name": "Experimental Prototype Board",
            "category": "motherboard",
            "price": None,
            "price_inr": None,
            "in_stock": True,
        },
    ]
    return InMemoryPartRepo(parts=data)


# ─── 1. Single vs $and Where Clause Tests ─────────────────────────────────────
def test_build_chroma_where_single_condition():
    """Verify that a single filter produces a single condition dict without $and."""
    params = SearchPartsInput(category="processor", in_stock_only=False)
    where, filters = build_chroma_where(params)
    assert where == {"category": "processor"}
    assert filters == {"category": "processor"}


def test_build_chroma_where_multiple_conditions_uses_and():
    """Verify that multiple filters produce a valid $and condition list."""
    params = SearchPartsInput(
        category="processor",
        in_stock_only=True,
        socket="AM5",
        max_price=25000.0,
    )
    where, filters = build_chroma_where(params)
    assert "$and" in where
    assert isinstance(where["$and"], list)
    assert len(where["$and"]) == 4

    # Check each constituent condition
    assert {"category": "processor"} in where["$and"]
    assert {"in_stock": True} in where["$and"]
    assert {"socket": "AM5"} in where["$and"]
    assert {"price": {"$lte": 25000.0}} in where["$and"]


# ─── 2. Case Form Factor Translation (Issue 3) ────────────────────────────────
def test_case_form_factor_translates_to_case_type():
    """Verify that allowed_form_factors for cabinet translates into case_type with $in."""
    params = SearchPartsInput(category="cabinet", allowed_form_factors=["ATX"], in_stock_only=False)
    where, filters = build_chroma_where(params)
    assert "$and" in where
    conditions = where["$and"]

    # Must contain case_type filter with $in for ATX compatible towers
    case_cond = next((c for c in conditions if "case_type" in c), None)
    assert case_cond is not None
    assert "$in" in case_cond["case_type"]
    assert "ATX Mid Tower" in case_cond["case_type"]["$in"]
    assert "ATX Full Tower" in case_cond["case_type"]["$in"]
    # MicroATX Mid Tower must NOT be allowed for full ATX!
    assert "MicroATX Mid Tower" not in case_cond["case_type"]["$in"]


# ─── 3. Spelling Variants Normalization (Issue 5) ─────────────────────────────
def test_spelling_variants_normalized():
    """Verify spelling variants like LGA 1700, AM 5, DDR 5, DDR-5, 5, m-ATX are normalized."""
    p1 = SearchPartsInput(category="processor", socket="LGA 1700", ram_type="DDR 5")
    assert p1.socket == "LGA1700"
    assert p1.ram_type == "DDR5"

    p2 = SearchPartsInput(category="motherboard", socket="AM 5", ram_type="DDR-5", allowed_form_factors=["m-ATX"])
    assert p2.socket == "AM5"
    assert p2.ram_type == "DDR5"
    assert p2.allowed_form_factors == ["Micro ATX"]

    p3 = SearchPartsInput(category="ram", ram_type="5")
    assert p3.ram_type == "DDR5"

    p4 = SearchPartsInput(category="ram", ram_type="4")
    assert p4.ram_type == "DDR4"


# ─── 4. Validation & Error Handling Tests (Issue 5 & 8) ───────────────────────
def test_bad_category_returns_error():
    """Verify that invalid category returns clean error message without crashing."""
    res = run_tool("search_parts", {"category": "flying_carpet"})
    assert "error" in res
    assert "Invalid arguments" in res["error"]


def test_os_category_rejected():
    """Verify that 'os' category is rejected because OS is not in the hardware catalogue."""
    res = run_tool("search_parts", {"category": "os"})
    assert "error" in res
    assert "Invalid arguments" in res["error"]


def test_over_limit_limit_returns_error():
    """Verify that limit > 10 returns clean validation error."""
    res = run_tool("search_parts", {"category": "processor", "limit": 15})
    assert "error" in res
    assert "limit" in res["error"]

    res_neg = run_tool("search_parts", {"category": "processor", "limit": 0})
    assert "error" in res_neg
    assert "limit" in res_neg["error"]


def test_negative_max_price_returns_error():
    """Verify that negative price budget returns clean error."""
    res = run_tool("search_parts", {"category": "gpu", "max_price": -500})
    assert "error" in res
    assert "max_price must be positive" in res["error"]


def test_nonexistent_tool_returns_error():
    """Verify that unknown tool name returns error with available tools list."""
    res = run_tool("unknown_magic_tool", {})
    assert "error" in res
    assert "not found" in res["error"]


def test_tool_execution_error_sanitization():
    """Verify execution errors do not leak internal exception details or hostnames (Issue 8)."""
    # Force an execution failure
    def failing_fn(*args, **kwargs):
        raise ConnectionError("mongodb://admin:secret_pass@db.internal.corp:27017 connection refused")

    original_fn = TOOLS["price_total"]["function"]
    TOOLS["price_total"]["function"] = failing_fn
    try:
        res = run_tool("price_total", {"part_ids": ["p1"]})
        assert "error" in res
        # Must NOT leak internal database URL or hostname
        assert "mongodb://" not in res["error"]
        assert "secret_pass" not in res["error"]
        assert "execution failed" in res["error"]
    finally:
        TOOLS["price_total"]["function"] = original_fn


# ─── 5. Unknown IDs Reporting ──────────────────────────────────────────────────
def test_price_total_reports_unresolved_ids(mock_parts_repo):
    """Verify that unknown IDs are reported in unresolved list in price_total."""
    params = PriceTotalInput(part_ids=["cpu_am5_1", "ghost_gpu_999"])
    res = price_total(params, repo=mock_parts_repo)
    assert "unresolved" in res
    assert "ghost_gpu_999" in res["unresolved"]
    assert res["total"] == 18500.0
    assert len(res["items"]) == 2


def test_check_compatibility_reports_unresolved_ids(mock_parts_repo):
    """Verify that unknown IDs are marked unresolved in check_compatibility."""
    params = CheckCompatibilityInput(part_ids=["cpu_am5_1", "ghost_board_xyz"])
    res = check_compatibility(params, repo=mock_parts_repo)
    assert res["valid"] is False
    assert "ghost_board_xyz" in res["unresolved"]


# ─── 6. Price Total Sum & Repetition Tests ──────────────────────────────────────
def test_price_total_sums_correctly_with_repetitions(mock_parts_repo):
    """Verify that price_total sums exact prices and counts repeated IDs (e.g. 2x RAM sticks)."""
    # 2x RAM (4,500 each) + 1x CPU (18,500) = 27,500
    params = PriceTotalInput(part_ids=["cpu_am5_1", "ram_ddr5_1", "ram_ddr5_1"])
    res = price_total(params, repo=mock_parts_repo)

    assert res["total"] == 27500.0
    assert res["item_count"] == 3
    assert len(res["items"]) == 3
    assert res["missing_price"] == []
    assert res["unresolved"] == []


def test_price_total_reports_missing_price(mock_parts_repo):
    """Verify that parts lacking price are recorded in missing_price list."""
    params = PriceTotalInput(part_ids=["cpu_am5_1", "part_noprice"])
    res = price_total(params, repo=mock_parts_repo)

    assert "part_noprice" in res["missing_price"]
    assert res["total"] == 18500.0


# ─── 7. Compatibility Verification (PASS & FAIL Examples) ─────────────────────
def test_check_compatibility_pass_example(mock_parts_repo):
    """
    PASS Example: Complete 9-part AM5 + DDR5 build with sufficient 750W PSU,
    ample GPU clearance, and within ₹150,000 budget.
    """
    valid_build_ids = [
        "cpu_am5_1",     # AMD Ryzen 5 7600 (AM5, 65W TDP)
        "mb_am5_1",      # MSI B650 (AM5, DDR5, ATX)
        "ram_ddr5_1",    # Corsair DDR5 16GB
        "gpu_4070_1",    # RTX 4070 (200W, 242mm)
        "psu_750_1",     # Corsair 750W
        "case_4000d",    # Corsair 4000D Airflow (360mm GPU clearance)
        "cooler_pa120",  # Thermalright Peerless Assassin 120 (157mm)
        "ssd_1tb_1",     # Samsung 980 Pro (Primary Storage)
        "hdd_2tb_1",     # Seagate Barracuda 2TB (Secondary Storage)
    ]
    params = CheckCompatibilityInput(part_ids=valid_build_ids, budget=150000.0)
    res = check_compatibility(params, repo=mock_parts_repo)

    assert res["valid"] is True
    assert len(res["fails"]) == 0
    assert res["rules"]["all_categories"]["verdict"] == "PASS"
    assert res["rules"]["socket_match"]["verdict"] == "PASS"
    assert res["rules"]["ram_type_match"]["verdict"] == "PASS"
    assert res["rules"]["psu_headroom"]["verdict"] == "PASS"
    assert res["rules"]["gpu_length"]["verdict"] == "PASS"
    assert res["rules"]["formfactor_fit"]["verdict"] == "PASS"
    assert res["rules"]["within_budget"]["verdict"] == "PASS"


def test_check_compatibility_fail_example(mock_parts_repo):
    """
    FAIL Example: Intel Core i5-13600K (LGA1700) on an AMD B650 Motherboard (AM5),
    plus an undersized 450W power supply for a 200W GPU + 125W CPU.
    """
    invalid_build_ids = [
        "cpu_intel_1",   # Intel LGA1700 (125W TDP)
        "mb_am5_1",      # AMD AM5 motherboard (Socket mismatch!)
        "ram_ddr5_1",
        "gpu_4070_1",    # RTX 4070 (200W)
        "psu_450_1",     # 450W PSU: (125 + 200 + 80) * 1.4 = 567W needed -> FAIL!
        "case_4000d",
        "cooler_pa120",
        "ssd_1tb_1",
        "hdd_2tb_1",
    ]
    params = CheckCompatibilityInput(part_ids=invalid_build_ids, budget=150000.0)
    res = check_compatibility(params, repo=mock_parts_repo)

    assert res["valid"] is False
    assert "socket_match" in res["fails"]
    assert "psu_headroom" in res["fails"]


# ─── 8. Search Ranking: Soft Boost, Not Absolute Override (Issue 1) ───────────
def test_search_parts_soft_boost_preserves_best_semantic_match(monkeypatch):
    """
    Verify that an exact semantic match (e.g. RX 7600 XT with low distance)
    is NOT overridden by a poorly matching checkable part (Issue 1).
    """
    monkeypatch.setattr("embeddings.embed_query", lambda q: [0.1] * 768)
    mock_collection = MagicMock()
    # Candidate 1: Exact match requested by user (distance 0.08), but uncheckable
    # Candidate 2: Poor semantic match (distance 0.40), but checkable
    mock_collection.get.return_value = {"ids": ["gpu_rx7600xt", "gpu_rtx3060"]}
    mock_collection.query.return_value = {
        "ids": [["gpu_rx7600xt", "gpu_rtx3060"]],
        "documents": [["Radeon RX 7600 XT graphics card.", "GeForce RTX 3060 graphics card."]],
        "metadatas": [[
            {"category": "gpu", "name": "Radeon RX 7600 XT", "price": 32000.0, "in_stock": True},
            {"category": "gpu", "name": "GeForce RTX 3060", "price": 28000.0, "chipset": "GeForce RTX 3060", "tdp": 170.0, "length": 242.0, "in_stock": True},
        ]],
        "distances": [[0.08, 0.40]],
    }

    params = SearchPartsInput(category="gpu", keywords="Radeon RX 7600 XT", in_stock_only=False, limit=5)
    res = search_parts(params, collection=mock_collection)

    assert res["count"] == 2
    # The exact semantic match must rank FIRST even though it is uncheckable
    assert res["cards"][0]["id"] == "gpu_rx7600xt"
    assert res["cards"][0]["checkable"] is False
    assert res["cards"][1]["id"] == "gpu_rtx3060"
    assert res["cards"][1]["checkable"] is True


def test_search_parts_checkable_tie_break(monkeypatch):
    """Verify that when semantic relevance is nearly identical, checkable parts win as tie-break."""
    monkeypatch.setattr("embeddings.embed_query", lambda q: [0.1] * 768)
    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": ["gpu_a", "gpu_b"]}
    mock_collection.query.return_value = {
        "ids": [["gpu_a", "gpu_b"]],
        "documents": [["GeForce RTX 4060 graphics card A.", "GeForce RTX 4060 graphics card B."]],
        "metadatas": [[
            {"category": "gpu", "name": "RTX 4060 Uncurated", "price": 29000.0, "in_stock": True},
            {"category": "gpu", "name": "RTX 4060 Curated", "price": 29000.0, "chipset": "GeForce RTX 4060", "tdp": 115.0, "length": 200.0, "in_stock": True},
        ]],
        "distances": [[0.22, 0.24]],  # Very close distances
    }

    params = SearchPartsInput(category="gpu", keywords="RTX 4060", in_stock_only=False, limit=5)
    res = search_parts(params, collection=mock_collection)

    # gpu_b gets 0.05 checkable boost (0.24 - 0.05 = 0.19) and ranks FIRST
    assert res["cards"][0]["id"] == "gpu_b"
    assert res["cards"][0]["checkable"] is True


# ─── 9. Rich Card Fields (Issue 4) ────────────────────────────────────────────
def test_search_parts_returns_rich_card_fields():
    """Verify cards include case_type, radiator_size, gpu_memory, speed_mhz, capacity_gb."""
    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["ram_test_1"],
        "documents": ["Corsair 32GB DDR5-5600 desktop memory."],
        "metadatas": [{
            "category": "ram",
            "name": "Corsair Vengeance",
            "price": 8500.0,
            "ram_type": "DDR5",
            "speed_mhz": 5600,
            "capacity_gb": 32,
            "in_stock": True,
        }],
    }

    params = SearchPartsInput(category="ram", in_stock_only=False, limit=5)
    res = search_parts(params, collection=mock_collection)

    card = res["cards"][0]
    assert card["speed_mhz"] == 5600
    assert card["capacity_gb"] == 32
    assert "case_type" in card
    assert "radiator_size" in card
    assert "gpu_memory" in card


# ─── 10. Read-Only Safety Test: Tools Never Write to Database ──────────────────
def test_tools_never_write_to_database(mock_parts_repo):
    """Verify that calling tools never mutates the underlying repository state."""
    initial_parts = mock_parts_repo.get_all()
    initial_count = len(initial_parts)
    initial_snapshot = [dict(p) for p in initial_parts]

    # Run price_total
    price_total(PriceTotalInput(part_ids=["cpu_am5_1", "ram_ddr5_1"]), repo=mock_parts_repo)

    # Run check_compatibility
    check_compatibility(CheckCompatibilityInput(part_ids=["cpu_am5_1", "mb_am5_1"]), repo=mock_parts_repo)

    # Verify repository was not mutated
    after_parts = mock_parts_repo.get_all()
    assert len(after_parts) == initial_count
    assert after_parts == initial_snapshot


# ─── 11. Tool Definitions Export ──────────────────────────────────────────────
def test_get_tool_definitions_has_valid_json_schemas():
    """Verify exported tool schemas match JSON schema specifications."""
    defs = get_tool_definitions()
    assert len(defs) == 3

    names = [d["name"] for d in defs]
    assert "search_parts" in names
    assert "price_total" in names
    assert "check_compatibility" in names

    for d in defs:
        assert "description" in d
        assert "parameters" in d
        params = d["parameters"]
        assert params.get("type") == "object"
        assert "properties" in params
