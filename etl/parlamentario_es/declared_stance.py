from __future__ import annotations

import re
import sqlite3
import unicodedata
from typing import Any

from etl.politicos_es.util import normalize_ws, now_utc_iso


def _normalize_for_match(text: str) -> str:
    t = normalize_ws(text).lower()
    # Remove accents/diacritics to keep regexes ASCII-only.
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t


_SUPPORT_EXPLICIT_PATTERNS = (
    re.compile(r"\bvotaremos\s+(a\s+)?favor\b"),
    re.compile(r"\bvotare(mos)?\s+(que\s+)?si\b"),
    re.compile(r"\bvotara(mos|n)?\s+(a\s+)?favor\b"),
    re.compile(r"\bnuestro\s+voto\s+sera\s+(favorable|positivo|afirmativo)\b"),
    re.compile(r"\bmi\s+voto\s+sera\s+(favorable|positivo|afirmativo)\b"),
    re.compile(r"\bvoto\s+(favorable|positivo|afirmativo)\b"),
)

_OPPOSE_EXPLICIT_PATTERNS = (
    re.compile(r"\bvotaremos\s+en\s+contra\b"),
    re.compile(r"\bvotare(mos)?\s+(que\s+)?no\b"),
    re.compile(r"\bvotara(mos|n)?\s+en\s+contra\b"),
    re.compile(r"\bnuestro\s+voto\s+sera\s+(negativo|desfavorable)\b"),
    re.compile(r"\bmi\s+voto\s+sera\s+(negativo|desfavorable)\b"),
    re.compile(r"\bvoto\s+(negativo|desfavorable)\b"),
)

_ABSTAIN_EXPLICIT_PATTERNS = (
    re.compile(r"\bnos\s+absten(dremos|emos)\b"),
    re.compile(r"\bme\s+abstendre\b"),
    re.compile(r"\bmi\s+voto\s+sera\s+abstencion\b"),
    re.compile(r"\babstencion\b"),
    re.compile(r"\babstener(nos|se)\b"),
)

_SUPPORT_DECLARED_PATTERNS = (
    re.compile(r"\bapoyamos\b"),
    re.compile(r"\brespaldamos\b"),
    re.compile(r"\bdefendemos\b"),
)

_OPPOSE_DECLARED_PATTERNS = (
    re.compile(r"\brechazamos\b"),
    re.compile(r"\bnos\s+oponemos\b"),
    re.compile(r"\bnos\s+opondremos\b"),
)


def _is_negated(text: str, match_start: int) -> bool:
    # Keep this conservative: only immediate negation directly before the phrase.
    prefix = text[max(0, match_start - 28) : match_start]
    return bool(re.search(r"\b(no|nunca|jamas)\s*$", prefix))


def _count_hits(patterns: tuple[re.Pattern[str], ...], text: str) -> int:
    hits = 0
    for pattern in patterns:
        for match in pattern.finditer(text):
            if _is_negated(text, match.start()):
                continue
            hits += 1
    return hits


def _infer_declared_stance_detail(text: str) -> tuple[str, int, float, str] | None:
    t = _normalize_for_match(text)
    if not t:
        return None

    abst_hits = _count_hits(_ABSTAIN_EXPLICIT_PATTERNS, t)
    support_explicit_hits = _count_hits(_SUPPORT_EXPLICIT_PATTERNS, t)
    oppose_explicit_hits = _count_hits(_OPPOSE_EXPLICIT_PATTERNS, t)
    support_declared_hits = _count_hits(_SUPPORT_DECLARED_PATTERNS, t)
    oppose_declared_hits = _count_hits(_OPPOSE_DECLARED_PATTERNS, t)

    if abst_hits > 0 and (support_explicit_hits + oppose_explicit_hits + support_declared_hits + oppose_declared_hits) > 0:
        return ("mixed", 0, 0.5, "conflicting_signal")
    if support_explicit_hits > 0 and oppose_explicit_hits > 0:
        return ("mixed", 0, 0.5, "conflicting_signal")
    if support_explicit_hits > 0:
        return ("support", 1, 0.72, "explicit_vote_intent")
    if oppose_explicit_hits > 0:
        return ("oppose", -1, 0.72, "explicit_vote_intent")
    if abst_hits > 0:
        return ("mixed", 0, 0.66, "abstention_intent")
    if support_declared_hits > 0 and oppose_declared_hits > 0:
        return ("mixed", 0, 0.5, "conflicting_signal")
    if support_declared_hits > 0:
        return ("support", 1, 0.58, "declared_support")
    if oppose_declared_hits > 0:
        return ("oppose", -1, 0.58, "declared_oppose")
    return None


