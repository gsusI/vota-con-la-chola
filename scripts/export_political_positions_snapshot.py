#!/usr/bin/env python3
"""Exporta una instantánea estática para /political-positions en GH Pages.

Objetivos:
- Trajectorias por persona y partido (topic_set + institución).
- Soporta comparación "declarado vs voto" (métodos).
- Cada punto incluye evidencia de respaldo y estado de revisión (topic_evidence_reviews).
- Incluye métricas de apoyo/rechazo por tipo de evidencia para trazabilidad.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/gh-pages/political-positions/data/stances.json")


TOPIC_SET_ID = 1
INSTITUTION_ID = 7
SNIPPET_MAX_CHARS = 280


SAFE_METHODS = ("combined", "votes", "declared")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta un snapshot de posiciones políticas explicables")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la base SQLite")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Ruta de salida JSON")
    p.add_argument("--topic-set-id", type=int, default=TOPIC_SET_ID)
    p.add_argument("--institution-id", type=int, default=INSTITUTION_ID)
    p.add_argument(
        "--methods",
        default=",".join(SAFE_METHODS),
        help="Métodos separados por coma (combined,votes,declared)",
    )
    p.add_argument("--max-topics", type=int, default=120, help="Máximo de topics exportados")
    p.add_argument("--max-persons", type=int, default=0, help="Máximo de personas (0=sin límite)")
    p.add_argument("--max-party-persons", type=int, default=0, help="Máximo miembros por partido para métricas")
    p.add_argument("--snapshot-date", default="", help="Fecha YYYY-MM-DD del corte (opcional)")
    p.add_argument("--max-evidence-samples", type=int, default=3, help="Muestras de evidencia por punto")
    p.add_argument("--max-methods-per-topic", type=int, default=5, help="Límite de métodos diferentes por punto (debería ser <= métodos")
    p.add_argument("--pretty", action="store_true", help="Salida prettificada")
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def clamp01(value: float) -> float:
    if math.isnan(value):
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def parse_date(value: Any) -> date | None:
    text = safe_text(value)
    if not text:
        return None
    if len(text) >= 10:
        text = text[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def is_date(value: Any) -> bool:
    return parse_date(value) is not None


def infer_snapshot_date(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """
        SELECT MAX(source_snapshot_date) AS d
        FROM topic_positions
        WHERE topic_set_id = ?
          AND institution_id = ?
          AND computed_method IN ('combined', 'votes', 'declared')
        """,
        (int(TOPIC_SET_ID), int(INSTITUTION_ID)),
    ).fetchone()
    if rows and is_date(rows[0]):
        return safe_text(rows[0])
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalize_methods(raw: str) -> tuple[str, ...]:
    methods = [safe_text(x).lower() for x in safe_text(raw).split(",")]
    out: list[str] = []
    for m in methods:
        if m in SAFE_METHODS and m not in out:
            out.append(m)
    if not out:
        return ("combined",)
    return tuple(out)


def build_qmarks(count: int) -> str:
    if count <= 0:
        return ""
    return ",".join("?" for _ in range(count))


def pick_topics(
    conn: sqlite3.Connection,
    *,
    topic_set_id: int,
    institution_id: int,
    methods: tuple[str, ...],
    max_topics: int,
) -> list[dict[str, Any]]:
    if max_topics <= 0:
        return []
    rows = conn.execute(
        f"""
        SELECT
          t.topic_id,
          COALESCE(t.label, '') AS topic_label,
          COALESCE(t.canonical_key, '') AS topic_key,
          COUNT(*) AS point_count,
          COALESCE(SUM(tp.evidence_count), 0) AS evidence_count_total
        FROM topic_positions tp
        JOIN topics t ON t.topic_id = tp.topic_id
        WHERE tp.topic_set_id = ?
          AND tp.institution_id = ?
          AND tp.computed_method IN ({build_qmarks(len(methods))})
        GROUP BY tp.topic_id, t.label, t.canonical_key
        ORDER BY evidence_count_total DESC, point_count DESC, t.label ASC
        LIMIT ?
        """,
        (topic_set_id, institution_id, *methods, int(max_topics)),
    ).fetchall()
    return [
        {
            "topic_id": safe_int(r["topic_id"]),
            "topic_label": safe_text(r["topic_label"]),
            "topic_key": safe_text(r["topic_key"]),
            "point_count": safe_int(r["point_count"]),
            "evidence_count_total": safe_int(r["evidence_count_total"]),
        }
        for r in rows
    ]


def pick_persons(
    conn: sqlite3.Connection,
    *,
    topic_set_id: int,
    institution_id: int,
    methods: tuple[str, ...],
    snapshot_date: str,
    max_persons: int,
    topic_ids: list[int],
) -> list[dict[str, Any]]:
    if not topic_ids:
        return []

    qmarks = build_qmarks(len(topic_ids))
    base = (
        f"""
        SELECT
          tp.person_id,
          COALESCE(p.full_name, '') AS full_name,
          COALESCE(p.canonical_key, '') AS canonical_key,
          COUNT(*) AS point_count,
          MAX(tp.as_of_date) AS latest_as_of,
          COALESCE(SUM(tp.evidence_count), 0) AS evidence_count_total
        FROM topic_positions tp
        JOIN persons p ON p.person_id = tp.person_id
        WHERE tp.topic_set_id = ?
          AND tp.institution_id = ?
          AND tp.computed_method IN ({build_qmarks(len(methods))})
          AND tp.topic_id IN ({qmarks})
          AND (? = '' OR tp.as_of_date <= ?)
        GROUP BY tp.person_id, p.full_name, p.canonical_key
        ORDER BY point_count DESC, evidence_count_total DESC, full_name ASC
        """
    )
    params = [topic_set_id, institution_id, *methods, *topic_ids, snapshot_date, snapshot_date]
    if max_persons > 0:
        base += " LIMIT ?"
        params.append(int(max_persons))
    rows = conn.execute(base, params).fetchall()

    return [
        {
            "person_id": safe_int(r["person_id"]),
            "full_name": safe_text(r["full_name"]),
            "canonical_key": safe_text(r["canonical_key"]),
            "point_count": safe_int(r["point_count"]),
            "latest_as_of": safe_text(r["latest_as_of"]),
            "evidence_count_total": safe_int(r["evidence_count_total"]),
        }
        for r in rows
    ]


def load_party_names(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    rows = conn.execute("SELECT party_id, COALESCE(name, '') AS name, COALESCE(acronym, '') AS acronym FROM parties")
    return {safe_int(r["party_id"]): (safe_text(r["name"]), safe_text(r["acronym"])) for r in rows}


def load_mandate_party_timeline(
    conn: sqlite3.Connection,
    *,
    person_ids: list[int],
    institution_id: int,
) -> dict[int, list[dict[str, Any]]]:
    if not person_ids:
        return {}
    qmarks = build_qmarks(len(person_ids))
    rows = conn.execute(
        f"""
        SELECT
          person_id,
          party_id,
          COALESCE(start_date, '') AS start_date,
          COALESCE(end_date, '') AS end_date,
          COALESCE(is_active, 0) AS is_active,
          COALESCE(source_snapshot_date, '') AS source_snapshot_date
        FROM mandates
        WHERE person_id IN ({qmarks})
          AND institution_id = ?
          AND party_id IS NOT NULL
          AND party_id > 0
        ORDER BY person_id ASC, start_date DESC
        """,
        (*person_ids, institution_id),
    ).fetchall()

    timeline: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pid = safe_int(row["person_id"])
        if pid <= 0:
            continue
        start = parse_date(row["start_date"])
        end = parse_date(row["end_date"])
        if end is None:
            end = date.max
        timeline[pid].append(
            {
                "party_id": safe_int(row["party_id"]),
                "start_date": start,
                "end_date": end,
                "is_active": safe_int(row["is_active"]) > 0,
                "source_snapshot_date": safe_text(row["source_snapshot_date"]),
            }
        )

    for entries in timeline.values():
        entries.sort(key=lambda item: (item["start_date"] or date.min), reverse=True)
    return timeline


def resolve_party_on_date(
    timeline: dict[int, list[dict[str, Any]]],
    person_id: int,
    as_of: str,
) -> int:
    point_date = parse_date(as_of)
    entries = timeline.get(int(person_id), [])
    if not entries:
        return 0

    if point_date is None:
        for entry in entries:
            if entry["is_active"]:
                return int(entry["party_id"])
        return int(entries[0]["party_id"]) if entries else 0

    for entry in entries:
        start = entry["start_date"] or date.min
        end = entry["end_date"] or date.max
        if start <= point_date <= end:
            return int(entry["party_id"])

    return int(entries[0]["party_id"]) if entries else 0


def pick_party_roster_limit(
    conn: sqlite3.Connection,
    *,
    institution_id: int,
    snapshot_date: str,
    topic_set_id: int,
    methods: tuple[str, ...],
    person_ids: list[int],
    topic_ids: list[int],
    max_party_persons: int,
) -> list[dict[str, Any]]:
    if max_party_persons <= 0:
        rows = conn.execute(
            """
            SELECT
              m.party_id,
              COALESCE(pa.name, '') AS party_name,
              COALESCE(pa.acronym, '') AS party_acronym,
              COUNT(DISTINCT m.person_id) AS member_count
            FROM mandates m
            JOIN parties pa ON pa.party_id = m.party_id
            WHERE m.institution_id = ?
              AND COALESCE(m.party_id, 0) > 0
              AND (m.start_date = '' OR m.start_date <= ?)
              AND (m.end_date = '' OR m.end_date >= ? OR m.end_date IS NULL)
            GROUP BY m.party_id
            ORDER BY party_name ASC
            """,
            (institution_id, snapshot_date, snapshot_date),
        ).fetchall()
        return [
            {
                "party_id": safe_int(r["party_id"]),
                "party_name": safe_text(r["party_name"]),
                "party_acronym": safe_text(r["party_acronym"]),
                "member_count": safe_int(r["member_count"]),
            }
            for r in rows
        ]

    if not person_ids or not topic_ids:
        return []

    # Estimación de partidos activos en el recorte para mantener orden estable.
    rows = conn.execute(
        f"""
        SELECT
          pa.party_id,
          COALESCE(pa.name, '') AS party_name,
          COALESCE(pa.acronym, '') AS party_acronym,
          COUNT(DISTINCT tp.person_id) AS person_points,
          COALESCE(SUM(tp.evidence_count), 0) AS evidence_count_total
        FROM topic_positions tp
        JOIN mandates m ON m.person_id = tp.person_id
        JOIN parties pa ON pa.party_id = m.party_id
        WHERE tp.topic_set_id = ?
          AND tp.institution_id = ?
          AND tp.computed_method IN ({build_qmarks(len(methods))})
          AND tp.topic_id IN ({build_qmarks(len(topic_ids))})
          AND tp.as_of_date <= ?
          AND tp.person_id IN ({build_qmarks(len(person_ids))})
          AND m.party_id IS NOT NULL
          AND m.party_id > 0
          AND m.institution_id = ?
        GROUP BY pa.party_id, pa.name, pa.acronym
        ORDER BY person_points DESC, evidence_count_total DESC
        LIMIT ?
        """,
        (
            topic_set_id,
            institution_id,
            *methods,
            *topic_ids,
            snapshot_date,
            *person_ids,
            institution_id,
            max_party_persons,
        ),
    ).fetchall()

    return [
        {
            "party_id": safe_int(r["party_id"]),
            "party_name": safe_text(r["party_name"]),
            "party_acronym": safe_text(r["party_acronym"]),
            "member_count": safe_int(r["person_points"]),
        }
        for r in rows
    ]


def fetch_topic_positions(
    conn: sqlite3.Connection,
    *,
    topic_set_id: int,
    institution_id: int,
    methods: tuple[str, ...],
    snapshot_date: str,
    person_ids: list[int],
    topic_ids: list[int],
    max_methods_per_topic: int,
    max_persons: int,
    max_topics: int,
) -> list[sqlite3.Row]:
    if not person_ids or not topic_ids:
        return []

    qmarks_persons = build_qmarks(len(person_ids))
    qmarks_topics = build_qmarks(len(topic_ids))
    limit_per_entity = int(max(max_methods_per_topic, 1))

    rows = conn.execute(
        f"""
        SELECT
          tp.person_id,
          tp.topic_id,
          COALESCE(t.label, '') AS topic_label,
          COALESCE(t.canonical_key, '') AS topic_key,
          COALESCE(tp.as_of_date, '') AS as_of_date,
          COALESCE(tp.window_days, 0) AS window_days,
          COALESCE(tp.stance, 'no_signal') AS stance,
          COALESCE(tp.score, 0.0) AS score,
          COALESCE(tp.confidence, 0.0) AS confidence,
          COALESCE(tp.evidence_count, 0) AS evidence_count,
          COALESCE(tp.last_evidence_date, '') AS last_evidence_date,
          COALESCE(tp.computed_method, '') AS computed_method,
          COALESCE(tp.computed_version, '') AS computed_version,
          tp.mandate_id,
          COALESCE(m.party_id, 0) AS direct_party_id,
          COALESCE(m.start_date, '') AS direct_party_start,
          COALESCE(m.end_date, '') AS direct_party_end
        FROM topic_positions tp
        JOIN topics t ON t.topic_id = tp.topic_id
        LEFT JOIN mandates m ON m.mandate_id = tp.mandate_id
        WHERE tp.topic_set_id = ?
          AND tp.institution_id = ?
          AND tp.computed_method IN ({build_qmarks(len(methods))})
          AND tp.topic_id IN ({qmarks_topics})
          AND tp.person_id IN ({qmarks_persons})
          AND (? = '' OR tp.as_of_date <= ?)
        ORDER BY tp.person_id ASC, tp.topic_id ASC, as_of_date ASC, tp.computed_method ASC, tp.position_id ASC
        """,
        (
            topic_set_id,
            institution_id,
            *methods,
            *topic_ids,
            *person_ids,
            snapshot_date,
            snapshot_date,
        ),
    ).fetchall()

    return rows


def fetch_evidence_rows(
    conn: sqlite3.Connection,
    *,
    topic_set_id: int,
    person_ids: list[int],
    topic_ids: list[int],
) -> list[sqlite3.Row]:
    if not person_ids or not topic_ids:
        return []

    rows = conn.execute(
        f"""
        SELECT
          evidence_id,
          person_id,
          topic_id,
          COALESCE(evidence_type, '') AS evidence_type,
          COALESCE(evidence_date, '') AS evidence_date,
          COALESCE(title, '') AS title,
          COALESCE(excerpt, '') AS excerpt,
          COALESCE(stance, 'no_signal') AS stance,
          COALESCE(confidence, 0.0) AS confidence,
          COALESCE(weight, 0.0) AS weight,
          COALESCE(source_id, '') AS source_id,
          COALESCE(source_url, '') AS source_url,
          source_record_pk
        FROM topic_evidence
        WHERE topic_set_id = ?
          AND person_id IN ({build_qmarks(len(person_ids))})
          AND topic_id IN ({build_qmarks(len(topic_ids))})
        ORDER BY person_id ASC, topic_id ASC, COALESCE(evidence_date, '' ) ASC, evidence_id ASC
        """,
        (
            topic_set_id,
            *person_ids,
            *topic_ids,
        ),
    ).fetchall()

    return rows

def fetch_reviews(conn: sqlite3.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          COALESCE(source_id, '') AS source_id,
          COALESCE(source_record_pk, '') AS source_record_pk,
          COALESCE(status, '') AS status,
          COALESCE(review_reason, '') AS review_reason,
          COALESCE(suggested_stance, '') AS suggested_stance,
          COALESCE(suggested_polarity, '') AS suggested_polarity,
          COALESCE(suggested_confidence, 0.0) AS suggested_confidence,
          COALESCE(updated_at, '') AS updated_at,
          COALESCE(note, '') AS note,
          COALESCE(extractor_version, '') AS extractor_version,
          review_id
        FROM topic_evidence_reviews
        ORDER BY updated_at ASC
        """
    ).fetchall()

    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (safe_text(row["source_id"]), safe_text(row["source_record_pk"]))
        # keep latest status by updated_at due ORDER BY asc and overwrite in loop
        out[key] = {
            "review_id": safe_int(row["review_id"]),
            "status": safe_text(row["status"]),
            "review_reason": safe_text(row["review_reason"]),
            "suggested_stance": safe_text(row["suggested_stance"]),
            "suggested_polarity": safe_text(row["suggested_polarity"]),
            "suggested_confidence": safe_float(row["suggested_confidence"]),
            "note": safe_text(row["note"]),
            "extractor_version": safe_text(row["extractor_version"]),
            "updated_at": safe_text(row["updated_at"]),
        }
    return out

