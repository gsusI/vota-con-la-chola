"""Typed, incremental Parquet publication for accountability-ledger facts."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    SemanticLaneContract,
    peak_rss_mb,
    private_token_findings,
    public_http_url,
    safe_component,
    sha256_file,
)
from .semantic_parquet_io import (
    PartitionWriter,
    reusable_partition,
    reuse_partition_files,
)

ACCOUNTABILITY_LEDGER_CONTRACT = SemanticLaneContract(
    lane="accountability_ledger",
    transformer_version="accountability_ledger_public_v2",
    id_column="entry_id",
    year_column="entry_year",
    schema=(
        {"name": "entry_id", "type": "string", "nullable": False},
        {"name": "issue_id", "type": "string", "nullable": False},
        {"name": "issue_key", "type": "string", "nullable": False},
        {"name": "issue_label", "type": "string", "nullable": False},
        {"name": "issue_status", "type": "string", "nullable": False},
        {"name": "entry_kind", "type": "string", "nullable": False},
        {"name": "accountability_role", "type": "string", "nullable": True},
        {"name": "role_in_chain", "type": "string", "nullable": True},
        {"name": "actor_label", "type": "string", "nullable": False},
        {"name": "actor_kind", "type": "string", "nullable": False},
        {"name": "actor_resolution_state", "type": "string", "nullable": False},
        {"name": "person_id", "type": "int64", "nullable": True},
        {"name": "party_id", "type": "int64", "nullable": True},
        {"name": "parliamentary_group_id", "type": "int64", "nullable": True},
        {"name": "mandate_id", "type": "int64", "nullable": True},
        {"name": "institution_id", "type": "int64", "nullable": True},
        {"name": "org_unit_id", "type": "int64", "nullable": True},
        {"name": "position_id", "type": "int64", "nullable": True},
        {"name": "linked_object_type", "type": "string", "nullable": True},
        {"name": "linked_object_id", "type": "string", "nullable": True},
        {"name": "policy_event_id", "type": "string", "nullable": True},
        {"name": "topic_evidence_id", "type": "int64", "nullable": True},
        {"name": "legal_fragment_id", "type": "string", "nullable": True},
        {"name": "event_date", "type": "string", "nullable": True},
        {"name": "published_date", "type": "string", "nullable": True},
        {"name": "entry_year", "type": "string", "nullable": False},
        {"name": "title", "type": "string", "nullable": True},
        {"name": "summary", "type": "string", "nullable": True},
        {
            "name": "accountability_question",
            "type": "string",
            "nullable": True,
        },
        {"name": "confidence", "type": "float64", "nullable": True},
        {"name": "evidence_tier", "type": "int64", "nullable": True},
        {"name": "source_id", "type": "string", "nullable": False},
        {"name": "source_id_scope", "type": "string", "nullable": False},
        {"name": "source_title", "type": "string", "nullable": True},
        {"name": "source_url", "type": "string", "nullable": True},
        {"name": "source_url_scope", "type": "string", "nullable": True},
        {"name": "source_record_pk", "type": "int64", "nullable": True},
        {"name": "evidence_quote", "type": "string", "nullable": True},
        {"name": "lineage_state", "type": "string", "nullable": False},
        {"name": "jurisdiction", "type": "string", "nullable": False},
    ),
)

ACCOUNTABILITY_LEDGER_SQL = """
SELECT
  l.entry_id,
  l.issue_id,
  i.canonical_key AS issue_key,
  i.label AS issue_label,
  i.issue_status,
  l.entry_kind,
  l.accountability_role,
  l.role_in_chain,
  l.actor_label,
  l.actor_kind,
  l.person_id,
  l.party_id,
  l.parliamentary_group_id,
  l.mandate_id,
  l.institution_id,
  l.org_unit_id,
  l.position_id,
  l.linked_object_type,
  l.linked_object_id,
  l.policy_event_id,
  l.topic_evidence_id,
  l.legal_fragment_id,
  l.event_date,
  l.published_date,
  CASE
    WHEN substr(COALESCE(NULLIF(l.event_date, ''), l.published_date, ''), 1, 4)
      GLOB '[12][0-9][0-9][0-9]'
    THEN substr(COALESCE(NULLIF(l.event_date, ''), l.published_date, ''), 1, 4)
    ELSE 'unknown'
  END AS entry_year,
  l.title,
  l.summary,
  l.accountability_question,
  l.confidence,
  l.evidence_tier,
  CASE
    WHEN NULLIF(l.source_id, '') IS NOT NULL THEN l.source_id
    WHEN l.source_url LIKE 'https://www.boe.es/%' THEN 'boe_api_legal'
    WHEN l.source_url LIKE 'https://contrataciondelestado.es/%' THEN 'placsp_contratacion'
    WHEN l.source_url LIKE 'https://www.pap.hacienda.gob.es/%' THEN 'bdns_subvenciones'
    WHEN l.source_url LIKE 'https://www.congreso.es/%' THEN 'congreso_votaciones'
    WHEN l.source_url LIKE 'https://www.senado.es/%' THEN 'senado_votaciones'
    ELSE 'unknown'
  END AS normalized_source_id,
  CASE
    WHEN NULLIF(l.source_id, '') IS NOT NULL THEN 'record'
    WHEN l.source_url LIKE 'https://www.boe.es/%'
      OR l.source_url LIKE 'https://contrataciondelestado.es/%'
      OR l.source_url LIKE 'https://www.pap.hacienda.gob.es/%'
      OR l.source_url LIKE 'https://www.congreso.es/%'
      OR l.source_url LIKE 'https://www.senado.es/%'
    THEN 'official_url'
    ELSE 'unknown'
  END AS source_id_scope,
  l.source_title,
  l.source_url,
  s.default_url AS source_default_url,
  l.source_record_pk,
  l.evidence_quote
