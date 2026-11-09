# Evaluation Report: v1-baseline

> Measured on 30 fixed test requests on 2026-11-08 21:41.
> This is a small sample. Results describe this specific test set, not general accuracy.

## Summary Table

| Metric | Value |
|--------|-------|
| Valid builds (no FAIL, all 9 categories) | 40.0% (4/10) |
| Within budget (among budgeted builds) | 55.6% (5/9) |
| Refusal rate (build requests declined) | 0.0% (0/10) |
| Unknown rate (missing data for checks) | 10.0% (1/10) |
| Comparisons handled correctly | 100.0% (5/5) |
| Impossible requests handled correctly (strict) | 20.0% (1/5) |
| Impossible requests breakdown | 1 correct, 2 partial, 2 incorrect (hand-graded) |
| Off-topic requests handled correctly | 80.0% (4/5) |
| Vague requests handled correctly | 80.0% (4/5) |
| Avg time per request | 16.89s |
| Avg tokens per request | 5438 |
| Total tokens used | 163125 |

## Three Key Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Success rate** | 40.0% | Valid and compatible builds within budget, out of all build requests |
| **Refusal rate** | 0.0% | How often the system declined a build request |
| **Unknown rate** | 10.0% | Checks that could not run due to missing spec data |

## Per-Request Breakdown

| ID | Type | Budget | Time | Tokens | Result | Details |
|----|------|--------|------|--------|--------|---------|
| 1 | normal_build | Rs.80,000 | 7.72s | 7355 | PASS | All categories present, no compatibility failures |
| 2 | normal_build | Rs.100,000 | 7.59s | 7325 | PASS | All categories present, no compatibility failures |
| 3 | normal_build | Rs.40,000 | 8.87s | 7572 | FAIL | 6_within_budget |
| 4 | normal_build | Rs.120,000 | 7.68s | 7769 | FAIL | 3_ram_type_match, 6_within_budget |
| 5 | normal_build | Rs.90,000 | 7.99s | 7897 | FAIL | 3_ram_type_match, 4_psu_sufficient, 6_within_budget |
| 6 | normal_build | Rs.150,000 | 9.75s | 7281 | PASS | All categories present, no compatibility failures |
| 7 | normal_build | Rs.95,000 | 19.21s | 7369 | PASS | All categories present, no compatibility failures |
| 8 | normal_build | Rs.55,000 | 23.53s | 7351 | FAIL | 6_within_budget |
| 9 | normal_build | - | 29.27s | 8100 | FAIL | 4_psu_sufficient |
| 10 | normal_build | Rs.70,000 | 8.63s | 7408 | FAIL | 2_socket_match |
| 11 | comparison | - | 3.52s | 1350 | CORRECT | The RTX 4060 offers better frame rates and lower power draw, while the RTX  |
| 12 | comparison | - | 3.92s | 1408 | CORRECT | The MSI RTX 5080 is superior for 4K gaming, delivering around 90fps in dema |
| 13 | comparison | - | 42.9s | 1431 | CORRECT | Comparing the Intel i5 12400 and AMD Ryzen 5 5600: The Intel i5 12400 costs |
| 14 | comparison | - | 38.45s | 1145 | CORRECT | The 650W PSU is better for mid-range gaming builds with dedicated GPUs, whi |
| 15 | comparison | - | 21.12s | 1238 | CORRECT | Comparing the 8GB and 16GB variants of the Adata XPG Gammix D30 DDR4 3200MH |
| 16 | impossible | Rs.15,000 | 34.45s | 7846 | CORRECT | Hand-graded: correct |
| 17 | impossible | Rs.50,000 | 61.8s | 7675 | PARTIAL | Hand-graded: partial |
| 18 | impossible | Rs.40,000 | 60.09s | 7709 | PARTIAL | Hand-graded: partial |
| 19 | impossible | Rs.120,000 | 24.22s | 7599 | INCORRECT | Hand-graded: incorrect |
| 20 | impossible | Rs.60,000 | 8.64s | 5173 | INCORRECT | Hand-graded: incorrect |
| 21 | off_topic | - | 1.61s | 174 | CORRECT | I cannot assist with that request. |
| 22 | off_topic | - | 1.14s | 172 | CORRECT | I cannot assist with that request. |
| 23 | off_topic | - | 1.45s | 174 | CORRECT | I cannot assist with that request. |
| 24 | off_topic | - | 11.36s | 7530 | INCORRECT | I cannot provide a free PC as requested, but I have put together a balanced |
| 25 | off_topic | - | 1.12s | 172 | CORRECT | I cannot assist with that request. |
| 26 | vague | - | 8.97s | 7492 | CORRECT | Build passed compatibility checker |
| 27 | vague | - | 17.66s | 7393 | INCORRECT | Build failed compatibility checker & no question asked |
| 28 | vague | - | 10.48s | 7417 | CORRECT | Build passed compatibility checker |
| 29 | vague | - | 15.58s | 7266 | CORRECT | Build passed compatibility checker |
| 30 | vague | - | 7.98s | 7334 | CORRECT | Build passed compatibility checker |

## Notes

- **Model**: Gemini 3.5 Flash Lite via `@google/genai` SDK
- **Architecture**: LangGraph multi-agent (Supervisor, Architect, Critic, Reviewer, Comparator)
- **RAG**: ChromaDB vector database (Docker)
- **Function Calling**: Strict mode (`toolConfig.functionCallingConfig.mode: "ANY"`)
- **Pacing**: 16s wait between requests to stay under 15 RPM
- **Pricing Rule**: Consistent 1x part pricing (no automatic RAM doubling).
- **Strict Scoring**:
  - Impossible requests are hand-graded from the saved replies (`eval/manual_grades.json`). Correct = refuses, or names the conflict without claiming the build satisfies it. Partial = names it but makes a false claim. Incorrect = no warning in the reply, or the reply contradicts the build. Only "correct" counts toward the headline.
  - Vague requests counted as correct only if clarifying question asked or build passes all 6 checker rules.
