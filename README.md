# Athena Research Assistant

Multi-agent **research copilot** for academic literature review: evidence-grounded gap analysis, outline scaffolding (not full-paper generation), and **deterministic** citation verification against scholarly APIs.

> **Research positioning:** Athena targets LLM hallucination and shallow synthesis in scholarly settings. It is a *research assistance* tool with an academic-integrity banner in the UI — not an essay or paper ghostwriter.

> **Local planning docs** (`execute.md`, `deliverables.md`, `docs/local/`) are gitignored and not part of the public repository.

## What it does

| Capability | Description |
|------------|-------------|
| **Multi-source retrieval** | arXiv, Semantic Scholar, Crossref → structured `KnowledgeCard` metadata (API-only, no invented DOIs) |
| **Citation Validator** | `verified` / `not_found` / `mismatch` via Crossref + S2 + fuzzy title match — **no LLM** in the match logic |
| **Critic** | Gap / weakness / relative-novelty critiques, each bound to `evidence_paper_ids` from the corpus |
| **Writer** | Outline scaffold with author-completion markers |
| **Local PDF RAG** | Upload PDFs → parse → chunk → embed → semantic search of your own documents (stays on-machine, never sent to APIs) |
| **Pipeline** | LangGraph: Planner → Research → Critic → Writer → Validator, with a **citation-driven revision loop** |
| **Evaluation** | HALLMARK benchmark (F1-H **0.747** on `dev_public`) + RQ1/RQ2/RQ3 TopicSet experiments ([committed snapshot](docs/evaluation/)) |

## Architecture

```
Topic (+ optional private PDFs)
        │
        ▼
   Planner ──► Research ──► Critic ──► Writer ──► Validator ──► Report
                  ▲            │           │            │
                  │            │           │            ├─ deterministic API match
                  │            │           │            │
                  │            │           │            ▼
                  │            │           │     revise? (too many unverified
                  │            │           │      citations + budget left)
                  │            │           │            │
                  └────────────┴───────────┴────────────┘  (loop back, broaden retrieval)
                  │            └─ evidence-bound critiques
                  └─ arXiv / S2 / Crossref         Local PDF RAG (private, on-machine)
```

The Validator emits a **conditional edge**: if the unverified-citation ratio exceeds
`revision_fake_threshold` and the `max_revisions` budget remains, the graph loops back to
Research with broader retrieval; otherwise it ends. This is a real agent feedback loop,
not a fixed straight-line DAG.

**Documentation:** [docs/README.md](docs/README.md) — technical report, HALLMARK reproduction, experiment reproduction, resume bullets.

## Requirements

**Python 3.10+** (CI tests 3.10 / 3.11 / 3.12). Dependencies are split so the core
install stays light:

| File / extra | Use |
|--------------|-----|
| `requirements.txt` | Core: pipeline, retrieval, citation validation, local PDF RAG (hashing backend), Streamlit |
| `requirements-rag.txt` / `[rag]` | Optional: `sentence-transformers` + `faiss` for higher-quality semantic embeddings |
| `requirements-eval.txt` / `[eval]` | Optional: `matplotlib` + `scipy` (RQ experiments) + HALLMARK runtime |
| `requirements.lock` | Pinned exact versions for reproducible installs |

## Quick start

```bash
cd ResearchFlow
python -m venv .venv          # Python 3.10+
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — OPENAI_API_KEY optional for smoke test (LLM step skipped if empty)
python scripts/smoke_test.py
pytest tests/test_storage.py -q
```

## Research retrieval

```bash
python scripts/run_research.py "retrieval augmented generation"
# JSON output; exit 1 if fewer than 10 unique cards (use --min-cards to adjust)
```

Searches **arXiv**, **Semantic Scholar**, and **Crossref**, deduplicates by DOI/title, returns `KnowledgeCard` metadata from APIs only (no LLM-hallucinated titles).

```bash
pytest tests/test_dedup.py tests/test_converters.py tests/test_research.py -q
```

## Semantic Scholar

`SEMANTIC_SCHOLAR_API_KEY` is optional. Without a key, the client uses **anonymous** access (~1 req/s). Add the key to `.env` when approved.

Set `CROSSREF_MAILTO` in `.env` for Crossref polite pool (recommended).

## Citation validation (deterministic, no LLM)

```bash
python scripts/validate_citations.py
# Or: python scripts/validate_citations.py my_citations.json
```

Returns `verified` / `not_found` / `mismatch` per reference via Crossref + Semantic Scholar + rapidfuzz.

```bash
pytest tests/test_citation_validator.py -q
```

## Local PDF RAG (private, on-machine)

Upload PDFs to search your own documents alongside public retrieval. Uploaded files are
parsed, chunked, embedded, and indexed **locally** — they are never sent to scholarly APIs.

```python
from athena.rag import PdfRagIndex

index = PdfRagIndex()                      # default: deterministic hashing embedder
index.add_pdf_path("paper.pdf")            # or index.add_pdf_bytes(...) / index.add_text(...)
for hit in index.query("what method is proposed?", top_k=3):
    print(hit.score, hit.chunk.doc_id, hit.chunk.text[:120])
```

In the Streamlit UI, upload a PDF in the sidebar and use the **"Your PDFs"** tab to search it.

**Backends** (configurable via `.env`):

- `ATHENA_RAG_EMBEDDING_BACKEND=hashing` (default) — dependency-free, deterministic, offline.
- `ATHENA_RAG_EMBEDDING_BACKEND=sentence-transformers` — semantic embeddings (needs the
  `[rag]` extra); set `ATHENA_RAG_USE_FAISS=true` to use FAISS for search.

