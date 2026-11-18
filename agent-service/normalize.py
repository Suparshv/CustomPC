"""
normalize.py - Normalize component specifications across seed and dataset formats

Translates varied field names (ramType vs ram_type, mATX vs Micro ATX, etc.)
and schema variations into a clean, uniform dictionary shape for compatibility checks.
Tracks unresolvable string IDs in an unresolved list rather than silently dropping them.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Optional seed specs lookup for resolving string IDs / names in baseline builds
BASE_DIR = Path(__file__).resolve().parent
SEED_SPECS_PATH = BASE_DIR.parent / "backend" / "data" / "componentSpecs.json"

_SEED_SPECS_BY_ID: Dict[str, Dict[str, Any]] = {}
_SEED_SPECS_BY_NAME: Dict[str, Dict[str, Any]] = {}

if SEED_SPECS_PATH.exists():
    try:
        with open(SEED_SPECS_PATH, "r", encoding="utf-8") as f:
            specs = json.load(f)
            for k, v in specs.items():
                item = dict(v)
                item["_id"] = k.strip()
                _SEED_SPECS_BY_ID[k.strip().lower()] = item
                if "name" in item:
                    _SEED_SPECS_BY_NAME[item["name"].strip().lower()] = item
    except Exception:
        pass


CATEGORY_MAP = {
    "cpu": "processor",
    "processor": "processor",
    "motherboard": "motherboard",
    "mobo": "motherboard",
    "gpu": "gpu",
    "video_card": "gpu",
    "videocard": "gpu",
    "ram": "ram",
    "memory": "ram",
    "ps": "ps",
    "ssd": "ps",
    "primary_storage": "ps",
    "ss": "ss",
    "hdd": "ss",
    "secondary_storage": "ss",
    "psu": "psu",
    "power_supply": "psu",
    "cabinet": "cabinet",
    "case": "cabinet",
    "cooling": "cooling",
    "cooler": "cooling",
}


def normalize_category(cat: Optional[str]) -> Optional[str]:
    """Map category alias to canonical 9 category names."""
    if not cat:
        return None
    c = str(cat).strip().lower()
    return CATEGORY_MAP.get(c, c)


def normalize_form_factor(ff: Optional[str]) -> Optional[str]:
    """Normalize motherboard and case form factor strings, handling spelling variants."""
    if not ff:
        return None
    clean = str(ff).strip()
    lower = re.sub(r"[\s\-_]+", " ", clean.lower()).strip()
    if lower in ("matx", "m atx", "micro atx", "microatx", "u atx", "uatx", "µ atx", "µatx"):
        return "Micro ATX"
    if lower in ("mitx", "m itx", "mini itx", "minitx"):
        return "Mini ITX"
    if lower in ("eatx", "e atx", "extended atx"):
        return "EATX"
    if lower in ("mini dtx", "m dtx", "dtx"):
        return "Mini DTX"
    if lower in ("atx", "standard atx"):
        return "ATX"
    return clean


def normalize_socket(sock: Optional[str]) -> Optional[str]:
    """Normalize CPU and Motherboard socket strings, handling spelling variants."""
    if not sock:
        return None
    s = str(sock).strip().upper()
    s = re.sub(r"^SOCKET[\s\-]*", "", s).strip()

    # Match AM4, AM5, AM3 (including "AM 5", "AM-5")
    m_am = re.search(r"\bAM[\s\-]*([345])\b", s)
    if m_am:
        return f"AM{m_am.group(1)}"

    # Match LGA 1700, LGA 1851, LGA 1200, LGA 1151 (including "LGA 1700", "LGA-1700")
    m_lga = re.search(r"\bLGA[\s\-]*(\d+)\b", s)
    if m_lga:
        return f"LGA{m_lga.group(1)}"

    # Match raw socket numbers
    if s in ("1700", "1851", "1200", "1151"):
        return f"LGA{s}"

    # Remove internal whitespace (e.g. "LGA 1700" fallback)
    return re.sub(r"\s+", "", s)


def normalize_ram_type(rt: Optional[str], socket: Optional[str] = None) -> Optional[str]:
    """Normalize RAM generation (DDR4, DDR5, DDR4/DDR5), handling spelling variants like DDR 5, 5."""
    if rt:
        clean = str(rt).strip().upper()
        # Handle single digit strings "4" -> DDR4, "5" -> DDR5
        if clean in ("5", "DDR 5", "DDR-5"):
            return "DDR5"
        if clean in ("4", "DDR 4", "DDR-4"):
            return "DDR4"
        if "/" in clean:
            types = [t.strip() for t in clean.split("/")]
            return "/".join(normalize_ram_type(t) or t for t in types)
        m = re.search(r"DDR[\s\-]*([345])", clean)
        if m:
            return f"DDR{m.group(1)}"
        return clean

    # Fallback to deriving from socket when missing
    if socket:
        sock_clean = normalize_socket(socket)
        if sock_clean in ("AM5", "LGA1851"):
            return "DDR5"
        if sock_clean == "AM4":
            return "DDR4"
        if sock_clean == "LGA1700":
            return "DDR4/DDR5"

    return None


def normalize_part(
    part: Union[Dict[str, Any], str],
    part_lookup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Normalize any component representation (dict from MongoDB, seed specs, or string identifier)
    into a standardized dictionary format.
    Unresolved string IDs are flagged with 'unresolved': True.
    """
    raw: Dict[str, Any] = {}
    is_unresolved = False

    if isinstance(part, str):
        key = part.strip().lower()
        found = None
        if part_lookup and part in part_lookup:
            found = part_lookup[part]
        elif part_lookup and key in part_lookup:
            found = part_lookup[key]
        else:
            found = _SEED_SPECS_BY_ID.get(key) or _SEED_SPECS_BY_NAME.get(key)

        if found:
            raw = dict(found)
        else:
            raw = {"_id": part, "name": part}
            is_unresolved = True
    elif isinstance(part, dict):
        raw = dict(part)
        if not raw.get("category"):
            is_unresolved = True
    else:
        return {"id": str(part), "name": str(part), "category": None, "unresolved": True, "raw": {}}

    # Category
    cat = normalize_category(raw.get("category"))
    if not cat:
        is_unresolved = True

    # Name and ID
    name = raw.get("name") or raw.get("_id") or "Unknown Part"
    part_id = raw.get("_id") or raw.get("id") or str(name)

    # Price
    price = raw.get("price_inr")
    if price is None:
        price = raw.get("price")
    try:
        price_val = float(price) if price is not None else None
    except (ValueError, TypeError):
        price_val = None

    # Socket
    socket = normalize_socket(raw.get("socket"))

    # RAM Type
    ram_raw = raw.get("ram_type") or raw.get("ramType")
    ram_type = normalize_ram_type(ram_raw, socket=socket if cat == "processor" else None)

    # Form Factor
    ff_raw = raw.get("form_factor") or raw.get("formFactor")
    form_factor = normalize_form_factor(ff_raw)

    # TDP / Wattage
    tdp = raw.get("tdp")
    try:
        tdp_val = float(tdp) if tdp is not None else None
    except (ValueError, TypeError):
        tdp_val = None

    wattage = raw.get("wattage")
    try:
        wattage_val = float(wattage) if wattage is not None else None
    except (ValueError, TypeError):
        wattage_val = None

    # Length (GPU)
    length = raw.get("length")
    try:
        length_val = float(length) if length is not None else None
    except (ValueError, TypeError):
        length_val = None

    # Height (Cooler)
    height = raw.get("height_mm") or raw.get("height")
    try:
        height_val = float(height) if height is not None else None
    except (ValueError, TypeError):
        height_val = None

    # Case Type
    case_type = raw.get("case_type") or raw.get("type")

    # Cooler Kind
    cooler_kind = raw.get("cooler_kind")
    if not cooler_kind and cat == "cooling":
        ctype = str(raw.get("type", "")).lower()
        cname = str(name).lower()
        if raw.get("size") is not None or "aio" in ctype or "liquid" in ctype or "aio" in cname or "liquid" in cname:
            cooler_kind = "liquid"
        else:
            cooler_kind = "air"

    # Chipset
    chipset = raw.get("chipset")

    return {
        "id": str(part_id),
        "name": str(name),
        "category": cat,
        "price": price_val,
        "socket": socket,
        "ram_type": ram_type,
        "form_factor": form_factor,
        "tdp": tdp_val,
        "wattage": wattage_val,
        "length": length_val,
        "height": height_val,
        "case_type": str(case_type) if case_type else None,
        "cooler_kind": cooler_kind,
        "chipset": str(chipset) if chipset else None,
        "unresolved": is_unresolved,
        "raw": raw,
    }


def normalize_build(
    build: List[Any],
    part_lookup: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Normalize an entire build list of parts.
    Returns:
        (normalized_parts, unresolved_identifiers)
    """
    normalized = []
    unresolved = []

    for item in build:
        norm = normalize_part(item, part_lookup=part_lookup)
        if norm.get("unresolved") or not norm.get("category"):
            identifier = norm.get("id") or norm.get("name") or str(item)
            unresolved.append(str(identifier))
        else:
            normalized.append(norm)

    return normalized, unresolved


def get_part_by_category(parts: List[Dict[str, Any]], category: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the first normalized part matching the target category.

    Only safe for one-per-build slots (CPU, motherboard, PSU, case, CPU cooler);
    the checker's `one_per_slot` rule FAILs builds that contain two of those.
    For RAM and GPUs use get_parts_by_category, because a build can hold several.
    """
    target = normalize_category(category)
    for p in parts:
        if p.get("category") == target:
            return p
    return None


def get_parts_by_category(parts: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """Retrieve EVERY normalized part matching the target category."""
    target = normalize_category(category)
    return [p for p in parts if p.get("category") == target]
