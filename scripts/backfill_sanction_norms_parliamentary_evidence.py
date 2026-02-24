#!/usr/bin/env python3
"""Backfill parliamentary evidence links for sanction norms from initiative documents."""

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

BOE_ID_RE = re.compile(r"BOE-A-\d{4}-\d{1,6}", re.IGNORECASE)
TITLE_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "BOE-A-2000-15060",
        re.compile(
            r"\b(?:texto refundido de la )?ley sobre infracciones y sanciones en el orden social\b",
            re.IGNORECASE,
        ),
        "title_rule:lisos_orden_social",
    ),
)


def now_utc_iso() -> str:
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


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    sid = _norm(source_id)
    if not sid:
        return False
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (sid,)).fetchone()
    return row is not None


def _candidate_evidence_type(initiative_source_id: str) -> str:
    src = _norm(initiative_source_id).lower()
    if src.startswith("congreso_"):
        return "congreso_diario"
    if src.startswith("senado_"):
        return "senado_diario"
    return "other"


def _extract_boe_ids(text: str) -> list[str]:
    values = {m.group(0).upper() for m in BOE_ID_RE.finditer(_norm(text))}
    return sorted(values)


def _extract_quote(text: str, *, boe_id: str, max_chars: int = 240) -> str:
    body = str(text or "")
    if not body:
        return ""
    match = re.search(re.escape(boe_id), body, flags=re.IGNORECASE)
    if match is None:
        return _norm(body[:max_chars])
    center = match.start()
    half = max_chars // 2
    lo = max(0, center - half)
    hi = min(len(body), lo + max_chars)
    return _norm(body[lo:hi])


def _iter_doc_rows(conn: sqlite3.Connection, *, limit: int) -> list[sqlite3.Row]:
    sql = """
        SELECT
          td.text_document_id,
          td.source_id AS text_source_id,
          td.source_url AS text_source_url,
          td.source_record_pk,
          td.text_excerpt,
          sr.source_snapshot_date AS text_source_snapshot_date,
          pid.initiative_id,
          pid.doc_kind,
          pid.doc_url,
          pi.source_id AS initiative_source_id,
          pi.legislature,
          pi.expediente,
          pi.title AS initiative_title,
          pi.presented_date,
          pi.qualified_date
        FROM text_documents td
        LEFT JOIN source_records sr ON sr.source_record_pk = td.source_record_pk
        JOIN parl_initiative_documents pid ON pid.source_record_pk = td.source_record_pk
        JOIN parl_initiatives pi ON pi.initiative_id = pid.initiative_id
        WHERE td.source_id = 'parl_initiative_docs'
        ORDER BY td.text_document_id
    """
    params: list[Any] = []
    if int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    return conn.execute(sql, tuple(params)).fetchall()


