#!/usr/bin/env python3
"""Prepare a deterministic, real-only BOE acquisition cohort in a clean queue DB."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PIPELINE_ID = "real_document_fetch_cohort_v1"
EXPECTED_PIPELINES = {
    "boe_document_fetch": ("boe_document_xml", 8),
    "boe_summary_fetch": ("boe_daily_summaries", 2),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repository: {path}") from exc


def read_only_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


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


def select_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        WITH ranked AS (
          SELECT
            w.pipeline_id AS source_pipeline_id,
            w.item_key AS source_url,
            w.payload_json,
            f.source_id,
            f.content_type,
            f.content_sha256,
            f.bytes,
            f.raw_path,
            NTILE(10) OVER (
              PARTITION BY w.pipeline_id
              ORDER BY f.bytes, w.item_key
            ) AS size_decile
          FROM pipeline_work_items w
          JOIN document_fetches f ON f.doc_url = w.item_key
          WHERE w.pipeline_id IN ('boe_document_fetch', 'boe_summary_fetch')
            AND w.state = 'succeeded'
            AND f.fetched_ok = 1
            AND f.last_http_status = 200
            AND f.doc_url LIKE 'https://www.boe.es/%'
            AND f.content_sha256 IS NOT NULL
            AND f.bytes > 0
            AND f.raw_path IS NOT NULL
        ), numbered AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY source_pipeline_id, size_decile
            ORDER BY source_url
          ) AS row_in_decile
          FROM ranked
        )
        SELECT *
        FROM numbered
        WHERE (source_pipeline_id = 'boe_document_fetch' AND row_in_decile <= 8)
           OR (source_pipeline_id = 'boe_summary_fetch' AND row_in_decile <= 2)
        ORDER BY source_pipeline_id, size_decile, source_url
        """
    ).fetchall()
    selected: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, dict):
            raise ValueError(f"queue payload is not an object: {row['source_url']}")
        selected.append({**dict(row), "payload": payload})
    return selected


def validate_selected_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) != 100:
        raise ValueError(f"expected 100 selected rows, got {len(rows)}")
    if len({str(row["source_url"]) for row in rows}) != len(rows):
        raise ValueError("selected URLs are not unique")
    counts: dict[tuple[str, int], int] = {}
    validated: list[dict[str, Any]] = []
    for row in rows:
        source_pipeline_id = str(row["source_pipeline_id"])
        expected_source_id, expected_per_decile = EXPECTED_PIPELINES[source_pipeline_id]
        decile = int(row["size_decile"])
        counts[(source_pipeline_id, decile)] = (
            counts.get((source_pipeline_id, decile), 0) + 1
        )
        payload = row["payload"]
        source_url = str(row["source_url"])
        if not source_url.startswith("https://www.boe.es/"):
            raise ValueError(f"non-BOE URL selected: {source_url}")
        if str(row["source_id"]) != expected_source_id:
            raise ValueError(f"source_id mismatch: {source_url}")
        if str(payload.get("document_source_id") or "") != expected_source_id:
            raise ValueError(f"payload source mismatch: {source_url}")
        if payload.get("synthetic_or_mock_records_counted") is not False:
            raise ValueError(f"non-real policy mismatch: {source_url}")
        if (
            payload.get("official_public_domain_personal_information_retained")
            is not True
        ):
            raise ValueError(f"public-information policy mismatch: {source_url}")
        raw_path = Path(str(row["raw_path"]))
        raw_repo_path = repo_path(raw_path)
        if not raw_path.is_file():
            raise ValueError(f"captured raw file missing: {raw_repo_path}")
        expected_bytes = int(row["bytes"])
        expected_sha256 = str(row["content_sha256"])
        if raw_path.stat().st_size != expected_bytes:
            raise ValueError(f"captured raw size mismatch: {source_url}")
        if sha256_path(raw_path) != expected_sha256:
            raise ValueError(f"captured raw hash mismatch: {source_url}")
        validated.append(
            {
                "source_pipeline_id": source_pipeline_id,
                "source_id": expected_source_id,
                "source_url": source_url,
                "size_decile": decile,
                "expected_bytes": expected_bytes,
                "expected_content_sha256": expected_sha256,
                "captured_raw_path": raw_repo_path,
                "payload": payload,
            }
        )
    for source_pipeline_id, (_, expected_per_decile) in EXPECTED_PIPELINES.items():
        for decile in range(1, 11):
            actual = counts.get((source_pipeline_id, decile), 0)
            if actual != expected_per_decile:
                raise ValueError(
                    f"stratum mismatch {source_pipeline_id} decile {decile}: "
                    f"{actual} != {expected_per_decile}"
                )
    return validated


