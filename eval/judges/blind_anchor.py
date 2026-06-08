"""
Blind human-annotation harness for the RQ1 depth/preference anchor.

This turns the RQ1 results into a **de-identified A/B rating packet** that a real
human fills in, then un-blinds the ratings into the standard human-anchor CSV used by
``eval/analysis/stats.py``. Unlike ``human_anchor.py`` (a reproducible heuristic proxy),
this produces *genuine* human labels.

Flow:
  1. ``build_blind_packet`` — sample rows, render each system's output as System A / B
     (order randomized per sample via a seed), write a markdown packet + blank CSV +
     a secret keymap (which of A/B is multi vs single).
  2. A human reads the packet and fills depth (1-5) + preference (A/B/tie) in the CSV.
  3. ``ingest_blind_ratings`` — map A/B back to multi/single using the keymap and write
     the standard human-anchor CSV.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from eval.judges.human_anchor import CSV_FIELDS, sample_id, select_stratified_rows

BLIND_FIELDS = [
    "sample_id",
    "topic_id",
    "depth_A_1to5",
    "depth_B_1to5",
    "preference_A_B_tie",
    "notes",
]


def render_system_output(system_data: dict[str, Any]) -> str:
    """Render one system's critiques + outline as de-identified markdown."""
    lines: list[str] = []
    critiques = system_data.get("critiques") or []
    lines.append(f"**Critiques ({len(critiques)}):**")
    if not critiques:
        lines.append("- (none)")
    for c in critiques:
        ctype = c.get("type", "?")
        claim = str(c.get("claim", "")).strip()
        n_ev = len(c.get("evidence_paper_ids") or [])
        lines.append(f"- _{ctype}_ (evidence: {n_ev} paper(s)): {claim}")

    outline = system_data.get("outline") or {}
    sections = outline.get("sections") or []
    lines.append("")
    lines.append(f"**Outline ({len(sections)} sections):**")
    for s in sections:
        lines.append(f"- **{s.get('heading', '')}**")
        for b in s.get("bullets") or []:
            lines.append(f"    - {b}")
    return "\n".join(lines)


def _ab_assignment(sample: str, seed: int) -> dict[str, str]:
    """Deterministically map A/B -> multi/single for one sample."""
    rng = random.Random(f"{seed}:{sample}")
    if rng.random() < 0.5:
        return {"A": "multi_agent", "B": "single_agent"}
    return {"A": "single_agent", "B": "multi_agent"}


def build_blind_packet(
    rq1_path: Path,
    out_dir: Path,
    *,
    fraction: float = 0.2,
    repeat: int = 0,
    seed: int = 42,
) -> dict[str, Path]:
    """Write the blind packet (markdown), blank rating CSV, and secret keymap."""
    payload = json.loads(Path(rq1_path).read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    picked = select_stratified_rows(rows, fraction=fraction, repeat=repeat)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    packet_md = out_dir / "annotation_packet.md"
    rating_csv = out_dir / "rating_sheet.csv"
    keymap_json = out_dir / "_keymap.json"

    keymap: dict[str, dict[str, str]] = {}
    md: list[str] = [
        "# Blind depth/preference annotation packet",
        "",
        "Score **Depth 1-5** for each system (see `eval/judges/rubric.md`) and pick a "
        "**Preference** (A / B / tie). You do NOT know which system is which — that is "
        "intentional. Fill `rating_sheet.csv`, then run `scripts/ingest_human_anchor.py`.",
        "",
        "Depth rubric: 5 = concrete gaps tied to specific papers + cross-paper comparison; "
        "3 = generic but relevant; 1 = off-topic/unsupported.",
        "",
    ]
    blank_rows: list[dict[str, str]] = []
    for r in picked:
        sid = sample_id(r["topic_id"], int(r["repeat"]))
        mapping = _ab_assignment(sid, seed)
        keymap[sid] = mapping
        a_data = r[mapping["A"]]
        b_data = r[mapping["B"]]

        md.append("---")
        md.append(f"## {sid} — topic: {r['topic']}")
        md.append("")
        md.append("### System A")
        md.append(render_system_output(a_data))
        md.append("")
        md.append("### System B")
        md.append(render_system_output(b_data))
        md.append("")

        blank_rows.append(
            {
                "sample_id": sid,
                "topic_id": r["topic_id"],
                "depth_A_1to5": "",
                "depth_B_1to5": "",
                "preference_A_B_tie": "",
                "notes": "",
            }
        )

    packet_md.write_text("\n".join(md), encoding="utf-8")
    with rating_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BLIND_FIELDS)
        writer.writeheader()
        writer.writerows(blank_rows)
    keymap_json.write_text(json.dumps(keymap, indent=2), encoding="utf-8")

    return {"packet": packet_md, "rating_csv": rating_csv, "keymap": keymap_json}


def _ab_to_system(value: str, mapping: dict[str, str]) -> str:
    """Map a preference token (A/B/tie) to multi/single/tie."""
    v = (value or "").strip().upper()
    if v == "TIE" or v == "":
        return "tie"
    if v in ("A", "B"):
        system = mapping[v]
        return "multi" if system == "multi_agent" else "single"
    raise ValueError(f"invalid preference {value!r} (expected A/B/tie)")


def ingest_blind_ratings(
    rating_csv: Path,
    keymap_json: Path,
    out_csv: Path,
) -> Path:
    """Un-blind a filled rating sheet into the standard human-anchor CSV."""
    keymap = json.loads(Path(keymap_json).read_text(encoding="utf-8"))
    out_rows: list[dict[str, str]] = []
    with Path(rating_csv).open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sid = row["sample_id"].strip()
            if not sid:
                continue
            depth_a = row.get("depth_A_1to5", "").strip()
            depth_b = row.get("depth_B_1to5", "").strip()
            if not depth_a or not depth_b:
                raise ValueError(f"{sid}: missing depth score (fill depth_A and depth_B)")
            mapping = keymap[sid]
            depth_by_system = {mapping["A"]: depth_a, mapping["B"]: depth_b}
            pref = _ab_to_system(row.get("preference_A_B_tie", ""), mapping)
            out_rows.append(
                {
                    "sample_id": sid,
                    "topic_id": row.get("topic_id", ""),
                    "depth_multi_1to5": depth_by_system["multi_agent"],
                    "depth_single_1to5": depth_by_system["single_agent"],
                    "preference_multi_single_tie": pref,
                    "notes": row.get("notes", ""),
                }
            )

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(out_rows)
    return out_csv