FROM accountability_ledger_entries AS l
JOIN accountability_issues AS i USING (issue_id)
LEFT JOIN sources AS s ON s.source_id = l.source_id
ORDER BY normalized_source_id, entry_year, l.entry_id
"""

NATIONAL_SOURCE_IDS = {
    "bdns_subvenciones",
    "boe_api_legal",
    "congreso_votaciones",
    "placsp_contratacion",
    "senado_votaciones",
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _integer(value: Any) -> int | None:
    return None if value is None else int(value)


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


def _jurisdiction(source_id: str) -> str:
    if source_id in NATIONAL_SOURCE_IDS:
        return "es-national"
    return "es-" + safe_component(source_id)


def _actor_resolution_state(row: sqlite3.Row) -> str:
    actor_kind = str(row["actor_kind"])
    key_by_kind = {
        "person": "person_id",
        "party": "party_id",
        "group": "parliamentary_group_id",
        "institution": "institution_id",
        "org_unit": "org_unit_id",
        "position": "position_id",
    }
    key = key_by_kind.get(actor_kind)
    if key and row[key] is not None:
        return "resolved_" + actor_kind
    return "unresolved_" + actor_kind


def _lineage_state(row: sqlite3.Row, source_url: str | None) -> str:
    if row["source_record_pk"] is not None:
        return "source_record"
    if row["policy_event_id"] not in (None, ""):
        return "policy_event"
    if row["topic_evidence_id"] is not None:
        return "topic_evidence"
    if row["legal_fragment_id"] not in (None, ""):
        return "legal_fragment"
    if row["linked_object_type"] not in (None, "") and row["linked_object_id"] not in (
        None,
        "",
    ):
        return "linked_object"
    if source_url:
        return "source_url"
    return "missing"


def _public_row(row: sqlite3.Row) -> dict[str, Any]:
    source_id = str(row["normalized_source_id"])
    record_url = public_http_url(row["source_url"])
    source_default_url = public_http_url(row["source_default_url"])
    source_url = record_url or source_default_url
    source_url_scope = (
        "record" if record_url else "source_default" if source_default_url else None
    )
    return {
        "entry_id": str(row["entry_id"]),
        "issue_id": str(row["issue_id"]),
        "issue_key": str(row["issue_key"]),
        "issue_label": str(row["issue_label"]),
        "issue_status": str(row["issue_status"]),
        "entry_kind": str(row["entry_kind"]),
        "accountability_role": _text(row["accountability_role"]),
        "role_in_chain": _text(row["role_in_chain"]),
        "actor_label": str(row["actor_label"]),
        "actor_kind": str(row["actor_kind"]),
        "actor_resolution_state": _actor_resolution_state(row),
        "person_id": _integer(row["person_id"]),
        "party_id": _integer(row["party_id"]),
        "parliamentary_group_id": _integer(row["parliamentary_group_id"]),
        "mandate_id": _integer(row["mandate_id"]),
        "institution_id": _integer(row["institution_id"]),
        "org_unit_id": _integer(row["org_unit_id"]),
        "position_id": _integer(row["position_id"]),
        "linked_object_type": _text(row["linked_object_type"]),
        "linked_object_id": _text(row["linked_object_id"]),
        "policy_event_id": _text(row["policy_event_id"]),
        "topic_evidence_id": _integer(row["topic_evidence_id"]),
        "legal_fragment_id": _text(row["legal_fragment_id"]),
        "event_date": _text(row["event_date"]),
        "published_date": _text(row["published_date"]),
        "entry_year": str(row["entry_year"]),
        "title": _text(row["title"]),
        "summary": _text(row["summary"]),
        "accountability_question": _text(row["accountability_question"]),
        "confidence": _float(row["confidence"]),
        "evidence_tier": _integer(row["evidence_tier"]),
        "source_id": source_id,
        "source_id_scope": str(row["source_id_scope"]),
        "source_title": _text(row["source_title"]),
        "source_url": source_url,
        "source_url_scope": source_url_scope,
        "source_record_pk": _integer(row["source_record_pk"]),
        "evidence_quote": _text(row["evidence_quote"]),
        "lineage_state": _lineage_state(row, source_url),
        "jurisdiction": _jurisdiction(source_id),
    }


def _iter_rows(db_path: Path) -> Iterator[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for row in conn.execute(ACCOUNTABILITY_LEDGER_SQL):
            yield _public_row(row)
    finally:
        conn.close()


def _partition_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["source_id"]),
        str(row["jurisdiction"]),
        str(row["entry_year"]),
    )


def _partition_id(key: tuple[str, str, str]) -> str:
    return "|".join(key)


def _partition_dir(snapshot_date: str, key: tuple[str, str, str]) -> Path:
    source_id, jurisdiction, year = key
    return Path(
        f"lane={ACCOUNTABILITY_LEDGER_CONTRACT.lane}",
        f"snapshot_date={safe_component(snapshot_date)}",
        f"source_id={safe_component(source_id)}",
        f"jurisdiction={safe_component(jurisdiction)}",
        f"year={safe_component(year)}",
    )


def _new_partition(snapshot_date: str, key: tuple[str, str, str]) -> dict[str, Any]:
    return {
        "partition_id": _partition_id(key),
        "values": {
            "snapshot_date": snapshot_date,
            "source_id": key[0],
            "jurisdiction": key[1],
            "year": key[2],
        },
        "relative_dir": _partition_dir(snapshot_date, key).as_posix(),
        "rows": 0,
        "min_id": None,
        "max_id": None,
        "source_url_rows": 0,
        "source_record_url_rows": 0,
        "source_default_url_rows": 0,
        "source_record_rows": 0,
        "official_url_source_id_rows": 0,
        "unknown_source_id_rows": 0,
        "lineage_rows": 0,
        "resolved_actor_rows": 0,
        "unresolved_actor_rows": 0,
        "private_token_findings": 0,
        "_digest": hashlib.sha256(),
    }


def scan_accountability_partitions(
    db_path: Path, *, snapshot_date: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    totals = {
        "rows": 0,
        "source_url_rows": 0,
        "source_record_url_rows": 0,
        "source_default_url_rows": 0,
        "source_record_rows": 0,
        "official_url_source_id_rows": 0,
        "unknown_source_id_rows": 0,
        "lineage_rows": 0,
        "resolved_actor_rows": 0,
        "unresolved_actor_rows": 0,
        "private_token_findings": 0,
        "unknown_year_rows": 0,
    }
    partitions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: tuple[str, str, str] | None = None
    for row in _iter_rows(db_path):
        key = _partition_key(row)
        if current_key != key:
            if current is not None:
                current["input_sha256"] = current.pop("_digest").hexdigest()
                partitions.append(current)
            current_key = key
            current = _new_partition(snapshot_date, key)
        assert current is not None
        row_id = str(row["entry_id"])
        current["rows"] += 1
        current["min_id"] = (
            row_id if current["min_id"] is None else min(str(current["min_id"]), row_id)
        )
        current["max_id"] = (
            row_id if current["max_id"] is None else max(str(current["max_id"]), row_id)
        )
        for metric, field in (
            ("source_url_rows", "source_url"),
            ("source_record_rows", "source_record_pk"),
        ):
            if row[field] not in (None, ""):
                current[metric] += 1
                totals[metric] += 1
        if row["source_url_scope"] == "record":
            current["source_record_url_rows"] += 1
            totals["source_record_url_rows"] += 1
        elif row["source_url_scope"] == "source_default":
            current["source_default_url_rows"] += 1
            totals["source_default_url_rows"] += 1
        if row["source_id_scope"] == "official_url":
            current["official_url_source_id_rows"] += 1
            totals["official_url_source_id_rows"] += 1
        elif row["source_id_scope"] == "unknown":
            current["unknown_source_id_rows"] += 1
            totals["unknown_source_id_rows"] += 1
        if row["lineage_state"] != "missing":
            current["lineage_rows"] += 1
            totals["lineage_rows"] += 1
        actor_metric = (
            "resolved_actor_rows"
            if str(row["actor_resolution_state"]).startswith("resolved_")
            else "unresolved_actor_rows"
        )
        current[actor_metric] += 1
        totals[actor_metric] += 1
        findings = private_token_findings(row)
        current["private_token_findings"] += findings
        totals["private_token_findings"] += findings
        if row["entry_year"] == "unknown":
            totals["unknown_year_rows"] += 1
        current["_digest"].update(
            ACCOUNTABILITY_LEDGER_CONTRACT.canonical_row_bytes(row)
        )
        totals["rows"] += 1
    if current is not None:
        current["input_sha256"] = current.pop("_digest").hexdigest()
        partitions.append(current)
    return partitions, totals


def _database_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        ledger_rows = int(
            conn.execute(
                "SELECT COUNT(*) FROM accountability_ledger_entries"
            ).fetchone()[0]
        )
        joined_rows = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM accountability_ledger_entries AS l
                JOIN accountability_issues AS i USING (issue_id)
                """
            ).fetchone()[0]
        )
        distinct_ids = int(
            conn.execute(
                "SELECT COUNT(DISTINCT entry_id) FROM accountability_ledger_entries"
            ).fetchone()[0]
        )
        return {
            "ledger_rows": ledger_rows,
            "joined_rows": joined_rows,
            "distinct_entry_ids": distinct_ids,
        }
    finally:
        conn.close()


