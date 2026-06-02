# Athena Research Assistant

Multi-agent research copilot for academic literature review with citation verification and evidence-grounded gap analysis.

## Quick start (W1)

```bash
cd ResearchFlow
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — OPENAI_API_KEY optional for smoke test (LLM step skipped if empty)
python scripts/smoke_test.py
pytest tests/test_w1_storage.py -q
```

## W2 — Research retrieval

```bash
python scripts/run_research.py "retrieval augmented generation"
# JSON output; exit 1 if fewer than 10 unique cards (use --min-cards to adjust)
```

Searches **arXiv**, **Semantic Scholar**, and **Crossref**, deduplicates by DOI/title, returns `KnowledgeCard` metadata from APIs only (no LLM-hallucinated titles).

## Semantic Scholar

`SEMANTIC_SCHOLAR_API_KEY` is optional. Without a key, the client uses **anonymous** access (~1 req/s). Add the key to `.env` when approved.

Set `CROSSREF_MAILTO` in `.env` for Crossref polite pool (recommended).

## W3 — Citation validation (deterministic, no LLM)

```bash
python scripts/validate_citations.py
# Or: python scripts/validate_citations.py my_citations.json
```

Returns `verified` / `not_found` / `mismatch` per reference via Crossref + Semantic Scholar + rapidfuzz.

```bash
pytest tests/test_citation_validator.py -q
```

## W4 — HALLMARK benchmark evaluation

Requires **Python 3.10+** (the main venv may be 3.9; use `python3.11` if available).

```bash
bash scripts/install_hallmark.sh   # .vendor/hallmark + .venv-eval (Python 3.10+)

.venv-eval/bin/python scripts/run_hallmark_eval.py --stats-only
.venv-eval/bin/python scripts/run_hallmark_eval.py --split dev_public --limit 50 --analyze \
  --output results/athena_dev_public_50.json \
  --comparison-md results/athena_vs_baselines.md
```

Maps Athena `verified` / `not_found` / `mismatch` → HALLMARK `VALID` / `HALLUCINATED` (see `eval/citebench/mapping.md`).

Full `dev_public` (~1,119 entries) hits Crossref/S2 APIs — use `--delay` and expect long runtimes.

```bash
pytest tests/test_hallmark_adapter.py -q
```

## Project layout

```
athena/          # core package (agents, tools, llm, storage, graph, rag)
eval/            # benchmarks & experiments (HALLMARK in W4)
app/             # Streamlit UI (W7)
scripts/         # smoke_test.py, run_research.py
tests/
```

## Clear LLM cache

```python
from athena.llm.client import LLMClient
LLMClient.clear_cache()
```
