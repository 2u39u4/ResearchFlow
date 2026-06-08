# Depth rubric (LLM-as-judge for RQ evaluation)

Score **1–5** for the analytical depth of a system's output on a given research topic.

| Score | Criteria |
|-------|----------|
| **5** | Multiple concrete gaps/weaknesses tied to specific papers; actionable next steps; explicit cross-paper comparison. |
| **4** | Clear gaps with paper-level evidence; some comparison; minor vagueness. |
| **3** | Generic but relevant gaps; uneven evidence; limited comparison. |
| **2** | Mostly high-level platitudes; weak or missing paper linkage. |
| **1** | Off-topic, empty, or unsupported claims. |

## Pairwise preference (A/B blind)

Judge which output better supports literature review planning:

- Specificity of identified gaps
- Grounding in provided papers (no invented IDs)
- Actionable structure (outline / critique usefulness)

Return `A`, `B`, or `tie`.

## Bias controls

- Judge model **≠** subject model (see `JUDGE_LLM_*` in `.env`)
- Outputs are **de-identified** (labels A/B only)
- **Left-right order randomized** per comparison (`EVAL_RANDOM_SEED`)

## Human anchor (~20%)

Anchor files:

- `eval/judges/human_anchor_human.csv` — **real blind human annotation (n=12)** (cite this).
- `eval/judges/human_anchor_template.csv` — **reproducible heuristic proxy** (pipeline fixture
  / sanity check only). **Not** independent human labels.
- `eval/judges/human_anchor_blank.csv` — blank schema for additional raters.

Follow the full procedure (de-identified A/B, two independent raters, adjudication, κ) in
[`ANCHOR_PROTOCOL.md`](ANCHOR_PROTOCOL.md). Report Cohen's κ / Spearman vs the LLM judge via
`eval/analysis/stats.py`, and always state which anchor (proxy vs human) the numbers come from.
