#!/usr/bin/env python3
"""Diagnose residual sanction-norm vote coverage gaps with explicit no-new-lever signals."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from etl.politicos_es.util import normalize_ws
from scripts.backfill_sanction_norms_vote_evidence import TITLE_MATCH_RULES, _fold

BOE_ID_RE = re.compile(r"BOE-A-\d{4}-\d{1,6}", re.IGNORECASE)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _parse_roles(raw: str) -> list[str]:
    allowed = {"propose", "approve", "delegate", "enforce", "audit"}
    out: list[str] = []
    for token in str(raw or "").split(","):
        role = _norm(token).lower()
        if role and role in allowed and role not in out:
            out.append(role)
    return out


def _iter_missing_vote_responsibilities(
    conn: sqlite3.Connection,
    *,
    roles: list[str],
) -> list[sqlite3.Row]:
    if not roles:
        return []
    placeholders = ",".join(["?"] * len(roles))
    sql = f"""
        WITH base AS (
          SELECT
            r.responsibility_id,
            r.role,
            ln.norm_id,
            ln.boe_id
          FROM legal_fragment_responsibilities r
          JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
          JOIN sanction_norm_catalog c ON c.norm_id = l.norm_id
          JOIN legal_norms ln ON ln.norm_id = c.norm_id
          WHERE r.role IN ({placeholders})
        )
        SELECT
          b.responsibility_id,
          b.role,
          b.norm_id,
          UPPER(TRIM(COALESCE(b.boe_id, ''))) AS boe_id,
          EXISTS(
            SELECT 1
            FROM legal_fragment_responsibility_evidence e
            WHERE e.responsibility_id = b.responsibility_id
              AND e.evidence_type IN ('congreso_diario', 'senado_diario')
          ) AS has_parliamentary,
          EXISTS(
            SELECT 1
            FROM legal_fragment_responsibility_evidence e
            WHERE e.responsibility_id = b.responsibility_id
              AND e.evidence_type IN ('congreso_vote', 'senado_vote')
          ) AS has_vote
        FROM base b
        WHERE UPPER(TRIM(COALESCE(b.boe_id, ''))) <> ''
          AND NOT EXISTS (
            SELECT 1
            FROM legal_fragment_responsibility_evidence e
            WHERE e.responsibility_id = b.responsibility_id
              AND e.evidence_type IN ('congreso_vote', 'senado_vote')
          )
        ORDER BY boe_id, b.role, b.responsibility_id
    """
    return conn.execute(sql, tuple(roles)).fetchall()


def _iter_vote_link_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
          pve.vote_event_id,
          pve.title AS vote_title,
          pve.expediente_text AS vote_expediente_text,
          pvi.initiative_id,
          pi.title AS initiative_title
        FROM parl_vote_event_initiatives pvi
        JOIN parl_vote_events pve ON pve.vote_event_id = pvi.vote_event_id
        LEFT JOIN parl_initiatives pi ON pi.initiative_id = pvi.initiative_id
        """
    ).fetchall()


