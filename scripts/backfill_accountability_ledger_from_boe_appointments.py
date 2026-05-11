#!/usr/bin/env python3
"""Backfill appointment/dismissal accountability rows from BOE policy event titles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso
from scripts.accountability_evidence_tiers import infer_accountability_evidence_tier


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
APPOINTMENT_RE = re.compile(
    r"\b(?:se\s+nombra|nombramiento\s+de|nombrar\s+a)\s+(?:a\s+)?(?:don|doña|d\.|dña\.)?\s*(?P<name>.+?)(?:[,.;]|$)",
    re.IGNORECASE,
)
APPOINTMENT_ROLE_THEN_NAME_RE = re.compile(
    r"\bse\s+nombra\s+(?P<role>.+?)\s+a(?:l| la)?\s+(?P<name>.+?)(?:[,.;]|$)",
    re.IGNORECASE,
)
DISMISSAL_RE = re.compile(
    r"\b(?:se\s+dispone\s+el\s+cese\s+de(?:l| la)?|se\s+cesa\s+a|cese\s+de(?:l| la)?)\s+"
    r"(?:don|doña|d\.|dña\.)?\s*(?P<name>.+?)(?:[,.;]|$)",
    re.IGNORECASE,
)
ROLE_AFTER_NAME_RE = re.compile(r"\s+(?:como|en\s+el\s+cargo\s+de|en\s+la\s+condicion\s+de)\s+.+$", re.IGNORECASE)
ROLE_SPLIT_RE = re.compile(
    r"\s+(?:como|en\s+el\s+cargo\s+de|en\s+la\s+condicion\s+de)\s+",
    re.IGNORECASE,
)
HONORIFIC_NAME_TAIL_RE = re.compile(r"(?:^|\s)(?:don|doña|d\.|dña\.)\s+(?P<name>.+)$", re.IGNORECASE)
POLITICAL_APPOINTEE_ROLE_TERMS = (
    "director general",
    "directora general",
    "secretario de estado",
    "secretaria de estado",
    "subsecretario",
    "subsecretaria",
    "delegado del gobierno",
    "delegada del gobierno",
    "alto comisionado",
    "alta comisionada",
    "presidente",
    "presidenta",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill accountability ledger from BOE appointment/dismissal titles")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-ids", nargs="*", default=["boe_api_legal"], help="BOE policy_events source_id filter")
    p.add_argument("--limit", type=int, default=0, help="Optional max BOE policy events to scan")
    p.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _clean_person_name(value: str) -> str:
    cleaned = ROLE_AFTER_NAME_RE.sub("", value)
    cleaned = re.sub(r"\s+(?:y\s+otros|y\s+otras)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = normalize_ws(cleaned.strip(" .,:;"))
    honorific_matches = list(HONORIFIC_NAME_TAIL_RE.finditer(cleaned))
    if honorific_matches:
        cleaned = normalize_ws(honorific_matches[-1].group("name").strip(" .,:;"))
    return cleaned


def _split_name_and_role(value: str) -> tuple[str, str]:
    token = normalize_ws(value.strip(" .,:;"))
    parts = ROLE_SPLIT_RE.split(token, maxsplit=1)
    if len(parts) != 2:
        return _clean_person_name(token), ""
    return _clean_person_name(parts[0]), normalize_ws(parts[1].strip(" .,:;"))


def _position_kind(role_title: str) -> str:
    role_key = normalize_key_part(role_title)
    if any(term in role_key for term in POLITICAL_APPOINTEE_ROLE_TERMS):
        return "political_appointee"
    return "unknown"


def _appointment_signal(title: str) -> dict[str, str] | None:
    title_key = normalize_key_part(title)
    if not title_key:
        return None
    dismissed = DISMISSAL_RE.search(title)
    if dismissed:
        name, role_title = _split_name_and_role(dismissed.group("name"))
        if name:
            return {"role": "dismissed", "kind": "dismissal", "name": name, "role_title": role_title}
    appointed_role_then_name = APPOINTMENT_ROLE_THEN_NAME_RE.search(title)
    if appointed_role_then_name:
        name = _clean_person_name(appointed_role_then_name.group("name"))
        role_title = normalize_ws(appointed_role_then_name.group("role").strip(" .,:;"))
        if name:
            return {"role": "appointed", "kind": "appointment", "name": name, "role_title": role_title}
    appointed = APPOINTMENT_RE.search(title)
    if appointed:
        name, role_title = _split_name_and_role(appointed.group("name"))
        if name:
            return {"role": "appointed", "kind": "appointment", "name": name, "role_title": role_title}
    if any(token in title_key for token in ("nombramiento", "se nombra", "nombrar a")):
        return {"role": "appointed", "kind": "appointment", "name": "", "role_title": ""}
    if any(token in title_key for token in ("cese de", "se cesa", "dispone el cese")):
        return {"role": "dismissed", "kind": "dismissal", "name": "", "role_title": ""}
    return None


def _get_or_create_person_stub(conn: Any, *, name: str, row: Any, now_iso: str) -> tuple[int | None, bool, bool]:
    name_norm = _norm(name)
    canonical_key = normalize_key_part(name_norm)
    if not canonical_key:
        return None, False, False
    found = conn.execute(
        "SELECT person_id FROM persons WHERE canonical_key = ?",
        (canonical_key,),
    ).fetchone()
    person_created = False
    if found is None:
        conn.execute(
            """
            INSERT INTO persons (
              full_name, territory_code, canonical_key, created_at, updated_at
            ) VALUES (?, '', ?, ?, ?)
            """,
            (name_norm, canonical_key, now_iso, now_iso),
        )
        person_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        person_created = True
    else:
        person_id = int(found["person_id"])

    alias_created = False
    alias_found = conn.execute(
        "SELECT person_name_alias_id FROM person_name_aliases WHERE canonical_alias = ?",
        (canonical_key,),
    ).fetchone()
    if alias_found is None:
        conn.execute(
            """
            INSERT INTO person_name_aliases (
              person_id, alias, canonical_alias, source_id, source_record_pk, source_kind,
              source_url, evidence_date, evidence_quote, confidence, note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'official_boe_appointment_title', ?, ?, ?, 0.75, ?, ?, ?)
            """,
            (
                person_id,
                name_norm,
                canonical_key,
                row["source_id"],
                row["source_record_pk"],
                _norm(row["source_url"]),
                _norm(row["published_date"]),
                _norm(row["title"]),
                "Conservative exact-name alias from BOE appointment/dismissal title.",
                now_iso,
                now_iso,
            ),
        )
        alias_created = True
    return person_id, person_created, alias_created


def _get_or_create_position(
    conn: Any,
    *,
    role_title: str,
    row: Any,
    now_iso: str,
) -> tuple[int | None, bool]:
    title = _norm(role_title)
    if not title:
        return None, False
    kind = _position_kind(title)
    position_code = normalize_key_part(title)
    found = conn.execute(
        """
        SELECT position_id
        FROM government_positions
        WHERE org_unit_id IS NULL
          AND title = ?
          AND position_kind = ?
          AND COALESCE(position_code, '') = ?
        ORDER BY position_id ASC
        LIMIT 1
        """,
        (title, kind, position_code),
    ).fetchone()
    if found is not None:
        return int(found["position_id"]), False
    conn.execute(
        """
        INSERT INTO government_positions (
          org_unit_id, source_id, source_record_pk, position_code, title,
          position_kind, is_top_responsible, source_url, raw_payload, created_at, updated_at
        ) VALUES (NULL, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """,
        (
            row["source_id"],
            row["source_record_pk"],
            position_code,
            title,
            kind,
            _norm(row["source_url"]),
            _stable_json({"source": "boe_appointment_title_backfill", "policy_event_id": row["policy_event_id"]}),
            now_iso,
            now_iso,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0]), True


def _upsert_person_position_membership(
    conn: Any,
    *,
    person_id: int | None,
    position_id: int | None,
    role_title: str,
    signal: dict[str, str],
    row: Any,
    now_iso: str,
) -> bool:
    if person_id is None:
        return False
    role_label = _norm(role_title) or signal["kind"]
    start_date = _norm(row["published_date"]) if signal["kind"] == "appointment" else ""
    end_date = _norm(row["published_date"]) if signal["kind"] == "dismissal" else ""
    existing = conn.execute(
        """
        SELECT membership_id
        FROM person_org_memberships
        WHERE person_id = ?
          AND membership_kind = 'public_position'
          AND COALESCE(position_id, -1) = COALESCE(?, -1)
          AND role_label = ?
          AND COALESCE(start_date, '') = ?
          AND COALESCE(end_date, '') = ?
          AND source_url = ?
        LIMIT 1
        """,
        (person_id, position_id, role_label, start_date, end_date, _norm(row["source_url"])),
    ).fetchone()
    if existing is not None:
        return False
    conn.execute(
        """
        INSERT INTO person_org_memberships (
          person_id, membership_kind, org_unit_id, party_id, position_id, role_label,
          start_date, end_date, source_id, source_record_pk, source_kind, source_url,
          evidence_date, evidence_quote, raw_payload, created_at, updated_at
        ) VALUES (
          ?, 'public_position', NULL, NULL, ?, ?, ?, ?, ?, ?, 'official_boe_appointment_title',
          ?, ?, ?, ?, ?, ?
        )
        """,
        (
            person_id,
            position_id,
            role_label,
            start_date or None,
            end_date or None,
            row["source_id"],
            row["source_record_pk"],
            _norm(row["source_url"]),
            _norm(row["published_date"]),
            _norm(row["title"]),
            _stable_json(
                {
                    "source": "boe_appointment_title_backfill",
                    "policy_event_id": row["policy_event_id"],
                    "appointment_kind": signal["kind"],
                    "role_title": role_label,
                }
            ),
            now_iso,
            now_iso,
        ),
    )
    return True


def _upsert_issue(conn: Any, *, row: Any, signal: dict[str, str], now_iso: str) -> str:
    issue_id = f"boe-appointment:{row['policy_event_id']}"
    label = _norm(row["title"]) or _norm(row["policy_event_id"])
    conn.execute(
        """
        INSERT INTO accountability_issues (
          issue_id,
          case_id,
          canonical_key,
          label,
          summary,
          scope,
          domain_id,
          topic_id,
          issue_status,
          source_kind,
          raw_payload_json,
          created_at,
          updated_at
        ) VALUES (?, NULL, ?, ?, ?, 'nacional', ?, NULL, 'active', 'derived', ?, ?, ?)
        ON CONFLICT(issue_id) DO UPDATE SET
          canonical_key = excluded.canonical_key,
          label = excluded.label,
          summary = excluded.summary,
          scope = excluded.scope,
          domain_id = excluded.domain_id,
          source_kind = excluded.source_kind,
          raw_payload_json = excluded.raw_payload_json,
          updated_at = excluded.updated_at
        """,
        (
            issue_id,
            issue_id,
            label,
            f"BOE {signal['kind']} event.",
            row["domain_id"],
            _stable_json({"source": "boe_appointment_title_backfill", "policy_event_id": row["policy_event_id"]}),
            now_iso,
            now_iso,
        ),
    )
    return issue_id


def backfill_boe_appointment_accountability_ledger(
    conn: Any,
    *,
    source_ids: tuple[str, ...] = ("boe_api_legal",),
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not source_ids:
        raise ValueError("source_ids cannot be empty")
    placeholders = ",".join("?" for _ in source_ids)
    params: list[Any] = list(source_ids)
    limit_sql = "LIMIT ?" if int(limit or 0) > 0 else ""
    if int(limit or 0) > 0:
        params.append(int(limit))
    rows = conn.execute(
        f"""
        SELECT
          pe.policy_event_id,
          pe.published_date,
          pe.domain_id,
          pe.title,
          pe.summary,
          pe.source_id,
          pe.source_url,
          pe.source_record_pk,
          pe.source_snapshot_date
        FROM policy_events pe
        LEFT JOIN policy_instruments pi ON pi.policy_instrument_id = pe.policy_instrument_id
        WHERE pe.source_id IN ({placeholders})
          AND (
            pi.code = 'boe_legal_document'
            OR pe.source_id LIKE 'boe_%'
          )
        ORDER BY COALESCE(pe.published_date, ''), pe.policy_event_id
        {limit_sql}
        """,
        tuple(params),
    ).fetchall()
    stats: dict[str, Any] = {
        "source_ids": list(source_ids),
        "source_rows_seen": len(rows),
        "appointment_candidates": 0,
        "issues_upserted": 0,
        "entries_upserted": 0,
        "signals_with_role_title": 0,
        "persons_upserted": 0,
        "person_aliases_upserted": 0,
        "positions_upserted": 0,
        "memberships_upserted": 0,
        "entries_by_role": {},
        "dry_run": bool(dry_run),
    }
    signals: list[tuple[Any, dict[str, str]]] = []
    for row in rows:
        signal = _appointment_signal(_norm(row["title"]))
        if signal is None:
            continue
        stats["appointment_candidates"] += 1
        if signal.get("role_title"):
            stats["signals_with_role_title"] += 1
        stats["entries_by_role"][signal["role"]] = int(stats["entries_by_role"].get(signal["role"], 0)) + 1
        signals.append((row, signal))
    if dry_run:
        return stats

    now_iso = now_utc_iso()
    with conn:
        for row, signal in signals:
            issue_id = _upsert_issue(conn, row=row, signal=signal, now_iso=now_iso)
            actor_label = signal["name"] or "Unknown appointed actor"
            person_id: int | None = None
            position_id: int | None = None
            if signal["name"]:
                person_id, person_created, alias_created = _get_or_create_person_stub(
                    conn,
                    name=signal["name"],
                    row=row,
                    now_iso=now_iso,
                )
                if person_created:
                    stats["persons_upserted"] += 1
                if alias_created:
                    stats["person_aliases_upserted"] += 1
            if signal.get("role_title"):
                position_id, position_created = _get_or_create_position(
                    conn,
                    role_title=signal["role_title"],
                    row=row,
                    now_iso=now_iso,
                )
                if position_created:
                    stats["positions_upserted"] += 1
            if _upsert_person_position_membership(
                conn,
                person_id=person_id,
                position_id=position_id,
                role_title=signal.get("role_title", ""),
                signal=signal,
                row=row,
                now_iso=now_iso,
            ):
                stats["memberships_upserted"] += 1

            source_title = "BOE appointment/dismissal title"
            evidence_tier = infer_accountability_evidence_tier(
                source_id=_norm(row["source_id"]),
                source_url=_norm(row["source_url"]),
                source_title=source_title,
                instrument_code="boe_legal_document",
            )
            payload = {
                "source": "boe_appointment_title_backfill",
                "policy_event_id": row["policy_event_id"],
                "appointment_kind": signal["kind"],
                "extracted_name": signal["name"],
                "extracted_role_title": signal.get("role_title", ""),
            }
            conn.execute(
                """
                INSERT INTO accountability_ledger_entries (
                  entry_id,
                  issue_id,
                  entry_kind,
                  accountability_role,
                  role_in_chain,
                  actor_label,
                  actor_kind,
                  person_id,
                  party_id,
                  mandate_id,
                  institution_id,
                  org_unit_id,
                  position_id,
                  linked_object_type,
                  linked_object_id,
                  policy_event_id,
                  topic_evidence_id,
                  legal_fragment_id,
                  event_date,
                  published_date,
                  title,
                  summary,
                  accountability_question,
                  confidence,
                  evidence_tier,
                  source_id,
                  source_title,
                  source_url,
                  source_locator,
                  source_record_pk,
                  evidence_quote,
                  raw_payload_json,
                  created_at,
                  updated_at
                ) VALUES (
                  ?, ?, 'appointment', ?, ?, ?, ?,
                  ?, NULL, NULL, NULL, NULL, ?,
                  'policy_event', ?, ?, NULL, NULL,
                  NULL, ?, ?, ?, ?, 0.75, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(entry_id) DO UPDATE SET
                  issue_id = excluded.issue_id,
                  entry_kind = excluded.entry_kind,
                  accountability_role = excluded.accountability_role,
                  role_in_chain = excluded.role_in_chain,
                  actor_label = excluded.actor_label,
                  actor_kind = excluded.actor_kind,
                  person_id = excluded.person_id,
                  position_id = excluded.position_id,
                  linked_object_type = excluded.linked_object_type,
                  linked_object_id = excluded.linked_object_id,
                  policy_event_id = excluded.policy_event_id,
                  published_date = excluded.published_date,
                  title = excluded.title,
                  summary = excluded.summary,
                  accountability_question = excluded.accountability_question,
                  confidence = excluded.confidence,
                  evidence_tier = excluded.evidence_tier,
                  source_id = excluded.source_id,
                  source_title = excluded.source_title,
                  source_url = excluded.source_url,
                  source_locator = excluded.source_locator,
                  source_record_pk = excluded.source_record_pk,
                  evidence_quote = excluded.evidence_quote,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                (
                    f"boe-appointment:{row['policy_event_id']}",
                    issue_id,
                    signal["role"],
                    signal["kind"],
                    actor_label,
                    "person" if person_id is not None or signal["name"] else "unknown",
                    person_id,
                    position_id,
                    row["policy_event_id"],
                    row["policy_event_id"],
                    row["published_date"],
                    _norm(row["title"]),
                    _norm(row["summary"]),
                    "Who was appointed or dismissed by this BOE act?",
                    evidence_tier,
                    row["source_id"],
                    source_title,
                    _norm(row["source_url"]),
                    _norm(row["policy_event_id"]),
                    row["source_record_pk"],
                    _norm(row["title"]),
                    _stable_json(payload),
                    now_iso,
                    now_iso,
                ),
            )
            stats["issues_upserted"] += 1
            stats["entries_upserted"] += 1
    return stats


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_boe_appointment_accountability_ledger(
            conn,
            source_ids=tuple(str(item) for item in args.source_ids),
            limit=int(args.limit or 0),
            dry_run=bool(args.dry_run),
        )
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(
        "OK BOE appointment accountability ledger "
        + f"(seen={summary['source_rows_seen']} candidates={summary['appointment_candidates']} "
        + f"entries={summary['entries_upserted']} dry_run={summary['dry_run']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
