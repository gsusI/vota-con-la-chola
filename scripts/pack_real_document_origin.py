#!/usr/bin/env python3
"""Build deterministic, byte-bounded immutable packs from the real object origin."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import tarfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.object_store import hash_file
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    iter_generation_rows,
    publish_generation_manifest,
    sha256_file,
)
from scripts.replicate_real_document_origin import (
    DATASET as ORIGIN_DATASET,
)
from scripts.replicate_real_document_origin import (
    ROW_SCHEMA as ORIGIN_ROW_SCHEMA,
)
from scripts.replicate_real_document_origin import (
    display_path,
    safe_child,
    utc_now,
)

DATASET = "real_document_origin_packs"
ROW_SCHEMA = "real_document_origin_pack_row_v1"
MEMBER_SCHEMA = "real_document_origin_pack_member_v1"
POLICY = {
    "official_public_domain_personal_information_retained": True,
    "synthetic_or_mock_records_counted": False,
    "automatic_deletion_forbidden": True,
    "exact_origin_generation_bound": True,
    "deterministic_archives": True,
    "pack_rows_and_payload_bytes_bounded": True,
    "terminal_only_manifest_activation": True,
}


class PackError(RuntimeError):
    """Raised when exact real-object packs cannot be produced safely."""


class HashingReader:
    """Hash and count the bytes tarfile consumes from one real object."""

    def __init__(self, handle: BinaryIO) -> None:
        self.handle = handle
        self.digest = hashlib.sha256()
        self.bytes = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self.handle.read(size)
        self.digest.update(chunk)
        self.bytes += len(chunk)
        return chunk


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin-manifest",
        default="etl/data/manifests/real-document-origin-replicas.json",
    )
    parser.add_argument(
        "--origin-root", default="etl/data/object-origin/real-document-corpus-v1"
    )
    parser.add_argument(
        "--state-db", default="etl/data/staging/real-document-origin-pack-v1.db"
    )
    parser.add_argument(
        "--pack-root", default="etl/data/object-origin-packs/real-document-corpus-v1"
    )
    parser.add_argument(
        "--manifest-out",
        default="etl/data/manifests/real-document-origin-packs.json",
    )
    parser.add_argument("--max-objects-per-pack", type=int, default=10_000)
    parser.add_argument(
        "--max-payload-bytes-per-pack", type=int, default=448 * 1024 * 1024
    )
    parser.add_argument("--gzip-level", type=int, default=6)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-packs", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--lease-seconds", type=int, default=3600)
    parser.add_argument("--manifest-shard-max-rows", type=int, default=1_000)
    parser.add_argument(
        "--manifest-shard-max-uncompressed-bytes",
        type=int,
        default=16 * 1024 * 1024,
    )
    parser.add_argument(
        "--report-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-packaging.json"
        ),
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=60)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS input_bindings (
          binding_key TEXT PRIMARY KEY,
          binding_value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS packs (
          pack_no INTEGER PRIMARY KEY,
          object_count INTEGER NOT NULL,
          payload_bytes INTEGER NOT NULL,
          first_identity TEXT NOT NULL,
          last_identity TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending'
            CHECK(state IN ('pending','leased','retry','succeeded','dead')),
          attempts INTEGER NOT NULL DEFAULT 0,
          lease_owner TEXT,
          lease_expires_at TEXT,
          archive_path TEXT,
          archive_sha256 TEXT,
          archive_bytes INTEGER,
          member_manifest_path TEXT,
          member_manifest_sha256 TEXT,
          member_manifest_bytes INTEGER,
          member_manifest_logical_sha256 TEXT,
          last_error TEXT,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pack_members (
          pack_no INTEGER NOT NULL REFERENCES packs(pack_no),
          member_no INTEGER NOT NULL,
          object_class TEXT NOT NULL,
          semantic_sha256 TEXT NOT NULL,
          blob_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          content_type TEXT,
          object_key TEXT NOT NULL,
          PRIMARY KEY(pack_no,member_no),
          UNIQUE(object_class,semantic_sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_packs_claim
          ON packs(state,attempts,pack_no);
        """
    )
    connection.commit()
    return connection


def bind_input(connection: sqlite3.Connection, key: str, value: str) -> None:
    existing = connection.execute(
        "SELECT binding_value FROM input_bindings WHERE binding_key=?", (key,)
    ).fetchone()
    if existing is not None and str(existing["binding_value"]) != value:
        raise PackError(f"input binding drift: {key}")
    connection.execute(
        "INSERT OR IGNORE INTO input_bindings(binding_key,binding_value) VALUES (?,?)",
        (key, value),
    )


