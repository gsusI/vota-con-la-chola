from __future__ import annotations

import sqlite3
from typing import Any

from etl.politicos_es.util import normalize_ws, now_utc_iso


VALID_REVIEW_STATUSES = ("pending", "resolved", "ignored")
VALID_REVIEW_REASONS = ("missing_text", "no_signal", "low_confidence", "conflicting_signal")
VALID_STANCES = ("support", "oppose", "mixed", "unclear", "no_signal")


def _normalize_status(value: str, *, allow_all: bool) -> str:
    status = normalize_ws(value).lower()
    if allow_all and status == "all":
        return status
    if status not in VALID_REVIEW_STATUSES:
        allowed = list(VALID_REVIEW_STATUSES)
        if allow_all:
            allowed = ["all", *allowed]
        raise ValueError(f"status invalido: {value} (esperado: {', '.join(allowed)})")
    return status


def _normalize_stance(value: str | None) -> str | None:
    if value is None:
        return None
    stance = normalize_ws(value).lower()
    if not stance:
        return None
    if stance not in VALID_STANCES:
        raise ValueError(f"stance invalido: {value} (esperado: {', '.join(VALID_STANCES)})")
    return stance


def _stance_to_polarity(stance: str) -> int:
    if stance == "support":
        return 1
    if stance == "oppose":
        return -1
    return 0


def _coerce_int_tuple(values: tuple[int, ...] | list[int] | None) -> tuple[int, ...]:
    if not values:
        return tuple()
    out: list[int] = []
    seen: set[int] = set()
    for raw in values:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return tuple(out)


def resolve_as_of_date(conn: sqlite3.Connection, as_of_date: str | None) -> str | None:
    candidate = normalize_ws(as_of_date or "")
    if candidate:
        return candidate
    row = conn.execute("SELECT MAX(as_of_date) AS d FROM topic_positions").fetchone()
    if not row:
        return None
    return normalize_ws(str(row["d"] or "")) or None


