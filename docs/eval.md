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
| C | New, upgrades off, Gemini | 5/10 (50%) | 1/1 (100%) | 5/10 (50%) | 0/10 (0%) | 9/10 (90%) | 1/10 (10%) |
| D | New, upgrades on, Gemini | 10/10 (100%) | 1/1 (100%) | 10/10 (100%) | 0/10 (0%) | 10/10 (100%) | 0/10 (0%) |
| E | New, upgrades off, Llama 3.1 8B | 2/10 (20%) | 1/1 (100%) | 2/10 (20%) | 0/10 (0%) | 9/10 (90%) | 1/10 (10%) |
| F | New, upgrades on, Llama 3.1 8B | 10/10 (100%) | 1/1 (100%) | 10/10 (100%) | 0/10 (0%) | 10/10 (100%) | 0/10 (0%) |

**Other requests, time, tokens and cost** (all 30 requests)

| Row | System | Comparisons | Impossible (hand-graded) | Off-topic | Vague | Median s | Avg tokens | Paid-equivalent $/request | Errored | Code version |
|---|---|---|---|---|---|---|---|---|---|---|
| A | Old Node system, Gemini | 5/5 (100%) | 1/5 (20%) | 4/5 (80%) | 4/5 (80%) | 9.4 | 5,438 | $0.00368 | 0 | a4ed31e (8 Nov, from the baseline notes) |
| C | New, upgrades off, Gemini | 4/5 (80%) | 0/5 (0%) | 5/5 (100%) | 0/5 (0%) | 10.3 | 2,723 | $0.00128 | 0 | fa18c90 |
| D | New, upgrades on, Gemini | 4/5 (80%) | 2/5 (40%) | 5/5 (100%) | 5/5 (100%) | 14.0 | 4,764 | $0.00240 | 0 | fa18c90 |
| E | New, upgrades off, Llama 3.1 8B | 4/5 (80%) | 0/5 (0%) | 5/5 (100%) | 0/5 (0%) | 6.7 | 2,225 | no per-token price | 0 | fa18c90 |
| F | New, upgrades on, Llama 3.1 8B | 4/5 (80%) | 3/5 (60%) | 5/5 (100%) | 5/5 (100%) | 14.1 | 4,006 | no per-token price | 0 | fa18c90 |
<!-- combined:end -->

All four new rows ran on 20 Nov 2026 at commit `fa18c90` (clean tree), 30/30 answered, 0 errored,
0 rate-limit retries. Per-run reports: `docs/eval-v2-off-gemini.md`, `docs/eval-v2-on-gemini.md`,
`docs/eval-v2-off-llama.md`, `docs/eval-v2-on-llama.md`. Hand grades were drafted by Claude and
**checked by the project owner on 21 Nov 2026** (no grade changed).

### What the numbers say

- **A vs D (headline, both Gemini 3.5 Flash-Lite):** valid builds **6/10 → 10/10**. Impossible
  requests 1/5 → 2/5: one request, so treat it as noise. Paid-equivalent cost **$0.00368 → $0.00240**
  per request (about a third cheaper; average tokens 5,438 → 4,764). It is **slower**: median
  9.4 s → 14.0 s, because one build is now about 10 small AI calls instead of one pass of 4 agents.
  One comparison is lost (5/5 → 4/5, see request 14 below).
- **C vs D (what the upgrades add, Gemini):** valid builds **5/10 → 10/10**, vague requests 0/5 → 5/5,
  impossible 0/5 → 2/5.
- **E vs F (what the upgrades add, Llama):** valid builds **2/10 → 10/10**, vague 0/5 → 5/5,
  impossible 0/5 → 3/5.
- **D vs F (Gemini vs local):** with the upgrades on, the local 8B model **matches** Gemini on builds
  (10/10 each), at the same median time (14.0 s vs 14.1 s). Impossible 2/5 vs 3/5 is one request: noise.
- **Not hidden:** with upgrades **off**, the new code on Gemini (C, 5/10) is one build below the old
  system (A, 6/10). One build is within noise, but the "off" setting is not better than the old system.

## 3. Failures of D and F

Every request that did not pass, after re-scoring with `checker.py` and the hand grades.

