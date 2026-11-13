# Day 5 Milestone: Dataset Analysis & Component Ingestion into MongoDB

## Overview

Day 5 scales the PC Builder's product knowledge from a toy catalog of 24 components in a static JSON file up to a portfolio-scale catalog of 2,820 real PC hardware parts (2,796 curated from the MIT-licensed `docyx/pc-part-dataset` July 2025 scrape + 24 frozen seed test parts) stored in the MongoDB collection `catalog_parts` in database `PC`.

### Key Accomplishments
1. **Raw Dataset Extraction & Field Verification:**
   - Sparse-cloned and extracted 8 category files (45,951 total parts, 10,349 priced) into `agent-service/data/raw/` (ignored in `.gitignore`).
   - Generated a full field completeness report saved at [`docs/dataset-field-check.md`](./dataset-field-check.md).
2. **Unified Data Model Across Seed & Dataset Parts:**
   - Seed parts mapped to canonical dataset field names (`ram_type`, `form_factor`, `capacity_gb`, `speed_mhz`, `memory`, `length`) so the compatibility checker and search filters use a single code path.
   - Original seed attributes preserved under `legacy_specs` for full backward compatibility.
3. **Price-Independent Stable Identifiers:**
   - IDs are deterministic 12-hex hashes based strictly on category and physical identity discriminators (`name`, `chipset`, `form_factor`, `wattage`, `capacity`, etc.), excluding volatile pricing, retailer, and URL data.
   - Price updates cleanly update existing parts rather than creating duplicate documents.
   - Stale dataset documents removed from the catalog are automatically deleted during re-ingestion.
4. **USD to INR Currency Conversion:**
   - Applied fixed rate `USD_TO_INR_RATE=93.0` (as of `2026-11-12`), clearly labeled with `price_inr_approx=True` for dataset parts and `price_inr_approx=False` for seed parts.
5. **Hardware Compatibility Derivations:**
   - **CPUs:** Ryzen 3000–5000 $\to$ AM4; Ryzen 7000–9000 $\to$ AM5; Intel 12th–14th Gen $\to$ LGA1700; Core Ultra $\to$ LGA1851.
   - **Motherboards:** AM4 $\to$ DDR4; AM5 / LGA1851 $\to$ DDR5; LGA1700 with `\b(ddr4|d4)\b` $\to$ DDR4; LGA1700 with `\b(ddr5|d5)\b` $\to$ DDR5 (`ASRock H610M-HDV/M.2+ D5`).
6. **Deterministic Simulated Stock:**
   - Consistent, repeatable ~92% in-stock flag calculated via MD5 hash of the part ID, marked `stock_simulated=True`.
7. **Database Performance & Idempotency:**
   - Collection: `catalog_parts` in database `PC` (`mongodb://127.0.0.1:27017/PC`).
   - Indexed on `category` and `source` for sub-millisecond retrieval.
   - Ingestion uses `pymongo.ReplaceOne(..., upsert=True)` via `bulk_write(ordered=False)`.
   - **Strict Idempotency:** Verified by running twice consecutively; the second run matched all 2,820 documents and modified/upserted **0** documents.

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
| **Primary Storage** | `ps` | 363 | 2 | **365** | SSDs $\ge 250$ GB; spread $\le 30$ per capacity |
| **Secondary Storage** | `ss` | 338 | 2 | **340** | 3.5" HDDs; spread $\le 25$ per capacity |
| **Cooling** | `cooling` | 212 | 2 | **214** | Air and liquid coolers with size/rpm specs; spread $\le 40$ per size |
| **Grand Total** | - | **2,796** | **24** | **2,820** | - |

> [!NOTE]
> **Catalogue Coverage Limit:** Only one LGA1700 DDR5 board qualifies (`ASRock H610M-HDV/M.2+ D5`, as most LGA1700 board names in the raw dataset omit "DDR5" explicitly). Consequently, Intel DDR5 builds will mostly draw from Core Ultra (LGA1851), while 12th–14th gen Intel builds will primarily pair with DDR4.

---

## Idempotency Test Execution

```powershell
# Run 1: Upsert and Stale Pruning
python agent-service/ingest_parts.py
# Bulk Write Results:
#   • Matched Count  : 24 (Seed parts updated with unified mapping)
#   • Upserted Count : 2796
#   • Inserted Count : 0
#   • Deleted Stale  : 2830 (Cleaned old price-dependent IDs)

# Run 2: Idempotency Verification
python agent-service/ingest_parts.py
# Bulk Write Results:
#   • Matched Count  : 2820
#   • Modified Count : 0
#   • Upserted Count : 0
#   • Inserted Count : 0
```

---

## Unit Tests

All 37 unit tests pass offline:
```powershell
.\agent-service\.venv\Scripts\pytest -q
.....................................                                    [100%]
37 passed in 0.85s
```
Covering:
- Stable ID generation and price invariance (price changes don't change IDs).
- Seed parts unified field mapping and `legacy_specs` preservation.
- Deterministic simulated stock generation (~92% distribution).
- Price-spread sampling covering min, mid, and max price boundaries.
- Synthetic derivation logic for CPU sockets and motherboard RAM types (runs cleanly on fresh clones without raw files).
- Real category parser integration test (skipped automatically with clear notice if raw dataset files are absent).
