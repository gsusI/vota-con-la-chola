#!/usr/bin/env python3
"""Run a checksum-verified deterministic restore sample from an object manifest."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.object_store import (  # noqa: E402
    ContentObjectStore,
    FilesystemObjectStore,
    ObjectReplica,
    S3ObjectStore,
)
from publicdata_core.util import now_utc_iso  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify object-store restore")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--backend", choices=("filesystem", "s3"), default="filesystem")
    parser.add_argument("--filesystem-root", default="etl/data/object-origin")
    parser.add_argument("--bucket", default=os.environ.get("OBJECT_STORE_BUCKET", ""))
    parser.add_argument(
        "--endpoint-url", default=os.environ.get("OBJECT_STORE_ENDPOINT_URL", "")
    )
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", ""))
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--max-object-bytes", type=int, default=2 * 1024 * 1024 * 1024)
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def deterministic_manifest_sample(
    manifest_path: Path, *, sample_size: int
) -> list[dict[str, object]]:
    selected: list[tuple[int, str, dict[str, object]]] = []
    with Path(manifest_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = dict(json.loads(line))
            token = hashlib.sha256(
                f"restore-sample-v1:{row.get('content_sha256', '')}".encode()
            ).digest()
            rank = int.from_bytes(token, "big")
            digest = str(row.get("content_sha256") or "")
            entry = (-rank, digest, row)
            if len(selected) < int(sample_size):
                heapq.heappush(selected, entry)
            elif rank < -selected[0][0]:
                heapq.heapreplace(selected, entry)
    return [row for _, _, row in sorted(selected, key=lambda value: -value[0])]


def restore_sample(
    rows: list[dict[str, object]],
    *,
    store: ContentObjectStore,
    restore_root: Path,
    max_object_bytes: int,
) -> dict[str, Any]:
    restored_bytes = 0
    for index, row in enumerate(rows):
        replica = ObjectReplica(
            backend=str(row["backend"]),
            bucket=str(row["bucket"]),
            object_key=str(row["object_key"]),
            content_sha256=str(row["content_sha256"]),
            bytes=int(row["bytes"]),
            content_type=(str(row["content_type"]) if row.get("content_type") else None),
            version_id=(str(row["version_id"]) if row.get("version_id") else None),
            deduplicated=bool(row.get("deduplicated")),
        )
        store.restore_verified(
            replica,
            destination=Path(restore_root) / f"{index:08d}.blob",
            max_bytes=int(max_object_bytes),
        )
        restored_bytes += int(replica.bytes)
    return {
        "schema_version": "object_store_restore_drill_v1",
        "status": "ok",
        "verified_at": now_utc_iso(),
        "sample_total": len(rows),
        "restored_bytes": restored_bytes,
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
    manifest_path = Path(args.manifest)
    if (
        not manifest_path.is_file()
        or int(args.sample_size) < 1
        or int(args.max_object_bytes) < 1
    ):
        print("ERROR: manifest must exist and sample/max bytes must be positive", file=sys.stderr)
        return 2
    try:
        store = _build_store(args)
        rows = deterministic_manifest_sample(
            manifest_path, sample_size=int(args.sample_size)
        )
        if not rows:
            raise RuntimeError("manifest contains no objects")
        with tempfile.TemporaryDirectory(prefix="vota-object-restore-") as temp_dir:
            report = restore_sample(
                rows,
                store=store,
                restore_root=Path(temp_dir),
                max_object_bytes=int(args.max_object_bytes),
            )
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if str(args.report_out or "").strip():
        out_path = Path(args.report_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
