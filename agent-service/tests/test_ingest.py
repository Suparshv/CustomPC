import pytest
from ingest_parts import (
    generate_stable_id,
    is_simulated_in_stock,
    spread_sample,
    load_seed_parts,
    load_cpus,
    load_motherboards,
    load_gpus,
    load_ram,
    load_psus,
    load_cases,
    load_storage,
    load_coolers,
)


def test_generate_stable_id():
    item1 = {"name": "Test Part", "price": 100}
    item2 = {"name": "Test Part", "price": 100}
    item3 = {"name": "Test Part", "price": 200}

    id1 = generate_stable_id("test", item1)
    id2 = generate_stable_id("test", item2)
    id3 = generate_stable_id("test", item3)

    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("test_")
    assert len(id1) == 5 + 12  # "test_" + 12 hex chars


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


def test_load_seed_parts():
    seed_parts = load_seed_parts()
    assert len(seed_parts) == 24
    for doc in seed_parts:
        assert doc["source"] == "seed24"
        assert doc["price_inr_approx"] is False
        assert doc["in_stock"] is True
        assert doc["stock_simulated"] is True
        assert doc["category"] in [
            "processor", "motherboard", "gpu", "ram",
            "ps", "ss", "psu", "cabinet", "cooling"
        ]


def test_dataset_category_parsers():
    cpus = load_cpus()
    assert len(cpus) == 115
    for c in cpus:
        assert c["category"] == "processor"
        assert c["socket"] in ["AM4", "AM5", "LGA1700", "LGA1851"]
        assert c["price_inr_approx"] is True

    mbs = load_motherboards()
    assert len(mbs) == 574
    for m in mbs:
        assert m["category"] == "motherboard"
        assert m["ram_type"] in ["DDR4", "DDR5"]
