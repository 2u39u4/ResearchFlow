# Athena documentation (public)

| Document | Purpose |
|----------|---------|
| [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) | Workshop-style technical report: method, evaluation, RQ results, limitations |
| [HALLMARK.md](HALLMARK.md) | Reproduce HALLMARK benchmark numbers (F1-H, baselines, mini vs full split) |
| [REPRODUCTION.md](REPRODUCTION.md) | Fixed seeds, cache behavior, step-by-step commands for key metrics |
| [RESUME_BULLETS.md](RESUME_BULLETS.md) | English resume bullets (research credibility framing) |
| [evaluation/](evaluation/) | Committed read-only snapshot of RQ summary + figures (verify numbers without re-running) |

**Evaluation artifacts:**

- Committed snapshot: [`evaluation/experiment_summary.md`](evaluation/experiment_summary.md) + [`evaluation/figures/`](evaluation/figures/)
- Regenerated locally: `results/experiments/experiment_summary.md`, `results/athena_dev_public_full.json`

**Code references:**

- Validator → HALLMARK mapping: [`eval/citebench/mapping.md`](../eval/citebench/mapping.md)
- Topic pools protocol: [`eval/topics/protocol.md`](../eval/topics/protocol.md)
- Judge rubric: [`eval/judges/rubric.md`](../eval/judges/rubric.md)
- Human-anchor protocol: [`eval/judges/ANCHOR_PROTOCOL.md`](../eval/judges/ANCHOR_PROTOCOL.md)
