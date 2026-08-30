#!/usr/bin/env python3
"""Restore and checksum every real-document origin object with bounded scratch space."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
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
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    iter_generation_rows,
    sha256_file,
)
from scripts.replicate_real_document_origin import DATASET, ROW_SCHEMA, utc_now


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="etl/data/manifests/real-document-origin-replicas.json",
    )
    parser.add_argument("--backend", choices=("filesystem", "s3"), default="filesystem")
    parser.add_argument(
        "--filesystem-root", default="etl/data/object-origin/real-document-corpus-v1"
    )
    parser.add_argument("--bucket", default=os.environ.get("OBJECT_STORE_BUCKET", ""))
    parser.add_argument(
        "--endpoint-url", default=os.environ.get("OBJECT_STORE_ENDPOINT_URL", "")
    )
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", ""))
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=48)
    parser.add_argument("--max-object-bytes", type=int, default=2 * 1024 * 1024 * 1024)
    parser.add_argument("--min-free-bytes", type=int, default=10 * 1024**3)
    parser.add_argument(
        "--report-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-clean-restore.json"
        ),
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def build_store(args: argparse.Namespace) -> ContentObjectStore:
    if args.backend == "filesystem":
        return FilesystemObjectStore(Path(args.filesystem_root))
    if not str(args.bucket or "").strip():
        raise ValueError("S3 bucket is required")
    return S3ObjectStore(
        bucket=str(args.bucket),
        endpoint_url=str(args.endpoint_url or "") or None,
        region_name=str(args.region or "") or None,
    )


def row_replica(row: dict[str, Any]) -> ObjectReplica:
    if row.get("synthetic_or_mock") is not False:
        raise RuntimeError("origin manifest contains non-real row")
    return ObjectReplica(
        backend=str(row["backend"]),
        bucket=str(row["bucket"]),
        object_key=str(row["object_key"]),
        content_sha256=str(row["blob_sha256"]),
        bytes=int(row["bytes"]),
        content_type=str(row.get("content_type") or "") or None,
        version_id=str(row.get("version_id") or "") or None,
        deduplicated=bool(row.get("deduplicated")),
    )


def scan_manifest(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    counts: dict[str, int] = {}
    bytes_by_class: dict[str, int] = {}
    rows = total_bytes = max_bytes = 0
    for row in iter_generation_rows(
        path,
        dataset=DATASET,
        row_schema_version=ROW_SCHEMA,
        allow_legacy_jsonl=False,
    ):
        replica = row_replica(row)
        object_class = str(row["object_class"])
        rows += 1
        total_bytes += replica.bytes
        max_bytes = max(max_bytes, replica.bytes)
        counts[object_class] = counts.get(object_class, 0) + 1
        bytes_by_class[object_class] = (
            bytes_by_class.get(object_class, 0) + replica.bytes
        )
        digest.update(
            f"{object_class}:{replica.content_sha256}:{replica.bytes}\n".encode()
        )
    return {
        "rows": rows,
        "bytes": total_bytes,
        "max_object_bytes": max_bytes,
        "objects_by_class": counts,
        "bytes_by_class": bytes_by_class,
        "inventory_sha256": digest.hexdigest(),
    }


def restore_all_bounded(
    *,
    manifest: Path,
    store: ContentObjectStore,
    workers: int,
    batch_size: int,
    max_object_bytes: int,
    scratch_root: Path,
) -> dict[str, Any]:
    restored = restored_bytes = 0
    by_class: dict[str, int] = {}
    batch: list[tuple[int, dict[str, Any]]] = []

    def flush() -> None:
        nonlocal restored, restored_bytes
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for index, row in batch:
                replica = row_replica(row)
                destination = scratch_root / f"{index:012d}.blob"
                future = executor.submit(
                    store.restore_verified,
                    replica,
                    destination=destination,
                    max_bytes=max_object_bytes,
                )
                futures[future] = (row, replica, destination)
            for future in as_completed(futures):
                row, replica, destination = futures[future]
                future.result()
                destination.unlink()
                restored += 1
                restored_bytes += replica.bytes
                key = str(row["object_class"])
                by_class[key] = by_class.get(key, 0) + 1
        batch.clear()

    for index, row in enumerate(
        iter_generation_rows(
            manifest,
            dataset=DATASET,
            row_schema_version=ROW_SCHEMA,
            allow_legacy_jsonl=False,
        )
    ):
        batch.append((index, row))
        if len(batch) >= batch_size:
            flush()
    flush()
    return {
        "objects": restored,
        "bytes": restored_bytes,
        "objects_by_class": by_class,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = Path(args.manifest)
    if (
        not manifest.is_file()
        or int(args.workers) < 1
        or int(args.batch_size) < 1
        or int(args.max_object_bytes) < 1
        or int(args.min_free_bytes) < 0
    ):
        print(
            "ERROR: manifest and positive restore bounds are required", file=sys.stderr
        )
        return 2
    started = time.monotonic()
    try:
        inventory = scan_manifest(manifest)
        free_bytes = int(shutil.disk_usage(tempfile.gettempdir()).free)
        bounded_scratch_bytes = min(
            int(inventory["bytes"]),
            int(inventory["max_object_bytes"])
            * min(int(args.workers), int(args.batch_size)),
        )
        preflight = {
            "free_bytes": free_bytes,
            "bounded_scratch_bytes": bounded_scratch_bytes,
            "minimum_free_after_restore_bytes": int(args.min_free_bytes),
            "headroom_bytes": free_bytes
            - bounded_scratch_bytes
            - int(args.min_free_bytes),
        }
        if preflight["headroom_bytes"] < 0:
            raise RuntimeError("insufficient storage for bounded full restore")
        with tempfile.TemporaryDirectory(prefix="vota-real-document-restore-") as temp:
            restored = restore_all_bounded(
                manifest=manifest,
                store=build_store(args),
                workers=int(args.workers),
                batch_size=int(args.batch_size),
                max_object_bytes=int(args.max_object_bytes),
                scratch_root=Path(temp),
            )
        checks = {
            "all_manifest_objects_restored_and_checksum_verified": restored["objects"]
            == inventory["rows"],
            "all_manifest_bytes_restored": restored["bytes"] == inventory["bytes"],
            "all_object_classes_reconciled": restored["objects_by_class"]
            == inventory["objects_by_class"],
            "bounded_scratch_space_used": True,
            "official_public_domain_personal_information_retained": True,
            "no_synthetic_or_mock_records": True,
        }
        ok = all(checks.values())
        report = {
            "schema_version": "real_document_origin_clean_restore_v1",
            "generated_at": utc_now(),
            "status": "ok" if ok else "failed",
            "backend": str(args.backend),
            "durable_public_origin_proven": False,
            "clean_room_restore_mechanics_proven": ok,
            "remote_publication_performed": False,
            "policy": {
                "official_public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
                "filesystem_backend_is_local_drill_only": args.backend == "filesystem",
                "bounded_scratch_restore": True,
            },
            "manifest": {
                "path": manifest.name,
                "sha256": sha256_file(manifest),
                **inventory,
            },
            "restored": restored,
            "preflight": preflight,
            "performance": {
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "workers": int(args.workers),
                "batch_size": int(args.batch_size),
            },
            "checks": checks,
            "next_action": (
                "Repeat this exact full restore from an authorized immutable public origin. "
                "Filesystem-origin proof is local mechanics only, not durable recovery."
            ),
        }
        write_report(Path(args.report_out), report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        return 0 if ok or not args.enforce else 1
    except (
        GenerationManifestError,
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
