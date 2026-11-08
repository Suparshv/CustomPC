"""
compat.py - The "Judge" for PC Build Compatibility

This script loads componentSpecs.json and validates a given build
against 6 hardware compatibility rules. Each rule returns:
  PASS   - The rule is satisfied.
  FAIL   - The rule is violated.
  UNKNOWN - Not enough data to check (never guesses).

Usage:
  python compat.py
"""

import json
import os
import sys
import math

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError with symbols/emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# ─── Load the component database ──────────────────────────────────────────────
SPECS_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "componentSpecs.json")

with open(SPECS_PATH, "r", encoding="utf-8") as f:
    ALL_SPECS = json.load(f)

# Build lookups: by name (lowercase) and by ID
SPEC_BY_NAME = {}
SPEC_BY_ID = {}
for key, spec in ALL_SPECS.items():
    SPEC_BY_ID[key.strip().lower()] = spec
    SPEC_BY_NAME[spec["name"].strip().lower()] = spec

# The 9 required categories for a full build
REQUIRED_CATEGORIES = ["processor", "motherboard", "gpu", "ram", "ps", "ss", "psu", "cabinet", "cooling"]


def find_spec(part_identifier):
    """
    Find the spec object for a given part name or part ID (case-insensitive).
    """
    if not part_identifier or not isinstance(part_identifier, str):
        return None
    key = part_identifier.strip().lower()
    return SPEC_BY_NAME.get(key) or SPEC_BY_ID.get(key)


def find_part_in_build(build, category):
    """Find a part in the build list by its category."""
    for part in build:
        spec = find_spec(part)
        if spec and spec.get("category") == category:
            return spec
    return None


# ─── Rule 1: All 9 categories present ────────────────────────────────────────
def rule_all_categories_present(build):
    """Check that all 9 required categories are present in the build."""
    found_categories = set()
    for part in build:
        spec = find_spec(part)
        if spec:
            found_categories.add(spec["category"])

    missing = [cat for cat in REQUIRED_CATEGORIES if cat not in found_categories]

    if len(missing) == 0:
        return "PASS", "All 9 categories present."
    else:
        return "FAIL", f"Missing categories: {', '.join(missing)}"


# ─── Rule 2: CPU socket matches motherboard socket ───────────────────────────
def rule_socket_match(build):
    """Check that the CPU socket matches the motherboard socket."""
    cpu = find_part_in_build(build, "processor")
    mobo = find_part_in_build(build, "motherboard")

    if not cpu or not mobo:
        return "UNKNOWN", "CPU or Motherboard not found in build."

    cpu_socket = cpu.get("socket")
    mobo_socket = mobo.get("socket")

    if not cpu_socket or not mobo_socket:
        return "UNKNOWN", "Socket data missing from specs."

    if cpu_socket == mobo_socket:
        return "PASS", f"Both use {cpu_socket}."
    else:
        return "FAIL", f"CPU socket ({cpu_socket}) != Motherboard socket ({mobo_socket})."


# ─── Rule 3: RAM type matches motherboard and CPU ────────────────────────────
def rule_ram_type_match(build):
    """Check that the RAM type (DDR4/DDR5) matches what the motherboard and CPU support."""
    ram = find_part_in_build(build, "ram")
    mobo = find_part_in_build(build, "motherboard")
    cpu = find_part_in_build(build, "processor")

    if not ram or not mobo:
        return "UNKNOWN", "RAM or Motherboard not found in build."

    ram_type = ram.get("ramType")
    mobo_ram_type = mobo.get("ramType")

    if not ram_type or not mobo_ram_type:
        return "UNKNOWN", "RAM type data missing from specs."

    # Handle mobos that support dual/split (e.g., "DDR4/DDR5")
    supported_mobo_types = [t.strip() for t in mobo_ram_type.split("/")]
    if ram_type not in supported_mobo_types:
        return "FAIL", f"RAM ({ram_type}) is NOT supported by Motherboard ({mobo_ram_type})."

    # Also verify CPU memory controller support if present
    if cpu and cpu.get("ramType"):
        cpu_supported = [t.strip() for t in cpu["ramType"].split("/")]
        if ram_type not in cpu_supported:
            return "FAIL", f"RAM ({ram_type}) is NOT supported by CPU ({cpu.get('name')}: {cpu['ramType']})."

    return "PASS", f"RAM ({ram_type}) is supported by Motherboard ({mobo_ram_type})."


# ─── Rule 4: PSU wattage is sufficient ───────────────────────────────────────
def rule_psu_sufficient(build):
    """
    Check that PSU wattage >= (CPU TDP + GPU TDP + 80W overhead) * 1.4 safety margin.
    """
    cpu = find_part_in_build(build, "processor")
    gpu = find_part_in_build(build, "gpu")
    psu = find_part_in_build(build, "psu")

    if not cpu or not gpu or not psu:
        return "UNKNOWN", "CPU, GPU, or PSU not found in build."

    cpu_tdp = cpu.get("tdp")
    gpu_tdp = gpu.get("tdp")
    psu_wattage = psu.get("wattage")

    if cpu_tdp is None or gpu_tdp is None or psu_wattage is None:
        return "UNKNOWN", "TDP or wattage data missing from specs."

    required_watts = math.ceil((cpu_tdp + gpu_tdp + 80) * 1.4)

    if psu_wattage >= required_watts:
        return "PASS", f"PSU ({psu_wattage}W) >= required ({required_watts}W)."
    else:
        return "FAIL", f"PSU ({psu_wattage}W) < required ({required_watts}W). Underpowered!"