def _iter_sanction_norm_boe_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT UPPER(TRIM(COALESCE(n.boe_id, ''))) AS boe_id
        FROM sanction_norm_catalog c
        JOIN legal_norms n ON n.norm_id = c.norm_id
        WHERE TRIM(COALESCE(n.boe_id, '')) <> ''
        """
    ).fetchall()
    return {str(r["boe_id"]) for r in rows if _norm(r["boe_id"])}


def _resolve_responsibilities(
    conn: sqlite3.Connection,
    *,
    boe_id: str,
    roles: list[str],
) -> list[sqlite3.Row]:
    if not roles:
        return []
    placeholders = ",".join(["?"] * len(roles))
    params: list[Any] = [boe_id, *roles]
    sql = f"""
        SELECT
          r.responsibility_id,
          r.role,
          r.fragment_id,
          n.norm_id,
          n.boe_id
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
        WHERE UPPER(TRIM(COALESCE(n.boe_id, ''))) = ?
          AND r.role IN ({placeholders})
        ORDER BY r.responsibility_id
    """
    return conn.execute(sql, tuple(params)).fetchall()


def backfill(
    conn: sqlite3.Connection,
    *,
    roles: list[str],
    limit: int,
) -> dict[str, Any]:
    roles_norm = [r for r in roles if r]
    if not roles_norm:
        raise ValueError("at least one role is required")

    now_iso = now_utc_iso()
    sanction_boe_ids = _iter_sanction_norm_boe_ids(conn)
    doc_rows = _iter_doc_rows(conn, limit=int(limit))

    counts: dict[str, int] = {
        "docs_scanned_total": len(doc_rows),
        "docs_with_boe_token_total": 0,
        "docs_with_title_rule_match_total": 0,
        "candidate_matches_total": 0,
        "candidates_without_responsibility_total": 0,
        "evidence_inserted": 0,
        "evidence_updated": 0,
    }
    by_evidence_type: dict[str, int] = {}
    by_boe_id: dict[str, int] = {}
    by_method: dict[str, int] = {}
    samples: list[dict[str, Any]] = []

    for row in doc_rows:
        excerpt = _norm(row["text_excerpt"])
        boe_ids = _extract_boe_ids(excerpt)
        if boe_ids:
            counts["docs_with_boe_token_total"] += 1

        matched_candidates: list[tuple[str, str]] = []
        seen_boe_ids: set[str] = set()
        for boe_id in boe_ids:
            if boe_id not in sanction_boe_ids:
                continue
            if boe_id in seen_boe_ids:
                continue
            matched_candidates.append((boe_id, "text_excerpt_boe_id_regex"))
            seen_boe_ids.add(boe_id)

        title_rule_hit = False
        for boe_id, title_re, method in TITLE_RULES:
            if boe_id in seen_boe_ids:
                continue
            if boe_id not in sanction_boe_ids:
                continue
            if title_re.search(excerpt) is None:
                continue
            matched_candidates.append((boe_id, method))
            seen_boe_ids.add(boe_id)
            title_rule_hit = True
        if title_rule_hit:
            counts["docs_with_title_rule_match_total"] += 1

        if not matched_candidates:
            continue

        for boe_id, match_method in matched_candidates:
            counts["candidate_matches_total"] += 1
            by_boe_id[boe_id] = int(by_boe_id.get(boe_id, 0)) + 1
            by_method[match_method] = int(by_method.get(match_method, 0)) + 1

            responsibilities = _resolve_responsibilities(conn, boe_id=boe_id, roles=roles_norm)
            if not responsibilities:
                counts["candidates_without_responsibility_total"] += 1
                if len(samples) < 20:
                    samples.append(
                        {
                            "boe_id": boe_id,
                            "initiative_id": _norm(row["initiative_id"]),
                            "match_method": match_method,
                            "reason": "no_matching_responsibility_for_roles",
                            "roles": roles_norm,
                        }
                    )
                continue

            evidence_type = _candidate_evidence_type(_norm(row["initiative_source_id"]))
            by_evidence_type[evidence_type] = int(by_evidence_type.get(evidence_type, 0)) + len(responsibilities)

            src_for_fk = _norm(row["initiative_source_id"])
            if not _source_exists(conn, src_for_fk):
                src_for_fk = _norm(row["text_source_id"])
            if not _source_exists(conn, src_for_fk):
                src_for_fk = ""

            source_url = _norm(row["text_source_url"]) or _norm(row["doc_url"])
            evidence_date = (
                _norm(row["presented_date"])
                or _norm(row["qualified_date"])
                or _norm(row["text_source_snapshot_date"])
                or now_iso[:10]
            )
            evidence_quote = _extract_quote(excerpt, boe_id=boe_id)

            for resp in responsibilities:
                responsibility_id = int(resp["responsibility_id"])
                exists = conn.execute(
                    """
                    SELECT responsibility_evidence_id
                    FROM legal_fragment_responsibility_evidence
                    WHERE responsibility_id = ?
                      AND evidence_type = ?
                      AND COALESCE(source_url, '') = ?
                      AND COALESCE(evidence_date, '') = ?
                    """,
                    (responsibility_id, evidence_type, source_url, evidence_date),
                ).fetchone()
                if exists is None and evidence_date:
                    exists = conn.execute(
                        """
                        SELECT responsibility_evidence_id
                        FROM legal_fragment_responsibility_evidence
                        WHERE responsibility_id = ?
                          AND evidence_type = ?
                          AND COALESCE(source_url, '') = ?
                          AND COALESCE(evidence_date, '') = ''
                        """,
                        (responsibility_id, evidence_type, source_url),
                    ).fetchone()

                payload = {
                    "record_kind": "sanction_norm_parliamentary_evidence_backfill",
                    "match_method": match_method,
                    "boe_id": boe_id,
                    "norm_id": _norm(resp["norm_id"]),
                    "responsibility_id": responsibility_id,
                    "role": _norm(resp["role"]),
                    "initiative_id": _norm(row["initiative_id"]),
                    "initiative_source_id": _norm(row["initiative_source_id"]),
                    "initiative_title": _norm(row["initiative_title"]),
                    "initiative_expediente": _norm(row["expediente"]),
                    "initiative_legislature": _norm(row["legislature"]),
                    "doc_kind": _norm(row["doc_kind"]),
                    "doc_url": _norm(row["doc_url"]),
                    "text_document_id": int(row["text_document_id"]),
                    "text_source_record_pk": int(row["source_record_pk"]) if row["source_record_pk"] is not None else None,
                }
                raw_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)

                if exists is None:
                    conn.execute(
                        """
                        INSERT INTO legal_fragment_responsibility_evidence (
                          responsibility_id,
                          evidence_type,
                          source_id,
                          source_url,
                          source_record_pk,
                          evidence_date,
                          evidence_quote,
                          raw_payload,
                          created_at,
                          updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            responsibility_id,
                            evidence_type,
                            src_for_fk or None,
                            source_url or None,
                            int(row["source_record_pk"]) if row["source_record_pk"] is not None else None,
                            evidence_date or None,
                            evidence_quote or None,
                            raw_payload,
                            now_iso,
                            now_iso,
                        ),
                    )
                    counts["evidence_inserted"] += 1
                else:
                    conn.execute(
                        """
                        UPDATE legal_fragment_responsibility_evidence
                        SET
                          source_id = ?,
                          source_url = ?,
                          source_record_pk = ?,
                          evidence_date = ?,
                          evidence_quote = ?,
                          raw_payload = ?,
                          updated_at = ?
                        WHERE responsibility_evidence_id = ?
                        """,
                        (
                            src_for_fk or None,
                            source_url or None,
                            int(row["source_record_pk"]) if row["source_record_pk"] is not None else None,
                            evidence_date or None,
                            evidence_quote or None,
                            raw_payload,
                            now_iso,
                            int(exists["responsibility_evidence_id"]),
                        ),
                    )
                    counts["evidence_updated"] += 1

                if len(samples) < 20:
                    samples.append(
                        {
                            "boe_id": boe_id,
                            "norm_id": _norm(resp["norm_id"]),
                            "responsibility_id": responsibility_id,
                            "role": _norm(resp["role"]),
                            "initiative_id": _norm(row["initiative_id"]),
                            "evidence_type": evidence_type,
                            "match_method": match_method,
                            "source_url": source_url,
                            "evidence_date": evidence_date,
                        }
                    )

    conn.commit()
    return {
        "generated_at": now_iso,
        "roles": roles_norm,
        "limit": int(limit),
        "counts": counts,
        "by_evidence_type": by_evidence_type,
        "by_boe_id": by_boe_id,
        "by_method": by_method,
        "samples": samples,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Backfill parliamentary evidence for sanction responsibilities from initiative docs"
    )
    ap.add_argument("--db", required=True)
    ap.add_argument("--roles", default="approve,propose")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    roles = _parse_roles(args.roles)
    conn = open_db(Path(args.db))
    try:
        report = backfill(conn, roles=roles, limit=int(args.limit))
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
