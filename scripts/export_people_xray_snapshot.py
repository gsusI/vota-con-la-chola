#!/usr/bin/env python3
"""Exporta perfiles X-ray por entidad para /people (partido, institución, ámbito, territorio, cargo)."""

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
DEFAULT_OUT = Path("docs/gh-pages/people/data/xray.json")
DATE_RE = re.compile(r"^[1-2][0-9]{3}-[01][0-9]-[0-3][0-9]")


KIND_DEFS = ("party", "institution", "ambito", "territorio", "cargo")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta perfiles X-ray por entidad para /people")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la base SQLite.")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Ruta de salida JSON.")
    p.add_argument("--snapshot-date", default="", help="Fecha del snapshot (YYYY-MM-DD).")
    p.add_argument(
        "--top-members",
        type=int,
        default=24,
        help="Máximo de personas en el bloque 'personas destacadas' por grupo.",
    )
    p.add_argument(
        "--include-party-proxies",
        action="store_true",
        help="Incluye personas canónicas party:* en el directorio.",
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


def slugify(value: Any, fallback: str = "sin-valor") -> str:
    raw = norm(value).lower()
    if not raw:
        return fallback
    decomposed = unicodedata.normalize("NFKD", raw)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text, flags=re.IGNORECASE)
    ascii_text = re.sub(r"-{2,}", "-", ascii_text).strip("-")
    return ascii_text or fallback


def slug_with_uniqueness(base: str, seen: dict[str, int]) -> str:
    count = seen.get(base, 0) + 1
    seen[base] = count
    if count == 1:
        return base
    return f"{base}-{count}"


def fetch_person_summaries(conn: sqlite3.Connection, include_party_proxies: bool) -> dict[int, dict[str, Any]]:
    sql = """
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
        MAX(CASE WHEN evidence_date GLOB '[1-2][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' THEN evidence_date END) AS last_evidence_date
      FROM topic_evidence
      GROUP BY person_id
    )
    SELECT
      p.person_id,
      p.full_name,
      COALESCE(tt.name, '') AS territory_name,
      COALESCE(ma.mandates_total, 0) AS mandates_total,
      COALESCE(ma.active_mandates, 0) AS active_mandates,
      COALESCE(ma.institutions_total, 0) AS institutions_total,
      COALESCE(ma.parties_total, 0) AS parties_total,
      COALESCE(va.votes_total, 0) AS votes_total,
      COALESCE(va.vote_events_total, 0) AS vote_events_total,
      ma.first_mandate_start,
      ma.last_mandate_date,
      va.last_vote_date,
      ea.last_evidence_date
    FROM persons p
    LEFT JOIN territories tt ON tt.territory_id = p.territory_id
    LEFT JOIN mandate_agg ma ON ma.person_id = p.person_id
    LEFT JOIN vote_agg va ON va.person_id = p.person_id
    LEFT JOIN evidence_agg ea ON ea.person_id = p.person_id
    WHERE (? = 1 OR p.canonical_key NOT LIKE 'party:%')
    """

    rows = conn.execute(sql, (1 if include_party_proxies else 0,)).fetchall()
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        person_id = as_int(row["person_id"])
        if person_id <= 0:
            continue
        last_action = max_date(row["last_mandate_date"], row["last_vote_date"], row["last_evidence_date"])
        out[person_id] = {
            "person_id": person_id,
            "full_name": norm(row["full_name"]),
            "mandates_total": as_int(row["mandates_total"]),
            "active_mandates": as_int(row["active_mandates"]),
            "votes_total": as_int(row["votes_total"]),
            "vote_events_total": as_int(row["vote_events_total"]),
            "institutions_total": as_int(row["institutions_total"]),
            "parties_total": as_int(row["parties_total"]),
            "last_action_date": last_action,
            "last_mandate_date": norm(row["last_mandate_date"]),
            "last_vote_date": norm(row["last_vote_date"]),
            "last_evidence_date": norm(row["last_evidence_date"]),
            "territory_name": norm(row["territory_name"]),
        }
    return out