def semantic_sha256(rows: list[dict[str, Any]]) -> str:
    projection = [
        {
            "source_pipeline_id": row["source_pipeline_id"],
            "source_id": row["source_id"],
            "source_url": row["source_url"],
            "size_decile": row["size_decile"],
            "expected_bytes": row["expected_bytes"],
            "expected_content_sha256": row["expected_content_sha256"],
        }
        for row in rows
    ]
    encoded = json.dumps(
        projection, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_queue_db(
    *,
    schema_path: Path,
    out_db: Path,
    rows: list[dict[str, Any]],
    prepared_at: str,
) -> None:
    out_db.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{out_db.name}.", suffix=".tmp", dir=out_db.parent
    )
    os.close(descriptor)
    try:
        conn = sqlite3.connect(temporary)
        try:
            conn.executescript(schema_path.read_text(encoding="utf-8"))
            conn.executemany(
                """
                INSERT INTO pipeline_work_items (
                  pipeline_id, item_key, partition_key, priority, state,
                  payload_json, available_at, attempts, max_attempts,
                  created_at, updated_at
                ) VALUES (?, ?, ?, 0, 'pending', ?, ?, 0, 2, ?, ?)
                """,
                [
                    (
                        PIPELINE_ID,
                        row["source_url"],
                        f"{row['source_pipeline_id']}:size_decile_{row['size_decile']}",
                        json.dumps(
                            row["payload"],
                            ensure_ascii=True,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        prepared_at,
                        prepared_at,
                        prepared_at,
                    )
                    for row in rows
                ],
            )
            conn.commit()
            integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            if integrity != "ok":
                raise ValueError(f"prepared database integrity failed: {integrity}")
        finally:
            conn.close()
        os.replace(temporary, out_db)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--schema", default="etl/load/sqlite_schema.sql")
    parser.add_argument("--out-db", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--prepared-at", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_db = Path(args.source_db)
    schema_path = Path(args.schema)
    out_db = Path(args.out_db)
    manifest_out = Path(args.manifest_out)
    prepared_at = str(args.prepared_at or "").strip() or utc_now()
    try:
        datetime.fromisoformat(prepared_at.replace("Z", "+00:00"))
        if not source_db.is_file() or not schema_path.is_file():
            raise ValueError("source database or schema is missing")
        with read_only_db(source_db) as conn:
            rows = validate_selected_rows(select_rows(conn))
        cohort_sha256 = semantic_sha256(rows)
        build_queue_db(
            schema_path=schema_path,
            out_db=out_db,
            rows=rows,
            prepared_at=prepared_at,
        )
        manifest = {
            "schema_version": "real_document_fetch_cohort_v1",
            "prepared_at": prepared_at,
            "status": "ready",
            "cohort_id": f"real_document_fetch_cohort_{cohort_sha256[:24]}",
            "cohort_semantic_sha256": cohort_sha256,
            "pipeline_id": PIPELINE_ID,
            "policy": {
                "official_real_documents_only": True,
                "synthetic_or_mock_records_counted": False,
                "official_public_domain_personal_information_retained": True,
                "known_blocked_rows_selected": 0,
            },
            "selection": {
                "method": "successful_boe_https_by_endpoint_and_captured_size_decile",
                "source_pipelines": {
                    "boe_document_fetch": {"per_decile": 8, "rows": 80},
                    "boe_summary_fetch": {"per_decile": 2, "rows": 20},
                },
                "size_deciles": 10,
                "rows": len(rows),
                "expected_bytes": sum(int(row["expected_bytes"]) for row in rows),
            },
            "inputs": {
                "source_db": {
                    "path": repo_path(source_db),
                    "bytes": source_db.stat().st_size,
                    "sha256": sha256_path(source_db),
                },
                "schema": {
                    "path": repo_path(schema_path),
                    "bytes": schema_path.stat().st_size,
                    "sha256": sha256_path(schema_path),
                },
            },
            "output_db": repo_path(out_db),
            "rows": rows,
        }
        write_json_atomic(manifest_out, manifest)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR real document fetch cohort preparation: {exc}")
        return 2
    print(
        "OK real document fetch cohort -> "
        f"{out_db} (rows={len(rows)} expected_bytes={manifest['selection']['expected_bytes']} "
        f"sha256={cohort_sha256})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
