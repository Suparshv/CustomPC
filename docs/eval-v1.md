# Evaluation Report: v1-baseline

> Measured on 30 fixed test requests on 2026-11-08 21:41 (re-scored 2026-11-17).
> This is a small sample. Results describe this specific test set, not general accuracy.

> **Re-scored for the before/after comparison** (re-scored on project Day 10). No requests were
> re-run: these are the saved 8 Nov replies (`eval/results.jsonl`, Gemini 3.5 Flash Lite, commit
> `a4ed31e`) scored again with the CURRENT scorer and judge, so the old and the new system are
> measured the same way.
>
> - **Judge:** `agent-service/checker.py` with parts read from MongoDB, the same code the new
>   system's `check_compatibility` tool uses. The 8 Nov report used `compat.py` (6 rules, 24 parts),
>   which cannot judge the new ~3,000-part catalogue. `checker.py` agrees with `compat.py` on every
>   saved build.
> - **Budget rule (changed on Day 10):** a build is judged against the budget the request TEXT
>   states (read by code), and only then. 9 of the 10 build requests state no budget; the 8 Nov
>   scoring judged them against a hidden budget in the test file that the system never saw. With no
>   stated budget there is no price limit to break, so any compatible build is valid. The test file
>   is not edited; its `budget` field is no longer used for judging. Only request #2 ("under 1 lakh")
>   states a budget, so "within budget" rests on 1 build: compare **valid builds** first.
> - **Old rule -> new rule:** valid builds 4/10 -> **6/10**, within budget 5/9 -> **1/1**,
>   success 4/10 -> **6/10**.
> - **Unchanged:** refusals 0/10, comparisons 5/5, impossible 1/5 (hand-graded), off-topic 4/5,
>   vague 4/5.
> - **New judge, more rules:** the unknown rate was 1/10 and is now 10/10, because the new judge also
>   checks cooler height and the old parts have no cooler-height data. For the same reason 0/10 old
>   builds are "fully verified" (every rule PASS).
> - **Time:** the 8 Nov times include any time the runner spent waiting before a retry (it did not
>   record retries then). Ids 17 and 18 (about 60 s) probably include such a wait. Compare the
>   **median** time; new runs record retry waits separately.

## Summary Table

| Metric | Value |
|--------|-------|
| Valid builds (no FAIL, all 9 categories) | 60.0% (6/10) |
| Within budget (among budgeted builds) | 100.0% (1/1) |
| Refusal rate (build requests declined) | 0.0% (0/10) |
| Unknown rate (a check could not run: missing data) | 100.0% (10/10) |
| Fully verified builds (every rule PASS) | 0.0% (0/10) |
| Comparisons handled correctly | 100.0% (5/5) |
| Impossible requests handled correctly (strict) | 20.0% (1/5) |
| Impossible requests breakdown | 1 correct, 2 partial, 2 incorrect (hand-graded) |
| Off-topic requests handled correctly | 80.0% (4/5) |
| Vague requests handled correctly | 80.0% (4/5) |
| Avg time per request | 16.89s |
| Median time per request | 9.36s |
| Avg tokens per request | 5438 |
| Total tokens used | 163125 |
| Errored requests (left out of every rate) | 0 |

## Three Key Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Success rate** | 60.0% | Valid and compatible builds within budget, out of all build requests |
| **Refusal rate** | 0.0% | How often the system declined a build request |
| **Unknown rate** | 100.0% | Checks that could not run due to missing spec data |

## Per-Request Breakdown

