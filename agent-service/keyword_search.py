#!/usr/bin/env python3
"""
keyword_search.py - BM25 keyword search index per category for PC parts.

Key Features:
- Preserves technical codes (e.g., 'i5-12400', 'b550m', 'rtx-4060') during tokenization.
- Splits compound unit numbers (e.g., '32gb' -> '32gb', '32', 'gb') to maximize match recall.
- Category-sharded BM25Okapi indices cached in memory.
- Filtering is done by Chroma; BM25 only ranks inside an allow-list of IDs.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Set, Tuple

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# NOTE (code review): this module used to keep its OWN copy of every metadata filter
# (`matches_filters` + a copy of the case-type map). It drifted from the Chroma `where`
# clause in tools.py (missing GPU length passed here but not in Chroma; case types differed).
# Now Chroma is the single source of truth: the caller asks Chroma which IDs pass the
# filters and hands that set to BM25 as `allowed_ids`.


def tokenize(text: str) -> List[str]:
    """
    Tokenize text while keeping product codes, chipset names, and hyphenated model IDs whole.
    Also expands compound units (like '32gb' -> '32gb', '32', 'gb') for high BM25 match recall.
    """
    if not text:
        return []
    
    text = text.lower()
    # Match alphanumeric sequences with internal hyphens or underscores
    raw_tokens = re.findall(r'[a-z0-9]+(?:[-_][a-z0-9]+)*', text)
    tokens: List[str] = []
    
    for t in raw_tokens:
        tokens.append(t)
        # If token has hyphens/underscores, also emit sub-tokens
        if '-' in t or '_' in t:
            subparts = re.split(r'[-_]', t)
            for p in subparts:
                if p and p != t:
                    tokens.append(p)
        # If token has number + unit (e.g. 32gb, 750w, 120mm, 2tb, 16gb, 6000mhz)
        m = re.match(r'^(\d+)([a-z]+)$', t)
        if m:
            tokens.append(m.group(1))
            tokens.append(m.group(2))

    return tokens


class CategoryBM25Index:
    """Manages an in-memory BM25Okapi index for one category."""

    def __init__(self, category: str, items: List[Dict[str, Any]]):
        self.category = category
        self.items = items  # Each has "id", "document", "metadata"
        self.corpus_tokens = [tokenize(item.get("document", "")) for item in items]
        total_tokens = sum(len(toks) for toks in self.corpus_tokens)
        if self.corpus_tokens and total_tokens > 0:
            self.bm25 = BM25Okapi(self.corpus_tokens)
        else:
            self.bm25 = None

    def search(
        self,
        query: str,
        allowed_ids: Optional[Set[str]] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Score documents with BM25 and return the top-N.
        allowed_ids: if given, only these IDs may be returned (they already passed Chroma's filters).
        """
        if not self.items:
            return []

        def allowed(item: Dict[str, Any]) -> bool:
            return allowed_ids is None or str(item["id"]) in allowed_ids

        if not self.bm25:
            # Fallback if corpus documents are empty (e.g. mock test collection)
            return [
                {"id": item["id"], "document": item.get("document", ""),
                 "metadata": item.get("metadata", {}), "score": 0.0}
                for item in self.items if allowed(item)
            ][:limit]

        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        scores = self.bm25.get_scores(q_tokens)

        candidates = []
        for idx, score in enumerate(scores):
            item = self.items[idx]
            if not allowed(item):
                continue
            candidates.append({
                "id": item["id"],
                "document": item["document"],
                "metadata": item["metadata"],
                "score": float(score)
            })

        # Sort descending by BM25 score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:limit]


class KeywordSearchEngine:
    """In-memory keyword search engine spanning all product categories."""

    def __init__(self, items: Optional[List[Dict[str, Any]]] = None):
        self.indices: Dict[str, CategoryBM25Index] = {}
        self.all_items: Dict[str, Dict[str, Any]] = {}
        if items is not None:
            self.build_indices(items)

    def build_indices(self, items: List[Dict[str, Any]]) -> None:
        """Group items by category and construct per-category BM25 indices."""
        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        self.all_items.clear()
        self.indices.clear()

        for item in items:
            item_id = str(item["id"])
            self.all_items[item_id] = item
            cat = item.get("metadata", {}).get("category", "unknown")
            by_cat.setdefault(cat, []).append(item)

        for cat, cat_items in by_cat.items():
            self.indices[cat] = CategoryBM25Index(cat, cat_items)

        logger.info("Built BM25 indices across %d categories (%d total items)", len(self.indices), len(items))

    def search(
        self,
        query: str,
        category: str,
        allowed_ids: Optional[Set[str]] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Search within a specific category index, restricted to allowed_ids if given."""
        cat_index = self.indices.get(category)
        if not cat_index:
            return []
        return cat_index.search(query=query, allowed_ids=allowed_ids, limit=limit)


# Cached keyword engine, plus the key of the collection it was built from.
_KEYWORD_ENGINE: Optional[KeywordSearchEngine] = None
_KEYWORD_ENGINE_KEY: Optional[Tuple[str, int]] = None


def _collection_key(chroma_coll) -> Tuple[str, int]:
    """Identity of the indexed data: which collection, and how many parts it holds."""
    return (str(getattr(chroma_coll, "id", None) or getattr(chroma_coll, "name", "")), chroma_coll.count())


def get_keyword_engine(chroma_coll=None, force_reload: bool = False) -> KeywordSearchEngine:
    """
    Get (or build) the BM25 engine for a Chroma collection.

    The engine is cached, and rebuilt when a DIFFERENT collection is passed in or the
    collection's size changes (parts added/removed by build_index.py). It used to be built
    once from the first collection and reused forever. Prices/stock shown to the user are
    re-read from Chroma by hybrid_search, so the cached copy only matters for ranking text.
    """
    global _KEYWORD_ENGINE, _KEYWORD_ENGINE_KEY

    if chroma_coll is None:
        from build_index import get_chroma_client, get_collection
        client = get_chroma_client()
        chroma_coll = get_collection(client)

    key = _collection_key(chroma_coll)
    if _KEYWORD_ENGINE is not None and _KEYWORD_ENGINE_KEY == key and not force_reload:
        return _KEYWORD_ENGINE

    data = chroma_coll.get(include=["documents", "metadatas"])
    items = []
    ids = data.get("ids", [])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])

    for i in range(len(ids)):
        items.append({
            "id": ids[i],
            "document": docs[i] if i < len(docs) else "",
            "metadata": metas[i] if i < len(metas) else {}
        })

    _KEYWORD_ENGINE = KeywordSearchEngine(items)
    _KEYWORD_ENGINE_KEY = key
    return _KEYWORD_ENGINE
