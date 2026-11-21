#!/usr/bin/env python3
"""
test_hybrid_search.py - Unit tests for the Hybrid Search and Reranker components.

Tests:
- Tokenizer preserving technical model codes, chipset names, and compound units.
- Reciprocal Rank Fusion (RRF) arithmetic and sorting properties.
- Metadata filtering parity for keyword search results.
- CategoryBM25Index indexing and retrieval.
- CrossEncoderReranker ordering and latency diagnostics.
- Retriever switch in SearchPartsInput and search_parts.
"""

from unittest.mock import MagicMock
import pytest

from keyword_search import (
    tokenize,
    CategoryBM25Index,
    KeywordSearchEngine,
)
from hybrid_search import (
    rrf_merge,
    CrossEncoderReranker,
)
from tool_models import SearchPartsInput
from tools import search_parts


# ─── 1. TOKENIZER TESTS ────────────────────────────────────────────────────────
def test_tokenize_preserves_product_codes():
    """Verify that hyphenated model numbers and alphanumeric codes remain whole."""
    text = "Intel Core i5-12400F desktop processor LGA1700"
    tokens = tokenize(text)
    assert "i5-12400f" in tokens
    assert "i5" in tokens
    assert "12400f" in tokens
    assert "lga1700" in tokens


def test_tokenize_preserves_chipset_and_models():
    """Verify chipset codes like b550m and rtx-4060 are preserved."""
    text = "MSI MAG B550M MORTAR WIFI and GeForce RTX-4060 Ti"
    tokens = tokenize(text)
    assert "b550m" in tokens
    assert "rtx-4060" in tokens
    assert "rtx" in tokens
    assert "4060" in tokens
    assert "ti" in tokens


def test_tokenize_expands_compound_units():
    """Verify compound units (e.g. 32gb, 750w, 120mm) emit both full and sub-tokens."""
    text = "Corsair 32GB DDR5 RAM, 750W Gold PSU, 120mm cooler"
    tokens = tokenize(text)
    assert "32gb" in tokens
    assert "32" in tokens
    assert "gb" in tokens
    assert "750w" in tokens
    assert "750" in tokens
    assert "w" in tokens
    assert "120mm" in tokens
    assert "120" in tokens
    assert "mm" in tokens


# ─── 2. RRF MERGE TESTS ────────────────────────────────────────────────────────
def test_rrf_merge_formula_and_scoring():
    """
    Verify pure RRF score calculation:
    score = sum(1 / (k + rank))
    With k=60:
    Rank 1 in both lists -> 1/61 + 1/61 = 2/61 ≈ 0.032787
    Rank 1 in vector only -> 1/61 ≈ 0.016393
    Rank 2 in both lists -> 1/62 + 1/62 = 2/62 ≈ 0.032258
    """
    vector_list = [
        {"id": "part_A", "document": "Part A doc", "metadata": {}, "score": 0.1},
        {"id": "part_B", "document": "Part B doc", "metadata": {}, "score": 0.2},
        {"id": "part_C", "document": "Part C doc", "metadata": {}, "score": 0.3},
    ]
    keyword_list = [
        {"id": "part_B", "document": "Part B doc", "metadata": {}, "score": 9.5},
        {"id": "part_A", "document": "Part A doc", "metadata": {}, "score": 8.0},
        {"id": "part_D", "document": "Part D doc", "metadata": {}, "score": 7.5},
    ]

    merged = rrf_merge(vector_list, keyword_list, k=60, limit=10)

    # Both part_A and part_B appear at rank 1 and 2:
    # part_A: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 ≈ 0.016393 + 0.016129 = 0.032522
    # part_B: 1/(60+2) + 1/(60+1) = 1/62 + 1/61 ≈ 0.032522
    expected_top_score = (1.0 / 61) + (1.0 / 62)
    assert pytest.approx(merged[0]["rrf_score"], rel=1e-4) == expected_top_score
    assert pytest.approx(merged[1]["rrf_score"], rel=1e-4) == expected_top_score

    # part_C: only in vector at rank 3 -> 1/(60+3) = 1/63 ≈ 0.015873
    # part_D: only in keyword at rank 3 -> 1/(60+3) = 1/63 ≈ 0.015873
    c_item = next(x for x in merged if x["id"] == "part_C")
    assert pytest.approx(c_item["rrf_score"], rel=1e-4) == (1.0 / 63)
    assert c_item["vector_rank"] == 3
    assert c_item["keyword_rank"] is None


