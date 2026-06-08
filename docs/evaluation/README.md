# Committed evaluation artifacts

This folder holds a **read-only snapshot** of the evaluation outputs so reviewers can
verify the headline numbers without re-running the full (network-heavy, multi-hour)
experiments. Re-running locally regenerates the same outputs under `results/experiments/`.

| File | What it is |
|------|------------|
| [`experiment_summary.md`](experiment_summary.md) | RQ1/RQ2/RQ3 statistics: means ± SD, 95% CIs, paired *t*-tests, human-anchor agreement |
| [`figures/rq1_coverage.png`](figures/rq1_coverage.png) | Multi- vs single-agent literature coverage |
| [`figures/rq2_ablation.png`](figures/rq2_ablation.png) | Critic ablation (fake-rate, grounding, depth) |
| [`figures/rq3_fake_citation.png`](figures/rq3_fake_citation.png) | Pipeline fake-citation rate (all vs verified-only) |

## Headline numbers (see the summary for full stats)

- **RQ1** — Coverage: multi **0.855 ± 0.138** vs single **0.787 ± 0.158**, paired *t*-test *p* ≈ 4.4×10⁻⁵ (multi higher). Blind pairwise preference for multi: 53.3% (NS, *p* ≈ 0.70).
- **RQ2** — Critic enforces evidence grounding **1.000**; fake-rate change not significant (*p* ≈ 0.22); depth favors the no-Critic path (*p* ≈ 0.007).
- **RQ3** — HALLMARK **F1-H 0.747** on `dev_public`; pipeline fake rate 27.8% (all cites) → **0%** under the verified-only policy.

## Regenerate

```bash
pip install -r requirements.txt -r requirements-eval.txt
python scripts/run_experiments.py rq3          # bundled samples, no LLM
python scripts/run_experiments.py rq1 rq2      # needs OPENAI_API_KEY + judge key
python scripts/run_experiments.py analysis     # writes results/experiments/{figures,experiment_summary.md}
```

These snapshots were produced from 60 matched runs per RQ (20 topics × 3 repeats).
See [`../TECHNICAL_REPORT.md`](../TECHNICAL_REPORT.md), [`../REPRODUCTION.md`](../REPRODUCTION.md),
and the human-anchor protocol in [`../../eval/judges/ANCHOR_PROTOCOL.md`](../../eval/judges/ANCHOR_PROTOCOL.md).
