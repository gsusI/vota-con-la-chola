"""Safety-gated workflow for anomaly review, correction, and publication."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

SIGNAL_STATES = {
    "observed_fact",
    "review_signal",
    "corroborated_risk",
    "official_finding",
    "rejected",
    "superseded",
}
PUBLICATION_STATUSES = {"internal", "approved", "published", "withdrawn"}
RESPONSE_STATUSES = {
    "pending",
    "received",
    "declined",
    "no_response_after_deadline",
    "not_required",
}
HUMAN_ACTOR_KINDS = {"human_reviewer", "maintainer"}
ALLOWED_TRANSITIONS = {
    "observed_fact": {"review_signal", "rejected", "superseded"},
    "review_signal": {"corroborated_risk", "rejected", "superseded"},
    "corroborated_risk": {"official_finding", "rejected", "superseded"},
    "official_finding": {"superseded"},
    "rejected": {"superseded"},
    "superseded": set(),
}


INTEGRITY_SIGNAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS integrity_signals (
  signal_id TEXT PRIMARY KEY,
  detector_id TEXT NOT NULL,
  detector_version TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  jurisdiction TEXT,
  period_start TEXT,
  period_end TEXT,
  state TEXT NOT NULL CHECK (state IN (
    'observed_fact','review_signal','corroborated_risk','official_finding',
    'rejected','superseded'
  )),
  review_priority INTEGER NOT NULL DEFAULT 0,
  summary TEXT NOT NULL,
  metrics_json TEXT NOT NULL DEFAULT '{}',
  limitations_json TEXT NOT NULL DEFAULT '[]',
  publication_status TEXT NOT NULL DEFAULT 'internal' CHECK (publication_status IN (
    'internal','approved','published','withdrawn'
  )),
  right_of_reply_status TEXT NOT NULL DEFAULT 'pending' CHECK (right_of_reply_status IN (
    'pending','received','declined','no_response_after_deadline','not_required'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (
    detector_id, detector_version, signal_type, subject_type, subject_id,
    period_start, period_end
  )
);

CREATE TABLE IF NOT EXISTS integrity_signal_evidence (
  signal_evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  evidence_role TEXT NOT NULL CHECK (evidence_role IN (
    'observed','corroborating','counterevidence','official_finding','context'
  )),
  independent_source_key TEXT NOT NULL,
  source_id TEXT,
  source_record_pk INTEGER REFERENCES source_records(source_record_pk),
  source_url TEXT,
  content_sha256 TEXT,
  excerpt TEXT,
  observed_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (
    signal_id, evidence_role, independent_source_key, source_id,
    source_record_pk, source_url
  )
);

CREATE TABLE IF NOT EXISTS integrity_signal_reviews (
  signal_review_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  reviewer_id TEXT NOT NULL,
  reviewer_independence_class TEXT NOT NULL DEFAULT 'unknown' CHECK (
    reviewer_independence_class IN ('author','maintainer','independent','unknown')
  ),
  decision TEXT NOT NULL CHECK (decision IN (
    'needs_more_evidence','corroborate','reject','approve_publication','withdraw'
  )),
  rationale TEXT NOT NULL,
  reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS integrity_signal_transitions (
  signal_transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  from_state TEXT NOT NULL,
  to_state TEXT NOT NULL,
  actor_kind TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  rationale TEXT NOT NULL,
  transitioned_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS integrity_signal_responses (
  signal_response_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  response_status TEXT NOT NULL CHECK (response_status IN (
    'received','declined','no_response_after_deadline','not_required'
  )),
  response_source_url TEXT,
  response_content_sha256 TEXT,
  response_summary TEXT,
  recorded_by TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS integrity_signal_corrections (
  signal_correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES integrity_signals(signal_id) ON DELETE CASCADE,
  correction_type TEXT NOT NULL CHECK (correction_type IN (
    'counterevidence','factual_correction','identity_correction','withdrawal','supersession'
  )),
  rationale TEXT NOT NULL,
  evidence_url TEXT,
  corrected_by TEXT NOT NULL,
  corrected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_integrity_signals_state_priority
  ON integrity_signals(state, review_priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_integrity_signals_subject
  ON integrity_signals(subject_type, subject_id, period_start);
CREATE INDEX IF NOT EXISTS idx_integrity_signals_publication
  ON integrity_signals(publication_status, state, updated_at);
CREATE INDEX IF NOT EXISTS idx_integrity_signal_evidence_signal_role
  ON integrity_signal_evidence(signal_id, evidence_role, independent_source_key);
CREATE INDEX IF NOT EXISTS idx_integrity_signal_transitions_signal
  ON integrity_signal_transitions(signal_id, transitioned_at);
CREATE INDEX IF NOT EXISTS idx_integrity_signal_reviews_signal
  ON integrity_signal_reviews(signal_id, reviewed_at);
"""


