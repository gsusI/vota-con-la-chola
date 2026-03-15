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
import shutil
import sqlite3
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/gh-pages/political-positions/data/stances.json")
PERSON_DETAIL_DIRNAME = "person-details"
PERSON_TRAJECTORY_CHUNK_DIRNAME = "person-trajectory-chunks"
PERSON_TRAJECTORY_CHUNK_SIZE = 25
PERSON_DEFAULT_ROWS_FILENAME = "person-default-rows.json"
PERSON_DEFAULT_ROWS_LIMIT = 400
PERSON_SEARCH_INDEX_FILENAME = "person-search-index.json"
PERSON_SEARCH_INDEX_MAX_TOPIC_CHUNKS = 8
PERSON_SORT_PREVIEW_DIRNAME = "person-sort-previews"
PERSON_SORT_PREVIEW_LIMIT = PERSON_DEFAULT_ROWS_LIMIT
PERSON_SORT_PREVIEW_SORTS = (
    "confidence_desc",
    "confidence_asc",
    "method",
    "stance",
    "as_of",
    "topic",
    "party",
)
TOPIC_SEARCH_INDEX_FILENAME = "topic-search-index.json"
TOPIC_SEARCH_INDEX_MAX_TOPICS = 8
TOPIC_PERSON_ROWS_DIRNAME = "topic-person-rows"
PERSON_TRAJECTORIES_FILENAME = "person-trajectories.json"
PARTY_TRAJECTORIES_FILENAME = "party-trajectories.json"


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


def normalize_search_text(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def extract_search_tokens(value: Any, *, min_len: int = 3) -> set[str]:
    text = normalize_search_text(value)
    if not text:
        return set()
    tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", text)
        if len(token) >= max(1, int(min_len))
        and not token.isdigit()
        and not re.fullmatch(r"[0-9a-f]{12,}", token)
        and not re.fullmatch(r"leg\d+", token)
        and token not in {"congreso", "senado", "derived"}
    }
    return tokens


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


def build_evidence_sample_payload(
    item: dict[str, Any],
    reviews: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    review = reviews.get((safe_text(item["source_id"]), safe_text(item["source_record_pk"])), {})
    review_status = safe_text(review.get("status"))
    sample = {
        "evidence_id": safe_int(item["evidence_id"]),
        "evidence_type": safe_text(item["evidence_type"]),
        "evidence_date": safe_text(item["evidence_date"]),
        "stance": safe_text(item["stance"]),
        "confidence": clamp01(safe_float(item["confidence"])),
        "excerpt": clip_snippet(safe_text(item["excerpt"] or item["title"]), SNIPPET_MAX_CHARS),
        "source_url": safe_url(safe_text(item["source_url"])),
        "source_id": safe_text(item["source_id"]),
    }
    if review_status:
        sample["review"] = {"status": review_status}
    if not sample["source_url"]:
        sample.pop("source_url", None)
    return sample


def point_detail_key(topic_id: int, as_of_date: str, computed_method: str) -> str:
    return f"{safe_int(topic_id)}|{safe_text(as_of_date)}|{safe_text(computed_method)}"


def method_priority(value: Any) -> int:
    method = safe_text(value).lower()
    if method == "combined":
        return 0
    if method == "votes":
        return 1
    if method == "declared":
        return 2
    return 3


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
            build_evidence_sample_payload(item, reviews)
            for item in selected_sorted[:max(0, int(max_evidence_samples))]
        ],
    }


def compact_payload_for_static_publish(payload: dict[str, Any]) -> dict[str, Any]:
    person_series = payload.get("_person_trajectory_payload", payload.get("person_trajectories", {}))
    for points in person_series.values():
        for point in points:
            point.pop("evidence_samples", None)
            for key in ("person_id", "topic_label", "topic_key", "party_label", "computed_version"):
                point.pop(key, None)
            if safe_int(point.get("window_days")) <= 0:
                point.pop("window_days", None)
            if safe_int(point.get("evidence_count")) <= 0:
                point.pop("evidence_count", None)
            if not safe_text(point.get("last_evidence_date")):
                point.pop("last_evidence_date", None)
            review_summary = point.get("review_summary") or {}
            if not any(safe_int(review_summary.get(name)) for name in ("pending", "resolved", "ignored")):
                point.pop("review_summary", None)
            evidence_summary = point.get("evidence_breakdown") or {}
            if not any(safe_int(evidence_summary.get(name)) for name in ("declared", "revealed", "other")):
                point.pop("evidence_breakdown", None)

    party_series = payload.get("_party_trajectory_payload", payload.get("party_trajectories", {}))
    for points in party_series.values():
        for point in points:
            for key in ("topic_label", "topic_key", "party_name", "party_acronym"):
                point.pop(key, None)

    return payload