def test_rrf_merge_respects_limit():
    """Verify limit parameter properly slices results."""
    vec = [{"id": f"v_{i}", "document": f"Doc {i}", "metadata": {}} for i in range(15)]
    kw = [{"id": f"k_{i}", "document": f"Doc {i}", "metadata": {}} for i in range(15)]
    merged = rrf_merge(vec, kw, k=60, limit=5)
    assert len(merged) == 5


# ─── 3. KEYWORD METADATA FILTER TESTS ─────────────────────────────────────────
# (matches_filters tests removed in the code review: BM25 no longer has its own
#  copy of the filters. Chroma's where clause is the only filter, tested in test_tools.py,
#  and BM25 is restricted to the IDs that pass it -- see the tests at the end of this file.)


# ─── 4. CATEGORY BM25 INDEX OFFLINE TESTS ─────────────────────────────────────
def test_category_bm25_search_offline():
    """Test BM25Okapi scoring on an isolated in-memory corpus."""
    items = [
        {"id": "p1", "document": "Intel Core i5-12400F 6-Core processor", "metadata": {"category": "processor", "price": 11000.0}},
        {"id": "p2", "document": "AMD Ryzen 5 7600 6-Core AM5 processor", "metadata": {"category": "processor", "price": 18000.0}},
        {"id": "p3", "document": "Intel Core i7-13700K 16-Core processor", "metadata": {"category": "processor", "price": 34000.0}},
    ]
    index = CategoryBM25Index("processor", items)
    results = index.search(query="i5-12400", limit=2)
    assert len(results) >= 1
    assert results[0]["id"] == "p1"

    # Restricted to an allow-list (the IDs that passed Chroma's filters, e.g. price <= 12000):
    results_budget = index.search(query="processor", allowed_ids={"p1"}, limit=3)
    assert len(results_budget) == 1
    assert results_budget[0]["id"] == "p1"


# ─── 5. RERANKER OFFLINE TESTS ────────────────────────────────────────────────
def test_cross_encoder_reranker_offline(monkeypatch):
    """Test reranking ordering with a mocked CrossEncoder."""
    reranker = CrossEncoderReranker()
    mock_model = MagicMock()
    # Return mock scores: second candidate gets higher score
    mock_model.predict.return_value = [1.2, 5.8, 3.1]
    monkeypatch.setattr(reranker, "_model", mock_model)

    candidates = [
        {"id": "c1", "document": "Passage 1"},
        {"id": "c2", "document": "Passage 2"},
        {"id": "c3", "document": "Passage 3"},
    ]
    reranked, elapsed_ms = reranker.rerank("test query", candidates, limit=2)
    assert len(reranked) == 2
    assert reranked[0]["id"] == "c2"
    assert reranked[0]["rerank_score"] == 5.8
    assert reranked[1]["id"] == "c3"
    assert reranked[1]["rerank_score"] == 3.1


# ─── 6. RETRIEVER SWITCH VALIDATION ──────────────────────────────────────────
def test_search_parts_input_retriever_validation():
    """Verify SearchPartsInput accepts all valid retriever options and rejects invalid ones."""
    p_vec = SearchPartsInput(category="processor", retriever="vector")
    assert p_vec.retriever == "vector"

    p_hyb = SearchPartsInput(category="processor", retriever="hybrid")
    assert p_hyb.retriever == "hybrid"

    p_rer = SearchPartsInput(category="processor", retriever="hybrid_rerank")
    assert p_rer.retriever == "hybrid_rerank"

    with pytest.raises(Exception):
        SearchPartsInput(category="processor", retriever="invalid_strategy")