def _now_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat(timespec="seconds")


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def ensure_integrity_signal_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(INTEGRITY_SIGNAL_SCHEMA)
    review_columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(integrity_signal_reviews)")
    }
    if "reviewer_independence_class" not in review_columns:
        conn.execute(
            """
            ALTER TABLE integrity_signal_reviews
            ADD COLUMN reviewer_independence_class TEXT NOT NULL DEFAULT 'unknown'
            CHECK (reviewer_independence_class IN (
              'author','maintainer','independent','unknown'
            ))
            """
        )
    conn.execute(
        """
        UPDATE integrity_signals
        SET publication_status = 'withdrawn'
        WHERE state = 'superseded'
          AND publication_status != 'withdrawn'
        """
    )
    conn.commit()


def add_signal_evidence(
    conn: sqlite3.Connection,
    *,
    signal_id: str,
    evidence: Iterable[Mapping[str, object]],
    now: datetime | None = None,
) -> int:
    ensure_integrity_signal_schema(conn)
    now_iso = _now_iso(now)
    inserted = 0
    for row in evidence:
        role = str(row.get("evidence_role") or "observed").strip()
        if role not in {
            "observed",
            "corroborating",
            "counterevidence",
            "official_finding",
            "context",
        }:
            raise ValueError(f"invalid evidence_role: {role}")
        source_key = str(row.get("independent_source_key") or "").strip()
        if not source_key:
            raise ValueError("independent_source_key is required")
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO integrity_signal_evidence (
              signal_id, evidence_role, independent_source_key, source_id,
              source_record_pk, source_url, content_sha256, excerpt,
              observed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                role,
                source_key,
                str(row.get("source_id") or "") or None,
                int(row["source_record_pk"]) if row.get("source_record_pk") else None,
                str(row.get("source_url") or "") or None,
                str(row.get("content_sha256") or "") or None,
                str(row.get("excerpt") or "")[:4_000] or None,
                str(row.get("observed_at") or "") or None,
                now_iso,
            ),
        )
        inserted += max(0, int(cursor.rowcount))
    conn.commit()
    return inserted


def create_review_signal(
    conn: sqlite3.Connection,
    *,
    signal_id: str | None,
    detector_id: str,
    detector_version: str,
    signal_type: str,
    subject_type: str,
    subject_id: str,
    summary: str,
    evidence: Iterable[Mapping[str, object]],
    jurisdiction: str = "",
    period_start: str = "",
    period_end: str = "",
    review_priority: int = 0,
    metrics: Mapping[str, object] | None = None,
    limitations: Iterable[str] = (),
    now: datetime | None = None,
) -> str:
    ensure_integrity_signal_schema(conn)
    normalized = {
        "detector_id": str(detector_id).strip(),
        "detector_version": str(detector_version).strip(),
        "signal_type": str(signal_type).strip(),
        "subject_type": str(subject_type).strip(),
        "subject_id": str(subject_id).strip(),
        "summary": str(summary).strip(),
    }
    if any(not value for value in normalized.values()):
        raise ValueError("detector, signal, subject, and summary fields are required")
    resolved_signal_id = str(signal_id or uuid.uuid4()).strip()
    now_iso = _now_iso(now)
    conn.execute(
        """
        INSERT INTO integrity_signals (
          signal_id, detector_id, detector_version, signal_type,
          subject_type, subject_id, jurisdiction, period_start, period_end,
          state, review_priority, summary, metrics_json, limitations_json,
          publication_status, right_of_reply_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'review_signal', ?, ?, ?, ?,
                  'internal', 'pending', ?, ?)
        ON CONFLICT(signal_id) DO UPDATE SET
          review_priority = excluded.review_priority,
          summary = excluded.summary,
          metrics_json = excluded.metrics_json,
          limitations_json = excluded.limitations_json,
          updated_at = excluded.updated_at
        """,
        (
            resolved_signal_id,
            normalized["detector_id"],
            normalized["detector_version"],
            normalized["signal_type"],
            normalized["subject_type"],
            normalized["subject_id"],
            str(jurisdiction or "") or None,
            str(period_start or "") or None,
            str(period_end or "") or None,
            int(review_priority),
            normalized["summary"],
            _stable_json(dict(metrics or {})),
            _stable_json([str(value) for value in limitations]),
            now_iso,
            now_iso,
        ),
    )
    add_signal_evidence(
        conn,
        signal_id=resolved_signal_id,
        evidence=evidence,
        now=now,
    )
    return resolved_signal_id