def _previous_partitions(
    manifest_path: Path | None,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    if manifest_path is None:
        return {}, None
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    valid = (
        payload.get("schema_version") == MANIFEST_SCHEMA_VERSION
        and payload.get("lane") == ACCOUNTABILITY_LEDGER_CONTRACT.lane
        and payload.get("transformer_version")
        == ACCOUNTABILITY_LEDGER_CONTRACT.transformer_version
        and payload.get("schema_sha256") == ACCOUNTABILITY_LEDGER_CONTRACT.schema_sha256
    )
    partitions = (
        {
            str(item["partition_id"]): item
            for item in list(payload.get("partitions") or [])
        }
        if valid
        else {}
    )
    return partitions, sha256_file(manifest_path)


def export_accountability_partitions(
    *,
    db_path: Path,
    output_root: Path,
    snapshot_date: str,
    compression: str = "zstd",
    row_group_rows: int = 25_000,
    max_file_rows: int = 100_000,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    min_rows: int = 100_000,
    max_peak_rss_mb: float = 1024.0,
    enforce: bool = False,
) -> dict[str, Any]:
    db_path = Path(db_path)
    output_root = Path(output_root)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if output_root.exists():
        raise FileExistsError(output_root)
    if row_group_rows <= 0 or max_file_rows <= 0:
        raise ValueError("row-group-rows and max-file-rows must be positive")
    if row_group_rows > max_file_rows:
        raise ValueError("row-group-rows cannot exceed max-file-rows")
    if (previous_manifest_path is None) != (previous_root is None):
        raise ValueError(
            "previous-manifest and previous-root must be provided together"
        )

    started = time.monotonic()
    scan_started = time.monotonic()
    partitions, scan_totals = scan_accountability_partitions(
        db_path, snapshot_date=snapshot_date
    )
    scan_seconds = time.monotonic() - scan_started
    database_counts = _database_counts(db_path)
    previous_by_id, previous_sha256 = _previous_partitions(previous_manifest_path)
    reusable: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        previous = previous_by_id.get(str(partition["partition_id"]))
        eligible = reusable_partition(
            partition=partition,
            previous=previous,
            previous_root=previous_root,
        )
        if eligible is not None:
            reusable[str(partition["partition_id"])] = eligible

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    partition_by_id = {
        str(partition["partition_id"]): partition for partition in partitions
    }
    hardlinks = 0
    copies = 0
    try:
        for partition_id, previous in reusable.items():
            partition = partition_by_id[partition_id]
            files, modes = reuse_partition_files(
                previous=previous,
                previous_root=Path(previous_root),
                staging_root=staging_root,
                partition=partition,
            )
            partition["files"] = files
            partition["materialization"] = "reused"
            hardlinks += modes["hardlink"]
            copies += modes["copy"]

        export_started = time.monotonic()
        active_id: str | None = None
        active_writer: PartitionWriter | None = None
        if len(reusable) < len(partitions):
            for row in _iter_rows(db_path):
                partition_id = _partition_id(_partition_key(row))
                if partition_id != active_id:
                    if active_writer is not None:
                        partition_by_id[str(active_id)]["files"] = active_writer.close()
                        partition_by_id[str(active_id)]["materialization"] = "rebuilt"
                    active_id = partition_id
                    if partition_id in reusable:
                        active_writer = None
                    else:
                        active_writer = PartitionWriter(
                            root=staging_root,
                            partition=partition_by_id[partition_id],
                            contract=ACCOUNTABILITY_LEDGER_CONTRACT,
                            compression=compression,
                            row_group_rows=row_group_rows,
                            max_file_rows=max_file_rows,
                        )
                if active_writer is not None:
                    active_writer.append(row)
            if active_writer is not None:
                partition_by_id[str(active_id)]["files"] = active_writer.close()
                partition_by_id[str(active_id)]["materialization"] = "rebuilt"
        export_seconds = time.monotonic() - export_started

        rows = int(scan_totals["rows"])
        files = sum(len(list(partition.get("files") or [])) for partition in partitions)
        parquet_bytes = sum(
            int(file_meta["bytes"])
            for partition in partitions
            for file_meta in list(partition.get("files") or [])
        )
        peak_rss = peak_rss_mb()
        checks = {
            "minimum_rows": rows >= int(min_rows),
            "database_join_balance": database_counts["ledger_rows"]
            == database_counts["joined_rows"]
            == rows,
            "distinct_entry_ids": database_counts["distinct_entry_ids"] == rows,
            "source_url_complete": scan_totals["source_url_rows"] == rows,
            "source_id_complete": scan_totals["unknown_source_id_rows"] == 0,
            "lineage_complete": scan_totals["lineage_rows"] == rows,
            "actor_resolution_state_complete": (
                scan_totals["resolved_actor_rows"]
                + scan_totals["unresolved_actor_rows"]
            )
            == rows,
            "no_private_tokens": scan_totals["private_token_findings"] == 0,
            "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
            "bounded_file_rows": all(
                int(file_meta["rows"]) <= int(max_file_rows)
                for partition in partitions
                for file_meta in list(partition.get("files") or [])
            ),
        }
        analytical_gate_passed = all(checks.values())
        promotion_checks = {
            "analytical_partition_gate": analytical_gate_passed,
            "durable_public_origin_verified": False,
            "published_artifact_restore_verified": False,
        }
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "snapshot_date": snapshot_date,
            "lane": ACCOUNTABILITY_LEDGER_CONTRACT.lane,
            "transformer_version": ACCOUNTABILITY_LEDGER_CONTRACT.transformer_version,
            "schema": ACCOUNTABILITY_LEDGER_CONTRACT.schema,
            "schema_sha256": ACCOUNTABILITY_LEDGER_CONTRACT.schema_sha256,
            "partition_contract": {
                "strategy": "semantic_hive",
                "keys": ["snapshot_date", "source_id", "jurisdiction", "year"],
                "ordering": ["source_id", "year", "entry_id"],
                "row_group_rows": int(row_group_rows),
                "max_file_rows": int(max_file_rows),
                "compression": compression,
            },
            "incremental_contract": {
                "input_fingerprint": "sha256_canonical_public_rows",
                "reuse_key": [
                    "partition_id",
                    "input_sha256",
                    "schema_sha256",
                    "transformer_version",
                ],
                "previous_manifest_sha256": previous_sha256,
                "partitions_reused": len(reusable),
                "partitions_rebuilt": len(partitions) - len(reusable),
                "files_hardlinked": hardlinks,
                "files_copied": copies,
            },
            "source": {
                "database_file": db_path.name,
                "database_bytes": int(db_path.stat().st_size),
                "table": "accountability_ledger_entries",
                "issue_table": "accountability_issues",
                "raw_payload_published": False,
                "source_locator_published": False,
            },
            "totals": {
                **database_counts,
                **scan_totals,
                "partitions": len(partitions),
                "files": files,
                "parquet_bytes": parquet_bytes,
            },
            "coverage": {
                "source_url": round(scan_totals["source_url_rows"] / rows, 8)
                if rows
                else 0.0,
                "source_record": round(scan_totals["source_record_rows"] / rows, 8)
                if rows
                else 0.0,
                "lineage": round(scan_totals["lineage_rows"] / rows, 8)
                if rows
                else 0.0,
                "resolved_actor": round(scan_totals["resolved_actor_rows"] / rows, 8)
                if rows
                else 0.0,
            },
            "checks": checks,
            "analytical_partition_gate_passed": analytical_gate_passed,
            "promotion_checks": promotion_checks,
            "promotion_gate_passed": all(promotion_checks.values()),
            "publication_status": "local_generated_not_published",
            "performance": {
                "fingerprint_seconds": round(scan_seconds, 6),
                "materialize_seconds": round(export_seconds, 6),
                "total_seconds": round(time.monotonic() - started, 6),
                "rows_per_second": round(
                    rows / max(time.monotonic() - started, 0.000001), 3
                ),
                "peak_rss_mb": peak_rss,
                "max_peak_rss_mb": float(max_peak_rss_mb),
            },
            "partitions": partitions,
            "limitations": [
                "Explicit unresolved actor states are preserved and require review rather than forced identity merges.",
                "Local materialization does not prove durable public-origin publication or restore.",
                "This ledger is dominated by parliamentary facts and does not imply complete money, implementation, enforcement, audit, or outcome coverage.",
            ],
        }
        if enforce and not analytical_gate_passed:
            failed = [key for key, value in checks.items() if not value]
            raise RuntimeError("analytical partition gate failed: " + ", ".join(failed))
        manifest_path = staging_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging_root.rename(output_root)
    except BaseException:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
    return manifest


__all__ = [
    "ACCOUNTABILITY_LEDGER_CONTRACT",
    "export_accountability_partitions",
    "scan_accountability_partitions",
]
