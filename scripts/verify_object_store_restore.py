#!/usr/bin/env python3
"""Run a checksum-verified deterministic restore sample from an object manifest."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import shutil
import sys
import tempfile
import time
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
    ObjectReplica,
    S3ObjectStore,
)
from publicdata_core.util import now_utc_iso


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
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-object-bytes", type=int, default=2 * 1024 * 1024 * 1024)
    parser.add_argument("--min-free-bytes", type=int, default=10 * 1024**3)
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def deterministic_manifest_sample(
    manifest_path: Path, *, sample_size: int
) -> list[dict[str, object]]:
    selected: list[tuple[int, str, dict[str, object]]] = []
    for row in iter_manifest_rows(manifest_path):
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


def iter_manifest_rows(manifest_path: Path) -> Iterable[dict[str, object]]:
    with Path(manifest_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield dict(json.loads(line))


def restore_preflight(
    *, selected_objects: int, selected_bytes: int, min_free_bytes: int
) -> dict[str, int | str]:
    free_bytes = int(shutil.disk_usage(tempfile.gettempdir()).free)
    required_bytes = int(selected_bytes) + int(min_free_bytes)
    return {
        "status": "ok" if free_bytes >= required_bytes else "blocked_storage",
        "selected_objects": int(selected_objects),
        "selected_bytes": int(selected_bytes),
        "free_bytes": free_bytes,
        "minimum_free_after_restore_bytes": int(min_free_bytes),
        "required_bytes": required_bytes,
        "headroom_bytes": free_bytes - required_bytes,
    }


def restore_sample(
    rows: Iterable[dict[str, object]],
    *,
    store: ContentObjectStore,
    restore_root: Path,
    max_object_bytes: int,
    workers: int = 8,
    selection_mode: str = "deterministic_sample",
) -> dict[str, Any]:
    if int(workers) < 1:
        raise ValueError("workers must be positive")
    started = time.monotonic()
    restored_bytes = 0
    restored_objects = 0
    with ThreadPoolExecutor(max_workers=int(workers)) as executor:
        batch: list[tuple[int, dict[str, object]]] = []

        def flush_batch() -> None:
            nonlocal restored_bytes, restored_objects
            futures = {}
            for index, row in batch:
                replica = ObjectReplica(
                    backend=str(row["backend"]),
                    bucket=str(row["bucket"]),
                    object_key=str(row["object_key"]),
                    content_sha256=str(row["content_sha256"]),
                    bytes=int(row["bytes"]),
                    content_type=(
                        str(row["content_type"]) if row.get("content_type") else None
                    ),
                    version_id=(
                        str(row["version_id"]) if row.get("version_id") else None
                    ),
                    deduplicated=bool(row.get("deduplicated")),
                )
                future = executor.submit(
                    store.restore_verified,
                    replica,
                    destination=Path(restore_root) / f"{index:012d}.blob",
                    max_bytes=int(max_object_bytes),
                )
                futures[future] = replica
            for future in as_completed(futures):
                future.result()
                replica = futures[future]
                restored_bytes += int(replica.bytes)
                restored_objects += 1
            batch.clear()

        for index, row in enumerate(rows):
            batch.append((index, row))
            if len(batch) >= int(workers) * 4:
                flush_batch()
        flush_batch()
    elapsed_seconds = max(time.monotonic() - started, 0.000001)
    return {
        "schema_version": "object_store_restore_drill_v2",
        "status": "ok",
        "verified_at": now_utc_iso(),
        "selection_mode": selection_mode,
        "sample_total": restored_objects,
        "objects_total": restored_objects,
        "restored_bytes": restored_bytes,
        "workers": int(workers),
        "performance": {
            "elapsed_seconds": round(elapsed_seconds, 6),
            "objects_per_second": round(restored_objects / elapsed_seconds, 3),
            "bytes_per_second": round(restored_bytes / elapsed_seconds, 3),
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
    manifest_path = Path(args.manifest)
    if (
        not manifest_path.is_file()
        or int(args.sample_size) < 1
        or int(args.max_object_bytes) < 1
        or int(args.workers) < 1
        or int(args.min_free_bytes) < 0
    ):
        print(
            "ERROR: manifest must exist and sample/max bytes must be positive",
            file=sys.stderr,
        )
        return 2
    try:
        store = _build_store(args)
        rows: Iterable[dict[str, object]]
        selection_mode = "full_manifest" if args.all else "deterministic_sample"
        if args.all:
            selected_objects = 0
            selected_bytes = 0
            for selected_objects, row in enumerate(
                iter_manifest_rows(manifest_path), start=1
            ):
                selected_bytes += int(row["bytes"])
            rows = iter_manifest_rows(manifest_path)
        else:
            sampled = deterministic_manifest_sample(
                manifest_path, sample_size=int(args.sample_size)
            )
            if not sampled:
                raise RuntimeError("manifest contains no objects")
            rows = sampled
            selected_objects = len(sampled)
            selected_bytes = sum(int(row["bytes"]) for row in sampled)
        preflight = restore_preflight(
            selected_objects=selected_objects,
            selected_bytes=selected_bytes,
            min_free_bytes=int(args.min_free_bytes),
        )
        if preflight["status"] != "ok":
            raise RuntimeError("insufficient storage for bounded object restore")
        with tempfile.TemporaryDirectory(prefix="vota-object-restore-") as temp_dir:
            report = restore_sample(
                rows,
                store=store,
                restore_root=Path(temp_dir),
                max_object_bytes=int(args.max_object_bytes),
                workers=int(args.workers),
                selection_mode=selection_mode,
            )
        report["preflight"] = preflight
        if int(report["objects_total"]) == 0:
            raise RuntimeError("manifest contains no objects")
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
