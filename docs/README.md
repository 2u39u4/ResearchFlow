# Athena documentation (public)

| Document | Purpose |
|----------|---------|
| [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) | Workshop-style technical report: method, evaluation, RQ results, limitations |
| [HALLMARK.md](HALLMARK.md) | Reproduce HALLMARK benchmark numbers (F1-H, baselines, mini vs full split) |
| [REPRODUCTION.md](REPRODUCTION.md) | Fixed seeds, cache behavior, step-by-step commands for key metrics |
| [RESUME_BULLETS.md](RESUME_BULLETS.md) | English resume bullets (research credibility framing) |

**Evaluation artifacts** (generated locally, not committed):

- `results/experiments/experiment_summary.md` — RQ1/RQ2/RQ3 statistics
- `results/athena_dev_public_full.json` — full HALLMARK run output
- `results/athena_vs_baselines_full.md` — baseline comparison table

**Code references:**

- Validator → HALLMARK mapping: [`eval/citebench/mapping.md`](../eval/citebench/mapping.md)
- Topic pools protocol: [`eval/topics/protocol.md`](../eval/topics/protocol.md)
- Judge rubric: [`eval/judges/rubric.md`](../eval/judges/rubric.md)
