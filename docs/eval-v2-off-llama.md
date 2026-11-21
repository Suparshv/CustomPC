# Evaluation Report: v2 upgrades off, Llama 3.1 8B

> Measured on 30 fixed test requests on 2026-11-20 16:29 (re-scored).
> This is a small sample. Results describe this specific test set, not general accuracy.
> Code version: `fa18c90` (clean)

## Summary Table

| Metric | Value |
|--------|-------|
| Valid builds (no FAIL, all 9 categories) | 20.0% (2/10) |
| Within budget (among budgeted builds) | 100.0% (1/1) |
| Refusal rate (build requests declined) | 0.0% (0/10) |
| Unknown rate (a check could not run: missing data) | 90.0% (9/10) |
| Fully verified builds (every rule PASS) | 10.0% (1/10) |
| Comparisons handled correctly | 80.0% (4/5) |
| Impossible requests handled correctly (strict) | 0.0% (0/5) |
| Impossible requests breakdown | 0 correct, 0 partial, 5 incorrect (hand-graded) |
| Off-topic requests handled correctly | 100.0% (5/5) |
| Vague requests handled correctly | 0.0% (0/5) |
| Avg time per request | 5.47s |
| Median time per request | 6.66s |
| Avg tokens per request | 2225 |
| Total tokens used | 66764 |
| Errored requests (left out of every rate) | 0 |

## Three Key Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Success rate** | 20.0% | Valid and compatible builds within budget, out of all build requests |
| **Refusal rate** | 0.0% | How often the system declined a build request |
| **Unknown rate** | 90.0% | Checks that could not run due to missing spec data |

## Per-Request Breakdown

| ID | Type | Budget | Time | Tokens | Result | Details |
|----|------|--------|------|--------|--------|---------|
| 1 | normal_build | - (not stated) | 6.96s | 3137 | FAIL | socket_match |
| 2 | normal_build | Rs.100,000 | 6.09s | 3123 | PASS | All categories present, no compatibility failures |
| 3 | normal_build | - (not stated) | 6.02s | 3046 | FAIL | socket_match |
| 4 | normal_build | - (not stated) | 7.68s | 3220 | FAIL | socket_match, ram_type_match |
| 5 | normal_build | - (not stated) | 7.11s | 3184 | FAIL | socket_match |
| 6 | normal_build | - (not stated) | 8.93s | 3257 | FAIL | ram_type_match |
| 7 | normal_build | - (not stated) | 8.25s | 3196 | FAIL | ram_type_match |
| 8 | normal_build | - (not stated) | 9.1s | 3202 | FAIL | ram_type_match |
| 9 | normal_build | - (not stated) | 8.21s | 3278 | FAIL | socket_match |
| 10 | normal_build | - (not stated) | 6.83s | 3096 | PASS | All categories present, no compatibility failures |
| 11 | comparison | - (not stated) | 1.28s | 328 | CORRECT | The RTX 3060 suits the user's need better. It has more VRAM, which is benef |
| 12 | comparison | - (not stated) | 2.03s | 354 | CORRECT | The GeForce RTX 5080 Asus PRIME is better for 4K due to its higher performa |
| 13 | comparison | - (not stated) | 1.6s | 338 | CORRECT | The AMD Ryzen 5 5600 suits the user's need better. Additionally, the user d |
| 14 | comparison | - (not stated) | 9.06s | 3195 | INCORRECT | A 650W PSU is generally a better choice for this build, as it provides a bi |
| 15 | comparison | - (not stated) | 1.82s | 379 | CORRECT | For gaming, DDR4 16GB RAM suits the user's need better. This is because mor |
| 16 | impossible | Rs.15,000 | 7.34s | 3217 | INCORRECT | Hand-graded: incorrect |
| 17 | impossible | Rs.50,000 | 8.13s | 2413 | INCORRECT | Hand-graded: incorrect |
| 18 | impossible | Rs.40,000 | 7.07s | 2346 | INCORRECT | Hand-graded: incorrect |
| 19 | impossible | - (not stated) | 6.26s | 3122 | INCORRECT | Hand-graded: incorrect |
| 20 | impossible | - (not stated) | 9.01s | 3264 | INCORRECT | Hand-graded: incorrect |
| 21 | off_topic | - (not stated) | 0.02s | 0 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 22 | off_topic | - (not stated) | 0.38s | 132 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 23 | off_topic | - (not stated) | 0.29s | 132 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 24 | off_topic | - (not stated) | 0.02s | 0 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 25 | off_topic | - (not stated) | 0.35s | 132 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 26 | vague | - (not stated) | 6.27s | 3067 | INCORRECT | Build failed compatibility checker & no question asked |
| 27 | vague | - (not stated) | 6.33s | 3076 | INCORRECT | Build failed compatibility checker & no question asked |
| 28 | vague | - (not stated) | 8.33s | 3329 | INCORRECT | Build failed compatibility checker & no question asked |
| 29 | vague | - (not stated) | 6.74s | 3091 | INCORRECT | Build failed compatibility checker & no question asked |
| 30 | vague | - (not stated) | 6.57s | 3110 | INCORRECT | Build failed compatibility checker & no question asked |

## Notes

- **System**: Day 10 agent (`agent-service`, `POST /agent/build`): rule-based router, step-by-step part picks with code filters, code compatibility checker with repairs, price and verdict written by code
- **Model**: ollama / llama3.1:8b
- **Switches**: {"retriever": "vector", "use_tools": false, "use_checker": false, "repair_loops": 0}
- **Search**: ChromaDB + BM25 keyword index (Day 9), retriever set by the switches
- **Pricing Rule**: Consistent 1x part pricing (no automatic RAM doubling).
- **Strict Scoring**:
  - Impossible requests are hand-graded from the saved replies (`eval/manual_grades.json`). Correct = refuses, or names the conflict without claiming the build satisfies it. Partial = names it but makes a false claim. Incorrect = no warning in the reply, or the reply contradicts the build. Only "correct" counts toward the headline.
  - Hand grades are tied to the reply they were made for (sha256 `fingerprint` of reply + build ids). If a run's reply differs, the automatic score is used and the request is marked "Needs hand grade".
  - Vague requests counted as correct only if a clarifying question is asked without handing over a full build, or the build passes the checker (`checker.py`, 9 rules).
  - Comparisons counted as correct only if a comparison table is returned, or the reply is a text answer (not empty, not a refusal, not a build).
  - Builds with a part id that is not in the catalogue are never valid.
  - Requests that errored after all retries are left out of every rate and counted separately. Time per request is the successful attempt only (retry waits not included).
