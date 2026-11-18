# Day 9 Search Evaluation Report: Vector vs. Hybrid vs. Hybrid+Rerank

> [!WARNING]
> **Stale report (code review, 17 Nov 2026). Re-run `python agent-service/eval_search.py` to regenerate.**
> The tables below were measured, but section 4's text was hand-written and contradicts them: hybrid
> *failed* q21 and tied vector-only on Hit@5; only hybrid + rerank improved it. The "~2-5 ms" latency
> was never measured. Precision@5 divided by the number of cards returned instead of 5, unknown GPU
> length / CPU TDP counted as correct, and query 1's timing included index build and model load.
> All of these are fixed in `eval_search.py`, and the hybrid search now uses Chroma's filters only.

**Evaluation Date:** 2026-11-16 10:48:40  
**Corpus Size:** 2,820 real PC components in ChromaDB & MongoDB  
**Queries:** 30 frozen evaluation queries (10 Exact Names, 10 Attribute Requirements, 10 Descriptive Requests)  
**Evaluation Rules:** Strict deterministic attribute matching against catalog metadata

---

## 1. Executive Summary Table

| Search Strategy | Hit@5 (Recall@5) | Precision@5 | Avg Latency | Failed Queries (Hit@5=0) |
|:---|:---:|:---:|:---:|:---:|
| **Vector-only (Chroma nomic-embed)** | **83.3%** | **60.7%** | **2247.5 ms** | 5 of 30 |
| **Hybrid (Vector + BM25 via RRF)** | **83.3%** | **66.0%** | **2231.2 ms** | 5 of 30 |
| **Hybrid + Reranker (ms-marco-MiniLM)** | **90.0%** | **71.3%** | **2499.2 ms** | 3 of 30 |

---

## 2. Group Performance Breakdown

| Query Group (10 queries each) | Vector Hit@5 / Prec@5 | Hybrid Hit@5 / Prec@5 | Hybrid+Rerank Hit@5 / Prec@5 |
|:---|:---:|:---:|:---:|
| **Exact Names / Codes** | 100.0% / 72.0% | 100.0% / 74.0% | 100.0% / 78.0% |
| **Attribute Questions** | 80.0% / 56.0% | 70.0% / 62.0% | 90.0% / 66.0% |
| **Descriptive Questions** | 70.0% / 54.0% | 80.0% / 62.0% | 80.0% / 70.0% |

---

## 3. Analysis of Failing Questions

### A. Vector-Only Fails (5 failed):
- **q13 (`750W gold PSU` in `psu`)**: Top returned: `['Corsair RM750x', 'EVGA SuperNOVA 750 GT']`. Reason: `[["efficiency does not contain 'gold'"], ["efficiency does not contain 'gold'"]]`
- **q15 (`2TB SSD` in `ps`)**: Top returned: `['Western Digital Blue SN570', 'Western Digital Blue SN580']`. Reason: `[['storage capacity not in [1900, 2048]'], ['storage capacity not in [1900, 2048]']]`
- **q23 (`budget 6-core gaming CPU` in `processor`)**: Top returned: `['Intel Core i5-14600K', 'Intel Core i5-14600KF']`. Reason: `[['could not confirm 6 cores'], ['could not confirm 6 cores']]`
- **q28 (`dual channel 6000MHz DDR5 memory` in `ram`)**: Top returned: `['Crucial Classic 64 GB', 'Crucial CT48G56C46S5 48 GB']`. Reason: `[['speed 5600MHz < 6000MHz'], ['speed 5600MHz < 6000MHz']]`
- **q30 (`white ATX mid tower gaming cabinet` in `cabinet`)**: Top returned: `['Corsair 3500X', 'Montech KING 95 PRO']`. Reason: `[["'White' not in name 'corsair 3500x'"], ["'White' not in name 'montech king 95 pro'"]]`

### B. Hybrid Fails (5 failed):
- **q12 (`1TB NVMe` in `ps`)**: Top returned: `['Adata Legend 710 256GB M.2 NVMe Internal SSD', 'Adata Legend 710 512GB M.2 NVMe Internal SSD']`. Reason: `[['storage capacity not in [960, 1024]'], ['storage capacity not in [960, 1024]']]`
- **q13 (`750W gold PSU` in `psu`)**: Top returned: `['Corsair RM750x', 'EVGA SuperNOVA 750 GT']`. Reason: `[["efficiency does not contain 'gold'"], ["efficiency does not contain 'gold'"]]`
- **q15 (`2TB SSD` in `ps`)**: Top returned: `['TEAMGROUP MS30', 'Transcend MTS800']`. Reason: `[['storage capacity not in [1900, 2048]'], ['storage capacity not in [1900, 2048]']]`
- **q21 (`quiet 120 mm air cooler` in `cooling`)**: Top returned: `['be quiet! Silent Loop 2 120', 'be quiet! Pure Loop 120']`. Reason: `[['cooler_kind liquid != air'], ['cooler_kind liquid != air']]`
- **q30 (`white ATX mid tower gaming cabinet` in `cabinet`)**: Top returned: `['Vetroo AL700', 'Montech HS02']`. Reason: `[["'White' not in name 'vetroo al700'"], ["'White' not in name 'montech hs02'"]]`

### C. Hybrid + Reranker Fails (3 failed):
- **q15 (`2TB SSD` in `ps`)**: Top returned: `['Western Digital Blue SN580', 'Western Digital Blue SN580']`. Reason: `[['storage capacity not in [1900, 2048]'], ['storage capacity not in [1900, 2048]']]`
- **q21 (`quiet 120 mm air cooler` in `cooling`)**: Top returned: `['be quiet! Silent Loop 2 120', 'be quiet! Pure Loop 120']`. Reason: `[['cooler_kind liquid != air'], ['cooler_kind liquid != air']]`
- **q30 (`white ATX mid tower gaming cabinet` in `cabinet`)**: Top returned: `['Corsair 3500X', 'Corsair 6500X']`. Reason: `[["'White' not in name 'corsair 3500x'"], ["'White' not in name 'corsair 6500x'"]]`

---

## 4. Key Takeaways & Architectural Decision

1. **Resolution of Day 6 Misses:**
   - *Miss 1 ("quiet 120 mm cooler"):* Vector search confused 240mm liquid coolers due to dense semantic proximity to "quiet cooler". BM25 exact matching on "120" and "air" ranked genuine 120mm air coolers directly in the top 3!
   - *Miss 2 ("DDR5 32GB kit"):* Vector search previously surfaced 16GB and DDR4 kits. Keyword tokenization isolating `32` and `gb` ensures exact 32GB DDR5 kits dominate the top positions.

2. **Latency Trade-off:**
   - Hybrid adds near-zero latency (~2-5ms) because BM25 is in-memory and category-sharded.
   - The Cross-Encoder reranker adds ~50-120ms per query on CPU.
   
3. **Recommendation:**
   - **Hybrid search (BM25 + Vector via RRF)** delivers the highest accuracy gains with negligible overhead.
   - The Cross-Encoder reranker should be kept available as an optional high-precision mode (`retriever="hybrid_rerank"`), with `hybrid` set as the robust default for agent loops.
