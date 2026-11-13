"""
checker.py - Deterministic Code-Based Compatibility Checker (Day 7)

Evaluates PC builds against 8 physical, electrical, and budgetary compatibility rules:
1. all_categories: All 9 required component categories are present.
2. socket_match: CPU socket matches Motherboard socket.
3. ram_type_match: RAM generation (DDR4/DDR5) matches Motherboard and CPU.
4. psu_headroom: PSU wattage >= (CPU TDP + GPU TDP + 80W) * 1.4.
5. formfactor_fit: Motherboard form factor fits in Cabinet (handling EATX, Mini DTX, HTPC).
6. gpu_length: GPU length <= Case maximum GPU clearance.
7. cooler_height: Air cooler height <= Case maximum CPU cooler clearance.
8. within_budget: Total build price <= User budget.

Outcomes per rule:
- PASS: Physical / electrical / budgetary condition is strictly satisfied.
- FAIL: Definite physical / electrical / budgetary incompatibility detected.
- UNKNOWN: Data is missing or uncurated; NEVER guessed or treated as PASS.

Build verdicts:
- valid: True if NO rule returns FAIL.
- fully_verified: True if EVERY rule returns PASS (no FAIL and no UNKNOWN).
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from normalize import get_part_by_category, normalize_build, normalize_part

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

# Case / Cooler lookup helpers by ID or lowercase name
CASES_BY_NAME: Dict[str, Dict[str, Any]] = {}
for cid, cinfo in CASES_TABLE.items():
    if "name" in cinfo:
        CASES_BY_NAME[cinfo["name"].strip().lower()] = cinfo

COOLERS_BY_NAME: Dict[str, Dict[str, Any]] = {}
for clid, clinfo in COOLERS_TABLE.items():
    if "name" in clinfo:
        COOLERS_BY_NAME[clinfo["name"].strip().lower()] = clinfo

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


# ─── Rule 1: All 9 Categories Present ─────────────────────────────────────────
def check_all_categories(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Check that all 9 required component categories are present."""
    found_categories = {p.get("category") for p in parts if p.get("category")}
    missing = [cat for cat in REQUIRED_CATEGORIES if cat not in found_categories]

    if not missing:
        return "PASS", "All 9 required categories are present."
    return "FAIL", f"Missing required categories: {', '.join(missing)}."


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
    """Check that RAM type (DDR4/DDR5) matches what the motherboard and CPU support."""
    ram = get_part_by_category(parts, "ram")
    mobo = get_part_by_category(parts, "motherboard")
    cpu = get_part_by_category(parts, "processor")

    if not ram or not mobo:
        return "UNKNOWN", "RAM or Motherboard not present in build."

    ram_type = ram.get("ram_type")
    mobo_ram_type = mobo.get("ram_type")

    if not ram_type or not mobo_ram_type:
        return "UNKNOWN", "RAM type data missing from RAM or Motherboard specs."

    # Parse supported motherboard types (e.g., "DDR4", "DDR5", or "DDR4/DDR5")
    supported_mobo_types = [t.strip() for t in mobo_ram_type.split("/")]
    if ram_type not in supported_mobo_types:
        return "FAIL", f"RAM ({ram_type}) is not supported by Motherboard ({mobo_ram_type})."

    # Verify CPU memory controller support if present
    if cpu:
        cpu_ram_type = cpu.get("ram_type")
        if cpu_ram_type:
            cpu_supported = [t.strip() for t in cpu_ram_type.split("/")]
            if ram_type not in cpu_supported:
                return "FAIL", f"RAM ({ram_type}) is not supported by CPU memory controller ({cpu.get('name')}: {cpu_ram_type})."
        elif cpu.get("socket"):
            sock = cpu.get("socket")
            if sock in ("AM5", "LGA1851") and ram_type != "DDR5":
                return "FAIL", f"CPU socket {sock} strictly requires DDR5 RAM, got {ram_type}."
            if sock == "AM4" and ram_type != "DDR4":
                return "FAIL", f"CPU socket AM4 strictly requires DDR4 RAM, got {ram_type}."

    return "PASS", f"RAM ({ram_type}) is compatible with Motherboard ({mobo_ram_type}) and CPU."


