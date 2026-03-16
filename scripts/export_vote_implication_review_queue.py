#!/usr/bin/env python3
"""Export review queue for citizen-facing vote implications.

This lane exists because official parliamentary vote titles are often procedural
wrappers ("Proposiciones no de Ley.", "Enmiendas del Senado.", etc.) rather than
citizen-meaningful descriptions of what is at stake.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SOURCE_ID = "congreso_votaciones"
DEFAULT_EXTRACT_SOURCE_ID = "parl_initiative_docs"

VALID_REVIEW_REASONS = (
    "generic_title",
    "split_vote_point",
    "procedural_wrapper",
    "subject_low_specificity",
    "missing_excerpt",
)
REVIEW_REASON_PRIORITY = (
    "split_vote_point",
    "generic_title",
    "procedural_wrapper",
    "subject_low_specificity",
    "missing_excerpt",
)
VALID_IMPLICATION_KINDS = (
    "binding_law",
    "budget_tax",
    "regulation",
    "non_binding_motion",
    "oversight",
    "authorization",
    "procedural",
    "unknown",
)
VALID_BINDING_STRENGTHS = ("binding", "non_binding", "authorization", "procedural", "unknown")

GENERIC_TITLE_PREFIXES = (
    "Proposiciones no de Ley",
    "Mociones consecuencia de interpelaciones urgentes",
    "Moción consecuencia de interpelación urgente",
    "Dictámenes de Comisiones",
    "Enmiendas del Senado",
    "Toma en consideración",
    "Debates de totalidad",
    "Avocación de iniciativas legislativas",
    "Resto del proyecto de ley",
    "Convalidación o derogación de Reales Decretos-leyes",
    "Autorización",
    "Actos en relación con los estados de alarma",
)

PROCEDURAL_TITLE_PREFIXES = (
    "Enmiendas del Senado",
    "Dictámenes de Comisiones",
    "Toma en consideración",
    "Debates de totalidad",
    "Avocación de iniciativas legislativas",
    "Resto del proyecto de ley",
    "Actos en relación con los estados de alarma",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export vote implication review queue")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-id", default=DEFAULT_SOURCE_ID, help="Vote-event source_id scope")
    p.add_argument(
        "--extract-source-id",
        default=DEFAULT_EXTRACT_SOURCE_ID,
        help="Doc extraction source_id used for subject/excerpt hints",
    )
    p.add_argument("--only-pending", action="store_true", help="Only export rows still pending")
    p.add_argument(
        "--review-reason",
        action="append",
        default=[],
        choices=VALID_REVIEW_REASONS,
        help="Filter exported rows to one or more review reasons",
    )
    p.add_argument(
        "--max-margin",
        type=int,
        default=-1,
        help="Filter exported rows to yes/no margin <= N; negative disables the filter",
    )
    p.add_argument(
        "--contains",
        action="append",
        default=[],
        help="Case-insensitive text filter across official title/subject/subgroup",
    )
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--offset", type=int, default=0, help="Row offset for deterministic batching")
    p.add_argument("--out", required=True, help="Output CSV path")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _load_json_dict(raw: Any) -> dict[str, Any]:
    token = _norm(raw)
    if not token:
        return {}
    try:
        obj = json.loads(token)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _review_key(vote_event_id: str, initiative_id: str) -> str:
    return f"{_norm(vote_event_id)}|{_norm(initiative_id)}"


def _is_generic_vote_title(title: str, initiative_title: str) -> bool:
    title_norm = _norm(title)
    initiative_norm = _norm(initiative_title)
    if not title_norm:
        return False
    if title_norm == initiative_norm and title_norm:
        return False
    return any(title_norm.startswith(prefix) for prefix in GENERIC_TITLE_PREFIXES)


def _is_procedural_wrapper(title: str) -> bool:
    title_norm = _norm(title)
    if not title_norm:
        return False
    return any(title_norm.startswith(prefix) for prefix in PROCEDURAL_TITLE_PREFIXES)


def classify_implication_kind(vote_title: str, initiative_title: str) -> str:
    subject = _norm(initiative_title) or _norm(vote_title)
    lower = subject.lower()
    if not subject:
        return "unknown"
    if lower.startswith("proyecto de ley") or lower.startswith("proposición de ley"):
        if "impuesto" in lower or "presupuestos generales del estado" in lower:
            return "budget_tax"
        return "binding_law"
    if lower.startswith("real decreto-ley") or lower.startswith("real decreto"):
        return "regulation"
    if lower.startswith("proposición no de ley") or lower.startswith("moción consecuencia de interpelación"):
        return "non_binding_motion"
    if lower.startswith("autorización") or lower.startswith("convenio ") or "tratado" in lower:
        return "authorization"
    if lower.startswith("pregunta") or lower.startswith("interpelación"):
        return "oversight"
    if _is_procedural_wrapper(vote_title):
        return "procedural"
    return "unknown"


def classify_binding_strength(implication_kind: str) -> str:
    if implication_kind in {"binding_law", "budget_tax", "regulation"}:
        return "binding"
    if implication_kind == "non_binding_motion" or implication_kind == "oversight":
        return "non_binding"
    if implication_kind == "authorization":
        return "authorization"
    if implication_kind == "procedural":
        return "procedural"
    return "unknown"


def compute_review_reasons(
    *,
    vote_title: str,
    subgroup_title: str,
    initiative_title: str,
    extracted_subject: str,
    extracted_excerpt: str,
    analysis_payload_json: str,
) -> list[str]:
    reasons: list[str] = []
    if _is_generic_vote_title(vote_title, initiative_title):
        reasons.append("generic_title")
    if "separada por puntos" in _norm(subgroup_title).lower():
        reasons.append("split_vote_point")
    if _is_procedural_wrapper(vote_title):
        reasons.append("procedural_wrapper")

    payload = _load_json_dict(analysis_payload_json)
    subject_method = _norm(payload.get("subject_method")).lower()
    extracted_subject_norm = _norm(extracted_subject)
    initiative_title_norm = _norm(initiative_title)
    if extracted_subject_norm and initiative_title_norm and extracted_subject_norm == initiative_title_norm:
        reasons.append("subject_low_specificity")
    elif subject_method.startswith("title"):
        reasons.append("subject_low_specificity")

    if not _norm(extracted_excerpt):
        reasons.append("missing_excerpt")
    return [reason for reason in VALID_REVIEW_REASONS if reason in reasons]


def compute_priority(
    *,
    reasons: list[str],
    implication_kind: str,
    totals_yes: Any,
    totals_no: Any,
) -> int:
    score = 50
    if "split_vote_point" in reasons:
        score += 20
    if "generic_title" in reasons:
        score += 15
    if "procedural_wrapper" in reasons:
        score += 10
    if "subject_low_specificity" in reasons:
        score += 10
    if "missing_excerpt" in reasons:
        score += 5
    try:
        margin = abs(int(totals_yes or 0) - int(totals_no or 0))
    except (TypeError, ValueError):
        margin = 999999
    if margin <= 5:
        score += 10
    if implication_kind in {"binding_law", "budget_tax", "regulation"}:
        score += 10
    return max(0, min(100, int(score)))


def _choose_primary_reason(reasons: list[str]) -> str | None:
    for reason in REVIEW_REASON_PRIORITY:
        if reason in reasons:
            return reason
    return None


def sync_review_queue(
    conn: Any,
    *,
    source_id: str,
    extract_source_id: str,
) -> dict[str, int]:
    conn.execute(
        """
        DELETE FROM parl_vote_implication_reviews
        WHERE source_id = ?
          AND vote_event_id IN (
            SELECT vote_event_id
            FROM parl_vote_events
            WHERE source_id = ?
              AND source_url LIKE 'file:%'
          )
        """,
        (str(source_id), str(source_id)),
    )
    rows = conn.execute(
        """
        SELECT
          v.vote_event_id,
          v.vote_date,
          v.legislature,
          v.title AS vote_title,
          v.subgroup_title,
          v.expediente_text,
          v.totals_yes,
          v.totals_no,
          v.totals_abstain,
          v.totals_no_vote,
          v.source_id,
          v.source_url,
          vei.initiative_id,
          i.title AS initiative_title,
          i.type AS initiative_type,
          i.procedure_type,
          i.source_url AS initiative_source_url,
          ex.source_record_pk AS extract_source_record_pk,
          ex.extracted_subject,
          ex.extracted_excerpt,
          ex.confidence AS extract_confidence,
          ex.analysis_payload_json,
          td.source_url AS doc_source_url,
          td.raw_path AS doc_raw_path
        FROM parl_vote_events v
        LEFT JOIN parl_vote_event_initiatives vei ON vei.vote_event_id = v.vote_event_id
        LEFT JOIN parl_initiatives i ON i.initiative_id = vei.initiative_id
        LEFT JOIN parl_initiative_doc_extractions ex
          ON ex.source_record_pk = (
            SELECT ex2.source_record_pk
            FROM parl_initiative_doc_extractions ex2
            WHERE ex2.sample_initiative_id = i.initiative_id
              AND ex2.source_id = ?
            ORDER BY ex2.needs_review ASC, ex2.confidence DESC, ex2.source_record_pk ASC
            LIMIT 1
          )
        LEFT JOIN text_documents td
          ON td.source_record_pk = ex.source_record_pk
         AND td.source_id = ex.source_id
        WHERE v.source_id = ?
          AND COALESCE(v.source_url, '') NOT LIKE 'file:%'
        ORDER BY v.vote_date DESC, v.vote_event_id DESC, COALESCE(vei.initiative_id, '') ASC
        """,
        (str(extract_source_id), str(source_id)),
    ).fetchall()

    now_iso = now_utc_iso()
    queued = 0
    upserted = 0
    for row in rows:
        reasons = compute_review_reasons(
            vote_title=str(row["vote_title"] or ""),
            subgroup_title=str(row["subgroup_title"] or ""),
            initiative_title=str(row["initiative_title"] or row["expediente_text"] or ""),
            extracted_subject=str(row["extracted_subject"] or ""),
            extracted_excerpt=str(row["extracted_excerpt"] or ""),
            analysis_payload_json=str(row["analysis_payload_json"] or ""),
        )
        if not reasons:
            continue
        queued += 1

        initiative_id = _norm(row["initiative_id"])
        review_key = _review_key(str(row["vote_event_id"] or ""), initiative_id)
        implication_kind = classify_implication_kind(
            str(row["vote_title"] or ""),
            str(row["initiative_title"] or row["expediente_text"] or ""),
        )
        binding_strength = classify_binding_strength(implication_kind)
        priority = compute_priority(
            reasons=reasons,
            implication_kind=implication_kind,
            totals_yes=row["totals_yes"],
            totals_no=row["totals_no"],
        )
        primary_reason = _choose_primary_reason(reasons)
        payload = {
            "reasons": reasons,
            "vote": {
                "vote_date": _norm(row["vote_date"]),
                "title": _norm(row["vote_title"]),
                "subgroup_title": _norm(row["subgroup_title"]),
                "expediente_text": _norm(row["expediente_text"]),
                "source_url": _norm(row["source_url"]),
                "totals_yes": int(row["totals_yes"] or 0),
                "totals_no": int(row["totals_no"] or 0),
                "totals_abstain": int(row["totals_abstain"] or 0),
                "totals_no_vote": int(row["totals_no_vote"] or 0),
            },
            "initiative": {
                "initiative_id": initiative_id,
                "title": _norm(row["initiative_title"]),
                "type": _norm(row["initiative_type"]),
                "procedure_type": _norm(row["procedure_type"]),
                "source_url": _norm(row["initiative_source_url"]),
            },
            "doc_hint": {
                "source_record_pk": int(row["extract_source_record_pk"] or 0) or None,
                "doc_source_url": _norm(row["doc_source_url"]),
                "doc_raw_path": _norm(row["doc_raw_path"]),
                "extracted_subject": _norm(row["extracted_subject"]),
                "extracted_excerpt": _norm(row["extracted_excerpt"]),
                "extract_confidence": float(row["extract_confidence"]) if row["extract_confidence"] is not None else None,
                "analysis_payload": _load_json_dict(row["analysis_payload_json"]),
            },
        }

        conn.execute(
            """
            INSERT INTO parl_vote_implication_reviews (
              review_key, vote_event_id, initiative_id, source_id, review_reason, status, priority,
              heuristic_subject, heuristic_implication_kind, heuristic_binding_strength,
              extractor_version, raw_payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(review_key) DO UPDATE SET
              vote_event_id = excluded.vote_event_id,
              initiative_id = excluded.initiative_id,
              source_id = excluded.source_id,
              review_reason = excluded.review_reason,
              status = CASE
                WHEN parl_vote_implication_reviews.status IN ('resolved', 'ignored')
                THEN parl_vote_implication_reviews.status
                ELSE 'pending'
              END,
              priority = excluded.priority,
              heuristic_subject = excluded.heuristic_subject,
              heuristic_implication_kind = excluded.heuristic_implication_kind,
              heuristic_binding_strength = excluded.heuristic_binding_strength,
              extractor_version = excluded.extractor_version,
              raw_payload_json = excluded.raw_payload_json,
              updated_at = excluded.updated_at
            """,
            (
                review_key,
                str(row["vote_event_id"] or ""),
                initiative_id or None,
                str(row["source_id"] or ""),
                primary_reason,
                priority,
                _norm(row["extracted_subject"] or row["initiative_title"] or row["expediente_text"]),
                implication_kind,
                binding_strength,
                "citizen_vote_implication_v1",
                stable_json(payload),
                now_iso,
                now_iso,
            ),
        )
        upserted += 1
    conn.commit()
    return {"candidate_rows": queued, "upserted": upserted}


def fetch_review_rows(
    conn: Any,
    *,
    source_id: str,
    only_pending: bool,
    review_reasons: list[str],
    max_margin: int,
    contains_terms: list[str],
    limit: int,
    offset: int,
) -> list[Any]:
    where = ["r.source_id = ?"]
    params: list[object] = [str(source_id)]
    if bool(only_pending):
        where.append("r.status = 'pending'")
    filtered_reasons = [reason for reason in review_reasons if reason in VALID_REVIEW_REASONS]
    if filtered_reasons:
        where.append(f"r.review_reason IN ({','.join(['?'] * len(filtered_reasons))})")
        params.extend(filtered_reasons)
    max_margin_i = int(max_margin or -1)
    if max_margin_i >= 0:
        where.append("ABS(COALESCE(v.totals_yes, 0) - COALESCE(v.totals_no, 0)) <= ?")
        params.append(max_margin_i)
    filtered_terms = [_norm(term).lower() for term in contains_terms if _norm(term)]
    if filtered_terms:
        match_expr = (
            "LOWER(COALESCE(i.title, '') || ' ' || COALESCE(v.expediente_text, '') || ' ' || "
            "COALESCE(v.title, '') || ' ' || COALESCE(v.subgroup_title, ''))"
        )
        term_clauses = []
        for term in filtered_terms:
            term_clauses.append(f"{match_expr} LIKE ?")
            params.append(f"%{term}%")
        where.append(f"({' OR '.join(term_clauses)})")

    limit_sql = ""
    limit_i = max(0, int(limit or 0))
    offset_i = max(0, int(offset or 0))
    if limit_i > 0:
        limit_sql = "LIMIT ? OFFSET ?"
        params.extend([limit_i, offset_i])
    elif offset_i > 0:
        limit_sql = "LIMIT -1 OFFSET ?"
        params.append(offset_i)

    return conn.execute(
        f"""
        SELECT
          r.review_id,
          r.review_key,
          r.vote_event_id,
          r.initiative_id,
          r.source_id,
          r.review_reason,
          r.status,
          r.priority,
          r.heuristic_subject,
          r.heuristic_implication_kind,
          r.heuristic_binding_strength,
          r.citizen_title,
          r.citizen_question,
          r.citizen_summary,
          r.impact_if_approved,
          r.impact_if_rejected,
          r.affected_groups,
          r.evidence_quote,
          r.final_implication_kind,
          r.final_binding_strength,
          r.confidence,
          r.extractor_version,
          r.note,
          v.vote_date,
          v.legislature,
          v.title AS vote_title,
          v.subgroup_title,
          v.expediente_text,
          v.totals_yes,
          v.totals_no,
          v.totals_abstain,
          v.totals_no_vote,
          v.source_url,
          i.title AS initiative_title,
          i.type AS initiative_type,
          i.procedure_type,
          i.source_url AS initiative_source_url
        FROM parl_vote_implication_reviews r
        JOIN parl_vote_events v ON v.vote_event_id = r.vote_event_id
        LEFT JOIN parl_initiatives i ON i.initiative_id = r.initiative_id
        WHERE {' AND '.join(where)}
        ORDER BY
          CASE r.status WHEN 'pending' THEN 0 WHEN 'resolved' THEN 1 ELSE 2 END ASC,
          r.priority DESC,
          v.vote_date DESC,
          r.review_id DESC
        {limit_sql}
        """,
        params,
    ).fetchall()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        sync = sync_review_queue(
            conn,
            source_id=str(args.source_id),
            extract_source_id=str(args.extract_source_id),
        )
        rows = fetch_review_rows(
            conn,
            source_id=str(args.source_id),
            only_pending=bool(args.only_pending),
            review_reasons=[str(reason) for reason in args.review_reason],
            max_margin=int(args.max_margin or -1),
            contains_terms=[str(term) for term in args.contains],
            limit=int(args.limit or 0),
            offset=int(args.offset or 0),
        )

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "review_id",
                "review_key",
                "vote_event_id",
                "initiative_id",
                "vote_date",
                "legislature",
                "review_reason",
                "current_status",
                "priority",
                "official_vote_title",
                "official_subject",
                "subgroup_title",
                "initiative_title",
                "initiative_type",
                "procedure_type",
                "totals_yes",
                "totals_no",
                "totals_abstain",
                "totals_no_vote",
                "margin",
                "heuristic_subject",
                "heuristic_implication_kind",
                "heuristic_binding_strength",
                "vote_source_url",
                "initiative_source_url",
                "review_status",
                "final_implication_kind",
                "final_binding_strength",
                "citizen_title",
                "citizen_question",
                "citizen_summary",
                "impact_if_approved",
                "impact_if_rejected",
                "affected_groups",
                "evidence_quote",
                "final_confidence",
                "review_note",
                "reviewer",
            ]
        )
        for row in rows:
            try:
                margin = abs(int(row["totals_yes"] or 0) - int(row["totals_no"] or 0))
            except (TypeError, ValueError):
                margin = ""
            w.writerow(
                [
                    str(row["review_id"] or ""),
                    str(row["review_key"] or ""),
                    str(row["vote_event_id"] or ""),
                    str(row["initiative_id"] or ""),
                    str(row["vote_date"] or ""),
                    str(row["legislature"] or ""),
                    str(row["review_reason"] or ""),
                    str(row["status"] or ""),
                    str(row["priority"] or ""),
                    str(row["vote_title"] or ""),
                    str(row["expediente_text"] or ""),
                    str(row["subgroup_title"] or ""),
                    str(row["initiative_title"] or ""),
                    str(row["initiative_type"] or ""),
                    str(row["procedure_type"] or ""),
                    str(row["totals_yes"] or ""),
                    str(row["totals_no"] or ""),
                    str(row["totals_abstain"] or ""),
                    str(row["totals_no_vote"] or ""),
                    str(margin),
                    str(row["heuristic_subject"] or ""),
                    str(row["heuristic_implication_kind"] or ""),
                    str(row["heuristic_binding_strength"] or ""),
                    str(row["source_url"] or ""),
                    str(row["initiative_source_url"] or ""),
                    "",
                    str(row["final_implication_kind"] or ""),
                    str(row["final_binding_strength"] or ""),
                    str(row["citizen_title"] or ""),
                    str(row["citizen_question"] or ""),
                    str(row["citizen_summary"] or ""),
                    str(row["impact_if_approved"] or ""),
                    str(row["impact_if_rejected"] or ""),
                    str(row["affected_groups"] or ""),
                    str(row["evidence_quote"] or ""),
                    str(row["confidence"] or ""),
                    str(row["note"] or ""),
                    "",
                ]
            )

    print(f"OK wrote {out_path} (rows={len(rows)}, candidate_rows={sync['candidate_rows']}, upserted={sync['upserted']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
