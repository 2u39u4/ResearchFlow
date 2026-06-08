"""RQ evaluation metric helpers (offline)."""

from __future__ import annotations

from eval.analysis.stats import cohens_kappa, mean_std, paired_ttest, spearman_rho
from eval.experiments.common import (
    coverage_rate,
    fake_citation_rate,
    fake_rate_with_validator_filter,
)


def test_coverage_rate():
    assert coverage_rate({"a", "b"}, {"a", "b", "c"}) == 2 / 3


def test_fake_citation_rate():
    rows = [
        {"status": "verified"},
        {"status": "not_found"},
        {"status": "mismatch"},
    ]
    r = fake_citation_rate(rows)
    assert r["total"] == 3
    assert abs(r["fake_rate"] - 1 / 3) < 1e-6


def test_fake_rate_with_validator_filter():
    rows = [
        {"status": "verified"},
        {"status": "not_found"},
    ]
    out = fake_rate_with_validator_filter(rows)
    assert out["without_validation"]["fake_rate"] == 0.5
    assert out["with_validation_verified_only"]["fake_rate"] == 0.0
    assert out["blocked_count"] == 1


def test_mean_std():
    s = mean_std([1.0, 2.0, 3.0])
    assert s["n"] == 3
    assert abs(s["mean"] - 2.0) < 1e-6


def test_paired_ttest_runs():
    r = paired_ttest([1.0, 2.0, 3.0], [1.1, 2.1, 3.1])
    assert r["n"] == 3


def test_agreement_metrics():
    assert cohens_kappa([1, 2, 3], [1, 2, 2]) is not None
    assert spearman_rho([1.0, 2.0, 3.0], [1.0, 2.5, 3.0]) is not None
