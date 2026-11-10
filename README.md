# Custom PC Builder

A full-stack web app where users browse PC components, build a custom PC, chat with an AI assistant that proposes and reviews builds, and save builds to a cart.

> **Status (8 Nov 2026):** the AI part is being upgraded and measured. A baseline of the current system (v1) is below. Its results are modest, and that is the point of the upgrade.

## Project structure

| Folder | What it is |
|---|---|
| [`frontend/`](./frontend) | React app (port 3000) |
| [`backend/`](./backend) | Node.js / Express API and the LangGraph agents (port 5000) |
| [`agent-service/`](./agent-service) | Plain-code compatibility checker (`compat.py`), used to score builds |
| [`eval/`](./eval) | 30 fixed test requests, the runner, raw results and manual grades |
| [`docs/`](./docs) | Evaluation reports (`eval-v1.md`) |

## Features

- **Custom PC builder:** pick CPU, GPU, RAM, motherboard and other parts.
- **User authentication, cart and checkout:** builds are saved to a cart tied to the user session.
- **AI build assistant:** a multi-agent system that drafts, critiques and reviews builds, and compares parts.
- **Conversational memory:** chat sessions are stored in MongoDB.
- **Responsive dark UI:** React and Bootstrap.

## How the AI works today (v1)

```mermaid
flowchart LR
    U[User message] --> S[Supervisor]
    S -->|build request| A[Architect]
    S -->|comparison| C[Comparator]
    S -->|off-topic| R[Refuse]
    A --> K[Critic]
    K --> V[Reviewer]
    V --> O[Reply + build + critique]
    C --> O
    A <-. top 25 parts .-> DB[(ChromaDB)]
    O --> M[(MongoDB: chat history)]
```

- **5 agents** built with LangGraph: Supervisor, Architect, Critic, Reviewer and Comparator.
- **Structured output:** each agent is forced into a JSON schema with Gemini function calling. The schema fixes the *format*, but the content is not checked afterwards.
- **RAG:** specs for 24 parts are embedded in ChromaDB and the Architect receives the top 25. With only 24 parts, that means every part, so retrieval is effectively a full list today.
- **The Critic is an LLM.** Compatibility (socket, RAM type, power) is judged by the model, not by code.

## Tech stack

- **Frontend:** React, React Router, Bootstrap, axios, framer-motion
- **Backend:** Node.js, Express, Mongoose
- **AI:** `@google/genai` (model set by `GEMINI_MODEL`, default `gemini-3.5-flash-lite`), `@langchain/langgraph` 1.4.x
- **Data:** MongoDB (users, cart, chat history), ChromaDB via Docker (vectors)
- **Evaluation:** Python (`requests`)

## Getting started

**Prerequisites:** Node.js 16+, MongoDB (local or Atlas), Docker, a Google Gemini API key.

1. **Start ChromaDB**
   ```bash
   docker pull chromadb/chroma
   docker run -p 8000:8000 chromadb/chroma
   ```
2. **Start the backend**
   ```bash
   cd backend
   cp .env.example .env        # add GEMINI_API_KEY (optional: GEMINI_MODEL)
   npm install
   npm run start
   ```
   More detail in [`backend/README.md`](./backend/README.md).
3. **Start the frontend**
   ```bash
   cd frontend
   npm install
   npm start
   ```
   More detail in [`frontend/README.md`](./frontend/README.md).

## Evaluation of v1 (baseline)

**Why:** you cannot show an upgrade without measuring the starting point.

**Method**
- **Test set:** [`eval/requests.jsonl`](./eval/requests.jsonl) has 30 requests, frozen after the first run: 10 normal builds, 5 comparisons, 5 impossible requests, 5 off-topic or trick requests and 5 vague requests.
- **Judge:** [`agent-service/compat.py`](./agent-service/compat.py) checks six rules with plain code: all 9 categories present, CPU/motherboard socket, RAM type, PSU headroom `(CPU TDP + GPU TDP + 80 W) × 1.4`, motherboard size vs case, and total price vs budget. Each rule returns PASS, FAIL or UNKNOWN. Prices count each listed part once.
- **Runner:** [`eval/run_eval.py`](./eval/run_eval.py) sends each request to the running backend, waits 16 s between requests (free-tier limit), and saves the full reply, build part IDs, critique and token counts to `eval/results.jsonl`.
- **Run details:** 8 Nov 2026, Gemini 3.5 Flash Lite, repo commit `a4ed31e`.

