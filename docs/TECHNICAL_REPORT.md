# Athena: Evidence-Grounded Research Assistance with Deterministic Citation Verification

**Technical report / workshop paper draft**  
*Athena Research Assistant — ResearchFlow repository*

---

## Abstract

Large language models are increasingly used for scholarly literature review, yet they routinely produce ungrounded claims and fabricated citations. **Athena** is a LangGraph-based multi-agent system that separates *generative* reasoning from *deterministic* verification: a Critic agent binds every gap claim to retrieved paper IDs, a Writer produces outline scaffolding (not full manuscripts), and a non-LLM Citation Validator resolves references against Crossref, Semantic Scholar, and arXiv. We evaluate the validator on the public **HALLMARK** benchmark (F1-H **0.747** on `dev_public`) and run three controlled experiments over 20 cross-domain topics: multi-agent vs single-agent coverage and depth (RQ1), Critic ablation (RQ2), and pipeline-level fake-citation reduction (RQ3). A bias-controlled protocol uses a judge model distinct from the subject system plus human anchors on a stratified 20% sample. Multi-agent outputs achieve significantly higher literature **coverage** (+6.8 pp, *p*≈4.4×10⁻⁵) but not significantly higher blind preference; Critic improves evidence grounding to 100% without significantly lowering fake citation rate in our ablation. We discuss limitations including LLM-judge bias on multi-agent verbosity and the verified-only filtering trade-off.

---

## 1. Introduction

### 1.1 Problem

LLM research assistants risk two failure modes relevant to graduate-level work:

1. **Citation hallucination** — bibliographic entries that do not resolve in scholarly APIs.
2. **Shallow gap analysis** — generic critiques without paper-level evidence or cross-corpus comparison.

Tools marketed as “paper writers” amplify academic-integrity concerns. Athena is positioned as **research assistance**: structured retrieval, evidence-bound critique, outline scaffolding with explicit author TODOs, and machine-checkable citation status.

### 1.2 Contributions

1. **Deterministic citation verification pipeline** evaluated on HALLMARK with published baseline comparison.
2. **Evidence-grounded gap discovery** — supported critiques require `evidence_paper_ids` from the retrieved corpus; relative (not absolute) novelty phrasing.
3. **Reproducible evaluation protocol** — TopicSet with fixed pool protocol, cross-model LLM judges, blind pairwise preference, human anchors, paired statistics over 60 matched runs per RQ.

### 1.3 Non-goals

- Full paper generation or ghostwriting.
- Absolute novelty guarantees beyond the retrieved set.
- Production PDF RAG in the Streamlit demo (upload path exists; FAISS indexing is not wired to retrieval in the current build).

---

## 2. System architecture

```
User topic (+ optional PDFs, constraints)
        │
        ▼
┌───────────────┐
│   Planner     │  Task DAG (JSON schema)
└───────┬───────┘
        ▼
┌───────────────┐     arXiv / Semantic Scholar / Crossref
│   Research    │ ──► KnowledgeCard corpus (API metadata only)
└───────┬───────┘
        ▼
┌───────────────┐     gap / weakness / relative novelty
│   Critic      │ ──► each claim → evidence_paper_ids[]
└───────┬───────┘
        ▼
┌───────────────┐     sections + bullets + evidence tags
│   Writer      │ ──► outline scaffold ([author to complete] markers)
└───────┬───────┘
        ▼
┌───────────────┐     NO LLM — API + fuzzy match
│  Validator    │ ──► verified | not_found | mismatch
└───────┬───────┘
        ▼
 Structured report + trace + validation_report
```

**Implementation:** `athena/graph/` (LangGraph), agents in `athena/agents/`, validator in `athena/tools/citation_validator.py`, demo UI in `app/streamlit_app.py`.

**Shared state:** `AthenaState` carries papers, critiques, outline, citations, validation results, and step-level `trace` for auditability.

---

## 3. Methods

### 3.1 Citation Validator (deterministic)