def infer_declared_stance(text: str) -> tuple[str, int, float] | None:
    """Best-effort stance inference for declared evidence.

    Public compatibility helper: returns only (stance, polarity, confidence).
    Detailed reason is available in the internal `_infer_declared_stance_detail`.
    """

    inferred = _infer_declared_stance_detail(text)
    if inferred is None:
        return None
    stance, polarity, confidence, _reason = inferred
    return stance, polarity, confidence


def _resolve_review_rows(conn: sqlite3.Connection, *, evidence_ids: list[int], now_iso: str) -> int:
    if not evidence_ids:
        return 0
    before = int(conn.total_changes)
    conn.executemany(
        """
        UPDATE topic_evidence_reviews
        SET status = CASE WHEN status = 'ignored' THEN status ELSE 'resolved' END,
            updated_at = ?
        WHERE evidence_id = ?
        """,
        [(now_iso, int(ev_id)) for ev_id in evidence_ids],
    )
    return int(conn.total_changes) - before


def backfill_declared_stance_from_topic_evidence(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    limit: int = 0,
    min_auto_confidence: float = 0.62,
    enable_review_queue: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Populate topic_evidence stance/polarity for declared evidence using text excerpts.

    v2 behavior:
    - conservative auto-updates when confidence >= min_auto_confidence
    - optional review queue rows for missing/ambiguous/low-confidence cases
    - never touches rows with non-auto/manual stance_method values
    """

    now_iso = now_utc_iso()
    params: list[Any] = [source_id]

    limit_sql = ""
    if int(limit) > 0:
        limit_sql = " LIMIT ?"
        params.append(int(limit))

    rows = conn.execute(
        f"""
        SELECT
          e.evidence_id,
          e.source_record_pk,
          COALESCE(d.text_excerpt, e.excerpt, '') AS text,
          e.stance AS current_stance,
          e.polarity AS current_polarity,
          e.confidence AS current_confidence,
          e.stance_method AS current_stance_method
        FROM topic_evidence e
        LEFT JOIN text_documents d
          ON d.source_id = e.source_id
         AND d.source_record_pk = e.source_record_pk
        WHERE e.source_id = ?
          AND e.evidence_type LIKE 'declared:%'
          AND (
            e.stance_method IS NULL
            OR e.stance_method IN ('intervention_metadata', 'declared:regex_v1', 'declared:regex_v2')
            OR e.stance IS NULL
            OR e.stance IN ('unclear', 'no_signal')
          )
        ORDER BY e.evidence_id ASC
        {limit_sql}
        """,
        params,
    ).fetchall()

    seen = 0
    updated = 0
    review_rows_resolved = 0
    review_rows_pending = 0
    support = 0
    oppose = 0
    mixed = 0
    review_missing_text = 0
    review_no_signal = 0
    review_low_confidence = 0
    review_conflicting_signal = 0

    updates: list[tuple[Any, ...]] = []
    review_upserts: list[tuple[Any, ...]] = []
    resolve_review_ids: list[int] = []
    for r in rows:
        seen += 1
        ev_id = int(r["evidence_id"])
        source_record_pk = int(r["source_record_pk"]) if r["source_record_pk"] is not None else None
        text = str(r["text"] or "")
        if not normalize_ws(text):
            if enable_review_queue:
                review_rows_pending += 1
                review_missing_text += 1
                review_upserts.append(
                    (
                        ev_id,
                        source_id,
                        source_record_pk,
                        "missing_text",
                        None,
                        None,
                        None,
                        "declared:regex_v2",
                        "declared evidence without text_excerpt",
                        now_iso,
                        now_iso,
                    )
                )
            continue

        inferred = _infer_declared_stance_detail(text)
        if inferred is None:
            if enable_review_queue:
                review_rows_pending += 1
                review_no_signal += 1
                review_upserts.append(
                    (
                        ev_id,
                        source_id,
                        source_record_pk,
                        "no_signal",
                        None,
                        None,
                        None,
                        "declared:regex_v2",
                        "no explicit declared stance pattern found",
                        now_iso,
                        now_iso,
                    )
                )
            continue

        stance, polarity, confidence, reason = inferred
        if float(confidence) < float(min_auto_confidence):
            if enable_review_queue:
                review_rows_pending += 1
                if reason == "conflicting_signal":
                    review_conflicting_signal += 1
                    review_reason = "conflicting_signal"
                else:
                    review_low_confidence += 1
                    review_reason = "low_confidence"
                review_upserts.append(
                    (
                        ev_id,
                        source_id,
                        source_record_pk,
                        review_reason,
                        stance,
                        int(polarity),
                        float(confidence),
                        "declared:regex_v2",
                        reason,
                        now_iso,
                        now_iso,
                    )
                )
            continue

        if stance == "support":
            support += 1
        elif stance == "oppose":
            oppose += 1
        else:
            mixed += 1
        current_stance = normalize_ws(str(r["current_stance"] or ""))
        current_polarity = int(r["current_polarity"]) if r["current_polarity"] is not None else None
        current_confidence = float(r["current_confidence"]) if r["current_confidence"] is not None else None
        current_method = normalize_ws(str(r["current_stance_method"] or ""))
        unchanged = (
            current_stance == stance
            and current_polarity == int(polarity)
            and current_method == "declared:regex_v2"
            and current_confidence is not None
            and abs(current_confidence - float(confidence)) <= 1e-9
        )
        if unchanged:
            resolve_review_ids.append(ev_id)
            continue
        updates.append((stance, int(polarity), float(confidence), "declared:regex_v2", now_iso, ev_id))
        resolve_review_ids.append(ev_id)

    if dry_run:
        return {
            "source_id": source_id,
            "dry_run": True,
            "seen": seen,
            "would_update": len(updates),
            "review_queue_enabled": bool(enable_review_queue),
            "would_queue_pending": review_rows_pending,
            "review_missing_text": review_missing_text,
            "review_no_signal": review_no_signal,
            "review_low_confidence": review_low_confidence,
            "review_conflicting_signal": review_conflicting_signal,
            "support": support,
            "oppose": oppose,
            "mixed": mixed,
        }

    with conn:
        if updates:
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
                updates,
            )
            updated = len(updates)

        if enable_review_queue:
            if review_upserts:
                conn.executemany(
                    """
                    INSERT INTO topic_evidence_reviews (
                      evidence_id, source_id, source_record_pk, review_reason, status,
                      suggested_stance, suggested_polarity, suggested_confidence, extractor_version, note,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(evidence_id) DO UPDATE SET
                      source_id=excluded.source_id,
                      source_record_pk=excluded.source_record_pk,
                      review_reason=excluded.review_reason,
                      status=CASE WHEN topic_evidence_reviews.status = 'ignored' THEN 'ignored' ELSE 'pending' END,
                      suggested_stance=excluded.suggested_stance,
                      suggested_polarity=excluded.suggested_polarity,
                      suggested_confidence=excluded.suggested_confidence,
                      extractor_version=excluded.extractor_version,
                      note=excluded.note,
                      updated_at=excluded.updated_at
                    """,
                    review_upserts,
                )
            review_rows_resolved = _resolve_review_rows(conn, evidence_ids=resolve_review_ids, now_iso=now_iso)

    review_pending_db = 0
    review_total_db = 0
    review_by_reason: dict[str, int] = {}
    if enable_review_queue:
        try:
            review_total_db = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id = ?",
                    (source_id,),
                ).fetchone()["c"]
                or 0
            )
            review_pending_db = int(
                conn.execute(
                    "SELECT COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id = ? AND status = 'pending'",
                    (source_id,),
                ).fetchone()["c"]
                or 0
            )
            for rr in conn.execute(
                """
                SELECT review_reason, COUNT(*) AS c
                FROM topic_evidence_reviews
                WHERE source_id = ? AND status = 'pending'
                GROUP BY review_reason
                ORDER BY c DESC, review_reason ASC
                """,
                (source_id,),
            ).fetchall():
                key = normalize_ws(str(rr["review_reason"] or ""))
                if not key:
                    continue
                review_by_reason[key] = int(rr["c"] or 0)
        except sqlite3.Error:
            review_total_db = 0
            review_pending_db = 0
            review_by_reason = {}

    return {
        "source_id": source_id,
        "dry_run": False,
        "seen": seen,
        "updated": updated,
        "review_queue_enabled": bool(enable_review_queue),
        "review_rows_resolved": review_rows_resolved,
        "review_total": review_total_db,
        "review_pending": review_pending_db,
        "review_pending_by_reason": review_by_reason,
        "support": support,
        "oppose": oppose,
        "mixed": mixed,
    }
