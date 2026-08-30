#!/usr/bin/env python3
"""Replicate the complete real raw/native/OCR document corpus to an object origin."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.object_store import (
    ContentObjectStore,
    FilesystemObjectStore,
    S3ObjectStore,
    hash_file,
)
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    iter_generation_rows,
    publish_generation_manifest,
    sha256_file,
)

ROW_SCHEMA = "real_document_origin_replica_row_v1"
DATASET = "real_document_origin_replicas"
POLICY = {
    "official_public_domain_personal_information_retained": True,
    "synthetic_or_mock_records_counted": False,
    "automatic_deletion_forbidden": True,
    "raw_native_and_ocr_objects_in_scope": True,
    "terminal_only_manifest_activation": True,
}


class OriginReplicationError(RuntimeError):
    """Raised when the exact real corpus cannot be replicated safely."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.name


def safe_child(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise OriginReplicationError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise OriginReplicationError(f"path escapes root: {relative}") from exc
    return candidate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--native-manifest",
        default="etl/data/published/real-document-text-manifest-latest.jsonl",
    )
    parser.add_argument(
        "--ocr-manifest",
        default="etl/data/published/real-document-page-ocr-manifest-latest.jsonl",
    )
    parser.add_argument("--raw-root", default="etl/data/raw")
    parser.add_argument(
        "--native-root", default="etl/data/derived/real-document-text-corpus-v2"
    )
    parser.add_argument(
        "--ocr-root", default="etl/data/derived/real-document-page-ocr-v2"
    )
    parser.add_argument(
        "--state-db",
        default="etl/data/staging/real-document-origin-replication-v1.db",
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
    parser.add_argument("--claim-size", type=int, default=48)
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument(
        "--manifest-out",
        default="etl/data/manifests/real-document-origin-replicas.json",
    )
    parser.add_argument("--manifest-shard-max-rows", type=int, default=10_000)
    parser.add_argument(
        "--manifest-shard-max-uncompressed-bytes",
        type=int,
        default=64 * 1024 * 1024,
    )
    parser.add_argument(
        "--report-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-replication.json"
        ),
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS input_bindings (
          binding_key TEXT PRIMARY KEY,
          binding_value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS origin_objects (
          object_class TEXT NOT NULL,
          semantic_sha256 TEXT NOT NULL,
          blob_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          content_type TEXT,
          source_relative_path TEXT NOT NULL,
          namespace TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending'
            CHECK(state IN ('pending','leased','retry','succeeded','dead')),
          attempts INTEGER NOT NULL DEFAULT 0,
          lease_owner TEXT,
          lease_expires_at TEXT,
          backend TEXT,
          bucket TEXT,
          object_key TEXT,
          version_id TEXT,
          deduplicated INTEGER,
          last_error TEXT,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(object_class, semantic_sha256),
          UNIQUE(namespace, blob_sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_origin_objects_claim
          ON origin_objects(state, attempts, object_class, semantic_sha256);
        """
    )
    conn.commit()
    return conn


def bind_input(conn: sqlite3.Connection, key: str, value: str) -> None:
    existing = conn.execute(
        "SELECT binding_value FROM input_bindings WHERE binding_key = ?", (key,)
    ).fetchone()
    if existing is not None and str(existing["binding_value"]) != value:
        raise OriginReplicationError(f"input binding drift: {key}")
    conn.execute(
        "INSERT OR IGNORE INTO input_bindings(binding_key,binding_value) VALUES (?,?)",
        (key, value),
    )


def upsert_object(
    conn: sqlite3.Connection,
    *,
    object_class: str,
    semantic_sha256: str,
    blob_sha256: str,
    bytes_value: int,
    content_type: str,
    source_relative_path: str,
    namespace: str,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO origin_objects(
          object_class,semantic_sha256,blob_sha256,bytes,content_type,
          source_relative_path,namespace,updated_at
        ) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(object_class,semantic_sha256) DO UPDATE SET
          source_relative_path = MIN(source_relative_path, excluded.source_relative_path),
          updated_at = excluded.updated_at
        """,
        (
            object_class,
            semantic_sha256,
            blob_sha256,
            int(bytes_value),
            content_type,
            source_relative_path,
            namespace,
            now,
        ),
    )
    stored = conn.execute(
        """
        SELECT blob_sha256,bytes,content_type,namespace
        FROM origin_objects WHERE object_class=? AND semantic_sha256=?
        """,
        (object_class, semantic_sha256),
    ).fetchone()
    if stored is None or (
        str(stored["blob_sha256"]),
        int(stored["bytes"]),
        str(stored["content_type"]),
        str(stored["namespace"]),
    ) != (blob_sha256, int(bytes_value), content_type, namespace):
        raise OriginReplicationError(
            f"semantic object collision: {object_class}:{semantic_sha256}"
        )


def _seed_compressed_text(
    conn: sqlite3.Connection,
    *,
    object_class: str,
    semantic_sha256: str,
    relative_path: str,
    root: Path,
    namespace: str,
) -> None:
    path = safe_child(root, relative_path)
    if not path.is_file():
        raise OriginReplicationError(f"CAS object missing: {relative_path}")
    blob_sha256, bytes_value = hash_file(path)
    upsert_object(
        conn,
        object_class=object_class,
        semantic_sha256=semantic_sha256,
        blob_sha256=blob_sha256,
        bytes_value=bytes_value,
        content_type="application/gzip",
        source_relative_path=relative_path,
        namespace=namespace,
    )


def seed_state(
    conn: sqlite3.Connection,
    *,
    native_manifest: Path,
    ocr_manifest: Path,
    raw_root: Path,
    native_root: Path,
    ocr_root: Path,
) -> dict[str, int]:
    bindings = {
        "native_manifest_sha256": sha256_file(native_manifest),
        "ocr_manifest_sha256": sha256_file(ocr_manifest),
        "raw_root_contract": display_path(raw_root),
        "native_root_contract": display_path(native_root),
        "ocr_root_contract": display_path(ocr_root),
    }
    for key, value in bindings.items():
        bind_input(conn, key, value)
    existing = int(conn.execute("SELECT COUNT(*) FROM origin_objects").fetchone()[0])
    if existing:
        conn.commit()
        return object_counts(conn)

    for row in iter_generation_rows(
        native_manifest,
        dataset="native_text",
        row_schema_version="real_document_text_manifest_row_v1",
        allow_legacy_jsonl=False,
    ):
        if row.get("synthetic_or_mock") is not False:
            raise OriginReplicationError("native manifest contains non-real row")
        raw_relative = str(row["path"])
        raw_path = safe_child(raw_root, raw_relative)
        if not raw_path.is_file() or raw_path.stat().st_size != int(row["bytes"]):
            raise OriginReplicationError(
                f"raw object missing or size drifted: {raw_relative}"
            )
        upsert_object(
            conn,
            object_class="raw_document",
            semantic_sha256=str(row["content_sha256"]),
            blob_sha256=str(row["content_sha256"]),
            bytes_value=int(row["bytes"]),
            content_type=str(row["mime_type"]),
            source_relative_path=raw_relative,
            namespace="real-documents/raw",
        )
        if row.get("native_text_cas_path"):
            _seed_compressed_text(
                conn,
                object_class="native_text",
                semantic_sha256=str(row["native_text_sha256"]),
                relative_path=str(row["native_text_cas_path"]),
                root=native_root,
                namespace="real-documents/native-text-gzip",
            )
    for row in iter_generation_rows(
        ocr_manifest,
        dataset="page_ocr",
        row_schema_version="real_document_page_ocr_manifest_row_v1",
        allow_legacy_jsonl=False,
    ):
        if row.get("synthetic_or_mock") is not False:
            raise OriginReplicationError("OCR manifest contains non-real row")
        if row.get("ocr_text_cas_path"):
            _seed_compressed_text(
                conn,
                object_class="ocr_text",
                semantic_sha256=str(row["ocr_text_sha256"]),
                relative_path=str(row["ocr_text_cas_path"]),
                root=ocr_root,
                namespace="real-documents/ocr-text-gzip",
            )
    conn.commit()
    return object_counts(conn)


def object_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {
        str(row["object_class"]): int(row["n"])
        for row in conn.execute(
            "SELECT object_class,COUNT(*) AS n FROM origin_objects GROUP BY object_class"
        )
    }
    counts["total"] = sum(counts.values())
    return counts


def source_path_for(
    row: sqlite3.Row, *, raw_root: Path, native_root: Path, ocr_root: Path
) -> Path:
    roots = {
        "raw_document": raw_root,
        "native_text": native_root,
        "ocr_text": ocr_root,
    }
    try:
        root = roots[str(row["object_class"])]
    except KeyError as exc:
        raise OriginReplicationError("unknown object class") from exc
    return safe_child(root, str(row["source_relative_path"]))


def reclaim_expired(conn: sqlite3.Connection) -> int:
    now = utc_now()
    cursor = conn.execute(
        """
        UPDATE origin_objects
        SET state='retry',lease_owner=NULL,lease_expires_at=NULL,
            last_error=COALESCE(last_error,'expired lease'),updated_at=?
        WHERE state='leased' AND lease_expires_at < ?
        """,
        (now, now),
    )
    conn.commit()
    return int(cursor.rowcount)


def claim_batch(
    conn: sqlite3.Connection,
    *,
    owner: str,
    claim_size: int,
    max_attempts: int,
    lease_seconds: int,
) -> list[sqlite3.Row]:
    now = datetime.now(UTC)
    rows = conn.execute(
        """
        SELECT * FROM origin_objects
        WHERE state IN ('pending','retry') AND attempts < ?
        ORDER BY object_class,semantic_sha256 LIMIT ?
        """,
        (int(max_attempts), int(claim_size)),
    ).fetchall()
    if not rows:
        return []
    expires = (
        (now + timedelta(seconds=int(lease_seconds))).isoformat().replace("+00:00", "Z")
    )
    now_iso = now.isoformat().replace("+00:00", "Z")
    conn.executemany(
        """
        UPDATE origin_objects SET state='leased',attempts=attempts+1,
          lease_owner=?,lease_expires_at=?,updated_at=?
        WHERE object_class=? AND semantic_sha256=? AND state IN ('pending','retry')
        """,
        [
            (
                owner,
                expires,
                now_iso,
                str(row["object_class"]),
                str(row["semantic_sha256"]),
            )
            for row in rows
        ],
    )
    conn.commit()
    return rows


def replicate_queue(
    conn: sqlite3.Connection,
    *,
    store: ContentObjectStore,
    raw_root: Path,
    native_root: Path,
    ocr_root: Path,
    workers: int,
    claim_size: int,
    max_items: int,
    max_attempts: int,
    lease_seconds: int,
) -> dict[str, int]:
    if workers < 1 or claim_size < 1 or max_items < 0 or max_attempts < 1:
        raise OriginReplicationError("invalid worker, claim, item or attempt bound")
    owner = f"real-document-origin-{uuid.uuid4().hex}"
    attempted = succeeded = failed = 0
    while max_items == 0 or attempted < max_items:
        remaining = (
            claim_size if max_items == 0 else min(claim_size, max_items - attempted)
        )
        rows = claim_batch(
            conn,
            owner=owner,
            claim_size=remaining,
            max_attempts=max_attempts,
            lease_seconds=lease_seconds,
        )
        if not rows:
            break
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    store.put_verified,
                    source_path_for(
                        row,
                        raw_root=raw_root,
                        native_root=native_root,
                        ocr_root=ocr_root,
                    ),
                    content_sha256=str(row["blob_sha256"]),
                    bytes_expected=int(row["bytes"]),
                    content_type=str(row["content_type"] or "") or None,
                    namespace=str(row["namespace"]),
                ): row
                for row in rows
            }
            for future in as_completed(futures):
                row = futures[future]
                attempted += 1
                now = utc_now()
                try:
                    replica = future.result()
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    next_state = (
                        "dead" if int(row["attempts"]) + 1 >= max_attempts else "retry"
                    )
                    conn.execute(
                        """
                        UPDATE origin_objects SET state=?,lease_owner=NULL,
                          lease_expires_at=NULL,last_error=?,updated_at=?
                        WHERE object_class=? AND semantic_sha256=?
                        """,
                        (
                            next_state,
                            f"{type(exc).__name__}: {exc}"[:2000],
                            now,
                            str(row["object_class"]),
                            str(row["semantic_sha256"]),
                        ),
                    )
                else:
                    succeeded += 1
                    conn.execute(
                        """
                        UPDATE origin_objects SET state='succeeded',lease_owner=NULL,
                          lease_expires_at=NULL,backend=?,bucket=?,object_key=?,
                          version_id=?,deduplicated=?,last_error=NULL,updated_at=?
                        WHERE object_class=? AND semantic_sha256=?
                        """,
                        (
                            replica.backend,
                            replica.bucket,
                            replica.object_key,
                            replica.version_id,
                            1 if replica.deduplicated else 0,
                            now,
                            str(row["object_class"]),
                            str(row["semantic_sha256"]),
                        ),
                    )
                conn.commit()
    return {"attempted": attempted, "succeeded": succeeded, "failed": failed}


def state_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        str(row["state"]): int(row["n"])
        for row in conn.execute(
            "SELECT state,COUNT(*) AS n FROM origin_objects GROUP BY state"
        )
    }


