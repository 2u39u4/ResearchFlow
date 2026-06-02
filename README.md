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

## Semantic Scholar

`SEMANTIC_SCHOLAR_API_KEY` is optional. Without a key, the client uses **anonymous** access (~1 req/s). Add the key to `.env` when approved.

## Project layout

```
athena/          # core package (agents, tools, llm, storage, graph, rag)
eval/            # benchmarks & experiments (HALLMARK in W4)
app/             # Streamlit UI (W7)
scripts/         # smoke_test.py
tests/
```

## Clear LLM cache

```python
from athena.llm.client import LLMClient
LLMClient.clear_cache()
```
