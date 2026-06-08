"""
Deterministic citation verification — no LLM calls.

Pipeline: DOI lookup (Crossref) -> else title search (Crossref + Semantic Scholar)
-> rapidfuzz title match -> author surname + year checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import requests
from rapidfuzz import fuzz

from athena.config import Settings, get_settings
from athena.schemas.citation import Citation, ValidationResult, ValidationStatus
from athena.tools.arxiv_search import ArxivPaper, search_arxiv
from athena.tools.converters import arxiv_to_card, crossref_work_to_card, semantic_scholar_to_card
from athena.tools.crossref import lookup_doi, search_by_title
from athena.tools.normalize import normalize_doi, normalize_title
from athena.tools.semantic_scholar import lookup_by_doi as s2_lookup_by_doi
from athena.tools.semantic_scholar import search_papers as s2_search_papers


@dataclass
class ResolvedWork:
    title: str
    authors: list[str]
    year: Optional[int]
    doi: str
    source: str


def _author_surnames(authors: list[str]) -> set[str]:
    surnames: set[str] = set()
    for name in authors:
        parts = name.replace(",", " ").split()
        if parts:
            surnames.add(parts[-1].lower())
    return surnames


def _work_from_crossref(work: dict[str, Any]) -> Optional[ResolvedWork]:
    card = crossref_work_to_card(work)
    if not card:
        return None
    return ResolvedWork(
        title=card.title,
        authors=card.authors,
        year=card.year,
        doi=card.doi,
        source="crossref",
    )


def _work_from_s2(item: dict[str, Any]) -> Optional[ResolvedWork]:
    card = semantic_scholar_to_card(item)
    if not card:
        return None
    return ResolvedWork(
        title=card.title,
        authors=card.authors,
        year=card.year,
        doi=card.doi,
        source="semantic_scholar",
    )


def _safe_lookup_doi(doi: str) -> Optional[dict[str, Any]]:
    try:
        return lookup_doi(doi)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise
    except requests.RequestException:
        return None


def _arxiv_id_from_doi(doi: str) -> Optional[str]:
    match = re.search(r"arxiv\.(\d{4}\.\d+)(?:v\d+)?", doi, re.I)
    return match.group(1) if match else None


def _work_from_arxiv(paper: ArxivPaper) -> ResolvedWork:
    card = arxiv_to_card(paper)
    return ResolvedWork(
        title=card.title,
        authors=card.authors,
        year=card.year,
        doi=card.doi,
        source="arxiv",
    )


def _resolve_by_doi(doi: str) -> Optional[ResolvedWork]:
    """Crossref -> arXiv (for arxiv DOIs) -> Semantic Scholar."""
    cr = _safe_lookup_doi(doi)
    if cr:
        work = _work_from_crossref(cr)
        if work:
            return work

    arxiv_id = _arxiv_id_from_doi(doi)
    if arxiv_id:
        try:
            papers = search_arxiv(f"id:{arxiv_id}", max_results=1)
            if papers:
                return _work_from_arxiv(papers[0])
        except Exception:
            pass

    try:
        s2_item = s2_lookup_by_doi(doi)
        if s2_item:
            work = _work_from_s2(s2_item)
            if work:
                return work
    except Exception:
        pass
    return None


def _title_score(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return float(fuzz.ratio(na, nb))


def _search_candidates(title: str, top_k: int) -> list[ResolvedWork]:
    candidates: list[ResolvedWork] = []
    seen_doi: set[str] = set()

    try:
        crossref_works = search_by_title(title, rows=top_k)
    except requests.RequestException:
        crossref_works = []
    for work in crossref_works:
        resolved = _work_from_crossref(work)
        if resolved and resolved.doi and resolved.doi not in seen_doi:
            seen_doi.add(resolved.doi)
            candidates.append(resolved)
        elif resolved and not resolved.doi:
            candidates.append(resolved)

    try:
        for item in s2_search_papers(title, limit=top_k):
            resolved = _work_from_s2(item)
            if not resolved:
                continue
            if resolved.doi and resolved.doi in seen_doi:
                continue
            if resolved.doi:
                seen_doi.add(resolved.doi)
            candidates.append(resolved)
    except Exception:
        pass

    return candidates


def _best_title_match(query_title: str, candidates: list[ResolvedWork]) -> tuple[Optional[ResolvedWork], float]:
    best: Optional[ResolvedWork] = None
    best_score = 0.0
    for cand in candidates:
        score = _title_score(query_title, cand.title)
        if score > best_score:
            best_score = score
            best = cand
    return best, best_score


def _years_compatible(expected: Optional[int], actual: Optional[int], tolerance: int) -> bool:
    if expected is None or actual is None:
        return True
    return abs(expected - actual) <= tolerance


def _authors_compatible(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return True
    exp = _author_surnames(expected)
    act = _author_surnames(actual)
    if not exp:
        return True
    return bool(exp & act)


def _check_mismatch(
    citation: Citation,
    work: ResolvedWork,
    *,
    year_tolerance: int,
) -> list[str]:
    issues: list[str] = []
    if citation.year is not None and work.year is not None:
        if not _years_compatible(citation.year, work.year, year_tolerance):
            issues.append(f"year: expected {citation.year}, found {work.year}")
    if citation.authors and not _authors_compatible(citation.authors, work.authors):
        issues.append(
            f"authors: expected surnames {_author_surnames(citation.authors)}, "
            f"found {_author_surnames(work.authors)}"
        )
    if citation.title.strip():
        score = _title_score(citation.title, work.title)
        if score < 100 and score < 95:
            issues.append(f"title_score: {score:.1f} (titles differ slightly)")
    return issues


def _result(
    citation: Citation,
    status: ValidationStatus,
    work: Optional[ResolvedWork] = None,
    *,
    match_score: float = 0.0,
    details: Optional[dict[str, Any]] = None,
) -> ValidationResult:
    return ValidationResult(
        status=status,
        citation=citation,
        matched_title=work.title if work else "",
        matched_doi=work.doi if work else "",
        matched_authors=work.authors if work else [],
        matched_year=work.year if work else None,
        match_score=match_score,
        details=details or {},
    )


class CitationValidator:
    """Verify citations against Crossref / Semantic Scholar (deterministic)."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def validate(self, citation: Citation) -> ValidationResult:
        threshold = self.settings.citation_title_match_threshold
        year_tol = self.settings.citation_year_tolerance
        top_k = self.settings.citation_search_top_k

        doi = normalize_doi(citation.doi)
        if doi:
            work = _resolve_by_doi(doi)
            if work:
                issues = _check_mismatch(citation, work, year_tolerance=year_tol)
                via = f"doi:{work.source}"
                if issues:
                    return _result(
                        citation,
                        "mismatch",
                        work,
                        match_score=100.0,
                        details={"issues": issues, "resolved_via": via},
                    )
                return _result(
                    citation,
                    "verified",
                    work,
                    match_score=100.0,
                    details={"resolved_via": via},
                )
            if not citation.title.strip():
                return _result(
                    citation,
                    "not_found",
                    details={"reason": "doi_not_found", "doi": doi},
                )

        title = citation.title.strip()
        if not title:
            return _result(
                citation,
                "not_found",
                details={"reason": "no_title_for_search", "doi": doi},
            )

        candidates = _search_candidates(title, top_k)
        best, score = _best_title_match(title, candidates)
        if best is None or score < threshold:
            return _result(
                citation,
                "not_found",
                details={
                    "reason": "no_title_match",
                    "best_score": score,
                    "threshold": threshold,
                    "candidates_checked": len(candidates),
                },
            )

        if doi and best.doi and normalize_doi(best.doi) != doi:
            return _result(
                citation,
                "mismatch",
                best,
                match_score=score,
                details={
                    "issues": [f"doi: expected {doi}, found {best.doi}"],
                    "resolved_via": best.source,
                },
            )

        issues = _check_mismatch(citation, best, year_tolerance=year_tol)
        if issues:
            return _result(
                citation,
                "mismatch",
                best,
                match_score=score,
                details={"issues": issues, "resolved_via": best.source},
            )

        return _result(
            citation,
            "verified",
            best,
            match_score=score,
            details={"resolved_via": best.source},
        )


def validate_citation(citation: Citation, settings: Optional[Settings] = None) -> ValidationResult:
    return CitationValidator(settings).validate(citation)


def validate_citations(
    citations: list[Citation],
    settings: Optional[Settings] = None,
) -> list[ValidationResult]:
    validator = CitationValidator(settings)
    return [validator.validate(c) for c in citations]
