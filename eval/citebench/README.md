# `eval/citebench` — HALLMARK adapter

Python package that runs Athena's deterministic `CitationValidator` on the public **HALLMARK** benchmark and computes official metrics.

## Quick links

- **Reproduction guide:** [docs/HALLMARK.md](../../docs/HALLMARK.md)
- **Label mapping:** [mapping.md](mapping.md)
- **CLI wrapper:** `scripts/run_hallmark_eval.py` (requires Python 3.10+)

## Modules

| File | Role |
|------|------|
| `hallmark_adapter.py` | BibTeX → `Citation` → validator → HALLMARK prediction |
| `run_eval.py` | CLI: load split, evaluate, optional baseline table |
| `run_eval_batch.py` | Checkpointed batch runs for full `dev_public` |
| `baseline_table.py` | Markdown comparison vs HALLMARK baselines |

## Mini eval (smoke)

```bash
bash scripts/install_hallmark.sh
.venv-eval/bin/python scripts/run_hallmark_eval.py --split dev_public --limit 50 --analyze
```
