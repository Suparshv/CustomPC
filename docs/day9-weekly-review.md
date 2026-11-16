# Week 2 Milestone & Day 9 Review: Search Upgrade & Reranker Verdict

**Date:** 2026-11-16  
**Milestone:** End of Week 2 (Days 8–9: Deterministic Tools & Hybrid Search Retrieval)  
**Status:** All 91/91 Unit & Integration Tests Passing

---

## 1. What Shipped

1. **BM25 Keyword Search Engine (`keyword_search.py`):**
   - In-memory, category-partitioned `BM25Okapi` index over all 2,820 catalog components.
   - Custom hardware tokenizer preserving technical model numbers (`i5-12400`, `b550m`, `rtx-4060`) and splitting compound units (`32gb` → `["32gb", "32", "gb"]`, `750w` → `["750w", "750", "w"]`).
   - 100% filter parity with ChromaDB vector search (`category`, `max_price`, `in_stock_only`, `socket`, `ram_type`, `allowed_form_factors`, `min_wattage`, `max_gpu_length`, `cooler_kind`).

2. **Reciprocal Rank Fusion (RRF) Merger (`hybrid_search.py`):**
   - Merges vector rankings and BM25 rankings using canonical RRF formula $1 / (60 + \text{rank})$.
   - Naturally rewards items with consensus across both semantic meaning and lexical exactness.

3. **Cross-Encoder Reranker (`hybrid_search.py`):**
   - Integrated `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence-transformers`.
   - Scores $(query, candidate\_text)$ pairs on the top 20 merged shortlist in ~115ms on local CPU.

4. **Retriever Switch in Agent Tools (`tools.py` & `tool_models.py`):**
   - Added `retriever: Literal["vector", "hybrid", "hybrid_rerank"]` to `SearchPartsInput`.
   - Routes seamlessly through vector query, hybrid RRF merge, or cross-encoder reranking.

5. **30 Frozen Evaluation Queries (`agent-service/data/eval_queries_day9.json`):**
   - 10 exact model/chipset names, 10 attribute requirements, 10 descriptive requests.
   - Evaluated automatically against deterministic ground-truth rules without data snooping.

6. **Automated Evaluation Harness & Report (`eval_search.py` & `docs/day9-search-eval.md`):**
   - Produces 3-row evaluation matrix, group breakdown, and detailed failure analysis.

---

## 2. What Slipped

- **None.** All Day 9 planned tasks were completed on schedule.
- All 8 Day 8 review issues (soft boost, real item counts, cabinet form factor translation, rich PartCard fields, spelling normalization, error sanitization) remain verified and passing.

---

## 3. Honest Scores: 3-Row Evaluation Table

| Search Mode | Hit@5 (Recall@5) | Precision@5 | Avg Latency | Failing Queries (out of 30) |
|:---|:---:|:---:|:---:|:---:|
| **Vector-Only (`nomic-embed-text`)** | 83.3% | 60.7% | 2,247 ms | 5 |
| **Hybrid (Vector + BM25 via RRF)** | 83.3% | 66.0% (+5.3%) | 2,231 ms | 5 |
| **Hybrid + Cross-Encoder Rerank** | **90.0% (+6.7%)** | **71.3% (+10.6%)** | 2,499 ms | **3** |

### Breakdown by Query Type:
- **Exact Names/Codes (10 queries):**
  - Vector: 100% Hit@5, 72.0% Precision@5
  - Hybrid: 100% Hit@5, 74.0% Precision@5
  - Hybrid + Rerank: **100% Hit@5, 78.0% Precision@5**
- **Attribute Queries (10 queries):**
  - Vector: 80.0% Hit@5, 56.0% Precision@5
  - Hybrid: 70.0% Hit@5, 62.0% Precision@5
  - Hybrid + Rerank: **90.0% Hit@5, 66.0% Precision@5**
- **Descriptive Queries (10 queries):**
  - Vector: 70.0% Hit@5, 54.0% Precision@5
  - Hybrid: 80.0% Hit@5, 62.0% Precision@5
  - Hybrid + Rerank: **80.0% Hit@5, 70.0% Precision@5**

### Day 6 Miss Resolution:
- **"quiet 120 mm cooler":** In vector search, 240mm AIO coolers ranked ahead of air coolers due to semantic closeness to "quiet cooling". With BM25 tokenizing `120`, exact 120mm air coolers rank in the top 3.
- **"DDR5 32GB kit":** Vector search previously surfaced 16GB and DDR4 kits. Compound unit expansion (`32`, `gb`) ensures exact 32GB DDR5 kits take rank 1.

---

## 4. Is the Reranker Staying?

**VERDICT: YES, the reranker stays.**

### Reasons:
1. **Measurable Accuracy Lift:** It yields a **+6.7% gain in Hit@5** (up to 90.0%) and a **+10.6% gain in Precision@5** (up to 71.3%), cutting query failures from 5 down to 3.
2. **Acceptable Latency Overhead:** It adds only **~250 ms** of local CPU inference on the 20-candidate shortlist. For a PC builder agent loop where each search returns parts that will be verified and priced by subsequent tools, an extra quarter of a second for vastly more accurate candidates directly avoids costly agent retry loops.
3. **Dual-Mode Flexibility:**
   - Default: `retriever="hybrid"` for high-speed routine exploration (~2.2s).
   - High-Precision: `retriever="hybrid_rerank"` for critical component selections (~2.5s).

---

## 5. Readiness for Day 10

The search engine is now rock-solid:
- Real parts from 2,820 items are indexed in ChromaDB and cached in BM25 memory.
- Compatibility and pricing tools are verified with 91 tests.
- Day 10 agent loops (Supervisor → Architect → Critic → Reviewer) can now call deterministic tools with full confidence.
