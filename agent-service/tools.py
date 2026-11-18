"""
tools.py - Day 8 Deterministic Tools and Agent Tool Registry

Provides three robust, validated tools for the PC building agent:
1. search_parts: Semantic vector search + strict metadata filtering ($and) via ChromaDB.
   Prioritizes components with verified physical/electrical specifications (checkable)
   via a soft boost/tie-break rather than an absolute override.
2. price_total: Exact arithmetic summation and per-item pricing from MongoDB.
   Accurately handles duplicate parts (e.g. 2x RAM sticks) and reports missing prices.
3. check_compatibility: Rigorous deterministic physical/electrical validation using checker.py.

All tools validate inputs using Pydantic, return clean structured JSON, never mutate
the database, and handle errors gracefully with sanitized error messages rather than crashing.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import chromadb
from pydantic import ValidationError

import embeddings
from build_index import COLLECTION_NAME, get_chroma_client, get_collection
from checker import check_build, is_part_checkable
from normalize import (
    normalize_category,
    normalize_form_factor,
    normalize_ram_type,
    normalize_socket,
)
from repo import BasePartRepo, RepoUnavailableError, get_repo
from tool_models import (
    CheckCompatibilityInput,
    PartCard,
    PriceTotalInput,
    SearchPartsInput,
)

logger = logging.getLogger(__name__)

# Mapping from motherboard form factor to compatible cabinet case_type values in the catalogue
CASE_TYPES_FOR_BOARD_FF: Dict[str, List[str]] = {
    "Mini ITX": [
        "ATX Full Tower", "ATX Mid Tower", "ATX Desktop",
        "MicroATX Mid Tower", "MicroATX Mini Tower", "MicroATX Desktop",
        "Mini ITX Tower", "Mini ITX Desktop",
    ],
    "Micro ATX": [
        "ATX Full Tower", "ATX Mid Tower", "ATX Desktop",
        "MicroATX Mid Tower", "MicroATX Mini Tower", "MicroATX Desktop",
    ],
    "ATX": [
        "ATX Full Tower", "ATX Mid Tower", "ATX Desktop",
    ],
    "EATX": [
        "ATX Full Tower",
    ],
}


# ─── 1. SEARCH_PARTS TOOL ──────────────────────────────────────────────────────
def build_chroma_where(params: SearchPartsInput) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Construct Chroma where filter dictionary from SearchPartsInput.
    Rules:
    - Single condition: returns the bare condition dict {"category": "processor"}.
    - Multiple conditions: wraps inside {"$and": [...]}.
    - When category is 'cabinet' and allowed_form_factors is provided, translates
      the motherboard form factors to valid case_type values with $in.
    - Returns (where_clause, filters_applied_dict).
    """
    conditions: List[Dict[str, Any]] = []
    filters_applied: Dict[str, Any] = {}

    # 1. Category (always required and normalized)
    cat = params.category
    conditions.append({"category": cat})
    filters_applied["category"] = cat

    # 2. In Stock Only
    if params.in_stock_only:
        conditions.append({"in_stock": True})
        filters_applied["in_stock_only"] = True

    # 3. Max Price Budget
    if params.max_price is not None:
        conditions.append({"price": {"$lte": float(params.max_price)}})
        filters_applied["max_price"] = float(params.max_price)

    # 4. Socket (CPU / Motherboard)
    if params.socket:
        sock = normalize_socket(params.socket)
        if sock:
            conditions.append({"socket": sock})
            filters_applied["socket"] = sock

    # 5. RAM Generation (DDR4 / DDR5)
    if params.ram_type:
        rt = normalize_ram_type(params.ram_type)
        if rt:
            if rt in ("DDR4", "DDR5"):
                # Parts that support both generations (e.g. LGA1700 CPUs) are stored as
                # "DDR4/DDR5". An exact {"ram_type": "DDR5"} match would silently drop them.
                conditions.append({"ram_type": {"$in": [rt, "DDR4/DDR5"]}})
            else:
                conditions.append({"ram_type": rt})
            filters_applied["ram_type"] = rt

    # 6. Form Factor (Motherboard vs Cabinet)
    if params.allowed_form_factors:
        clean_ffs = [normalize_form_factor(ff) for ff in params.allowed_form_factors if ff]
        clean_ffs = [f for f in clean_ffs if f]

        if cat == "cabinet":
            allowed_cases = set()
            for ff in clean_ffs:
                types = CASE_TYPES_FOR_BOARD_FF.get(ff)
                if types:
                    allowed_cases.update(types)
                else:
                    allowed_cases.add(ff)

            compat_case_types = sorted(list(allowed_cases))
            if compat_case_types:
                if len(compat_case_types) == 1:
                    conditions.append({"case_type": compat_case_types[0]})
                else:
                    conditions.append({"case_type": {"$in": compat_case_types}})
                filters_applied["compatible_case_types"] = compat_case_types
        else:
            # Motherboard form factor filter
            if len(clean_ffs) == 1:
                conditions.append({"form_factor": clean_ffs[0]})
                filters_applied["allowed_form_factors"] = clean_ffs
            elif len(clean_ffs) > 1:
                conditions.append({"form_factor": {"$in": clean_ffs}})
                filters_applied["allowed_form_factors"] = clean_ffs

    # 7. Min Wattage (PSU)
    if params.min_wattage is not None:
        conditions.append({"wattage": {"$gte": float(params.min_wattage)}})
        filters_applied["min_wattage"] = float(params.min_wattage)

    # 8. Max GPU Length
    if params.max_gpu_length is not None:
        conditions.append({"length": {"$lte": float(params.max_gpu_length)}})
        filters_applied["max_gpu_length"] = float(params.max_gpu_length)

    # 9. Cooler Kind ('air' vs 'liquid')
    if params.cooler_kind:
        conditions.append({"cooler_kind": params.cooler_kind})
        filters_applied["cooler_kind"] = params.cooler_kind

    # Single condition vs $and wrapping
    if not conditions:
        return None, filters_applied
    if len(conditions) == 1:
        return conditions[0], filters_applied
    return {"$and": conditions}, filters_applied


