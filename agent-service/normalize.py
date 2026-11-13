"""
normalize.py - Normalize component specifications across seed and dataset formats

Translates varied field names (ramType vs ram_type, mATX vs Micro ATX, etc.)
and schema variations into a clean, uniform dictionary shape for compatibility checks.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Optional seed specs lookup for resolving string IDs / names in baseline builds
BASE_DIR = Path(__file__).resolve().parent
SEED_SPECS_PATH = BASE_DIR.parent / "backend" / "data" / "componentSpecs.json"

_SEED_SPECS_BY_ID = {}
_SEED_SPECS_BY_NAME = {}

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
    """Normalize motherboard and case form factor strings."""
    if not ff:
        return None
    clean = str(ff).strip()
    lower = clean.lower()
    if lower in ("matx", "micro atx", "microatx", "micro-atx"):
        return "Micro ATX"
    if lower in ("mitx", "mini itx", "minitx", "mini-itx"):
        return "Mini ITX"
    if lower in ("eatx", "extended atx", "extended-atx"):
        return "EATX"
    if lower in ("mini dtx", "dtx", "mini-dtx"):
        return "Mini DTX"
    if lower in ("atx", "standard atx"):
        return "ATX"
    return clean


def normalize_socket(sock: Optional[str]) -> Optional[str]:
    """Normalize CPU and Motherboard socket strings."""
    if not sock:
        return None
    s = str(sock).strip().upper()
    s = s.replace("SOCKET ", "").replace("SOCKET-", "")
    return s


def normalize_ram_type(rt: Optional[str], socket: Optional[str] = None) -> Optional[str]:
    """Normalize RAM generation (DDR4, DDR5, DDR4/DDR5)."""
    if rt:
        clean = str(rt).strip().upper()
        # Handle formats like "DDR4-3200", "DDR4 / DDR5", "DDR4/DDR5"
        if "/" in clean:
            types = [t.strip() for t in clean.split("/")]
            return "/".join(t for t in types if t.startswith("DDR"))
        m = re.search(r"(DDR[345])", clean)
        if m:
            return m.group(1)
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


def normalize_part(part: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """
    Normalize any component representation (dict from MongoDB, seed specs, or string identifier)
    into a standardized dictionary format.
    """
    raw: Dict[str, Any] = {}
    if isinstance(part, str):
        # Resolve string ID or name from seed specs if available
        key = part.strip().lower()
        found = _SEED_SPECS_BY_ID.get(key) or _SEED_SPECS_BY_NAME.get(key)
        if found:
            raw = dict(found)
        else:
            raw = {"_id": part, "name": part}
    elif isinstance(part, dict):
        raw = dict(part)
    else:
        return {}

    # Category
    cat = normalize_category(raw.get("category"))

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
        "raw": raw,
    }


def normalize_build(build: List[Any]) -> List[Dict[str, Any]]:
    """Normalize an entire build list of parts."""
    normalized = []
    for item in build:
        norm = normalize_part(item)
        if norm and norm.get("category"):
            normalized.append(norm)
    return normalized


def get_part_by_category(parts: List[Dict[str, Any]], category: str) -> Optional[Dict[str, Any]]:
    """Retrieve the first normalized part matching the target category."""
    target = normalize_category(category)
    for p in parts:
        if p.get("category") == target:
            return p
    return None