def _signal_row(conn: sqlite3.Connection, signal_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM integrity_signals WHERE signal_id = ?", (signal_id,)
    ).fetchone()
    if row is None:
        raise KeyError(signal_id)
    return row


def _corroboration_gate(conn: sqlite3.Connection, signal_id: str) -> None:
    rows = conn.execute(
        """
        SELECT evidence_role, independent_source_key, source_url, content_sha256
        FROM integrity_signal_evidence
        WHERE signal_id = ? AND evidence_role IN ('observed', 'corroborating')
        """,
        (signal_id,),
    ).fetchall()
    independent = {str(row["independent_source_key"]) for row in rows}
    traceable = [
        row
        for row in rows
        if str(row["source_url"] or "").strip()
        and str(row["content_sha256"] or "").strip()
    ]
    if len(independent) < 2 or len(traceable) < 2:
        raise ValueError(
            "corroborated_risk requires two independent traceable evidence sources"
        )
    reviews = conn.execute(
        """
        SELECT reviewer_id, reviewer_independence_class
        FROM integrity_signal_reviews
        WHERE signal_id = ? AND decision = 'corroborate'
        """,
        (signal_id,),
    ).fetchall()
    reviewers = {str(row["reviewer_id"]) for row in reviews}
    independent = {
        str(row["reviewer_id"])
        for row in reviews
        if str(row["reviewer_independence_class"]) == "independent"
    }
    if len(reviewers) < 2 or not independent:
        raise ValueError(
            "corroborated_risk requires two human corroboration reviews, including one independent reviewer"
        )


