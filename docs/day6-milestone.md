# Day 6 Milestone: Local Vector Index & Retrieval Evaluation

## Overview

Day 6 replaces v1's per-startup embedding bottleneck (which called Gemini once per part for 24 parts) with an offline, local vector search index across the entire 2,820 component catalog stored in Chroma collection `parts_nomic_v1`.

Embeddings are generated locally using `nomic-embed-text` (768 dimensions) via Ollama, running at zero API cost, with zero rate limits, and serving both Gemini and local Ollama agents.

---

### Key Capabilities Added

1. **Local Embedding Service (`agent-service/embeddings.py`):**
   - Wraps `ollama.Client().embed(model="nomic-embed-text", input=[...])`.
   - Strictly enforces required training prefixes:
     - `search_document: ` for part descriptions.
     - `search_query: ` for search queries.
   - Batching in groups of 64 with exponential backoff retry handling.

2. **Semantic Text & Metadata Builders (`agent-service/build_index.py`):**
   - **`describe(doc)`:** Constructs natural sentences per component category. Numerical prices are deliberately excluded from the text so as not to distort semantic embeddings.
   - **`build_metadata(doc)`:** Builds clean filterable metadata containing only valid simple types (`str`, `int`, `float`, `bool`) and strictly omitting any missing/None fields.
   - Includes compatibility keys (`socket`, `ram_type`, `form_factor`, `wattage`, `tdp`, `length`, `capacity`, `speed_mhz`, `efficiency`, `chipset`).

3. **Incremental Synchronization & Cheap Re-runs (`build_index.py`):**
   - Computes a deterministic hash of each component's descriptive sentence (`doc_hash`).
   - On startup, compares current hashes against Chroma's existing metadata:
     - Only **new** or **modified** components are embedded.
     - Unchanged components are skipped.
     - Stale components removed from MongoDB are pruned.
   - **Performance:** Initial full index completed in ~157 seconds. Re-running completes in **0.37 seconds** with **0 components re-embedded**.

4. **Multi-Condition `$and` Vector Search (`agent-service/search_check.py`):**
   - Evaluated 8 diverse queries against the 2,820-part catalog.
   - Verified that compound filtering requires Chroma's `$and` operator (e.g. `{"$and": [{"category": "gpu"}, {"price": {"$lte": 30000.0}}]}`).
   - Documented exact findings and baseline misses in [`docs/day6-search-notes.md`](./day6-search-notes.md) to motivate Day 9's hybrid search (dense + BM25 + Cross-Encoder reranker).

---

## Verification Checklist

| Requirement | Target | Achieved | Status |
|---|---|---|---|
| Chroma Collection Count | Matches Mongo (`2,820`) | **2,820 / 2,820** | Verified |
| Second Run Idempotency | 0 embeds, $< 5$s | **0 embeds, 0.37s** | Verified |
| Ollama Embedding Model | `nomic-embed-text` | **768-dim vectors** | Verified |
| Training Prefixes | Applied strictly once | **Verified in unit tests** | Verified |
| Compound Filtering | Multi-condition `$and` | **Verified in search_check** | Verified |
| Offline Unit Tests | Cover text, meta, prefix, hash, re-run | **42 / 42 passed** | Verified |

---

## Test Execution

```powershell
.\agent-service\.venv\Scripts\pytest -q
..........................................                               [100%]
42 passed in 3.00s
```
