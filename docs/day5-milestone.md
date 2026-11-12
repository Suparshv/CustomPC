# Day 5 Milestone: Dataset Analysis & Component Ingestion into MongoDB

## Overview

Day 5 scales the PC Builder's product knowledge from a toy catalog of 24 components in a static JSON file up to a production-grade MongoDB catalog containing 2,854 real PC hardware parts (2,830 curated from the MIT-licensed `docyx/pc-part-dataset` July 2025 scrape + 24 frozen seed test parts).

### Key Accomplishments
1. **Raw Dataset Extraction & Field Verification:**
   - Sparse-cloned and extracted 8 category files (45,951 total parts, 10,349 priced) into `agent-service/data/raw/` (ignored in `.gitignore`).
   - Generated a full field completeness report saved at [`docs/dataset-field-check.md`](./dataset-field-check.md).
2. **Deterministic Data Transformation & Ingestion Pipeline (`agent-service/ingest_parts.py`):**
   - **Stable ID Generation:** Collision-free, deterministic 12-hex hash identifiers derived from category prefix and full item attributes, ensuring strict idempotency.
   - **USD to INR Currency Conversion:** Applied fixed rate `USD_TO_INR_RATE=93.0` (as of `2026-11-12`), clearly labeled with `price_inr_approx=True` for dataset parts and `price_inr_approx=False` for seed parts.
   - **Socket & RAM Generation Derivation:**
     - CPUs: Ryzen 3000–5000 $\to$ AM4; Ryzen 7000–9000 $\to$ AM5; Intel 12th–14th Gen $\to$ LGA1700; Core Ultra $\to$ LGA1851.
     - Motherboards: AM4 $\to$ DDR4; AM5 / LGA1851 $\to$ DDR5; LGA1700 $\to$ DDR4 (or verified DDR5 boards).
   - **Deterministic Simulated Stock:** Consistent, repeatable ~92% in-stock flag calculated via hash of the part ID, marked `stock_simulated=True`.
   - **Balanced Price Spread:** Grouped sampling (GPUs by chipset, RAM by generation & capacity, PSUs by wattage, cases by form factor, storage by capacity) ensuring budget, mid-range, and high-end representation across all categories rather than taking only the cheapest components.
   - **Seed Set Retention:** Preserved all 24 original baseline parts with `source: "seed24"` and original IDs (`p1`-`p4`, `m1`-`m4`, `g1`-`g4`, `r1`-`r2`, `ps1`-`ps2`, `ss1`-`ss2`, `psu1`-`psu2`, `cab1`-`cab2`, `c1`-`c2`).
3. **Database Performance & Idempotency:**
   - Collection: `catalog_parts` in database `PC` (`mongodb://127.0.0.1:27017/PC`).
   - Indexed on `category` and `source` for sub-millisecond retrieval.
   - Ingestion uses `pymongo.ReplaceOne(..., upsert=True)` via `bulk_write(ordered=False)`.
   - **Strict Idempotency:** Verified by running twice consecutively; the second run matched all 2,854 documents and inserted/upserted **0** documents.

---

## Catalog Breakdown in MongoDB (`catalog_parts`)

| Category | Database Category | Source: `pcpartpicker` | Source: `seed24` | Total in Catalog | Selection / Derivation Rules |
|---|---|---|---|---|---|
| **Processors** | `processor` | 115 | 4 | **119** | Ryzen 3000–9000 & Intel 12th–14th + Core Ultra desktop; socket derived |
| **Motherboards** | `motherboard` | 574 | 4 | **578** | AM4, AM5, LGA1700, LGA1851; RAM type derived |
| **Graphics Cards** | `gpu` | 309 | 4 | **313** | RTX 20–50, GTX 16, RX 6000/7000/9000 with physical length; spread $\le 5$ per chipset |
| **Memory** | `ram` | 346 | 2 | **348** | DDR4 & DDR5, 8–128 GB total; spread $\le 30$ per (gen, capacity) |
| **Power Supplies** | `psu` | 205 | 2 | **207** | ATX form factor, $\ge 450$ W; spread $\le 15$ per wattage |
| **Cases / Cabinets** | `cabinet` | 334 | 2 | **336** | Standard ATX/mATX/ITX desktop form factors; spread $\le 50$ per type |
| **Primary Storage** | `ps` | 371 | 2 | **373** | SSDs $\ge 250$ GB; spread $\le 30$ per capacity |
| **Secondary Storage** | `ss` | 365 | 2 | **367** | 3.5" HDDs; spread $\le 25$ per capacity |
| **Cooling** | `cooling` | 212 | 2 | **214** | Air and liquid coolers with size/rpm specs; spread $\le 40$ per size |
| **Grand Total** | - | **2,830** | **24** | **2,854** | - |

---

## Idempotency Test Execution

```powershell
# Run 1: Initial Ingestion
python agent-service/ingest_parts.py
# Bulk Write Results:
#   • Matched Count  : 0
#   • Upserted Count : 2854
#   • Inserted Count : 0

# Run 2: Idempotency Verification
python agent-service/ingest_parts.py
# Bulk Write Results:
#   • Matched Count  : 2854
#   • Modified Count : 0
#   • Upserted Count : 0
#   • Inserted Count : 0
```

---

## Unit Tests

All 35 unit tests pass:
```powershell
.\agent-service\.venv\Scripts\pytest -q
...................................                                      [100%]
35 passed in 0.84s
```
Covering:
- Stable ID generation and cross-run determinism.
- Simulated stock generation (~92% distribution).
- Price-spread sampling across min, mid, and max price boundaries.
- 24 seed parts schema and category integrity.
- Category parser derivation logic (CPU sockets, motherboard RAM types).