def build_topic_evidence_review_report(
    conn: sqlite3.Connection,
    *,
    source_id: str | None = None,
    status: str = "pending",
    review_reason: str | None = None,
    topic_set_id: int | None = None,
    topic_id: int | None = None,
    person_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    status_norm = _normalize_status(status, allow_all=True)
    source_norm = normalize_ws(source_id or "") or None
    reason_norm = normalize_ws(review_reason or "").lower() or None
    if reason_norm and reason_norm not in VALID_REVIEW_REASONS:
        raise ValueError(
            f"review_reason invalido: {review_reason} (esperado: {', '.join(VALID_REVIEW_REASONS)})"
        )

    where: list[str] = ["1=1"]
    params: list[Any] = []
    if source_norm:
        where.append("r.source_id = ?")
        params.append(source_norm)
    if status_norm != "all":
        where.append("r.status = ?")
        params.append(status_norm)
    if reason_norm:
        where.append("r.review_reason = ?")
        params.append(reason_norm)
    if topic_set_id is not None:
        where.append("e.topic_set_id = ?")
        params.append(int(topic_set_id))
    if topic_id is not None:
        where.append("e.topic_id = ?")
        params.append(int(topic_id))
    if person_id is not None:
        where.append("e.person_id = ?")
        params.append(int(person_id))
    where_sql = " AND ".join(where)
    limit_n = max(1, min(500, int(limit)))
    offset_n = max(0, int(offset))

    count_row = conn.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM topic_evidence_reviews r
        JOIN topic_evidence e ON e.evidence_id = r.evidence_id
        WHERE {where_sql}
        """,
        params,
    ).fetchone()
    total = int((count_row["c"] if count_row else 0) or 0)

    rows = conn.execute(
        f"""
        SELECT
          r.review_id,
          r.evidence_id,
          r.source_id,
          r.source_record_pk,
          r.review_reason,
          r.status,
          r.suggested_stance,
          r.suggested_polarity,
          r.suggested_confidence,
          r.extractor_version,
          r.note,
          r.created_at AS review_created_at,
          r.updated_at AS review_updated_at,
          e.topic_set_id,
          e.topic_id,
          t.label AS topic_label,
          e.person_id,
          p.full_name AS person_name,
          e.evidence_type,
          e.evidence_date,
          e.stance AS evidence_stance,
          e.polarity AS evidence_polarity,
          e.confidence AS evidence_confidence,
          e.stance_method AS evidence_stance_method,
          SUBSTR(COALESCE(e.excerpt, ''), 1, 260) AS evidence_excerpt
        FROM topic_evidence_reviews r
        JOIN topic_evidence e ON e.evidence_id = r.evidence_id
        LEFT JOIN topics t ON t.topic_id = e.topic_id
        LEFT JOIN persons p ON p.person_id = e.person_id
        WHERE {where_sql}
        ORDER BY
          CASE r.status WHEN 'pending' THEN 0 WHEN 'resolved' THEN 1 ELSE 2 END ASC,
          r.updated_at DESC,
          r.review_id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit_n, offset_n),
    ).fetchall()

    summary_status_rows = conn.execute(
        """
        SELECT status, COUNT(*) AS c
        FROM topic_evidence_reviews
        WHERE (? = '' OR source_id = ?)
        GROUP BY status
        ORDER BY status
        """,
        (source_norm or "", source_norm or ""),
    ).fetchall()
    summary_reason_rows = conn.execute(
        """
        SELECT review_reason, COUNT(*) AS c
        FROM topic_evidence_reviews
        WHERE status = 'pending'
          AND (? = '' OR source_id = ?)
        GROUP BY review_reason
        ORDER BY c DESC, review_reason ASC
        """,
        (source_norm or "", source_norm or ""),
    ).fetchall()

    by_status: dict[str, int] = {}
    by_reason_pending: dict[str, int] = {}
    for r in summary_status_rows:
        key = normalize_ws(str(r["status"] or "")).lower()
        if key:
            by_status[key] = int(r["c"] or 0)
    for r in summary_reason_rows:
        key = normalize_ws(str(r["review_reason"] or "")).lower()
        if key:
            by_reason_pending[key] = int(r["c"] or 0)

    items: list[dict[str, Any]] = []
    for r in rows:
        items.append(
            {
                "review_id": int(r["review_id"]),
                "evidence_id": int(r["evidence_id"]),
                "source_id": str(r["source_id"] or ""),
                "source_record_pk": int(r["source_record_pk"]) if r["source_record_pk"] is not None else None,
                "review_reason": str(r["review_reason"] or ""),
                "status": str(r["status"] or ""),
                "suggested_stance": str(r["suggested_stance"] or ""),
                "suggested_polarity": int(r["suggested_polarity"]) if r["suggested_polarity"] is not None else None,
                "suggested_confidence": float(r["suggested_confidence"]) if r["suggested_confidence"] is not None else None,
                "extractor_version": str(r["extractor_version"] or ""),
                "note": str(r["note"] or ""),
                "review_created_at": str(r["review_created_at"] or ""),
                "review_updated_at": str(r["review_updated_at"] or ""),
                "topic_set_id": int(r["topic_set_id"]) if r["topic_set_id"] is not None else None,
                "topic_id": int(r["topic_id"]) if r["topic_id"] is not None else None,
                "topic_label": str(r["topic_label"] or ""),
                "person_id": int(r["person_id"]) if r["person_id"] is not None else None,
                "person_name": str(r["person_name"] or ""),
                "evidence_type": str(r["evidence_type"] or ""),
                "evidence_date": str(r["evidence_date"] or ""),
                "evidence_stance": str(r["evidence_stance"] or ""),
                "evidence_polarity": int(r["evidence_polarity"]) if r["evidence_polarity"] is not None else None,
                "evidence_confidence": float(r["evidence_confidence"]) if r["evidence_confidence"] is not None else None,
                "evidence_stance_method": str(r["evidence_stance_method"] or ""),
                "evidence_excerpt": str(r["evidence_excerpt"] or ""),
            }
        )

    return {
        "source_id": source_norm or "",
        "status": status_norm,
        "review_reason": reason_norm or "",
        "filters": {
            "topic_set_id": int(topic_set_id) if topic_set_id is not None else None,
            "topic_id": int(topic_id) if topic_id is not None else None,
            "person_id": int(person_id) if person_id is not None else None,
        },
        "summary": {
            "total": sum(int(v or 0) for v in by_status.values()),
            "pending": int(by_status.get("pending", 0)),
            "resolved": int(by_status.get("resolved", 0)),
            "ignored": int(by_status.get("ignored", 0)),
            "pending_by_reason": by_reason_pending,
        },
        "page": {
            "limit": limit_n,
            "offset": offset_n,
            "total": total,
            "returned": len(items),
        },
        "items": items,
    }


