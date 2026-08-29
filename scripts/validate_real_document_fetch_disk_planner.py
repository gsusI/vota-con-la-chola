#!/usr/bin/env python3
"""Independently reconcile a disk-planned real-document cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from scripts.validate_real_document_fetch_scale_cohort import iter_manifest_rows
except ModuleNotFoundError:
    from validate_real_document_fetch_scale_cohort import iter_manifest_rows


PIPELINE_ID = "real_document_fetch_scale_cohort_v2"
KNOWN_BLOCKED_HOSTS = {
    "contrataciondelestado.es",
    "parlamentodenavarra.es",
    "www.congreso.es",
    "www.senado.es",
}
PROJECTION_FIELDS = (
    "source_pipeline_id",
    "source_id",
    "source_url",
    "source_host",
    "document_kind",
    "validation_mode",
    "size_decile",
    "expected_bytes",
    "expected_content_sha256",
)
EXECUTION_FIELDS = (
    "source_pipeline_id",
    "source_id",
    "provenance_source_id",
    "source_url",
    "source_host",
    "document_kind",
    "validation_mode",
    "size_decile",
    "expected_bytes",
    "expected_content_sha256",
    "captured_raw_path",
    "partition_key",
    "queue_priority",
    "payload",
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repository: {path}") from exc


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def normalized_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(canonical_json(payload))
    provenance = normalized.get("provenance") or {}
    if isinstance(provenance, dict):
        provenance.pop("reference_edges", None)
    return normalized


def validate_reference_edges(payload: dict[str, Any]) -> int:
    provenance = payload.get("provenance") or {}
    if not isinstance(provenance, dict):
        raise ValueError("Parliament provenance is not an object")
    edges = provenance.get("reference_edges") or []
    if not isinstance(edges, list) or not 1 <= len(edges) <= 10_000:
        raise ValueError("Parliament provenance reference-edge count is invalid")
    pairs: list[tuple[str, str]] = []
    for edge in edges:
        if not isinstance(edge, dict) or set(edge) != {"db_ref", "table_name"}:
            raise ValueError("Parliament provenance reference edge is invalid")
        pair = (str(edge.get("db_ref") or ""), str(edge.get("table_name") or ""))
        if not all(pair):
            raise ValueError("Parliament provenance reference edge is empty")
        pairs.append(pair)
    if pairs != sorted(set(pairs)):
        raise ValueError("Parliament provenance reference edges are not sorted unique")
    if provenance.get("db_refs") != sorted({pair[0] for pair in pairs}):
        raise ValueError("Parliament provenance db-ref projection mismatch")
    if provenance.get("table_names") != sorted({pair[1] for pair in pairs}):
        raise ValueError("Parliament provenance table-name projection mismatch")
    return len(pairs)


def open_harness_store(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), uri=True)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA temp_store = FILE;
        PRAGMA journal_mode = DELETE;
        PRAGMA synchronous = FULL;

        CREATE TABLE cohort_rows (
          lane TEXT NOT NULL,
          source_url TEXT NOT NULL,
          source_pipeline_id TEXT NOT NULL,
          source_host TEXT NOT NULL,
          size_decile INTEGER NOT NULL,
          projection_json TEXT NOT NULL,
          normalized_row_json TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          partition_key TEXT NOT NULL,
          queue_priority INTEGER NOT NULL,
          PRIMARY KEY (lane, source_url)
        ) WITHOUT ROWID;
        CREATE INDEX cohort_rows_lane_group_idx
          ON cohort_rows(lane, source_pipeline_id, size_decile, source_url);
        """
    )
    return conn