# ─── Rule 5: Motherboard form factor fits the cabinet ────────────────────────
def rule_formfactor_fit(build):
    """
    Check that the motherboard form factor fits inside the cabinet.
    ATX case fits: ATX, mATX, mITX.
    mATX case fits: mATX, mITX.
    mITX case fits: mITX only.
    """
    mobo = find_part_in_build(build, "motherboard")
    cab = find_part_in_build(build, "cabinet")

    if not mobo or not cab:
        return "UNKNOWN", "Motherboard or Cabinet not found in build."

    mobo_ff = mobo.get("formFactor")
    cab_ff = cab.get("formFactor")

    if not mobo_ff or not cab_ff:
        return "UNKNOWN", "Form factor data missing from specs."

    compatibility = {
        "ATX": ["ATX", "mATX", "mITX"],
        "mATX": ["mATX", "mITX"],
        "mITX": ["mITX"],
    }

    allowed = compatibility.get(cab_ff, [])

    if mobo_ff in allowed:
        return "PASS", f"Motherboard ({mobo_ff}) fits in Cabinet ({cab_ff})."
    else:
        return "FAIL", f"Motherboard ({mobo_ff}) does NOT fit in Cabinet ({cab_ff})."


# ─── Rule 6: Total price is within budget ────────────────────────────────────
def rule_within_budget(build, budget):
    """
    Check that the total price of all parts listed in the build does not exceed the user's budget.
    Prices exactly what the AI lists (consistent 1x price per item).
    """
    if budget is None:
        return "UNKNOWN", "No budget specified."

    total = 0
    for part in build:
        spec = find_spec(part)
        if spec:
            total += spec.get("price", 0)
        else:
            return "UNKNOWN", f"Part '{part}' not found in database. Cannot calculate total."

    if total <= budget:
        return "PASS", f"Total (Rs.{total:,}) <= Budget (Rs.{budget:,})."
    else:
        return "FAIL", f"Total (Rs.{total:,}) > Budget (Rs.{budget:,}). Over budget by Rs.{total - budget:,}."


# ─── Run All Rules ────────────────────────────────────────────────────────────
def judge_build(build, budget=None):
    """Run all 6 compatibility rules on a build. Returns a results dict."""
    results = {}
    results["1_all_categories"]  = rule_all_categories_present(build)
    results["2_socket_match"]    = rule_socket_match(build)
    results["3_ram_type_match"]  = rule_ram_type_match(build)
    results["4_psu_sufficient"]  = rule_psu_sufficient(build)
    results["5_formfactor_fit"]  = rule_formfactor_fit(build)
    results["6_within_budget"]   = rule_within_budget(build, budget)
    return results


def print_results(label, results):
    """Pretty-print the judge results."""
    print(f"\n{'='*60}")
    print(f"  BUILD: {label}")
    print(f"{'='*60}")
    all_pass = True
    for rule, (verdict, reason) in results.items():
        icon = "[PASS]" if verdict == "PASS" else ("[FAIL]" if verdict == "FAIL" else "[?]")
        print(f"  {icon} {rule}: {verdict} — {reason}")
        if verdict == "FAIL":
            all_pass = False
    print(f"{'─'*60}")
    overall = "PASS [OK]" if all_pass else "FAIL [X]"
    print(f"  OVERALL: {overall}")
    print(f"{'='*60}\n")


# ─── Self-Test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    good_build = [
        "Intel i5 12400",
        "MSI PRO B660M-E DDR4",
        "Gigabyte RTX 4060 OC 8GB",
        "Adata XPG Gammix D30 16GB DDR4 3200MHz (Red)",
        "Adata Legend 710 512GB M.2 NVMe Internal SSD",
        "Western Digital HDD 1TB",
        "MSI MAG A650BN PSU-650W 80 Plus Bronze",
        "Deepcool Macube 110 Cabinet(White)",
        "Cooler Master Liquid 240L ARGB (White)",
    ]

    bad_build = [
        "AMD Ryzen 5 5600",
        "MSI PRO B760M-E DDR5",
        "Gigabyte RTX 4060 OC 8GB",
        "Adata XPG Gammix D30 8GB DDR4 3200MHz (Red)",
        "Adata Legend 710 256GB M.2 NVMe Internal SSD",
        "Western Digital HDD 1TB",
        "MSI MAG A550BN PSU-550W 80 Plus Bronze",
        "GALAX Revolution-06 Mesh RGB (ATX) Mid-tower",
        "Cooler Master Liquid 240L ARGB (Black)",
    ]

    print("\nRunning Compatibility Judge Self-Test...\n")

    good_results = judge_build(good_build, budget=80000)
    print_results("GOOD BUILD (Expected: ALL PASS)", good_results)

    bad_results = judge_build(bad_build, budget=60000)
    print_results("BAD BUILD (Expected: FAIL)", bad_results)