Given a structured `Citation` (title, authors, year, DOI, venue), the validator:

1. Resolves DOI via Crossref when present.
2. Falls back to title search (Crossref → Semantic Scholar) with `rapidfuzz` title matching (default threshold 90).
3. Compares year (±1 tolerance) and author overlap when a candidate is found.

Outputs: `verified`, `not_found`, or `mismatch`. No LLM participates in the match decision.

**HALLMARK mapping** (`eval/citebench/mapping.md`): `verified` → VALID; `not_found` and `mismatch` → HALLUCINATED (conservative for bibliographic errors).

### 3.2 Critic (evidence-grounded)

The Critic reads retrieved `KnowledgeCard` objects and emits typed critiques (`gap`, `weakness`, `novelty`). Rules enforced in code and prompts:

- Supported critiques must list non-empty `evidence_paper_ids` from the corpus.
- Absolute novelty claims are rejected; relative novelty must reference the retrieved set size.
- **Evidence grounding rate** = fraction of supported critiques with ≥1 valid evidence ID.

### 3.3 Writer (scaffolding only)

Produces an `Outline` with section headings, bullets, and per-section evidence IDs. Markers indicate where the human author must complete argumentation. This is intentional human-in-the-loop design.

### 3.4 Retrieval

Multi-source search with deduplication (`athena/tools/dedup.py`). Metadata fields on cards originate from API converters only — not LLM-invented titles or DOIs.

---

## 4. Evaluation methodology

### 4.1 HALLMARK (RQ3 — validator)

- **Split:** `dev_public` (~1,119 blind BibTeX entries).
- **Metrics:** Detection rate, F1-H (hallucination F1), tier-weighted F1, ECE.
- **Baselines:** Compared via HALLMARK’s bundled baseline results (`--comparison-md`).

### 4.2 TopicSet experiments (RQ1 / RQ2)

- **20 topics** across domains (`eval/topics/topic_set.json`).
- **Reference pools** built under fixed protocol (`eval/topics/protocol.md`): per-topic arXiv + Crossref search, deduplicated card snapshots in `eval/topics/pools/`.
- **Repeats:** 3 per topic → 60 matched rows per RQ.
- **Coverage (RQ1):** |output paper IDs ∩ pool| / |pool|.

### 4.3 LLM-as-judge (bias controls)

| Control | Implementation |
|---------|----------------|
| Judge ≠ subject | `JUDGE_LLM_MODEL` / `JUDGE_LLM_PROVIDER` ≠ `DEFAULT_LLM_*` |
| Depth rubric | 1–5 scale (`eval/judges/rubric.md`) |
| Blind pairwise | Outputs labeled A/B; left-right order seeded (`EVAL_RANDOM_SEED + repeat`) |
| Human anchor | ~20% stratified sample; Cohen's κ / Spearman vs judge (`eval/judges/human_anchor_template.csv`) |

### 4.4 Statistics

Paired two-sided *t*-tests on matched topic/repeat rows; 95% CIs (normal approx.); α=0.05; no multiple-comparison correction (noted as limitation).

---

## 5. Results

### 5.1 RQ1: Multi-Agent vs Single-Agent (n=60)

| Metric | Multi-Agent | Single-Agent | Significance |
|--------|-------------|--------------|--------------|
| Coverage | 0.855 ± 0.138 | 0.787 ± 0.158 | **p≈4.4×10⁻⁵** (multi higher) |
| Depth (judge 1–5) | 4.00 ± 0.71 | 4.55 ± 0.50 | **p≈5.7×10⁻⁵** (single higher) |
| Pairwise win rate (multi) | 53.3% | — | *p*≈0.70 vs 50% (NS) |

**Interpretation:** Multi-agent pipeline references more of the fixed pool but blind preference does not favor it; single-agent outputs score deeper on the LLM judge rubric.

### 5.2 RQ2: Critic ablation (n=60)