def _iter_vote_linked_doc_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
          pid.initiative_id,
          td.text_document_id,
          td.text_excerpt
        FROM parl_initiative_documents pid
        JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
        WHERE td.source_id = 'parl_initiative_docs'
          AND pid.initiative_id IN (
            SELECT DISTINCT initiative_id
            FROM parl_vote_event_initiatives
          )
        """
    ).fetchall()


def _iter_parliamentary_initiatives_for_responsibility(
    conn: sqlite3.Connection,
    *,
    responsibility_id: int,
) -> set[str]:
    rows = conn.execute(
        """
        SELECT
          raw_payload
        FROM legal_fragment_responsibility_evidence
        WHERE responsibility_id = ?
          AND evidence_type IN ('congreso_diario', 'senado_diario')
        """,
        (int(responsibility_id),),
    ).fetchall()
    out: set[str] = set()
    for row in rows:
        try:
            payload = json.loads(str(row["raw_payload"] or "{}"))
        except json.JSONDecodeError:
            payload = {}
        initiative_id = _norm(payload.get("initiative_id"))
        if initiative_id:
            out.add(initiative_id)
    return out


def build_report(conn: sqlite3.Connection, *, roles: list[str]) -> dict[str, Any]:
    roles_norm = [r for r in roles if r]
    if not roles_norm:
        raise ValueError("at least one role is required")

    missing_rows = _iter_missing_vote_responsibilities(conn, roles=roles_norm)
    vote_rows = _iter_vote_link_rows(conn)
    vote_docs = _iter_vote_linked_doc_rows(conn)
    vote_linked_inits = {
        _norm(row["initiative_id"])
        for row in conn.execute("SELECT DISTINCT initiative_id FROM parl_vote_event_initiatives").fetchall()
        if _norm(row["initiative_id"])
    }

    vote_texts_raw: list[str] = []
    vote_texts_folded: list[str] = []
    for row in vote_rows:
        merged = " ".join(
            [
                _norm(row["vote_title"]),
                _norm(row["vote_expediente_text"]),
                _norm(row["initiative_title"]),
            ]
        ).strip()
        if not merged:
            continue
        vote_texts_raw.append(merged)
        vote_texts_folded.append(_fold(merged))

    vote_doc_texts_raw = [_norm(r["text_excerpt"]) for r in vote_docs if _norm(r["text_excerpt"])]
    vote_doc_texts_folded = [_fold(t) for t in vote_doc_texts_raw]

    missing: list[dict[str, Any]] = []
    boe_ids_missing: set[str] = set()
    missing_with_title_candidates = 0
    missing_with_doc_candidates = 0
    missing_with_linked_parl_inits = 0

    for row in missing_rows:
        responsibility_id = int(row["responsibility_id"])
        boe_id = _norm(row["boe_id"]).upper()
        role = _norm(row["role"])
        has_parliamentary = bool(int(row["has_parliamentary"]))

        boe_token_hits = sum(1 for text in vote_texts_raw if boe_id and boe_id in text.upper())
        doc_boe_token_hits = sum(1 for text in vote_doc_texts_raw if boe_id and boe_id in text.upper())

        title_rule_hits = 0
        for rule_name, terms in TITLE_MATCH_RULES.get(boe_id, []):
            if any(all(term in text for term in terms) for text in vote_texts_folded):
                title_rule_hits += 1
                break

        doc_title_rule_hits = 0
        for _, terms in TITLE_MATCH_RULES.get(boe_id, []):
            if any(all(term in text for term in terms) for text in vote_doc_texts_folded):
                doc_title_rule_hits += 1
                break

        has_vote_title_candidate = (boe_token_hits + title_rule_hits) > 0
        has_vote_doc_candidate = (doc_boe_token_hits + doc_title_rule_hits) > 0

        parliamentary_initiatives = sorted(
            _iter_parliamentary_initiatives_for_responsibility(
                conn, responsibility_id=responsibility_id
            )
        )
        parliamentary_initiatives_with_vote_link = [
            iid for iid in parliamentary_initiatives if iid in vote_linked_inits
        ]

        if has_vote_title_candidate:
            missing_with_title_candidates += 1
        if has_vote_doc_candidate:
            missing_with_doc_candidates += 1
        if parliamentary_initiatives_with_vote_link:
            missing_with_linked_parl_inits += 1

        if has_vote_title_candidate or has_vote_doc_candidate:
            reason = "candidate_present_needs_rule_or_bridge"
        elif parliamentary_initiatives and not parliamentary_initiatives_with_vote_link:
            reason = "no_vote_event_link_for_parliamentary_initiatives"
        elif has_parliamentary:
            reason = "no_vote_corpus_signal"
        else:
            reason = "missing_parliamentary_and_vote_signal"

        missing.append(
            {
                "responsibility_id": responsibility_id,
                "norm_id": _norm(row["norm_id"]),
                "boe_id": boe_id,
                "role": role,
                "has_parliamentary": has_parliamentary,
                "has_vote": False,
                "vote_title_candidates": {
                    "boe_token_hits": boe_token_hits,
                    "title_rule_hits": title_rule_hits,
                    "has_candidate": has_vote_title_candidate,
                },
                "vote_doc_candidates": {
                    "boe_token_hits": doc_boe_token_hits,
                    "title_rule_hits": doc_title_rule_hits,
                    "has_candidate": has_vote_doc_candidate,
                },
                "parliamentary_initiatives": parliamentary_initiatives,
                "parliamentary_initiatives_with_vote_link": parliamentary_initiatives_with_vote_link,
                "diagnosis_reason": reason,
            }
        )
        if boe_id:
            boe_ids_missing.add(boe_id)

    unreachable_missing_total = sum(
        1
        for row in missing
        if row["diagnosis_reason"] in {"no_vote_event_link_for_parliamentary_initiatives", "no_vote_corpus_signal"}
    )

    status = "ok" if not missing else "degraded"
    return {
        "generated_at": _now_utc_iso(),
        "status": status,
        "roles": roles_norm,
        "totals": {
            "vote_link_rows_scanned_total": len(vote_rows),
            "vote_linked_docs_scanned_total": len(vote_docs),
            "responsibilities_missing_vote_total": len(missing),
            "boe_ids_missing_vote_total": len(boe_ids_missing),
            "missing_with_vote_title_candidates_total": missing_with_title_candidates,
            "missing_with_vote_doc_candidates_total": missing_with_doc_candidates,
            "missing_with_parliamentary_initiatives_with_vote_link_total": missing_with_linked_parl_inits,
            "unreachable_missing_total": unreachable_missing_total,
        },
        "checks": {
            "missing_vote_visible": len(missing) > 0,
            "all_missing_have_vote_candidates": len(missing) > 0 and missing_with_title_candidates == len(missing),
            "all_missing_have_vote_doc_candidates": len(missing) > 0 and missing_with_doc_candidates == len(missing),
        },
        "missing_vote_responsibilities": missing,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Diagnose residual sanction-norm vote gaps with explicit candidate/no-new-lever signals"
    )
    ap.add_argument("--db", required=True)
    ap.add_argument("--roles", default="approve,propose,enforce,delegate")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    roles = _parse_roles(args.roles)
    conn = open_db(Path(args.db))
    try:
        report = build_report(conn, roles=roles)
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
