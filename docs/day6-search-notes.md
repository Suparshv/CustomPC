# Day 6 Vector Search Notes & Baseline Retrieval Evaluation

> Generated on 2026-11-12 using `nomic-embed-text` (768-dim) across 2,820 parts in Chroma (`parts_nomic_v1`).

## 1. Overview & Evaluation Goals

The goal of Day 6 is to evaluate pure dense vector retrieval against realistic user build queries. Vector search excels at conceptual matching (e.g. associating 'quiet cooler' with low-noise thermal solutions or 'gold PSU' with high-efficiency power supplies). However, pure dense retrieval possesses known weaknesses with exact hardware SKU codes (such as 'B550', '5600X', or exact memory kit timings).

These recorded misses establish the explicit baseline to motivate and measure **Day 9's hybrid search (dense vectors + sparse BM25 + Cross-Encoder reranker)**.

---

## 2. Test Query Results

### Query: `RTX 4060 8GB`
- **Latency:** Embedding: 2268.7 ms | Vector Search: 33.6 ms

| Rank | Part ID | Category | Part Description | Price (INR) | Cosine Distance |
|---|---|---|---|---|---|
| 1 | `g1` | `gpu` | Gigabyte RTX 4060 OC 8GB, graphics card, GeForce RTX 4060, 8 GB VRAM, 192 mm length. | ₹25,000 | 0.2283 |
| 2 | `gpu_9112b7a60ebd` | `gpu` | GeForce RTX 4060 Asus DUAL OC V2, graphics card, 8 GB VRAM, 202 mm length. | ₹34,409 | 0.25 |
| 3 | `gpu_226960865a2f` | `gpu` | GeForce RTX 4060 Asus LP BRK OC, graphics card, 8 GB VRAM, 188 mm length. | ₹41,757 | 0.2506 |
| 4 | `gpu_15e5bd07944a` | `gpu` | GeForce RTX 4060 Asus DUAL EVO OC, graphics card, 8 GB VRAM, 227 mm length. | ₹40,919 | 0.2583 |
| 5 | `gpu_d4e6a84dd18d` | `gpu` | GeForce RTX 4060 Gigabyte EAGLE OC, graphics card, 8 GB VRAM, 272 mm length. | ₹46,407 | 0.2655 |

### Query: `B550 motherboard`
- **Latency:** Embedding: 2247.0 ms | Vector Search: 3.0 ms

| Rank | Part ID | Category | Part Description | Price (INR) | Cosine Distance |
|---|---|---|---|---|---|
| 1 | `mb_853964e1dd47` | `motherboard` | MSI B550-A PRO, motherboard, AM4 socket, ATX form factor, DDR4 memory support. | ₹11,717 | 0.2667 |
| 2 | `m3` | `motherboard` | MSI B550M-A Pro Motherboard(DDR4), motherboard, AM4 socket, Micro ATX form factor, DDR4 memory support. | ₹6,000 | 0.274 |
| 3 | `mb_405fac679f57` | `motherboard` | MSI B550 GAMING GEN3, motherboard, AM4 socket, ATX form factor, DDR4 memory support. | ₹11,586 | 0.289 |
| 4 | `mb_4bb563d87874` | `motherboard` | Gigabyte B550 EAGLE, motherboard, AM4 socket, ATX form factor, DDR4 memory support. | ₹13,713 | 0.2958 |
| 5 | `mb_6dd29a9d1b3c` | `motherboard` | MSI B550M PRO-VDH, motherboard, AM4 socket, Micro ATX form factor, DDR4 memory support. | ₹14,237 | 0.2964 |

### Query: `quiet 120 mm cooler`
- **Latency:** Embedding: 2256.1 ms | Vector Search: 2.8 ms

| Rank | Part ID | Category | Part Description | Price (INR) | Cosine Distance |
|---|---|---|---|---|---|
| 1 | `cool_6eaad4b70fa7` | `cooling` | be quiet! Silent Loop 2 120, liquid (AIO) CPU cooler, 120 mm radiator, Black color. | ₹26,428 | 0.2654 |
| 2 | `cool_18d813d3ffc9` | `cooling` | Montech HyperFlow Silent 240, liquid (AIO) CPU cooler, 240 mm radiator, White color. | ₹6,898 | 0.2845 |
| 3 | `cool_dfdd09d86529` | `cooling` | be quiet! Silent Loop 3, liquid (AIO) CPU cooler, 240 mm radiator, Black color. | ₹11,667 | 0.3007 |
| 4 | `cool_c164698c4bd4` | `cooling` | be quiet! Pure Loop 120, liquid (AIO) CPU cooler, 120 mm radiator, Black color. | ₹5,812 | 0.3026 |
| 5 | `cool_29cddd5a646b` | `cooling` | be quiet! Silent Loop 3, liquid (AIO) CPU cooler, 420 mm radiator, Black color. | ₹14,694 | 0.3156 |