def build_person_detail_payloads(
    person_rows: dict[str, list[dict[str, Any]]],
    *,
    snapshot_date: str,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for person_id, points in person_rows.items():
        evidence_samples_by_point: dict[str, list[dict[str, Any]]] = {}
        for point in points:
            samples = point.get("evidence_samples") or []
            if not samples:
                continue
            evidence_samples_by_point[
                point_detail_key(
                    safe_int(point.get("topic_id")),
                    safe_text(point.get("as_of_date")),
                    safe_text(point.get("computed_method")),
                )
            ] = samples
        out[str(safe_int(person_id))] = {
            "meta": {
                "person_id": safe_int(person_id),
                "snapshot_date": safe_text(snapshot_date),
            },
            "evidence_samples_by_point": evidence_samples_by_point,
        }
    return out


def write_person_detail_payloads(
    out_path: Path,
    detail_payloads: dict[str, dict[str, Any]],
) -> None:
    detail_dir = out_path.parent / PERSON_DETAIL_DIRNAME
    if detail_dir.exists():
        shutil.rmtree(detail_dir)
    detail_dir.mkdir(parents=True, exist_ok=True)
    for person_id, payload in detail_payloads.items():
        (detail_dir / f"{safe_int(person_id)}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


def build_person_default_rows(
    persons_out: list[dict[str, Any]],
    person_rows: dict[str, list[dict[str, Any]]],
    *,
    max_rows: int = PERSON_DEFAULT_ROWS_LIMIT,
) -> list[dict[str, Any]]:
    rows = build_person_flat_rows(persons_out, person_rows)
    sorted_rows = sort_person_rows(rows, "person")
    return [strip_internal_person_row(row) for row in sorted_rows[: max(1, int(max_rows))]]


def build_person_flat_rows(
    persons_out: list[dict[str, Any]],
    person_rows: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    stable_index = 0

    for person in persons_out:
        person_id = safe_int(person.get("person_id"))
        person_name = safe_text(person.get("full_name"))
        canonical_key = safe_text(person.get("canonical_key"))
        for point in person_rows.get(str(person_id), []):
            topic_id = safe_int(point.get("topic_id"))
            method = safe_text(point.get("computed_method")).lower()
            as_of = safe_text(point.get("as_of_date"))
            rows.append(
                {
                    "scope": "person",
                    "key": f"i-{person_id}-{topic_id}-{as_of}-{method}",
                    "personId": person_id,
                    "personName": person_name,
                    "canonicalKey": canonical_key,
                    "partyId": safe_int(point.get("party_id")),
                    "partyLabel": safe_text(point.get("party_label")),
                    "topicId": topic_id,
                    "topicLabel": safe_text(point.get("topic_label")),
                    "topicKey": safe_text(point.get("topic_key")),
                    "asOf": as_of,
                    "windowDays": safe_int(point.get("window_days")),
                    "method": method,
                    "stance": safe_text(point.get("stance")).lower(),
                    "score": clamp01(safe_float(point.get("score"))),
                    "confidence": clamp01(safe_float(point.get("confidence"))),
                    "evidenceCount": safe_int(point.get("evidence_count")),
                    "lastEvidenceDate": safe_text(point.get("last_evidence_date")),
                    "evidenceBreakdown": dict(point.get("evidence_breakdown") or {}),
                    "reviewSummary": dict(point.get("review_summary") or {}),
                    "samples": [],
                    "_stable_index": stable_index,
                }
            )
            stable_index += 1

    return rows


def strip_internal_person_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "_stable_index"}


def compact_topic_person_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"_stable_index", "scope", "topicId", "topicLabel", "topicKey", "samples"}
    }


