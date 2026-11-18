"""
checker.py - Deterministic Code-Based Compatibility Checker (Day 7)

Evaluates PC builds against 9 physical, electrical, and budgetary compatibility rules:
1. all_categories: All 9 required component categories are present (UNKNOWN for partial builds).
1b. one_per_slot: At most one CPU, motherboard, PSU, case and CPU cooler.
2. socket_match: CPU socket matches Motherboard socket.
3. ram_type_match: EVERY RAM kit's generation (DDR4/DDR5) matches Motherboard and CPU.
4. psu_headroom: PSU wattage >= (CPU TDP + sum of all GPU TDPs + 80W) * 1.4.
5. formfactor_fit: Motherboard form factor fits in Cabinet (handling EATX, MicroATX Mid Tower, Mini DTX, HTPC).
6. gpu_length: EVERY GPU length <= Case maximum GPU clearance.
7. cooler_height: Air cooler height <= Case maximum CPU cooler clearance.
8. within_budget: Total build price <= User budget.

Outcomes per rule:
- PASS: Physical / electrical / budgetary condition is strictly satisfied.
- FAIL: Definite physical / electrical / budgetary incompatibility detected.
- UNKNOWN: Data is missing or uncurated; NEVER guessed or treated as PASS.

Build verdicts:
- valid: True if NO rule returns FAIL and NO unresolved part IDs exist.
- fully_verified: True if EVERY rule returns PASS (no FAIL, no UNKNOWN, no unresolved parts).
- checkable: Helper indicating if a part has sufficient specifications/curated data.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from normalize import get_part_by_category, get_parts_by_category, normalize_build, normalize_part

BASE_DIR = Path(__file__).resolve().parent
CURATED_DIR = BASE_DIR / "data" / "curated"

# ─── Load Curated Tables ───────────────────────────────────────────────────────
GPU_TDP_TABLE: Dict[str, Dict[str, Any]] = {}
CASES_TABLE: Dict[str, Dict[str, Any]] = {}
COOLERS_TABLE: Dict[str, Dict[str, Any]] = {}

gpu_tdp_path = CURATED_DIR / "gpu_tdp.json"
if gpu_tdp_path.exists():
    with open(gpu_tdp_path, "r", encoding="utf-8") as f:
        GPU_TDP_TABLE = json.load(f)

cases_path = CURATED_DIR / "cases.json"
if cases_path.exists():
    with open(cases_path, "r", encoding="utf-8") as f:
        CASES_TABLE = json.load(f)

coolers_path = CURATED_DIR / "coolers.json"
if coolers_path.exists():
    with open(coolers_path, "r", encoding="utf-8") as f:
        COOLERS_TABLE = json.load(f)

# Case / Cooler lookup helpers by exact lowercase name
CASES_BY_NAME: Dict[str, Dict[str, Any]] = {}
for cid, cinfo in CASES_TABLE.items():
    if "name" in cinfo:
        CASES_BY_NAME[cinfo["name"].strip().lower()] = cinfo

COOLERS_BY_NAME: Dict[str, Dict[str, Any]] = {}
for clid, clinfo in COOLERS_TABLE.items():
    if "name" in clinfo:
        COOLERS_BY_NAME[clinfo["name"].strip().lower()] = clinfo

# Explicit alias map for GPU chipsets (Issue 2: strictly no fuzzy substring fallback)
GPU_TDP_ALIASES: Dict[str, str] = {
    "rtx 4060": "GeForce RTX 4060",
    "rtx 4060 ti": "GeForce RTX 4060 Ti",
    "rtx 4070": "GeForce RTX 4070",
    "rtx 4070 super": "GeForce RTX 4070 SUPER",
    "rtx 4070 ti": "GeForce RTX 4070 Ti",
    "rtx 4070 ti super": "GeForce RTX 4070 Ti SUPER",
    "rtx 4080": "GeForce RTX 4080",
    "rtx 4080 super": "GeForce RTX 4080 SUPER",
    "rtx 4090": "GeForce RTX 4090",
    "rtx 5070": "GeForce RTX 5070",
    "rtx 5070 ti": "GeForce RTX 5070 Ti",
    "rtx 5080": "GeForce RTX 5080",
    "rtx 5090": "GeForce RTX 5090",
    "rtx 3050 6gb": "GeForce RTX 3050 6GB",
    "rtx 3050 8gb": "GeForce RTX 3050 8GB",
    "rtx 3060": "GeForce RTX 3060",
    "rtx 3060 12gb": "GeForce RTX 3060 12GB",
    "rtx 3060 8gb": "GeForce RTX 3060 8GB",
    "rtx 3060 ti": "GeForce RTX 3060 Ti",
    "rtx 3060 ti lhr": "GeForce RTX 3060 Ti LHR",
    "rtx 3070": "GeForce RTX 3070",
    "rtx 3070 lhr": "GeForce RTX 3070 LHR",
    "rtx 3070 ti": "GeForce RTX 3070 Ti",
    "rtx 3080 10gb": "GeForce RTX 3080 10GB",
    "rtx 3080 10gb lhr": "GeForce RTX 3080 10GB LHR",
    "rtx 3080 12gb lhr": "GeForce RTX 3080 12GB LHR",
    "rtx 3080 ti": "GeForce RTX 3080 Ti",
    "rtx 3090": "GeForce RTX 3090",
    "rtx 3090 ti": "GeForce RTX 3090 Ti",
    "gtx 1650": "GeForce GTX 1650 G5",
    "gtx 1650 super": "GeForce GTX 1650 SUPER",
    "gtx 1660": "GeForce GTX 1660",
    "gtx 1660 super": "GeForce GTX 1660 SUPER",
    "gtx 1660 ti": "GeForce GTX 1660 Ti",
    "rx 6600": "Radeon RX 6600",
    "rx 6600 xt": "Radeon RX 6600 XT",
    "rx 6650 xt": "Radeon RX 6650 XT",
    "rx 6700 xt": "Radeon RX 6700 XT",
    "rx 6750 xt": "Radeon RX 6750 XT",
    "rx 6800": "Radeon RX 6800",
    "rx 6800 xt": "Radeon RX 6800 XT",
    "rx 6900 xt": "Radeon RX 6900 XT",
    "rx 7600": "Radeon RX 7600",
    "rx 7600 xt": "Radeon RX 7600 XT",
    "rx 7700 xt": "Radeon RX 7700 XT",
    "rx 7800 xt": "Radeon RX 7800 XT",
    "rx 7900 gre": "Radeon RX 7900 GRE",
    "rx 7900 xt": "Radeon RX 7900 XT",
    "rx 7900 xtx": "Radeon RX 7900 XTX",
}

REQUIRED_CATEGORIES = [
    "processor",
    "motherboard",
    "gpu",
    "ram",
    "ps",
    "ss",
    "psu",
    "cabinet",
    "cooling",
]


# ─── Part Checkability Inspector (Issue 5) ────────────────────────────────────
def is_part_checkable(part: Dict[str, Any]) -> bool:
    """
    Check if a component has sufficient specifications/curated data to be fully verified
    without yielding UNKNOWN on any compatibility rule.
    Used by Day 8 search/agent tools to prefer parts with verified physical/TDP data.
    """
    cat = part.get("category")
    if not cat:
        return False

    if cat == "processor":
        return bool(part.get("socket") and part.get("tdp"))

    if cat == "motherboard":
        return bool(part.get("socket") and part.get("ram_type") and part.get("form_factor"))

    if cat == "ram":
        return bool(part.get("ram_type"))

    if cat == "psu":
        return bool(part.get("wattage"))

    if cat in ("ps", "ss"):
        return part.get("price") is not None

    if cat == "gpu":
        has_length = bool(part.get("length"))
        has_tdp = bool(part.get("tdp"))
        if not has_tdp:
            cs = (part.get("chipset") or "").strip()
            name = (part.get("name") or "").strip()
            cs_lower = cs.lower()
            name_lower = name.lower()
            canonical = GPU_TDP_ALIASES.get(cs_lower) or GPU_TDP_ALIASES.get(name_lower)
            has_tdp = bool(
                cs in GPU_TDP_TABLE
                or name in GPU_TDP_TABLE
                or (canonical and canonical in GPU_TDP_TABLE)
                or any(k.lower() == cs_lower or k.lower() == name_lower for k in GPU_TDP_TABLE)
            )
        return has_length and has_tdp

    if cat == "cabinet":
        ctype = part.get("case_type") or part.get("form_factor") or ""
        if "htpc" in ctype.lower() or not ctype:
            return False
        cid = part.get("id") or ""
        cname = (part.get("name") or "").strip().lower()
        return bool(
            part.get("raw", {}).get("max_gpu_length_mm")
            or cid in CASES_TABLE
            or cname in CASES_BY_NAME
        )

    if cat == "cooling":
        if part.get("cooler_kind") != "air":
            return False
        clid = part.get("id") or ""
        clname = (part.get("name") or "").strip().lower()
        return bool(
            part.get("height")
            or part.get("raw", {}).get("height_mm")
            or clid in COOLERS_TABLE
            or clname in COOLERS_BY_NAME
        )

    return False


# ─── Rule 1: All 9 Categories Present (Issue 3: Unresolved IDs) ───────────────
def check_all_categories(
    parts: List[Dict[str, Any]],
    unresolved: Optional[List[str]] = None,
    partial: bool = False,
) -> Tuple[str, str]:
    """
    Check that all 9 required component categories are present.
    If unknown/unresolved part identifiers were passed, report them clearly.

    partial=True is for an agent that is still building step by step: a missing
    category means "not chosen yet", so it is UNKNOWN rather than FAIL.
    Unresolved IDs are always a FAIL, partial or not.
    """
    found_categories = {p.get("category") for p in parts if p.get("category")}
    missing = [cat for cat in REQUIRED_CATEGORIES if cat not in found_categories]

    if not missing and not unresolved:
        return "PASS", "All 9 required categories are present."

    msg_parts = []
    if missing:
        msg_parts.append(f"Missing required categories: {', '.join(missing)}")
    if unresolved:
        msg_parts.append(f"Unresolved part identifiers: {', '.join(unresolved)}")
    if partial and not unresolved:
        return "UNKNOWN", "Partial build. " + ". ".join(msg_parts) + "."
    return "FAIL", ". ".join(msg_parts) + "."


# ─── At Most One Part per Single Slot ────────────────────────────────
# A PC has one CPU socket, one motherboard, one PSU, one case and one CPU cooler.
# RAM kits, GPUs and drives may legitimately appear more than once, so the
# rules below check EVERY RAM kit and EVERY GPU instead of only the first one.
SINGLE_SLOT_CATEGORIES = ["processor", "motherboard", "psu", "cabinet", "cooling"]


def check_one_per_slot(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """FAIL if a one-per-build category (e.g. two CPUs) appears more than once."""
    duplicated = [
        f"{cat} x{len(found)}"
        for cat in SINGLE_SLOT_CATEGORIES
        if len(found := get_parts_by_category(parts, cat)) > 1
    ]
    if duplicated:
        return "FAIL", f"A build can only hold one of each: {', '.join(duplicated)}."
    return "PASS", "At most one CPU, motherboard, PSU, case and CPU cooler."


# ─── Rule 2: CPU Socket Matches Motherboard Socket ────────────────────────────
def check_socket_match(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Check that CPU socket matches Motherboard socket."""
    cpu = get_part_by_category(parts, "processor")
    mobo = get_part_by_category(parts, "motherboard")

    if not cpu or not mobo:
        return "UNKNOWN", "CPU or Motherboard not present in build."

    cpu_socket = cpu.get("socket")
    mobo_socket = mobo.get("socket")

    if not cpu_socket or not mobo_socket:
        return "UNKNOWN", "Socket specification missing from CPU or Motherboard specs."

    if cpu_socket == mobo_socket:
        return "PASS", f"Both CPU and Motherboard use socket {cpu_socket}."
    return "FAIL", f"CPU socket ({cpu_socket}) does not match Motherboard socket ({mobo_socket})."


