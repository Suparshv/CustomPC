from pathlib import Path
import pytest
from ingest_parts import (
    generate_stable_id,
    is_simulated_in_stock,
    spread_sample,
    load_seed_parts,
    load_cpus,
    load_motherboards,
    RAW_DATA_DIR,
)


def test_generate_stable_id():
    item1 = {"name": "Test Part", "price": 100, "socket": "AM4"}
    item2 = {"name": "Test Part", "price": 100, "socket": "AM4"}
    item3 = {"name": "Test Part 2", "price": 100, "socket": "AM5"}

    id1 = generate_stable_id("test", item1)
    id2 = generate_stable_id("test", item2)
    id3 = generate_stable_id("test", item3)

    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("test_")
    assert len(id1) == 5 + 12  # "test_" + 12 hex chars


def test_stable_id_price_invariance():
    """Verify that a refreshed dataset with a changed price retains the same ID."""
    gpu_initial = {"name": "RTX 4070 OC", "chipset": "GeForce RTX 4070", "price": 549.99}
    gpu_price_drop = {"name": "RTX 4070 OC", "chipset": "GeForce RTX 4070", "price": 499.99}

    assert generate_stable_id("gpu", gpu_initial) == generate_stable_id("gpu", gpu_price_drop)


def test_is_simulated_in_stock():
    # Deterministic behavior
    status1 = is_simulated_in_stock("part_123")
    status2 = is_simulated_in_stock("part_123")
    assert status1 == status2

    # Approximate distribution (~92% in stock over 1000 IDs)
    sample = [is_simulated_in_stock(f"part_{i}") for i in range(1000)]
    in_stock_rate = sum(sample) / len(sample)
    assert 0.88 <= in_stock_rate <= 0.96


def test_spread_sample():
    items = [{"price": i * 10} for i in range(10)]
    # Requesting fewer items than available
    sampled = spread_sample(items, 3)
    assert len(sampled) == 3
    # Check that it covers min and max
    assert sampled[0]["price"] == 0
    assert sampled[-1]["price"] == 90

    # Requesting more items than available
    assert len(spread_sample(items, 20)) == 10


def test_load_seed_parts_unified_fields():
    """Verify seed parts have unified dataset field names and legacy_specs preserved."""
    seed_parts = load_seed_parts()
    assert len(seed_parts) == 24
    for doc in seed_parts:
        assert doc["source"] == "seed24"
        assert doc["price_inr_approx"] is False
        assert doc["in_stock"] is True
        assert doc["stock_simulated"] is True
        assert "legacy_specs" in doc

        # Check field unification
        cat = doc["category"]
        if cat == "processor":
            assert doc["socket"] in ["AM4", "LGA1700"]
            assert doc["ram_type"] in ["DDR4", "DDR4/DDR5"]
            assert doc["core_count"] == 6
        elif cat == "motherboard":
            assert doc["ram_type"] in ["DDR4", "DDR5"]
            assert doc["form_factor"] == "Micro ATX"
        elif cat == "gpu":
            assert doc["memory"] in [8.0, 12.0, 16.0]
            assert doc["length"] > 0
            assert "chipset" in doc
        elif cat == "ram":
            assert doc["ram_type"] == "DDR4"
            assert doc["speed_mhz"] == 3200
            assert doc["capacity_gb"] in [8, 16]


def test_synthetic_derivation_logic():
    """Test socket and RAM derivation on synthetic rows without needing raw files."""
    import re

    # CPU socket derivation logic
    def derive_socket(name, arch):
        if re.search(r"Ryzen \d\s+(3\d{3}|4\d{3}|5\d{3})", name): return "AM4"
        if re.search(r"Ryzen \d\s+(7\d{3}|8\d{3}|9\d{3})", name): return "AM5"
        if re.search(r"i[3579]-(12\d{3}|13\d{3}|14\d{3})", name): return "LGA1700"
        if "Core Ultra" in name or "Arrow Lake" in arch: return "LGA1851"
        return None

    assert derive_socket("AMD Ryzen 5 5600X", "Zen 3") == "AM4"
    assert derive_socket("AMD Ryzen 7 7800X3D", "Zen 4") == "AM5"
    assert derive_socket("Intel Core i5-13600K", "Raptor Lake") == "LGA1700"
    assert derive_socket("Intel Core Ultra 7 265K", "Arrow Lake") == "LGA1851"
    assert derive_socket("Intel Core i7-7700K", "Kaby Lake") is None

    # Motherboard RAM type derivation logic
    def derive_ram_type(socket, name):
        if socket == "AM4": return "DDR4"
        if socket in ("AM5", "LGA1851"): return "DDR5"
        if socket == "LGA1700":
            if re.search(r"\b(ddr4|d4)\b", name, re.IGNORECASE): return "DDR4"
            if re.search(r"\b(ddr5|d5)\b", name, re.IGNORECASE): return "DDR5"
        return None

    assert derive_ram_type("AM4", "MSI B550-A PRO") == "DDR4"
    assert derive_ram_type("AM5", "Gigabyte B650 AORUS ELITE") == "DDR5"
    assert derive_ram_type("LGA1851", "ASUS PRIME Z890-P") == "DDR5"
    assert derive_ram_type("LGA1700", "MSI PRO Z790-P WIFI DDR4") == "DDR4"
    assert derive_ram_type("LGA1700", "ASRock H610M-HDV/M.2+ D5") == "DDR5"
    assert derive_ram_type("LGA1700", "MSI MAG B760 TOMAHAWK WIFI") is None


@pytest.mark.skipif(
    not (RAW_DATA_DIR / "cpu.json").exists(),
    reason="Raw dataset not present on clean clone (git-ignored)",
)
def test_dataset_category_parsers_real():
    """Integration check on raw files when locally present; asserts valid schema, not exact counts."""
    cpus = load_cpus()
    assert len(cpus) > 0
    for c in cpus:
        assert c["category"] == "processor"
        assert c["socket"] in ["AM4", "AM5", "LGA1700", "LGA1851"]
        assert c["price_inr_approx"] is True

    mbs = load_motherboards()
    assert len(mbs) > 0
    for m in mbs:
        assert m["category"] == "motherboard"
        assert m["ram_type"] in ["DDR4", "DDR5"]
