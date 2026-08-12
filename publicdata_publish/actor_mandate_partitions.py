"""Typed, incremental Parquet publication for actor-mandate facts."""

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

ACTOR_MANDATE_CONTRACT = SemanticLaneContract(
    lane="actor_mandates",
    transformer_version="actor_mandates_public_v1",
    id_column="mandate_id",
    year_column="mandate_year",
    schema=(
        {"name": "mandate_id", "type": "int64", "nullable": False},
        {"name": "person_id", "type": "int64", "nullable": False},
        {"name": "full_name", "type": "string", "nullable": False},
        {"name": "given_name", "type": "string", "nullable": True},
        {"name": "family_name", "type": "string", "nullable": True},
        {"name": "person_canonical_key", "type": "string", "nullable": False},
        {"name": "gender_code", "type": "string", "nullable": True},
        {"name": "birth_date", "type": "string", "nullable": True},
        {"name": "identity_state", "type": "string", "nullable": False},
        {"name": "source_identifiers", "type": "list_string", "nullable": False},
        {"name": "aliases", "type": "list_string", "nullable": False},
        {"name": "institution_id", "type": "int64", "nullable": False},
        {"name": "institution_name", "type": "string", "nullable": False},
        {"name": "party_id", "type": "int64", "nullable": True},
        {"name": "party_name", "type": "string", "nullable": True},
        {"name": "party_acronym", "type": "string", "nullable": True},
        {"name": "role_id", "type": "int64", "nullable": True},
        {"name": "role_title", "type": "string", "nullable": False},
        {"name": "normalized_role_title", "type": "string", "nullable": True},
        {"name": "level", "type": "string", "nullable": False},
        {"name": "admin_level_code", "type": "string", "nullable": True},
        {"name": "territory_code", "type": "string", "nullable": False},
        {"name": "territory_id", "type": "int64", "nullable": True},
        {"name": "start_date", "type": "string", "nullable": True},
        {"name": "end_date", "type": "string", "nullable": True},
        {"name": "is_active", "type": "int64", "nullable": False},
        {"name": "mandate_year", "type": "string", "nullable": False},
        {"name": "source_id", "type": "string", "nullable": False},
        {"name": "source_record_id", "type": "string", "nullable": False},
        {"name": "source_record_pk", "type": "int64", "nullable": True},
        {"name": "source_snapshot_date", "type": "string", "nullable": True},
        {"name": "source_url", "type": "string", "nullable": True},
        {"name": "source_url_scope", "type": "string", "nullable": True},
        {"name": "lineage_state", "type": "string", "nullable": False},
        {"name": "jurisdiction", "type": "string", "nullable": False},
    ),
)


