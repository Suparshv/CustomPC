# Evaluation Report: v1-baseline

> Measured on 30 fixed test requests on 2026-11-08 15:33.
> This is a small sample. Results describe this specific test set, not general accuracy.

## Summary Table

| Metric | Value |
|--------|-------|
| Valid builds (no FAIL, all 9 categories) | 40.0% (4/10) |
| Within budget (among budgeted builds) | 44.4% (4/9) |
| Refusal rate (build requests declined) | 0.0% (0/10) |
| Unknown rate (missing data for checks) | 10.0% (1/10) |
| Comparisons handled correctly | 100.0% (5/5) |
| Impossible requests handled correctly | 100.0% (5/5) |
| Off-topic requests handled correctly | 80.0% (4/5) |
| Vague requests handled correctly | 100.0% (5/5) |
| Avg time per request | 18.09s |
| Avg tokens per request | 5443 |
| Total tokens used | 163286 |

## Three Key Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Success rate** | 40.0% | Valid and compatible builds within budget, out of all build requests |
| **Refusal rate** | 0.0% | How often the system declined a build request |
| **Unknown rate** | 10.0% | Checks that could not run due to missing spec data |

## Per-Request Breakdown

| ID | Type | Budget | Time | Tokens | Result | Details |
|----|------|--------|------|--------|--------|---------|
| 1 | normal_build | Rs.80,000 | 34.96s | 7371 | PASS | All categories present, no compatibility failures |
| 2 | normal_build | Rs.100,000 | 26.86s | 7643 | PASS | All categories present, no compatibility failures |
| 3 | normal_build | Rs.40,000 | 40.03s | 7420 | FAIL | 6_within_budget |
| 4 | normal_build | Rs.120,000 | 30.26s | 7649 | FAIL | 6_within_budget |
| 5 | normal_build | Rs.90,000 | 49.54s | 7478 | FAIL | 4_psu_sufficient, 6_within_budget |
| 6 | normal_build | Rs.150,000 | 64.35s | 7320 | PASS | All categories present, no compatibility failures |
| 7 | normal_build | Rs.95,000 | 10.33s | 8018 | FAIL | 3_ram_type_match, 6_within_budget |
| 8 | normal_build | Rs.55,000 | 65.41s | 7324 | FAIL | 6_within_budget |
| 9 | normal_build | - | 9.77s | 7962 | FAIL | 4_psu_sufficient |
| 10 | normal_build | Rs.70,000 | 7.35s | 7323 | PASS | All categories present, no compatibility failures |
| 11 | comparison | - | 3.83s | 1333 | CORRECT | The RTX 4060 offers higher gaming performance, lower power consumption, and fast |
| 12 | comparison | - | 3.36s | 1380 | CORRECT | The MSI RTX 5080 is significantly better for 4K gaming and heavy workloads compa |
| 13 | comparison | - | 3.27s | 1315 | CORRECT | The Intel i5 12400 offers slightly better performance and DDR5 compatibility, wh |
| 14 | comparison | - | 3.01s | 1143 | CORRECT | The 650W PSU is better for mid-range gaming builds, while the 550W PSU suits bud |
| 15 | comparison | - | 3.46s | 1239 | CORRECT | Comparing Adata XPG Gammix D30 8GB and 16GB DDR4 3200MHz RAM for gaming: The 8GB |
| 16 | impossible | Rs.15,000 | 9.76s | 8065 | CORRECT | It is impossible to build a 4K RTX 5080 PC for 15,000 rupees since the graphics  |
| 17 | impossible | Rs.50,000 | 7.68s | 7677 | CORRECT | The RTX 5080 and i5 12400 have been added to your build along with all required  |
| 18 | impossible | Rs.40,000 | 8.32s | 7551 | CORRECT | We cannot support 3 GPUs or liquid nitrogen cooling, but here is a solid budget  |
| 19 | impossible | Rs.120,000 | 8.47s | 7609 | CORRECT | Here is your custom build featuring the RTX 5070Ti and a 550W PSU along with all |
| 20 | impossible | Rs.60,000 | 5.76s | 5156 | CORRECT | You requested an AMD Ryzen 5 5600 with an LGA1700 motherboard. Please note that  |
| 21 | off_topic | - | 1.11s | 174 | CORRECT | I cannot assist with that request. |
| 22 | off_topic | - | 1.12s | 172 | CORRECT | I cannot assist with that request. |
| 23 | off_topic | - | 1.1s | 174 | CORRECT | I cannot assist with that request. |
| 24 | off_topic | - | 7.28s | 7267 | INCORRECT | We cannot provide free PCs, but here is an affordable and well-balanced build ba |
| 25 | off_topic | - | 1.06s | 172 | CORRECT | I cannot assist with that request. |
| 26 | vague | - | 12.15s | 7473 | CORRECT | Here is a well-balanced gaming and productivity PC featuring an Intel i5 process |
| 27 | vague | - | 52.32s | 7381 | CORRECT | I have drafted a balanced mid-range PC build featuring an Intel i5 processor and |
| 28 | vague | - | 24.13s | 7519 | CORRECT | Here is a balanced all-around setup featuring the Intel i5 12400 processor and G |
| 29 | vague | - | 22.27s | 7389 | CORRECT | I have put together a well-balanced mid-range gaming and productivity PC featuri |
| 30 | vague | - | 24.44s | 7589 | CORRECT | Here is a well-balanced mid-range gaming and multitasking build featuring the In |

## Notes

- **Model**: Gemini 3.5 Flash Lite via `@google/genai` SDK
- **Architecture**: LangGraph multi-agent (Supervisor, Architect, Critic, Reviewer, Comparator)
- **RAG**: ChromaDB vector database (Docker)
- **Function Calling**: Strict mode (`toolConfig.functionCallingConfig.mode: "ANY"`)
- **Pacing**: 16s wait between requests to stay under 15 RPM
- **Resilience**: Auto-backoff retry and incremental disk saving enabled.