| Metric | No Critic | With Critic | Significance |
|--------|-----------|-------------|--------------|
| Fake citation rate | 0.172 ± 0.110 | 0.185 ± 0.100 | NS (*p*≈0.22) |
| Evidence grounding | — | 1.000 | By construction (supported → evidence) |
| Gap depth (judge) | 4.35 ± 0.58 | 4.00 ± 0.71 | **p≈0.007** (no critic higher) |

**Interpretation:** Critic enforces evidence binding but does not significantly reduce fake cites in this setup. The **depth advantage for the no-Critic path** is not a contradiction with Critic’s *design goal* (evidence binding and structured gaps), but a tension with the *LLM depth rubric*:

1. **Role split:** Critic is optimized to produce *supported, corpus-relative* claims; Writer then synthesizes critiques into an outline. The judge scores the **final bundled text** (critiques + outline), not “Critic quality” in isolation.
2. **Verbosity penalty (human anchor corroborates):** Multi-agent outputs often repeat corpus-level boilerplate (“Among the N retrieved papers…”). The depth rubric rewards cross-paper comparison, but penalizes repetition — Critic-mediated bundles can look **shallower** even when evidence binding is stricter.
3. **Writer freedom:** Without Critic input, Writer draws directly from raw `KnowledgeCard` abstracts and may produce broader, more “survey-like” sections that score higher on coverage-style depth cues, at the cost of weaker per-claim evidence discipline (grounding rate is undefined on that path).
4. **Fake-rate null result:** Both paths still emit citations that fail API resolution at similar rates; Critic’s value in RQ2 is primarily **grounding = 1.0**, not fake-rate reduction under our citation extraction policy.

We therefore report Critic as a **trust / evidence-binding module**, not as a guaranteed win on LLM-judged depth or fake-rate alone. Future work could judge Critic-only outputs, tighten Writer prompts to reduce template repetition, or use human depth scores as primary.

### 5.3 RQ3: Citation validation

| Setting | Result |
|---------|--------|
| HALLMARK F1-H (`dev_public`) | **0.747** |
| Detection rate | 0.776 |
| Tier-weighted F1 | 0.813 |
| ECE | 0.240 |
| Pipeline fake rate (all cites) | 27.8% (18 cites) |
| Pipeline fake rate (verified-only policy) | **0%** |

### 5.4 Human anchor agreement (n=12)

| Metric | Value |
|--------|-------|
| Depth (single) Cohen's κ | 0.544 |
| Depth (multi) Cohen's κ | −0.618 |
| Preference agreement | 58.3% |

Human raters penalized repetitive multi-agent phrasing that the LLM judge did not; this supports keeping human anchors in the protocol.

---

## 6. Limitations

1. **LLM judges** correlate imperfectly with humans, especially on verbose multi-agent outputs.
2. **No multiple-testing correction** across RQ claims.
3. **TopicSet size** (20 topics) limits generalization; pools depend on arXiv availability and rate limits.
4. **Verified-only policy** eliminates fake cites at the cost of dropping unresolved references.
5. **Subject / judge models** may change over time; diskcache makes exact LLM replications depend on cache state.
6. **Critic ablation** confounds “no critic” with different writer inputs — causal claims require care.

---

## 7. Conclusion

Athena demonstrates that scholarly assistance benefits from **splitting generation and verification**: deterministic validation achieves strong HALLMARK performance and can zero out pipeline fake citations under a strict filtering policy, while multi-agent structuring improves literature coverage with mixed effects on judged depth and user preference. The evaluation stack — public benchmark + TopicSet ablations + bias-aware judges + human anchors — is designed for **research credibility**, not opaque text generation.

---

## References (selected)

- HALLMARK benchmark (citation hallucination detection).
- Crossref, Semantic Scholar, arXiv APIs for metadata resolution.

---

## Appendix: Reproduction

See [REPRODUCTION.md](REPRODUCTION.md) and [HALLMARK.md](HALLMARK.md). Generated summaries: `results/experiments/experiment_summary.md` (after `python scripts/run_experiments.py analysis`).