| Row | Request | Type | What went wrong | Kind of failure |
|---|---|---|---|---|
| D, F | 14 "Which is better, 550W PSU or 650W PSU?" | comparison | Sent down the **build** path: the router's compare rule knows "vs", "compare", "better than", but not "which is better". The answer recommends 650 W, then lists a full build. | Router rule miss |
| D | 17 "RTX 5080 and i5 12400 together in a 50k build" | impossible | A valid Rs.49,122 build with an RTX 3050 and a Ryzen 5 3600. Neither requested part is in it, and the reply never says so. | Silent substitution (no warning) |
| D, F | 19 "RTX 5070Ti and a 550W PSU" | impossible | Both quietly used a 750 W PSU (checker.py needs 700 W in D and 623 W in F). F's text even calls its PSU "550W", which contradicts the build. | Silent substitution; false spec in the AI's text (F) |
| D, F | 20 "Ryzen 5 5600 with an LGA1700 motherboard" | impossible | Both quietly picked an AM4 B550 board (compatible) and said it was chosen "to meet your request" / "the matching motherboard". | Silent substitution (no warning) |

Other findings:

- **No retrieval misses and no wrong refusals:** all 10 build requests gave a valid build in both D and F.
- **"No valid build in this budget"** was the right answer for 16 and 18 (and 17 in F). It was graded
  correct, but the reason given is mechanical ("no motherboard within Rs.1,980 fits"), not the real
  conflict (an RTX 5080 alone costs far more than Rs.15,000).
- **UNKNOWN checks never caused a failure,** but every build has one. In 9 of 10 requests the budget
  rule is UNKNOWN because no budget is stated (by design: see the budget rule). The rest is missing
  catalogue data: GPU length and cooler height.
- **Without the upgrades (C, E) the main failure is a CPU/motherboard socket mismatch.** Socket
  mismatches: C 4 of 5 failed builds, E 5 of 8; RAM type mismatches: C 1, E 4. All 10 vague-request
  builds in C and E fail on socket. In one-shot mode nothing ties the board to the CPU.

## 4. Three lessons

1. **Rules in code beat a better model.** The step-by-step picks, with each search filtered by code
   (the board's socket from the CPU, the RAM type from the board, the PSU watts from the checker),
   took valid builds from 5/10 to 10/10 on Gemini and from 2/10 to 10/10 on a local 8B model. Once
   code holds the rules, the small local model builds as well as Gemini.
2. **A valid build is not an honest answer.** The same filters that make every build valid also make
   impossible requests disappear quietly: the agent swaps in parts that work and never tells the user
   (D: 17, 19, 20; F: 19, 20). The explanation prompt forbids talking about compatibility and budget, so
   nobody says "you asked for X, that's not possible because Y, so I used Z". The fix belongs in code,
   like the price and the verdict: compare the parts and limits the user named with the final build, and
   write that line. *(A labelled follow-up; not built or run today.)*
3. **Read the failures, not the averages.** The averages look perfect on builds. The individual replies
   show a router gap ("which is better"), mechanical refusal reasons, and an AI sentence that states a
   false spec ("550W" for a 750 W PSU). The explanation filter blocks prices and verdicts, but not wrong
   specs.

## 5. Limits

- **Small sample.** 30 requests, 10 builds: one build = 10 points, so treat a one-build difference as
  noise. "Within budget" rests on one request (#2). Each row ran **once**. The optional repeat of D
  (to measure noise) was not run.
- **Temperature.** The 8 Nov baseline (A) ran at Gemini's default temperature; the new rows at 0.
- **Thin data, so "fully verified" is rare.** 2,820 parts, many without GPU length or cooler height,
  and 9 of 10 requests state no budget, so most builds keep an UNKNOWN rule. 0–1 of 10 builds per row
  are fully verified (every rule PASS).
- **"Valid" is not "what the user asked".** A build is valid when all 9 categories are present and no
  rule fails. It can still ignore parts the user named (lesson 2).
- **Hand grades.** Requests 16–20 of rows C–F were graded by Claude with the baseline rubric
  (reasons in `eval/grades-v2-*.json`) and checked by the project owner, who kept every grade. One grader
  and one reviewer is still a small check.
- **Time.** The Gemini rows also use the local machine (Ollama embeddings, the reranker), and D ran at
  the same time as F and E, so the Gemini rows' seconds may include waiting for the shared machine.
  Seconds exclude the runner's 30 s pacing waits. Row A's 8 Nov times may include retry waits (median used).
- **Cost** is paid-equivalent at the list price read on 20 Nov 2026 (the free tier actually cost $0).
  Row A's tokens come from the old system's Gemini usage records, with the same model and the same price.
- **Row B was skipped**, so "what scale does" (24 parts vs 2,820) is not measured.
