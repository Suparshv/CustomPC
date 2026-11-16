#!/usr/bin/env python3
"""
keyword_search.py - BM25 keyword search index per category for PC parts.

Key Features:
- Preserves technical codes (e.g., 'i5-12400', 'b550m', 'rtx-4060') during tokenization.
- Splits compound unit numbers (e.g., '32gb' -> '32gb', '32', 'gb') to maximize match recall.
- Category-sharded BM25Okapi indices cached in memory.
- Strict metadata filtering parity with Chroma vector search filters.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Set

from rank_bm25 import BM25Okapi

from normalize import normalize_socket, normalize_ram_type, normalize_form_factor

logger = logging.getLogger(__name__)

# Motherboard to Case compatibility mapping (matching Day 8 specification)
CASE_TYPES_FOR_BOARD_FF: Dict[str, List[str]] = {
    "ATX": ["ATX Mid Tower", "ATX Full Tower", "ATX Desktop"],
    "Micro ATX": ["MicroATX Mid Tower", "MicroATX Mini Tower", "ATX Mid Tower", "ATX Full Tower"],
    "Mini ITX": ["Mini ITX Desktop", "Mini ITX Tower", "MicroATX Mid Tower", "MicroATX Mini Tower", "ATX Mid Tower", "ATX Full Tower"],
    "Mini-ITX": ["Mini ITX Desktop", "Mini ITX Tower", "MicroATX Mid Tower", "MicroATX Mini Tower", "ATX Mid Tower", "ATX Full Tower"],
    "E-ATX": ["ATX Full Tower"],
    "EATX": ["ATX Full Tower"],
}


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


def matches_filters(meta: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """
    Check if a component's metadata dict satisfies the applied search filters.
    Matches the exact semantics of Chroma's where clause.
    """
    if not filters:
        return True

    # 1. Category
    if "category" in filters and filters["category"]:
        if meta.get("category") != filters["category"]:
            return False

    # 2. In stock only
    if filters.get("in_stock_only"):
        if not bool(meta.get("in_stock", True)):
            return False

    # 3. Max price
    if filters.get("max_price") is not None:
        price = meta.get("price")
        if price is None:
            return False
        try:
            if float(price) > float(filters["max_price"]):
                return False
        except (ValueError, TypeError):
            return False

    # 4. Socket
    if filters.get("socket"):
        target_sock = normalize_socket(filters["socket"])
        cand_sock = normalize_socket(meta.get("socket") or "")
        if cand_sock != target_sock:
            return False

    # 5. RAM Generation
    if filters.get("ram_type"):
        target_rt = normalize_ram_type(filters["ram_type"])
        cand_rt = normalize_ram_type(meta.get("ram_type") or "")
        # Allow multi-compatible boards/CPUs like "DDR4/DDR5"
        raw_cand = str(meta.get("ram_type", "")).upper()
        if cand_rt != target_rt and (target_rt not in raw_cand):
            return False

    # 6. Form factor & Case type
    if filters.get("allowed_form_factors"):
        cat = meta.get("category", "")
        raw_ffs = filters["allowed_form_factors"]
        clean_ffs = [normalize_form_factor(ff) for ff in raw_ffs if ff]
        clean_ffs = [f for f in clean_ffs if f]

        if cat == "cabinet":
            allowed_cases: Set[str] = set()
            for ff in clean_ffs:
                types = CASE_TYPES_FOR_BOARD_FF.get(ff)
                if types:
                    allowed_cases.update(types)
                else:
                    allowed_cases.add(ff)
            case_type = meta.get("case_type")
            if case_type not in allowed_cases:
                return False
        else:
            cand_ff = normalize_form_factor(meta.get("form_factor") or "")
            if cand_ff not in clean_ffs:
                return False

    # 7. Min wattage (PSU)
    if filters.get("min_wattage") is not None:
        watt = meta.get("wattage")
        if watt is None:
            return False
        try:
            if float(watt) < float(filters["min_wattage"]):
                return False
        except (ValueError, TypeError):
            return False

    # 8. Max GPU length
    if filters.get("max_gpu_length") is not None:
        length = meta.get("length")
        if length is not None:
            try:
                if float(length) > float(filters["max_gpu_length"]):
                    return False
            except (ValueError, TypeError):
                pass  # If length missing/invalid, do not reject outright

    # 9. Cooler kind
    if filters.get("cooler_kind"):
        if meta.get("cooler_kind") != filters["cooler_kind"]:
            return False

    return True


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
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Score documents with BM25, apply metadata filters, return top-N."""
        if not self.items:
            return []

        if not self.bm25:
            # Fallback if corpus documents are empty (e.g. mock test collection)
            candidates = []
            for item in self.items:
                if filters and not matches_filters(item.get("metadata", {}), filters):
                    continue
                candidates.append({
                    "id": item["id"],
                    "document": item.get("document", ""),
                    "metadata": item.get("metadata", {}),
                    "score": 0.0
                })
            return candidates[:limit]

        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        scores = self.bm25.get_scores(q_tokens)
        
        # Collect scored candidates that pass metadata filters
        candidates = []
        for idx, score in enumerate(scores):
            item = self.items[idx]
            if filters and not matches_filters(item["metadata"], filters):
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
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Search within a specific category index."""
        cat_index = self.indices.get(category)
        if not cat_index:
            return []
        
        filt = dict(filters) if filters else {}
        filt["category"] = category
        return cat_index.search(query=query, filters=filt, limit=limit)


# Global singleton keyword engine
_KEYWORD_ENGINE: Optional[KeywordSearchEngine] = None


def get_keyword_engine(chroma_coll=None, force_reload: bool = False) -> KeywordSearchEngine:
    """
    Get or initialize the global KeywordSearchEngine from Chroma collection.
    Loads documents and metadatas into memory once and caches them.
    """
    global _KEYWORD_ENGINE
    if _KEYWORD_ENGINE is not None and not force_reload:
        return _KEYWORD_ENGINE

    if chroma_coll is None:
        from build_index import get_chroma_client, get_collection
        client = get_chroma_client()
        chroma_coll = get_collection(client)

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
    return _KEYWORD_ENGINE