def split_evidence_types(evidence_type: str) -> str:
    if evidence_type.startswith("declared:"):
        return "declared"
    if evidence_type.startswith("revealed:"):
        return "revealed"
    return "other"


def safe_url(value: str) -> str:
    if not value:
        return ""
    v = safe_text(value).lower()
    if v.startswith("http://") or v.startswith("https://"):
        return safe_text(value)
    return ""


def clip_snippet(text: str, max_chars: int = SNIPPET_MAX_CHARS) -> str:
    value = safe_text(text).replace("\n", " ").replace("\r", " ")
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars].rstrip()}…"


def build_evidence_by_person_topic(rows: list[sqlite3.Row]) -> dict[tuple[int, int], list[dict[str, Any]]]:
    out: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = (safe_int(r["person_id"]), safe_int(r["topic_id"]))
        out[key].append(
            {
                "evidence_id": safe_int(r["evidence_id"]),
                "evidence_type": safe_text(r["evidence_type"]),
                "evidence_date": safe_text(r["evidence_date"]),
                "title": safe_text(r["title"]),
                "excerpt": safe_text(r["excerpt"]),
                "stance": safe_text(r["stance"]),
                "confidence": safe_float(r["confidence"]),
                "weight": safe_float(r["weight"]),
                "source_id": safe_text(r["source_id"]),
                "source_url": safe_url(safe_text(r["source_url"])),
                "source_record_pk": safe_text(r["source_record_pk"]),
            }
        )

    for key, evidence_rows in out.items():
        evidence_rows.sort(
            key=lambda item: (
                parse_date(item["evidence_date"]) or date.min,
                item["evidence_id"],
            )
        )
    return out