def default_person_row_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        safe_text(item.get("personName")).casefold(),
        safe_text(item.get("topicLabel")).casefold(),
        -(parse_date(item.get("asOf")) or date.min).toordinal(),
        method_priority(item.get("method")),
        safe_int(item.get("topicId")),
        safe_int(item.get("_stable_index")),
    )


def sort_person_rows(rows: list[dict[str, Any]], sort_mode: str) -> list[dict[str, Any]]:
    mode = safe_text(sort_mode).lower() or "person"
    out = list(rows)

    if mode == "confidence_desc":
        out.sort(
            key=lambda item: (
                -clamp01(safe_float(item.get("confidence"))),
                -clamp01(safe_float(item.get("score"))),
                -safe_int(item.get("evidenceCount")),
                safe_int(item.get("_stable_index")),
            )
        )
        return out

    if mode == "confidence_asc":
        out.sort(
            key=lambda item: (
                clamp01(safe_float(item.get("confidence"))),
                clamp01(safe_float(item.get("score"))),
                safe_int(item.get("_stable_index")),
            )
        )
        return out

    if mode == "method":
        out.sort(
            key=lambda item: (
                method_priority(item.get("method")),
                *default_person_row_sort_key(item),
            )
        )
        return out

    if mode == "stance":
        out.sort(
            key=lambda item: (
                safe_text(item.get("stance")).casefold(),
                *default_person_row_sort_key(item),
            )
        )
        return out

    if mode == "as_of":
        out.sort(
            key=lambda item: (
                -(parse_date(item.get("asOf")) or date.min).toordinal(),
                safe_int(item.get("_stable_index")),
            )
        )
        return out

    if mode == "topic":
        out.sort(
            key=lambda item: (
                safe_text(item.get("topicLabel")).casefold(),
                safe_text(item.get("asOf")),
                safe_int(item.get("_stable_index")),
            )
        )
        return out

    if mode == "party":
        out.sort(
            key=lambda item: (
                safe_text(item.get("partyLabel")).casefold(),
                *default_person_row_sort_key(item),
            )
        )
        return out

    out.sort(key=default_person_row_sort_key)
    return out


def build_person_sort_preview_payloads(
    persons_out: list[dict[str, Any]],
    person_rows: dict[str, list[dict[str, Any]]],
    *,
    sort_modes: tuple[str, ...] = PERSON_SORT_PREVIEW_SORTS,
    max_rows: int = PERSON_SORT_PREVIEW_LIMIT,
) -> dict[str, list[dict[str, Any]]]:
    rows = build_person_flat_rows(persons_out, person_rows)
    limit = max(1, int(max_rows))
    previews: dict[str, list[dict[str, Any]]] = {}

    for sort_mode in sort_modes:
        previews[safe_text(sort_mode)] = [
            strip_internal_person_row(row)
            for row in sort_person_rows(rows, safe_text(sort_mode))[:limit]
        ]

    return previews


