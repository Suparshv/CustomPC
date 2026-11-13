# Day 6 Milestone: Local Vector Index & Retrieval Evaluation

## Overview

Day 6 replaces v1's per-startup embedding bottleneck (which called Gemini once per part for 24 parts) with an offline, local vector search index across the entire 2,820 component catalog stored in Chroma collection `parts_nomic_v1`.

Embeddings are generated locally using `nomic-embed-text` (768 dimensions) via Ollama with `keep_alive="1h"`, running at zero API cost, with zero rate limits, and serving both Gemini and local Ollama agents.

---

### Key Capabilities & Enhancements Added

1. **Local Embedding Service (`agent-service/embeddings.py`):**
   - Wraps `ollama.Client().embed(model="nomic-embed-text", input=[...], keep_alive="1h")` with zero API cost and zero cold-start GPU unload latency.
   - Enforces required model training prefixes:
     - `search_document: ` for part descriptions.
     - `search_query: ` for search queries.
     - Strictly guards against double prefixing.
   - Batching in groups of 64 with exponential backoff retry handling on Ollama API failures.

2. **Semantic Text & Metadata Builders (`agent-service/build_index.py`):**
   - **`describe(doc)`:** Constructs natural sentences per component category. Prices are deliberately excluded from sentence text because numbers embed poorly and distort semantic similarity.
   - **Cooler Distinction:** Distinguishes liquid coolers (`liquid (AIO) CPU cooler, {size} mm radiator`) from air coolers (`air CPU cooler`).
   - **`build_metadata(doc)`:** Builds clean filterable metadata containing only valid simple types (`str`, `int`, `float`, `bool`) and strictly omitting any missing/None fields.
   - **Hardware & Filter Keys:** Includes compatibility keys (`socket`, `ram_type`, `form_factor`, `wattage`, `tdp`, `length`, `capacity`, `speed_mhz`, `efficiency`, `chipset`, `cooler_kind`, `case_type`, `gpu_memory`).

3. **Incremental Synchronization & Zero-Cost Metadata Updates (`build_index.py`):**
   - **Dual Hashes:** Storing both `doc_hash` (`f"{model}:{text}"`) and `meta_hash` (`hash(metadata)`).
   - **Fast Metadata-Only Updates:** When only price or stock status changes in MongoDB, Chroma's metadata is updated via `collection.update()` without re-embedding (0 embedding calls, $< 1$s).
   - **Idempotency:** Re-running with unchanged data skips all 2,820 components in **0.39 seconds** with **0 components re-embedded**.
   - **Safety Guards:**
     - Aborts if MongoDB returns 0 documents to prevent wiping the vector index.
     - Mass deletion guard prevents deleting $>50\%$ of the collection without explicit `ALLOW_MASS_DELETION=1`.
     - Explicit server connection check requiring `CHROMA_ALLOW_FALLBACK=1` for fallback to local files.

4. **Multi-Condition `$and` Vector Search (`agent-service/search_check.py`):**
   - Evaluated 8 diverse queries against the 2,820-part catalog.
   - Verified that compound filtering requires Chroma's `$and` operator (e.g. `{"$and": [{"category": "gpu"}, {"price": {"$lte": 30000.0}}]}`).
   - Documented exact findings and real misses in [`docs/day6-search-notes.md`](./day6-search-notes.md) to motivate Day 9's hybrid search (dense + BM25 + Cross-Encoder reranker).

---

## Verification Checklist

| Requirement | Target | Achieved | Status |
|---|---|---|---|
| Chroma Collection Count | Matches Mongo (`2,820`) | **2,820 / 2,820** | Verified |
| Second Run Idempotency | 0 embeds, $< 5$s | **0 embeds, 0.39s** | Verified |
| Metadata Update on Price/Stock Change | 0 embeds, updates Chroma metadata | **0 embeds, 0.73s** | Verified |
| Empty DB & Mass Deletion Guards | Abort on 0 docs / $>50\%$ deletion | **Verified** | Verified |
| Ollama Embedding Model | `nomic-embed-text` with `keep_alive="1h"` | **768-dim vectors** | Verified |
| Training Prefixes | Applied strictly once | **Verified in unit tests** | Verified |
| Cooler Distinction | Liquid (AIO) vs Air | **Verified in unit tests & search** | Verified |
| Compound Filtering | Multi-condition `$and` | **Verified in search_check** | Verified |
| Unit Tests | Complete offline test suite | **45 / 45 passed** | Verified |

---

## Test Execution

```powershell
.\agent-service\.venv\Scripts\pytest -q
.............................................                            [100%]
45 passed in 3.33s
```
