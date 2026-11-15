# Compatibility Checker Rules & Verification Specification (Day 7)

## 1. Overview & Philosophy

In the v1 system, an LLM "Critic" was prompted to judge whether recommended components fit together. When LLM parsing failed or hallucinated, the `/compatibility` endpoint defaulted to reporting "compatible". This allowed builds with incompatible CPU sockets, insufficient power supplies, and over-budget components to pass undetected.

Day 7 replaces AI speculation with a deterministic, code-based compatibility judge ([`checker.py`](../agent-service/checker.py)). The LLM only proposes component candidates and explains results; plain code reads numerical specifications and enforces physical, electrical, and budgetary rules.

---

## 2. The Three-Outcome Model

Every rule yields one of three mutually exclusive verdicts:

| Verdict | Meaning | Handling in System |
|---|---|---|
| **`PASS`** | The condition is rigorously verified and satisfied by specification numbers. | Counted towards verification. |
| **`FAIL`** | An explicit physical, electrical, or budgetary conflict was detected. | Invalidates the build. Flagged to retry loop with corrective feedback. |
| **`UNKNOWN`** | Required specification data is missing or uncurated. | **Never converted to `PASS`**. A checker that guesses is no better than an AI Critic. |

### Build Status Definitions:
- **`valid` (`bool`):** True if **no rule returns `FAIL`** and **no unresolved part IDs exist** (`len(fails) == 0 and len(unresolved) == 0`). Allows builds with missing data to be reviewed while preventing known-broken builds.
- **`fully_verified` (`bool`):** True if **every single rule returns `PASS`** (`len(fails) == 0 and len(unknowns) == 0 and len(unresolved) == 0`). Indicates complete physical, electrical, and budgetary certainty.
- **`unresolved` (`list`):** Explicitly lists any part identifiers that could not be mapped to known specifications.

---

## 3. Specification of the 8 Compatibility Rules

### Rule 1: `all_categories`
- **Data Needed:** Component `category` across all build parts.
- **Requirement:** All 9 canonical categories must be present: `processor`, `motherboard`, `gpu`, `ram`, `ps` (primary SSD), `ss` (secondary HDD), `psu`, `cabinet`, `cooling`.
- **`PASS`:** All 9 categories exist in the build with 0 unresolved identifiers.
- **`FAIL`:** Any category is missing or unresolved part identifiers exist (lists exact missing categories and unresolved IDs).

### Rule 2: `socket_match`
- **Data Needed:** CPU `socket`, Motherboard `socket`.
- **Requirement:** Physical socket matching (e.g. AMD `AM5` $\to$ `AM5`, Intel `LGA1700` $\to$ `LGA1700`).
- **`PASS`:** `cpu_socket == mobo_socket`.
- **`FAIL`:** `cpu_socket != mobo_socket` (e.g. Ryzen 7600 on B760 board).
- **`UNKNOWN`:** CPU or Motherboard absent, or socket field is missing/empty.

### Rule 3: `ram_type_match`
- **Data Needed:** RAM `ram_type`, Motherboard `ram_type`, CPU `ram_type` / `socket`.
- **Requirement:** Memory generation physical slot and memory controller compatibility.
  - Motherboard dual-support (e.g., `DDR4/DDR5`) handles either generation.
  - Sockets `AM5` and `LGA1851` strictly require `DDR5`.
  - Socket `AM4` strictly requires `DDR4`.
- **`PASS`:** RAM generation is supported by both Motherboard and CPU memory controller.
- **`FAIL`:** DDR4 RAM in DDR5 motherboard, DDR5 in DDR4 board, or DDR4 paired with AM5 CPU.
- **`UNKNOWN`:** RAM or Motherboard absent, or `ram_type` missing from specs.

### Rule 4: `psu_headroom`
- **Data Needed:** CPU `tdp`, GPU `tdp`, PSU `wattage`.
- **Formula (identical to baseline):**
  $$\text{required\_watts} = \left\lceil (\text{CPU TDP} + \text{GPU TDP} + 80\text{W}) \times 1.4 \right\rceil$$