def fetch_mandate_rows(conn: sqlite3.Connection, include_party_proxies: bool) -> list[sqlite3.Row]:
    sql = """
    SELECT
      m.mandate_id,
      m.person_id,
      m.party_id,
      COALESCE(pa.name, '') AS party_name,
      COALESCE(pa.acronym, '') AS party_acronym,
      m.institution_id,
      COALESCE(i.name, '') AS institution_name,
      m.role_title,
      m.admin_level_id,
      COALESCE(al.label, '') AS admin_level_label,
      m.territory_id,
      COALESCE(tt.name, '') AS territory_name,
      COALESCE(tt.code, '') AS territory_code,
      COALESCE(m.is_active, 0) AS is_active
    FROM mandates m
    JOIN persons p ON p.person_id = m.person_id
    LEFT JOIN parties pa ON pa.party_id = m.party_id
    LEFT JOIN institutions i ON i.institution_id = m.institution_id
    LEFT JOIN admin_levels al ON al.admin_level_id = m.admin_level_id
    LEFT JOIN territories tt ON tt.territory_id = m.territory_id
    WHERE (? = 1 OR p.canonical_key NOT LIKE 'party:%')
    ORDER BY m.person_id, m.mandate_id
    """
    return conn.execute(sql, (1 if include_party_proxies else 0,)).fetchall()


def make_group_key(kind: str, row: sqlite3.Row) -> tuple[str, str, Any, str, str]:
    if kind == "party":
        raw_id = as_int(row["party_id"])
        raw_label = norm(row["party_name"]) or norm(row["party_acronym"]) or "Sin partido"
        group_key = f"party:{raw_id}" if raw_id > 0 else "party:sin_partido"
        explorer_value = raw_id if raw_id > 0 else ""
        return "party_id", group_key, explorer_value, raw_label, slugify(raw_label, fallback="sin-partido")

    if kind == "institution":
        raw_id = as_int(row["institution_id"])
        raw_label = norm(row["institution_name"]) or "Sin institución"
        group_key = f"institution:{raw_id}" if raw_id > 0 else "institution:sin_institucion"
        explorer_value = raw_id if raw_id > 0 else ""
        return "institution_id", group_key, explorer_value, raw_label, slugify(raw_label, fallback="sin-institucion")

    if kind == "ambito":
        raw_id = as_int(row["admin_level_id"])
        raw_label = norm(row["admin_level_label"]) or "Sin ámbito"
        group_key = f"ambito:{raw_id}" if raw_id > 0 else "ambito:sin_ambito"
        explorer_value = raw_id if raw_id > 0 else ""
        return "admin_level_id", group_key, explorer_value, raw_label, slugify(raw_label, fallback="sin-ambito")

    if kind == "territorio":
        raw_id = as_int(row["territory_id"])
        raw_label = norm(row["territory_name"]) or norm(row["territory_code"]) or "Sin territorio"
        group_key = f"territorio:{raw_id}" if raw_id > 0 else "territorio:sin_territorio"
        explorer_value = raw_id if raw_id > 0 else ""
        return "territory_id", group_key, explorer_value, raw_label, slugify(raw_label, fallback="sin-territorio")

    raw_label = norm(row["role_title"]) or "Sin cargo"
    group_key = f"cargo:{raw_label.lower()}"
    return "role_title", group_key, raw_label, raw_label, slugify(raw_label, fallback="sin-cargo")