def iter_replica_rows(conn: sqlite3.Connection):
    for row in conn.execute(
        """
        SELECT object_class,semantic_sha256,blob_sha256,bytes,content_type,
               namespace,backend,bucket,object_key,version_id,deduplicated
        FROM origin_objects WHERE state='succeeded'
        ORDER BY object_class,semantic_sha256
        """
    ):
        yield {
            "schema_version": ROW_SCHEMA,
            "object_class": str(row["object_class"]),
            "semantic_sha256": str(row["semantic_sha256"]),
            "blob_sha256": str(row["blob_sha256"]),
            "bytes": int(row["bytes"]),
            "content_type": str(row["content_type"] or "") or None,
            "namespace": str(row["namespace"]),
            "backend": str(row["backend"]),
            "bucket": str(row["bucket"]),
            "object_key": str(row["object_key"]),
            "version_id": str(row["version_id"] or "") or None,
            "deduplicated": bool(row["deduplicated"]),
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock": False,
        }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_store(args: argparse.Namespace) -> ContentObjectStore:
    if args.backend == "filesystem":
        return FilesystemObjectStore(Path(args.filesystem_root))
    if not str(args.bucket or "").strip():
        raise OriginReplicationError("S3 bucket is required")
    return S3ObjectStore(
        bucket=str(args.bucket),
        endpoint_url=str(args.endpoint_url or "") or None,
        region_name=str(args.region or "") or None,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    native_manifest = Path(args.native_manifest)
    ocr_manifest = Path(args.ocr_manifest)
    report_path = Path(args.report_out)
    started = time.monotonic()
    if not native_manifest.is_file() or not ocr_manifest.is_file():
        print("ERROR: current native and OCR manifests are required", file=sys.stderr)
        return 2
    conn: sqlite3.Connection | None = None
    try:
        conn = open_state(Path(args.state_db))
        reclaimed = reclaim_expired(conn)
        seeded = seed_state(
            conn,
            native_manifest=native_manifest,
            ocr_manifest=ocr_manifest,
            raw_root=Path(args.raw_root),
            native_root=Path(args.native_root),
            ocr_root=Path(args.ocr_root),
        )
        run = replicate_queue(
            conn,
            store=build_store(args),
            raw_root=Path(args.raw_root),
            native_root=Path(args.native_root),
            ocr_root=Path(args.ocr_root),
            workers=int(args.workers),
            claim_size=int(args.claim_size),
            max_items=int(args.max_items),
            max_attempts=int(args.max_attempts),
            lease_seconds=int(args.lease_seconds),
        )
        states = state_counts(conn)
        terminal = states == {"succeeded": seeded["total"]}
        manifest: dict[str, Any] | None = None
        if terminal:
            manifest = publish_generation_manifest(
                manifest_path=Path(args.manifest_out),
                rows=iter_replica_rows(conn),
                dataset=DATASET,
                row_schema_version=ROW_SCHEMA,
                state_connection=conn,
                max_rows=int(args.manifest_shard_max_rows),
                max_uncompressed_bytes=int(args.manifest_shard_max_uncompressed_bytes),
                policy=POLICY,
            )
            manifest["path"] = display_path(Path(args.manifest_out))
        bindings = {
            str(row["binding_key"]): str(row["binding_value"])
            for row in conn.execute(
                "SELECT binding_key,binding_value FROM input_bindings ORDER BY binding_key"
            )
        }
        report = {
            "schema_version": "real_document_origin_replication_v1",
            "generated_at": utc_now(),
            "status": "ok" if terminal else "partial",
            "backend": str(args.backend),
            "durable_public_origin_proven": False,
            "clean_room_restore_proven": False,
            "policy": {
                **POLICY,
                "filesystem_backend_is_local_drill_only": args.backend == "filesystem",
                "remote_publication_performed": False,
            },
            "inputs": bindings,
            "seeded": seeded,
            "state_counts": states,
            "run": {**run, "reclaimed_expired_leases": reclaimed},
            "manifest": manifest,
            "performance": {
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "workers": int(args.workers),
                "claim_size": int(args.claim_size),
            },
            "checks": {
                "all_real_objects_seeded": seeded["total"] > 0,
                "all_objects_terminal_success": terminal,
                "bounded_partitioned_manifest_activated": manifest is not None,
                "official_public_domain_personal_information_retained": True,
                "no_synthetic_or_mock_records": True,
                "no_remote_publication_claimed": True,
            },
            "next_action": (
                "Run the full bounded clean-restore validator. Then replicate the same exact "
                "generation to an authorized immutable public origin; local filesystem proof "
                "must never be presented as durable public origin."
            ),
        }
        write_report(report_path, report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        if args.enforce and not terminal:
            return 1
        return 0
    except (
        GenerationManifestError,
        OriginReplicationError,
        OSError,
        RuntimeError,
        sqlite3.Error,
        ValueError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
