#!/usr/bin/env python3
"""Replicate local content-addressed documents to a durable object origin."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.object_store import (
    ContentObjectStore,
    FilesystemObjectStore,
    S3ObjectStore,
)
from publicdata_core.util import now_utc_iso
from publicdata_sqlite import open_db


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replicate content objects")
    parser.add_argument("--db", default="etl/data/staging/politicos-es.db")
    parser.add_argument("--backend", choices=("filesystem", "s3"), default="filesystem")
    parser.add_argument("--filesystem-root", default="etl/data/object-origin")
    parser.add_argument("--bucket", default=os.environ.get("OBJECT_STORE_BUCKET", ""))
    parser.add_argument(
        "--endpoint-url", default=os.environ.get("OBJECT_STORE_ENDPOINT_URL", "")
    )
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", ""))
    parser.add_argument("--namespace", default="raw/text-documents")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--report-out", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def iter_local_documents(
    conn: sqlite3.Connection, *, limit: int = 0
) -> Iterable[dict[str, object]]:
    sql = """
        SELECT content_sha256, MAX(bytes) AS bytes, MAX(content_type) AS content_type,
               MIN(raw_path) AS raw_path
        FROM text_documents
        WHERE content_sha256 IS NOT NULL AND content_sha256 != ''
          AND raw_path IS NOT NULL AND raw_path != ''
        GROUP BY content_sha256
        ORDER BY content_sha256
    """
    params: tuple[object, ...] = ()
    if int(limit) > 0:
        sql += " LIMIT ?"
        params = (int(limit),)
    for row in conn.execute(sql, params):
        yield {
            "content_sha256": str(row["content_sha256"]),
            "bytes": int(row["bytes"] or 0),
            "content_type": str(row["content_type"] or "") or None,
            "raw_path": str(row["raw_path"]),
        }


def replicate_objects(
    rows: Iterable[dict[str, object]],
    *,
    store: ContentObjectStore | None,
    namespace: str,
    manifest_out: Path,
    dry_run: bool = False,
    workers: int = 8,
) -> dict[str, Any]:
    if int(workers) < 1:
        raise ValueError("workers must be positive")
    started = time.monotonic()
    manifest_out = Path(manifest_out)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    partial = manifest_out.with_name(f".{manifest_out.name}.{uuid.uuid4().hex}.partial")
    totals = {
        "candidates": 0,
        "replicated": 0,
        "deduplicated": 0,
        "missing_local": 0,
        "bytes": 0,
    }
    try:
        with (
            partial.open("x", encoding="utf-8") as handle,
            ThreadPoolExecutor(max_workers=int(workers)) as executor,
        ):
            batch_size = max(int(workers) * 4, 1)
            batch: list[dict[str, object]] = []

            def flush_batch() -> None:
                if not batch:
                    return
                futures = {}
                for row in batch:
                    totals["candidates"] += 1
                    local_path = Path(str(row["raw_path"]))
                    if not local_path.is_file():
                        totals["missing_local"] += 1
                        continue
                    if dry_run:
                        continue
                    if store is None:
                        raise RuntimeError("object store is required outside dry-run")
                    future = executor.submit(
                        store.put_verified,
                        local_path,
                        content_sha256=str(row["content_sha256"]),
                        bytes_expected=int(row["bytes"]),
                        content_type=(
                            str(row["content_type"])
                            if row.get("content_type")
                            else None
                        ),
                        namespace=namespace,
                    )
                    futures[future] = str(row["content_sha256"])
                replicas = []
                for future in as_completed(futures):
                    replicas.append(future.result())
                replicas.sort(key=lambda replica: replica.content_sha256)
                for replica in replicas:
                    manifest_row = {
                        "schema_version": "content_object_manifest_row_v2",
                        **replica.as_manifest_row(),
                    }
                    handle.write(
                        json.dumps(manifest_row, ensure_ascii=True, sort_keys=True)
                    )
                    handle.write("\n")
                    totals["replicated"] += 1
                    totals["bytes"] += int(replica.bytes)
                    totals["deduplicated"] += 1 if replica.deduplicated else 0
                batch.clear()

            for row in rows:
                batch.append(row)
                if len(batch) >= batch_size:
                    flush_batch()
            flush_batch()
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, manifest_out)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    manifest_digest = hashlib.sha256()
    with manifest_out.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            manifest_digest.update(chunk)
    elapsed_seconds = max(time.monotonic() - started, 0.000001)
    return {
        "schema_version": "content_object_replication_report_v2",
        "generated_at": now_utc_iso(),
        "status": (
            "dry_run"
            if dry_run
            else "ok"
            if totals["missing_local"] == 0
            else "partial"
        ),
        "backend": "dry_run" if dry_run else "configured",
        "namespace": namespace,
        "workers": int(workers),
        "manifest": str(manifest_out.name),
        "manifest_bytes": int(manifest_out.stat().st_size),
        "manifest_sha256": manifest_digest.hexdigest(),
        "totals": totals,
        "performance": {
            "elapsed_seconds": round(elapsed_seconds, 6),
            "objects_per_second": round(totals["replicated"] / elapsed_seconds, 3),
            "bytes_per_second": round(totals["bytes"] / elapsed_seconds, 3),
        },
    }


def _build_store(args: argparse.Namespace) -> ContentObjectStore:
    if args.backend == "filesystem":
        return FilesystemObjectStore(Path(args.filesystem_root))
    if not str(args.bucket or "").strip():
        raise ValueError("--bucket or OBJECT_STORE_BUCKET is required for s3")
    return S3ObjectStore(
        bucket=str(args.bucket),
        endpoint_url=str(args.endpoint_url or "") or None,
        region_name=str(args.region or "") or None,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.is_file() or int(args.limit) < 0 or int(args.workers) < 1:
        print("ERROR: DB must exist, limit >= 0, and workers >= 1", file=sys.stderr)
        return 2
    try:
        store = None if args.dry_run else _build_store(args)
        conn = open_db(db_path, wal=False)
        try:
            report = replicate_objects(
                iter_local_documents(conn, limit=int(args.limit)),
                store=store,
                namespace=str(args.namespace),
                manifest_out=Path(args.manifest_out),
                dry_run=bool(args.dry_run),
                workers=int(args.workers),
            )
            report["backend"] = str(args.backend)
        finally:
            conn.close()
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if str(args.report_out or "").strip():
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
