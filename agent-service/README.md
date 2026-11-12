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
Ingest ~2,854 recent PC components (2,830 from PCPartPicker dataset + 24 frozen seed parts) into MongoDB `catalog_parts`:
```bash
python ingest_parts.py
```
- Fully idempotent: running multiple times upserts 0 additional documents.
- Includes indexes on `category` and `source`.
- Deterministic simulated stock (~92%) and currency conversion ($1 = ₹93.0).

### 4. Run the Service
```bash
uvicorn main:app --port 8001 --reload
```

- Health check: `GET http://localhost:8001/health`
- Draft build debug: `POST http://localhost:8001/debug/draft-build` with `{"message": "Build me a gaming PC under 80000"}`

### 5. Run Tests & Smoke Evaluation
```bash
# Run unit & regression test suite (35 tests)
pytest -q

# Run 20-prompt smoke test with the active provider
python smoke_test.py
```