ACTOR_MANDATE_SQL = """
SELECT
  m.mandate_id,
  m.person_id,
  p.full_name,
  p.given_name,
  p.family_name,
  p.canonical_key AS person_canonical_key,
  COALESCE(g.code, NULLIF(p.gender, '')) AS gender_code,
  p.birth_date,
  COALESCE(
    (
      SELECT json_group_array(
        identifier.namespace || ':' || identifier.value
        ORDER BY identifier.namespace, identifier.value,
          identifier.person_identifier_id
      )
      FROM person_identifiers AS identifier
      WHERE identifier.person_id = p.person_id
    ),
    '[]'
  ) AS identifiers_json,
  COALESCE(
    (
      SELECT json_group_array(
        alias.alias
        ORDER BY alias.canonical_alias, alias.person_name_alias_id
      )
      FROM person_name_aliases AS alias
      WHERE alias.person_id = p.person_id
    ),
    '[]'
  ) AS aliases_json,
  m.institution_id,
  institution.name AS institution_name,
  m.party_id,
  party.name AS party_name,
  party.acronym AS party_acronym,
  m.role_id,
  m.role_title,
  role.title AS normalized_role_title,
  m.level,
  admin.code AS admin_level_code,
  m.territory_code,
  m.territory_id,
  m.start_date,
  m.end_date,
  m.is_active,
  CASE
    WHEN substr(COALESCE(NULLIF(m.start_date, ''), m.source_snapshot_date, ''), 1, 4)
      GLOB '[12][0-9][0-9][0-9]'
    THEN substr(COALESCE(NULLIF(m.start_date, ''), m.source_snapshot_date, ''), 1, 4)
    ELSE 'unknown'
  END AS mandate_year,
  m.source_id,
  m.source_record_id,
  m.source_record_pk,
  m.source_snapshot_date,
  source.default_url AS source_default_url,
  public_jurisdiction(m.level) AS jurisdiction
FROM mandates AS m
JOIN persons AS p ON p.person_id = m.person_id
JOIN institutions AS institution ON institution.institution_id = m.institution_id
JOIN sources AS source ON source.source_id = m.source_id
LEFT JOIN parties AS party ON party.party_id = m.party_id
LEFT JOIN roles AS role ON role.role_id = m.role_id
LEFT JOIN admin_levels AS admin ON admin.admin_level_id = m.admin_level_id
LEFT JOIN genders AS g ON g.gender_id = p.gender_id
ORDER BY
  m.source_id,
  m.level,
  CASE
    WHEN substr(COALESCE(NULLIF(m.start_date, ''), m.source_snapshot_date, ''), 1, 4)
      GLOB '[12][0-9][0-9][0-9]'
    THEN substr(COALESCE(NULLIF(m.start_date, ''), m.source_snapshot_date, ''), 1, 4)
    ELSE 'unknown'
  END,
  m.mandate_id
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _integer(value: Any) -> int | None:
    return None if value is None else int(value)


def _string_list(value: Any) -> list[str]:
    parsed = json.loads(str(value or "[]"))
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        raise ValueError("identity rollup must be a JSON string list")
    return parsed


def _jurisdiction(level: str) -> str:
    normalized = level.strip().lower()
    if normalized == "europeo":
        return "eu"
    if normalized == "nacional":
        return "es-national"
    if normalized == "autonomico":
        return "es-autonomic"
    if normalized == "municipal":
        return "es-municipal"
    return "es-" + safe_component(normalized)


def _identity_state(
    row: sqlite3.Row,
    identifiers: list[str],
    aliases: list[str],
) -> str:
    if identifiers:
        return "source_identifier_present"
    if row["source_record_pk"] is not None:
        return "source_record_present"
    if aliases:
        return "alias_only"
    return "observed_label_only"


def _lineage_state(row: sqlite3.Row, source_url: str | None) -> str:
    if row["source_record_pk"] is not None:
        return "source_record"
    if row["source_record_id"] not in (None, ""):
        return "source_scoped_record_id"
    if source_url:
        return "source_default_url"
    return "missing"


def _public_row(row: sqlite3.Row) -> dict[str, Any]:
    source_url = public_http_url(row["source_default_url"])
    identifiers = _string_list(row["identifiers_json"])
    aliases = _string_list(row["aliases_json"])
    return {
        "mandate_id": int(row["mandate_id"]),
        "person_id": int(row["person_id"]),
        "full_name": str(row["full_name"]),
        "given_name": _text(row["given_name"]),
        "family_name": _text(row["family_name"]),
        "person_canonical_key": str(row["person_canonical_key"]),
        "gender_code": _text(row["gender_code"]),
        "birth_date": _text(row["birth_date"]),
        "identity_state": _identity_state(row, identifiers, aliases),
        "source_identifiers": identifiers,
        "aliases": aliases,
        "institution_id": int(row["institution_id"]),
        "institution_name": str(row["institution_name"]),
        "party_id": _integer(row["party_id"]),
        "party_name": _text(row["party_name"]),
        "party_acronym": _text(row["party_acronym"]),
        "role_id": _integer(row["role_id"]),
        "role_title": str(row["role_title"]),
        "normalized_role_title": _text(row["normalized_role_title"]),
        "level": str(row["level"]),
        "admin_level_code": _text(row["admin_level_code"]),
        "territory_code": str(row["territory_code"]),
        "territory_id": _integer(row["territory_id"]),
        "start_date": _text(row["start_date"]),
        "end_date": _text(row["end_date"]),
        "is_active": int(row["is_active"]),
        "mandate_year": str(row["mandate_year"]),
        "source_id": str(row["source_id"]),
        "source_record_id": str(row["source_record_id"]),
        "source_record_pk": _integer(row["source_record_pk"]),
        "source_snapshot_date": _text(row["source_snapshot_date"]),
        "source_url": source_url,
        "source_url_scope": "source_default" if source_url else None,
        "lineage_state": _lineage_state(row, source_url),
        "jurisdiction": str(row["jurisdiction"]),
    }


def _iter_rows(db_path: Path) -> Iterator[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.create_function("public_jurisdiction", 1, _jurisdiction, deterministic=True)
    try:
        for row in conn.execute(ACTOR_MANDATE_SQL):
            yield _public_row(row)
    finally:
        conn.close()


def _partition_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["source_id"]),
        str(row["jurisdiction"]),
        str(row["mandate_year"]),
    )


def _partition_id(key: tuple[str, str, str]) -> str:
    return "|".join(key)


def _partition_dir(snapshot_date: str, key: tuple[str, str, str]) -> Path:
    source_id, jurisdiction, year = key
    return Path(
        f"lane={ACTOR_MANDATE_CONTRACT.lane}",
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
        "source_record_rows": 0,
        "lineage_rows": 0,
        "source_identifier_rows": 0,
        "source_record_identity_rows": 0,
        "alias_only_rows": 0,
        "observed_label_only_rows": 0,
        "rows_with_aliases": 0,
        "active_rows": 0,
        "private_token_findings": 0,
        "_digest": hashlib.sha256(),
    }


def scan_actor_mandate_partitions(
    db_path: Path, *, snapshot_date: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    totals = {
        "rows": 0,
        "source_url_rows": 0,
        "source_record_rows": 0,
        "lineage_rows": 0,
        "source_identifier_rows": 0,
        "source_record_identity_rows": 0,
        "alias_only_rows": 0,
        "observed_label_only_rows": 0,
        "rows_with_aliases": 0,
        "source_identifiers_total": 0,
        "aliases_total": 0,
        "active_rows": 0,
        "unknown_year_rows": 0,
        "private_token_findings": 0,
    }
    state_metric = {
        "source_identifier_present": "source_identifier_rows",
        "source_record_present": "source_record_identity_rows",
        "alias_only": "alias_only_rows",
        "observed_label_only": "observed_label_only_rows",
    }
    partitions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: tuple[str, str, str] | None = None
    previous_id: int | None = None
    for row in _iter_rows(db_path):
        key = _partition_key(row)
        if current_key != key:
            if current is not None:
                current["input_sha256"] = current.pop("_digest").hexdigest()
                partitions.append(current)
            current_key = key
            current = _new_partition(snapshot_date, key)
            previous_id = None
        assert current is not None
        row_id = int(row["mandate_id"])
        if previous_id is not None and row_id <= previous_id:
            raise RuntimeError("actor-mandate input is not ordered within partition")
        previous_id = row_id
        current["rows"] += 1
        current["min_id"] = (
            row_id if current["min_id"] is None else min(current["min_id"], row_id)
        )
        current["max_id"] = (
            row_id if current["max_id"] is None else max(current["max_id"], row_id)
        )
        for metric, field in (
            ("source_url_rows", "source_url"),
            ("source_record_rows", "source_record_pk"),
        ):
            if row[field] not in (None, ""):
                current[metric] += 1
                totals[metric] += 1
        if row["lineage_state"] != "missing":
            current["lineage_rows"] += 1
            totals["lineage_rows"] += 1
        metric = state_metric[str(row["identity_state"])]
        current[metric] += 1
        totals[metric] += 1
        identifiers = list(row["source_identifiers"])
        aliases = list(row["aliases"])
        totals["source_identifiers_total"] += len(identifiers)
        totals["aliases_total"] += len(aliases)
        if aliases:
            current["rows_with_aliases"] += 1
            totals["rows_with_aliases"] += 1
        if int(row["is_active"]):
            current["active_rows"] += 1
            totals["active_rows"] += 1
        if row["mandate_year"] == "unknown":
            totals["unknown_year_rows"] += 1
        findings = private_token_findings(row)
        current["private_token_findings"] += findings
        totals["private_token_findings"] += findings
        current["_digest"].update(ACTOR_MANDATE_CONTRACT.canonical_row_bytes(row))
        totals["rows"] += 1
    if current is not None:
        current["input_sha256"] = current.pop("_digest").hexdigest()
        partitions.append(current)
    return partitions, totals


def _database_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        mandates = int(conn.execute("SELECT COUNT(*) FROM mandates").fetchone()[0])
        joined = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM mandates AS m
                JOIN persons AS p ON p.person_id = m.person_id
                JOIN institutions AS i ON i.institution_id = m.institution_id
                JOIN sources AS s ON s.source_id = m.source_id
                """
            ).fetchone()[0]
        )
        distinct_ids = int(
            conn.execute("SELECT COUNT(DISTINCT mandate_id) FROM mandates").fetchone()[
                0
            ]
        )
        people = int(
            conn.execute("SELECT COUNT(DISTINCT person_id) FROM mandates").fetchone()[0]
        )
        return {
            "mandate_rows": mandates,
            "joined_rows": joined,
            "distinct_mandate_ids": distinct_ids,
            "distinct_people": people,
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
        and payload.get("lane") == ACTOR_MANDATE_CONTRACT.lane
        and payload.get("transformer_version")
        == ACTOR_MANDATE_CONTRACT.transformer_version
        and payload.get("schema_sha256") == ACTOR_MANDATE_CONTRACT.schema_sha256
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


def export_actor_mandate_partitions(
    *,
    db_path: Path,
    output_root: Path,
    snapshot_date: str,
    compression: str = "zstd",
    row_group_rows: int = 25_000,
    max_file_rows: int = 100_000,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    min_rows: int = 1,
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
    partitions, scan_totals = scan_actor_mandate_partitions(
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
                            contract=ACTOR_MANDATE_CONTRACT,
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
        identity_state_rows = sum(
            int(scan_totals[key])
            for key in (
                "source_identifier_rows",
                "source_record_identity_rows",
                "alias_only_rows",
                "observed_label_only_rows",
            )
        )
        peak_rss = peak_rss_mb()
        checks = {
            "minimum_rows": rows >= int(min_rows),
            "database_join_balance": database_counts["mandate_rows"]
            == database_counts["joined_rows"]
            == rows,
            "distinct_mandate_ids": database_counts["distinct_mandate_ids"] == rows,
            "source_url_complete": scan_totals["source_url_rows"] == rows,
            "lineage_complete": scan_totals["lineage_rows"] == rows,
            "identity_state_complete": identity_state_rows == rows,
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
            "representative_100k_real_rows": rows >= 100_000,
            "million_real_rows": rows >= 1_000_000,
            "external_identity_quality_verified": False,
            "durable_public_origin_verified": False,
        }
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "snapshot_date": snapshot_date,
            "lane": ACTOR_MANDATE_CONTRACT.lane,
            "transformer_version": ACTOR_MANDATE_CONTRACT.transformer_version,
            "schema": ACTOR_MANDATE_CONTRACT.schema,
            "schema_sha256": ACTOR_MANDATE_CONTRACT.schema_sha256,
            "partition_contract": {
                "strategy": "semantic_hive_coarse_jurisdiction",
                "keys": ["snapshot_date", "source_id", "jurisdiction", "year"],
                "ordering": ["source_id", "level", "year", "mandate_id"],
                "row_group_rows": int(row_group_rows),
                "max_file_rows": int(max_file_rows),
                "compression": compression,
                "exact_territory_retained_as_column": True,
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
                "table": "mandates",
                "person_table": "persons",
                "identifier_table": "person_identifiers",
                "alias_table": "person_name_aliases",
                "raw_payload_published": False,
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
                "source_identifier": round(
                    scan_totals["source_identifier_rows"] / rows, 8
                )
                if rows
                else 0.0,
            },
            "identity_assurance": "source_scoped_states_not_external_identity",
            "checks": checks,
            "analytical_partition_gate_passed": analytical_gate_passed,
            "promotion_checks": promotion_checks,
            "promotion_gate_passed": all(promotion_checks.values()),
            "publication_status": "local_generated_not_published",
            "capacity_class": "below_s1_100k" if rows < 100_000 else "s1_100k",
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
                "Source identifiers and aliases are preserved as evidence; they do not prove external identity equivalence.",
                "The real corpus remains below the representative 100k and one-million actor promotion classes.",
                "Local materialization does not prove durable public-origin publication or restore.",
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
    "ACTOR_MANDATE_CONTRACT",
    "export_actor_mandate_partitions",
    "scan_actor_mandate_partitions",
]
