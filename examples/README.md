# Bundled examples for offline / CI reproduction

These files let `python scripts/run_experiments.py rq3` and documentation examples work **without** large `results/` artifacts.

| File | Purpose |
|------|---------|
| `pipeline_report_sample.json` | 18 pipeline `validation_report` rows — RQ3 fake-rate before/after verified-only |
| `hallmark_metrics_sample.json` | Precomputed HALLMARK metrics (F1-H **0.747** on `dev_public`) for RQ3 hallmark section |

## Regenerate locally

```bash
# After a full pipeline run:
python -c "
import json, pathlib
r = json.load(open('results/pipeline_report_v2.json'))
pathlib.Path('examples/pipeline_report_sample.json').write_text(json.dumps({
  'run_id': 'sample-rq3-demo',
  'topic': r['topic'],
  'validation_report': r['validation_report'],
}, indent=2))
"

# After full HALLMARK eval:
python -c "
import json, pathlib
h = json.load(open('results/athena_dev_public_full.json'))
keys = ['split_name','num_entries','detection_rate','f1_hallucination',
        'tier_weighted_f1','false_positive_rate','ece','per_tier_metrics']
pathlib.Path('examples/hallmark_metrics_sample.json').write_text(
    json.dumps({k: h[k] for k in keys if k in h}, indent=2))
"
```

Full reproduction commands: [docs/REPRODUCTION.md](../docs/REPRODUCTION.md).
