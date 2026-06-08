# Athena Evaluation Summary (RQ1 / RQ2 / RQ3)

Stats: paired two-sided *t*-tests on matched topic/repeat rows; 95% CIs are normal-approx (mean ± 1.96×SE). α=0.05. No multiple-comparison correction.

## RQ1: Multi-Agent vs Single-Agent
- Runs: 60 (repeats=3)
- Coverage multi: 0.855 ± 0.138 (n=60, 95% CI [0.820, 0.890])
- Coverage single: 0.787 ± 0.158 (n=60, 95% CI [0.748, 0.827])
- Depth multi: 4.00 ± 0.71 (n=60, 95% CI [3.82, 4.18])
- Depth single: 4.55 ± 0.50 (n=60, 95% CI [4.42, 4.68])
- Pairwise win rate (multi): 53.3% (n=60, 95% CI [40.7%, 66.0%])
- Binomial test vs 50%: p=0.6989 (not significant)
- Paired *t*-test (coverage multi − single): p=4.44e-05 (significant)
- Coverage difference: 0.068 ± 0.119 (n=60, 95% CI [0.038, 0.097]) (positive → multi higher)
- Paired *t*-test (depth multi − single): p=5.66e-05 (significant)
- Depth difference: -0.55 ± 0.98 (n=60, 95% CI [-0.80, -0.30]) (positive → multi higher)

## RQ2: Critic ablation
- Runs: 60 (repeats=3)
- Evidence grounding (with critic): 1.000 ± 0.000 (n=60, 95% CI [1.000, 1.000])
- Fake rate no critic: 0.172 ± 0.110 (n=60, 95% CI [0.144, 0.200])
- Fake rate with critic: 0.185 ± 0.100 (n=60, 95% CI [0.160, 0.210])
- Paired *t*-test (fake rate no critic − with critic): p=0.2230 (not significant)
- Fake-rate difference: -0.013 ± 0.080 (n=60, 95% CI [-0.033, 0.007]) (positive → no critic lower / critic helps)
- Depth no critic: 4.35 ± 0.58 (n=60, 95% CI [4.20, 4.50])
- Depth with critic: 4.00 ± 0.71 (n=60, 95% CI [3.82, 4.18])
- Paired *t*-test (depth no critic − with critic): p=0.0071 (significant)
- Depth difference: 0.35 ± 0.97 (n=60, 95% CI [0.10, 0.60]) (positive → no critic deeper)

## RQ3: Citation validation
- HALLMARK F1-H: 0.747
- Detection rate: 0.776
- Tier-weighted F1: 0.813
- ECE: 0.240
- Pipeline fake rate (no filter): 27.8% (18 citations)
- Pipeline fake rate (verified-only): 0.0%

## Significance at a glance (α=0.05)
| Claim | Result |
|-------|--------|
| Multi Coverage > Single | **significant** (p=4.44e-05) |
| Multi Depth > Single | **significant** (favors single, p=5.66e-05) |
| Pairwise preference for multi | not significant (p=0.6989) |
| Critic lowers fake citation rate | not significant (p=0.2230) |
| Critic improves depth | **significant** (favors no critic, p=0.0071) |
| Validator removes pipeline fake cites | descriptive (n=18 pipeline cites) |

## Human anchor vs LLM judge (real blind annotation, n=12)

A single human rater scored a blind, A/B-randomized 20% stratified sample (`repeat=0`)
without knowing which output was multi- vs single-agent. Source: `eval/judges/human_anchor_human.csv`
(produced via `scripts/build_blind_annotation.py` → `scripts/ingest_human_anchor.py`).

Agreement with the LLM judge:
- Depth (multi) Cohen's κ: 0.103
- Depth (single) Cohen's κ: -0.012
- Depth (multi) Spearman ρ: 0.372
- Preference agreement: 58.3% (7/12)

Key finding — **the human and the LLM judge disagree on the direction of the depth gap**:
- Human depth: multi 4.83 vs single 4.17 (**multi deeper**); preferred multi-agent in **11/12** items.
- LLM judge depth (RQ1): multi 4.00 vs single 4.55 (single deeper).

This supports the report's hypothesis that the LLM judge penalizes multi-agent verbosity
that a human reader actually values for evidence depth.

**Caveats:** single rater (the author), n=12, blind but not a powered multi-rater study.
Treat as a directional sanity check, not a definitive human evaluation. The earlier
heuristic-proxy anchor (`human_anchor_template.csv`) is retained only as a pipeline fixture;
see `eval/judges/ANCHOR_PROTOCOL.md` for the two-rater procedure.
