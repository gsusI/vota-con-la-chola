#!/usr/bin/env python3
"""Exporta un directorio estático de perfiles de personas para Next.js GH Pages."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/gh-pages/people/data/profiles.json")
DATE_RE = re.compile(r"^[1-2][0-9]{3}-[01][0-9]-[0-3][0-9]")
BUCKET_ORDER = [chr(code) for code in range(ord("A"), ord("Z") + 1)] + ["0-9", "OTROS"]

COLUMNS = [
    "person_id",
    "full_name",
    "canonical_key",
    "birth_date",
    "gender_label",
    "territory_name",
    "territory_code",
    "mandates_total",
    "active_mandates",
    "institutions_total",
    "parties_total",
    "votes_total",
    "vote_events_total",
    "declared_evidence_total",
    "revealed_vote_evidence_total",
    "topic_positions_total",
    "aliases_total",
    "identifiers_total",
    "first_mandate_start",
    "last_mandate_date",
    "last_vote_date",
    "last_evidence_date",
    "last_action_date",
    "roles_ever",
    "institutions_ever",
    "parties_ever",
    "positions_ever_json",
    "queue_pending_total",
    "queue_in_progress_total",
    "queue_priority_max",
    "queue_gap_codes",
    "queue_next_actions",
]
FULL_NAME_COL_INDEX = COLUMNS.index("full_name")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta perfiles de personas para /people en GH Pages")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la base SQLite")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Ruta de salida del manifiesto JSON")
    p.add_argument("--snapshot-date", default="", help="Fecha snapshot (YYYY-MM-DD); si no, se infiere")
    p.add_argument(
        "--max-list-values",
        type=int,
        default=8,
        help="Máximo de valores en listas por persona (roles, instituciones, partidos, gaps)",
    )
    p.add_argument(
        "--max-positions",
        type=int,
        default=10,
        help="Máximo de posiciones históricas por persona",
    )
    p.add_argument(
        "--top-rows",
        type=int,
        default=1200,
        help="Filas incluidas en el archivo top para carga inicial",
    )
    p.add_argument(
        "--include-party-proxies",
        action="store_true",
        help="Incluye personas canónicas party:* en el directorio",
    )
    return p.parse_args()


def norm(value: Any) -> str:
    return str(value or "").strip()


def as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_valid_date(value: Any) -> bool:
    return bool(DATE_RE.match(norm(value)))


def max_date(*values: Any) -> str:
    valid = [norm(v) for v in values if is_valid_date(v)]
    return max(valid) if valid else ""


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def infer_snapshot_date(conn: sqlite3.Connection) -> str:
    candidates = [
        conn.execute(
            """
            SELECT MAX(source_snapshot_date)
            FROM mandates
            WHERE source_snapshot_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'
            """
        ).fetchone()[0],
        conn.execute(
            """
            SELECT MAX(source_snapshot_date)
            FROM parl_vote_events
            WHERE source_snapshot_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'
            """
        ).fetchone()[0],
        conn.execute(
            """
            SELECT MAX(source_snapshot_date)
            FROM topic_evidence
            WHERE source_snapshot_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'
            """
        ).fetchone()[0],
    ]
    valid = [norm(v) for v in candidates if is_valid_date(v)]
    if valid:
        return max(valid)
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def csv_to_values(value: Any, *, max_values: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in norm(value).split(","):
        token = norm(raw)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
        if max_values > 0 and len(out) >= max_values:
            break
    return out


def append_unique(target: list[str], seen: set[str], value: Any, *, max_values: int) -> None:
    token = norm(value)
    if not token or token in seen:
        return
    if max_values > 0 and len(target) >= max_values:
        return
    seen.add(token)
    target.append(token)


def normalize_bucket_text(value: Any) -> str:
    text = norm(value)
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return plain.upper()


def bucket_for_name(full_name: Any) -> str:
    normalized = normalize_bucket_text(full_name)
    for ch in normalized:
        if "A" <= ch <= "Z":
            return ch
        if ch.isdigit():
            return "0-9"
    return "OTROS"


def bucket_slug(bucket: str) -> str:
    if bucket == "0-9":
        return "0-9"
    if bucket == "OTROS":
        return "otros"
    return bucket.lower()


def bucket_sort_key(bucket: str) -> tuple[int, str]:
    try:
        return (0, str(BUCKET_ORDER.index(bucket)).zfill(3))
    except ValueError:
        return (1, bucket)


def build_positions_by_person(
    conn: sqlite3.Connection,
    *,
    include_party_proxies: bool,
    max_list_values: int,
    max_positions: int,
) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          m.person_id,
          COALESCE(r.title, m.role_title, '') AS role_title,
          COALESCE(i.name, '') AS institution_name,
          COALESCE(pa.acronym, pa.name, '') AS party_name,
          COALESCE(al.label, m.level, '') AS admin_level,
          COALESCE(tt.name, m.territory_code, '') AS territory_name,
          MIN(CASE WHEN m.start_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN m.start_date END) AS first_start_date,
          MAX(CASE WHEN COALESCE(m.end_date, m.start_date) GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN COALESCE(m.end_date, m.start_date) END) AS last_end_date,
          MAX(m.is_active) AS currently_active,
          COUNT(*) AS source_rows
        FROM mandates m
        JOIN persons p ON p.person_id = m.person_id
        LEFT JOIN roles r ON r.role_id = m.role_id
        LEFT JOIN institutions i ON i.institution_id = m.institution_id
        LEFT JOIN parties pa ON pa.party_id = m.party_id
        LEFT JOIN admin_levels al ON al.admin_level_id = m.admin_level_id
        LEFT JOIN territories tt ON tt.territory_id = m.territory_id
        WHERE (? = 1 OR p.canonical_key NOT LIKE 'party:%')
        GROUP BY
          m.person_id,
          COALESCE(r.title, m.role_title, ''),
          COALESCE(i.name, ''),
          COALESCE(pa.acronym, pa.name, ''),
          COALESCE(al.label, m.level, ''),
          COALESCE(tt.name, m.territory_code, '')
        ORDER BY
          m.person_id ASC,
          currently_active DESC,
          last_end_date DESC,
          first_start_date DESC,
          role_title ASC,
          institution_name ASC
        """,
        (1 if include_party_proxies else 0,),
    ).fetchall()

    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        person_id = as_int(row["person_id"])
        if person_id <= 0:
            continue

        bucket = out.get(person_id)
        if bucket is None:
            bucket = {
                "roles": [],
                "roles_seen": set(),
                "institutions": [],
                "institutions_seen": set(),
                "parties": [],
                "parties_seen": set(),
                "positions": [],
            }
            out[person_id] = bucket

        append_unique(
            bucket["roles"],
            bucket["roles_seen"],
            row["role_title"],
            max_values=max_list_values,
        )
        append_unique(
            bucket["institutions"],
            bucket["institutions_seen"],
            row["institution_name"],
            max_values=max_list_values,
        )
        append_unique(
            bucket["parties"],
            bucket["parties_seen"],
            row["party_name"],
            max_values=max_list_values,
        )

        if max_positions <= 0 or len(bucket["positions"]) < max_positions:
            bucket["positions"].append(
                {
                    "role_title": norm(row["role_title"]),
                    "institution_name": norm(row["institution_name"]),
                    "party": norm(row["party_name"]),
                    "admin_level": norm(row["admin_level"]),
                    "territory_name": norm(row["territory_name"]),
                    "first_start_date": norm(row["first_start_date"]),
                    "last_end_date": norm(row["last_end_date"]),
                    "currently_active": as_int(row["currently_active"]),
                    "source_rows": as_int(row["source_rows"]),
                }
            )

    for bucket in out.values():
        bucket.pop("roles_seen", None)
        bucket.pop("institutions_seen", None)
        bucket.pop("parties_seen", None)

    return out