# ─── Rule 3: RAM Generation Matches Motherboard and CPU ───────────────────────
def check_ram_generation(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Check that EVERY RAM kit's type (DDR4/DDR5) matches what the motherboard and CPU support."""
    rams = get_parts_by_category(parts, "ram")
    mobo = get_part_by_category(parts, "motherboard")
    cpu = get_part_by_category(parts, "processor")

    if not rams or not mobo:
        return "UNKNOWN", "RAM or Motherboard not present in build."

    mobo_ram_type = mobo.get("ram_type")
    if not mobo_ram_type:
        return "UNKNOWN", "RAM type data missing from Motherboard specs."
    # Parse supported motherboard types (e.g., "DDR4", "DDR5", or "DDR4/DDR5")
    supported_mobo_types = [t.strip() for t in mobo_ram_type.split("/")]

    # A FAIL on any kit wins; otherwise a kit with missing data makes the rule UNKNOWN.
    missing_data = False
    for ram in rams:
        ram_type = ram.get("ram_type")
        if not ram_type:
            missing_data = True
            continue

        if ram_type not in supported_mobo_types:
            return "FAIL", f"RAM '{ram.get('name')}' ({ram_type}) is not supported by Motherboard ({mobo_ram_type})."

        # Verify CPU memory controller support if present
        if cpu:
            cpu_ram_type = cpu.get("ram_type")
            if cpu_ram_type:
                cpu_supported = [t.strip() for t in cpu_ram_type.split("/")]
                if ram_type not in cpu_supported:
                    return "FAIL", f"RAM '{ram.get('name')}' ({ram_type}) is not supported by CPU memory controller ({cpu.get('name')}: {cpu_ram_type})."
            elif cpu.get("socket"):
                sock = cpu.get("socket")
                if sock in ("AM5", "LGA1851") and ram_type != "DDR5":
                    return "FAIL", f"CPU socket {sock} strictly requires DDR5 RAM, got {ram_type}."
                if sock == "AM4" and ram_type != "DDR4":
                    return "FAIL", f"CPU socket AM4 strictly requires DDR4 RAM, got {ram_type}."

    if missing_data:
        return "UNKNOWN", "RAM type data missing from at least one RAM kit."
    kit_types = ", ".join(sorted({r["ram_type"] for r in rams}))
    return "PASS", f"RAM ({kit_types}, {len(rams)} kit(s)) is compatible with Motherboard ({mobo_ram_type}) and CPU."


# ─── Rule 4: PSU Wattage & Headroom (Issue 2: Strict Exact/Alias Lookup) ──────
def _resolve_gpu_tdp(gpu: Dict[str, Any]) -> Optional[float]:
    """GPU TDP from the part's own specs, else an exact/alias match in gpu_tdp.json, else None."""
    gpu_tdp = gpu.get("tdp")
    if gpu_tdp is not None:
        return float(gpu_tdp)

    chipset = (gpu.get("chipset") or "").strip()
    gname = (gpu.get("name") or "").strip()

    # 1. Exact match in table
    curated_info = GPU_TDP_TABLE.get(chipset) or GPU_TDP_TABLE.get(gname)

    # 2. Case-insensitive exact match or explicit alias table
    if not curated_info:
        cs_lower = chipset.lower()
        gn_lower = gname.lower()
        canonical = GPU_TDP_ALIASES.get(cs_lower) or GPU_TDP_ALIASES.get(gn_lower)
        if canonical and canonical in GPU_TDP_TABLE:
            curated_info = GPU_TDP_TABLE[canonical]
        else:
            for k, v in GPU_TDP_TABLE.items():
                if k.lower() == cs_lower or k.lower() == gn_lower:
                    curated_info = v
                    break

    # NOTE (Issue 2): Strict exact/alias resolution only! Substring fallback completely removed.
    if curated_info and "tdp_w" in curated_info:
        return float(curated_info["tdp_w"])
    return None


def check_psu_headroom(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Check PSU wattage >= (CPU TDP + GPU TDP + 80W overhead) * 1.4 safety margin.
    Uses exact key or explicit alias matching in GPU_TDP_TABLE (no fuzzy substring matching).
    """
    cpu = get_part_by_category(parts, "processor")
    gpus = get_parts_by_category(parts, "gpu")
    psu = get_part_by_category(parts, "psu")

    if not cpu or not gpus or not psu:
        return "UNKNOWN", "CPU, GPU, or PSU not present in build."

    cpu_tdp = cpu.get("tdp")
    psu_wattage = psu.get("wattage")

    if cpu_tdp is None:
        return "UNKNOWN", "CPU TDP missing from specifications."

    # Every GPU draws power at the same time, so their TDPs add up.
    gpu_tdp = 0.0
    for gpu in gpus:
        one_tdp = _resolve_gpu_tdp(gpu)
        if one_tdp is None:
            return "UNKNOWN", f"GPU TDP missing or uncurated for '{gpu.get('chipset') or gpu.get('name')}'."
        gpu_tdp += one_tdp

    if psu_wattage is None:
        return "UNKNOWN", "PSU wattage missing from specifications."

    required_watts = math.ceil((cpu_tdp + gpu_tdp + 80) * 1.4)

    if psu_wattage >= required_watts:
        return (
            "PASS",
            f"PSU wattage ({int(psu_wattage)}W) satisfies required headroom "
            f"({required_watts}W for CPU {int(cpu_tdp)}W + GPU {int(gpu_tdp)}W + 80W overhead * 1.4).",
        )
    return (
        "FAIL",
        f"PSU wattage ({int(psu_wattage)}W) is insufficient! "
        f"Required: {required_watts}W (CPU {int(cpu_tdp)}W + GPU {int(gpu_tdp)}W + 80W overhead * 1.4). "
        f"Underpowered by {required_watts - int(psu_wattage)}W.",
    )


# ─── Rule 5: Motherboard Form Factor Fits Cabinet (Issue 1: Test Micro First) ─
def check_formfactor_fit(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Check that Motherboard form factor fits in the Cabinet.
    Handles catalogue quirks:
    - MicroATX Mid Tower cases tested BEFORE standard Mid Tower (rejects ATX).
    - EATX boards require Full Tower case.
    - Mini DTX boards and HTPC cases return UNKNOWN.
    """
    mobo = get_part_by_category(parts, "motherboard")
    cab = get_part_by_category(parts, "cabinet")

    if not mobo or not cab:
        return "UNKNOWN", "Motherboard or Cabinet not present in build."

    mobo_ff = mobo.get("form_factor")
    case_type = cab.get("case_type") or cab.get("form_factor") or ""

    if not mobo_ff or not case_type:
        return "UNKNOWN", "Form factor data missing from Motherboard or Cabinet specs."

    # Catalogue quirks: Mini DTX and HTPC return UNKNOWN (niche formats)
    if mobo_ff == "Mini DTX" or "htpc" in case_type.lower():
        return "UNKNOWN", f"Form factor compatibility between '{mobo_ff}' and '{case_type}' is unverified (specialized/niche form factor)."

    case_type_lower = case_type.lower()

    # Issue 1 Fix: Test the most specific and restrictive form factors FIRST!
    # Specifically, check Mini ITX and MicroATX before generic Full/Mid Tower strings!
    if "mini itx" in case_type_lower or case_type_lower == "mini itx":
        allowed = ["Mini ITX"]
    elif "microatx" in case_type_lower or "micro atx" in case_type_lower or "mini tower" in case_type_lower:
        # MicroATX cases (including "MicroATX Mid Tower", "MicroATX Mini Tower", "MicroATX Desktop")
        # only accept Micro ATX and Mini ITX boards - NEVER full ATX or EATX!
        allowed = ["Micro ATX", "Mini ITX"]
    elif "full tower" in case_type_lower:
        allowed = ["EATX", "ATX", "Micro ATX", "Mini ITX"]
    elif "mid tower" in case_type_lower or case_type_lower == "atx desktop" or case_type_lower == "atx":
        # Standard ATX Mid Tower / ATX Desktop cases fit ATX, Micro ATX, and Mini ITX (NOT EATX)
        allowed = ["ATX", "Micro ATX", "Mini ITX"]
    else:
        return "UNKNOWN", f"Cabinet case type '{case_type}' not recognized in compatibility matrix."

    if mobo_ff in allowed:
        return "PASS", f"Motherboard ({mobo_ff}) fits in Cabinet ({case_type})."
    return "FAIL", f"Motherboard ({mobo_ff}) does NOT fit in Cabinet ({case_type})."


# ─── Rule 6: GPU Length vs Case Limit (Issue 4: Exact Match Only) ──────────────
def check_gpu_length(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Check that GPU card length <= Cabinet maximum GPU clearance limit.
    Matches exact case ID or exact name only (no fuzzy substring matching).
    """
    gpus = get_parts_by_category(parts, "gpu")
    cab = get_part_by_category(parts, "cabinet")

    if not gpus or not cab:
        return "UNKNOWN", "GPU or Cabinet not present in build."

    # Look up case limit from raw part or curated table (exact ID or exact name only)
    case_limit = None
    raw_cab = cab.get("raw", {})
    if raw_cab.get("max_gpu_length_mm"):
        case_limit = float(raw_cab["max_gpu_length_mm"])
    elif raw_cab.get("max_gpu_length"):
        case_limit = float(raw_cab["max_gpu_length"])

    if case_limit is None:
        cab_id = cab.get("id")
        cab_name = (cab.get("name") or "").strip().lower()
        # Issue 4: Match exact ID or exact lowercase name ONLY!
        curated_case = CASES_TABLE.get(cab_id) or CASES_BY_NAME.get(cab_name)
        if curated_case and "max_gpu_length_mm" in curated_case:
            case_limit = float(curated_case["max_gpu_length_mm"])

    if case_limit is None:
        return "UNKNOWN", f"Case GPU clearance limit missing or uncurated for '{cab.get('name')}'."

    # Every GPU has to fit. A FAIL on any card wins; a card with no length makes it UNKNOWN.
    missing_length = None
    for gpu in gpus:
        gpu_length = gpu.get("length")
        if gpu_length is None:
            missing_length = missing_length or gpu.get("name")
            continue
        if gpu_length > case_limit:
            return "FAIL", (
                f"GPU '{gpu.get('name')}' length ({int(gpu_length)} mm) exceeds Case maximum clearance "
                f"({int(case_limit)} mm) by {int(gpu_length - case_limit)} mm!"
            )

    if missing_length is not None:
        return "UNKNOWN", f"GPU length missing for '{missing_length}'."
    longest = max(float(g["length"]) for g in gpus)
    return "PASS", f"GPU length ({int(longest)} mm) <= Case maximum clearance ({int(case_limit)} mm)."


# ─── Rule 7: Cooler Height vs Case Limit (Issue 4: Exact Match Only) ───────────
def check_cooler_height(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Check that air cooler height <= Cabinet maximum CPU cooler clearance limit.
    Matches exact cooler/case ID or exact name only (no fuzzy substring matching).
    Liquid (AIO) coolers return UNKNOWN because radiator mounting clearance is distinct.
    """
    cooler = get_part_by_category(parts, "cooling")
    cab = get_part_by_category(parts, "cabinet")

    if not cooler or not cab:
        return "UNKNOWN", "Cooler or Cabinet not present in build."

    # Liquid coolers return UNKNOWN (radiator mounting cannot be judged by air cooler height)
    if cooler.get("cooler_kind") == "liquid":
        return "UNKNOWN", "Liquid (AIO) cooler radiator clearance requires chassis radiator mounting curation."

    cooler_height = cooler.get("height")
    if cooler_height is None:
        cl_id = cooler.get("id")
        cl_name = (cooler.get("name") or "").strip().lower()
        # Issue 4: Match exact ID or exact lowercase name ONLY!
        curated_cl = COOLERS_TABLE.get(cl_id) or COOLERS_BY_NAME.get(cl_name)
        if curated_cl and "height_mm" in curated_cl:
            cooler_height = float(curated_cl["height_mm"])

    case_limit = None
    raw_cab = cab.get("raw", {})
    if raw_cab.get("max_cooler_height_mm"):
        case_limit = float(raw_cab["max_cooler_height_mm"])
    elif raw_cab.get("max_cooler_height"):
        case_limit = float(raw_cab["max_cooler_height"])

    if case_limit is None:
        cab_id = cab.get("id")
        cab_name = (cab.get("name") or "").strip().lower()
        # Issue 4: Match exact ID or exact lowercase name ONLY!
        curated_case = CASES_TABLE.get(cab_id) or CASES_BY_NAME.get(cab_name)
        if curated_case and "max_cooler_height_mm" in curated_case:
            case_limit = float(curated_case["max_cooler_height_mm"])

    if cooler_height is None:
        return "UNKNOWN", f"Air cooler height missing or uncurated for '{cooler.get('name')}'."
    if case_limit is None:
        return "UNKNOWN", f"Case CPU cooler clearance limit missing or uncurated for '{cab.get('name')}'."

    if cooler_height <= case_limit:
        return "PASS", f"Air cooler height ({int(cooler_height)} mm) <= Case maximum clearance ({int(case_limit)} mm)."
    return "FAIL", f"Air cooler height ({int(cooler_height)} mm) exceeds Case maximum clearance ({int(case_limit)} mm) by {int(cooler_height - case_limit)} mm!"


# ─── Rule 8: Within Budget ────────────────────────────────────────────────────
def compute_total_price(parts: List[Dict[str, Any]], unresolved: Optional[List[str]] = None) -> Optional[float]:
    """Sum of part prices, or None when any price is unknown (unresolved part or missing price)."""
    if unresolved:
        return None
    if any(p.get("price") is None for p in parts):
        return None
    return float(sum(float(p["price"]) for p in parts))


def check_within_budget(
    parts: List[Dict[str, Any]],
    budget: Optional[float] = None,
    unresolved: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """Check that total build price does not exceed the user's budget."""
    if budget is None:
        return "UNKNOWN", "No budget specified."

    # A part we could not find has an unknown price, so the total is unknown too.
    if unresolved:
        return "UNKNOWN", f"Unresolved part(s) {', '.join(unresolved)} have no known price. Cannot compute total."

    total = 0.0
    for p in parts:
        price = p.get("price")
        if price is None:
            return "UNKNOWN", f"Part '{p.get('name')}' missing price specification. Cannot compute total."
        total += float(price)

    if total <= budget:
        return "PASS", f"Total price (₹{int(total):,}) <= Budget (₹{int(budget):,})."
    return "FAIL", f"Total price (₹{int(total):,}) > Budget (₹{int(budget):,}). Over budget by ₹{int(total - budget):,}."


# ─── Master Compatibility Evaluator ───────────────────────────────────────────
def check_build(
    build: List[Any],
    budget: Optional[float] = None,
    part_lookup: Optional[Dict[str, Any]] = None,
    partial: bool = False,
) -> Dict[str, Any]:
    """
    Run all 9 deterministic compatibility rules on a build.

    Parameters:
        build: List of part dicts, raw MongoDB documents, or part ID strings.
        budget: Optional maximum spending threshold in INR.
        part_lookup: Optional dictionary mapping part IDs to documents (for resolving non-seed IDs).
        partial: True while the build is still being assembled; missing categories
                 become UNKNOWN instead of FAIL, so `valid` can be True mid-build.

    Returns:
        Dictionary containing:
        - rules: Dict mapping rule name to {verdict: "PASS"|"FAIL"|"UNKNOWN", message: str}
        - valid: bool (True if NO rule failed and NO unresolved part IDs exist)
        - fully_verified: bool (True if all rules returned PASS and NO unresolved parts exist)
        - fails: List of rule names that returned FAIL
        - unknowns: List of rule names that returned UNKNOWN
        - unresolved: List of string identifiers that could not be resolved (Issue 3)
        - total_price: float, or None when any part's price is unknown
        - checkable_parts: List of part names that have full physical/electrical data (Issue 5)
        - uncheckable_parts: List of part names that yield UNKNOWN due to missing data (Issue 5)
    """
    parts, unresolved = normalize_build(build, part_lookup=part_lookup)

    rules: Dict[str, Dict[str, str]] = {}

    v1, m1 = check_all_categories(parts, unresolved=unresolved, partial=partial)
    rules["all_categories"] = {"verdict": v1, "message": m1}

    v1b, m1b = check_one_per_slot(parts)
    rules["one_per_slot"] = {"verdict": v1b, "message": m1b}

    v2, m2 = check_socket_match(parts)
    rules["socket_match"] = {"verdict": v2, "message": m2}

    v3, m3 = check_ram_generation(parts)
    rules["ram_type_match"] = {"verdict": v3, "message": m3}

    v4, m4 = check_psu_headroom(parts)
    rules["psu_headroom"] = {"verdict": v4, "message": m4}

    v5, m5 = check_formfactor_fit(parts)
    rules["formfactor_fit"] = {"verdict": v5, "message": m5}

    v6, m6 = check_gpu_length(parts)
    rules["gpu_length"] = {"verdict": v6, "message": m6}

    v7, m7 = check_cooler_height(parts)
    rules["cooler_height"] = {"verdict": v7, "message": m7}

    v8, m8 = check_within_budget(parts, budget=budget, unresolved=unresolved)
    rules["within_budget"] = {"verdict": v8, "message": m8}

    fails = [r for r, res in rules.items() if res["verdict"] == "FAIL"]
    unknowns = [r for r, res in rules.items() if res["verdict"] == "UNKNOWN"]

    total_price = compute_total_price(parts, unresolved=unresolved)

    # Attach checkability status for Day 8 tools
    checkable_parts = []
    uncheckable_parts = []
    for p in parts:
        p["checkable"] = is_part_checkable(p)
        if p["checkable"]:
            checkable_parts.append(p.get("name", p.get("id")))
        else:
            uncheckable_parts.append(p.get("name", p.get("id")))

    # A build is valid only if nothing fails AND no unknown/unresolvable part IDs exist
    is_valid = len(fails) == 0 and len(unresolved) == 0
    is_fully_verified = len(fails) == 0 and len(unknowns) == 0 and len(unresolved) == 0

    return {
        "rules": rules,
        "valid": is_valid,
        "fully_verified": is_fully_verified,
        "fails": fails,
        "unknowns": unknowns,
        "unresolved": unresolved,
        "total_price": total_price,
        "checkable_parts": checkable_parts,
        "uncheckable_parts": uncheckable_parts,
    }


def print_check_summary(label: str, result: Dict[str, Any]) -> None:
    """Pretty print build check results."""
    print(f"\n{'='*70}")
    print(f"  BUILD CHECK: {label}")
    print(f"{'='*70}")
    for rname, rres in result["rules"].items():
        v = rres["verdict"]
        icon = "[PASS]" if v == "PASS" else ("[FAIL]" if v == "FAIL" else "[?]")
        print(f"  {icon} {rname:<18}: {v:<7} — {rres['message']}")
    if result.get("unresolved"):
        print(f"  [X] Unresolved IDs    : {', '.join(result['unresolved'])}")
    print(f"{'─'*70}")
    status = "VALID [OK]" if result["valid"] else "INVALID [X]"
    verified = "YES (All PASS)" if result["fully_verified"] else f"NO ({len(result['unknowns'])} UNKNOWN)"
    print(f"  VERDICT         : {status}")
    print(f"  FULLY VERIFIED  : {verified}")
    print(f"  CHECKABLE PARTS : {len(result['checkable_parts'])} / {len(result['checkable_parts']) + len(result['uncheckable_parts'])}")
    print(f"{'='*70}\n")
