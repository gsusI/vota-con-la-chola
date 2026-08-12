#!/usr/bin/env python3
"""Replicate local content-addressed documents to a durable object origin."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.object_store import (  # noqa: E402
    ContentObjectStore,
    FilesystemObjectStore,
    S3ObjectStore,
)
from publicdata_core.util import now_utc_iso  # noqa: E402
from publicdata_sqlite import open_db  # noqa: E402


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
) -> dict[str, Any]:
    manifest_out = Path(manifest_out)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    partial = manifest_out.with_name(
        f".{manifest_out.name}.{uuid.uuid4().hex}.partial"
    )
    totals = {
        "candidates": 0,
        "replicated": 0,
        "deduplicated": 0,
        "missing_local": 0,
        "bytes": 0,
    }
    try:
        with partial.open("x", encoding="utf-8") as handle:
            for row in rows:
                totals["candidates"] += 1
                local_path = Path(str(row["raw_path"]))
                if not local_path.is_file():
                    totals["missing_local"] += 1
                    continue
                if dry_run:
                    continue
                if store is None:
                    raise RuntimeError("object store is required outside dry-run")
                replica = store.put_verified(
                    local_path,
                    content_sha256=str(row["content_sha256"]),
                    bytes_expected=int(row["bytes"]),
                    content_type=(
                        str(row["content_type"]) if row.get("content_type") else None
                    ),
                    namespace=namespace,
                )
                manifest_row = {
                    "schema_version": "content_object_manifest_row_v1",
                    "replicated_at": now_utc_iso(),
                    **replica.as_manifest_row(),
                }
                handle.write(json.dumps(manifest_row, ensure_ascii=True, sort_keys=True))
                handle.write("\n")
                totals["replicated"] += 1
                totals["bytes"] += int(replica.bytes)
                totals["deduplicated"] += 1 if replica.deduplicated else 0
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, manifest_out)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return {
        "schema_version": "content_object_replication_report_v1",
        "status": (
            "dry_run"
            if dry_run
            else "ok"
            if totals["missing_local"] == 0
            else "partial"
        ),
        "backend": "dry_run" if dry_run else "configured",
        "namespace": namespace,
        "manifest": str(manifest_out.name),
        "totals": totals,
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
    if not db_path.is_file() or int(args.limit) < 0:
        print("ERROR: DB must exist and limit must be >= 0", file=sys.stderr)
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
            )
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
