"""Tests for the blind human-annotation harness (build -> fill -> un-blind)."""

from __future__ import annotations

import csv
import json

from eval.judges.blind_anchor import (
    BLIND_FIELDS,
    build_blind_packet,
    ingest_blind_ratings,
    render_system_output,
)


def _system(tag: str) -> dict:
    # Neutral content tags (no "multi"/"single") so tests check the renderer, not fixtures.
    return {
        "critiques": [
            {"type": "gap", "claim": f"{tag} gap claim", "evidence_paper_ids": ["arxiv:1"]},
        ],
        "outline": {
            "title": f"{tag} outline",
            "sections": [{"heading": "Intro", "bullets": [f"{tag} bullet"]}],
        },
    }


def _fake_rq1(n_topics: int = 6) -> dict:
    rows = []
    for i in range(n_topics):
        tid = f"t{i + 1:02d}"
        rows.append(
            {
                "topic_id": tid,
                "topic": f"topic {tid}",
                "domain": f"domain{i}",
                "repeat": 0,
                "coverage": {"multi_agent": 0.8, "single_agent": 0.7},
                "depth": {"multi_agent": 3, "single_agent": 4},
                "pairwise": {"winner": "tie"},
                "multi_agent": _system("ALPHA"),
                "single_agent": _system("BETA"),
            }
        )
    return {"rq": "rq1", "rows": rows}


def test_render_hides_system_identity():
    md = render_system_output(_system("ALPHA"))
    assert "Critiques" in md and "Outline" in md
    # Renderer must not inject system identity labels.
    assert "multi" not in md.lower() and "single" not in md.lower()


def test_build_packet_and_unblind_roundtrip(tmp_path):
    rq1 = tmp_path / "rq1.json"
    rq1.write_text(json.dumps(_fake_rq1()), encoding="utf-8")
    out_dir = tmp_path / "blind"

    paths = build_blind_packet(rq1, out_dir, fraction=0.5, repeat=0, seed=7)
    assert paths["packet"].exists() and paths["rating_csv"].exists() and paths["keymap"].exists()

    keymap = json.loads(paths["keymap"].read_text())
    # The packet must not leak which system is which.
    assert "multi" not in paths["packet"].read_text().lower()

    # Simulate a rater: always score MULTI=5, SINGLE=2, prefer the multi side.
    with paths["rating_csv"].open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and list(rows[0].keys()) == BLIND_FIELDS
    for row in rows:
        sid = row["sample_id"]
        mapping = keymap[sid]
        row["depth_A_1to5"] = "5" if mapping["A"] == "multi_agent" else "2"
        row["depth_B_1to5"] = "5" if mapping["B"] == "multi_agent" else "2"
        row["preference_A_B_tie"] = "A" if mapping["A"] == "multi_agent" else "B"
    with paths["rating_csv"].open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BLIND_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    out_csv = tmp_path / "human.csv"
    ingest_blind_ratings(paths["rating_csv"], paths["keymap"], out_csv)

    with out_csv.open(encoding="utf-8") as f:
        human = list(csv.DictReader(f))
    assert human
    # Un-blinding must recover multi=5, single=2, preference=multi for every row.
    for row in human:
        assert row["depth_multi_1to5"] == "5"
        assert row["depth_single_1to5"] == "2"
        assert row["preference_multi_single_tie"] == "multi"