# ─── One source of truth for filters, no stale BM25 index ───
# All three go end to end through search_parts with an
# in-memory Chroma collection and a fake embedder (no Ollama needed).
import chromadb
import keyword_search
import embeddings as embeddings_module


def _gpu_collection(name, docs):
    """docs: list of (id, document, metadata)."""
    coll = chromadb.EphemeralClient().get_or_create_collection(name)
    coll.add(
        ids=[d[0] for d in docs],
        documents=[d[1] for d in docs],
        metadatas=[d[2] for d in docs],
        embeddings=[[1.0, float(i)] for i in range(len(docs))],
    )
    return coll


@pytest.fixture
def fresh_hybrid(monkeypatch):
    monkeypatch.setattr(keyword_search, "_KEYWORD_ENGINE", None, raising=False)
    monkeypatch.setattr(keyword_search, "_KEYWORD_ENGINE_KEY", None, raising=False)
    monkeypatch.setattr(embeddings_module, "embed_query", lambda q, **kw: [1.0, 0.0])


def test_hybrid_never_returns_parts_the_chroma_filter_excluded(fresh_hybrid):
    """
    Old bug: BM25 had its own filter copy (matches_filters) that let a GPU with NO
    length through max_gpu_length, while Chroma's $lte excluded it. RRF then merged it in.
    """
    coll = _gpu_collection("review_hybrid_filter", [
        ("g_short", "RTX 4060 compact 200 mm", {"category": "gpu", "price": 1.0, "in_stock": True, "length": 200.0}),
        ("g_nolen", "RTX 4060 compact compact compact", {"category": "gpu", "price": 1.0, "in_stock": True}),
    ])
    res = search_parts(
        SearchPartsInput(category="gpu", keywords="RTX 4060 compact", max_gpu_length=250, retriever="hybrid"),
        collection=coll,
    )
    ids = [c["id"] for c in res["cards"]]
    assert "g_nolen" not in ids
    assert ids == ["g_short"]


def test_hybrid_keyword_engine_follows_the_collection_it_is_given(fresh_hybrid):
    """Old bug: the BM25 engine was built once from the FIRST collection and reused forever."""
    coll_a = _gpu_collection("review_hybrid_a", [
        ("a_only", "Radeon RX 7600", {"category": "gpu", "price": 1.0, "in_stock": True}),
    ])
    coll_b = _gpu_collection("review_hybrid_b", [
        ("b_only", "Radeon RX 7600", {"category": "gpu", "price": 1.0, "in_stock": True}),
    ])
    p = SearchPartsInput(category="gpu", keywords="RX 7600", retriever="hybrid")
    assert [c["id"] for c in search_parts(p, collection=coll_a)["cards"]] == ["a_only"]
    assert [c["id"] for c in search_parts(p, collection=coll_b)["cards"]] == ["b_only"]


def test_hybrid_cards_show_current_price_after_reindex(fresh_hybrid, monkeypatch):
    """
    Old bug: a part found ONLY by BM25 got its card from metadata cached inside the
    BM25 engine at first use, so a price change in Chroma never showed up.
    (The vector leg is switched off so the hit is keyword-only.)
    """
    import hybrid_search
    monkeypatch.setattr(hybrid_search, "run_vector_search", lambda *a, **kw: [])
    coll = _gpu_collection("review_hybrid_price", [
        ("g1", "GeForce RTX 4070", {"category": "gpu", "price": 50000.0, "in_stock": True}),
    ])
    p = SearchPartsInput(category="gpu", keywords="RTX 4070", retriever="hybrid")
    assert search_parts(p, collection=coll)["cards"][0]["price"] == 50000.0

    coll.update(ids=["g1"], metadatas=[{"category": "gpu", "price": 45000.0, "in_stock": True}])
    assert search_parts(p, collection=coll)["cards"][0]["price"] == 45000.0
