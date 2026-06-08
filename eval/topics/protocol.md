# TopicSet reference pool protocol (RQ evaluation)

Fixed retrieval protocol for building per-topic **reference paper pools** (RQ1 Coverage denominator).

## Inputs

- Topic string from `eval/topics/topic_set.json`
- `per_source_limit=10`, `min_cards=8`

## Retrieval

1. **arXiv**: query = topic string (short form, not Planner-expanded query)
2. **Crossref**: query = topic string (title search)
3. **Semantic Scholar**: skipped when `SEMANTIC_SCHOLAR_API_KEY` is empty

Same implementation as `athena.agents.research.run_research(..., arxiv_query=topic)`.

## Pool definition

- Deduplicate cards across sources (`tools/dedup.py`)
- **Reference pool** = set of `paper_id` values in the merged corpus
- Store full card snapshots in `eval/topics/pools/{topic_id}.json`

## Reproducibility

- Record `built_at` (UTC ISO), `protocol_version`, and `research_errors` in each pool file
- Rebuild: `python scripts/run_experiments.py build-pools`

## Why t01 often succeeds while t02+ hit 429

1. **First request** — arXiv anonymous quota is per-IP; the first topic in a batch behaves like a cold start.
2. **Disk cache** — if the topic string was searched before (e.g. pipeline demo on RAG), `athena_cache/arxiv` serves results with **zero** API calls (see log: `arxiv cache hit`).
3. **Burst traffic** — back-to-back topics + library internal retries caused t02–t04 to fail in the first batch run.

**Batch mitigation (same protocol, still requires arXiv):**

```bash
python scripts/run_experiments.py build-pools --topic-sleep 90 --sleep-after-429 120
# Skips t01 if pool already has arXiv; use --force to rebuild
```

- `--topic-sleep 90`: pause between topics (replicate t01 spacing)
- `--sleep-after-429 120`: longer pause after a 429 failure
- arXiv client `num_retries=1` + longer 429 backoff in `arxiv_search.py`

## Coverage metric (RQ1)

```
Coverage = |output_paper_ids ∩ reference_pool| / |reference_pool|
```

`output_paper_ids` = union of evidence IDs from critiques + outline sections (multi-agent or single-agent).
