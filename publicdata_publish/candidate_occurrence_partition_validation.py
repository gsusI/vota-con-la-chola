"""Independent full-row validation for candidate-occurrence Parquet."""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, date, datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .candidate_occurrence_partitions import (
    CANDIDATE_OCCURRENCE_CONTRACT,
    election_scope,
)
from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    peak_rss_mb,
    private_token_findings,
    safe_child,
    safe_component,
    sha256_file,
)


VALIDATION_SCHEMA_VERSION = "candidate_occurrence_partition_validation_v1"
NON_PUBLICATION_COLUMNS = {"raw_payload"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _is_public_url(value: Any) -> bool:
    if value in (None, ""):
        return False
    try:
        parsed = urlsplit(str(value))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _expected_occurrence_id(row: dict[str, Any]) -> str:
    parts = (
        row["election_type_code"],
        row["election_year"],
        row["election_month"],
        row["election_round"],
        row["province_code"],
        row["district_code"],
        row["candidate_scope_code"],
        row["party_source_code"],
        row["candidate_order"],
        row["candidate_type_code"],
    )
    encoded = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return "infoelectoral-candidate:" + hashlib.sha256(
        encoded.encode("utf-8")
    ).hexdigest()


def _expected_relative_dir(manifest: dict[str, Any], values: dict[str, Any]) -> str:
    return Path(
        f"lane={CANDIDATE_OCCURRENCE_CONTRACT.lane}",
        f"snapshot_date={safe_component(str(manifest.get('snapshot_date') or ''))}",
        f"election_type={safe_component(str(values.get('election_type') or ''))}",
        f"year={safe_component(str(values.get('year') or ''))}",
    ).as_posix()


def _valid_sha256(value: Any) -> bool:
    token = str(value or "")
    return len(token) == 64 and all(char in "0123456789abcdef" for char in token)


def validate_candidate_occurrence_partitions(
    *,
    root: Path,
    manifest_path: Path | None = None,
    batch_rows: int = 10_000,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
    workers: int = 1,
    _partition_ids: tuple[str, ...] | None = None,
    _partial_scope: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required; install the project parquet extra"
        ) from exc

    if batch_rows <= 0:
        raise ValueError("batch-rows must be positive")
    if workers <= 0:
        raise ValueError("workers must be positive")
    root = Path(root)
    manifest_path = Path(manifest_path) if manifest_path else root / "manifest.json"
    if not root.is_dir():
        raise FileNotFoundError(root)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if workers > 1 and _partition_ids is None:
        return _validate_parallel_candidate_occurrence_partitions(
            root=root,
            manifest_path=manifest_path,
            manifest=manifest,
            batch_rows=batch_rows,
            min_rows=min_rows,
            max_peak_rss_mb=max_peak_rss_mb,
            workers=workers,
            started=started,
        )
    expected_schema = CANDIDATE_OCCURRENCE_CONTRACT.arrow_schema()

    expected_paths: set[str] = set()
    seen_partition_ids: set[str] = set()
    duplicate_paths = 0
    duplicate_partition_ids = 0
    files_present = True
    checksums_valid = True
    schemas_valid = True
    file_rows_valid = True
    file_minmax_valid = True
    partition_rows_valid = True
    partition_hashes_valid = True
    partition_values_valid = True
    ids_sorted = True
    occurrence_ids_valid = True
    source_record_ids_valid = True
    urls_public = True
    source_ids_valid = True
    lineage_valid = True
    binary_fields_valid = True
    election_fields_valid = True
    source_evidence_valid = True
    observation_windows_valid = True

    rows_total = 0
    files_total = 0
    bytes_total = 0
    source_url_rows = 0
    source_record_rows = 0
    elected_rows = 0
    present_rows = 0
    birth_date_rows = 0
    birth_date_source_rows = 0
    dni_rows = 0
    public_identity_fields_valid = True
    private_findings = 0
    partition_reports: list[dict[str, Any]] = []

    manifest_partitions = list(manifest.get("partitions") or [])
    if _partition_ids is not None:
        selected = set(_partition_ids)
        manifest_partitions = [
            partition
            for partition in manifest_partitions
            if str(partition.get("partition_id") or "") in selected
        ]
        if len(manifest_partitions) != len(selected):
            raise ValueError("candidate validation partition selection drift")

    for partition in manifest_partitions:
        partition_id = str(partition.get("partition_id") or "")
        if partition_id in seen_partition_ids:
            duplicate_partition_ids += 1
        seen_partition_ids.add(partition_id)
        digest = hashlib.sha256()
        partition_rows = 0
        partition_min_id: str | None = None
        partition_max_id: str | None = None
        partition_previous_id: str | None = None
        values = dict(partition.get("values") or {})
        expected_relative_dir = _expected_relative_dir(manifest, values)
        expected_partition_id = "|".join(
            str(values.get(key) or "") for key in ("election_type", "year")
        )
        if str(partition.get("relative_dir") or "") != expected_relative_dir:
            partition_values_valid = False
        if partition_id != expected_partition_id:
            partition_values_valid = False
        if str(values.get("snapshot_date") or "") != str(
            manifest.get("snapshot_date") or ""
        ):
            partition_values_valid = False
        partition_metrics = {
            "source_url_rows": 0,
            "source_record_rows": 0,
            "elected_rows": 0,
            "present_rows": 0,
            "birth_date_rows": 0,
            "birth_date_source_rows": 0,
            "dni_rows": 0,
            "private_token_findings": 0,
        }
        partition_file_reports: list[dict[str, Any]] = []
        for file_meta in list(partition.get("files") or []):
            relative = str(file_meta.get("path") or "")
            if relative in expected_paths:
                duplicate_paths += 1
            expected_paths.add(relative)
            if Path(relative).parent.as_posix() != expected_relative_dir:
                partition_values_valid = False
            file_path = safe_child(root, relative)
            files_total += 1
            if file_path is None or not file_path.is_file():
                files_present = False
                continue
            actual_bytes = int(file_path.stat().st_size)
            actual_sha256 = sha256_file(file_path)
            bytes_total += actual_bytes
            if actual_bytes != int(file_meta.get("bytes") or -1):
                checksums_valid = False
            if actual_sha256 != str(file_meta.get("sha256") or ""):
                checksums_valid = False
            parquet_file = pq.ParquetFile(file_path)
            if not parquet_file.schema_arrow.equals(expected_schema, check_metadata=True):
                schemas_valid = False
            expected_file_rows = int(file_meta.get("rows") or 0)
            if int(parquet_file.metadata.num_rows) != expected_file_rows:
                file_rows_valid = False
            file_rows = 0
            file_min_id: str | None = None
            file_max_id: str | None = None
            for batch in parquet_file.iter_batches(batch_size=batch_rows):
                columns = {
                    name: batch.column(index).to_pylist()
                    for index, name in enumerate(CANDIDATE_OCCURRENCE_CONTRACT.columns)
                }
                for row_index in range(batch.num_rows):
                    row = {
                        name: columns[name][row_index]
                        for name in CANDIDATE_OCCURRENCE_CONTRACT.columns
                    }
                    occurrence_id = str(row["candidate_occurrence_id"])
                    if (
                        partition_previous_id is not None
                        and occurrence_id <= partition_previous_id
                    ):
                        ids_sorted = False
                    partition_previous_id = occurrence_id
                    file_min_id = occurrence_id if file_min_id is None else min(file_min_id, occurrence_id)
                    file_max_id = occurrence_id if file_max_id is None else max(file_max_id, occurrence_id)
                    partition_min_id = occurrence_id if partition_min_id is None else min(partition_min_id, occurrence_id)
                    partition_max_id = occurrence_id if partition_max_id is None else max(partition_max_id, occurrence_id)

                    if occurrence_id != _expected_occurrence_id(row):
                        occurrence_ids_valid = False
                    if str(row["source_record_id"]) != occurrence_id:
                        source_record_ids_valid = False
                    if str(row["election_type_code"]) != str(values.get("election_type")):
                        partition_values_valid = False
                    if str(row["election_year"]) != str(values.get("year")):
                        partition_values_valid = False
                    if row["election_scope"] != election_scope(str(row["election_type_code"])):
                        election_fields_valid = False
                    try:
                        election_date = date.fromisoformat(str(row["election_date"]))
                    except ValueError:
                        election_fields_valid = False
                    else:
                        if election_date.year != int(row["election_year"]):
                            election_fields_valid = False
                        if election_date.month != int(row["election_month"]):
                            election_fields_valid = False
                    if int(row["candidate_order"]) < 0:
                        election_fields_valid = False
                    if int(row["is_elected"]) not in (0, 1):
                        binary_fields_valid = False
                    if int(row["is_present"]) not in (0, 1):
                        binary_fields_valid = False
                    if int(row["is_elected"]):
                        elected_rows += 1
                        partition_metrics["elected_rows"] += 1
                    if int(row["is_present"]):
                        present_rows += 1
                        partition_metrics["present_rows"] += 1
                    birth_date = str(row["birth_date"] or "").strip()
                    birth_date_source = str(row["birth_date_source"] or "").strip()
                    dni = str(row["dni"] or "").strip()
                    if birth_date:
                        birth_date_rows += 1
                        partition_metrics["birth_date_rows"] += 1
                    if birth_date_source:
                        birth_date_source_rows += 1
                        partition_metrics["birth_date_source_rows"] += 1
                        expected_birth_date = birth_date_source
                        if len(birth_date_source) == 8 and birth_date_source.isdigit():
                            try:
                                expected_birth_date = datetime.strptime(
                                    birth_date_source, "%d%m%Y"
                                ).date().isoformat()
                            except ValueError:
                                pass
                        if birth_date != expected_birth_date:
                            public_identity_fields_valid = False
                    elif birth_date:
                        public_identity_fields_valid = False
                    if dni:
                        dni_rows += 1
                        partition_metrics["dni_rows"] += 1
                    if _is_public_url(row["source_url"]):
                        source_url_rows += 1
                        partition_metrics["source_url_rows"] += 1
                    else:
                        urls_public = False
                    if row["source_id"] != "infoelectoral_candidates":
                        source_ids_valid = False
                    if int(row["source_record_pk"]) < 1:
                        source_evidence_valid = False
                    else:
                        source_record_rows += 1
                        partition_metrics["source_record_rows"] += 1
                    if row["lineage_state"] != "source_record":
                        lineage_valid = False
                    if not _valid_sha256(row["source_content_sha256"]):
                        source_evidence_valid = False
                    member_name = Path(str(row["source_member_name"])).name.upper()
                    if not member_name.startswith("04") or not member_name.endswith(".DAT"):
                        source_evidence_valid = False
                    if int(row["source_line_number"]) < 1:
                        source_evidence_valid = False
                    if str(row["first_seen_snapshot_date"]) > str(
                        row["last_seen_snapshot_date"]
                    ):
                        observation_windows_valid = False
                    row_private_findings = private_token_findings(row)
                    private_findings += row_private_findings
                    partition_metrics["private_token_findings"] += row_private_findings
                    digest.update(CANDIDATE_OCCURRENCE_CONTRACT.canonical_row_bytes(row))
                    file_rows += 1
                    partition_rows += 1
                    rows_total += 1
            if file_rows != expected_file_rows:
                file_rows_valid = False
            if file_min_id != file_meta.get("min_id"):
                file_minmax_valid = False
            if file_max_id != file_meta.get("max_id"):
                file_minmax_valid = False
            partition_file_reports.append(
                {
                    "path": relative,
                    "rows": file_rows,
                    "bytes": actual_bytes,
                    "sha256": actual_sha256,
                }
            )
        if partition_rows != int(partition.get("rows") or 0):
            partition_rows_valid = False
        if partition_min_id != partition.get("min_id"):
            partition_rows_valid = False
        if partition_max_id != partition.get("max_id"):
            partition_rows_valid = False
        if any(
            key not in partition or int(partition.get(key) or 0) != value
            for key, value in partition_metrics.items()
        ):
            partition_rows_valid = False
        actual_input_sha256 = digest.hexdigest()
        if actual_input_sha256 != str(partition.get("input_sha256") or ""):
            partition_hashes_valid = False
        partition_reports.append(
            {
                "partition_id": partition_id,
                "rows": partition_rows,
                "files": partition_file_reports,
                "input_sha256": actual_input_sha256,
            }
        )

    actual_paths = (
        expected_paths
        if _partial_scope
        else {
            path.relative_to(root).as_posix() for path in root.rglob("*.parquet")
        }
    )
    peak_rss = peak_rss_mb()
    totals = dict(manifest.get("totals") or {})
    calculated_totals = {
        "rows": rows_total,
        "files": files_total,
        "parquet_bytes": bytes_total,
        "partitions": len(partition_reports),
        "source_url_rows": source_url_rows,
        "source_record_rows": source_record_rows,
        "elected_rows": elected_rows,
        "present_rows": present_rows,
        "birth_date_rows": birth_date_rows,
        "birth_date_source_rows": birth_date_source_rows,
        "dni_rows": dni_rows,
        "private_token_findings": private_findings,
    }
    expected_coverage = {
        "source_url": round(source_url_rows / rows_total, 8) if rows_total else 0.0,
        "source_record": round(source_record_rows / rows_total, 8)
        if rows_total
        else 0.0,
        "present": round(present_rows / rows_total, 8) if rows_total else 0.0,
        "elected": round(elected_rows / rows_total, 8) if rows_total else 0.0,
        "birth_date": round(birth_date_rows / rows_total, 8)
        if rows_total
        else 0.0,
        "birth_date_source": round(birth_date_source_rows / rows_total, 8)
        if rows_total
        else 0.0,
        "dni": round(dni_rows / rows_total, 8) if rows_total else 0.0,
    }
    source_contract = dict(manifest.get("source") or {})
    source_database = dict(manifest.get("source_database") or {})
    contract_columns = set(CANDIDATE_OCCURRENCE_CONTRACT.columns)
    checks = {
        "manifest_schema": manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
        "lane": manifest.get("lane") == CANDIDATE_OCCURRENCE_CONTRACT.lane,
        "transformer_version": manifest.get("transformer_version")
        == CANDIDATE_OCCURRENCE_CONTRACT.transformer_version,
        "schema_sha256": manifest.get("schema_sha256")
        == CANDIDATE_OCCURRENCE_CONTRACT.schema_sha256,
        "manifest_schema_definition": manifest.get("schema")
        == list(CANDIDATE_OCCURRENCE_CONTRACT.schema),
        "raw_payload_excluded": NON_PUBLICATION_COLUMNS.isdisjoint(contract_columns),
        "public_domain_identity_contract": source_contract.get(
            "raw_payload_published"
        )
        is False
        and source_contract.get("official_archive_publication")
        == "publishable_with_source_provenance"
        and set(source_contract.get("public_domain_identity_fields") or [])
        == {"birth_date", "birth_date_source", "dni"},
        "minimum_rows": True if _partial_scope else rows_total >= int(min_rows),
        "all_files_present": files_present,
        "no_duplicate_manifest_paths": duplicate_paths == 0,
        "partition_ids_unique": duplicate_partition_ids == 0,
        "no_extra_parquet_files": True
        if _partial_scope
        else actual_paths == expected_paths,
        "checksums_and_bytes": checksums_valid,
        "parquet_schemas": schemas_valid,
        "file_rows": file_rows_valid,
        "file_minmax": file_minmax_valid,
        "partition_rows": partition_rows_valid,
        "partition_hashes": partition_hashes_valid,
        "partition_values": partition_values_valid,
        "occurrence_ids_sorted_within_partitions": ids_sorted,
        "occurrence_ids_match_natural_key": occurrence_ids_valid,
        "source_record_ids_match_occurrence_ids": source_record_ids_valid,
        "source_urls_complete_and_public": urls_public
        and source_url_rows == rows_total,
        "source_ids_valid": source_ids_valid,
        "source_records_complete": source_record_rows == rows_total,
        "lineage_complete": lineage_valid,
        "binary_fields_valid": binary_fields_valid,
        "election_fields_valid": election_fields_valid,
        "source_evidence_valid": source_evidence_valid,
        "observation_windows_valid": observation_windows_valid,
        "public_identity_fields_valid": public_identity_fields_valid,
        "public_birth_dates_retained_exactly": True
        if _partial_scope
        else int(source_database.get("source_birth_date_rows") or 0)
        == birth_date_rows,
        "public_source_birth_dates_retained_exactly": True
        if _partial_scope
        else int(source_database.get("source_birth_date_source_rows") or 0)
        == birth_date_source_rows,
        "public_dni_retained_exactly": True
        if _partial_scope
        else int(source_database.get("source_dni_rows") or 0) == dni_rows,
        "manifest_row_total": True
        if _partial_scope
        else rows_total == int(totals.get("rows") or -1),
        "manifest_file_total": True
        if _partial_scope
        else files_total == int(totals.get("files") or -1),
        "manifest_byte_total": True
        if _partial_scope
        else bytes_total == int(totals.get("parquet_bytes") or -1),
        "manifest_metric_totals": True
        if _partial_scope
        else all(
            key in totals and int(totals.get(key) or 0) == value
            for key, value in calculated_totals.items()
        ),
        "manifest_coverage": True
        if _partial_scope
        else manifest.get("coverage") == expected_coverage,
        "no_private_tokens": private_findings == 0,
        "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
    }
    status = "ok" if all(checks.values()) else "failed"
    elapsed = time.monotonic() - started
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "status": status,
        "manifest_file": manifest_path.name,
        "root_name": root.name,
        "checks": checks,
        "totals": calculated_totals,
        "coverage": expected_coverage,
        "performance": {
            "peak_rss_mb": peak_rss,
            "max_peak_rss_mb": float(max_peak_rss_mb),
            "batch_rows": int(batch_rows),
            "total_seconds": round(elapsed, 6),
            "rows_per_second": round(
                rows_total / max(elapsed, 0.000001), 3
            ),
            "workers": 1,
            "validation_mode": (
                "partition_worker" if _partial_scope else "sequential"
            ),
        },
        "identity_assurance": manifest.get("identity_assurance"),
        "publication_status": manifest.get("publication_status"),
        "analytical_partition_gate_passed": all(checks.values()),
        "promotion_gate_passed": bool(manifest.get("promotion_gate_passed"))
        and all(checks.values()),
        "partitions": partition_reports,
    }