def build_topic_person_row_payloads(
    persons_out: list[dict[str, Any]],
    person_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in build_person_flat_rows(persons_out, person_rows):
        topic_id = safe_int(row.get("topicId"))
        if topic_id <= 0:
            continue
        grouped_rows[str(topic_id)].append(row)

    out: dict[str, list[dict[str, Any]]] = {}
    for topic_id, rows in grouped_rows.items():
        out[topic_id] = [
            compact_topic_person_row(row)
            for row in sort_person_rows(rows, "person")
        ]
    return out


def write_person_default_rows_payload(
    out_path: Path,
    rows: list[dict[str, Any]],
) -> None:
    (out_path.parent / PERSON_DEFAULT_ROWS_FILENAME).write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def write_person_sort_preview_payloads(
    out_path: Path,
    sort_preview_payloads: dict[str, list[dict[str, Any]]],
) -> None:
    preview_dir = out_path.parent / PERSON_SORT_PREVIEW_DIRNAME
    if preview_dir.exists():
        shutil.rmtree(preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)
    for sort_key, payload in sort_preview_payloads.items():
        (preview_dir / f"{safe_text(sort_key)}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


def write_topic_person_row_payloads(
    out_path: Path,
    topic_person_row_payloads: dict[str, list[dict[str, Any]]],
) -> None:
    topic_dir = out_path.parent / TOPIC_PERSON_ROWS_DIRNAME
    if topic_dir.exists():
        shutil.rmtree(topic_dir)
    topic_dir.mkdir(parents=True, exist_ok=True)
    for topic_id, payload in topic_person_row_payloads.items():
        (topic_dir / f"{safe_int(topic_id)}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


def compact_chunk_ref_index(
    raw_index: dict[str, set[str]],
    *,
    max_chunks: int = 0,
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    limit = max(0, int(max_chunks))
    for token, chunk_ids in raw_index.items():
        chunk_list = sorted(str(chunk_id) for chunk_id in chunk_ids if safe_text(chunk_id))
        if not chunk_list:
            continue
        if limit > 0 and len(chunk_list) > limit:
            continue
        out[safe_text(token)] = chunk_list
    return out


def compact_selective_chunk_ref_index(
    raw_index: dict[str, set[str]],
    *,
    total_chunks: int,
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    limit = max(0, int(total_chunks))
    for token, chunk_ids in raw_index.items():
        chunk_list = sorted(str(chunk_id) for chunk_id in chunk_ids if safe_text(chunk_id))
        if not chunk_list:
            continue
        if limit > 0 and len(chunk_list) >= limit:
            continue
        out[safe_text(token)] = chunk_list
    return out


def compact_selective_topic_ref_index(
    raw_index: dict[str, set[int]],
    *,
    max_topics: int = 0,
) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    limit = max(0, int(max_topics))
    for token, topic_ids in raw_index.items():
        topic_list = sorted({safe_int(topic_id) for topic_id in topic_ids if safe_int(topic_id) > 0})
        if not topic_list:
            continue
        if limit > 0 and len(topic_list) > limit:
            continue
        out[safe_text(token)] = topic_list
    return out


def build_person_search_index(
    person_chunk_payloads: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    snapshot_date: str,
    generated_at: str,
    max_topic_chunks: int = PERSON_SEARCH_INDEX_MAX_TOPIC_CHUNKS,
) -> dict[str, Any]:
    total_chunks = len([chunk_id for chunk_id in person_chunk_payloads if safe_text(chunk_id)])
    topic_ids: dict[str, set[str]] = defaultdict(set)
    topic_tokens: dict[str, set[str]] = defaultdict(set)
    party_tokens: dict[str, set[str]] = defaultdict(set)
    methods: dict[str, set[str]] = defaultdict(set)
    stances: dict[str, set[str]] = defaultdict(set)

    for chunk_id, payload in person_chunk_payloads.items():
        normalized_chunk_id = safe_text(chunk_id)
        if not normalized_chunk_id:
            continue
        for points in payload.values():
            for point in points:
                topic_id = safe_int(point.get("topic_id"))
                if topic_id > 0:
                    topic_ids[str(topic_id)].add(normalized_chunk_id)
                for token in extract_search_tokens(point.get("topic_label")):
                    topic_tokens[token].add(normalized_chunk_id)
                for token in extract_search_tokens(point.get("topic_key")):
                    topic_tokens[token].add(normalized_chunk_id)
                for token in extract_search_tokens(point.get("party_label"), min_len=2):
                    party_tokens[token].add(normalized_chunk_id)
                method = safe_text(point.get("computed_method")).lower()
                if method:
                    methods[method].add(normalized_chunk_id)
                stance = safe_text(point.get("stance")).lower()
                if stance:
                    stances[stance].add(normalized_chunk_id)

    selective_topic_ids = compact_selective_chunk_ref_index(
        topic_ids,
        total_chunks=total_chunks,
    )
    return {
        "meta": {
            "generated_at": safe_text(generated_at),
            "snapshot_date": safe_text(snapshot_date),
            "topic_token_max_chunks": max(0, int(max_topic_chunks)),
            "counts": {
                "topic_ids": len(selective_topic_ids),
                "topic_tokens": len(compact_chunk_ref_index(topic_tokens, max_chunks=max_topic_chunks)),
                "party_tokens": len(compact_chunk_ref_index(party_tokens)),
                "methods": len(compact_chunk_ref_index(methods)),
                "stances": len(compact_chunk_ref_index(stances)),
            },
        },
        "topic_ids": selective_topic_ids,
        "topic_tokens": compact_chunk_ref_index(topic_tokens, max_chunks=max_topic_chunks),
        "party_tokens": compact_chunk_ref_index(party_tokens),
        "methods": compact_chunk_ref_index(methods),
        "stances": compact_chunk_ref_index(stances),
    }


def build_topic_search_index(
    topics: list[dict[str, Any]],
    *,
    snapshot_date: str,
    generated_at: str,
    max_topics: int = TOPIC_SEARCH_INDEX_MAX_TOPICS,
) -> dict[str, Any]:
    topic_tokens: dict[str, set[int]] = defaultdict(set)
    for topic in topics:
        topic_id = safe_int(topic.get("topic_id") or topic.get("topicId"))
        if topic_id <= 0:
            continue
        for token in extract_search_tokens(topic.get("topic_label")):
            topic_tokens[token].add(topic_id)
        for token in extract_search_tokens(topic.get("topic_key")):
            topic_tokens[token].add(topic_id)

    selective_topic_tokens = compact_selective_topic_ref_index(
        topic_tokens,
        max_topics=max_topics,
    )
    return {
        "meta": {
            "generated_at": safe_text(generated_at),
            "snapshot_date": safe_text(snapshot_date),
            "topic_token_max_topics": max(0, int(max_topics)),
            "counts": {
                "topic_tokens": len(selective_topic_tokens),
            },
        },
        "topic_tokens": selective_topic_tokens,
    }


def write_person_search_index_payload(
    out_path: Path,
    search_index_payload: dict[str, Any],
) -> None:
    (out_path.parent / PERSON_SEARCH_INDEX_FILENAME).write_text(
        json.dumps(search_index_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def write_topic_search_index_payload(
    out_path: Path,
    search_index_payload: dict[str, Any],
) -> None:
    (out_path.parent / TOPIC_SEARCH_INDEX_FILENAME).write_text(
        json.dumps(search_index_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def compact_person_chunk_manifest(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for chunk in chunks:
        out.append(
            {
                key: value
                for key, value in chunk.items()
                if key not in {"topic_tokens", "party_tokens", "methods", "stances"}
            }
        )
    return out


def build_person_trajectory_chunks(
    persons_out: list[dict[str, Any]],
    person_rows: dict[str, list[dict[str, Any]]],
    *,
    chunk_size: int = PERSON_TRAJECTORY_CHUNK_SIZE,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, list[dict[str, Any]]]]]:
    size = max(1, int(chunk_size))
    chunks: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, list[dict[str, Any]]]] = {}
    chunk_filters: dict[str, dict[str, set[str]]] = {}

    for index, person in enumerate(persons_out):
        chunk_id = f"chunk-{(index // size) + 1:03d}"
        person["trajectory_chunk"] = chunk_id
        if not chunks or chunks[-1]["chunk_id"] != chunk_id:
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "person_count": 0,
                    "point_count_total": 0,
                    "person_ids": [],
                    "topic_tokens": [],
                    "party_tokens": [],
                    "methods": [],
                    "stances": [],
                }
            )
            payloads[chunk_id] = {}
            chunk_filters[chunk_id] = {
                "topic_tokens": set(),
                "party_tokens": set(),
                "methods": set(),
                "stances": set(),
            }
        person_id = safe_int(person.get("person_id"))
        point_count = safe_int(person.get("point_count") or person.get("points_count"))
        chunks[-1]["person_count"] += 1
        chunks[-1]["point_count_total"] += point_count
        chunks[-1]["person_ids"].append(person_id)
        person_points = person_rows.get(str(person_id), [])
        payloads[chunk_id][str(person_id)] = person_points
        chunk_filter = chunk_filters[chunk_id]
        for point in person_points:
            chunk_filter["topic_tokens"].update(extract_search_tokens(point.get("topic_label")))
            chunk_filter["topic_tokens"].update(extract_search_tokens(point.get("topic_key")))
            chunk_filter["party_tokens"].update(extract_search_tokens(point.get("party_label"), min_len=2))
            method = safe_text(point.get("computed_method")).lower()
            if method:
                chunk_filter["methods"].add(method)
            stance = safe_text(point.get("stance")).lower()
            if stance:
                chunk_filter["stances"].add(stance)

    for chunk in chunks:
        chunk_id = safe_text(chunk.get("chunk_id"))
        filters = chunk_filters.get(chunk_id, {})
        chunk["topic_tokens"] = sorted(filters.get("topic_tokens", set()))
        chunk["party_tokens"] = sorted(filters.get("party_tokens", set()))
        chunk["methods"] = sorted(filters.get("methods", set()))
        chunk["stances"] = sorted(filters.get("stances", set()))

    return chunks, payloads


def write_trajectory_payloads(
    out_path: Path,
    *,
    person_manifest: dict[str, Any],
    person_chunk_payloads: dict[str, dict[str, list[dict[str, Any]]]],
    person_search_index_payload: dict[str, Any],
    topic_search_index_payload: dict[str, Any],
    person_sort_preview_payloads: dict[str, list[dict[str, Any]]],
    topic_person_row_payloads: dict[str, list[dict[str, Any]]],
    party_payload: dict[str, list[dict[str, Any]]],
) -> None:
    (out_path.parent / PERSON_TRAJECTORIES_FILENAME).write_text(
        json.dumps(person_manifest, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    chunk_dir = out_path.parent / PERSON_TRAJECTORY_CHUNK_DIRNAME
    if chunk_dir.exists():
        shutil.rmtree(chunk_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for chunk_id, payload in person_chunk_payloads.items():
        (chunk_dir / f"{chunk_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    write_person_search_index_payload(out_path, person_search_index_payload)
    write_topic_search_index_payload(out_path, topic_search_index_payload)
    write_person_sort_preview_payloads(out_path, person_sort_preview_payloads)
    write_topic_person_row_payloads(out_path, topic_person_row_payloads)
    (out_path.parent / PARTY_TRAJECTORIES_FILENAME).write_text(
        json.dumps(party_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


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
                "point_count": safe_int(p["point_count"]),
                "points_count": safe_int(p["point_count"]),
                "latest_as_of": last_point,
                "evidence_count_total": safe_int(p["evidence_count_total"]),
            }
        )
    persons_out.sort(
        key=lambda item: (
            safe_text(item.get("full_name")).casefold(),
            safe_text(item.get("canonical_key")).casefold(),
            safe_int(item.get("person_id")),
        )
    )
    person_default_rows = build_person_default_rows(
        persons_out,
        person_rows,
        max_rows=PERSON_DEFAULT_ROWS_LIMIT,
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

    payload = {
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
            "person_detail_dir": PERSON_DETAIL_DIRNAME,
            "person_default_rows_path": PERSON_DEFAULT_ROWS_FILENAME,
            "person_default_rows_limit": PERSON_DEFAULT_ROWS_LIMIT,
            "person_trajectories_path": PERSON_TRAJECTORIES_FILENAME,
            "person_search_index_path": PERSON_SEARCH_INDEX_FILENAME,
            "person_trajectory_chunk_dir": PERSON_TRAJECTORY_CHUNK_DIRNAME,
            "person_trajectory_chunk_size": PERSON_TRAJECTORY_CHUNK_SIZE,
            "party_trajectories_path": PARTY_TRAJECTORIES_FILENAME,
            "review_pending": sum(item["review_summary"]["pending"] for points in person_rows.values() for item in points),
        },
        "topics": topics,
        "persons": persons_out,
        "parties": parties_out,
        "person_trajectories": {},
        "party_trajectories": {},
        "_person_trajectory_payload": person_rows,
        "_party_trajectory_payload": party_rows,
        "_person_default_rows_payload": person_default_rows,
        "_person_detail_payloads": build_person_detail_payloads(
            person_rows,
            snapshot_date=snapshot_date,
        ),
    }
    person_chunks, person_chunk_payloads = build_person_trajectory_chunks(
        persons_out,
        person_rows,
    )
    person_sort_preview_payloads = build_person_sort_preview_payloads(
        persons_out,
        person_rows,
    )
    topic_person_row_payloads = build_topic_person_row_payloads(
        persons_out,
        person_rows,
    )
    person_search_index_payload = build_person_search_index(
        person_chunk_payloads,
        snapshot_date=snapshot_date,
        generated_at=payload["meta"]["generated_at"],
    )
    topic_search_index_payload = build_topic_search_index(
        topics,
        snapshot_date=snapshot_date,
        generated_at=payload["meta"]["generated_at"],
    )
    payload = compact_payload_for_static_publish(payload)
    payload["meta"]["person_trajectory_chunks_total"] = len(person_chunks)
    payload["_person_trajectory_manifest"] = {
        "meta": {
            "generated_at": payload["meta"]["generated_at"],
            "snapshot_date": snapshot_date,
            "chunk_dir": PERSON_TRAJECTORY_CHUNK_DIRNAME,
            "chunk_size": PERSON_TRAJECTORY_CHUNK_SIZE,
            "chunk_count": len(person_chunks),
            "person_count": len(persons_out),
        },
        "chunks": compact_person_chunk_manifest(person_chunks),
    }
    payload["_person_trajectory_chunk_payloads"] = person_chunk_payloads
    payload["_person_search_index_payload"] = person_search_index_payload
    payload["_topic_search_index_payload"] = topic_search_index_payload
    payload["_person_sort_preview_payloads"] = person_sort_preview_payloads
    payload["_topic_person_row_payloads"] = topic_person_row_payloads
    payload["meta"]["person_sort_preview_dir"] = PERSON_SORT_PREVIEW_DIRNAME
    payload["meta"]["person_sort_preview_limit"] = PERSON_SORT_PREVIEW_LIMIT
    payload["meta"]["topic_search_index_path"] = TOPIC_SEARCH_INDEX_FILENAME
    payload["meta"]["topic_person_rows_dir"] = TOPIC_PERSON_ROWS_DIRNAME
    payload["meta"]["topic_person_rows_total"] = len(topic_person_row_payloads)
    payload["meta"]["person_search_index_counts"] = dict(
        person_search_index_payload.get("meta", {}).get("counts", {})
    )
    payload["meta"]["topic_search_index_counts"] = dict(
        topic_search_index_payload.get("meta", {}).get("counts", {})
    )
    payload["meta"]["person_sort_preview_paths"] = {
        sort_key: f"{PERSON_SORT_PREVIEW_DIRNAME}/{sort_key}.json"
        for sort_key in PERSON_SORT_PREVIEW_SORTS
    }
    payload.pop("_person_trajectory_payload", None)
    return payload


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

    person_detail_payloads = payload.pop("_person_detail_payloads", {})
    person_default_rows_payload = payload.pop("_person_default_rows_payload", [])
    person_trajectory_manifest = payload.pop("_person_trajectory_manifest", {"meta": {}, "chunks": []})
    person_trajectory_chunk_payloads = payload.pop("_person_trajectory_chunk_payloads", {})
    person_search_index_payload = payload.pop("_person_search_index_payload", {"meta": {}, "topic_ids": {}, "topic_tokens": {}, "party_tokens": {}, "methods": {}, "stances": {}})
    topic_search_index_payload = payload.pop("_topic_search_index_payload", {"meta": {}, "topic_tokens": {}})
    person_sort_preview_payloads = payload.pop("_person_sort_preview_payloads", {})
    topic_person_row_payloads = payload.pop("_topic_person_row_payloads", {})
    party_trajectory_payload = payload.pop("_party_trajectory_payload", {})
    write_person_default_rows_payload(out_path, person_default_rows_payload)
    write_person_detail_payloads(out_path, person_detail_payloads)
    write_trajectory_payloads(
        out_path,
        person_manifest=person_trajectory_manifest,
        person_chunk_payloads=person_trajectory_chunk_payloads,
        person_search_index_payload=person_search_index_payload,
        topic_search_index_payload=topic_search_index_payload,
        person_sort_preview_payloads=person_sort_preview_payloads,
        topic_person_row_payloads=topic_person_row_payloads,
        party_payload=party_trajectory_payload,
    )
    encoded = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, separators=None if args.pretty else (",", ":"))
    out_path.write_text(encoded, encoding="utf-8")
    print(f"OK political positions snapshot -> {out_path} ({len(encoded)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
