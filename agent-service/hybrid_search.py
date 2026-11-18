#!/usr/bin/env python3
"""
hybrid_search.py - Hybrid search combining Chroma vector search, BM25 keyword search,
Reciprocal Rank Fusion (RRF), and Cross-Encoder reranking.

Components:
1. rrf_merge: Pure function merging two ranked lists using 1 / (k + rank).
2. CrossEncoderReranker: Lazy-loaded cross-encoder for second-stage candidate re-scoring.
3. hybrid_search: High-level search function supporting 'vector', 'hybrid', and 'hybrid_rerank'.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Set, Tuple, Literal

import embeddings
from keyword_search import get_keyword_engine

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def rrf_merge(
    vector_candidates: List[Dict[str, Any]],
    keyword_candidates: List[Dict[str, Any]],
    k: int = DEFAULT_RRF_K,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Merge vector search candidates and BM25 keyword search candidates using Reciprocal Rank Fusion (RRF).
    
    Formula:
        RRF_Score(item) = sum_{sources} ( 1.0 / (k + rank) )
    where rank is 1-indexed (1, 2, ..., N).
    
    Candidates that appear in both lists receive additive scores, boosting high-consensus items.
    """
    merged: Dict[str, Dict[str, Any]] = {}

    for rank, cand in enumerate(vector_candidates, start=1):
        cand_id = str(cand["id"])
        rrf_contrib = 1.0 / (k + rank)
        if cand_id not in merged:
            merged[cand_id] = {
                "id": cand_id,
                "document": cand.get("document", ""),
                "metadata": cand.get("metadata", {}),
                "rrf_score": rrf_contrib,
                "vector_rank": rank,
                "keyword_rank": None,
                "vector_score": cand.get("score"),
                "keyword_score": None,
            }
        else:
            merged[cand_id]["rrf_score"] += rrf_contrib
            merged[cand_id]["vector_rank"] = rank
            merged[cand_id]["vector_score"] = cand.get("score")

    for rank, cand in enumerate(keyword_candidates, start=1):
        cand_id = str(cand["id"])
        rrf_contrib = 1.0 / (k + rank)
        if cand_id not in merged:
            merged[cand_id] = {
                "id": cand_id,
                "document": cand.get("document", ""),
                "metadata": cand.get("metadata", {}),
                "rrf_score": rrf_contrib,
                "vector_rank": None,
                "keyword_rank": rank,
                "vector_score": None,
                "keyword_score": cand.get("score"),
            }
        else:
            merged[cand_id]["rrf_score"] += rrf_contrib
            merged[cand_id]["keyword_rank"] = rank
            merged[cand_id]["keyword_score"] = cand.get("score")

    # Sort descending by rrf_score
    merged_list = list(merged.values())
    merged_list.sort(key=lambda x: x["rrf_score"], reverse=True)
    return merged_list[:limit]


class CrossEncoderReranker:
    """Singleton-friendly wrapper around sentence-transformers CrossEncoder."""

    def __init__(self, model_name: str = RERANKER_MODEL):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info("Loading CrossEncoder model '%s'...", self.model_name)
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        limit: int = 10
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Score (query, document) pairs using the cross-encoder and re-sort descending.
        Returns (reranked_candidates, elapsed_time_ms).
        """
        if not candidates:
            return [], 0.0

        # Make a shallow copy of candidates so we don't mutate input unexpectedly
        cands = [dict(c) for c in candidates]
        pairs = [(query, c.get("document", "")) for c in cands]

        t0 = time.perf_counter()
        scores = self.model.predict(pairs)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        for idx, score in enumerate(scores):
            cands[idx]["rerank_score"] = float(score)

        cands.sort(key=lambda x: x["rerank_score"], reverse=True)
        return cands[:limit], elapsed_ms


_RERANKER_INSTANCE: Optional[CrossEncoderReranker] = None


def get_reranker() -> CrossEncoderReranker:
    """Return the global CrossEncoderReranker instance."""
    global _RERANKER_INSTANCE
    if _RERANKER_INSTANCE is None:
        _RERANKER_INSTANCE = CrossEncoderReranker()
    return _RERANKER_INSTANCE


def run_vector_search(
    query: str,
    chroma_coll,
    where_clause: Optional[Dict[str, Any]],
    limit: int = 30
) -> List[Dict[str, Any]]:
    """Execute Chroma vector search with asymmetric 'search_query:' prefix."""
    q_vec = embeddings.embed_query(f"search_query: {query.strip()}")
    
    query_kwargs: Dict[str, Any] = {
        "query_embeddings": [q_vec],
        "n_results": limit,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_clause:
        query_kwargs["where"] = where_clause

    results = chroma_coll.query(**query_kwargs)
    
    candidates = []
    if results and results.get("ids") and results["ids"][0]:
        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        dists = results["distances"][0] if results.get("distances") else [0.0] * len(ids)
        for i in range(len(ids)):
            candidates.append({
                "id": ids[i],
                "document": docs[i],
                "metadata": metas[i],
                "score": float(dists[i]),  # distance (lower is closer in Chroma L2/cosine)
            })
    return candidates


def refresh_from_chroma(chroma_coll, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Re-read document + metadata for the final candidates straight from Chroma.

    BM25-only hits carry the copy of metadata cached when the keyword engine was built.
    Price and stock can change after that (build_index.py updates metadata in place),
    so the cards the user sees must come from the live index, not the cache.
    """
    if not candidates:
        return candidates
    ids = [str(c["id"]) for c in candidates]
    live = chroma_coll.get(ids=ids, include=["documents", "metadatas"])
    by_id = {
        live_id: (doc, meta)
        for live_id, doc, meta in zip(live.get("ids", []), live.get("documents", []), live.get("metadatas", []))
    }
    refreshed = []
    for c in candidates:
        if str(c["id"]) not in by_id:
            continue  # deleted from the index since the BM25 cache was built
        doc, meta = by_id[str(c["id"])]
        refreshed.append({**c, "document": doc, "metadata": meta or {}})
    return refreshed