def fetch_people_rows(
    conn: sqlite3.Connection,
    *,
    include_party_proxies: bool,
    has_queue: bool,
) -> list[sqlite3.Row]:
    queue_cte = (
        """
        queue_agg AS (
          SELECT
            person_id,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS queue_pending_total,
            SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS queue_in_progress_total,
            MAX(CASE WHEN status IN ('pending', 'in_progress') THEN priority ELSE NULL END) AS queue_priority_max,
            GROUP_CONCAT(DISTINCT CASE WHEN status IN ('pending', 'in_progress') THEN gap_code END) AS queue_gap_codes_csv,
            GROUP_CONCAT(DISTINCT CASE WHEN status IN ('pending', 'in_progress') THEN next_action END) AS queue_next_actions_csv
          FROM person_public_data_queue
          GROUP BY person_id
        )
        """
        if has_queue
        else """
        queue_agg AS (
          SELECT
            NULL AS person_id,
            0 AS queue_pending_total,
            0 AS queue_in_progress_total,
            NULL AS queue_priority_max,
            '' AS queue_gap_codes_csv,
            '' AS queue_next_actions_csv
          WHERE 0
        )
        """
    )

    sql = f"""
    WITH
    mandate_agg AS (
      SELECT
        person_id,
        COUNT(*) AS mandates_total,
        SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_mandates,
        COUNT(DISTINCT institution_id) AS institutions_total,
        COUNT(DISTINCT party_id) AS parties_total,
        MIN(CASE WHEN start_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN start_date END) AS first_mandate_start,
        MAX(CASE WHEN COALESCE(end_date, start_date) GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN COALESCE(end_date, start_date) END) AS last_mandate_date
      FROM mandates
      GROUP BY person_id
    ),
    vote_agg AS (
      SELECT
        mv.person_id,
        COUNT(*) AS votes_total,
        COUNT(DISTINCT mv.vote_event_id) AS vote_events_total,
        MAX(CASE WHEN e.vote_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN e.vote_date END) AS last_vote_date
      FROM parl_vote_member_votes mv
      LEFT JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
      WHERE mv.person_id IS NOT NULL
      GROUP BY mv.person_id
    ),
    evidence_agg AS (
      SELECT
        person_id,
        SUM(CASE WHEN evidence_type LIKE 'declared:%' THEN 1 ELSE 0 END) AS declared_evidence_total,
        SUM(CASE WHEN evidence_type = 'revealed:vote' THEN 1 ELSE 0 END) AS revealed_vote_evidence_total,
        MAX(CASE WHEN evidence_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN evidence_date END) AS last_evidence_date
      FROM topic_evidence
      GROUP BY person_id
    ),
    position_agg AS (
      SELECT
        person_id,
        COUNT(*) AS topic_positions_total
      FROM topic_positions
      GROUP BY person_id
    ),
    alias_agg AS (
      SELECT person_id, COUNT(*) AS aliases_total
      FROM person_name_aliases
      GROUP BY person_id
    ),
    id_agg AS (
      SELECT person_id, COUNT(*) AS identifiers_total
      FROM person_identifiers
      GROUP BY person_id
    ),
    {queue_cte}
    SELECT
      p.person_id,
      p.full_name,
      p.canonical_key,
      p.birth_date,
      COALESCE(NULLIF(g.label, ''), NULLIF(p.gender, ''), '') AS gender_label,
      COALESCE(tt.name, '') AS territory_name,
      p.territory_code,
      COALESCE(ma.mandates_total, 0) AS mandates_total,
      COALESCE(ma.active_mandates, 0) AS active_mandates,
      COALESCE(ma.institutions_total, 0) AS institutions_total,
      COALESCE(ma.parties_total, 0) AS parties_total,
      COALESCE(va.votes_total, 0) AS votes_total,
      COALESCE(va.vote_events_total, 0) AS vote_events_total,
      COALESCE(ea.declared_evidence_total, 0) AS declared_evidence_total,
      COALESCE(ea.revealed_vote_evidence_total, 0) AS revealed_vote_evidence_total,
      COALESCE(pa.topic_positions_total, 0) AS topic_positions_total,
      COALESCE(aa.aliases_total, 0) AS aliases_total,
      COALESCE(ia.identifiers_total, 0) AS identifiers_total,
      ma.first_mandate_start,
      ma.last_mandate_date,
      va.last_vote_date,
      ea.last_evidence_date,
      COALESCE(qa.queue_pending_total, 0) AS queue_pending_total,
      COALESCE(qa.queue_in_progress_total, 0) AS queue_in_progress_total,
      COALESCE(qa.queue_priority_max, 0) AS queue_priority_max,
      COALESCE(qa.queue_gap_codes_csv, '') AS queue_gap_codes_csv,
      COALESCE(qa.queue_next_actions_csv, '') AS queue_next_actions_csv
    FROM persons p
    LEFT JOIN genders g ON g.gender_id = p.gender_id
    LEFT JOIN territories tt ON tt.territory_id = p.territory_id
    LEFT JOIN mandate_agg ma ON ma.person_id = p.person_id
    LEFT JOIN vote_agg va ON va.person_id = p.person_id
    LEFT JOIN evidence_agg ea ON ea.person_id = p.person_id
    LEFT JOIN position_agg pa ON pa.person_id = p.person_id
    LEFT JOIN alias_agg aa ON aa.person_id = p.person_id
    LEFT JOIN id_agg ia ON ia.person_id = p.person_id
    LEFT JOIN queue_agg qa ON qa.person_id = p.person_id
    WHERE (? = 1 OR p.canonical_key NOT LIKE 'party:%')
    ORDER BY
      COALESCE(ma.active_mandates, 0) DESC,
      COALESCE(va.votes_total, 0) DESC,
      p.full_name ASC,
      p.person_id ASC
    """

    return conn.execute(sql, (1 if include_party_proxies else 0,)).fetchall()


