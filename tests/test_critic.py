"""Critic agent tests — evidence binding and novelty policy offline; LLM mocked."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from athena.agents.critic import (
    apply_novelty_policy,
    bind_evidence,
    check_relative_novelty,
    grounding_rate,
    run_critic,
    supported_only,
)
from athena.graph.nodes import critic_node
from athena.schemas.critique import Critique
from athena.schemas.knowledge_card import KnowledgeCard


def _card(paper_id: str, title: str = "Paper") -> KnowledgeCard:
    return KnowledgeCard(
        paper_id=paper_id,
        title=title,
        authors=["A Author"],
        year=2024,
        abstract="We study transformers and evaluation metrics.",
        source="arxiv",
    )


def test_bind_evidence_drops_invalid_ids():
    critiques = [
        Critique(
            claim="Gap exists",
            type="gap",
            evidence_paper_ids=["real:1", "fake:9"],
            confidence=0.8,
        )
    ]
    bound = bind_evidence(critiques, {"real:1"})
    assert bound[0].evidence_paper_ids == ["real:1"]
    assert bound[0].status == "supported"


def test_bind_evidence_unsupported_when_no_valid_ids():
    critiques = [
        Critique(
            claim="Unsupported gap",
            type="gap",
            evidence_paper_ids=["missing:1"],
            confidence=0.7,
        )
    ]
    bound = bind_evidence(critiques, {"other:1"})
    assert bound[0].status == "unsupported"
    assert bound[0].evidence_paper_ids == []


def test_absolute_novelty_marked_unsupported():
    claim = "This is the first ever method to solve X completely."
    _, status, _ = check_relative_novelty(claim, n_papers=10)
    assert status == "unsupported"


def test_relative_novelty_prefix_when_missing():
    claim = "No paper addresses efficient federated distillation."
    new_claim, status, note = check_relative_novelty(claim, n_papers=12)
    assert status == "supported"
    assert "Among the 12 retrieved papers" in new_claim
    assert "prefixed" in note


def test_apply_novelty_policy_leaves_gap_untouched():
    c = Critique(claim="Limited benchmarks in paper A.", type="gap", evidence_paper_ids=["a:1"])
    out = apply_novelty_policy([c], n_papers=5)
    assert out[0].claim == c.claim


def test_grounding_rate():
    critiques = [
        Critique(claim="a", type="gap", evidence_paper_ids=["x"], status="supported"),
        Critique(claim="b", type="gap", evidence_paper_ids=[], status="unsupported"),
    ]
    assert grounding_rate(critiques) == 0.5


@patch("athena.agents.critic.LLMClient")
def test_run_critic_mock_llm(mock_client_cls):
    payload = {
        "critiques": [
            {
                "claim": "Among the 2 retrieved papers, neither explores metric X.",
                "type": "novelty",
                "evidence_paper_ids": ["arxiv:1"],
                "confidence": 0.75,
            },
            {
                "claim": "Paper B lacks ablation studies.",
                "type": "weakness",
                "evidence_paper_ids": ["arxiv:2"],
                "confidence": 0.8,
            },
            {
                "claim": "Hallucinated evidence.",
                "type": "gap",
                "evidence_paper_ids": ["not-in-corpus"],
                "confidence": 0.9,
            },
        ]
    }
    mock_client = MagicMock()
    mock_client.return_value.chat.return_value = json.dumps(payload)
    mock_client_cls.return_value = mock_client

    cards = [_card("arxiv:1"), _card("arxiv:2")]
    result = run_critic("test topic", cards, llm=mock_client.return_value)

    assert result.corpus_size == 2
    assert len(result.critiques) == 3
    supported = supported_only(result.critiques)
    assert len(supported) == 2
    assert result.evidence_grounding_rate >= 0.5
    unsupported = [c for c in result.critiques if c.status == "unsupported"]
    assert any("not-in-corpus" in (c.notes or "") or not c.evidence_paper_ids for c in unsupported)


@patch("athena.graph.nodes.run_critic")
def test_critic_node(mock_run):
    from athena.agents.critic import CriticResult

    mock_run.return_value = CriticResult(
        topic="rag",
        corpus_size=1,
        critiques=[
            Critique(
                claim="Among the 1 retrieved papers, gap.", type="gap", evidence_paper_ids=["a:1"]
            )
        ],
        dropped_unsupported=0,
        evidence_grounding_rate=1.0,
        model="gpt-5.5",
        errors=[],
    )
    out = critic_node({"topic": "rag", "papers": [_card("a:1")]})
    assert len(out["critiques"]) == 1
    assert out["critic_meta"]["evidence_grounding_rate"] == 1.0


def test_critic_requires_papers():
    with pytest.raises(ValueError):
        run_critic("topic", [])