def identity(row: dict[str, Any]) -> str:
    return f"{row['object_class']}:{row['semantic_sha256']}"


def seed_plan(
    connection: sqlite3.Connection,
    *,
    origin_manifest: Path,
    origin_root: Path,
    max_objects: int,
    max_payload_bytes: int,
) -> dict[str, int]:
    if max_objects < 1 or max_payload_bytes < 1:
        raise PackError("pack row and payload limits must be positive")
    bindings = {
        "origin_manifest_sha256": sha256_file(origin_manifest),
        "origin_root_contract": display_path(origin_root),
        "max_objects_per_pack": str(max_objects),
        "max_payload_bytes_per_pack": str(max_payload_bytes),
    }
    for key, value in bindings.items():
        bind_input(connection, key, value)
    existing = int(
        connection.execute("SELECT COUNT(*) FROM pack_members").fetchone()[0]
    )
    if existing:
        connection.commit()
        return plan_totals(connection)
    connection.commit()

    pack_no = 0
    current: list[dict[str, Any]] = []
    current_bytes = 0

    def flush() -> None:
        nonlocal pack_no, current, current_bytes
        if not current:
            return
        now = utc_now()
        connection.execute(
            """
            INSERT INTO packs(
              pack_no,object_count,payload_bytes,first_identity,last_identity,updated_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                pack_no,
                len(current),
                current_bytes,
                identity(current[0]),
                identity(current[-1]),
                now,
            ),
        )
        connection.executemany(
            """
            INSERT INTO pack_members(
              pack_no,member_no,object_class,semantic_sha256,blob_sha256,
              bytes,content_type,object_key
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            [
                (
                    pack_no,
                    member_no,
                    str(row["object_class"]),
                    str(row["semantic_sha256"]),
                    str(row["blob_sha256"]),
                    int(row["bytes"]),
                    str(row.get("content_type") or "") or None,
                    str(row["object_key"]),
                )
                for member_no, row in enumerate(current)
            ],
        )
        pack_no += 1
        current = []
        current_bytes = 0

    connection.execute("BEGIN IMMEDIATE")
    for raw_row in iter_generation_rows(
        origin_manifest,
        dataset=ORIGIN_DATASET,
        row_schema_version=ORIGIN_ROW_SCHEMA,
        allow_legacy_jsonl=False,
    ):
        row = dict(raw_row)
        if row.get("synthetic_or_mock") is not False:
            raise PackError("origin generation contains non-real row")
        bytes_value = int(row["bytes"])
        if bytes_value < 0 or bytes_value > max_payload_bytes:
            raise PackError("origin object violates pack payload ceiling")
        safe_child(origin_root, str(row["object_key"]))
        if current and (
            len(current) >= max_objects
            or current_bytes + bytes_value > max_payload_bytes
        ):
            flush()
        current.append(row)
        current_bytes += bytes_value
    flush()
    connection.commit()
    totals = plan_totals(connection)
    if totals["objects"] < 1 or totals["packs"] < 1:
        raise PackError("refusing to build an empty pack plan")
    return totals


def plan_totals(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COUNT(*) AS packs,COALESCE(SUM(object_count),0) AS objects,
               COALESCE(SUM(payload_bytes),0) AS payload_bytes,
               COALESCE(MAX(object_count),0) AS max_objects,
               COALESCE(MAX(payload_bytes),0) AS max_payload_bytes
        FROM packs
        """
    ).fetchone()
    return {
        key: int(row[key])
        for key in (
            "packs",
            "objects",
            "payload_bytes",
            "max_objects",
            "max_payload_bytes",
        )
    }


def reclaim_expired(connection: sqlite3.Connection) -> int:
    now = utc_now()
    cursor = connection.execute(
        """
        UPDATE packs SET state='retry',lease_owner=NULL,lease_expires_at=NULL,
          last_error=COALESCE(last_error,'expired lease'),updated_at=?
        WHERE state='leased' AND lease_expires_at < ?
        """,
        (now, now),
    )
    connection.commit()
    return int(cursor.rowcount)


def claim_packs(
    connection: sqlite3.Connection,
    *,
    owner: str,
    limit: int,
    max_attempts: int,
    lease_seconds: int,
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    now = datetime.now(UTC)
    pack_rows = connection.execute(
        """
        SELECT * FROM packs
        WHERE state IN ('pending','retry') AND attempts < ?
        ORDER BY pack_no LIMIT ?
        """,
        (max_attempts, limit),
    ).fetchall()
    if not pack_rows:
        return []
    expires = (
        (now + timedelta(seconds=lease_seconds)).isoformat().replace("+00:00", "Z")
    )
    now_iso = now.isoformat().replace("+00:00", "Z")
    connection.executemany(
        """
        UPDATE packs SET state='leased',attempts=attempts+1,lease_owner=?,
          lease_expires_at=?,updated_at=? WHERE pack_no=? AND state IN ('pending','retry')
        """,
        [(owner, expires, now_iso, int(row["pack_no"])) for row in pack_rows],
    )
    connection.commit()
    claimed: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for pack_row in pack_rows:
        members = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM pack_members WHERE pack_no=? ORDER BY member_no",
                (int(pack_row["pack_no"]),),
            )
        ]
        claimed.append((dict(pack_row), members))
    return claimed


def canonical_member_bytes(row: dict[str, Any]) -> bytes:
    return (
        json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def publish_immutable(temp_path: Path, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    if final_path.exists():
        if (
            not final_path.is_file()
            or final_path.stat().st_size != temp_path.stat().st_size
            or sha256_file(final_path) != sha256_file(temp_path)
        ):
            raise PackError(f"immutable pack collision: {final_path.name}")
        temp_path.unlink()
        return
    os.replace(temp_path, final_path)


def build_one_pack(
    *,
    pack: dict[str, Any],
    members: list[dict[str, Any]],
    origin_root: Path,
    pack_root: Path,
    gzip_level: int,
) -> dict[str, Any]:
    if len(members) != int(pack["object_count"]):
        raise PackError("pack member count drifted")
    staging = pack_root / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    unique = uuid.uuid4().hex
    archive_temp = staging / f"pack-{int(pack['pack_no']):05d}-{unique}.tar.gz"
    manifest_temp = staging / f"pack-{int(pack['pack_no']):05d}-{unique}.jsonl.gz"
    logical_digest = hashlib.sha256()
    payload_bytes = 0
    try:
        with (
            archive_temp.open("xb") as archive_raw,
            gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=archive_raw,
                compresslevel=gzip_level,
                mtime=0,
            ) as archive_gzip,
            tarfile.open(
                fileobj=archive_gzip, mode="w|", format=tarfile.USTAR_FORMAT
            ) as archive,
            manifest_temp.open("xb") as manifest_raw,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=manifest_raw, compresslevel=6, mtime=0
            ) as manifest_gzip,
        ):
            for member in members:
                blob_sha256 = str(member["blob_sha256"])
                object_class = str(member["object_class"])
                member_name = f"objects/{object_class}/{blob_sha256}"
                source = safe_child(origin_root, str(member["object_key"]))
                if not source.is_file() or source.stat().st_size != int(
                    member["bytes"]
                ):
                    raise PackError(
                        f"origin object missing or size drifted: {member_name}"
                    )
                info = tarfile.TarInfo(member_name)
                info.size = int(member["bytes"])
                info.mtime = 0
                info.mode = 0o444
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                with source.open("rb") as source_handle:
                    reader = HashingReader(source_handle)
                    archive.addfile(info, reader)
                if (
                    reader.bytes != int(member["bytes"])
                    or reader.digest.hexdigest() != blob_sha256
                ):
                    raise PackError(f"origin object checksum drifted: {member_name}")
                manifest_row = {
                    "schema_version": MEMBER_SCHEMA,
                    "pack_no": int(pack["pack_no"]),
                    "member_no": int(member["member_no"]),
                    "member_name": member_name,
                    "object_class": object_class,
                    "semantic_sha256": str(member["semantic_sha256"]),
                    "blob_sha256": blob_sha256,
                    "bytes": int(member["bytes"]),
                    "content_type": str(member.get("content_type") or "") or None,
                    "official_public_domain_personal_information_retained": True,
                    "synthetic_or_mock": False,
                }
                encoded = canonical_member_bytes(manifest_row)
                manifest_gzip.write(encoded)
                logical_digest.update(encoded)
                payload_bytes += int(member["bytes"])
            archive_raw.flush()
            manifest_raw.flush()
        with archive_temp.open("rb") as handle:
            os.fsync(handle.fileno())
        with manifest_temp.open("rb") as handle:
            os.fsync(handle.fileno())
        if payload_bytes != int(pack["payload_bytes"]):
            raise PackError("pack payload bytes drifted")
        archive_sha256, archive_bytes = hash_file(archive_temp)
        manifest_sha256, manifest_bytes = hash_file(manifest_temp)
        archive_relative = Path("packs") / f"{archive_sha256}.tar.gz"
        manifest_relative = Path("members") / f"{manifest_sha256}.jsonl.gz"
        publish_immutable(archive_temp, pack_root / archive_relative)
        publish_immutable(manifest_temp, pack_root / manifest_relative)
        return {
            "archive_path": archive_relative.as_posix(),
            "archive_sha256": archive_sha256,
            "archive_bytes": archive_bytes,
            "member_manifest_path": manifest_relative.as_posix(),
            "member_manifest_sha256": manifest_sha256,
            "member_manifest_bytes": manifest_bytes,
            "member_manifest_logical_sha256": logical_digest.hexdigest(),
        }
    finally:
        archive_temp.unlink(missing_ok=True)
        manifest_temp.unlink(missing_ok=True)


def run_pack_queue(
    connection: sqlite3.Connection,
    *,
    origin_root: Path,
    pack_root: Path,
    gzip_level: int,
    workers: int,
    max_packs: int,
    max_attempts: int,
    lease_seconds: int,
) -> dict[str, int]:
    if (
        workers < 1
        or max_packs < 0
        or max_attempts < 1
        or lease_seconds < 1
        or gzip_level < 0
        or gzip_level > 9
    ):
        raise PackError("invalid pack execution bounds")
    owner = f"real-document-packs-{uuid.uuid4().hex}"
    attempted = succeeded = failed = 0
    while max_packs == 0 or attempted < max_packs:
        limit = workers if max_packs == 0 else min(workers, max_packs - attempted)
        claimed = claim_packs(
            connection,
            owner=owner,
            limit=limit,
            max_attempts=max_attempts,
            lease_seconds=lease_seconds,
        )
        if not claimed:
            break
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    build_one_pack,
                    pack=pack,
                    members=members,
                    origin_root=origin_root,
                    pack_root=pack_root,
                    gzip_level=gzip_level,
                ): pack
                for pack, members in claimed
            }
            for future in as_completed(futures):
                pack = futures[future]
                attempted += 1
                now = utc_now()
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    next_state = (
                        "dead" if int(pack["attempts"]) + 1 >= max_attempts else "retry"
                    )
                    connection.execute(
                        """
                        UPDATE packs SET state=?,lease_owner=NULL,lease_expires_at=NULL,
                          last_error=?,updated_at=? WHERE pack_no=?
                        """,
                        (
                            next_state,
                            f"{type(exc).__name__}: {exc}"[:2000],
                            now,
                            int(pack["pack_no"]),
                        ),
                    )
                else:
                    succeeded += 1
                    connection.execute(
                        """
                        UPDATE packs SET state='succeeded',lease_owner=NULL,
                          lease_expires_at=NULL,archive_path=?,archive_sha256=?,
                          archive_bytes=?,member_manifest_path=?,
                          member_manifest_sha256=?,member_manifest_bytes=?,
                          member_manifest_logical_sha256=?,last_error=NULL,updated_at=?
                        WHERE pack_no=?
                        """,
                        (
                            result["archive_path"],
                            result["archive_sha256"],
                            result["archive_bytes"],
                            result["member_manifest_path"],
                            result["member_manifest_sha256"],
                            result["member_manifest_bytes"],
                            result["member_manifest_logical_sha256"],
                            now,
                            int(pack["pack_no"]),
                        ),
                    )
                connection.commit()
    return {"attempted": attempted, "succeeded": succeeded, "failed": failed}


def state_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        str(row["state"]): int(row["n"])
        for row in connection.execute(
            "SELECT state,COUNT(*) AS n FROM packs GROUP BY state"
        )
    }


def iter_pack_rows(connection: sqlite3.Connection, source_manifest_sha256: str):
    for row in connection.execute(
        "SELECT * FROM packs WHERE state='succeeded' ORDER BY pack_no"
    ):
        yield {
            "schema_version": ROW_SCHEMA,
            "pack_no": int(row["pack_no"]),
            "object_count": int(row["object_count"]),
            "payload_bytes": int(row["payload_bytes"]),
            "first_identity": str(row["first_identity"]),
            "last_identity": str(row["last_identity"]),
            "archive_path": str(row["archive_path"]),
            "archive_sha256": str(row["archive_sha256"]),
            "archive_bytes": int(row["archive_bytes"]),
            "member_manifest_path": str(row["member_manifest_path"]),
            "member_manifest_sha256": str(row["member_manifest_sha256"]),
            "member_manifest_bytes": int(row["member_manifest_bytes"]),
            "member_manifest_logical_sha256": str(
                row["member_manifest_logical_sha256"]
            ),
            "source_origin_manifest_sha256": source_manifest_sha256,
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock": False,
        }


def output_totals(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(archive_bytes),0) AS archive_bytes,
               COALESCE(SUM(member_manifest_bytes),0) AS member_manifest_bytes
        FROM packs WHERE state='succeeded'
        """
    ).fetchone()
    return {key: int(row[key]) for key in ("archive_bytes", "member_manifest_bytes")}


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    origin_manifest = Path(args.origin_manifest)
    report_path = Path(args.report_out)
    started = time.monotonic()
    if not origin_manifest.is_file():
        print("ERROR: current real-object origin manifest is required", file=sys.stderr)
        return 2
    connection: sqlite3.Connection | None = None
    try:
        connection = open_state(Path(args.state_db))
        reclaimed = reclaim_expired(connection)
        plan = seed_plan(
            connection,
            origin_manifest=origin_manifest,
            origin_root=Path(args.origin_root),
            max_objects=int(args.max_objects_per_pack),
            max_payload_bytes=int(args.max_payload_bytes_per_pack),
        )
        run = run_pack_queue(
            connection,
            origin_root=Path(args.origin_root),
            pack_root=Path(args.pack_root),
            gzip_level=int(args.gzip_level),
            workers=int(args.workers),
            max_packs=int(args.max_packs),
            max_attempts=int(args.max_attempts),
            lease_seconds=int(args.lease_seconds),
        )
        states = state_counts(connection)
        terminal = states == {"succeeded": plan["packs"]}
        source_manifest_sha256 = sha256_file(origin_manifest)
        manifest: dict[str, Any] | None = None
        if terminal:
            manifest = publish_generation_manifest(
                manifest_path=Path(args.manifest_out),
                rows=iter_pack_rows(connection, source_manifest_sha256),
                dataset=DATASET,
                row_schema_version=ROW_SCHEMA,
                state_connection=connection,
                max_rows=int(args.manifest_shard_max_rows),
                max_uncompressed_bytes=int(args.manifest_shard_max_uncompressed_bytes),
                policy=POLICY,
            )
            manifest["path"] = display_path(Path(args.manifest_out))
        bindings = {
            str(row["binding_key"]): str(row["binding_value"])
            for row in connection.execute(
                "SELECT binding_key,binding_value FROM input_bindings ORDER BY binding_key"
            )
        }
        packed = output_totals(connection)
        report = {
            "schema_version": "real_document_origin_packaging_v1",
            "generated_at": utc_now(),
            "status": "ok" if terminal else "partial",
            "durable_public_origin_proven": False,
            "remote_publication_performed": False,
            "policy": {
                **POLICY,
                "immutable_publication_package_only": True,
                "remote_restore_not_yet_proven": True,
            },
            "inputs": bindings,
            "plan": plan,
            "state_counts": states,
            "run": {**run, "reclaimed_expired_leases": reclaimed},
            "packed": packed,
            "manifest": manifest,
            "performance": {
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "workers": int(args.workers),
                "gzip_level": int(args.gzip_level),
            },
            "checks": {
                "exact_real_origin_generation_bound": bool(
                    bindings.get("origin_manifest_sha256")
                ),
                "all_packs_terminal_success": terminal,
                "bounded_pack_manifest_activated": manifest is not None,
                "pack_row_ceiling_respected": plan["max_objects"]
                <= int(args.max_objects_per_pack),
                "pack_payload_ceiling_respected": plan["max_payload_bytes"]
                <= int(args.max_payload_bytes_per_pack),
                "official_public_domain_personal_information_retained": True,
                "no_synthetic_or_mock_records": True,
                "no_remote_publication_claimed": True,
            },
            "next_action": (
                "Run the full independent pack verifier. After explicit release authority, "
                "publish the immutable pack generation to a public origin without delete "
                "operations, then restore and rehash it from an independent clean machine."
            ),
        }
        write_report(report_path, report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        if args.enforce and not terminal:
            return 1
        return 0
    except (
        GenerationManifestError,
        OSError,
        PackError,
        RuntimeError,
        sqlite3.Error,
        tarfile.TarError,
        ValueError,
    ) as exc:
        if connection is not None:
            connection.rollback()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