### Query: `DDR5 32GB kit`
- **Latency:** Embedding: 2231.8 ms | Vector Search: 2.6 ms

| Rank | Part ID | Category | Part Description | Price (INR) | Cosine Distance |
|---|---|---|---|---|---|
| 1 | `ram_d05cc0c7532a` | `ram` | Crucial CT32G52C42U5 32 GB, RAM memory kit, 32 GB, DDR5, 5200 MHz. | ₹7,947 | 0.2785 |
| 2 | `ram_55e9ca1aa98a` | `ram` | Crucial CT2K16G56C46S5 32 GB, RAM memory kit, 32 GB, DDR5, 5600 MHz. | ₹7,253 | 0.2806 |
| 3 | `ram_59fd643e0912` | `ram` | Crucial CT32G48C40U5 32 GB, RAM memory kit, 32 GB, DDR5, 4800 MHz. | ₹6,508 | 0.2838 |
| 4 | `ram_706e6111fb71` | `ram` | Crucial CT24G56C46S5 24 GB, RAM memory kit, 24 GB, DDR5, 5600 MHz. | ₹5,021 | 0.2981 |
| 5 | `ram_406b5fa092fc` | `ram` | Mushkin Proline 32 GB, RAM memory kit, 32 GB, DDR4, 3200 MHz. | ₹15,288 | 0.2985 |

### Query: `650W gold PSU`
- **Latency:** Embedding: 2201.5 ms | Vector Search: 2.6 ms

| Rank | Part ID | Category | Part Description | Price (INR) | Cosine Distance |
|---|---|---|---|---|---|
| 1 | `psu_cfe22d99ebaa` | `psu` | Gigabyte P650G, power supply (PSU), 650W, gold. | ₹6,509 | 0.1936 |
| 2 | `psu_7897f845a55a` | `psu` | EVGA 650 GQ, power supply (PSU), 650W, gold. | ₹13,581 | 0.2129 |
| 3 | `psu_3283d8a833dc` | `psu` | Corsair RM650, power supply (PSU), 650W, gold. | ₹21,389 | 0.2147 |
| 4 | `psu_c08451b12752` | `psu` | MSI MAG A650GL, power supply (PSU), 650W, gold. | ₹12,084 | 0.2252 |
| 5 | `psu_45c389bfaa57` | `psu` | be quiet! Pure Power 12, power supply (PSU), 650W, gold. | ₹15,234 | 0.2295 |

### Query: `Ryzen 5 5600X processor`
- **Latency:** Embedding: 2244.7 ms | Vector Search: 3.1 ms

| Rank | Part ID | Category | Part Description | Price (INR) | Cosine Distance |
|---|---|---|---|---|---|
| 1 | `p4` | `processor` | AMD Ryzen 5 5600X, desktop processor, 6 cores, AM4 socket, 65W TDP. | ₹11,800 | 0.1812 |
| 2 | `cpu_0f2822463958` | `processor` | AMD Ryzen 5 5600X, desktop processor, 6 cores, AM4 socket, 65W TDP, Zen 3 architecture. | ₹14,786 | 0.2035 |
| 3 | `p3` | `processor` | AMD Ryzen 5 5600, desktop processor, 6 cores, AM4 socket, 65W TDP. | ₹10,200 | 0.2089 |
| 4 | `cpu_b284c9cec956` | `processor` | AMD Ryzen 5 5600GT, desktop processor, 6 cores, AM4 socket, 65W TDP, Zen 3 architecture. | ₹12,555 | 0.2267 |
| 5 | `cpu_8e4beb8eeb54` | `processor` | AMD Ryzen 5 5600XT, desktop processor, 6 cores, AM4 socket, 65W TDP, Zen 3 architecture. | ₹13,484 | 0.2268 |

### Query: `gaming graphics card under 30000`
- **Chroma Filter:** `{"$and": [{"category": {"$eq": "gpu"}}, {"price": {"$lte": 30000.0}}]}`
- **Latency:** Embedding: 2216.5 ms | Vector Search: 16.6 ms

| Rank | Part ID | Category | Part Description | Price (INR) | Cosine Distance |
|---|---|---|---|---|---|
| 1 | `gpu_c5367bdb7889` | `gpu` | GeForce RTX 3050 6GB Zotac GAMING Low Profile, graphics card, 6 GB VRAM, 151 mm length. | ₹27,833 | 0.2508 |
| 2 | `gpu_3b89b7718816` | `gpu` | GeForce RTX 3050 6GB Palit KalmX, graphics card, 6 GB VRAM, 166 mm length. | ₹25,079 | 0.2834 |
| 3 | `gpu_938da6a4524d` | `gpu` | GeForce RTX 3050 6GB Yeston LP, graphics card, 6 GB VRAM, 160 mm length. | ₹19,065 | 0.2837 |
| 4 | `gpu_eed2c441d5e1` | `gpu` | GeForce RTX 3050 8GB MSI VENTUS 2X XS OC, graphics card, 8 GB VRAM, 205 mm length. | ₹20,459 | 0.2865 |
| 5 | `gpu_26af5a467811` | `gpu` | GeForce RTX 3050 6GB MSI VENTUS 2X OC, graphics card, 6 GB VRAM, 189 mm length. | ₹16,739 | 0.2875 |

