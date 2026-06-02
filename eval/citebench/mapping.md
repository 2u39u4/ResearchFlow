# Athena Validator → HALLMARK label mapping

HALLMARK evaluates **binary** citation validity: each BibTeX entry is either `VALID` or `HALLUCINATED`.

Athena's deterministic `CitationValidator` returns three states:

| Athena status | HALLMARK label | Confidence (default) | Rationale |
|---------------|----------------|----------------------|-----------|
| `verified` | `VALID` | `0.90` | Metadata matches a resolved work in Crossref / Semantic Scholar / arXiv. |
| `not_found` | `HALLUCINATED` | `0.90` | No resolvable DOI and no title match above threshold — treat as non-existent citation. |
| `mismatch` | `HALLUCINATED` | `0.85` | A work was found but author/year/DOI/title checks failed — bibliographic error equivalent to a bad citation for detection purposes. |

## Design notes

- **`mismatch` → `HALLUCINATED` (conservative):** HALLMARK's task is hallucination *detection*. A reference that points to the wrong paper or wrong metadata is unsafe for downstream use, so we flag it as hallucinated rather than `VALID`.
- **Confidence:** Used for ECE calibration in HALLMARK. Higher values reflect stronger agreement between the validator signal and the mapped label. `mismatch` uses slightly lower confidence because resolution succeeded but field checks failed.
- **No `UNCERTAIN`:** Athena's validator always returns a definitive three-state result; we do not emit `UNCERTAIN`.
- **Blind evaluation:** Run tools on `BlindEntry` only (`entry.to_blind()`). Ground-truth `label` / `difficulty_tier` must not be passed to the validator.

## BibTeX → `Citation`

| BibTeX field | `Citation` field |
|--------------|------------------|
| `title` | `title` |
| `author` (split on ` and `) | `authors` |
| `year` | `year` (int if numeric) |
| `doi` | `doi` |
| `booktitle` or `journal` | `venue` |

Predictions must use `bibtex_key` from the blind entry (not a synthetic id).