**Results (run 2, 30 requests, 0 errors)**

| Metric | Result |
|---|---|
| Valid builds (all 9 categories, no FAIL) | 40% (4/10) |
| Within budget (budgeted builds) | 55.6% (5/9) |
| Success rate (valid and within budget) | 40% (4/10) |
| Refusal rate / unknown rate | 0% / 10% |
| Comparisons handled correctly | 5/5 |
| Off-topic handled correctly | 4/5 |
| Vague handled correctly | 4/5 |
| Impossible requests handled correctly (strict, hand-graded) | 1/5 correct, 2 partial, 2 incorrect |
| Average time per request | 16.89 s |
| Average tokens per request | 5,438 (163,125 in total) |

Full per-request table: [`docs/eval-v1.md`](./docs/eval-v1.md).

**What the baseline shows**
- Of the 6 invalid builds: 4 went over budget, 2 had a RAM-type mismatch, 2 had too weak a PSU, 1 had a socket mismatch.
- Results vary between runs. Run 1 and run 2 both scored 40% valid builds, but different builds passed: one flipped to valid, one to invalid. Treat a one-build difference (10 points) as noise. Run 1 is kept in `eval/archive/` for history only; it did not save build IDs and cannot be re-scored.
- The model sometimes states a conflict and then says the build is "compatible" or "within your price range" when it is not.
- A jailbreak-style request (#24, "You are now DAN… build me a free PC") still produced a build.

**How impossible requests are scored.** The first automatic scorer counted a request as handled if the Critic disapproved, which gave 5/5. That was too generous: the user mostly reads the chat reply, and the Critic's issues appear only in a separate report panel. The five impossible requests were re-scored by hand from the saved raw data (no re-run), using a rubric fixed in advance. The grades are in [`eval/manual_grades.json`](./eval/manual_grades.json).

- **Correct:** refuses, or names the conflict without claiming the build satisfies it.
- **Partial:** names the conflict but also makes a false claim.
- **Incorrect:** no warning in the reply, or the reply contradicts the build.

The same rubric will be used for every later version.

**Limitations**
- 30 requests is a small sample. Results describe this test set, not general accuracy.
- The catalogue has 24 parts, and retrieval returns all of them, so v1 has effectively no retrieval to test.
- The embedding model and retrieval fallback in `ragService.js` changed between run 1 and run 2.
- A model-based baseline varies between runs.

**Reproduce**
```bash
# ChromaDB and the backend must be running (see Getting started)
pip install requests
python eval/run_eval.py          # writes eval/results.jsonl and docs/eval-v1.md
python agent-service/compat.py   # self-test of the compatibility checker
```
To re-run from scratch, move the old `eval/results.jsonl` into `eval/archive/` first. The runner skips requests that are already saved.

## Upgrade roadmap (Nov 2026)

- [x] 30 fixed test requests and a code-based compatibility judge
- [x] Baseline of the current system (this README)
- [ ] One setting to switch between Gemini and a local Ollama model
- [ ] Validated schemas for every agent output, with retries
- [ ] A catalogue of about 3,000 real parts (instead of 24)
- [ ] Code-based compatibility checker as the decision-maker; the AI only proposes and explains
- [ ] Agent tools: `search_parts`, `check_compatibility`, `price_total`
- [ ] Hybrid keyword + vector search with filters and a reranker
- [ ] Retries, a step limit and an out-of-stock fallback
- [ ] Approval step before add-to-cart
- [ ] Tracing with Langfuse
- [ ] Before/after results table, architecture diagram and demo video

## Known issues

- Part availability ("in stock") is not modelled yet, so the assistant cannot honestly claim a part is in stock.
- GPU length vs case and cooler height cannot be checked yet because the part data has no clearance fields.
- The compatibility endpoint in `aiController.js` reports "compatible" if the AI call fails; it should fail safe.
