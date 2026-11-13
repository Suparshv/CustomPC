# Agent Service Microservice

A Python / FastAPI service providing structured output generation, schema validation, catalogue cross-referencing, and automated retry loops across cloud (Gemini) and local (Ollama) LLMs.

## Quickstart

### 1. Setup Virtual Environment & Install Dependencies
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configuration
Copy `.env.example` to `.env` and fill in your keys:
```env
LLM_PROVIDER=gemini        # 'gemini' or 'ollama'
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
OLLAMA_MODEL=llama3.1:8b
OLLAMA_NUM_CTX=8192
OLLAMA_HOST=http://localhost:11434
MONGODB_URI=mongodb://127.0.0.1:27017/PC
USD_TO_INR_RATE=93.0
USD_TO_INR_DATE=2026-11-12
```

### 3. Ingest Component Catalog (Day 5)
Ingest a portfolio-scale catalog of ~2,820 recent PC components (2,796 from PCPartPicker dataset + 24 frozen seed parts) into MongoDB `catalog_parts`:
```bash
python ingest_parts.py
```
- Fully idempotent: running multiple times upserts 0 additional documents.
- Includes indexes on `category` and `source`.
- Deterministic simulated stock (~92%) and currency conversion ($1 = ₹93.0).
- Automatic deletion of stale dataset documents upon re-ingestion.

> [!NOTE]
> **Catalogue Coverage Limit:** Only one LGA1700 DDR5 board qualifies (`ASRock H610M-HDV/M.2+ D5`, as most LGA1700 board names in the raw dataset omit "DDR5" explicitly). Consequently, Intel DDR5 builds will mostly draw from Core Ultra (LGA1851), while 12th–14th gen Intel builds will primarily pair with DDR4.

### 4. Build Chroma Vector Search Index (Day 6)
Embed all components locally with `nomic-embed-text` into the Chroma collection `parts_nomic_v1`:
```bash
# 1. Start Ollama and Chroma server (if not already running)
ollama serve
chroma run --path ./data/chroma --port 8000

# 2. Build or incrementally sync index
python build_index.py
```
- Formats components into natural sentences (leaving price out of text).
- Stores category, price, stock, and compatibility fields as filterable metadata.
- Applies `search_document: ` and `search_query: ` prefixes for optimal retrieval.
- Incremental sync: tracks text hashes; re-running embeds 0 parts and finishes in $< 1$s.

### 5. Vector Search Verification & Baseline
```bash
python search_check.py
```
Runs 8 test queries including multi-condition `$and` filtering and logs findings to [`docs/day6-search-notes.md`](../docs/day6-search-notes.md).

### 6. Run the Service
```bash
uvicorn main:app --port 8001 --reload
```

- Health check: `GET http://localhost:8001/health`
- Draft build debug: `POST http://localhost:8001/debug/draft-build` with `{"message": "Build me a gaming PC under 80000"}`

### 7. Run Tests & Smoke Evaluation
```bash
# Run unit & regression test suite (42 tests)
pytest -q

# Run 20-prompt smoke test with the active provider
python smoke_test.py
```