| ID | Type | Budget | Time | Tokens | Result | Details |
|----|------|--------|------|--------|--------|---------|
| 1 | normal_build | - (not stated) | 7.72s | 7355 | PASS | All categories present, no compatibility failures |
| 2 | normal_build | Rs.100,000 | 7.59s | 7325 | PASS | All categories present, no compatibility failures |
| 3 | normal_build | - (not stated) | 8.87s | 7572 | PASS | All categories present, no compatibility failures |
| 4 | normal_build | - (not stated) | 7.68s | 7769 | FAIL | ram_type_match |
| 5 | normal_build | - (not stated) | 7.99s | 7897 | FAIL | ram_type_match, psu_headroom |
| 6 | normal_build | - (not stated) | 9.75s | 7281 | PASS | All categories present, no compatibility failures |
| 7 | normal_build | - (not stated) | 19.21s | 7369 | PASS | All categories present, no compatibility failures |
| 8 | normal_build | - (not stated) | 23.53s | 7351 | PASS | All categories present, no compatibility failures |
| 9 | normal_build | - (not stated) | 29.27s | 8100 | FAIL | psu_headroom |
| 10 | normal_build | - (not stated) | 8.63s | 7408 | FAIL | socket_match |
| 11 | comparison | - (not stated) | 3.52s | 1350 | CORRECT | The RTX 4060 offers better frame rates and lower power draw, while the RTX  |
| 12 | comparison | - (not stated) | 3.92s | 1408 | CORRECT | The MSI RTX 5080 is superior for 4K gaming, delivering around 90fps in dema |
| 13 | comparison | - (not stated) | 42.9s | 1431 | CORRECT | Comparing the Intel i5 12400 and AMD Ryzen 5 5600: The Intel i5 12400 costs |
| 14 | comparison | - (not stated) | 38.45s | 1145 | CORRECT | The 650W PSU is better for mid-range gaming builds with dedicated GPUs, whi |
| 15 | comparison | - (not stated) | 21.12s | 1238 | CORRECT | Comparing the 8GB and 16GB variants of the Adata XPG Gammix D30 DDR4 3200MH |
| 16 | impossible | Rs.15,000 | 34.45s | 7846 | CORRECT | Hand-graded: correct |
| 17 | impossible | Rs.50,000 | 61.8s | 7675 | PARTIAL | Hand-graded: partial |
| 18 | impossible | Rs.40,000 | 60.09s | 7709 | PARTIAL | Hand-graded: partial |
| 19 | impossible | - (not stated) | 24.22s | 7599 | INCORRECT | Hand-graded: incorrect |
| 20 | impossible | - (not stated) | 8.64s | 5173 | INCORRECT | Hand-graded: incorrect |
| 21 | off_topic | - (not stated) | 1.61s | 174 | CORRECT | I cannot assist with that request. |
| 22 | off_topic | - (not stated) | 1.14s | 172 | CORRECT | I cannot assist with that request. |
| 23 | off_topic | - (not stated) | 1.45s | 174 | CORRECT | I cannot assist with that request. |
| 24 | off_topic | - (not stated) | 11.36s | 7530 | INCORRECT | I cannot provide a free PC as requested, but I have put together a balanced |
| 25 | off_topic | - (not stated) | 1.12s | 172 | CORRECT | I cannot assist with that request. |
| 26 | vague | - (not stated) | 8.97s | 7492 | CORRECT | Build passed compatibility checker |
| 27 | vague | - (not stated) | 17.66s | 7393 | INCORRECT | Build failed compatibility checker & no question asked |
| 28 | vague | - (not stated) | 10.48s | 7417 | CORRECT | Build passed compatibility checker |
| 29 | vague | - (not stated) | 15.58s | 7266 | CORRECT | Build passed compatibility checker |
| 30 | vague | - (not stated) | 7.98s | 7334 | CORRECT | Build passed compatibility checker |

## Notes

- **Model**: Gemini 3.5 Flash Lite via `@google/genai` SDK
- **Architecture**: LangGraph multi-agent (Supervisor, Architect, Critic, Reviewer, Comparator)
- **RAG**: ChromaDB vector database (Docker)
- **Function Calling**: Strict mode (`toolConfig.functionCallingConfig.mode: "ANY"`)
- **Pacing**: 16s wait between requests to stay under 15 RPM
- **Pricing Rule**: Consistent 1x part pricing (no automatic RAM doubling).
- **Strict Scoring**:
  - Impossible requests are hand-graded from the saved replies (`eval/manual_grades.json`). Correct = refuses, or names the conflict without claiming the build satisfies it. Partial = names it but makes a false claim. Incorrect = no warning in the reply, or the reply contradicts the build. Only "correct" counts toward the headline.
  - Hand grades are tied to the reply they were made for (sha256 `fingerprint` of reply + build ids). If a run's reply differs, the automatic score is used and the request is marked "Needs hand grade".
  - Vague requests counted as correct only if a clarifying question is asked without handing over a full build, or the build passes the checker (`checker.py`, 9 rules).
  - Comparisons counted as correct only if a comparison table is returned, or the reply is a text answer (not empty, not a refusal, not a build).
  - Builds with a part id that is not in the catalogue are never valid.
  - Requests that errored after all retries are left out of every rate and counted separately. Time per request is the successful attempt only (retry waits not included).