def run_hybrid_pipeline(
    query: str,
    category: str,
    chroma_coll,
    where_clause: Optional[Dict[str, Any]],
    allowed_ids: Optional[Set[str]] = None,
    strategy: Literal["vector", "hybrid", "hybrid_rerank"] = "hybrid",
    top_k: int = 8
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Execute retrieval according to the requested strategy.
    
    Strategies:
    - 'vector': Chroma vector search only (top candidates)
    - 'hybrid': Vector (top 30) + BM25 (top 30) merged via RRF (top 20 -> top_k)
    - 'hybrid_rerank': Hybrid (top 20) -> Cross-Encoder reranked -> top_k
    
    Filtering: Chroma's where_clause is the ONLY filter. BM25 may only return IDs in
    `allowed_ids` (the IDs that pass where_clause). If the caller didn't pass them, they
    are fetched here with one cheap collection.get(where=..., include=[]).

    Returns (candidate_list, diagnostics_dict).
    """
    diagnostics: Dict[str, Any] = {
        "strategy": strategy,
        "query": query,
        "category": category,
        "vector_count": 0,
        "keyword_count": 0,
        "merged_count": 0,
        "rerank_elapsed_ms": 0.0,
    }

    # 1. Strategy: Vector Only
    if strategy == "vector":
        t0 = time.perf_counter()
        candidates = run_vector_search(query, chroma_coll, where_clause, limit=max(top_k, 30))
        diagnostics["vector_count"] = len(candidates)
        diagnostics["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
        return candidates[:top_k], diagnostics

    # 2. Hybrid: Vector + BM25
    t_start = time.perf_counter()
    vector_candidates = run_vector_search(query, chroma_coll, where_clause, limit=30)
    diagnostics["vector_count"] = len(vector_candidates)

    if allowed_ids is None:
        passing = chroma_coll.get(where=where_clause, include=[]) if where_clause else chroma_coll.get(include=[])
        allowed_ids = {str(i) for i in passing.get("ids", [])}

    kw_engine = get_keyword_engine(chroma_coll=chroma_coll)
    keyword_candidates = kw_engine.search(query=query, category=category, allowed_ids=allowed_ids, limit=30)
    diagnostics["keyword_count"] = len(keyword_candidates)

    merged = rrf_merge(vector_candidates, keyword_candidates, k=DEFAULT_RRF_K, limit=20)
    # Fresh price/stock/document for everything we might show (fixes stale BM25 cache).
    merged = refresh_from_chroma(chroma_coll, merged)
    diagnostics["merged_count"] = len(merged)

    # 3. Strategy: Hybrid without reranker
    if strategy == "hybrid":
        diagnostics["elapsed_ms"] = (time.perf_counter() - t_start) * 1000.0
        return merged[:top_k], diagnostics

    # 4. Strategy: Hybrid with Cross-Encoder Reranker
    reranker = get_reranker()
    reranked, rerank_ms = reranker.rerank(query, merged, limit=top_k)
    diagnostics["rerank_elapsed_ms"] = rerank_ms
    diagnostics["elapsed_ms"] = (time.perf_counter() - t_start) * 1000.0
    return reranked, diagnostics
