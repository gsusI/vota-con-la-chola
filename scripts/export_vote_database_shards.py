#!/usr/bin/env python3
"""Export bounded deterministic vote-event shards directly from SQLite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.publish import (  # noqa: E402
    _event_source_hash,
    _initiative_source_hash,
    _parse_json_maybe,
    _public_source_default_url,
    _public_source_url,
    _sha256_text,
)
from scripts.shard_large_vote_snapshot import (  # noqa: E402
    _make_member_lineage_explicit,
    _promote_source_record_urls,
    _redact_non_public_source_urls,
    _sha256_file,
    _write_gzip_json_atomic,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--source-ids", default="congreso_votaciones,senado_votaciones")
    parser.add_argument("--shard-root", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--snapshot-key", default="")
    parser.add_argument("--max-index-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--max-shard-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--max-members-per-shard", type=int, default=1_000)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def _next_or_none(iterator: Iterator[sqlite3.Row]) -> sqlite3.Row | None:
    try:
        return next(iterator)
    except StopIteration:
        return None


def _take_group(
    iterator: Iterator[sqlite3.Row],
    current: sqlite3.Row | None,
    event_id: str,
) -> tuple[list[sqlite3.Row], sqlite3.Row | None]:
    while current is not None and str(current["vote_event_id"]) < event_id:
        current = _next_or_none(iterator)
    rows: list[sqlite3.Row] = []
    while current is not None and str(current["vote_event_id"]) == event_id:
        rows.append(current)
        current = _next_or_none(iterator)
    return rows, current


def _initiative_item(row: sqlite3.Row) -> dict[str, Any]:
    evidence = _parse_json_maybe(row["evidence_json"])
    return {
        "initiative": {
            "initiative_id": str(row["initiative_id"]),
            "source_id": str(row["initiative_source_id"]),
            "legislature": row["legislature"],
            "expediente": row["expediente"],
            "supertype": row["supertype"],
            "grouping": row["grouping"],
            "type": row["type"],
            "title": row["title"],
        },
        "link": {
            "method": row["link_method"],
            "confidence": row["confidence"],
            "evidence": evidence if evidence is not None else row["evidence_json"],
        },
        "source": {
            "source_id": str(row["initiative_source_id"]),
            "source_record_id": row["initiative_source_record_id"],
            "source_snapshot_date": row["initiative_source_snapshot_date"],
            "source_url": _public_source_url(
                row["initiative_source_url"],
                fallback_url=row["initiative_source_default_url"],
                payload_text=row["initiative_raw_payload"],
            ),
            "source_default_url": _public_source_default_url(
                row["initiative_source_default_url"]
            ),
            "source_hash": _initiative_source_hash(row),
            "source_record_pk": row["initiative_source_record_pk"],
        },
    }


def _member_item(row: sqlite3.Row) -> dict[str, Any]:
    raw_payload = str(row["raw_payload"] or "")
    return {
        "seat": row["seat"],
        "member_name": row["member_name"],
        "member_name_normalized": row["member_name_normalized"],
        "person_id": row["person_id"],
        "person_full_name": row["person_full_name"],
        "group_code": row["group_code"],
        "vote_choice": row["vote_choice"],
        "source": {
            "source_id": row["source_id"],
            "source_url": _public_source_url(
                row["source_url"],
                fallback_url=row["source_default_url"],
                payload_text=raw_payload,
            ),
            "source_default_url": _public_source_default_url(row["source_default_url"]),
            "source_snapshot_date": row["source_snapshot_date"],
            "source_hash": _sha256_text(raw_payload),
            "source_record_pk": row["event_source_record_pk"],
            "source_record_id": row["event_source_record_id"],
            "source_record_scope": "parent_vote_event",
        },
    }


def _write_manifest_atomic(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = b""
    for _ in range(4):
        encoded = (
            json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
            + "\n"
        ).encode("utf-8")
        manifest["index_bytes"] = len(encoded)
        manifest["checks"]["index_bytes"] = len(encoded) <= int(
            manifest["limits"]["max_index_bytes"]
        )
        manifest["bounded_delivery_gate_passed"] = all(
            manifest["checks"].values()
        )
    encoded = (
        json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")
    partial = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with partial.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def export_database_shards(
    db_path: Path,
    *,
    snapshot_date: str,
    source_ids: tuple[str, ...],
    shard_root: Path,
    manifest_out: Path,
    snapshot_key: str,
    max_index_bytes: int,
    max_shard_bytes: int,
    max_members_per_shard: int,
) -> dict[str, Any]:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if not source_ids:
        raise ValueError("source_ids is empty")
    placeholders = ",".join("?" for _ in source_ids)
    output_root = Path(shard_root) / snapshot_key
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        event_cursor = conn.execute(
            f"""
            SELECT
              e.vote_event_id, e.legislature, e.session_number, e.vote_number,
              e.vote_date, e.title, e.expediente_text, e.subgroup_title,
              e.subgroup_text, e.assentimiento, e.totals_present, e.totals_yes,
              e.totals_no, e.totals_abstain, e.totals_no_vote, e.totals_absent,
              e.source_id, e.source_url, s.default_url AS source_default_url,
              e.source_record_pk, e.source_snapshot_date,
              e.raw_payload AS event_raw_payload,
              sr.source_record_id AS event_source_record_id,
              sr.content_sha256 AS event_source_hash
            FROM parl_vote_events AS e
            JOIN sources AS s ON s.source_id = e.source_id
            LEFT JOIN source_records AS sr ON sr.source_record_pk = e.source_record_pk
            WHERE e.source_id IN ({placeholders})
            ORDER BY e.vote_event_id
            """,
            source_ids,
        )
        member_iterator = iter(
            conn.execute(
                f"""
                SELECT
                  mv.vote_event_id, mv.seat, mv.member_name,
                  mv.member_name_normalized, mv.person_id,
                  p.full_name AS person_full_name, mv.group_code, mv.vote_choice,
                  mv.source_id, mv.source_url, s.default_url AS source_default_url,
                  mv.source_snapshot_date, mv.raw_payload,
                  e.source_record_pk AS event_source_record_pk,
                  sr.source_record_id AS event_source_record_id
                FROM parl_vote_member_votes AS mv
                JOIN sources AS s ON s.source_id = mv.source_id
                JOIN parl_vote_events AS e ON e.vote_event_id = mv.vote_event_id
                LEFT JOIN source_records AS sr ON sr.source_record_pk = e.source_record_pk
                LEFT JOIN persons AS p ON p.person_id = mv.person_id
                WHERE mv.source_id IN ({placeholders})
                ORDER BY mv.vote_event_id, mv.seat, mv.member_name, mv.member_vote_id
                """,
                source_ids,
            )
        )
        initiative_iterator = iter(
            conn.execute(
                f"""
                SELECT
                  l.vote_event_id, l.link_method, l.confidence, l.evidence_json,
                  i.initiative_id, i.legislature, i.expediente, i.supertype,
                  i.grouping, i.type, i.title,
                  i.source_id AS initiative_source_id,
                  i.source_url AS initiative_source_url,
                  si.default_url AS initiative_source_default_url,
                  i.source_record_pk AS initiative_source_record_pk,
                  i.source_snapshot_date AS initiative_source_snapshot_date,
                  i.raw_payload AS initiative_raw_payload,
                  sr.source_record_id AS initiative_source_record_id,
                  sr.content_sha256 AS initiative_source_hash
                FROM parl_vote_event_initiatives AS l
                JOIN parl_vote_events AS e ON e.vote_event_id = l.vote_event_id
                JOIN parl_initiatives AS i ON i.initiative_id = l.initiative_id
                JOIN sources AS si ON si.source_id = i.source_id
                LEFT JOIN source_records AS sr ON sr.source_record_pk = i.source_record_pk
                WHERE e.source_id IN ({placeholders})
                ORDER BY l.vote_event_id, i.initiative_id, l.link_method
                """,
                source_ids,
            )
        )
        current_member = _next_or_none(member_iterator)
        current_initiative = _next_or_none(initiative_iterator)
        entries: list[dict[str, Any]] = []
        total_member_votes = 0
        total_shard_bytes = 0
        max_observed_shard_bytes = 0
        max_observed_members = 0
        lineage = {
            "member_votes": 0,
            "source_record_inherited": 0,
            "source_record_unresolved": 0,
            "public_source_url_inherited": 0,
            "public_source_url_unresolved": 0,
            "non_public_source_urls_redacted": 0,
            "source_record_urls_promoted": 0,
        }
        seen_events: set[str] = set()
        for row in event_cursor:
            event_id = str(row["vote_event_id"] or "").strip()
            if not event_id or event_id in seen_events:
                raise ValueError(f"invalid or duplicate vote_event_id: {event_id!r}")
            seen_events.add(event_id)
            member_rows, current_member = _take_group(
                member_iterator, current_member, event_id
            )
            initiative_rows, current_initiative = _take_group(
                initiative_iterator, current_initiative, event_id
            )
            item: dict[str, Any] = {
                "event": {
                    "vote_event_id": event_id,
                    "source_id": str(row["source_id"]),
                    "legislature": row["legislature"],
                    "session_number": row["session_number"],
                    "vote_number": row["vote_number"],
                    "vote_date": row["vote_date"],
                    "title": row["title"],
                    "expediente_text": row["expediente_text"],
                    "subgroup_title": row["subgroup_title"],
                    "subgroup_text": row["subgroup_text"],
                    "assentimiento": row["assentimiento"],
                    "totals_present": row["totals_present"],
                    "totals_yes": row["totals_yes"],
                    "totals_no": row["totals_no"],
                    "totals_abstain": row["totals_abstain"],
                    "totals_no_vote": row["totals_no_vote"],
                    "totals_absent": row["totals_absent"],
                },
                "source": {
                    "source_id": str(row["source_id"]),
                    "source_record_id": row["event_source_record_id"],
                    "source_snapshot_date": row["source_snapshot_date"],
                    "source_url": _public_source_url(
                        row["source_url"],
                        fallback_url=row["source_default_url"],
                        payload_text=row["event_raw_payload"],
                    ),
                    "source_default_url": _public_source_default_url(
                        row["source_default_url"]
                    ),
                    "source_hash": _event_source_hash(row),
                    "source_record_pk": row["source_record_pk"],
                },
                "initiatives": [_initiative_item(value) for value in initiative_rows],
                "member_votes": [_member_item(value) for value in member_rows],
            }
            lineage["source_record_urls_promoted"] += _promote_source_record_urls(item)
            item_lineage = _make_member_lineage_explicit(item)
            for key, value in item_lineage.items():
                lineage[key] += int(value)
            lineage["non_public_source_urls_redacted"] += _redact_non_public_source_urls(item)
            event_hash = hashlib.sha256(event_id.encode()).hexdigest()
            relative_path = Path(event_hash[:2]) / f"{event_hash}.json.gz"
            digest, shard_bytes = _write_gzip_json_atomic(
                output_root / relative_path, item
            )
            member_count = len(member_rows)
            total_member_votes += member_count
            total_shard_bytes += shard_bytes
            max_observed_shard_bytes = max(max_observed_shard_bytes, shard_bytes)
            max_observed_members = max(max_observed_members, member_count)
            entries.append(
                {
                    "vote_event_id": event_id,
                    "source_id": str(row["source_id"]),
                    "vote_date": str(row["vote_date"] or ""),
                    "legislature": str(row["legislature"] or ""),
                    "title": str(row["title"] or "")[:500],
                    "member_votes": member_count,
                    "shard": (Path(snapshot_key) / relative_path).as_posix(),
                    "shard_bytes": shard_bytes,
                    "shard_sha256": digest,
                }
            )
    finally:
        conn.close()

    checks = {
        "index_bytes": True,
        "max_shard_bytes": max_observed_shard_bytes <= int(max_shard_bytes),
        "max_members_per_shard": max_observed_members
        <= int(max_members_per_shard),
        "unique_event_shards": len(entries) == len(seen_events),
        "member_source_record_coverage_at_least_99_pct": lineage[
            "source_record_unresolved"
        ]
        <= lineage["member_votes"] * 0.01,
        "member_public_source_url_coverage_at_least_99_pct": lineage[
            "public_source_url_unresolved"
        ]
        <= lineage["member_votes"] * 0.01,
    }
    database_sha256 = _sha256_file(db_path)
    manifest: dict[str, Any] = {
        "schema_version": "member_vote_event_shards_v2_sqlite_direct",
        "source_kind": "sqlite_direct",
        "source_database": db_path.name,
        "source_database_sha256": database_sha256,
        "source_snapshot": db_path.name,
        "source_snapshot_sha256": database_sha256,
        "snapshot_date": snapshot_date,
        "events_total": len(entries),
        "member_votes_total": total_member_votes,
        "shard_bytes_total": total_shard_bytes,
        "max_shard_bytes": max_observed_shard_bytes,
        "max_members_per_shard": max_observed_members,
        "compression": "gzip",
        "publication_status": "local_generated_not_published",
        "lineage": lineage,
        "limits": {
            "max_index_bytes": int(max_index_bytes),
            "max_shard_bytes": int(max_shard_bytes),
            "max_members_per_shard": int(max_members_per_shard),
        },
        "checks": checks,
        "index_bytes": 0,
        "bounded_delivery_gate_passed": False,
        "entries": entries,
    }
    _write_manifest_atomic(Path(manifest_out), manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_ids = tuple(
        value.strip() for value in str(args.source_ids).split(",") if value.strip()
    )
    snapshot_key = str(args.snapshot_key or "").strip() or (
        f"votaciones-db-{args.snapshot_date}"
    )
    try:
        manifest = export_database_shards(
            Path(args.db),
            snapshot_date=str(args.snapshot_date),
            source_ids=source_ids,
            shard_root=Path(args.shard_root),
            manifest_out=Path(args.manifest_out),
            snapshot_key=snapshot_key,
            max_index_bytes=int(args.max_index_bytes),
            max_shard_bytes=int(args.max_shard_bytes),
            max_members_per_shard=int(args.max_members_per_shard),
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "ok"
                if manifest["bounded_delivery_gate_passed"]
                else "failed",
                "events": manifest["events_total"],
                "member_votes": manifest["member_votes_total"],
                "manifest": Path(args.manifest_out).name,
            },
            sort_keys=True,
        )
    )
    return 1 if args.enforce and not manifest["bounded_delivery_gate_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