def _search_error(message: str, filters_applied: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Error-shaped search result. The "error" key tells the agent this is an outage,
    so it should report the problem instead of loosening the user's filters.
    """
    return {
        "error": message,
        "count": 0,
        "total_matching": 0,
        "filters_applied": filters_applied or {},
        "cards": [],
        "message": message,
    }


def _suggest_relaxation(params: SearchPartsInput) -> str:
    """Generate helpful guidance on which filter to relax when 0 parts match."""
    relaxations = []
    if params.max_price is not None:
        relaxations.append(f"increasing max_price (currently ₹{int(params.max_price):,})")
    if params.in_stock_only:
        relaxations.append("setting in_stock_only=False")
    if params.socket:
        relaxations.append(f"removing socket constraint '{params.socket}'")
    if params.ram_type:
        relaxations.append(f"removing ram_type constraint '{params.ram_type}'")
    if params.allowed_form_factors:
        relaxations.append(f"expanding allowed_form_factors ({params.allowed_form_factors})")
    if params.min_wattage:
        relaxations.append(f"lowering min_wattage ({params.min_wattage}W)")
    if params.max_gpu_length:
        relaxations.append("relaxing max_gpu_length")
    if params.cooler_kind:
        relaxations.append(f"relaxing cooler_kind '{params.cooler_kind}'")

    if relaxations:
        return "No parts matched all criteria. Try: " + "; or ".join(relaxations) + "."
    return "No parts found in the catalog matching the requested category."


# One shared Chroma collection for all search_parts calls. Opening a new connection
# costs ~300ms , and the agent calls search_parts many times per request.
_CHROMA_COLLECTION: Optional[chromadb.Collection] = None


def _shared_collection(reconnect: bool = False) -> chromadb.Collection:
    """Return the shared collection, connecting only the first time (or when reconnect=True)."""
    global _CHROMA_COLLECTION
    if _CHROMA_COLLECTION is None or reconnect:
        _CHROMA_COLLECTION = None  # never keep a connection we just decided is bad
        _CHROMA_COLLECTION = get_collection(get_chroma_client())
    return _CHROMA_COLLECTION


def search_parts(
    params: SearchPartsInput,
    repo: Optional[BasePartRepo] = None,
    collection: Optional[chromadb.Collection] = None,
) -> Dict[str, Any]:
    """
    Search component catalog using ChromaDB vector similarity and metadata filtering.
    Prioritizes parts with verified physical/electrical specifications (checkable)
    using a tie-break / soft boost rather than an absolute override.

    Connection handling:
    - A collection passed in by the caller (tests, eval_search.py) is used as it is.
    - Otherwise one shared connection is reused. If a search through it fails, the
      connection may be stale (Chroma restarted, or build_index.py rebuilt the index),
      so we reconnect ONCE and retry. If that fails too, the error is returned.
    """
    if collection is not None:
        return _search_parts_in(params, collection)

    # Only CONNECTING is caught here. Other errors (e.g. Ollama down while embedding the
    # query) pass through to run_tool unchanged, so they are not blamed on Chroma.
    unavailable = "Vector search service unavailable. Please check Chroma server."
    try:
        coll = _shared_collection()
    except Exception as exc:
        logger.warning("ChromaDB unavailable in search_parts: %s", exc)
        return _search_error(unavailable)

    result = _search_parts_in(params, coll)
    if "error" not in result:
        return result

    logger.warning("search_parts failed on the saved Chroma connection; reconnecting once.")
    try:
        coll = _shared_collection(reconnect=True)
    except Exception as exc:
        logger.warning("ChromaDB still unavailable after reconnecting: %s", exc)
        return _search_error(unavailable)
    return _search_parts_in(params, coll)


def _search_parts_in(params: SearchPartsInput, collection: chromadb.Collection) -> Dict[str, Any]:
    """The search itself, on a given Chroma collection."""
    where, filters_applied = build_chroma_where(params)
    keywords_clean = (params.keywords or "").strip()
    candidates: List[Dict[str, Any]] = []

    if keywords_clean:
        try:
            matched_ids_res = collection.get(where=where, include=[])
            total_matching = len(matched_ids_res["ids"]) if matched_ids_res and matched_ids_res.get("ids") else 0
        except Exception as exc:
            # A failed query is an outage, NOT "zero parts matched" -- don't tell the agent to relax filters.
            logger.warning("Chroma matching count query failed: %s", exc)
            return _search_error("Search index query failed. Check Chroma server status.", filters_applied)

        if total_matching == 0:
            return {
                "count": 0,
                "total_matching": 0,
                "filters_applied": filters_applied,
                "cards": [],
                "message": _suggest_relaxation(params),
            }

        strategy = getattr(params, "retriever", "vector")
        if strategy == "vector":
            # Embed query with asymmetric prefix
            query_emb = embeddings.embed_query(f"search_query: {keywords_clean}")
            # Fetch sufficient results to rank and sort (up to 5x limit or all matching, max 60)
            fetch_k = min(total_matching, max(params.limit * 5, 25), 60)
            try:
                results = collection.query(
                    query_embeddings=[query_emb],
                    n_results=fetch_k,
                    where=where,
                    include=["documents", "metadatas", "distances"],
                )
                if results and results.get("ids") and results["ids"][0]:
                    for i in range(len(results["ids"][0])):
                        pid = results["ids"][0][i]
                        doc_text = results["documents"][0][i]
                        meta = results["metadatas"][0][i] or {}
                        dist = results["distances"][0][i] if results.get("distances") else 0.0
                        candidates.append({
                            "id": pid,
                            "document": doc_text,
                            "metadata": meta,
                            "distance": dist,
                        })
            except Exception as exc:
                logger.error("Chroma query failed: %s", exc)
                return _search_error("Search query failed. Check query parameters or server status.", filters_applied)
        else:
            # 'hybrid' or 'hybrid_rerank'
            try:
                from hybrid_search import run_hybrid_pipeline
                cands, _ = run_hybrid_pipeline(
                    query=keywords_clean,
                    category=params.category,
                    chroma_coll=collection,
                    where_clause=where,
                    # IDs that passed Chroma's filters above: BM25 may only rank these,
                    # so there is exactly ONE filter implementation (the where clause).
                    allowed_ids={str(i) for i in matched_ids_res["ids"]},
                    strategy=strategy,
                    top_k=params.limit,
                )
                for c in cands:
                    candidates.append({
                        "id": c["id"],
                        "document": c.get("document", ""),
                        "metadata": c.get("metadata", {}),
                        "distance": c.get("vector_score", 0.0) or 0.0,
                    })
            except Exception as exc:
                logger.error("Hybrid pipeline failed: %s", exc)
                return _search_error("Hybrid search failed. Check search parameters or server status.", filters_applied)
    else:
        try:
            results = collection.get(
                where=where,
                include=["documents", "metadatas"],
            )
            if results and results.get("ids"):
                for i in range(len(results["ids"])):
                    pid = results["ids"][i]
                    doc_text = results["documents"][i] if results.get("documents") else ""
                    meta = results["metadatas"][i] if results.get("metadatas") else {}
                    candidates.append({
                        "id": pid,
                        "document": doc_text,
                        "metadata": meta,
                        "distance": 0.0,
                    })
            total_matching = len(candidates)
        except Exception as exc:
            logger.error("Chroma get failed: %s", exc)
            return _search_error("Catalog lookup failed. Check filter parameters or server status.", filters_applied)

    if total_matching == 0:
        return {
            "count": 0,
            "total_matching": 0,
            "filters_applied": filters_applied,
            "cards": [],
            "message": _suggest_relaxation(params),
        }

    # Enrich candidates with checkability & build PartCards (Issue 4: rich card fields)
    cards: List[Dict[str, Any]] = []
    for cand in candidates:
        meta = cand["metadata"]
        pid = cand["id"]

        # Infer name from document or metadata
        doc_text = cand.get("document", "")
        name = meta.get("name")
        if not name:
            name = doc_text.split(",")[0].rstrip(".") if doc_text else pid

        part_dict = {
            "id": pid,
            "name": name,
            "category": meta.get("category", params.category),
            "price": meta.get("price"),
            "socket": meta.get("socket"),
            "ram_type": meta.get("ram_type"),
            "form_factor": meta.get("form_factor"),
            "tdp": meta.get("tdp"),
            "wattage": meta.get("wattage"),
            "length": meta.get("length"),
            "height": meta.get("height_mm") or meta.get("height"),
            "cooler_kind": meta.get("cooler_kind"),
            "case_type": meta.get("case_type"),
            "chipset": meta.get("chipset"),
            "max_gpu_length": meta.get("max_gpu_length"),
            "max_cooler_height": meta.get("max_cooler_height"),
            "in_stock": meta.get("in_stock", True),
            "raw": meta,
        }

        # Radiator size for coolers
        radiator_size = meta.get("radiator_size") or meta.get("size")
        if radiator_size is None and "radiator" in doc_text:
            m_rad = re.search(r"(\d+)\s*mm\s*radiator", doc_text, re.IGNORECASE)
            if m_rad:
                radiator_size = int(m_rad.group(1))
        elif radiator_size is not None:
            try:
                radiator_size = int(float(radiator_size))
            except (ValueError, TypeError):
                radiator_size = None

        # GPU memory
        gpu_memory = meta.get("gpu_memory") or meta.get("memory")
        if gpu_memory is not None:
            try:
                gpu_memory = int(float(gpu_memory))
            except (ValueError, TypeError):
                gpu_memory = None

        # RAM speed
        speed_mhz = meta.get("speed_mhz")
        if speed_mhz is not None:
            try:
                speed_mhz = int(float(speed_mhz))
            except (ValueError, TypeError):
                speed_mhz = None

        # Storage / RAM capacity
        capacity_gb = meta.get("capacity_gb") or meta.get("capacity")
        if capacity_gb is not None:
            try:
                capacity_gb = int(float(capacity_gb))
            except (ValueError, TypeError):
                capacity_gb = None

        # Check if component is checkable
        is_chk = is_part_checkable(part_dict)

        card = PartCard(
            id=pid,
            name=name,
            category=part_dict["category"],
            price=part_dict["price"],
            socket=part_dict.get("socket"),
            ram_type=part_dict.get("ram_type"),
            form_factor=part_dict.get("form_factor"),
            case_type=part_dict.get("case_type"),
            wattage=part_dict.get("wattage"),
            tdp=part_dict.get("tdp"),
            length_mm=part_dict.get("length"),
            height_mm=part_dict.get("height"),
            cooler_kind=part_dict.get("cooler_kind"),
            radiator_size=radiator_size,
            gpu_memory=gpu_memory,
            speed_mhz=speed_mhz,
            capacity_gb=capacity_gb,
            in_stock=bool(part_dict.get("in_stock", True)),
            checkable=is_chk,
        ).model_dump()

        card["_distance"] = cand.get("distance", 0.0)
        cards.append(card)

    if keywords_clean:
        if getattr(params, "retriever", "vector") == "vector":
            # Distance is cosine distance (lower = closer semantic match).
            # Checkable parts receive a small 0.05 boost so close matches prefer checkable,
            # but a strong semantic match (e.g. RX 9060 XT) will never be overtaken by an irrelevant checkable part.
            def _keyword_sort_key(c: Dict[str, Any]) -> Tuple[float, float]:
                raw_dist = c.get("_distance", 0.0)
                boost = 0.05 if c.get("checkable") else 0.0
                effective_dist = max(0.0, raw_dist - boost)
                price = c.get("price") or 999999.0
                return (round(effective_dist, 4), price)

            cards.sort(key=_keyword_sort_key)
        else:
            # Hybrid and hybrid_rerank are already ordered by RRF / cross-encoder rank
            pass
    else:
        cards.sort(key=lambda c: (c.get("price") or 999999.0, not c.get("checkable", False)))

    # Strip internal sort key and slice to limit
    final_cards = []
    for c in cards[: params.limit]:
        c.pop("_distance", None)
        final_cards.append(c)

    return {
        "count": len(final_cards),
        "total_matching": total_matching,
        "filters_applied": filters_applied,
        "cards": final_cards,
        "message": f"Found {len(final_cards)} matching {params.category} candidate(s) out of {total_matching} total match(es).",
    }


# ─── 2. PRICE_TOTAL TOOL ───────────────────────────────────────────────────────
def price_total(
    params: PriceTotalInput,
    repo: Optional[BasePartRepo] = None,
) -> Dict[str, Any]:
    """
    Look up each ID in MongoDB and calculate total build cost, per-item pricing,
    and flag any parts missing price data. Repeated IDs are counted multiple times.
    """
    if repo is None:
        repo = get_repo()

    part_ids = params.part_ids
    if not part_ids:
        return {
            "items": [],
            "total": 0.0,
            "item_count": 0,
            "missing_price": [],
            "unresolved": [],
        }

    # Fetch parts matching unique IDs
    unique_ids = list(set(part_ids))
    found_parts = repo.get_many(unique_ids)

    # Build lookup maps by exact ID and lowercase ID
    part_map: Dict[str, Dict[str, Any]] = {}
    for p in found_parts:
        pid = str(p.get("id") or p.get("_id", "")).strip()
        if pid:
            part_map[pid] = p
            part_map[pid.lower()] = p

    items: List[Dict[str, Any]] = []
    total = 0.0
    missing_price: List[str] = []
    unresolved: List[str] = []

    # Preserve order and count repetitions (e.g. 2x RAM sticks)
    for raw_id in part_ids:
        clean_id = str(raw_id).strip()
        doc = part_map.get(clean_id) or part_map.get(clean_id.lower())

        if not doc:
            unresolved.append(clean_id)
            items.append({
                "id": clean_id,
                "name": f"Unknown Component ({clean_id})",
                "price": None,
                "category": None,
            })
            continue

        name = doc.get("name", clean_id)
        cat = doc.get("category")
        price = doc.get("price") if doc.get("price") is not None else doc.get("price_inr")

        if price is None:
            missing_price.append(clean_id)
            items.append({
                "id": clean_id,
                "name": name,
                "price": None,
                "category": cat,
            })
        else:
            try:
                p_val = float(price)
                total += p_val
                items.append({
                    "id": clean_id,
                    "name": name,
                    "price": p_val,
                    "category": cat,
                })
            except (ValueError, TypeError):
                missing_price.append(clean_id)
                items.append({
                    "id": clean_id,
                    "name": name,
                    "price": None,
                    "category": cat,
                })

    return {
        "items": items,
        "total": round(total, 2),
        "item_count": len(items),
        "missing_price": missing_price,
        "unresolved": unresolved,
    }


# ─── 3. CHECK_COMPATIBILITY TOOL ───────────────────────────────────────────────
def check_compatibility(
    params: CheckCompatibilityInput,
    repo: Optional[BasePartRepo] = None,
) -> Dict[str, Any]:
    """
    Verify physical, electrical, and budgetary compatibility of a proposed PC build
    using the deterministic checker. Never guesses. Resolves IDs and reports unresolved parts.
    """
    if repo is None:
        repo = get_repo()

    part_ids = params.part_ids
    unique_ids = list(set(part_ids))

    # Resolve from repo
    found_parts = repo.get_many(unique_ids)
    part_lookup: Dict[str, Dict[str, Any]] = {}
    for p in found_parts:
        pid = str(p.get("id") or p.get("_id", "")).strip()
        if pid:
            part_lookup[pid] = p
            part_lookup[pid.lower()] = p

    # Execute deterministic compatibility check
    check_result = check_build(
        build=part_ids,
        budget=params.budget,
        part_lookup=part_lookup,
        partial=params.partial,
    )

    return {
        "valid": check_result["valid"],
        "fully_verified": check_result["fully_verified"],
        "rules": check_result["rules"],
        "fails": check_result["fails"],
        "unknowns": check_result["unknowns"],
        "unresolved": check_result["unresolved"],
        "total_price": check_result["total_price"],
        "checkable_parts": check_result["checkable_parts"],
        "uncheckable_parts": check_result["uncheckable_parts"],
    }


# ─── 4. TOOL REGISTRY & DISPATCHER ────────────────────────────────────────────
TOOLS: Dict[str, Dict[str, Any]] = {
    "search_parts": {
        "name": "search_parts",
        "description": (
            "Search real PC components in the catalog by category, keywords, budget, "
            "and physical/electrical constraints (socket, RAM generation, form factor, wattage). "
            "Returns up to 10 candidate cards prioritizing checkable parts."
        ),
        "input_model": SearchPartsInput,
        "function": search_parts,
    },
    "price_total": {
        "name": "price_total",
        "description": (
            "Calculate exact total price and per-item costs for a list of component IDs from the catalog. "
            "Accurately handles repeated parts and reports missing prices."
        ),
        "input_model": PriceTotalInput,
        "function": price_total,
    },
    "check_compatibility": {
        "name": "check_compatibility",
        "description": (
            "Verify physical, electrical, and budgetary compatibility of a proposed PC build "
            "using the deterministic 9-rule Python checker. Never guesses. "
            "Set partial=true while still choosing parts, so categories not chosen yet are UNKNOWN instead of FAIL."
        ),
        "input_model": CheckCompatibilityInput,
        "function": check_compatibility,
    },
}


def run_tool(
    name: str,
    args: Dict[str, Any],
    repo: Optional[BasePartRepo] = None,
    collection: Optional[chromadb.Collection] = None,
) -> Dict[str, Any]:
    """
    Execute a registered tool by name with arguments.
    Validates arguments via Pydantic model and handles errors gracefully without crashing.
    """
    if name not in TOOLS:
        valid_tools = ", ".join(sorted(list(TOOLS.keys())))
        return {"error": f"Tool '{name}' not found. Available tools are: {valid_tools}"}

    tool_entry = TOOLS[name]
    input_model = tool_entry["input_model"]
    fn = tool_entry["function"]

    # 1. Validate arguments
    try:
        validated_params = input_model(**args)
    except ValidationError as val_err:
        errors = []
        for e in val_err.errors():
            loc = ".".join(str(x) for x in e["loc"])
            msg = e["msg"]
            errors.append(f"{loc}: {msg}")
        return {"error": f"Invalid arguments for tool '{name}': {'; '.join(errors)}"}
    except Exception as exc:
        logger.warning("Unexpected validation error for tool '%s': %s", name, exc)
        return {"error": f"Invalid arguments for tool '{name}'."}

    # 2. Execute tool (sanitized error reporting, no internal leakage)
    try:
        if name == "search_parts":
            return fn(validated_params, repo=repo, collection=collection)
        elif name in ("price_total", "check_compatibility"):
            return fn(validated_params, repo=repo)
        else:
            return fn(validated_params)
    except RepoUnavailableError as exc:
        # Say clearly that this is a server outage, so the agent doesn't retry with "better" part IDs.
        logger.error("Tool '%s' could not reach the parts database: %s", name, exc)
        return {"error": f"Tool '{name}' failed: the parts database is unavailable (server problem, not a bad part ID)."}
    except Exception as exc:
        logger.exception("Error executing tool '%s': %s", name, exc)
        return {"error": f"Tool '{name}' execution failed. Please check arguments or retry."}


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Export raw tool definitions with JSON schemas for function calling..
    """
    defs = []
    for t_name, t_info in TOOLS.items():
        defs.append({
            "name": t_name,
            "description": t_info["description"],
            "parameters": t_info["input_model"].model_json_schema(),
        })
    return defs