def build_payload(
    person_summaries: dict[int, dict[str, Any]],
    mandate_rows: list[sqlite3.Row],
    top_members: int,
) -> dict[str, Any]:
    groups: dict[str, dict[str, dict[str, Any]]] = {kind: {} for kind in KIND_DEFS}
    member_lists: dict[str, dict[str, set[int]]] = {kind: {} for kind in KIND_DEFS}

    for row in mandate_rows:
        person_id = as_int(row["person_id"])
        if person_id <= 0:
            continue

        is_active = as_int(row["is_active"]) > 0
        person_summary = person_summaries.get(person_id)

        for kind in KIND_DEFS:
            wc, group_key, wc_value, label, base_slug = make_group_key(kind, row)
            kind_groups = groups[kind]
            if group_key not in kind_groups:
                kind_groups[group_key] = {
                    "kind": kind,
                    "group_key": group_key,
                    "label": label,
                    "slug": base_slug,
                    "explorer_wc": wc,
                    "explorer_wv": wc_value,
                    "person_count": 0,
                    "active_person_count": 0,
                    "mandates_total": 0,
                    "active_mandates_total": 0,
                    "votes_total": 0,
                    "vote_events_total": 0,
                    "last_action_date": "",
                    "_member_ids": set(),
                }
                member_lists[kind][group_key] = set()

            group = kind_groups[group_key]
            group["mandates_total"] += 1
            if is_active:
                group["active_mandates_total"] += 1

            if person_id not in member_lists[kind][group_key]:
                member_lists[kind][group_key].add(person_id)
                if person_summary is not None:
                    group["person_count"] += 1
                    if as_int(person_summary["active_mandates"]) > 0:
                        group["active_person_count"] += 1
                    group["votes_total"] += as_int(person_summary["votes_total"])
                    group["vote_events_total"] += as_int(person_summary["vote_events_total"])
                    person_last = norm(person_summary["last_action_date"])
                    if person_last and (not group["last_action_date"] or person_last > group["last_action_date"]):
                        group["last_action_date"] = person_last

    # Unique slug assignment per kind (avoid collisions).
    for kind in KIND_DEFS:
        seen_slugs: dict[str, int] = {}
        for group in groups[kind].values():
            group["slug"] = slug_with_uniqueness(group["slug"], seen_slugs)

    out_groups: dict[str, list[dict[str, Any]]] = {}
    for kind in KIND_DEFS:
        entries: list[dict[str, Any]] = []
        for key, group in groups[kind].items():
            member_ids = member_lists[kind].get(key, set())
            sorted_people = sorted(
                (person_summaries.get(pid) for pid in member_ids),
                key=lambda item: (
                    -(as_int(item["active_mandates"]) if item else 0),
                    -(as_int(item["votes_total"]) if item else 0),
                    -(as_int(item["vote_events_total"]) if item else 0),
                    norm(item["full_name"]) if item else "",
                ),
            )

            people_preview: list[dict[str, Any]] = []
            for person in sorted_people[:top_members]:
                if not person:
                    continue
                people_preview.append(
                    {
                        "person_id": as_int(person["person_id"]),
                        "full_name": norm(person["full_name"]),
                        "mandates_total": as_int(person["mandates_total"]),
                        "active_mandates": as_int(person["active_mandates"]),
                        "votes_total": as_int(person["votes_total"]),
                        "vote_events_total": as_int(person["vote_events_total"]),
                        "last_action_date": norm(person["last_action_date"]),
                    }
                )

            entry = {
                "kind": kind,
                "group_key": group["group_key"],
                "slug": group["slug"],
                "label": group["label"],
                "explorer_wc": group["explorer_wc"],
                "explorer_wv": norm(group["explorer_wv"]),
                "person_count": as_int(group["person_count"]),
                "active_person_count": as_int(group["active_person_count"]),
                "mandates_total": as_int(group["mandates_total"]),
                "active_mandates_total": as_int(group["active_mandates_total"]),
                "votes_total": as_int(group["votes_total"]),
                "vote_events_total": as_int(group["vote_events_total"]),
                "last_action_date": norm(group["last_action_date"]),
                "top_people": people_preview,
            }
            entries.append(entry)
        out_groups[kind] = sorted(entries, key=lambda item: (-item["person_count"], str(item["label"]).lower()))

    return out_groups


def write_payload(path: Path, payload: dict[str, Any]) -> int:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(encoded, encoding="utf-8")
    return len(encoded.encode("utf-8"))


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: no existe el DB -> {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        snapshot_date = norm(args.snapshot_date) or infer_snapshot_date(conn)
        person_summaries = fetch_person_summaries(conn, include_party_proxies=bool(args.include_party_proxies))
        mandate_rows = fetch_mandate_rows(conn, include_party_proxies=bool(args.include_party_proxies))
        groups_payload = build_payload(
            person_summaries=person_summaries,
            mandate_rows=mandate_rows,
            top_members=max(1, int(args.top_members)),
        )
    finally:
        conn.close()

    xray_index: dict[str, dict[str, str]] = {}
    for kind in KIND_DEFS:
        kind_index: dict[str, str] = {}
        for group in groups_payload.get(kind, []):
            kind_index[group["slug"]] = group["group_key"]
        xray_index[kind] = kind_index

    payload = {
        "meta": {
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "source_snapshot": snapshot_date,
            "top_members": max(1, int(args.top_members)),
            "include_party_proxies": bool(args.include_party_proxies),
            "group_count": {kind: len(groups_payload.get(kind, [])) for kind in KIND_DEFS},
        },
        "kinds": KIND_DEFS,
        "groups": groups_payload,
        "group_index": xray_index,
    }
    bytes_written = write_payload(out_path, payload)
    print(f"OK people xray snapshot -> {out_path} ({bytes_written} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