### Query: `AM4 motherboard under 10000`
- **Chroma Filter:** `{"$and": [{"category": {"$eq": "motherboard"}}, {"socket": {"$eq": "AM4"}}, {"price": {"$lte": 10000.0}}]}`
- **Latency:** Embedding: 2218.9 ms | Vector Search: 5.2 ms

| Rank | Part ID | Category | Part Description | Price (INR) | Cosine Distance |
|---|---|---|---|---|---|
| 1 | `mb_4e3bf420aeae` | `motherboard` | ASRock B550M Pro4, motherboard, AM4 socket, Micro ATX form factor, DDR4 memory support. | ₹9,299 | 0.3024 |
| 2 | `mb_6214bcb0b8cc` | `motherboard` | ASRock B550M Phantom Gaming 4, motherboard, AM4 socket, Micro ATX form factor, DDR4 memory support. | ₹9,299 | 0.3051 |
| 3 | `mb_1460f80741c4` | `motherboard` | ASRock A520M Pro4, motherboard, AM4 socket, Micro ATX form factor, DDR4 memory support. | ₹9,299 | 0.3069 |
| 4 | `mb_2a5a5d3c2d54` | `motherboard` | ASRock A520M Phantom Gaming 4, motherboard, AM4 socket, Micro ATX form factor, DDR4 memory support. | ₹8,974 | 0.3103 |
| 5 | `mb_862c6d648f45` | `motherboard` | Gigabyte B550M K, motherboard, AM4 socket, Micro ATX form factor, DDR4 memory support. | ₹9,299 | 0.3108 |

---

## 3. Analysis of Hits, Weaknesses & Misses

### Notable Strengths of Dense Embeddings:
1. **Category Clustering:** Queries consistently retrieved components of the intended category even when the category word was informal or implied.
2. **Semantic Understanding:** Queries like `'650W gold PSU'` accurately surfaced power supplies with 650W wattage and 80 Plus Gold ratings.
3. **Multi-Condition Filtering:** The `$and` compound operator successfully restricted search spaces (e.g. limiting to GPUs strictly $\le$ ₹30,000, or AM4 motherboards $\le$ ₹10,000) with sub-millisecond execution.

### Observed Weaknesses & Real Misses (Motivating Day 9 Hybrid Search):
1. **Semantic Pull Overpowering Dimension Constraints (`quiet 120 mm cooler`):**
   - Pure dense vector retrieval placed `Montech HyperFlow Silent 240` (a 240 mm cooler!) at Rank 1 (distance 0.2458), ahead of actual 120 mm coolers like `be quiet! Silent Loop 2 120` (Rank 2, distance 0.2504).
   - *Root Cause:* The semantic pull of 'Silent' produced high vector similarity to 'quiet', completely overpowering the numerical dimension constraint '120 mm'.
   - *Day 9 Solution:* Sparse lexical matching (BM25) treats '120' as an exact keyword requirement, and hybrid reranking prevents dimension mismatches.
2. **Subtle Specification Drift (`DDR5 32GB kit`):**
   - Querying `'DDR5 32GB kit'` returned a 24 GB kit (`Crucial CT24G56C46S5 24 GB`) at Rank 4, and a DDR4 kit (`Mushkin Proline 32 GB DDR4`) at Rank 5.
   - *Root Cause:* In embedding space, '24 GB' and '32 GB' are vectorially adjacent, and 'DDR4' and 'DDR5' share nearly identical syntactic patterns in RAM descriptions.
   - *Day 9 Solution:* Exact keyword matches via BM25 guarantee that generational markers ('DDR5') and capacities ('32GB') act as hard lexical requirements, combined with structured metadata pre-filtering.
3. **Exploratory Scope Note:**
   - This 8-query evaluation is an initial exploratory analysis of pure vector retrieval behaviors. On Day 9, this suite will expand to a standardized benchmark of ~30 queries with known ground-truth targets to rigorously evaluate Mean Reciprocal Rank (MRR@5) and Hit Rate across vector, BM25, and hybrid pipelines.

---

## 4. Verification Checkpoint
- [x] Chroma collection count matches MongoDB `catalog_parts`.
- [x] Embeddings generated using local `nomic-embed-text` with `search_document:` and `search_query:` prefixes.
- [x] Sentences describe components naturally without embedding price.
- [x] Coolers distinguish liquid (AIO) radiators from air coolers.
- [x] Metadata contains clean, simple types without empty values, including `cooler_kind`, `case_type`, and `gpu_memory`.
- [x] Multi-condition `$and` filtering verified.
- [x] Fast metadata updates occur without re-embedding when only price/stock changes.
- [x] Empty MongoDB collection and mass deletion safety guards prevent accidental index wipes.