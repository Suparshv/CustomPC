"""
tools.py - Day 8 Deterministic Tools and Agent Tool Registry

Provides three robust, validated tools for the PC building agent:
1. search_parts: Semantic vector search + strict metadata filtering ($and) via ChromaDB.
   Prioritizes components with verified physical/electrical specifications (checkable).
2. price_total: Exact arithmetic summation and per-item pricing from MongoDB.
   Accurately handles duplicate parts (e.g. 2x RAM sticks) and reports missing prices.
3. check_compatibility: Rigorous deterministic physical/electrical validation using checker.py.

All tools validate inputs using Pydantic, return clean structured JSON, never mutate
the database, and handle errors gracefully with informative messages rather than crashing.
"""

import logging
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
from repo import BasePartRepo, get_repo
from tool_models import (
    CheckCompatibilityInput,
    PartCard,
    PriceTotalInput,
    SearchPartsInput,
)

logger = logging.getLogger(__name__)


# ─── 1. SEARCH_PARTS TOOL ──────────────────────────────────────────────────────
def build_chroma_where(params: SearchPartsInput) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Construct Chroma where filter dictionary from SearchPartsInput.
    Rules:
    - Single condition: returns the bare condition dict {"category": "processor"}.
    - Multiple conditions: wraps inside {"$and": [...]}.
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
            conditions.append({"ram_type": rt})
            filters_applied["ram_type"] = rt

    # 6. Form Factor (Motherboard / Case)
    if params.allowed_form_factors:
        clean_ffs = [normalize_form_factor(ff) for ff in params.allowed_form_factors if ff]
        clean_ffs = [f for f in clean_ffs if f]
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


def search_parts(
    params: SearchPartsInput,
    repo: Optional[BasePartRepo] = None,
    collection: Optional[chromadb.Collection] = None,
) -> Dict[str, Any]:
    """
    Search component catalog using ChromaDB vector similarity and metadata filtering.
    Prioritizes parts with verified physical/electrical specifications (checkable).
    """
    if collection is None:
        try:
            client = get_chroma_client()
            collection = get_collection(client)
        except Exception as exc:
            # Fallback for offline testing without Chroma server
            logger.warning("ChromaDB unavailable in search_parts: %s", exc)
            return {
                "count": 0,
                "total_matching": 0,
                "filters_applied": {},
                "cards": [],
                "message": f"Vector search service unavailable: {str(exc)}",
            }

    where, filters_applied = build_chroma_where(params)
    fetch_k = min(max(params.limit * 4, 16), 40)

    keywords_clean = (params.keywords or "").strip()
    candidates: List[Dict[str, Any]] = []

    if keywords_clean:
        # Embed query with asymmetric prefix
        query_emb = embeddings.embed_query(keywords_clean)
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
            return {
                "count": 0,
                "total_matching": 0,
                "filters_applied": filters_applied,
                "cards": [],
                "message": f"Search query failed: {str(exc)}",
            }
    else:
        # No keywords: use collection.get(where=...) and sort by price
        try:
            results = collection.get(
                where=where,
                limit=fetch_k,
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
        except Exception as exc:
            logger.error("Chroma get failed: %s", exc)
            return {
                "count": 0,
                "total_matching": 0,
                "filters_applied": filters_applied,
                "cards": [],
                "message": f"Catalog lookup failed: {str(exc)}",
            }

    total_matching = len(candidates)

    if total_matching == 0:
        return {
            "count": 0,
            "total_matching": 0,
            "filters_applied": filters_applied,
            "cards": [],
            "message": _suggest_relaxation(params),
        }

    # Enrich candidates with checkability & build PartCards
    # Evaluate checkability using metadata & checker helper
    cards: List[Dict[str, Any]] = []
    for cand in candidates:
        meta = cand["metadata"]
        pid = cand["id"]

        # Infer name from document or metadata
        doc_text = cand.get("document", "")
        name = meta.get("name")
        if not name:
            # Extract first segment before comma
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
            wattage=part_dict.get("wattage"),
            length_mm=part_dict.get("length"),
            height_mm=part_dict.get("height"),
            cooler_kind=part_dict.get("cooler_kind"),
            in_stock=bool(part_dict.get("in_stock", True)),
            checkable=is_chk,
        ).model_dump()

        card["_distance"] = cand.get("distance", 0.0)
        cards.append(card)

    # Sort: checkable=True FIRST, then by distance (if keywords) or price (if no keywords)
    if keywords_clean:
        cards.sort(key=lambda c: (not c["checkable"], c.get("_distance", 0.0), c.get("price") or 999999))
    else:
        cards.sort(key=lambda c: (not c["checkable"], c.get("price") or 999999))

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
        "message": f"Found {len(final_cards)} matching {params.category} candidate(s).",
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
            "using the deterministic 8-rule Python checker. Never guesses."
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
        return {"error": f"Invalid arguments for tool '{name}': {str(exc)}"}

    # 2. Execute tool
    try:
        if name == "search_parts":
            return fn(validated_params, repo=repo, collection=collection)
        elif name in ("price_total", "check_compatibility"):
            return fn(validated_params, repo=repo)
        else:
            return fn(validated_params)
    except Exception as exc:
        logger.exception("Error executing tool '%s': %s", name, exc)
        return {"error": f"Execution of tool '{name}' failed: {str(exc)}"}


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Export tool definitions with JSON schemas for Day 10 LLM function calling
    (compatible with Gemini function declarations and Ollama tools).
    """
    defs = []
    for t_name, t_info in TOOLS.items():
        defs.append({
            "name": t_name,
            "description": t_info["description"],
            "parameters": t_info["input_model"].model_json_schema(),
        })
    return defs