def stage_lane(
    *,
    conn: sqlite3.Connection,
    lane: str,
    manifest: dict[str, Any],
    manifest_path: Path,
) -> dict[str, Any]:
    schema_version = str(manifest.get("schema_version") or "")
    selection_digest = hashlib.sha256()
    execution_digest = hashlib.sha256()
    logical_digests: dict[tuple[str, int], Any] = {}
    host_ranks: dict[str, int] = {}
    batch: list[tuple[Any, ...]] = []
    rows = 0
    real_policy_rows = 0
    public_information_rows = 0
    blocked_host_rows = 0
    provenance_enrichment_rows = 0
    provenance_reference_pairs = 0
    for row in iter_manifest_rows(manifest=manifest, manifest_path=manifest_path):
        payload = row.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValueError(f"{lane} payload is not an object")
        source_url = str(row.get("source_url") or "")
        source_host = str(row.get("source_host") or "")
        source_pipeline_id = str(row.get("source_pipeline_id") or "")
        size_decile = int(row.get("size_decile") or 0)
        if payload.get("synthetic_or_mock_records_counted") is False:
            real_policy_rows += 1
        else:
            raise ValueError(f"{lane} synthetic/mock policy mismatch: {source_url}")
        if payload.get("official_public_domain_personal_information_retained") is True:
            public_information_rows += 1
        else:
            raise ValueError(f"{lane} public-information policy mismatch: {source_url}")
        if source_host in KNOWN_BLOCKED_HOSTS:
            blocked_host_rows += 1
        if schema_version == "real_document_fetch_scale_cohort_v4" and source_host == "www.parlamentodeandalucia.es":
            provenance_reference_pairs += validate_reference_edges(payload)
            provenance_enrichment_rows += 1
        projection = {field: row.get(field) for field in PROJECTION_FIELDS}
        projection_json = canonical_json(projection)
        selection_digest.update(projection_json.encode("utf-8"))
        selection_digest.update(b"\n")
        if schema_version == "real_document_fetch_scale_cohort_v4":
            queue_priority = -host_ranks.get(source_host, 0)
            host_ranks[source_host] = host_ranks.get(source_host, 0) + 1
        else:
            queue_priority = int(row.get("queue_priority") or 0)
        execution_row = {field: row.get(field) for field in EXECUTION_FIELDS}
        execution_row["queue_priority"] = queue_priority
        execution_digest.update(canonical_json(execution_row).encode("utf-8"))
        execution_digest.update(b"\n")
        normalized_row = {
            **row,
            "payload": normalized_payload(payload),
        }
        normalized_row.pop("queue_priority", None)
        logical_key = (source_pipeline_id, size_decile)
        logical_digest = logical_digests.setdefault(logical_key, hashlib.sha256())
        logical_digest.update(canonical_json(normalized_row).encode("utf-8"))
        logical_digest.update(b"\n")
        batch.append(
            (
                lane,
                source_url,
                source_pipeline_id,
                source_host,
                size_decile,
                projection_json,
                canonical_json(normalized_row),
                canonical_json(payload),
                str(row.get("partition_key") or ""),
                queue_priority,
            )
        )
        rows += 1
        if len(batch) >= 1_000:
            conn.executemany(
                "INSERT INTO cohort_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            batch.clear()
    if batch:
        conn.executemany(
            "INSERT INTO cohort_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
    conn.commit()
    return {
        "rows": rows,
        "selection_sha256": selection_digest.hexdigest(),
        "execution_sha256": execution_digest.hexdigest(),
        "real_policy_rows": real_policy_rows,
        "public_information_rows": public_information_rows,
        "blocked_host_rows": blocked_host_rows,
        "provenance_enrichment_rows": provenance_enrichment_rows,
        "provenance_reference_pairs": provenance_reference_pairs,
        "logical_partition_hashes": {
            f"{key[0]}:size_decile_{key[1]}": digest.hexdigest()
            for key, digest in sorted(logical_digests.items())
        },
    }


def attach_and_validate_queue(
    *, conn: sqlite3.Connection, candidate_db: Path, expected_rows: int
) -> dict[str, Any]:
    candidate_uri = f"{candidate_db.resolve().as_uri()}?mode=ro"
    conn.execute("ATTACH DATABASE ? AS candidate", (candidate_uri,))
    integrity = str(conn.execute("PRAGMA candidate.integrity_check").fetchone()[0])
    foreign_keys = conn.execute("PRAGMA candidate.foreign_key_check").fetchall()
    queue_rows = int(
        conn.execute(
            "SELECT COUNT(*) FROM candidate.pipeline_work_items WHERE pipeline_id = ?",
            (PIPELINE_ID,),
        ).fetchone()[0]
    )
    priority_min, priority_max, distinct_priorities = conn.execute(
        """
        SELECT MIN(priority), MAX(priority), COUNT(DISTINCT priority)
        FROM candidate.pipeline_work_items
        WHERE pipeline_id = ?
        """,
        (PIPELINE_ID,),
    ).fetchone()
    queue_mismatch_rows = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM cohort_rows e
            LEFT JOIN candidate.pipeline_work_items q
              ON q.pipeline_id = ? AND q.item_key = e.source_url
            WHERE e.lane = 'candidate'
              AND (
                q.item_key IS NULL
                OR q.partition_key <> e.partition_key
                OR q.priority <> e.queue_priority
                OR q.payload_json <> e.payload_json
                OR q.state <> 'pending'
                OR q.attempts <> 0
              )
            """,
            (PIPELINE_ID,),
        ).fetchone()[0]
    )
    extra_queue_rows = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM candidate.pipeline_work_items q
            LEFT JOIN cohort_rows e
              ON e.lane = 'candidate' AND e.source_url = q.item_key
            WHERE q.pipeline_id = ? AND e.source_url IS NULL
            """,
            (PIPELINE_ID,),
        ).fetchone()[0]
    )
    fetch_rows = int(
        conn.execute("SELECT COUNT(*) FROM candidate.document_fetches").fetchone()[0]
    )
    document_rows = int(
        conn.execute("SELECT COUNT(*) FROM candidate.text_documents").fetchone()[0]
    )
    conn.execute("DETACH DATABASE candidate")
    return {
        "database_integrity": integrity,
        "foreign_key_violations": len(foreign_keys),
        "queue_rows": queue_rows,
        "priority_min": int(priority_min or 0),
        "priority_max": int(priority_max or 0),
        "distinct_priorities": int(distinct_priorities or 0),
        "queue_mismatch_rows": queue_mismatch_rows,
        "extra_queue_rows": extra_queue_rows,
        "preexisting_fetch_rows": fetch_rows,
        "preexisting_document_rows": document_rows,
        "valid": (
            integrity == "ok"
            and not foreign_keys
            and queue_rows == expected_rows
            and queue_mismatch_rows == 0
            and extra_queue_rows == 0
            and fetch_rows == 0
            and document_rows == 0
        ),
    }


