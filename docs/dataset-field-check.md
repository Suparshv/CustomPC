# Dataset Field Check & Completeness Report

> Generated on 2026-11-12 from docyx/pc-part-dataset (MIT License, July 2025 scrape).

## 1. Summary of Categories & Price Availability

| Category File | Total Parts | Priced Parts | % with Price | Total Fields |
|---|---|---|---|---|
| `cpu.json` | 1,413 | 547 | 38.7% | 8 |
| `motherboard.json` | 4,973 | 951 | 19.1% | 7 |
| `video-card.json` | 6,636 | 1,275 | 19.2% | 8 |
| `memory.json` | 13,553 | 2,907 | 21.4% | 8 |
| `internal-hard-drive.json` | 6,461 | 2,103 | 32.5% | 8 |
| `power-supply.json` | 3,438 | 567 | 16.5% | 7 |
| `case.json` | 6,626 | 1,053 | 15.9% | 8 |
| `cpu-cooler.json` | 2,851 | 946 | 33.2% | 6 |
| **Total (8 Categories)** | **45,951** | **10,349** | **22.5%** | - |

---

## 2. Field-by-Field Completeness Analysis

### `cpu.json` (cpu)
- **Total Rows:** 1,413
- **Rows with Valid Price:** 547 (38.7%)

| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |
|---|---|---|---|
| `name` | 1,413 | 100.0% | Key component identifier |
| `core_count` | 1,413 | 100.0% | Complete |
| `core_clock` | 1,413 | 100.0% | Complete |
| `microarchitecture` | 1,413 | 100.0% | Complete |
| `tdp` | 1,413 | 100.0% | Complete |
| `boost_clock` | 727 | 51.5% | Partially available |
| `graphics` | 621 | 43.9% | Sparse |
| `price` | 547 | 38.7% | **Required filter:** unpriced parts are excluded |

### `motherboard.json` (motherboard)
- **Total Rows:** 4,973
- **Rows with Valid Price:** 951 (19.1%)

| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |
|---|---|---|---|
| `name` | 4,973 | 100.0% | Key component identifier |
| `socket` | 4,973 | 100.0% | Complete |
| `form_factor` | 4,973 | 100.0% | Complete |
| `max_memory` | 4,973 | 100.0% | Complete |
| `memory_slots` | 4,973 | 100.0% | Complete |
| `color` | 4,670 | 93.9% | Partially available |
| `price` | 951 | 19.1% | **Required filter:** unpriced parts are excluded |

### `video-card.json` (video-card)
- **Total Rows:** 6,636
- **Rows with Valid Price:** 1,275 (19.2%)

| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |
|---|---|---|---|
| `name` | 6,636 | 100.0% | Key component identifier |
| `chipset` | 6,636 | 100.0% | Complete |
| `memory` | 6,636 | 100.0% | Complete |
| `core_clock` | 6,512 | 98.1% | Partially available |
| `color` | 6,336 | 95.5% | Partially available |
| `length` | 5,976 | 90.1% | Partially available |
| `boost_clock` | 4,138 | 62.4% | Partially available |
| `price` | 1,275 | 19.2% | **Required filter:** unpriced parts are excluded |

### `memory.json` (memory)
- **Total Rows:** 13,553
- **Rows with Valid Price:** 2,907 (21.4%)

| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |
|---|---|---|---|
| `name` | 13,553 | 100.0% | Key component identifier |
| `speed` | 13,553 | 100.0% | Complete |
| `modules` | 13,553 | 100.0% | Complete |
| `first_word_latency` | 13,553 | 100.0% | Complete |
| `cas_latency` | 13,553 | 100.0% | Complete |
| `color` | 12,859 | 94.9% | Partially available |
| `price` | 2,907 | 21.4% | **Required filter:** unpriced parts are excluded |
| `price_per_gb` | 2,851 | 21.0% | Sparse |

### `internal-hard-drive.json` (internal-hard-drive)
- **Total Rows:** 6,461
- **Rows with Valid Price:** 2,103 (32.5%)

| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |
|---|---|---|---|
| `name` | 6,461 | 100.0% | Key component identifier |
| `capacity` | 6,461 | 100.0% | Complete |
| `form_factor` | 6,461 | 100.0% | Complete |
| `interface` | 6,461 | 100.0% | Complete |
| `type` | 6,431 | 99.5% | Complete |
| `price` | 2,103 | 32.5% | **Required filter:** unpriced parts are excluded |
| `price_per_gb` | 2,048 | 31.7% | Sparse |
| `cache` | 1,967 | 30.4% | Sparse |

### `power-supply.json` (power-supply)
- **Total Rows:** 3,438
- **Rows with Valid Price:** 567 (16.5%)

| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |
|---|---|---|---|
| `name` | 3,438 | 100.0% | Key component identifier |
| `type` | 3,438 | 100.0% | Complete |
| `wattage` | 3,438 | 100.0% | Complete |
| `modular` | 3,438 | 100.0% | Complete |
| `efficiency` | 3,028 | 88.1% | Partially available |
| `color` | 1,859 | 54.1% | Partially available |
| `price` | 567 | 16.5% | **Required filter:** unpriced parts are excluded |

### `case.json` (case)
- **Total Rows:** 6,626
- **Rows with Valid Price:** 1,053 (15.9%)

| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |
|---|---|---|---|
| `name` | 6,626 | 100.0% | Key component identifier |
| `type` | 6,626 | 100.0% | Complete |
| `internal_35_bays` | 6,626 | 100.0% | Complete |
| `color` | 6,568 | 99.1% | Complete |
| `external_volume` | 5,265 | 79.5% | Partially available |
| `side_panel` | 4,629 | 69.9% | Partially available |
| `price` | 1,053 | 15.9% | **Required filter:** unpriced parts are excluded |
| `psu` | 521 | 7.9% | Sparse |

### `cpu-cooler.json` (cpu-cooler)
- **Total Rows:** 2,851
- **Rows with Valid Price:** 946 (33.2%)

| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |
|---|---|---|---|
| `name` | 2,851 | 100.0% | Key component identifier |
| `rpm` | 2,702 | 94.8% | Partially available |
| `noise_level` | 2,565 | 90.0% | Partially available |
| `color` | 1,923 | 67.5% | Partially available |
| `size` | 1,293 | 45.4% | Sparse |
| `price` | 946 | 33.2% | **Required filter:** unpriced parts are excluded |

---

## 3. Compatibility Field Gaps & Ingestion Strategy

The raw dataset is missing several critical hardware compatibility attributes required for physical checks. These are derived or handled as follows:

1. **CPU Socket Missing:**
   - `cpu.json` contains `name` and `microarchitecture` but no direct `socket` field.
   - *Strategy:* Derive socket from name and microarchitecture: Ryzen 3000-5000 -> AM4; Ryzen 7000-9000 -> AM5; Intel 12th-14th Gen -> LGA1700; Core Ultra (Arrow Lake) -> LGA1851.

2. **Motherboard RAM Generation Missing:**
   - `motherboard.json` specifies socket and form factor, but RAM type (DDR4 vs DDR5) is not an explicit column.
   - *Strategy:* Derive from socket: AM5 and LGA1851 are exclusively DDR5; AM4 is DDR4. For LGA1700 boards, inspect the name for 'DDR4' or 'D4' (DDR4) or qualify verified DDR5 boards. Non-conforming LGA1700 boards are excluded.

3. **GPU Wattage / TDP:**
   - `video-card.json` contains chipset, memory, and length, but power consumption is omitted.
   - *Strategy:* Use default TDP tables by chipset family on Day 7.

4. **Case Clearance & Cooler Height:**
   - GPU maximum length clearance and cooler height clearance are sparsely populated across cases.
   - *Strategy:* Curate standard clearance thresholds on Day 7.

5. **Stock Availability:**
   - Scraped PCPartPicker data has no inventory status.
   - *Strategy:* Deterministically simulate ~92% in-stock based on a hash of the part ID, clearly marked `in_stock: true/false` and `stock_simulated: true`.