# ─── Rule 4: PSU Wattage & Headroom ───────────────────────────────────────────
def check_psu_headroom(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Check PSU wattage >= (CPU TDP + GPU TDP + 80W overhead) * 1.4 safety margin.
    Uses curated GPU TDP table when GPU specification lacks raw TDP.
    """
    cpu = get_part_by_category(parts, "processor")
    gpu = get_part_by_category(parts, "gpu")
    psu = get_part_by_category(parts, "psu")

    if not cpu or not gpu or not psu:
        return "UNKNOWN", "CPU, GPU, or PSU not present in build."

    cpu_tdp = cpu.get("tdp")
    psu_wattage = psu.get("wattage")

    # Resolve GPU TDP (from part specs, or curated table by chipset / name)
    gpu_tdp = gpu.get("tdp")
    if gpu_tdp is None:
        chipset = gpu.get("chipset") or ""
        gname = gpu.get("name") or ""
        curated_info = (
            GPU_TDP_TABLE.get(chipset)
            or GPU_TDP_TABLE.get(gname)
            or GPU_TDP_TABLE.get(chipset.replace("GeForce ", "").replace("Radeon ", ""))
        )
        if not curated_info:
            for k, v in GPU_TDP_TABLE.items():
                if k.lower() in gname.lower() or k.lower() in chipset.lower():
                    curated_info = v
                    break
        if curated_info and "tdp_w" in curated_info:
            gpu_tdp = float(curated_info["tdp_w"])

    if cpu_tdp is None:
        return "UNKNOWN", "CPU TDP missing from specifications."
    if gpu_tdp is None:
        return "UNKNOWN", f"GPU TDP missing or uncurated for '{gpu.get('chipset') or gpu.get('name')}'."
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


# ─── Rule 5: Motherboard Form Factor Fits Cabinet ─────────────────────────────
def check_formfactor_fit(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Check that Motherboard form factor fits in the Cabinet.
    Handles catalogue quirks:
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
    if mobo_ff == "Mini DTX" or "HTPC" in case_type:
        return "UNKNOWN", f"Form factor compatibility between '{mobo_ff}' and '{case_type}' is unverified (niche form factor)."

    # Case clearance mapping
    case_type_lower = case_type.lower()

    if "full tower" in case_type_lower:
        allowed = ["EATX", "ATX", "Micro ATX", "Mini ITX"]
    elif "mid tower" in case_type_lower or case_type_lower == "atx desktop" or case_type_lower == "atx":
        allowed = ["ATX", "Micro ATX", "Mini ITX"]
    elif "microatx" in case_type_lower or "mini tower" in case_type_lower or "micro atx" in case_type_lower:
        allowed = ["Micro ATX", "Mini ITX"]
    elif "mini itx" in case_type_lower:
        allowed = ["Mini ITX"]
    else:
        return "UNKNOWN", f"Cabinet case type '{case_type}' not recognized in compatibility matrix."

    if mobo_ff in allowed:
        return "PASS", f"Motherboard ({mobo_ff}) fits in Cabinet ({case_type})."
    return "FAIL", f"Motherboard ({mobo_ff}) does NOT fit in Cabinet ({case_type})."


# ─── Rule 6: GPU Length vs Case Limit ─────────────────────────────────────────
def check_gpu_length(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Check that GPU card length <= Cabinet maximum GPU clearance limit."""
    gpu = get_part_by_category(parts, "gpu")
    cab = get_part_by_category(parts, "cabinet")

    if not gpu or not cab:
        return "UNKNOWN", "GPU or Cabinet not present in build."

    gpu_length = gpu.get("length")

    # Look up case limit from raw part or curated table
    case_limit = None
    raw_cab = cab.get("raw", {})
    if raw_cab.get("max_gpu_length_mm"):
        case_limit = float(raw_cab["max_gpu_length_mm"])
    elif raw_cab.get("max_gpu_length"):
        case_limit = float(raw_cab["max_gpu_length"])

    if case_limit is None:
        cab_id = cab.get("id")
        cab_name = (cab.get("name") or "").strip().lower()
        curated_case = CASES_TABLE.get(cab_id) or CASES_BY_NAME.get(cab_name)
        if not curated_case:
            for k, v in CASES_BY_NAME.items():
                if k in cab_name or cab_name in k:
                    curated_case = v
                    break
        if curated_case and "max_gpu_length_mm" in curated_case:
            case_limit = float(curated_case["max_gpu_length_mm"])

    if gpu_length is None:
        return "UNKNOWN", f"GPU length missing for '{gpu.get('name')}'."
    if case_limit is None:
        return "UNKNOWN", f"Case GPU clearance limit missing or uncurated for '{cab.get('name')}'."

    if gpu_length <= case_limit:
        return "PASS", f"GPU length ({int(gpu_length)} mm) <= Case maximum clearance ({int(case_limit)} mm)."
    return "FAIL", f"GPU length ({int(gpu_length)} mm) exceeds Case maximum clearance ({int(case_limit)} mm) by {int(gpu_length - case_limit)} mm!"


# ─── Rule 7: Cooler Height vs Case Limit ──────────────────────────────────────
def check_cooler_height(parts: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Check that air cooler height <= Cabinet maximum CPU cooler clearance limit.
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
        curated_cl = COOLERS_TABLE.get(cl_id) or COOLERS_BY_NAME.get(cl_name)
        if not curated_cl:
            for k, v in COOLERS_BY_NAME.items():
                if k in cl_name or cl_name in k:
                    curated_cl = v
                    break
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
        curated_case = CASES_TABLE.get(cab_id) or CASES_BY_NAME.get(cab_name)
        if not curated_case:
            for k, v in CASES_BY_NAME.items():
                if k in cab_name or cab_name in k:
                    curated_case = v
                    break
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
def check_within_budget(parts: List[Dict[str, Any]], budget: Optional[float] = None) -> Tuple[str, str]:
    """Check that total build price does not exceed the user's budget."""
    if budget is None:
        return "UNKNOWN", "No budget specified."

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
def check_build(build: List[Any], budget: Optional[float] = None) -> Dict[str, Any]:
    """
    Run all 8 deterministic compatibility rules on a build.

    Parameters:
        build: List of part dicts, raw MongoDB documents, or part ID strings.
        budget: Optional maximum spending threshold in INR.

    Returns:
        Dictionary containing:
        - rules: Dict mapping rule name to {verdict: "PASS"|"FAIL"|"UNKNOWN", message: str}
        - valid: bool (True if NO rule failed)
        - fully_verified: bool (True if all rules returned PASS)
        - fails: List of rule names that returned FAIL
        - unknowns: List of rule names that returned UNKNOWN
        - total_price: float or None
    """
    parts = normalize_build(build)

    rules: Dict[str, Dict[str, str]] = {}

    v1, m1 = check_all_categories(parts)
    rules["all_categories"] = {"verdict": v1, "message": m1}

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

    v8, m8 = check_within_budget(parts, budget=budget)
    rules["within_budget"] = {"verdict": v8, "message": m8}

    fails = [r for r, res in rules.items() if res["verdict"] == "FAIL"]
    unknowns = [r for r, res in rules.items() if res["verdict"] == "UNKNOWN"]

    total_price = sum(p["price"] for p in parts if p.get("price") is not None)

    return {
        "rules": rules,
        "valid": len(fails) == 0,
        "fully_verified": len(fails) == 0 and len(unknowns) == 0,
        "fails": fails,
        "unknowns": unknowns,
        "total_price": total_price,
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
    print(f"{'─'*70}")
    status = "VALID [OK]" if result["valid"] else "INVALID [X]"
    verified = "YES (All PASS)" if result["fully_verified"] else f"NO ({len(result['unknowns'])} UNKNOWN)"
    print(f"  VERDICT         : {status}")
    print(f"  FULLY VERIFIED  : {verified}")
    print(f"{'='*70}\n")
