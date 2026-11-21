# Evaluation Report: v2 upgrades on, Gemini

> Measured on 30 fixed test requests on 2026-11-20 16:29 (re-scored).
> This is a small sample. Results describe this specific test set, not general accuracy.
> Code version: `fa18c90` (clean)

## Summary Table

| Metric | Value |
|--------|-------|
| Valid builds (no FAIL, all 9 categories) | 100.0% (10/10) |
| Within budget (among budgeted builds) | 100.0% (1/1) |
| Refusal rate (build requests declined) | 0.0% (0/10) |
| Unknown rate (a check could not run: missing data) | 100.0% (10/10) |
| Fully verified builds (every rule PASS) | 0.0% (0/10) |
| Comparisons handled correctly | 80.0% (4/5) |
| Impossible requests handled correctly (strict) | 40.0% (2/5) |
| Impossible requests breakdown | 2 correct, 0 partial, 3 incorrect (hand-graded) |
| Off-topic requests handled correctly | 100.0% (5/5) |
| Vague requests handled correctly | 100.0% (5/5) |
| Avg time per request | 17.23s |
| Median time per request | 14.04s |
| Avg tokens per request | 4764 |
| Total tokens used | 142931 |
| Errored requests (left out of every rate) | 0 |

## Three Key Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Success rate** | 100.0% | Valid and compatible builds within budget, out of all build requests |
| **Refusal rate** | 0.0% | How often the system declined a build request |
| **Unknown rate** | 100.0% | Checks that could not run due to missing spec data |

## Per-Request Breakdown

| ID | Type | Budget | Time | Tokens | Result | Details |
|----|------|--------|------|--------|--------|---------|
| 1 | normal_build | - (not stated) | 28.5s | 7237 | PASS | All categories present, no compatibility failures |
| 2 | normal_build | Rs.100,000 | 13.79s | 7264 | PASS | All categories present, no compatibility failures |
| 3 | normal_build | - (not stated) | 13.29s | 7231 | PASS | All categories present, no compatibility failures |
| 4 | normal_build | - (not stated) | 14.66s | 7364 | PASS | All categories present, no compatibility failures |
| 5 | normal_build | - (not stated) | 12.48s | 7167 | PASS | All categories present, no compatibility failures |
| 6 | normal_build | - (not stated) | 14.8s | 7167 | PASS | All categories present, no compatibility failures |
| 7 | normal_build | - (not stated) | 14.18s | 7118 | PASS | All categories present, no compatibility failures |
| 8 | normal_build | - (not stated) | 14.23s | 7070 | PASS | All categories present, no compatibility failures |
| 9 | normal_build | - (not stated) | 13.89s | 7209 | PASS | All categories present, no compatibility failures |
| 10 | normal_build | - (not stated) | 25.39s | 7401 | PASS | All categories present, no compatibility failures |
| 11 | comparison | - (not stated) | 1.63s | 374 | CORRECT | The Gigabyte RTX 4060 OC 8GB is more expensive, but it offers a much newer  |
| 12 | comparison | - (not stated) | 1.81s | 365 | CORRECT | For 4K gaming, the GeForce RTX 5080 Asus PRIME is the better choice because |
| 13 | comparison | - (not stated) | 2.02s | 386 | CORRECT | The AMD Ryzen 5 5600 is slightly better for budget-conscious builders becau |
| 14 | comparison | - (not stated) | 13.74s | 7183 | INCORRECT | Choosing a 650W power supply gives your system plenty of reliable energy to |
| 15 | comparison | - (not stated) | 1.39s | 384 | CORRECT | For a modern gaming PC, the Adata XPG Gammix D30 16GB DDR4 RAM is much bett |
| 16 | impossible | Rs.15,000 | 6.06s | 676 | CORRECT | Hand-graded: correct |
| 17 | impossible | Rs.50,000 | 38.12s | 6609 | INCORRECT | Hand-graded: incorrect |
| 18 | impossible | Rs.40,000 | 19.78s | 4077 | CORRECT | Hand-graded: correct |
| 19 | impossible | - (not stated) | 41.88s | 7349 | INCORRECT | Hand-graded: incorrect |
| 20 | impossible | - (not stated) | 42.89s | 7380 | INCORRECT | Hand-graded: incorrect |
| 21 | off_topic | - (not stated) | 0.02s | 0 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 22 | off_topic | - (not stated) | 3.11s | 123 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 23 | off_topic | - (not stated) | 0.94s | 120 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 24 | off_topic | - (not stated) | 0.03s | 0 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 25 | off_topic | - (not stated) | 5.74s | 123 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 26 | vague | - (not stated) | 31.04s | 7099 | CORRECT | Build passed compatibility checker |
| 27 | vague | - (not stated) | 31.13s | 7053 | CORRECT | Build passed compatibility checker |
| 28 | vague | - (not stated) | 38.08s | 7273 | CORRECT | Build passed compatibility checker |
| 29 | vague | - (not stated) | 37.52s | 7092 | CORRECT | Build passed compatibility checker |
| 30 | vague | - (not stated) | 34.7s | 7037 | CORRECT | Build passed compatibility checker |

## Notes

- **System**: Day 10 agent (`agent-service`, `POST /agent/build`): rule-based router, step-by-step part picks with code filters, code compatibility checker with repairs, price and verdict written by code
- **Model**: gemini / gemini-3.5-flash-lite
- **Switches**: defaults (all upgrades on)
- **Search**: ChromaDB + BM25 keyword index (Day 9), retriever set by the switches
- **Pricing Rule**: Consistent 1x part pricing (no automatic RAM doubling).
- **Strict Scoring**:
  - Impossible requests are hand-graded from the saved replies (`eval/manual_grades.json`). Correct = refuses, or names the conflict without claiming the build satisfies it. Partial = names it but makes a false claim. Incorrect = no warning in the reply, or the reply contradicts the build. Only "correct" counts toward the headline.
  - Hand grades are tied to the reply they were made for (sha256 `fingerprint` of reply + build ids). If a run's reply differs, the automatic score is used and the request is marked "Needs hand grade".
  - Vague requests counted as correct only if a clarifying question is asked without handing over a full build, or the build passes the checker (`checker.py`, 9 rules).
  - Comparisons counted as correct only if a comparison table is returned, or the reply is a text answer (not empty, not a refusal, not a build).
  - Builds with a part id that is not in the catalogue are never valid.
  - Requests that errored after all retries are left out of every rate and counted separately. Time per request is the successful attempt only (retry waits not included).
