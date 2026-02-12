from __future__ import annotations

import re
import sqlite3
from typing import Any

from etl.politicos_es.util import now_utc_iso, stable_json


EXPEDIENTE_RE = re.compile(r"\b\d{3}/\d{6}/\d{4}\b")


def link_congreso_votes_to_initiatives(
    conn: sqlite3.Connection,
    *,
    max_events: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Best-effort deterministic linking using expediente numbers embedded in vote text.

    Congreso roll-call vote JSON doesn't expose initiative IDs; sometimes the free-text
    fields contain an expediente like '121/000001/0000'. When present, we link with
    confidence 1.0 and store the evidence.
    """
    # Preload initiatives by (legislature, expediente) for O(1) lookup.
    init_rows = conn.execute(
        """
        SELECT initiative_id, legislature, expediente
        FROM parl_initiatives
        WHERE expediente IS NOT NULL AND legislature IS NOT NULL
        """
    ).fetchall()
    init_map: dict[tuple[str, str], str] = {}
    for r in init_rows:
        init_map[(str(r["legislature"]), str(r["expediente"]))] = str(r["initiative_id"])

    q = """
    SELECT vote_event_id, legislature, expediente_text, subgroup_title, subgroup_text, title
    FROM parl_vote_events
    WHERE source_id = 'congreso_votaciones'
    ORDER BY vote_date, session_number, vote_number
    """
    if isinstance(max_events, int) and max_events > 0:
        q += f" LIMIT {int(max_events)}"

    vote_rows = conn.execute(q).fetchall()
    seen = 0
    inserted = 0
    now_iso = now_utc_iso()
    link_rows: list[dict[str, Any]] = []

    for row in vote_rows:
        seen += 1
        vote_event_id = str(row["vote_event_id"])
        leg = row["legislature"]
        if leg is None:
            continue
        leg = str(leg)

        haystacks = [
            ("expediente_text", row["expediente_text"]),
            ("subgroup_title", row["subgroup_title"]),
            ("subgroup_text", row["subgroup_text"]),
            ("title", row["title"]),
        ]
        found: list[tuple[str, str]] = []
        for field, text in haystacks:
            if not text:
                continue
            for m in EXPEDIENTE_RE.finditer(str(text)):
                found.append((field, m.group(0)))

        # Deduplicate deterministically.
        seen_pairs: set[tuple[str, str]] = set()
        deduped: list[tuple[str, str]] = []
        for field, exp in found:
            k = (field, exp)
            if k in seen_pairs:
                continue
            seen_pairs.add(k)
            deduped.append(k)

        for field, exp in deduped:
            initiative_id = init_map.get((leg, exp))
            if not initiative_id:
                continue
            evidence = stable_json({"field": field, "expediente": exp, "legislature": leg})
            link_rows.append(
                {
                    "vote_event_id": vote_event_id,
                    "initiative_id": initiative_id,
                    "link_method": "expediente_regex",
                    "confidence": 1.0,
                    "evidence_json": evidence,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
            )

    if not dry_run and link_rows:
        conn.executemany(
            """
            INSERT INTO parl_vote_event_initiatives (
              vote_event_id, initiative_id, link_method, confidence, evidence_json, created_at, updated_at
            ) VALUES (
              :vote_event_id, :initiative_id, :link_method, :confidence, :evidence_json, :created_at, :updated_at
            )
            ON CONFLICT(vote_event_id, initiative_id, link_method) DO UPDATE SET
              confidence=excluded.confidence,
              evidence_json=excluded.evidence_json,
              updated_at=excluded.updated_at
            """,
            link_rows,
        )
        inserted = len(link_rows)
        conn.commit()

    return {
        "events_seen": seen,
        "links_prepared": len(link_rows),
        "links_written": 0 if dry_run else inserted,
        "dry_run": bool(dry_run),
    }

