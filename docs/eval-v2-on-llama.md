# Evaluation Report: v2 upgrades on, Llama 3.1 8B

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
| Impossible requests handled correctly (strict) | 60.0% (3/5) |
| Impossible requests breakdown | 3 correct, 0 partial, 2 incorrect (hand-graded) |
| Off-topic requests handled correctly | 100.0% (5/5) |
| Vague requests handled correctly | 100.0% (5/5) |
| Avg time per request | 10.54s |
| Median time per request | 14.07s |
| Avg tokens per request | 4006 |
| Total tokens used | 120176 |
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
| 1 | normal_build | - (not stated) | 29.83s | 6303 | PASS | All categories present, no compatibility failures |
| 2 | normal_build | Rs.100,000 | 22.82s | 6287 | PASS | All categories present, no compatibility failures |
| 3 | normal_build | - (not stated) | 14.15s | 6201 | PASS | All categories present, no compatibility failures |
| 4 | normal_build | - (not stated) | 15.54s | 6346 | PASS | All categories present, no compatibility failures |
| 5 | normal_build | - (not stated) | 15.23s | 6352 | PASS | All categories present, no compatibility failures |
| 6 | normal_build | - (not stated) | 16.85s | 6412 | PASS | All categories present, no compatibility failures |
| 7 | normal_build | - (not stated) | 15.32s | 6332 | PASS | All categories present, no compatibility failures |
| 8 | normal_build | - (not stated) | 13.98s | 6160 | PASS | All categories present, no compatibility failures |
| 9 | normal_build | - (not stated) | 16.6s | 6448 | PASS | All categories present, no compatibility failures |
| 10 | normal_build | - (not stated) | 15.18s | 6426 | PASS | All categories present, no compatibility failures |
| 11 | comparison | - (not stated) | 1.23s | 317 | CORRECT | The RTX 3060 suits the user's need better. It has more VRAM and is slightly |
| 12 | comparison | - (not stated) | 2.14s | 354 | CORRECT | The GeForce RTX 5080 Asus PRIME is better for 4K due to its higher performa |
| 13 | comparison | - (not stated) | 1.72s | 338 | CORRECT | The AMD Ryzen 5 5600 suits the user's need better. Additionally, the user d |
| 14 | comparison | - (not stated) | 14.07s | 6086 | INCORRECT | A 650W PSU is generally a better choice for this build, as it provides a bi |
| 15 | comparison | - (not stated) | 1.81s | 363 | CORRECT | For gaming, the DDR4 16GB RAM suits the user's need better. This is because |
| 16 | impossible | Rs.15,000 | 1.78s | 606 | CORRECT | Hand-graded: correct |
| 17 | impossible | Rs.50,000 | 8.51s | 3457 | CORRECT | Hand-graded: correct |
| 18 | impossible | Rs.40,000 | 4.2s | 1639 | CORRECT | Hand-graded: correct |
| 19 | impossible | - (not stated) | 15.56s | 6402 | INCORRECT | Hand-graded: incorrect |
| 20 | impossible | - (not stated) | 14.28s | 6296 | INCORRECT | Hand-graded: incorrect |
| 21 | off_topic | - (not stated) | 0.02s | 0 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 22 | off_topic | - (not stated) | 0.39s | 132 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 23 | off_topic | - (not stated) | 0.27s | 132 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 24 | off_topic | - (not stated) | 0.03s | 0 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 25 | off_topic | - (not stated) | 0.31s | 132 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 26 | vague | - (not stated) | 14.88s | 6104 | CORRECT | Build passed compatibility checker |
| 27 | vague | - (not stated) | 15.28s | 6119 | CORRECT | Build passed compatibility checker |
| 28 | vague | - (not stated) | 16.04s | 6331 | CORRECT | Build passed compatibility checker |
| 29 | vague | - (not stated) | 14.08s | 6024 | CORRECT | Build passed compatibility checker |
| 30 | vague | - (not stated) | 14.0s | 6077 | CORRECT | Build passed compatibility checker |

## Notes

- **System**: Day 10 agent (`agent-service`, `POST /agent/build`): rule-based router, step-by-step part picks with code filters, code compatibility checker with repairs, price and verdict written by code
- **Model**: ollama / llama3.1:8b
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
