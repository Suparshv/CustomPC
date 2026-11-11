# Day 4 Milestone: Local Model (Ollama), Retries & Catalogue Validation

## Overview

Day 4 integrates a local open-weights LLM running offline on GPU alongside Google Gemini, unified by a shared validation and retry orchestration layer.

### Key Capabilities Added
1. **Local Model Execution:** Ollama running `llama3.1:8b` (4-bit quantized) with 100% offload onto the local NVIDIA RTX 4060 GPU and context window expanded to 8,192 tokens (`OLLAMA_NUM_CTX=8192`).
2. **Two-Layer Architecture:**
   - **Low-Level Provider Layer (`_complete`):** Talks directly to provider APIs (Google Gemini via `google-genai` and Ollama via `ollama.Client`).
   - **High-Level Orchestration Layer (`BaseLLM.generate`):** Handles Pydantic schema parsing, catalogue cross-checks, token accumulation across attempts, and dynamic error feedback retry loops (up to 2 retries / 3 attempts total).
3. **Catalogue Integrity Check (`catalog.py`):** Cross-checks part IDs against `ALL_SPECS`. Rejects non-existent IDs (e.g. `g99`) and category mismatches (e.g. CPU listed as GPU) before returning.
4. **Resilient Error Serialization & Health Checks:**
   - Pydantic validation errors use `e.errors(include_url=False, include_context=False)`, resolving the HTTP 500 regression on custom validator exceptions and returning a structured HTTP 422.
   - `/health` actively verifies provider connectivity (pinging Ollama via `client.list()` and checking that the configured model is pulled), returning HTTP 503 Service Unavailable when the daemon is offline.
   - Provider connection errors in `/debug/draft-build` cleanly map to HTTP 503 instead of unhandled 500 crashes.

---

## 20-Prompt Smoke Test Evaluation

Tested on 20 newly authored, independent prompts (10 full builds with budgets, 4 single-component requests, 3 vague requests, and 3 edge cases) from `agent-service/tests/smoke_prompts.txt`, completely separate from the 30 frozen test cases in `eval/requests.jsonl`:

| Provider | Model | Execution Environment | Well-Formed Output ($\le 3$ tries) | First-Try Valid | Avg Attempts | Avg Tokens | Avg Latency |
|---|---|---|---|---|---|---|---|
| **Gemini** | `gemini-3.5-flash-lite` | Cloud API | **20/20 (100.0%)** | 20/20 (100.0%) | 1.00 | 1,332.5 | 2.07 s |
| **Ollama** | `llama3.1:8b` | Local RTX 4060 (100% GPU) | **20/20 (100.0%)** | 20/20 (100.0%) | 1.00 | 1,173.0 | 3.11 s |

> [!NOTE]
> **Clarification on "Well-Formed Output" vs "Valid Build":**
> "Well-formed output" means the model strictly adhered to the Pydantic schema, populated the `build` list with actual component IDs (empty builds are rejected), kept part IDs out of the reply text, and extracted budgets accurately via deterministic regex code. **It does NOT mean the build is hardware-compatible or within budget.** Deep hardware compatibility (CPU socket matching, DDR generation matching, PSU headroom) will be enforced by plain-code tools on Day 7.
>
> Both models scored 100% on the first attempt across all 20 prompts. The self-correction retry loop and token-accumulation logic are verified via unit tests in `test_retry_and_catalog.py`.

### Raw Per-Prompt Audit Files
- Gemini: [`agent-service/tests/smoke_results_gemini.json`](../agent-service/tests/smoke_results_gemini.json)
- Ollama: [`agent-service/tests/smoke_results_ollama.json`](../agent-service/tests/smoke_results_ollama.json)

---

## Unit & Regression Tests

All 30 unit and regression tests pass offline:
```powershell
.\agent-service\.venv\Scripts\pytest -q
..............................                                           [100%]
30 passed in 0.88s
..........................                                               [100%]
26 passed in 0.86s
```
Covering:
- Route, DraftBuild, Critique, Reviews, and Comparison schema validation.
- Retries succeeding on second attempt with summed token counting.
- Retries giving up after 3 attempts with preserved token/latency metrics in `LLMValidationError`.
- Recovery from empty responses.
- Catalogue check rejecting unknown IDs and category mismatches.
- Duplicate IDs returning HTTP 422 with string problem descriptions.
- Closed-port connection errors returning HTTP 503 on `/health` and `/debug/draft-build`.