```bash
pip install -r requirements-rag.txt   # optional, for semantic embeddings + FAISS
pytest tests/test_rag.py -q
```

## HALLMARK benchmark evaluation

Full guide: [docs/HALLMARK.md](docs/HALLMARK.md). `scripts/install_hallmark.sh` creates an isolated `.venv-eval` with the HALLMARK runtime.

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

## Critic Agent (evidence-grounded gaps)

```bash
# Retrieve papers then critique (needs OPENAI_API_KEY)
python scripts/run_critic.py "retrieval augmented generation"

# Reuse saved research JSON
python scripts/run_research.py "your topic" > /tmp/papers.json
python scripts/run_critic.py "your topic" --papers-json /tmp/papers.json
```

Outputs `gap` / `weakness` / `novelty` critiques. Each claim must cite `paper_id`s from the retrieved corpus; absolute novelty phrasing is rejected. Relative novelty must refer to the retrieved set (e.g. “Among the N retrieved papers…”).

```bash
pytest tests/test_critic.py -q
```

## End-to-end pipeline (LangGraph)

```bash
python scripts/run_pipeline.py "retrieval augmented generation"
# Optional: --output results/pipeline_report.json --thread-id my-run-1
```

Runs **Planner → Research → Critic → Writer (outline scaffold) → Citation Validator** with a
**citation-driven revision loop** (re-research when too many citations fail verification),
step `trace`, and SQLite checkpointing (`data/athena_checkpoints.db`). Tune the loop with
`max_revisions` and `revision_fake_threshold` (in `.env` or pipeline constraints).

```bash
pytest tests/test_pipeline.py -q
```

## Streamlit UI

```bash
# Requires OPENAI_API_KEY and dependencies from requirements.txt
streamlit run app/streamlit_app.py
# Or: bash scripts/run_streamlit.sh
```

Features: topic + constraints, full pipeline run with step progress, citation validation badges, critique evidence cards, outline scaffolding, academic-integrity banner, trace/timing table, JSON export/load. Optional password gate via `ATHENA_UI_PASSWORD` when not running on localhost only.

```bash
pytest tests/test_streamlit_app.py -q
```

## Evaluation experiments (RQ1 / RQ2 / RQ3)

Cross-domain **TopicSet** (20 topics), **LLM-as-judge** (configured separately from the subject model), and reproducible RQ scripts. Full guide: [docs/REPRODUCTION.md](docs/REPRODUCTION.md). Results write-up: [docs/TECHNICAL_REPORT.md](docs/TECHNICAL_REPORT.md).

```bash
pip install matplotlib scipy   # figures + stats

# 1) Build reference pools (fixed protocol; slow — arXiv rate limits)
python scripts/run_experiments.py build-pools --limit 5

# 2) RQ3 only (bundled examples/ samples; no LLM; no large results/ files required)
python scripts/run_experiments.py rq3

# Judge smoke test (Gemini — paste GEMINI_API_KEY in .env first)
python scripts/smoke_judge_gemini.py

# 3) RQ1 / RQ2 (needs OPENAI_API_KEY; set JUDGE_LLM_* to a different provider/model, e.g. gemini)
python scripts/run_experiments.py rq1 --limit 3 --repeats 3
python scripts/run_experiments.py rq2 --limit 3 --repeats 3

# Pilot without judge API calls:
python scripts/run_experiments.py rq1 --topic-ids t01 --repeats 1 --skip-judge

# 4) Figures + markdown summary
python scripts/run_experiments.py analysis
```

**Outputs** (under `results/experiments/`, gitignored locally):

| Path | Description |
|------|-------------|
| `rq1/latest.json`, `rq2/latest.json`, `rq3/latest.json` | Per-RQ raw results |
| `figures/rq1_coverage.png`, `rq2_ablation.png`, `rq3_fake_citation.png` | Summary plots |
| `experiment_summary.md` | Statistical summary (CI, *t*-tests, human-anchor agreement) |

Human anchor template: `eval/judges/human_anchor_template.csv` (~20% stratified sample).

```bash
pytest tests/test_eval_metrics.py -q
```

## Project layout

```
athena/          # Core: agents, tools, llm, storage, graph
  rag/           # Local PDF RAG: pdf parse, chunking, embeddings, vector store, index
eval/            # HALLMARK adapter (citebench), LLM judge, RQ experiments, analysis
  topics/pools/  # Committed reference pools (20 topics) — skip slow build-pools on clone
  judges/        # Depth rubric + human-anchor protocol (ANCHOR_PROTOCOL.md)
app/             # Streamlit demo UI (+ private PDF RAG tab)
docs/            # Technical report, HALLMARK & experiment reproduction, resume bullets
  evaluation/    # Committed read-only snapshot of RQ summary + figures
examples/        # Minimal RQ3 / pipeline samples (no results/ required)
scripts/         # CLI entry points
tests/           # Offline unit tests (incl. test_rag.py)
.github/         # CI workflow (ruff lint + pytest on Python 3.10/3.11/3.12)
```

**Author:** Junye Zhao ([@2u39u4](https://github.com/2u39u4)) — sole developer and maintainer.

Licensed under [MIT](LICENSE).

## Reproducing published numbers

| Metric | Command / doc |
|--------|----------------|
| HALLMARK F1-H 0.747 | [docs/HALLMARK.md](docs/HALLMARK.md) |
| RQ1/RQ2/RQ3 stats | [docs/REPRODUCTION.md](docs/REPRODUCTION.md) |
| Seeds & cache | `EVAL_RANDOM_SEED=42`, `athena_cache/` |

## Clear LLM cache

```python
from athena.llm.client import LLMClient
LLMClient.clear_cache()
```