def record_signal_review(
    conn: sqlite3.Connection,
    *,
    signal_id: str,
    reviewer_id: str,
    reviewer_independence_class: str,
    decision: str,
    rationale: str,
    now: datetime | None = None,
) -> None:
    ensure_integrity_signal_schema(conn)
    _signal_row(conn, signal_id)
    independence = str(reviewer_independence_class).strip()
    if independence not in {"author", "maintainer", "independent", "unknown"}:
        raise ValueError(f"invalid reviewer independence class: {independence}")
    normalized_decision = str(decision).strip()
    if normalized_decision not in {
        "needs_more_evidence",
        "corroborate",
        "reject",
        "approve_publication",
        "withdraw",
    }:
        raise ValueError(f"invalid review decision: {normalized_decision}")
    normalized_reviewer = str(reviewer_id).strip()
    if not normalized_reviewer or not str(rationale).strip():
        raise ValueError("reviewer_id and rationale are required")
    conn.execute(
        """
        INSERT INTO integrity_signal_reviews (
          signal_id, reviewer_id, reviewer_independence_class,
          decision, rationale, reviewed_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            normalized_reviewer,
            independence,
            normalized_decision,
            str(rationale).strip(),
            _now_iso(now),
        ),
    )
    conn.commit()


def transition_signal(
    conn: sqlite3.Connection,
    *,
    signal_id: str,
    to_state: str,
    actor_kind: str,
    actor_id: str,
    rationale: str,
    now: datetime | None = None,
) -> None:
    ensure_integrity_signal_schema(conn)
    target = str(to_state).strip()
    if target not in SIGNAL_STATES:
        raise ValueError(f"invalid signal state: {target}")
    row = _signal_row(conn, signal_id)
    current = str(row["state"])
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid signal transition: {current} -> {target}")
    normalized_actor_kind = str(actor_kind).strip()
    if target in {"corroborated_risk", "rejected"} and normalized_actor_kind not in HUMAN_ACTOR_KINDS:
        raise ValueError(f"{target} requires a human reviewer or maintainer")
    if target == "official_finding":
        official = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM integrity_signal_evidence
                WHERE signal_id = ? AND evidence_role = 'official_finding'
                  AND source_url IS NOT NULL AND content_sha256 IS NOT NULL
                """,
                (signal_id,),
            ).fetchone()[0]
        )
        if official < 1:
            raise ValueError("official_finding requires traceable official evidence")
    if target == "corroborated_risk":
        _corroboration_gate(conn, signal_id)
    now_iso = _now_iso(now)
    conn.execute(
        "UPDATE integrity_signals SET state = ?, updated_at = ? WHERE signal_id = ?",
        (target, now_iso, signal_id),
    )
    conn.execute(
        """
        INSERT INTO integrity_signal_transitions (
          signal_id, from_state, to_state, actor_kind, actor_id,
          rationale, transitioned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            current,
            target,
            normalized_actor_kind,
            str(actor_id).strip(),
            str(rationale).strip(),
            now_iso,
        ),
    )
    if target in {"rejected", "superseded"}:
        conn.execute(
            """
            UPDATE integrity_signals
            SET publication_status = 'withdrawn', updated_at = ?
            WHERE signal_id = ?
            """,
            (now_iso, signal_id),
        )
    conn.commit()


def supersede_internal_review_signals(
    conn: sqlite3.Connection,
    *,
    signal_ids: Iterable[str],
    actor_kind: str,
    actor_id: str,
    rationale: str,
    now: datetime | None = None,
) -> int:
    """Supersede an exact internal review-signal set with transition history."""
    ensure_integrity_signal_schema(conn)
    normalized_ids = sorted({str(value).strip() for value in signal_ids if str(value).strip()})
    if not normalized_ids:
        return 0
    if not str(actor_kind).strip() or not str(actor_id).strip() or not str(rationale).strip():
        raise ValueError("actor_kind, actor_id, and rationale are required")
    eligible: list[str] = []
    for offset in range(0, len(normalized_ids), 500):
        batch = normalized_ids[offset : offset + 500]
        marks = ",".join("?" for _ in batch)
        eligible.extend(
            str(row[0])
            for row in conn.execute(
                f"""
                SELECT signal_id
                FROM integrity_signals
                WHERE signal_id IN ({marks})
                  AND state = 'review_signal'
                  AND publication_status = 'internal'
                ORDER BY signal_id
                """,
                batch,
            )
        )
    if not eligible:
        return 0
    now_iso = _now_iso(now)
    conn.executemany(
        """
        INSERT INTO integrity_signal_transitions (
          signal_id, from_state, to_state, actor_kind, actor_id,
          rationale, transitioned_at
        ) VALUES (?, 'review_signal', 'superseded', ?, ?, ?, ?)
        """,
        [
            (
                signal_id,
                str(actor_kind).strip(),
                str(actor_id).strip(),
                str(rationale).strip(),
                now_iso,
            )
            for signal_id in eligible
        ],
    )
    for offset in range(0, len(eligible), 500):
        batch = eligible[offset : offset + 500]
        marks = ",".join("?" for _ in batch)
        conn.execute(
            f"""
            UPDATE integrity_signals
            SET state = 'superseded', publication_status = 'withdrawn',
                updated_at = ?
            WHERE signal_id IN ({marks})
              AND state = 'review_signal'
              AND publication_status = 'internal'
            """,
            (now_iso, *batch),
        )
    conn.commit()
    return len(eligible)


def record_right_of_reply(
    conn: sqlite3.Connection,
    *,
    signal_id: str,
    response_status: str,
    recorded_by: str,
    response_source_url: str = "",
    response_content_sha256: str = "",
    response_summary: str = "",
    now: datetime | None = None,
) -> None:
    status = str(response_status).strip()
    if status not in RESPONSE_STATUSES - {"pending"}:
        raise ValueError(f"invalid response status: {status}")
    _signal_row(conn, signal_id)
    now_iso = _now_iso(now)
    conn.execute(
        """
        INSERT INTO integrity_signal_responses (
          signal_id, response_status, response_source_url,
          response_content_sha256, response_summary, recorded_by, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            status,
            str(response_source_url or "") or None,
            str(response_content_sha256 or "") or None,
            str(response_summary or "") or None,
            str(recorded_by).strip(),
            now_iso,
        ),
    )
    conn.execute(
        """
        UPDATE integrity_signals
        SET right_of_reply_status = ?, updated_at = ?
        WHERE signal_id = ?
        """,
        (status, now_iso, signal_id),
    )
    conn.commit()


