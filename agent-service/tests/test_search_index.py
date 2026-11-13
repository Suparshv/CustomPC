"""
test_search_index.py - Offline unit tests for Day 6 vector search & indexing

Tests:
- Prefix application (search_document: and search_query:) applied strictly once.
- Text builder (describe) generating sentences per category without embedding price.
- Metadata builder strictly omitting None/empty values and preserving simple types.
- Text hash sensitivity and determinism.
- Second run embedding 0 parts using a simulated embedder.
"""

import pytest
from embeddings import format_doc_text, format_query_text, DOC_PREFIX, QUERY_PREFIX
from build_index import describe, build_metadata, compute_doc_hash


# ─── 1. PREFIX TESTS ──────────────────────────────────────────────────────────
def test_prefix_applied_once():
    # Document prefix
    raw_doc = "Intel Core i5-12400 processor, 6 cores, LGA1700 socket."
    p1 = format_doc_text(raw_doc)
    assert p1.startswith(DOC_PREFIX)
    assert p1 == f"{DOC_PREFIX}{raw_doc}"

    # Applying again must not double prefix
    p2 = format_doc_text(p1)
    assert p2 == p1
    assert not p2.startswith(f"{DOC_PREFIX}{DOC_PREFIX}")

    # Query prefix
    raw_query = "RTX 4060 8GB"
    q1 = format_query_text(raw_query)
    assert q1.startswith(QUERY_PREFIX)
    assert q1 == f"{QUERY_PREFIX}{raw_query}"

    # Applying again must not double prefix
    q2 = format_query_text(q1)
    assert q2 == q1
    assert not q2.startswith(f"{QUERY_PREFIX}{QUERY_PREFIX}")


# ─── 2. TEXT BUILDER TESTS (WITHOUT PRICE) ───────────────────────────────────
def test_describe_all_categories_excludes_price():
    dummy_docs = [
        {
            "category": "processor",
            "name": "AMD Ryzen 5 5600X",
            "core_count": 6,
            "socket": "AM4",
            "tdp": 65,
            "price_inr": 11800,
            "price_usd": 126.88,
        },
        {
            "category": "motherboard",
            "name": "MSI PRO B660M-E DDR4",
            "socket": "LGA1700",
            "form_factor": "Micro ATX",
            "ram_type": "DDR4",
            "price_inr": 8500,
        },
        {
            "category": "gpu",
            "name": "Gigabyte RTX 4060 OC 8GB",
            "chipset": "GeForce RTX 4060",
            "memory": 8.0,
            "length": 192,
            "price_inr": 25000,
        },
        {
            "category": "ram",
            "name": "Corsair Vengeance 32GB",
            "capacity_gb": 32,
            "ram_type": "DDR5",
            "speed_mhz": 6000,
            "price_inr": 9500,
        },
        {
            "category": "ps",
            "name": "Samsung 990 Pro 1TB",
            "capacity": 1000,
            "form_factor": "M.2-2280",
            "interface": "PCIe 4.0 x4",
            "price_inr": 8200,
        },
        {
            "category": "ss",
            "name": "Seagate Barracuda 2TB",
            "capacity": 2000,
            "rpm": 7200,
            "price_inr": 4800,
        },
        {
            "category": "psu",
            "name": "Corsair RM750x",
            "wattage": 750,
            "efficiency": "80 Plus Gold",
            "price_inr": 9200,
        },
        {
            "category": "cabinet",
            "name": "NZXT H5 Flow",
            "type": "ATX Mid Tower",
            "color": "Black",
            "price_inr": 7400,
        },
        {
            "category": "cooling",
            "name": "Noctua NH-D15",
            "size": 140,
            "color": "Brown",
            "price_inr": 8900,
        },
    ]

    for doc in dummy_docs:
        desc = describe(doc)
        assert isinstance(desc, str)
        assert len(desc) > 10
        assert desc.endswith(".")

        # Verify price numbers and symbols never appear in description
        assert "11800" not in desc
        assert "8500" not in desc
        assert "25000" not in desc
        assert "₹" not in desc
        assert "$" not in desc
        assert "inr" not in desc.lower()


