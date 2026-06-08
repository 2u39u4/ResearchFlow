# Athena Research Assistant

> Multi-agent research copilot that **separates LLM generation from deterministic verification** to fight citation hallucination in scholarly literature review.

[![CI](https://github.com/2u39u4/ResearchFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/2u39u4/ResearchFlow/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-78%20passing-brightgreen)

Athena retrieves real papers from scholarly APIs, generates **evidence-grounded** gap analysis and outline scaffolding, and then verifies every citation **without an LLM in the matching logic** — so bibliographic claims are machine-checkable, not hallucinated. It is a *research-assistance* tool with an academic-integrity banner in the UI, **not** an essay or paper ghostwriter.

The core design bet — evaluated below on a public benchmark — is that **generation should be creative but verification should be deterministic**.

## Results at a glance

| Question | Result | Significance |
|----------|--------|--------------|
| Citation hallucination detection (HALLMARK `dev_public`, **full N=1119**) | **F1-H 0.747** · detection 0.776 · tier-weighted F1 0.813 | beats `doi_only` 0.373; see [breakdown](docs/evaluation/hallmark_full.md) |
| Pipeline fake-citation rate | 27.8% (all) → **0%** (verified-only policy) | deterministic filter |
| Multi-agent vs single-agent literature coverage | **0.855 vs 0.787** (+6.8 pp) | paired *t*-test *p* ≈ 4.4×10⁻⁵ |
| Blind pairwise preference (multi vs single) | 53.3% | **not** significant (*p* ≈ 0.70) — reported honestly |
| Critic evidence-grounding rate | **1.000** | by construction |

Numbers come from 60 matched runs per RQ (20 topics × 3 repeats). A **committed, read-only snapshot** of the statistics and figures lives in [`docs/evaluation/`](docs/evaluation/) so you can verify them without re-running the multi-hour experiments. Full method and caveats: [`docs/TECHNICAL_REPORT.md`](docs/TECHNICAL_REPORT.md).

## Why Athena

LLM research assistants fail in two ways that matter for graduate-level work:

1. **Citation hallucination** — references that do not resolve in any scholarly API.
2. **Shallow synthesis** — generic critiques with no paper-level evidence.

Athena addresses both: retrieval is API-only (no invented DOIs), critiques must cite `evidence_paper_ids` from the retrieved corpus, and citations are resolved deterministically against Crossref / Semantic Scholar / arXiv.

## How it works

```mermaid
flowchart LR
    T([Topic + optional private PDFs]) --> P[Planner]
    P --> R[Research]
    R --> C[Critic]
    C --> W[Writer]
    W --> V[Validator]
    V -->|verified enough| OUT([Report + trace])
    V -.->|too many unverified,<br/>budget remains| R
    R -.-> SRC[(arXiv / S2 / Crossref)]
    C -.- E[evidence-bound critiques]
    W -.- O[outline scaffold only]
    V -.- D[deterministic API match · no LLM]
    T -.- RAG[(Local PDF RAG · private, on-machine)]
```

| Agent / module | Responsibility |
|----------------|----------------|
| **Planner** | Turns a topic into a typed task plan (LLM with template fallback) |
| **Research** | Multi-source retrieval → deduplicated `KnowledgeCard` metadata (API-only) |
| **Critic** | `gap` / `weakness` / relative-`novelty` claims, each bound to corpus `evidence_paper_ids` |
| **Writer** | Outline scaffold with explicit `[TODO: author to complete]` markers (human-in-the-loop) |
| **Validator** | `verified` / `not_found` / `mismatch` via DOI + fuzzy title + author/year checks — **no LLM** |
| **Local PDF RAG** | Parse → chunk → embed → semantic search of uploaded PDFs, kept on-machine |

**Agent feedback loop (not a straight-line DAG):** the Validator emits a *conditional edge* — when the unverified-citation ratio exceeds `revision_fake_threshold` and the `max_revisions` budget remains, the graph loops back to Research with broader retrieval; otherwise it ends.

Implementation: LangGraph orchestration in `athena/graph/`, agents in `athena/agents/`, deterministic validator in `athena/tools/citation_validator.py`.

## Quick start

**Python 3.10+** (CI tests 3.10 / 3.11 / 3.12). Dependencies are split so the core install stays light:

| Install target | Use |
|----------------|-----|
| `requirements.txt` | Core: pipeline, retrieval, citation validation, local PDF RAG (hashing backend), Streamlit |
| `requirements-rag.txt` · `[rag]` | Optional: `sentence-transformers` + `faiss` for semantic embeddings |
| `requirements-eval.txt` · `[eval]` | Optional: `matplotlib` + `scipy` (RQ experiments) + HALLMARK runtime |
| `requirements.lock` | Pinned exact versions for reproducible installs |

```bash
cd ResearchFlow
python -m venv .venv          # Python 3.10+
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# OPENAI_API_KEY is optional for the smoke test (the LLM step is skipped if empty)
python scripts/smoke_test.py
```

API keys are all optional to get started: Semantic Scholar falls back to anonymous access (~1 req/s); set `CROSSREF_MAILTO` for Crossref's polite pool; set `SEMANTIC_SCHOLAR_API_KEY` when approved.

## Usage

**Retrieve papers** (arXiv + Semantic Scholar + Crossref, deduplicated, API metadata only):

```bash
python scripts/run_research.py "retrieval augmented generation"
# JSON to stdout; exits 1 if fewer than 10 unique cards (--min-cards to adjust)
```

**Validate citations** (deterministic, no LLM):

```bash
python scripts/validate_citations.py my_citations.json
# verified / not_found / mismatch per reference (Crossref + S2 + rapidfuzz)
```

**Evidence-grounded critique** (needs `OPENAI_API_KEY`):

```bash
python scripts/run_critic.py "retrieval augmented generation"
# gap / weakness / novelty; absolute-novelty phrasing is rejected
```

**End-to-end pipeline** (Planner → Research → Critic → Writer → Validator + revision loop):

```bash
python scripts/run_pipeline.py "retrieval augmented generation" \
  --output results/pipeline_report.json
# Tune the loop with max_revisions / revision_fake_threshold (.env or constraints)
```

**Streamlit demo UI:**

```bash
streamlit run app/streamlit_app.py   # or: bash scripts/run_streamlit.sh
```

Topic + constraints, live pipeline progress, citation-validation badges, critique evidence cards, outline scaffold, academic-integrity banner, trace/timing table, a **"Your PDFs"** private-RAG search tab, and JSON export/load. Optional password gate via `ATHENA_UI_PASSWORD` (recommended before exposing beyond localhost).

### Local PDF RAG (private, on-machine)

Uploaded PDFs are parsed, chunked, embedded, and indexed **locally** — never sent to scholarly APIs.

```python
from athena.rag import PdfRagIndex

index = PdfRagIndex()                 # default: deterministic, offline hashing embedder
index.add_pdf_path("paper.pdf")       # or .add_pdf_bytes(...) / .add_text(...)
for hit in index.query("what method is proposed?", top_k=3):
    print(hit.score, hit.chunk.doc_id, hit.chunk.text[:120])
```

Backends (via `.env`): `ATHENA_RAG_EMBEDDING_BACKEND=hashing` (default, offline) or `sentence-transformers` (needs the `[rag]` extra; set `ATHENA_RAG_USE_FAISS=true` for FAISS search).

## Evaluation

Three research questions over a cross-domain **TopicSet** (20 topics), with an **LLM-as-judge configured to differ from the subject model** plus a human-anchor sanity check.

| RQ | What it tests |
|----|---------------|
| **RQ1** | Multi-agent vs single-agent coverage & depth |
| **RQ2** | Critic ablation (evidence grounding, fake-rate, depth) |
| **RQ3** | Citation-validator accuracy on HALLMARK + pipeline fake-citation reduction |

```bash
pip install -r requirements-eval.txt          # matplotlib + scipy (+ HALLMARK runtime)

python scripts/run_experiments.py rq3          # bundled samples; no LLM, no API calls
python scripts/run_experiments.py rq1 --limit 3 --repeats 3   # needs OPENAI_API_KEY + judge key
python scripts/run_experiments.py rq2 --limit 3 --repeats 3
python scripts/run_experiments.py analysis     # figures + experiment_summary.md
```

**HALLMARK benchmark** (isolated env via `scripts/install_hallmark.sh`):

```bash
.venv-eval/bin/python scripts/run_hallmark_eval.py --split dev_public --limit 50 --analyze \
  --output results/athena_dev_public_50.json --comparison-md results/athena_vs_baselines.md
```

Athena `verified` / `not_found` / `mismatch` map to HALLMARK `VALID` / `HALLUCINATED` (`eval/citebench/mapping.md`). Bias controls (judge ≠ subject, blind A/B, seeded order) and the honest **proxy-vs-real human-anchor protocol** are documented in [`eval/judges/ANCHOR_PROTOCOL.md`](eval/judges/ANCHOR_PROTOCOL.md). A committed snapshot of all results lives in [`docs/evaluation/`](docs/evaluation/).

Reproduce the headline numbers: [`docs/REPRODUCTION.md`](docs/REPRODUCTION.md) · [`docs/HALLMARK.md`](docs/HALLMARK.md) (`EVAL_RANDOM_SEED=42`, cache in `athena_cache/`).

## Testing

All unit tests are offline (network calls are mocked):

```bash
pytest -q                       # full suite (78 passing, 1 skipped without HALLMARK)
pytest tests/test_rag.py -q     # PDF RAG module
pytest tests/test_pipeline.py -q  # graph, agents, revision loop
ruff check . && ruff format --check .   # lint + format (enforced in CI)
```

## Limitations & non-goals

Stated up front, because credibility matters more than hype:

- **Not a paper writer.** Writer produces an outline scaffold with author-completion markers, not submittable prose.
- **LLM judges ≠ humans.** On verbose multi-agent output the judge and the human anchor disagree; depth/preference results are mixed and reported as such (see the technical report).
- **The committed human anchor is a reproducible heuristic proxy**, not an independent human study — `ANCHOR_PROTOCOL.md` explains how to plug in real two-rater blind labels.
- **Verified-only policy trades recall for precision** — it zeroes fake citations by dropping unresolved references.
- **TopicSet is 20 topics**; statistics use no multiple-comparison correction. Generalization is limited.

## Project layout

```
athena/          # Core: agents, tools, llm, storage, graph
  rag/           # Local PDF RAG: parse, chunking, embeddings, vector store, index
eval/            # HALLMARK adapter (citebench), LLM judge, RQ experiments, analysis
  topics/pools/  # Committed reference pools (20 topics) — skip slow build-pools on clone
  judges/        # Depth rubric + human-anchor protocol (ANCHOR_PROTOCOL.md)
app/             # Streamlit demo UI (+ private PDF RAG tab)
docs/            # Technical report, HALLMARK & experiment reproduction, resume bullets
  evaluation/    # Committed read-only snapshot of RQ summary + figures
examples/        # Minimal RQ3 / pipeline samples (no results/ required)
scripts/         # CLI entry points
tests/           # Offline unit tests
.github/         # CI: ruff lint + pytest on Python 3.10 / 3.11 / 3.12
```

## Author & license

**Junye Zhao** — applying for MS in AI / ML, Fall 2027. Licensed under [MIT](LICENSE).