def apply_topic_evidence_review_decision(
    conn: sqlite3.Connection,
    *,
    evidence_ids: tuple[int, ...] | list[int],
    status: str,
    final_stance: str | None = None,
    final_confidence: float | None = None,
    note: str | None = None,
    source_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    selected_ids = _coerce_int_tuple(evidence_ids)
    status_norm = _normalize_status(status, allow_all=False)
    final_stance_norm = _normalize_stance(final_stance)
    source_norm = normalize_ws(source_id or "") or None
    note_norm = normalize_ws(note or "")
    if final_confidence is not None:
        try:
            final_conf = float(final_confidence)
        except (TypeError, ValueError):
            raise ValueError("final_confidence invalido") from None
        if final_conf < 0.0 or final_conf > 1.0:
            raise ValueError("final_confidence debe estar entre 0 y 1")
    else:
        final_conf = None

    if status_norm != "resolved" and final_stance_norm:
        raise ValueError("final_stance solo aplica con status=resolved")

    if not selected_ids:
        return {
            "dry_run": bool(dry_run),
            "status": status_norm,
            "selected": 0,
            "matched": 0,
            "review_rows_updated": 0,
            "evidence_rows_updated": 0,
            "not_found_evidence_ids": [],
            "source_id": source_norm or "",
        }

    qmarks = ",".join("?" for _ in selected_ids)
    where_sql = f"r.evidence_id IN ({qmarks})"
    params: list[Any] = list(selected_ids)
    if source_norm:
        where_sql = f"{where_sql} AND r.source_id = ?"
        params.append(source_norm)

    rows = conn.execute(
        f"""
        SELECT
          r.review_id,
          r.evidence_id,
          r.source_id,
          r.status AS review_status,
          r.suggested_stance,
          r.suggested_polarity,
          r.suggested_confidence,
          r.note AS review_note,
          e.stance AS evidence_stance,
          e.polarity AS evidence_polarity,
          e.confidence AS evidence_confidence
        FROM topic_evidence_reviews r
        JOIN topic_evidence e ON e.evidence_id = r.evidence_id
        WHERE {where_sql}
        ORDER BY r.review_id ASC
        """,
        params,
    ).fetchall()

    found_ids = {int(r["evidence_id"]) for r in rows}
    not_found = [int(x) for x in selected_ids if int(x) not in found_ids]
    now_iso = now_utc_iso()

    review_updates: list[tuple[Any, ...]] = []
    evidence_updates: list[tuple[Any, ...]] = []

    for r in rows:
        evidence_id = int(r["evidence_id"])
        suggested_stance = _normalize_stance(r["suggested_stance"])
        suggested_confidence = float(r["suggested_confidence"]) if r["suggested_confidence"] is not None else None
        evidence_confidence = float(r["evidence_confidence"]) if r["evidence_confidence"] is not None else None

        chosen_stance = final_stance_norm
        if status_norm == "resolved" and not chosen_stance:
            chosen_stance = suggested_stance or _normalize_stance(r["evidence_stance"])

        chosen_polarity: int | None = None
        if chosen_stance:
            chosen_polarity = _stance_to_polarity(chosen_stance)

        chosen_confidence = final_conf
        if chosen_confidence is None and status_norm == "resolved":
            chosen_confidence = suggested_confidence if suggested_confidence is not None else evidence_confidence
            if chosen_confidence is None:
                chosen_confidence = 0.5

        if status_norm == "resolved" and chosen_stance is not None:
            evidence_updates.append(
                (
                    chosen_stance,
                    chosen_polarity,
                    chosen_confidence,
                    "declared:manual_review_v1",
                    now_iso,
                    evidence_id,
                )
            )

        review_updates.append(
            (
                status_norm,
                note_norm if note_norm else None,
                chosen_stance if status_norm == "resolved" else None,
                chosen_polarity if status_norm == "resolved" else None,
                chosen_confidence if status_norm == "resolved" else None,
                now_iso,
                evidence_id,
            )
        )

    if not dry_run and (review_updates or evidence_updates):
        with conn:
            if review_updates:
                conn.executemany(
                    """
                    UPDATE topic_evidence_reviews
                    SET status = ?,
                        note = COALESCE(?, note),
                        suggested_stance = COALESCE(?, suggested_stance),
                        suggested_polarity = COALESCE(?, suggested_polarity),
                        suggested_confidence = COALESCE(?, suggested_confidence),
                        updated_at = ?
                    WHERE evidence_id = ?
                    """,
                    review_updates,
                )
            if evidence_updates:
                conn.executemany(
                    """
                    UPDATE topic_evidence
                    SET stance = ?,
                        polarity = ?,
                        confidence = ?,
                        stance_method = ?,
                        updated_at = ?
                    WHERE evidence_id = ?
                    """,
                    evidence_updates,
                )

    return {
        "dry_run": bool(dry_run),
        "status": status_norm,
        "selected": len(selected_ids),
        "matched": len(rows),
        "review_rows_updated": len(review_updates),
        "evidence_rows_updated": len(evidence_updates),
        "not_found_evidence_ids": not_found,
        "source_id": source_norm or "",
        "final_stance": final_stance_norm or "",
        "final_confidence": final_conf,
    }

