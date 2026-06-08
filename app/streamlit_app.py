"""
Athena Research Assistant — Streamlit demo UI.

Run: streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.components import (  # noqa: E402
    CRITIQUE_TYPE_LABELS,
    papers_by_id,
    render_integrity_banner,
    render_paper_card,
    status_badge,
    trace_timings,
)
from app.upload_utils import load_bounded_json, resolve_upload_path  # noqa: E402
from athena.agents.research import CriticalResearchSourcesError  # noqa: E402
from athena.config import get_settings  # noqa: E402
from athena.graph.build_graph import build_athena_graph, initial_state  # noqa: E402
from athena.graph.report import state_to_report  # noqa: E402
from athena.storage.sqlite import init_db, persist_traces  # noqa: E402

PIPELINE_STEPS = [
    ("planner", "Planner"),
    ("research", "Research"),
    ("critic", "Critic"),
    ("writer", "Writer"),
    ("prepare_citations", "Prepare citations"),
    ("validator", "Validator"),
]


def _save_uploaded_pdf(uploaded_file) -> Path | None:
    if uploaded_file is None:
        return None
    upload_dir = ROOT / "data" / "uploads"
    dest = resolve_upload_path(upload_dir, uploaded_file.name)
    dest.write_bytes(uploaded_file.getvalue())
    return dest


def _require_ui_auth() -> None:
    """Optional password gate when ATHENA_UI_PASSWORD is set."""
    password = get_settings().athena_ui_password.strip()
    if not password:
        return
    if st.session_state.get("ui_authenticated"):
        return
    st.subheader("Sign in")
    st.caption("Set `ATHENA_UI_PASSWORD` in `.env` when exposing this app beyond localhost.")
    entered = st.text_input("Password", type="password", key="ui_password_input")
    if st.button("Unlock", type="primary"):
        if entered == password:
            st.session_state.ui_authenticated = True
            st.rerun()
        st.error("Invalid password.")
    st.stop()


def _run_pipeline(
    topic: str,
    constraints: dict[str, Any],
    *,
    use_sqlite_checkpoint: bool,
) -> dict[str, Any] | None:
    init_db()
    graph = build_athena_graph(use_sqlite=use_sqlite_checkpoint)
    thread_id = f"ui-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": thread_id}}
    state = initial_state(topic, constraints=constraints, run_id=thread_id)

    completed: list[str] = []
    progress = st.progress(0.0, text="Starting pipeline…")
    log = st.empty()

    try:
        for event in graph.stream(state, config=config, stream_mode="updates"):
            for node_name in event:
                completed.append(node_name)
                idx = len(completed)
                progress.progress(
                    idx / len(PIPELINE_STEPS),
                    text=f"Completed: {node_name} ({idx}/{len(PIPELINE_STEPS)})",
                )
                log.markdown(f"- Finished **{node_name}**")
    except CriticalResearchSourcesError as exc:
        progress.empty()
        st.error("Research stopped: arXiv and Semantic Scholar both failed.")
        for err in exc.errors:
            st.caption(err)
        return None

    snapshot = graph.get_state(config)
    final_state = dict(snapshot.values) if snapshot and snapshot.values else {}
    report = state_to_report(final_state)
    if report.get("run_id"):
        persist_traces(str(report["run_id"]), report.get("trace") or [])
    progress.progress(1.0, text="Pipeline complete")
    return report


def _render_overview(report: dict[str, Any]) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Papers", len(report.get("papers") or []))
    critiques = report.get("critiques") or []
    supported = [c for c in critiques if c.get("status") == "supported"]
    col2.metric("Critiques (supported)", len(supported))
    val = report.get("validation_report") or []
    verified = sum(1 for v in val if v.get("status") == "verified")
    col3.metric("Citations verified", f"{verified}/{len(val)}")
    meta = report.get("critic_meta") or {}
    rate = meta.get("evidence_grounding_rate")
    col4.metric("Evidence grounding", f"{rate:.0%}" if rate is not None else "—")

    if report.get("research_errors"):
        st.warning("Research warnings:\n" + "\n".join(f"- {e}" for e in report["research_errors"]))
    sources = report.get("research_sources_ok") or {}
    if sources:
        labels = ", ".join(f"{k}: {'OK' if v else 'fail'}" for k, v in sources.items())
        st.caption(f"Retrieval sources — {labels}")


def _render_papers(report: dict[str, Any]) -> None:
    papers = report.get("papers") or []
    if not papers:
        st.info("No papers retrieved.")
        return
    for paper in papers:
        with st.expander(paper.get("title", paper.get("paper_id", "Paper"))[:80]):
            render_paper_card(paper)


def _render_critiques(report: dict[str, Any]) -> None:
    critiques = report.get("critiques") or []
    by_id = papers_by_id(report.get("papers") or [])
    if not critiques:
        st.info("No critiques generated.")
        return

    show_unsupported = st.checkbox("Show unsupported critiques", value=False)
    for c in critiques:
        if c.get("status") != "supported" and not show_unsupported:
            continue
        label = CRITIQUE_TYPE_LABELS.get(c.get("type", ""), c.get("type", ""))
        status = c.get("status", "supported")
        header = f"[{label}] {c.get('claim', '')[:100]}"
        with st.expander(header):
            st.caption(f"Status: **{status}** · confidence: {c.get('confidence', 0):.2f}")
            if c.get("notes"):
                st.caption(c["notes"])
            st.markdown(c.get("claim", ""))
            st.markdown("**Evidence papers**")
            ids = c.get("evidence_paper_ids") or []
            if not ids:
                st.caption("No linked paper IDs.")
            for pid in ids:
                paper = by_id.get(pid)
                if paper:
                    render_paper_card(paper)
                else:
                    st.caption(f"Unknown paper_id: `{pid}`")


def _render_outline(report: dict[str, Any]) -> None:
    draft = report.get("draft")
    if not draft:
        st.info("No outline produced.")
        return
    st.subheader(draft.get("title", "Outline"))
    if draft.get("academic_integrity_note"):
        st.caption(draft["academic_integrity_note"])
    by_id = papers_by_id(report.get("papers") or [])
    for section in draft.get("sections") or []:
        with st.expander(section.get("heading", "Section")):
            for bullet in section.get("bullets") or []:
                st.markdown(f"- {bullet}")
            if section.get("evidence_paper_ids"):
                st.markdown("**Evidence**")
                for pid in section["evidence_paper_ids"]:
                    paper = by_id.get(pid)
                    if paper:
                        st.caption(paper.get("title", pid))


def _render_validation(report: dict[str, Any]) -> None:
    results = report.get("validation_report") or []
    if not results:
        st.info("No validation results.")
        return
    for i, vr in enumerate(results):
        status = vr.get("status", "unknown")
        citation = vr.get("citation") or {}
        title = citation.get("title") or citation.get("doi") or f"Citation {i + 1}"
        with st.expander(f"{status_badge(status)} — {title[:70]}"):
            st.markdown(status_badge(status))
            st.json(citation)
            if vr.get("matched_title"):
                st.markdown(f"**Matched title:** {vr['matched_title']}")
            if vr.get("matched_doi"):
                st.markdown(f"**Matched DOI:** `{vr['matched_doi']}`")
            if vr.get("match_score"):
                st.caption(f"Title match score: {vr['match_score']:.1f}")
            details = vr.get("details") or {}
            if details:
                st.markdown("**Details**")
                st.json(details)


def _render_trace(report: dict[str, Any]) -> None:
    trace = report.get("trace") or []
    if not trace:
        st.info("No trace logs.")
        return
    rows = trace_timings(trace)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Raw trace JSON"):
        st.json(trace)


def main() -> None:
    st.set_page_config(
        page_title="Athena Research Assistant",
        page_icon="🔬",
        layout="wide",
    )
    st.title("Athena Research Assistant")
    st.caption("Multi-agent literature review · citation verification · evidence-grounded gaps")

    render_integrity_banner()
    _require_ui_auth()

    if "report" not in st.session_state:
        st.session_state.report = None
    if "last_run_at" not in st.session_state:
        st.session_state.last_run_at = None

    with st.sidebar:
        st.header("Settings")
        topic = st.text_input("Research topic", placeholder="e.g. retrieval augmented generation")
        year_min = st.number_input("Year from (optional)", min_value=1990, max_value=2030, value=2018)
        year_max = st.number_input("Year to (optional)", min_value=1990, max_value=2030, value=2026)
        domain = st.text_input("Domain / field (optional)", placeholder="e.g. NLP, systems")
        min_cards = st.slider("Minimum papers", 5, 20, 10)
        per_source = st.slider("Max per source", 5, 25, 15)
        use_checkpoint = st.checkbox("SQLite checkpoint", value=True)

        st.divider()
        st.subheader("PDF upload")
        pdf_file = st.file_uploader("Upload PDF (optional)", type=["pdf"])
        if pdf_file:
            path = _save_uploaded_pdf(pdf_file)
            st.caption(f"Saved to `{path}`")
            st.info(
                "PDF private RAG indexing is not wired in this build. "
                "The file is stored for future use; retrieval still uses public APIs."
            )

        st.divider()
        st.subheader("Load saved report")
        uploaded_json = st.file_uploader("JSON report", type=["json"])
        if uploaded_json and st.button("Load JSON"):
            try:
                st.session_state.report = load_bounded_json(uploaded_json.getvalue())
                st.session_state.last_run_at = datetime.now(timezone.utc).isoformat()
                st.success("Report loaded.")
            except (ValueError, json.JSONDecodeError) as exc:
                st.error(f"Could not load report: {exc}")

    constraints: dict[str, Any] = {
        "min_cards": min_cards,
        "per_source_limit": per_source,
        "year_min": year_min,
        "year_max": year_max,
    }
    if domain.strip():
        constraints["domain"] = domain.strip()

    run_col, _ = st.columns([1, 3])
    with run_col:
        run_clicked = st.button("Run full pipeline", type="primary", disabled=not topic.strip())

    if run_clicked:
        try:
            with st.spinner("Running Planner → Research → Critic → Writer → Validator…"):
                report = _run_pipeline(
                    topic.strip(),
                    constraints,
                    use_sqlite_checkpoint=use_checkpoint,
                )
            if report is None:
                st.stop()
            st.session_state.report = report
            st.session_state.last_run_at = datetime.now(timezone.utc).isoformat()
            st.success("Pipeline finished.")
        except Exception as exc:
            st.error(f"Pipeline failed: {exc}")
            st.exception(exc)

    report = st.session_state.report
    if not report:
        st.info("Enter a topic and click **Run full pipeline**, or load a saved JSON report from the sidebar.")
        return

    if st.session_state.last_run_at:
        st.caption(f"Last run: {st.session_state.last_run_at} · run_id: `{report.get('run_id', '—')}`")

    tab_overview, tab_papers, tab_critiques, tab_outline, tab_citations, tab_trace = st.tabs(
        [
            "Overview",
            "Papers",
            "Critiques & evidence",
            "Outline",
            "Citation validation",
            "Progress & logs",
        ]
    )

    with tab_overview:
        _render_overview(report)
        st.subheader("Tasks")
        st.json(report.get("tasks") or [])

    with tab_papers:
        _render_papers(report)

    with tab_critiques:
        _render_critiques(report)

    with tab_outline:
        _render_outline(report)

    with tab_citations:
        _render_validation(report)

    with tab_trace:
        _render_trace(report)

    st.divider()
    st.download_button(
        "Download report JSON",
        data=json.dumps(report, indent=2, ensure_ascii=False),
        file_name=f"athena_report_{report.get('run_id', 'run')}.json",
        mime="application/json",
    )


if __name__ == "__main__":
    main()