def write_payload(path: Path, payload: dict[str, Any]) -> int:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(encoded, encoding="utf-8")
    return len(encoded.encode("utf-8"))


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    manifest_path = Path(args.out)

    if not db_path.exists():
        print(f"ERROR: no existe el DB -> {db_path}")
        return 2

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        has_queue = table_exists(conn, "person_public_data_queue")
        snapshot_date = norm(args.snapshot_date) or infer_snapshot_date(conn)
        people_rows = fetch_people_rows(
            conn,
            include_party_proxies=bool(args.include_party_proxies),
            has_queue=has_queue,
        )
        positions_by_person = build_positions_by_person(
            conn,
            include_party_proxies=bool(args.include_party_proxies),
            max_list_values=max(0, int(args.max_list_values)),
            max_positions=max(0, int(args.max_positions)),
        )
    finally:
        conn.close()

    rows_out: list[list[Any]] = []
    max_list_values = max(0, int(args.max_list_values))
    max_positions = max(0, int(args.max_positions))

    for row in people_rows:
        person_id = as_int(row["person_id"])
        pos = positions_by_person.get(person_id) or {
            "roles": [],
            "institutions": [],
            "parties": [],
            "positions": [],
        }

        queue_gap_codes = csv_to_values(row["queue_gap_codes_csv"], max_values=max_list_values)
        queue_next_actions = csv_to_values(row["queue_next_actions_csv"], max_values=max_list_values)

        positions_json = json.dumps(
            list(pos["positions"])[:max_positions] if max_positions > 0 else [],
            ensure_ascii=False,
            separators=(",", ":"),
        )

        row_values = [
            person_id,
            norm(row["full_name"]),
            norm(row["canonical_key"]),
            norm(row["birth_date"]),
            norm(row["gender_label"]),
            norm(row["territory_name"]),
            norm(row["territory_code"]),
            as_int(row["mandates_total"]),
            as_int(row["active_mandates"]),
            as_int(row["institutions_total"]),
            as_int(row["parties_total"]),
            as_int(row["votes_total"]),
            as_int(row["vote_events_total"]),
            as_int(row["declared_evidence_total"]),
            as_int(row["revealed_vote_evidence_total"]),
            as_int(row["topic_positions_total"]),
            as_int(row["aliases_total"]),
            as_int(row["identifiers_total"]),
            norm(row["first_mandate_start"]),
            norm(row["last_mandate_date"]),
            norm(row["last_vote_date"]),
            norm(row["last_evidence_date"]),
            max_date(row["last_mandate_date"], row["last_vote_date"], row["last_evidence_date"]),
            "|".join(list(pos["roles"])[:max_list_values] if max_list_values > 0 else []),
            "|".join(list(pos["institutions"])[:max_list_values] if max_list_values > 0 else []),
            "|".join(list(pos["parties"])[:max_list_values] if max_list_values > 0 else []),
            positions_json,
            as_int(row["queue_pending_total"]),
            as_int(row["queue_in_progress_total"]),
            as_int(row["queue_priority_max"]),
            "|".join(queue_gap_codes),
            "|".join(queue_next_actions),
        ]
        rows_out.append(row_values)

    bucket_rows: dict[str, list[list[Any]]] = {}
    person_bucket_index: dict[str, str] = {}
    for row in rows_out:
        bucket = bucket_for_name(row[FULL_NAME_COL_INDEX])
        person_id = as_int(row[0])
        if person_id > 0:
            person_bucket_index[str(person_id)] = bucket
        bucket_rows.setdefault(bucket, []).append(row)

    data_dir = manifest_path.parent
    generated_files: list[dict[str, Any]] = []

    for bucket in sorted(bucket_rows.keys(), key=bucket_sort_key):
        filename = f"profiles-bucket-{bucket_slug(bucket)}.json"
        file_path = data_dir / filename
        payload = {
            "bucket": bucket,
            "columns": COLUMNS,
            "rows": bucket_rows[bucket],
            "rows_total": len(bucket_rows[bucket]),
        }
        bytes_written = write_payload(file_path, payload)
        generated_files.append(
            {
                "kind": "bucket",
                "bucket": bucket,
                "file": filename,
                "rows_total": len(bucket_rows[bucket]),
                "bytes": bytes_written,
            }
        )

    top_rows_count = max(0, int(args.top_rows))
    top_filename = "profiles-top.json"
    top_path = data_dir / top_filename
    top_payload = {
        "kind": "top",
        "columns": COLUMNS,
        "rows": rows_out[:top_rows_count] if top_rows_count > 0 else [],
        "rows_total": min(len(rows_out), top_rows_count) if top_rows_count > 0 else 0,
    }
    top_bytes = write_payload(top_path, top_payload)

    bucket_manifest = [
        {
            "bucket": item["bucket"],
            "file": item["file"],
            "rows_total": item["rows_total"],
            "bytes": item["bytes"],
        }
        for item in generated_files
        if item["kind"] == "bucket"
    ]

    manifest_payload = {
        "meta": {
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "people_total": len(rows_out),
            "queue_table_present": has_queue,
            "include_party_proxies": bool(args.include_party_proxies),
            "max_list_values": max_list_values,
            "max_positions": max_positions,
        },
        "columns": COLUMNS,
        "person_bucket_index": person_bucket_index,
        "top": {
            "file": top_filename,
            "rows_total": top_payload["rows_total"],
            "bytes": top_bytes,
        },
        "buckets": bucket_manifest,
    }
    manifest_bytes = write_payload(manifest_path, manifest_payload)

    print(
        "OK people snapshot exportado: "
        f"{manifest_path} ({len(rows_out)} people, {len(bucket_manifest)} buckets, manifest_bytes={manifest_bytes})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
