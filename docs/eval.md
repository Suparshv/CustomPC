# Evaluation: before and after (Day 13)

The same 30 frozen requests, sent to the old system and to the new agent, every answer scored by
the same judge. This file was written **before the first run** (20 Nov 2026), so the settings of
every row were fixed before any result was seen.

## 1. The plan (frozen before the runs)

| Row | System | Model | Switches | Results / report / hand grades |
|---|---|---|---|---|
| A | Old Node system (done 8 Nov, re-scored 17 Nov) | Gemini 3.5 Flash-Lite | n/a | `eval/results.jsonl` / `docs/eval-v1.md` / `eval/manual_grades.json` |
| B | *Skipped* (see below) | | | |
| C | New agent, upgrades **off** | Gemini 3.5 Flash-Lite | `{"retriever":"vector","use_tools":false,"use_checker":false,"repair_loops":0}` | `eval/results-v2-off-gemini.jsonl` / `docs/eval-v2-off-gemini.md` / `eval/grades-v2-off-gemini.json` |
| D | New agent, upgrades **on** | Gemini 3.5 Flash-Lite | defaults: `hybrid_rerank`, tools, checker, 2 repairs | `eval/results-v2-on-gemini.jsonl` / `docs/eval-v2-on-gemini.md` / `eval/grades-v2-on-gemini.json` |
| E | New agent, upgrades **off** | Llama 3.1 8B (Ollama) | same as C | `eval/results-v2-off-llama.jsonl` / `docs/eval-v2-off-llama.md` / `eval/grades-v2-off-llama.json` |
| F | New agent, upgrades **on** | Llama 3.1 8B (Ollama) | same as D | `eval/results-v2-on-llama.jsonl` / `docs/eval-v2-on-llama.md` / `eval/grades-v2-on-llama.json` |

**Comparisons:** A vs D (the headline), C vs D and E vs F (what the upgrades add), D vs F (Gemini vs local).

**Row B skipped (decided 20 Nov, before any run).** It needs a new `catalogue` switch in the agent
code and one more Gemini run. We kept the agent code unchanged on the day of the proof runs, and
kept the Gemini quota for the headline rows. So "what scale does" (B vs C) is not measured.

### Fixed settings

- **Test set:** `eval/requests.jsonl`, unchanged since commit `0106438` (8 Nov).
  SHA-256 `12d708d77f6ce861fc304a8431d84584b8c81177778596dcef3307a23504ac5f`.
- **Judge:** `eval/run_eval.py` + `agent-service/checker.py`, with part data read from MongoDB, for every row.
- **Budget rule:** a build is judged only against a budget the request text states. Only request #2 does.
- **Code version:** every new row records the git commit it ran on (and any uncommitted files) in its results file.
- **Temperature:** 0 for the new agent (both providers). The 8 Nov baseline ran at Gemini's default temperature.
- **Services:** Gemini agent on port 8001 (`LLM_PROVIDER=gemini`), Llama agent on port 8002
  (`LLM_PROVIDER=ollama`), one Chroma server on port 8000 serving `agent-service/data/chroma`
  (2,820 parts, the same count as MongoDB `catalog_parts`), MongoDB, Ollama.
- **Pacing:** `--wait 30` for Gemini rows (about 10 AI calls per request; free tier), `--wait 0` for Llama rows.
- **Order:** D and F first, in parallel; then C and E, in parallel.
- **Commands** (from the repo root, `python` = `agent-service/.venv/Scripts/python.exe`):

```bash
# D
python eval/run_eval.py --target agent --agent-url http://127.0.0.1:8001/agent/build --wait 30 \
  --results eval/results-v2-on-gemini.jsonl --report docs/eval-v2-on-gemini.md \
  --grades eval/grades-v2-on-gemini.json --title "v2 upgrades on, Gemini"
# F
python eval/run_eval.py --target agent --agent-url http://127.0.0.1:8002/agent/build --wait 0 \
  --results eval/results-v2-on-llama.jsonl --report docs/eval-v2-on-llama.md \
  --grades eval/grades-v2-on-llama.json --title "v2 upgrades on, Llama 3.1 8B"
# C and E: the same on ports 8001 / 8002, plus
#   --overrides '{"retriever":"vector","use_tools":false,"use_checker":false,"repair_loops":0}'
# and the -off- file names.
```

### Hand grading (requests 16–20, every run)

The same rubric as the baseline (`eval/manual_grades.json`):

- **correct:** refuses, or the chat reply names the conflict without claiming the returned build satisfies it;
- **partial:** names the conflict but also makes a false claim (for example "compatible" or "within your price range");
- **incorrect:** no warning in the chat reply, or the reply contradicts the build.

Only "correct" counts in the headline. Each grade is tied to the exact reply (sha256 fingerprint).
Claude drafts the grades with a reason for each; the human checks and may change them before commit.

### Cost

Gemini's free tier costs $0. The **paid-equivalent** cost uses the Standard paid-tier price of
`gemini-3.5-flash-lite`, read from Google's pricing page (aistudio.google.com/docs/pricing) on
**20 Nov 2026**: **$0.30 per 1M input tokens, $2.50 per 1M output tokens** (output includes
thinking tokens; a test call on 20 Nov returned no thinking tokens, and the baseline's saved
token records have none). Llama runs locally: no per-token price, so we report tokens and seconds.

### Noise

Two baseline runs both scored 4/10 valid builds, but two of the ten builds changed. With 10 build
requests, **one build is 10 percentage points**: treat a one-build difference as noise.

## 2. Combined results

Built by `python eval/combine_eval.py` from the saved results files (no hand-typed numbers).

<!-- combined:start -->
**Build requests** (10 per run)

| Row | System | Valid builds | Within budget | Success | Refused | Unknown | Fully verified |
|---|---|---|---|---|---|---|---|
| A | Old Node system, Gemini | 6/10 (60%) | 1/1 (100%) | 6/10 (60%) | 0/10 (0%) | 10/10 (100%) | 0/10 (0%) |
| C | New, upgrades off, Gemini | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |
| D | New, upgrades on, Gemini | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |
| E | New, upgrades off, Llama 3.1 8B | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |
| F | New, upgrades on, Llama 3.1 8B | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |

**Other requests, time, tokens and cost** (all 30 requests)

| Row | System | Comparisons | Impossible (hand-graded) | Off-topic | Vague | Median s | Avg tokens | Paid-equivalent $/request | Errored | Code version |
|---|---|---|---|---|---|---|---|---|---|---|
| A | Old Node system, Gemini | 5/5 (100%) | 1/5 (20%) | 4/5 (80%) | 4/5 (80%) | 9.4 | 5,438 | $0.00368 | 0 | a4ed31e (8 Nov, from the baseline notes) |
| C | New, upgrades off, Gemini | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |
| D | New, upgrades on, Gemini | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |
| E | New, upgrades off, Llama 3.1 8B | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |
| F | New, upgrades on, Llama 3.1 8B | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |
<!-- combined:end -->

## 3. Failures of D and F

*(After the runs.)*

## 4. Three lessons

*(After the runs.)*

## 5. Limits

*(After the runs.)*