def _validate_partition_process(
    args: tuple[str, str, str, int, float],
) -> dict[str, Any]:
    root, manifest_path, partition_id, batch_rows, max_peak_rss_mb = args
    return validate_candidate_occurrence_partitions(
        root=Path(root),
        manifest_path=Path(manifest_path),
        batch_rows=batch_rows,
        min_rows=0,
        max_peak_rss_mb=max_peak_rss_mb,
        workers=1,
        _partition_ids=(partition_id,),
        _partial_scope=True,
    )


def _validate_parallel_candidate_occurrence_partitions(
    *,
    root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    batch_rows: int,
    min_rows: int,
    max_peak_rss_mb: float,
    workers: int,
    started: float,
) -> dict[str, Any]:
    partitions = list(manifest.get("partitions") or [])
    if len(partitions) < 2:
        return validate_candidate_occurrence_partitions(
            root=root,
            manifest_path=manifest_path,
            batch_rows=batch_rows,
            min_rows=min_rows,
            max_peak_rss_mb=max_peak_rss_mb,
            workers=1,
        )
    workers_used = min(workers, len(partitions))
    tasks = [
        (
            str(root),
            str(manifest_path),
            str(partition.get("partition_id") or ""),
            batch_rows,
            max_peak_rss_mb,
        )
        for partition in partitions
    ]
    with ProcessPoolExecutor(
        max_workers=workers_used,
        mp_context=get_context("spawn"),
    ) as executor:
        worker_reports = list(executor.map(_validate_partition_process, tasks))

    total_keys = (
        "rows",
        "files",
        "parquet_bytes",
        "partitions",
        "source_url_rows",
        "source_record_rows",
        "elected_rows",
        "present_rows",
        "birth_date_rows",
        "birth_date_source_rows",
        "dni_rows",
        "private_token_findings",
    )
    calculated_totals = {
        key: sum(int(report["totals"].get(key) or 0) for report in worker_reports)
        for key in total_keys
    }
    rows_total = calculated_totals["rows"]
    expected_coverage = {
        "source_url": round(
            calculated_totals["source_url_rows"] / rows_total, 8
        )
        if rows_total
        else 0.0,
        "source_record": round(
            calculated_totals["source_record_rows"] / rows_total, 8
        )
        if rows_total
        else 0.0,
        "present": round(calculated_totals["present_rows"] / rows_total, 8)
        if rows_total
        else 0.0,
        "elected": round(calculated_totals["elected_rows"] / rows_total, 8)
        if rows_total
        else 0.0,
        "birth_date": round(calculated_totals["birth_date_rows"] / rows_total, 8)
        if rows_total
        else 0.0,
        "birth_date_source": round(
            calculated_totals["birth_date_source_rows"] / rows_total, 8
        )
        if rows_total
        else 0.0,
        "dni": round(calculated_totals["dni_rows"] / rows_total, 8)
        if rows_total
        else 0.0,
    }
    partition_ids = [str(item.get("partition_id") or "") for item in partitions]
    manifest_paths = [
        str(file_meta.get("path") or "")
        for partition in partitions
        for file_meta in list(partition.get("files") or [])
    ]
    expected_paths = set(manifest_paths)
    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*.parquet")
    }
    worker_peak_rss = [
        float(report["performance"].get("peak_rss_mb") or 0.0)
        for report in worker_reports
    ]
    parent_peak_rss = peak_rss_mb()
    max_worker_peak_rss = max(worker_peak_rss, default=0.0)
    conservative_parallel_peak_rss = round(
        parent_peak_rss + (workers_used * max_worker_peak_rss), 3
    )
    checks = {
        key: all(bool(report["checks"].get(key)) for report in worker_reports)
        for key in worker_reports[0]["checks"]
    }
    totals = dict(manifest.get("totals") or {})
    source_database = dict(manifest.get("source_database") or {})
    checks.update(
        {
            "minimum_rows": rows_total >= int(min_rows),
            "no_duplicate_manifest_paths": len(manifest_paths)
            == len(expected_paths),
            "partition_ids_unique": len(partition_ids) == len(set(partition_ids)),
            "no_extra_parquet_files": actual_paths == expected_paths,
            "manifest_row_total": rows_total == int(totals.get("rows") or -1),
            "manifest_file_total": calculated_totals["files"]
            == int(totals.get("files") or -1),
            "manifest_byte_total": calculated_totals["parquet_bytes"]
            == int(totals.get("parquet_bytes") or -1),
            "manifest_metric_totals": all(
                key in totals and int(totals.get(key) or 0) == value
                for key, value in calculated_totals.items()
            ),
            "manifest_coverage": manifest.get("coverage") == expected_coverage,
            "public_birth_dates_retained_exactly": int(
                source_database.get("source_birth_date_rows") or 0
            )
            == calculated_totals["birth_date_rows"],
            "public_source_birth_dates_retained_exactly": int(
                source_database.get("source_birth_date_source_rows") or 0
            )
            == calculated_totals["birth_date_source_rows"],
            "public_dni_retained_exactly": int(
                source_database.get("source_dni_rows") or 0
            )
            == calculated_totals["dni_rows"],
            "bounded_peak_rss": conservative_parallel_peak_rss
            <= float(max_peak_rss_mb),
        }
    )
    status = "ok" if all(checks.values()) else "failed"
    elapsed = time.monotonic() - started
    partition_reports_by_id = {
        str(report["partitions"][0]["partition_id"]): report["partitions"][0]
        for report in worker_reports
    }
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "status": status,
        "manifest_file": manifest_path.name,
        "root_name": root.name,
        "checks": checks,
        "totals": calculated_totals,
        "coverage": expected_coverage,
        "performance": {
            "peak_rss_mb": parent_peak_rss,
            "worker_peak_rss_mb_max": max_worker_peak_rss,
            "conservative_parallel_peak_rss_mb": (
                conservative_parallel_peak_rss
            ),
            "parallel_peak_bound_method": (
                "parent_peak_plus_workers_times_max_worker_peak"
            ),
            "max_peak_rss_mb": float(max_peak_rss_mb),
            "batch_rows": int(batch_rows),
            "total_seconds": round(elapsed, 6),
            "rows_per_second": round(rows_total / max(elapsed, 0.000001), 3),
            "workers": workers_used,
            "validation_mode": "process_pool_partition_parallel",
        },
        "identity_assurance": manifest.get("identity_assurance"),
        "publication_status": manifest.get("publication_status"),
        "analytical_partition_gate_passed": all(checks.values()),
        "promotion_gate_passed": bool(manifest.get("promotion_gate_passed"))
        and all(checks.values()),
        "partitions": [
            partition_reports_by_id[partition_id] for partition_id in partition_ids
        ],
    }


__all__ = [
    "VALIDATION_SCHEMA_VERSION",
    "validate_candidate_occurrence_partitions",
]
