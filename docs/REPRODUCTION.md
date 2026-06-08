# Reproducing Athena experiments

This guide lists **fixed seeds**, **cache behavior**, and **commands** to reproduce the key numbers cited in [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md). Runtime outputs are written under `results/`; clone the repo and run locally.

---

## 1. Environment setup

```bash
cd ResearchFlow
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Minimum `.env` for full reproduction:**

```bash
OPENAI_API_KEY=...          # subject agents (pipeline, RQ1/RQ2)
CROSSREF_MAILTO=you@edu.com
JUDGE_LLM_MODEL=gemini-3.5-flash   # must differ from DEFAULT_LLM_MODEL
JUDGE_LLM_PROVIDER=gemini
GEMINI_API_KEY=...          # if judge provider is gemini
EVAL_RANDOM_SEED=42
EVAL_DEFAULT_REPEATS=3
```

Optional but recommended: `SEMANTIC_SCHOLAR_API_KEY` (higher rate limits).

---

## 2. Random seeds & determinism

| Component | Seed / config | Location |
|-----------|---------------|----------|
| Pairwise blind order | `EVAL_RANDOM_SEED + repeat` per topic | `eval/experiments/common.py` (`seeded_rng`, SHA-256) |
| Judge temperature | 0.1 (depth / pairwise) | `eval/judges/llm_judge.py` |
| TopicSet repeats | `EVAL_DEFAULT_REPEATS=3` | `.env` |
| LangGraph thread | CLI `--thread-id` or UUID per run | `scripts/run_pipeline.py` |

**Non-deterministic:** LLM sampling (low temperature but not zero), API result ordering, arXiv rate-limit timing.

---

## 3. Disk cache (LLM + arXiv)

| Cache | Path | Effect |
|-------|------|--------|
| LLM responses | `athena_cache/` (`ATHENA_CACHE_DIR`) | Identical prompts → no repeat API cost; **required for cheap RQ repeats 2–3** |
| arXiv search | same tree | Repeated topic strings hit cache |

```python
from athena.llm.client import LLMClient
LLMClient.clear_cache()  # force fresh LLM calls
```

**Reproducing exact judge scores:** Keep cache from the original run or accept small drift if models/providers update.

---

## 4. Key numbers checklist

### 4.1 HALLMARK F1-H = 0.747

```bash
bash scripts/install_hallmark.sh
.venv-eval/bin/python scripts/run_hallmark_eval.py \
  --split dev_public --analyze --delay 0.5 \
  --output results/athena_dev_public_full.json \
  --comparison-md results/athena_vs_baselines_full.md
```

See [HALLMARK.md](HALLMARK.md) for mini-set shortcut (`--limit 50`).

### 4.2 RQ1 / RQ2 / RQ3 (60 runs each)

```bash
pip install matplotlib scipy

# Step 1: reference pools (slow; 20 topics)
python scripts/run_experiments.py build-pools --topic-sleep 90 --sleep-after-429 120

# Step 2–3: experiments (uses diskcache heavily after first repeat)
python scripts/run_experiments.py rq1 --repeats 3
python scripts/run_experiments.py rq2 --repeats 3
python scripts/run_experiments.py rq3
# Uses bundled examples/hallmark_metrics_sample.json + examples/pipeline_report_sample.json by default

# Step 4: stats + figures
python scripts/run_experiments.py analysis
# → results/experiments/experiment_summary.md
# → results/experiments/figures/rq*.png
```

**Checkpointing:** Each topic writes `results/experiments/rq{1,2}/by_topic/tXX.json`. Resume after interrupt without `--fresh`.

**Pilot (3 topics, 1 repeat, no judge API):**

```bash
python scripts/run_experiments.py rq1 --limit 3 --repeats 1 --skip-judge
```

### 4.3 Human anchor

```bash
python scripts/build_human_anchor.py
# Reads rq1/latest.json → eval/judges/human_anchor_template.csv
# Prints κ / agreement vs LLM judge
```

### 4.4 End-to-end pipeline demo

```bash
python scripts/run_pipeline.py "retrieval augmented generation" \
  --output results/pipeline_report.json
streamlit run app/streamlit_app.py
```

---

## 5. Expected summary statistics

After a full RQ run, `experiment_summary.md` should show approximately:

| Claim | Expected direction |
|-------|-------------------|
| Multi coverage > single | Significant (Δ≈+0.07) |
| Multi depth > single | Significant favoring **single** |
| Pairwise multi preference | Not significant (~53%) |
| Critic lowers fake rate | Not significant |
| Critic depth vs no critic | Significant favoring **no critic** |
| Pipeline verified-only fake rate | 0% (descriptive, small n) |

Exact *p*-values depend on cache-complete reruns; see report for reference run.

---

## 6. Test suite (regression, no API)

```bash
pytest tests/ -q
```

Core offline coverage: `test_citation_validator.py`, `test_hallmark_adapter.py`, `test_pipeline.py`, `test_eval_metrics.py`.

---

## 7. What is NOT committed

| Path | Reason |
|------|--------|
| `results/` | Generated metrics, figures, JSON |
| `data/`, `athena_cache/` | Runtime DB + caches |
| `.env` | Secrets |

To share numbers publicly, copy `experiment_summary.md` or figures into a release / paper appendix manually.