def approve_signal_publication(
    conn: sqlite3.Connection,
    *,
    signal_id: str,
    reviewer_id: str,
    rationale: str,
    now: datetime | None = None,
) -> None:
    row = _signal_row(conn, signal_id)
    if str(row["state"]) not in {"corroborated_risk", "official_finding"}:
        raise ValueError("only corroborated_risk or official_finding can be published")
    if str(row["right_of_reply_status"]) == "pending":
        raise ValueError("right-of-reply status must be resolved before publication")
    now_iso = _now_iso(now)
    conn.execute(
        """
        UPDATE integrity_signals
        SET publication_status = 'approved', updated_at = ?
        WHERE signal_id = ?
        """,
        (now_iso, signal_id),
    )
    conn.execute(
        """
        INSERT INTO integrity_signal_reviews (
          signal_id, reviewer_id, reviewer_independence_class,
          decision, rationale, reviewed_at
        ) VALUES (?, ?, 'maintainer', 'approve_publication', ?, ?)
        """,
        (signal_id, str(reviewer_id).strip(), str(rationale).strip(), now_iso),
    )
    conn.commit()


def record_signal_correction(
    conn: sqlite3.Connection,
    *,
    signal_id: str,
    correction_type: str,
    rationale: str,
    corrected_by: str,
    evidence_url: str = "",
    now: datetime | None = None,
) -> None:
    allowed = {
        "counterevidence",
        "factual_correction",
        "identity_correction",
        "withdrawal",
        "supersession",
    }
    normalized_type = str(correction_type).strip()
    if normalized_type not in allowed:
        raise ValueError(f"invalid correction_type: {normalized_type}")
    row = _signal_row(conn, signal_id)
    now_iso = _now_iso(now)
    conn.execute(
        """
        INSERT INTO integrity_signal_corrections (
          signal_id, correction_type, rationale, evidence_url,
          corrected_by, corrected_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            normalized_type,
            str(rationale).strip(),
            str(evidence_url or "") or None,
            str(corrected_by).strip(),
            now_iso,
        ),
    )
    if str(row["state"]) != "superseded":
        conn.execute(
            """
            INSERT INTO integrity_signal_transitions (
              signal_id, from_state, to_state, actor_kind, actor_id,
              rationale, transitioned_at
            ) VALUES (?, ?, 'superseded', 'maintainer', ?, ?, ?)
            """,
            (
                signal_id,
                str(row["state"]),
                str(corrected_by).strip(),
                str(rationale).strip(),
                now_iso,
            ),
        )
    conn.execute(
        """
        UPDATE integrity_signals
        SET state = 'superseded', publication_status = 'withdrawn', updated_at = ?
        WHERE signal_id = ?
        """,
        (now_iso, signal_id),
    )
    conn.commit()


def public_integrity_signals(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT signal_id, signal_type, subject_type, subject_id, jurisdiction,
               period_start, period_end, state, summary, metrics_json,
               limitations_json, right_of_reply_status, updated_at
        FROM integrity_signals
        WHERE publication_status IN ('approved', 'published')
          AND state IN ('corroborated_risk', 'official_finding')
        ORDER BY updated_at DESC, signal_id
        """
    ).fetchall()
    return [
        {
            **dict(row),
            "metrics": json.loads(str(row["metrics_json"] or "{}")),
            "limitations": json.loads(str(row["limitations_json"] or "[]")),
        }
        for row in rows
    ]