# ─── 3. METADATA BUILDER TESTS ───────────────────────────────────────────────
def test_build_metadata_omits_none_and_keeps_simple_types():
    doc_with_nones = {
        "_id": "test_1",
        "category": "gpu",
        "name": "Test GPU",
        "price_inr": 25000,
        "in_stock": True,
        "source": "seed24",
        "chipset": "RTX 4060",
        "socket": None,           # Missing for GPU
        "core_count": None,       # Missing for GPU
        "boost_clock": None,      # None value
        "empty_string": "",       # Empty string
        "nested_dict": {"a": 1},  # Must not leak invalid nested types
    }

    meta = build_metadata(doc_with_nones, doc_hash="hash_123")

    # Assert clean simple types
    for key, val in meta.items():
        assert val is not None, f"Key {key} has None value"
        assert type(val) in (str, int, float, bool), f"Key {key} has invalid type {type(val)}"

    # Assert expected inclusions
    assert meta["category"] == "gpu"
    assert meta["price"] == 25000.0
    assert meta["in_stock"] is True
    assert meta["source"] == "seed24"
    assert meta["chipset"] == "RTX 4060"
    assert meta["doc_hash"] == "hash_123"

    # Assert omitted None / empty keys
    assert "socket" not in meta
    assert "core_count" not in meta
    assert "boost_clock" not in meta
    assert "empty_string" not in meta
    assert "nested_dict" not in meta


# ─── 4. DOC HASH DETERMINISM AND SENSITIVITY ──────────────────────────────────
def test_compute_doc_hash():
    text1 = "Intel i5 12400, desktop processor, 6 cores, LGA1700 socket."
    text2 = "Intel i5 12400, desktop processor, 6 cores, LGA1700 socket."
    text3 = "AMD Ryzen 5 5600X, desktop processor, 6 cores, AM4 socket."

    h1 = compute_doc_hash(text1)
    h2 = compute_doc_hash(text2)
    h3 = compute_doc_hash(text3)

    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16


# ─── 5. FAKE EMBEDDER IDEMPOTENCY TEST (ZERO EMBEDDINGS ON RUN 2) ────────────
def test_fake_embedder_idempotency():
    """Simulate indexing loop with a fake embedder verifying second run embeds 0 parts."""
    fake_mongo = [
        {"_id": "p1", "category": "processor", "name": "Intel i5 12400", "core_count": 6, "socket": "LGA1700"},
        {"_id": "g1", "category": "gpu", "name": "RTX 4060", "chipset": "GeForce RTX 4060", "memory": 8.0},
    ]

    # In-memory Chroma simulator
    chroma_store = {}
    embed_call_count = 0

    def fake_embed(texts):
        nonlocal embed_call_count
        embed_call_count += len(texts)
        return [[0.1] * 768 for _ in texts]

    # RUN 1: Initial Indexing
    for doc in fake_mongo:
        text = describe(doc)
        thash = compute_doc_hash(text)
        meta = build_metadata(doc, doc_hash=thash)
        doc_id = doc["_id"]

        # If not present or hash changed, embed
        if doc_id not in chroma_store or chroma_store[doc_id]["hash"] != thash:
            emb = fake_embed([text])[0]
            chroma_store[doc_id] = {"doc": text, "hash": thash, "meta": meta, "emb": emb}

    assert embed_call_count == 2
    assert len(chroma_store) == 2

    # RUN 2: Re-run with unchanged data
    run2_embeds = 0
    for doc in fake_mongo:
        text = describe(doc)
        thash = compute_doc_hash(text)
        doc_id = doc["_id"]

        # Check existing hash
        if doc_id not in chroma_store or chroma_store[doc_id]["hash"] != thash:
            emb = fake_embed([text])[0]
            run2_embeds += 1

    assert run2_embeds == 0  # Zero parts re-embedded!
