# Evaluation Report: v2 upgrades off, Gemini

> Measured on 30 fixed test requests on 2026-11-20 16:29 (re-scored).
> This is a small sample. Results describe this specific test set, not general accuracy.
> Code version: `fa18c90` (clean)

## Summary Table

| Metric | Value |
|--------|-------|
| Valid builds (no FAIL, all 9 categories) | 50.0% (5/10) |
| Within budget (among budgeted builds) | 100.0% (1/1) |
| Refusal rate (build requests declined) | 0.0% (0/10) |
| Unknown rate (a check could not run: missing data) | 90.0% (9/10) |
| Fully verified builds (every rule PASS) | 10.0% (1/10) |
| Comparisons handled correctly | 80.0% (4/5) |
| Impossible requests handled correctly (strict) | 0.0% (0/5) |
| Impossible requests breakdown | 0 correct, 0 partial, 5 incorrect (hand-graded) |
| Off-topic requests handled correctly | 100.0% (5/5) |
| Vague requests handled correctly | 0.0% (0/5) |
| Avg time per request | 10.4s |
| Median time per request | 10.29s |
| Avg tokens per request | 2723 |
| Total tokens used | 81698 |
| Errored requests (left out of every rate) | 0 |

## Three Key Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Success rate** | 50.0% | Valid and compatible builds within budget, out of all build requests |
| **Refusal rate** | 0.0% | How often the system declined a build request |
| **Unknown rate** | 90.0% | Checks that could not run due to missing spec data |

## Per-Request Breakdown

| ID | Type | Budget | Time | Tokens | Result | Details |
|----|------|--------|------|--------|--------|---------|
| 1 | normal_build | - (not stated) | 11.95s | 3933 | FAIL | socket_match |
| 2 | normal_build | Rs.100,000 | 13.15s | 3860 | PASS | All categories present, no compatibility failures |
| 3 | normal_build | - (not stated) | 8.04s | 3824 | FAIL | socket_match |
| 4 | normal_build | - (not stated) | 9.22s | 3893 | FAIL | ram_type_match |
| 5 | normal_build | - (not stated) | 8.58s | 3981 | FAIL | socket_match |
| 6 | normal_build | - (not stated) | 9.63s | 3956 | PASS | All categories present, no compatibility failures |
| 7 | normal_build | - (not stated) | 14.58s | 3878 | PASS | All categories present, no compatibility failures |
| 8 | normal_build | - (not stated) | 18.13s | 3825 | PASS | All categories present, no compatibility failures |
| 9 | normal_build | - (not stated) | 19.83s | 3984 | FAIL | socket_match |
| 10 | normal_build | - (not stated) | 12.06s | 3852 | PASS | All categories present, no compatibility failures |
| 11 | comparison | - (not stated) | 6.27s | 396 | CORRECT | The Gigabyte RTX 4060 OC 8GB is more expensive, but it offers newer archite |
| 12 | comparison | - (not stated) | 4.01s | 361 | CORRECT | The GeForce RTX 5080 Asus PRIME is the better choice for 4K gaming because  |
| 13 | comparison | - (not stated) | 6.07s | 362 | CORRECT | The AMD Ryzen 5 5600 is slightly cheaper and uses the mature AM4 platform,  |
| 14 | comparison | - (not stated) | 12.06s | 3801 | INCORRECT | Choosing a 650W power supply gives your system plenty of reliable energy to |
| 15 | comparison | - (not stated) | 8.23s | 389 | CORRECT | The Crucial 16 GB RAM suits gaming needs better because its higher capacity |
| 16 | impossible | Rs.15,000 | 11.46s | 3981 | INCORRECT | Hand-graded: incorrect |
| 17 | impossible | Rs.50,000 | 12.08s | 2831 | INCORRECT | Hand-graded: incorrect |
| 18 | impossible | Rs.40,000 | 10.11s | 2819 | INCORRECT | Hand-graded: incorrect |
| 19 | impossible | - (not stated) | 10.48s | 3885 | INCORRECT | Hand-graded: incorrect |
| 20 | impossible | - (not stated) | 10.79s | 3944 | INCORRECT | Hand-graded: incorrect |
| 21 | off_topic | - (not stated) | 0.02s | 0 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 22 | off_topic | - (not stated) | 1.56s | 123 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 23 | off_topic | - (not stated) | 9.03s | 125 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 24 | off_topic | - (not stated) | 0.04s | 0 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 25 | off_topic | - (not stated) | 6.31s | 123 | CORRECT | I can only help with building a PC or comparing PC parts. |
| 26 | vague | - (not stated) | 17.97s | 3870 | INCORRECT | Build failed compatibility checker & no question asked |
| 27 | vague | - (not stated) | 16.9s | 3860 | INCORRECT | Build failed compatibility checker & no question asked |
| 28 | vague | - (not stated) | 19.06s | 4034 | INCORRECT | Build failed compatibility checker & no question asked |
| 29 | vague | - (not stated) | 9.02s | 3898 | INCORRECT | Build failed compatibility checker & no question asked |
| 30 | vague | - (not stated) | 15.27s | 3910 | INCORRECT | Build failed compatibility checker & no question asked |

## Notes

- **System**: Day 10 agent (`agent-service`, `POST /agent/build`): rule-based router, step-by-step part picks with code filters, code compatibility checker with repairs, price and verdict written by code
- **Model**: gemini / gemini-3.5-flash-lite
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