def review_status_summary(review_lookup: dict[tuple[str, str], dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, int]:
    pending = resolved = ignored = 0
    for item in evidence:
        key = (safe_text(item["source_id"]), safe_text(item["source_record_pk"]))
        rev = review_lookup.get(key)
        if not rev:
            continue
        status = rev["status"]
        if status == "pending":
            pending += 1
        elif status == "resolved":
            resolved += 1
        elif status == "ignored":
            ignored += 1
    return {
        "pending": pending,
        "resolved": resolved,
        "ignored": ignored,
    }


def evidence_breakdown(evidence: list[dict[str, Any]]) -> dict[str, int]:
    breakdown = {
        "declared": 0,
        "revealed": 0,
        "other": 0,
    }
    for item in evidence:
        key = split_evidence_types(safe_text(item.get("evidence_type", "")))
        breakdown[key] = breakdown.get(key, 0) + 1
    return breakdown


def build_point_payload(
    row: sqlite3.Row,
    *,
    topic_labels: dict[int, str],
    party_map: dict[int, tuple[str, str]],
    party_timeline: dict[int, list[dict[str, Any]]],
    evidence_by_key: dict[tuple[int, int], list[dict[str, Any]]],
    reviews: dict[tuple[str, str], dict[str, Any]],
    max_evidence_samples: int,
) -> dict[str, Any]:
    person_id = safe_int(row["person_id"])
    topic_id = safe_int(row["topic_id"])
    as_of_date = safe_text(row["as_of_date"])

    party_id = safe_int(row["direct_party_id"])
    if party_id <= 0:
        party_id = resolve_party_on_date(party_timeline, person_id, as_of_date)

    evidence_rows = evidence_by_key.get((person_id, topic_id), [])
    selected: list[dict[str, Any]] = []
    if evidence_rows:
        point_date = parse_date(as_of_date)
        if point_date is None:
            selected = evidence_rows
        else:
            selected = [
                item
                for item in evidence_rows
                if (parse_date(item["evidence_date"]) or point_date) <= point_date
            ]
            if not selected:
                # if no evidence at/before date, fall back to the latest evidence for topic/person
                selected = evidence_rows

    selected_sorted = sorted(
        selected,
        key=lambda item: (
            parse_date(item["evidence_date"]) or date.min,
            safe_int(item["evidence_id"]),
        ),
        reverse=True,
    )

    breakdown = evidence_breakdown(selected_sorted)
    reviews_sum = review_status_summary(reviews, selected_sorted)

    return {
        "topic_id": topic_id,
        "topic_label": safe_text(row["topic_label"]),
        "topic_key": safe_text(row["topic_key"]),
        "as_of_date": as_of_date,
        "window_days": safe_int(row["window_days"]),
        "computed_method": safe_text(row["computed_method"]),
        "stance": safe_text(row["stance"]),
        "score": clamp01(safe_float(row["score"])),
        "confidence": clamp01(safe_float(row["confidence"])),
        "evidence_count": safe_int(row["evidence_count"]),
        "last_evidence_date": safe_text(row["last_evidence_date"]),
        "computed_version": safe_text(row["computed_version"]),
        "party_id": party_id,
        "party_label": party_map.get(party_id, ("", ""))[0] if party_id > 0 else "",
        "evidence_breakdown": breakdown,
        "review_summary": reviews_sum,
        "evidence_samples": [
            {
                "evidence_id": safe_int(item["evidence_id"]),
                "evidence_type": safe_text(item["evidence_type"]),
                "evidence_date": safe_text(item["evidence_date"]),
                "title": safe_text(item["title"]),
                "excerpt": clip_snippet(safe_text(item["excerpt"]), SNIPPET_MAX_CHARS),
                "stance": safe_text(item["stance"]),
                "source_url": safe_url(safe_text(item["source_url"])),
                "source_id": safe_text(item["source_id"]),
                "source_record_pk": safe_text(item["source_record_pk"]),
                "review": reviews.get((safe_text(item["source_id"]), safe_text(item["source_record_pk"]), ), {}),
            }
            for item in selected_sorted[:max(0, int(max_evidence_samples))]
        ],
    }


def derive_party_stance(*, members_total: int, members_with_signal: int, support: int, oppose: int, mixed: int, unclear: int) -> str:
    if members_total <= 0 or members_with_signal <= 0:
        return "no_signal"

    # coverage guard (mirrors citizen export heuristics)
    if members_total > 0:
        min_needed = max(1, min(3, members_total), int(math.ceil(members_total * 0.20)))
        if members_with_signal < min_needed:
            return "unclear"

    clear = int(support) + int(oppose) + int(mixed)
    if clear <= 0:
        return "unclear" if unclear > 0 else "no_signal"

    if support > 0 and oppose > 0:
        ratio = max(int(support), int(oppose)) / float(clear)
        if ratio < 0.75:
            return "mixed"

    return "support" if int(support) >= int(oppose) else "oppose"


def build_party_series(
    person_series: dict[int, list[dict[str, Any]]],
    party_map: dict[int, tuple[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[int, int, str, str], dict[str, Any]] = {}

    for person_id, points in person_series.items():
        seen: set[tuple[int, int, str]] = set()
        for point in points:
            topic_id = safe_int(point["topic_id"])
            party_id = safe_int(point["party_id"])
            if party_id <= 0:
                continue
            as_of = safe_text(point["as_of_date"])
            method = safe_text(point["computed_method"])
            key = (party_id, topic_id, as_of, method)
            bucket = grouped.setdefault(
                key,
                {
                    "party_id": party_id,
                    "topic_id": topic_id,
                    "topic_label": point["topic_label"],
                    "topic_key": point["topic_key"],
                    "as_of_date": as_of,
                    "computed_method": method,
                    "support_members": 0,
                    "oppose_members": 0,
                    "mixed_members": 0,
                    "unclear_members": 0,
                    "no_signal_members": 0,
                    "members_total": 0,
                    "evidence_count_total": 0,
                    "score_weighted_sum": 0.0,
                    "confidence_weighted_sum": 0.0,
                    "evidence_weight_total": 0.0,
                    "person_ids": set(),
                },
            )

            person_topic_key = (party_id, topic_id, method)
            if person_topic_key in seen:
                continue
            seen.add(person_topic_key)

            bucket["members_total"] += 1
            bucket["evidence_count_total"] += safe_int(point["evidence_count"])
            weight = safe_int(point["evidence_count"]) or 1
            bucket["score_weighted_sum"] += safe_float(point["score"]) * weight
            bucket["confidence_weighted_sum"] += safe_float(point["confidence"]) * weight
            bucket["evidence_weight_total"] += weight
            bucket["person_ids"].add(person_id)

            stance = safe_text(point["stance"])
            if stance == "support":
                bucket["support_members"] += 1
            elif stance == "oppose":
                bucket["oppose_members"] += 1
            elif stance == "mixed":
                bucket["mixed_members"] += 1
            elif stance == "unclear":
                bucket["unclear_members"] += 1
            else:
                bucket["no_signal_members"] += 1

    out: dict[str, list[dict[str, Any]]] = {}
    for key, bucket in grouped.items():
        party_id = int(bucket["party_id"])
        members_total = int(bucket["members_total"])
        members_signal = (
            int(bucket["support_members"]) + int(bucket["oppose_members"]) + int(bucket["mixed_members"]) + int(bucket["unclear_members"])
        )
        weight_total = float(bucket["evidence_weight_total"]) or 1.0
        score = float(bucket["score_weighted_sum"]) / weight_total
        confidence = float(bucket["confidence_weighted_sum"]) / weight_total
        stance = derive_party_stance(
            members_total=members_total,
            members_with_signal=members_signal,
            support=int(bucket["support_members"]),
            oppose=int(bucket["oppose_members"]),
            mixed=int(bucket["mixed_members"]),
            unclear=int(bucket["unclear_members"]),
        )
        party_payload = {
            "party_id": party_id,
            "party_name": party_map.get(party_id, ("", ""))[0],
            "party_acronym": party_map.get(party_id, ("", ""))[1],
            "topic_id": int(bucket["topic_id"]),
            "topic_label": safe_text(bucket["topic_label"]),
            "topic_key": safe_text(bucket["topic_key"]),
            "as_of_date": safe_text(bucket["as_of_date"]),
            "computed_method": safe_text(bucket["computed_method"]),
            "stance": stance,
            "score": clamp01(score),
            "confidence": clamp01(confidence),
            "support_members": int(bucket["support_members"]),
            "oppose_members": int(bucket["oppose_members"]),
            "mixed_members": int(bucket["mixed_members"]),
            "unclear_members": int(bucket["unclear_members"]),
            "no_signal_members": int(bucket["no_signal_members"]),
            "members_total": members_total,
            "evidence_count_total": int(bucket["evidence_count_total"]),
            "coverage": {
                "members_with_signal": members_signal,
                "members_total": members_total,
            },
        }

        out.setdefault(str(party_id), []).append(party_payload)

    for party_id in list(out.keys()):
        out[party_id].sort(
            key=lambda item: (safe_text(item["as_of_date"]), safe_text(item["topic_label"]), safe_text(item["computed_method"]),),
        )

    return out


def build_payload(
    conn: sqlite3.Connection,
    args: argparse.Namespace,
) -> dict[str, Any]:
    topic_set_id = int(args.topic_set_id)
    institution_id = int(args.institution_id)
    methods = normalize_methods(args.methods)
    max_topics = max(0, int(args.max_topics))
    max_persons = max(0, int(args.max_persons))
    max_evidence_samples = max(1, int(args.max_evidence_samples))

    snapshot_date = safe_text(args.snapshot_date) or infer_snapshot_date(conn)

    topics = pick_topics(
        conn,
        topic_set_id=topic_set_id,
        institution_id=institution_id,
        methods=methods,
        max_topics=max_topics if max_topics > 0 else 200,
    )
    topic_ids = [t["topic_id"] for t in topics]

    if not topic_ids:
        return {
            "meta": {
                "generated_at": now_utc_iso(),
                "snapshot_date": snapshot_date,
                "topic_set_id": topic_set_id,
                "institution_id": institution_id,
                "methods": methods,
                "error": "No hay topics para el scope solicitado",
            },
            "topics": [],
            "persons": [],
            "parties": [],
            "person_trajectories": {},
            "party_trajectories": {},
        }

    persons = pick_persons(
        conn,
        topic_set_id=topic_set_id,
        institution_id=institution_id,
        methods=methods,
        snapshot_date=snapshot_date,
        max_persons=max_persons if max_persons > 0 else 0,
        topic_ids=topic_ids,
    )
    person_ids = [p["person_id"] for p in persons]

    if not person_ids:
        return {
            "meta": {
                "generated_at": now_utc_iso(),
                "snapshot_date": snapshot_date,
                "topic_set_id": topic_set_id,
                "institution_id": institution_id,
                "methods": methods,
                "error": "No hay personas para el scope solicitado",
            },
            "topics": topics,
            "persons": [],
            "parties": [],
            "person_trajectories": {},
            "party_trajectories": {},
        }

    party_roster = pick_party_roster_limit(
        conn,
        topic_set_id=topic_set_id,
        institution_id=institution_id,
        snapshot_date=snapshot_date,
        methods=methods,
        person_ids=person_ids,
        topic_ids=topic_ids,
        max_party_persons=max(0, int(args.max_party_persons)),
    )

    party_ids = [p["party_id"] for p in party_roster if p.get("party_id")]
    party_map = load_party_names(conn)

    reviews = fetch_reviews(conn)
    evidence_rows = fetch_evidence_rows(
        conn,
        topic_set_id=topic_set_id,
        person_ids=person_ids,
        topic_ids=topic_ids,
    )
    evidence_by_key = build_evidence_by_person_topic(evidence_rows)

    mand_timeline = load_mandate_party_timeline(
        conn,
        person_ids=person_ids,
        institution_id=institution_id,
    )

    position_rows = fetch_topic_positions(
        conn,
        topic_set_id=topic_set_id,
        institution_id=institution_id,
        methods=methods,
        snapshot_date=snapshot_date,
        person_ids=person_ids,
        topic_ids=topic_ids,
        max_methods_per_topic=max(1, int(args.max_methods_per_topic)),
        max_persons=max_persons,
        max_topics=max_topics,
    )

    topic_labels = {t["topic_id"]: safe_text(t["topic_label"]) for t in topics}
    topic_keys = {t["topic_id"]: safe_text(t["topic_key"]) for t in topics}
    for t in topics:
        t["topic_key"] = safe_text(t.get("topic_key") or "")

    person_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    point_index: set[tuple[int, int, str, str]] = set()

    for row in position_rows:
        point = build_point_payload(
            row,
            topic_labels=topic_labels,
            party_map=party_map,
            party_timeline=mand_timeline,
            evidence_by_key=evidence_by_key,
            reviews=reviews,
            max_evidence_samples=max_evidence_samples,
        )
        key = (
            safe_int(row["person_id"]),
            safe_int(row["topic_id"]),
            safe_text(row["as_of_date"]),
            safe_text(row["computed_method"]),
        )
        if key in point_index:
            # deduplicate accidental duplicates in source data
            continue
        point_index.add(key)
        point["person_id"] = safe_int(row["person_id"])
        point["topic_label"] = safe_text(point.get("topic_label") or topic_labels.get(point["topic_id"], ""))
        point["topic_key"] = safe_text(point.get("topic_key") or topic_keys.get(point["topic_id"], ""))

        person_rows[str(point["person_id"])].append(point)

    for person_id in list(person_rows.keys()):
        person_rows[person_id].sort(
            key=lambda item: (
                safe_text(item.get("topic_label", "")),
                safe_text(item.get("as_of_date", "")),
                safe_text(item.get("computed_method", "")),
            )
        )

    party_rows = build_party_series(person_rows, party_map)

    party_lookup: dict[int, dict[str, Any]] = {}
    for row in party_roster:
        party_lookup[safe_int(row["party_id"])] = {
            "party_id": safe_int(row["party_id"]),
            "party_name": safe_text(row["party_name"]),
            "party_acronym": safe_text(row["party_acronym"]),
            "member_count": safe_int(row["member_count"]),
        }

    # Add party entities missing from roster but present in trajectories.
    for party_id in [safe_int(k) for k in party_rows.keys()]:
        if party_id > 0 and party_id not in party_lookup:
            party_name, party_acronym = party_map.get(party_id, ("", ""))
            party_lookup[party_id] = {
                "party_id": party_id,
                "party_name": party_name,
                "party_acronym": party_acronym,
                "member_count": 0,
            }

    persons_out: list[dict[str, Any]] = []
    for p in persons:
        pid = safe_int(p["person_id"])
        points = person_rows.get(str(pid), [])
        last_point = points[-1]["as_of_date"] if points else safe_text(p.get("latest_as_of", ""))
        persons_out.append(
            {
                "person_id": pid,
                "full_name": safe_text(p["full_name"]),
                "canonical_key": safe_text(p["canonical_key"]),
                "points_count": safe_int(p["point_count"]),
                "latest_as_of": last_point,
                "evidence_count_total": safe_int(p["evidence_count_total"]),
            }
        )

    parties_out = sorted(
        [
            {
                "party_id": value["party_id"],
                "name": value["party_name"],
                "acronym": value["party_acronym"],
                "member_count": value["member_count"],
                "point_count": sum(1 for row in party_rows.get(str(value["party_id"]), [])),
            }
            for value in party_lookup.values()
        ],
        key=lambda item: safe_text(item["name"]).lower(),
    )

    # Ensure only requested parties present, with stable order.
    if party_ids:
        parties_out = [
            row
            for row in parties_out
            if row["party_id"] in set(party_ids) or row["point_count"] > 0
        ]

    return {
        "meta": {
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "topic_set_id": topic_set_id,
            "institution_id": institution_id,
            "methods": list(methods),
            "max_persons": max_persons,
            "max_topics": max_topics,
            "max_evidence_samples": max_evidence_samples,
            "topic_count": len(topics),
            "person_count": len(persons),
            "party_count": len(parties_out),
            "review_pending": sum(item["review_summary"]["pending"] for points in person_rows.values() for item in points),
        },
        "topics": topics,
        "persons": persons_out,
        "parties": parties_out,
        "person_trajectories": person_rows,
        "party_trajectories": party_rows,
    }


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"ERROR: no existe la DB -> {db_path}")
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        payload = build_payload(conn, args)
    finally:
        conn.close()

    encoded = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, separators=None if args.pretty else (",", ":"))
    out_path.write_text(encoded, encoding="utf-8")
    print(f"OK political positions snapshot -> {out_path} ({len(encoded)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
