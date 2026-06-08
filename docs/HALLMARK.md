# HALLMARK evaluation — reproduction guide

Athena's Citation Validator is evaluated on the public **[HALLMARK](https://github.com/hallucination-benchmark/hallmark)** benchmark via `eval/citebench/`. This document explains data loading, label mapping, and how to reproduce reported numbers.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python **3.10+** for HALLMARK | Main project venv may be 3.9; use `.venv-eval` |
| Network | Crossref / Semantic Scholar API calls |
| `CROSSREF_MAILTO` | Set in `.env` (polite pool) |

```bash
bash scripts/install_hallmark.sh
# Creates .vendor/hallmark and .venv-eval (Python 3.10+)
```

---

## Label mapping (Athena → HALLMARK)

Full rules: [`eval/citebench/mapping.md`](../eval/citebench/mapping.md)

| Athena `status` | HALLMARK label | Rationale |
|-----------------|----------------|-----------|
| `verified` | `VALID` | Resolved metadata match |
| `not_found` | `HALLUCINATED` | No resolvable work |
| `mismatch` | `HALLUCINATED` | Wrong paper / metadata (conservative) |

**Blind evaluation:** The adapter runs on `BlindEntry` only — ground-truth labels never reach the validator.

---

## Quick smoke (dataset stats, no API)

```bash
.venv-eval/bin/python scripts/run_hallmark_eval.py --stats-only
```

Prints entry counts, label distribution, hallucination tiers.

---

## Mini run (~50 entries, minutes)

Useful for CI-style checks or verifying install:

```bash
.venv-eval/bin/python scripts/run_hallmark_eval.py \
  --split dev_public \
  --limit 50 \
  --analyze \
  --delay 0.5 \
  --output results/athena_dev_public_50.json \
  --comparison-md results/athena_vs_baselines.md
```

---

## Full `dev_public` (~1,119 entries)

Expect **hours** of API time. Checkpointing is supported for batch resume:

```bash
.venv-eval/bin/python scripts/run_hallmark_eval.py \
  --split dev_public \
  --analyze \
  --delay 0.5 \
  --output results/athena_dev_public_full.json \
  --comparison-md results/athena_vs_baselines_full.md
```

**Reported full-run metrics (author environment):**

| Metric | Value |
|--------|-------|
| F1-H | **0.747** |
| Detection rate | 0.776 |
| Tier-weighted F1 | 0.813 |
| ECE | 0.240 |

Regenerate locally to verify; outputs are written under `results/`.

### Batch / resume (long runs)

```bash
.venv-eval/bin/python -m eval.citebench.run_eval_batch \
  --split dev_public --delay 0.5 \
  --checkpoint-dir results/hallmark_checkpoints/dev_public
```

See `eval/citebench/run_eval_batch.py` for resume flags.

---

## Baseline comparison

`--comparison-md PATH` writes a markdown table comparing Athena against HALLMARK's bundled baselines (e.g. doi-only heuristics). Requires `--analyze` after predictions are computed.

---

## RQ3 integration

`python scripts/run_experiments.py rq3` loads:

- HALLMARK results from `results/athena_dev_public_full.json` (configurable via `--hallmark`)
- Pipeline citations from `results/pipeline_report_v2.json` (configurable via `--pipeline`)

and writes `results/experiments/rq3/latest.json` including pipeline fake-rate before/after verified-only filtering.

---

## Tests (offline)

```bash
pytest tests/test_hallmark_adapter.py -q
```

Mocks HALLMARK entries; no network.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `HALLMARK not found` | Run `bash scripts/install_hallmark.sh` |
| Python 3.9 error | Use `.venv-eval/bin/python` or `python3.11` |
| Slow / 429 | Increase `--delay`; set `SEMANTIC_SCHOLAR_API_KEY` |
| Different F1-H vs paper | API drift, mapping threshold, or partial split — confirm `--limit 0` |