def compare_lanes(conn: sqlite3.Connection) -> dict[str, Any]:
    candidate_minus_reference = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT normalized_row_json FROM cohort_rows WHERE lane = 'candidate'
              EXCEPT
              SELECT normalized_row_json FROM cohort_rows WHERE lane = 'reference'
            )
            """
        ).fetchone()[0]
    )
    reference_minus_candidate = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT normalized_row_json FROM cohort_rows WHERE lane = 'reference'
              EXCEPT
              SELECT normalized_row_json FROM cohort_rows WHERE lane = 'candidate'
            )
            """
        ).fetchone()[0]
    )
    return {
        "candidate_minus_reference_rows": candidate_minus_reference,
        "reference_minus_candidate_rows": reference_minus_candidate,
        "normalized_semantic_payload_parity": (
            candidate_minus_reference == 0 and reference_minus_candidate == 0
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--candidate-db", required=True)
    parser.add_argument("--reference-manifest", default="")
    parser.add_argument("--expected-rows", required=True, type=int)
    parser.add_argument("--expected-selection-sha256", default="")
    parser.add_argument("--max-planner-peak-rss-mb", type=float, default=256.0)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    candidate_manifest_path = Path(args.candidate_manifest)
    candidate_db = Path(args.candidate_db)
    reference_manifest_path = Path(args.reference_manifest) if args.reference_manifest else None
    out_path = Path(args.out)
    errors: list[str] = []
    descriptor, store_name = tempfile.mkstemp(
        prefix=".real-document-planner-harness-",
        suffix=".sqlite",
        dir="etl/data/staging",
    )
    os.close(descriptor)
    store_path = Path(store_name)
    try:
        conn = open_harness_store(store_path)
        try:
            candidate_manifest = read_json(candidate_manifest_path)
            if candidate_manifest.get("schema_version") != "real_document_fetch_scale_cohort_v4":
                errors.append("candidate manifest is not v4")
            candidate = stage_lane(
                conn=conn,
                lane="candidate",
                manifest=candidate_manifest,
                manifest_path=candidate_manifest_path,
            )
            expected_rows = int(args.expected_rows)
            if candidate["rows"] != expected_rows:
                errors.append("candidate row count mismatch")
            if int((candidate_manifest.get("selection") or {}).get("rows") or 0) != expected_rows:
                errors.append("manifest selection row count mismatch")
            if candidate_manifest.get("cohort_selection_sha256") != candidate["selection_sha256"]:
                errors.append("candidate selection identity mismatch")
            if args.expected_selection_sha256 and candidate["selection_sha256"] != args.expected_selection_sha256:
                errors.append("expected selection identity mismatch")
            execution_contract = candidate_manifest.get("execution_contract") or {}
            if execution_contract.get("sha256") != candidate["execution_sha256"]:
                errors.append("candidate execution identity mismatch")
            if candidate["real_policy_rows"] != expected_rows:
                errors.append("candidate real-policy count mismatch")
            if candidate["public_information_rows"] != expected_rows:
                errors.append("candidate public-information count mismatch")
            if candidate["blocked_host_rows"] != 0:
                errors.append("candidate contains blocked hosts")
            planner_peak_rss = int(
                (candidate_manifest.get("planning") or {}).get("peak_rss_bytes") or 0
            )
            max_peak_rss = int(float(args.max_planner_peak_rss_mb) * 1024 * 1024)
            if planner_peak_rss < 1 or planner_peak_rss > max_peak_rss:
                errors.append("candidate planner peak RSS exceeds bound")
            queue = attach_and_validate_queue(
                conn=conn,
                candidate_db=candidate_db,
                expected_rows=expected_rows,
            )
            if not queue["valid"]:
                errors.append("candidate queue/database reconciliation failed")
            reference: dict[str, Any] | None = None
            comparison: dict[str, Any] | None = None
            logical_partition_parity: bool | None = None
            if reference_manifest_path is not None:
                reference_manifest = read_json(reference_manifest_path)
                reference = stage_lane(
                    conn=conn,
                    lane="reference",
                    manifest=reference_manifest,
                    manifest_path=reference_manifest_path,
                )
                comparison = compare_lanes(conn)
                logical_partition_parity = (
                    candidate["logical_partition_hashes"]
                    == reference["logical_partition_hashes"]
                )
                if reference["rows"] != expected_rows:
                    errors.append("reference row count mismatch")
                if not comparison["normalized_semantic_payload_parity"]:
                    errors.append("candidate/reference normalized row parity failed")
                if not logical_partition_parity:
                    errors.append("candidate/reference logical partition parity failed")
            rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            report = {
                "schema_version": "real_document_fetch_disk_planner_validation_v1",
                "status": "ok" if not errors else "error",
                "policy": {
                    "official_real_documents_only": True,
                    "synthetic_or_mock_records_counted": False,
                    "official_public_domain_personal_information_retained": True,
                },
                "inputs": {
                    "candidate_manifest": {
                        "path": repo_path(candidate_manifest_path),
                        "bytes": candidate_manifest_path.stat().st_size,
                        "sha256": sha256_path(candidate_manifest_path),
                    },
                    "candidate_database": {
                        "path": repo_path(candidate_db),
                        "bytes": candidate_db.stat().st_size,
                        "sha256": sha256_path(candidate_db),
                    },
                    "reference_manifest": (
                        {
                            "path": repo_path(reference_manifest_path),
                            "bytes": reference_manifest_path.stat().st_size,
                            "sha256": sha256_path(reference_manifest_path),
                        }
                        if reference_manifest_path is not None
                        else None
                    ),
                },
                "candidate": candidate,
                "reference": reference,
                "comparison": comparison,
                "logical_partition_parity": logical_partition_parity,
                "queue": queue,
                "planning": {
                    "backend": "disk_backed_sqlite",
                    "full_cohort_materialized_in_memory": False,
                    "planner_peak_rss_bytes": planner_peak_rss,
                    "planner_peak_rss_bound_bytes": max_peak_rss,
                    "planner_peak_rss_within_bound": (
                        0 < planner_peak_rss <= max_peak_rss
                    ),
                },
                "validation_performance": {
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                    "peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
                    "temporary_store_removed_after_validation": True,
                },
                "error_count": len(errors),
                "errors": errors[:100],
            }
        finally:
            conn.close()
        store_path.unlink(missing_ok=True)
        write_json_atomic(out_path, report)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        store_path.unlink(missing_ok=True)
        report = {
            "schema_version": "real_document_fetch_disk_planner_validation_v1",
            "status": "error",
            "error_count": 1,
            "errors": [str(exc)],
        }
        write_json_atomic(out_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
