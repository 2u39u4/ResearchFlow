# HALLMARK results — full `dev_public` split (N = 1119)

Committed summary of the **complete** `dev_public` run (1,119 blind BibTeX entries),
so the headline F1-H is verifiable without re-running the multi-hour, API-bound benchmark.
Source run: `results/athena_dev_public_full.json` (regenerate with `docs/HALLMARK.md`).

## Headline metrics

| Metric | Value |
|--------|------:|
| Entries evaluated | 1119 (606 hallucinated, 513 valid) |
| Detection rate | 0.776 |
| **F1-H (hallucination F1)** | **0.747** |
| Tier-weighted F1 | 0.813 |
| False-positive rate | 0.357 |
| MCC | 0.423 |
| ECE | 0.240 |
| Coverage | 1.00 |

## Baselines (same split)

| Tool | N | Detection | F1-H | Tier-weighted F1 | FPR | ECE |
|------|---:|---:|---:|---:|---:|---:|
| **athena-validator** | 1119 | 0.776 | **0.747** | 0.813 | 0.357 | 0.240 |
| doi_only | 1068 | 0.268 | 0.373 | 0.329 | 0.185 | 0.143 |
| bibtexupdater | 1119 | 0.865 | 0.890 | 0.908 | 0.092 | 0.383 |

Athena clears the naive `doi_only` baseline by a wide margin and trails the stronger
`bibtexupdater` — a fair, honest placement for a no-LLM deterministic validator.

## Per-error-type F1 (where the validator is strong vs weak)

| Error type | F1 | Note |
|------------|---:|------|
| chimeric_title | 1.00 | strong |
| plausible_fabrication | 1.00 | strong |
| future_date | 1.00 | strong |
| hybrid_fabrication | 1.00 | strong |
| fabricated_doi | 0.99 | strong |
| placeholder_authors | 0.99 | strong |
| swapped_authors | 0.94 | strong |
| merged_citation | 0.93 | strong |
| near_miss_title | 0.86 | good |
| arxiv_version_mismatch | 0.83 | good |
| partial_author_list | 0.75 | moderate |
| wrong_venue | 0.53 | **weak** — venue checks are not in the match logic |
| preprint_as_published | 0.49 | **weak** — preprint↔published resolves as valid |
| nonexistent_venue | 0.34 | **weak** — title/DOI can still resolve |

**Takeaway:** deterministic matching excels at fabricated identifiers and titles, and is
weakest on *venue-only* discrepancies (by design — the validator checks DOI, title, author,
and year, not venue legitimacy). This is a clear, honest direction for future work.