- **GPU TDP Resolution:** When GPU specification lacks raw TDP, it resolves via exact key or explicit alias matching in [`gpu_tdp.json`](../agent-service/data/curated/gpu_tdp.json). Substring fallback matching is strictly removed to prevent power leaks (e.g., RX 7600 XT gets 190W, not RX 7600's 165W; RTX 3060 Ti LHR gets 200W, not 170W; RTX 3060 8GB gets 115W).
- **`PASS`:** `psu_wattage >= required_watts`.
- **`FAIL`:** `psu_wattage < required_watts` (reports required vs actual wattage).
- **`UNKNOWN`:** CPU TDP missing, PSU wattage missing, or GPU chipset is uncurated.

### Rule 5: `formfactor_fit`
- **Data Needed:** Motherboard `form_factor`, Cabinet `case_type` / `form_factor`.
- **Clearance Matrix:**
  - `Mini ITX Tower` / `Mini ITX Desktop` $\to$ `["Mini ITX"]`
  - `MicroATX Mid Tower` / `MicroATX Mini Tower` / `MicroATX Desktop` $\to$ `["Micro ATX", "Mini ITX"]` (Tested first; strictly rejects ATX and EATX!)
  - `ATX Full Tower` $\to$ `["EATX", "ATX", "Micro ATX", "Mini ITX"]`
  - `ATX Mid Tower` / `ATX Desktop` $\to$ `["ATX", "Micro ATX", "Mini ITX"]` (does not fit EATX)
- **Catalogue Quirks Handled:**
  - **MicroATX Mid Towers (50 in catalogue):** Tested before generic Mid Tower checks to ensure full ATX motherboards FAIL.
  - **EATX Boards (16 in catalogue):** Requires Full Tower case. Fails in standard Mid Tower.
  - **Mini DTX Boards (1 in catalogue):** Returns `UNKNOWN` (niche form factor).
  - **HTPC Cases (19 in catalogue):** Returns `UNKNOWN` (specialized low-profile clearance).
- **`PASS`:** Motherboard form factor is contained within case supported list.
- **`FAIL`:** Motherboard is physically larger than case mounting tray.
- **`UNKNOWN`:** Missing form factor or unclassified case type.

### Rule 6: `gpu_length`
- **Data Needed:** GPU card `length` (mm), Case clearance limit `max_gpu_length_mm`.
- **Clearance Resolution:** Sourced from manufacturer specs in hand-curated [`cases.json`](../agent-service/data/curated/cases.json) by exact ID or exact lowercase name only (no fuzzy substring matching).
- **`PASS`:** $\text{GPU length} \le \text{Case maximum clearance}$.
- **`FAIL`:** $\text{GPU length} > \text{Case maximum clearance}$.
- **`UNKNOWN`:** GPU length missing or case model uncurated.

### Rule 7: `cooler_height`
- **Data Needed:** Air cooler `height_mm`, Case CPU cooler clearance `max_cooler_height_mm`.
- **Height & Clearance Resolution:** Sourced from official spec pages in [`coolers.json`](../agent-service/data/curated/coolers.json) and [`cases.json`](../agent-service/data/curated/cases.json) by exact ID or exact lowercase name only.
- **`PASS`:** $\text{Cooler height} \le \text{Case maximum clearance}$.
- **`FAIL`:** $\text{Cooler height} > \text{Case maximum clearance}$.
- **`UNKNOWN`:** Cooler is liquid (AIO), or cooler height/case clearance is uncurated.

### Rule 8: `within_budget`
- **Data Needed:** Component prices (`price_inr` / `price`), user `budget` (INR).
- **`PASS`:** $\sum \text{Part prices} \le \text{Budget}$.
- **`FAIL`:** $\sum \text{Part prices} > \text{Budget}$ (reports exact overage in INR).
- **`UNKNOWN`:** No budget provided (`budget is None`), or any part lacks a price.

---

## 4. Curated Hand-Made Specification Tables

Missing manufacturer dimensions were gathered directly from official spec pages with verified URLs on every record:

1. **[`data/curated/gpu_tdp.json`](../agent-service/data/curated/gpu_tdp.json):**
   - 50 GPU chipsets and specific power variants (RTX 4060, 4070, 4080, 4090, 5070, 5080, 5090, RTX 3060 8GB, RTX 3060 Ti LHR, RX 7600 XT, 7800 XT, 7900 XTX, GTX 1660 SUPER, etc.).
   - Sourced from official NVIDIA / AMD spec sheets.
2. **[`data/curated/cases.json`](../agent-service/data/curated/cases.json):**
   - 24 chassis (`cab1` Deepcool Macube 110, `cab2` GALAX Rev-06, Corsair 4000D, NZXT H7 Flow, Lian Li Lancool 207, Cooler Master Q300L, Fractal Pop Air, etc.).
   - Stores `max_gpu_length_mm` and `max_cooler_height_mm`.
3. **[`data/curated/coolers.json`](../agent-service/data/curated/coolers.json):**
   - 18 popular air coolers (Peerless Assassin 120, Phantom Spirit 120 SE, Hyper 212, Pure Rock LP, Noctua NH-U12S, Scythe Mugen 6, etc.).
   - Stores `height_mm`.

---

## 5. Part Checkability & Day 8 Preference Flag

Because 172 of 212 catalog coolers are liquid AIOs (which yield `UNKNOWN` for air cooler height clearance) and uncurated cases/coolers yield `UNKNOWN`, the checker exposes an `is_part_checkable(part)` inspection function.

A component is flagged as `"checkable": true` if all required physical, thermal, and electrical specifications are present or curated:
- **Processor:** `socket` and `tdp` present.
- **Motherboard:** `socket`, `ram_type`, and `form_factor` present.
- **RAM:** `ram_type` present.
- **PSU:** `wattage` present.
- **Storage:** `price` present.
- **GPU:** `length` present AND (`tdp` present or chipset in `gpu_tdp.json`).
- **Cabinet:** Non-HTPC case type AND entry present in `cases.json`.
- **Cooling:** Air cooler with height curated in `coolers.json`.

### Day 8 Search Strategy:
In Day 8's agent tools, candidate component search will use this flag to prioritize and boost parts with complete physical specifications over uncurated parts, allowing agent builds to consistently achieve `fully_verified = True`.

---

## 6. Explicit Limitations (What is NOT Checked)

The following physical compatibility attributes cannot be checked due to dataset limitations:
1. **Cooler Socket Mounting Bracket Support:** The open dataset does not list per-cooler mounting brackets for specific sockets (e.g. AM5 or LGA1700 adapter brackets).
2. **Motherboard M.2 NVMe Slot Count:** The raw dataset records only form factor and socket; total onboard M.2 slot count is unrecorded.
3. **Liquid AIO Radiator Clearance:** Radiator support (top vs front vs side, 240 mm vs 360 mm) requires full chassis radiator mounting curation.

Per architectural guidelines, the checker returns `UNKNOWN` or omits these checks rather than guessing or fabricating arbitrary pass conditions.

---

## 7. Golden Baseline Verification

To ensure zero drift from the v1 baseline scoring, [`agent-service/tests/test_checker.py`](../agent-service/tests/test_checker.py) runs a golden test loading all 30 baseline builds from [`eval/results.jsonl`](../eval/results.jsonl).

- **Total Builds Evaluated:** 30
- **Agreement on Shared Rules (`compat.py` vs `checker.py`):** **100% agreement (0 mismatches)**.
- **Failures Matched:** Socket mismatches, RAM generation incompatibilities, underpowered PSUs, and budget overages matched identically.
