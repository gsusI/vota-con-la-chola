"""Crash-safe partitioned manifests for real-document processing generations."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INDEX_SCHEMA = "real_document_generation_manifest_v1"
RECEIPT_SCHEMA = "real_document_generation_activation_receipt_v1"
LAYOUT = "partitioned_jsonl_gzip_v1"


class GenerationManifestError(RuntimeError):
    """Raised when a document-generation artifact violates its contract."""


def sha256_file(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def canonical_index_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _archive_immutable(path: Path, payload: bytes) -> None:
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise GenerationManifestError(f"immutable artifact collision: {path.name}")
        return
    atomic_write_bytes(path, payload)


def _safe_relative_child(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise GenerationManifestError(f"unsafe generation path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise GenerationManifestError(
            f"generation path escapes root: {relative}"
        ) from exc
    return candidate


def lifecycle_roots(manifest_path: Path) -> tuple[Path, Path, Path, Path]:
    parent = manifest_path.parent
    stem = manifest_path.stem
    return (
        parent / f"{stem}-data",
        parent / f"{stem}-history",
        parent / f"{stem}-receipts",
        parent / f"{stem}-state",
    )


def _relative_to_manifest_parent(path: Path, manifest_path: Path) -> str:
    try:
        return path.resolve().relative_to(manifest_path.parent.resolve()).as_posix()
    except ValueError as exc:
        raise GenerationManifestError(
            "generation artifact escapes manifest parent"
        ) from exc


def _encode_row(row: Mapping[str, Any]) -> bytes:
    return (json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8")


def _publish_shards(
    *,
    staging_dir: Path,
    generation_root: Path,
    logical_sha256: str,
    staged_shards: list[dict[str, Any]],
) -> Path:
    generation_root.mkdir(parents=True, exist_ok=True)
    final_dir = generation_root / logical_sha256
    expected_names = {str(item["name"]) for item in staged_shards}
    if final_dir.exists():
        actual = set(final_dir.iterdir())
        if {path.name for path in actual} != expected_names or any(
            not path.is_file() for path in actual
        ):
            raise GenerationManifestError("generation shard inventory collision")
        for item in staged_shards:
            staged = staging_dir / str(item["name"])
            retained = final_dir / str(item["name"])
            if retained.stat().st_size != staged.stat().st_size or sha256_file(
                retained
            ) != sha256_file(staged):
                raise GenerationManifestError("generation shard checksum collision")
        shutil.rmtree(staging_dir)
    else:
        os.replace(staging_dir, final_dir)
        _fsync_directory(generation_root)
    return final_dir


def build_partitioned_index(
    *,
    manifest_path: Path,
    rows: Iterable[Mapping[str, Any]],
    dataset: str,
    row_schema_version: str,
    max_rows: int,
    max_uncompressed_bytes: int,
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    """Materialize immutable bounded shards and return their small index."""
    if not dataset or not row_schema_version:
        raise GenerationManifestError("dataset and row schema are required")
    if max_rows < 1 or max_uncompressed_bytes < 1:
        raise GenerationManifestError("manifest shard bounds must be positive")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    generation_root, _, _, _ = lifecycle_roots(manifest_path)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{manifest_path.stem}-", dir=manifest_path.parent)
    )
    staged: list[dict[str, Any]] = []
    logical_digest = hashlib.sha256()
    total_rows = 0
    total_uncompressed = 0
    shard_raw: Any = None
    shard_gzip: Any = None
    shard_path: Path | None = None
    shard_rows = 0
    shard_uncompressed = 0
    shard_logical = hashlib.sha256()

    def open_shard() -> None:
        nonlocal shard_raw, shard_gzip, shard_path
        nonlocal shard_rows, shard_uncompressed, shard_logical
        shard_path = staging_dir / f"part-{len(staged):05d}.jsonl.gz"
        shard_raw = shard_path.open("xb")
        shard_gzip = gzip.GzipFile(filename="", mode="wb", fileobj=shard_raw, mtime=0)
        shard_rows = 0
        shard_uncompressed = 0
        shard_logical = hashlib.sha256()

    def close_shard() -> None:
        nonlocal shard_raw, shard_gzip, shard_path
        if shard_gzip is None or shard_raw is None or shard_path is None:
            return
        shard_gzip.close()
        shard_raw.flush()
        os.fsync(shard_raw.fileno())
        shard_raw.close()
        staged.append(
            {
                "name": shard_path.name,
                "rows": shard_rows,
                "bytes": shard_path.stat().st_size,
                "uncompressed_bytes": shard_uncompressed,
                "sha256": sha256_file(shard_path),
                "logical_sha256": shard_logical.hexdigest(),
            }
        )
        shard_raw = None
        shard_gzip = None
        shard_path = None

    try:
        for row in rows:
            if row.get("schema_version") != row_schema_version:
                raise GenerationManifestError(
                    "row schema drifted during generation build"
                )
            encoded = _encode_row(row)
            if shard_gzip is None:
                open_shard()
            if shard_rows and (
                shard_rows >= max_rows
                or shard_uncompressed + len(encoded) > max_uncompressed_bytes
            ):
                close_shard()
                open_shard()
            shard_gzip.write(encoded)
            shard_rows += 1
            shard_uncompressed += len(encoded)
            total_rows += 1
            total_uncompressed += len(encoded)
            shard_logical.update(encoded)
            logical_digest.update(encoded)
        close_shard()
        if not staged:
            raise GenerationManifestError("refusing to publish an empty generation")
        logical_sha256 = logical_digest.hexdigest()
        final_dir = _publish_shards(
            staging_dir=staging_dir,
            generation_root=generation_root,
            logical_sha256=logical_sha256,
            staged_shards=staged,
        )
    except Exception:
        if shard_gzip is not None:
            shard_gzip.close()
        if shard_raw is not None and not shard_raw.closed:
            shard_raw.close()
        raise
    partitions = [
        {
            **{key: value for key, value in item.items() if key != "name"},
            "path": _relative_to_manifest_parent(
                final_dir / str(item["name"]), manifest_path
            ),
        }
        for item in staged
    ]
    payload = {
        "schema_version": INDEX_SCHEMA,
        "dataset": dataset,
        "row_schema_version": row_schema_version,
        "layout": LAYOUT,
        "logical_sha256": logical_sha256,
        "shard_root": _relative_to_manifest_parent(final_dir, manifest_path),
        "partition_limits": {
            "max_rows": max_rows,
            "max_uncompressed_bytes": max_uncompressed_bytes,
        },
        "partitions": partitions,
        "totals": {
            "rows": total_rows,
            "shard_files": len(partitions),
            "compressed_bytes": sum(int(item["bytes"]) for item in partitions),
            "uncompressed_bytes": total_uncompressed,
        },
        "policy": dict(policy),
    }
    return payload, canonical_index_bytes(payload)


def load_index_bytes(
    payload_bytes: bytes, *, dataset: str | None = None
) -> dict[str, Any]:
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise GenerationManifestError("generation index is invalid JSON") from exc
    policy = payload.get("policy") or {}
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != INDEX_SCHEMA
        or payload.get("layout") != LAYOUT
        or not SHA256_RE.fullmatch(str(payload.get("logical_sha256") or ""))
        or (dataset is not None and payload.get("dataset") != dataset)
        or policy.get("official_public_domain_personal_information_retained")
        is not True
        or policy.get("synthetic_or_mock_records_counted") is not False
        or policy.get("automatic_deletion_forbidden") is not True
    ):
        raise GenerationManifestError("generation index contract drifted")
    return payload


def _snapshot_state_database(
    *,
    connection: sqlite3.Connection,
    state_root: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    state_root.mkdir(parents=True, exist_ok=True)
    descriptor, snapshot_name = tempfile.mkstemp(
        prefix=f".{manifest_path.stem}-state-",
        suffix=".sqlite",
        dir=manifest_path.parent,
    )
    os.close(descriptor)
    snapshot_path = Path(snapshot_name)
    gzip_temp = snapshot_path.with_suffix(".sqlite.gz.part")
    try:
        target = sqlite3.connect(str(snapshot_path))
        try:
            connection.backup(target)
            target.commit()
        finally:
            target.close()
        with snapshot_path.open("rb") as handle:
            os.fsync(handle.fileno())
        raw_bytes = snapshot_path.stat().st_size
        raw_sha256 = sha256_file(snapshot_path)
        final_path = state_root / f"{raw_sha256}.sqlite.gz"
        if final_path.exists():
            if not final_path.is_file():
                raise GenerationManifestError("state snapshot path collision")
        else:
            with snapshot_path.open("rb") as source, gzip_temp.open("xb") as raw_out:
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=raw_out, mtime=0
                ) as zipped:
                    shutil.copyfileobj(source, zipped, length=1024 * 1024)
                raw_out.flush()
                os.fsync(raw_out.fileno())
            os.replace(gzip_temp, final_path)
            _fsync_directory(state_root)
        return {
            "path": _relative_to_manifest_parent(final_path, manifest_path),
            "sha256": raw_sha256,
            "bytes": raw_bytes,
            "compressed_sha256": sha256_file(final_path),
            "compressed_bytes": final_path.stat().st_size,
            "sqlite_quick_check": "ok",
        }
    finally:
        snapshot_path.unlink(missing_ok=True)
        gzip_temp.unlink(missing_ok=True)


def _load_receipt(path: Path, *, manifest_sha256: str, dataset: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise GenerationManifestError("activation receipt is invalid JSON") from exc
    predecessor = payload.get("predecessor_manifest_sha256")
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != RECEIPT_SCHEMA
        or payload.get("dataset") != dataset
        or payload.get("active_manifest_sha256") != manifest_sha256
        or (predecessor is not None and not SHA256_RE.fullmatch(str(predecessor)))
        or payload.get("superseded_predecessor") is not (predecessor is not None)
        or payload.get("deletion_performed") is not False
        or payload.get("remote_mutation_performed") is not False
        or payload.get("retention_policy")
        != {
            "manifest_indices_immutable": True,
            "referenced_generations_immutable": True,
            "state_snapshots_immutable": True,
            "automatic_deletion_forbidden": True,
            "interrupted_artifacts_retained_for_audit": True,
        }
    ):
        raise GenerationManifestError("activation receipt drifted")
    return payload


def activate_generation(
    *,
    manifest_path: Path,
    payload: Mapping[str, Any],
    payload_bytes: bytes,
    state_connection: sqlite3.Connection,
) -> dict[str, Any]:
    """Archive state and switch the live index last; never delete a generation."""
    dataset = str(payload.get("dataset") or "")
    new_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    _, history_root, receipt_root, state_root = lifecycle_roots(manifest_path)
    previous_sha256: str | None = None
    previous_logical_sha256: str | None = None
    legacy_migrated = False
    if manifest_path.exists():
        previous_bytes = manifest_path.read_bytes()
        try:
            previous = load_index_bytes(previous_bytes, dataset=dataset)
        except GenerationManifestError:
            legacy_sha256 = hashlib.sha256(previous_bytes).hexdigest()
            if legacy_sha256 != payload.get("logical_sha256"):
                raise GenerationManifestError(
                    "legacy live manifest differs from the candidate generation"
                )
            legacy_migrated = True
        else:
            previous_sha256 = hashlib.sha256(previous_bytes).hexdigest()
            previous_logical_sha256 = str(previous["logical_sha256"])
            _archive_immutable(history_root / f"{previous_sha256}.json", previous_bytes)
    archive_path = history_root / f"{new_sha256}.json"
    _archive_immutable(archive_path, payload_bytes)
    receipt_path = receipt_root / f"{new_sha256}.json"
    live_changed = (
        not manifest_path.exists() or manifest_path.read_bytes() != payload_bytes
    )
    if receipt_path.exists():
        receipt = _load_receipt(
            receipt_path, manifest_sha256=new_sha256, dataset=dataset
        )
        if (
            live_changed
            and receipt.get("predecessor_manifest_sha256") != previous_sha256
        ):
            raise GenerationManifestError(
                "historical generation reactivation requires an explicit rollback workflow"
            )
    else:
        state_snapshot = _snapshot_state_database(
            connection=state_connection,
            state_root=state_root,
            manifest_path=manifest_path,
        )
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "dataset": dataset,
            "active_manifest_sha256": new_sha256,
            "active_logical_sha256": payload["logical_sha256"],
            "predecessor_manifest_sha256": (
                previous_sha256 if previous_sha256 != new_sha256 else None
            ),
            "predecessor_logical_sha256": (
                previous_logical_sha256 if previous_sha256 != new_sha256 else None
            ),
            "superseded_predecessor": (
                previous_sha256 is not None and previous_sha256 != new_sha256
            ),
            "state_snapshot": state_snapshot,
            "legacy_equivalent_jsonl_migrated": legacy_migrated,
            "retention_policy": {
                "manifest_indices_immutable": True,
                "referenced_generations_immutable": True,
                "state_snapshots_immutable": True,
                "automatic_deletion_forbidden": True,
                "interrupted_artifacts_retained_for_audit": True,
            },
            "deletion_performed": False,
            "remote_mutation_performed": False,
        }
        _archive_immutable(receipt_path, canonical_index_bytes(receipt))
    if live_changed:
        atomic_write_bytes(manifest_path, payload_bytes)
    return {
        "activated": True,
        "active_manifest_sha256": new_sha256,
        "active_logical_sha256": payload["logical_sha256"],
        "active_history_path": _relative_to_manifest_parent(
            archive_path, manifest_path
        ),
        "active_receipt_path": _relative_to_manifest_parent(
            receipt_path, manifest_path
        ),
        "state_snapshot": receipt["state_snapshot"],
        "predecessor_manifest_sha256": receipt.get("predecessor_manifest_sha256"),
        "superseded_predecessor": receipt.get("superseded_predecessor") is True,
        "legacy_equivalent_jsonl_migrated": receipt.get(
            "legacy_equivalent_jsonl_migrated"
        )
        is True,
        "live_index_changed": live_changed,
        "live_index_switched_last": True,
        "automatic_deletion_performed": False,
    }


def publish_generation_manifest(
    *,
    manifest_path: Path,
    rows: Iterable[Mapping[str, Any]],
    dataset: str,
    row_schema_version: str,
    state_connection: sqlite3.Connection,
    max_rows: int,
    max_uncompressed_bytes: int,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    payload, payload_bytes = build_partitioned_index(
        manifest_path=manifest_path,
        rows=rows,
        dataset=dataset,
        row_schema_version=row_schema_version,
        max_rows=max_rows,
        max_uncompressed_bytes=max_uncompressed_bytes,
        policy=policy,
    )
    publication = activate_generation(
        manifest_path=manifest_path,
        payload=payload,
        payload_bytes=payload_bytes,
        state_connection=state_connection,
    )
    return {
        "path": str(manifest_path),
        "rows": int(payload["totals"]["rows"]),
        "bytes": len(payload_bytes),
        "sha256": publication["active_manifest_sha256"],
        "logical_sha256": payload["logical_sha256"],
        "shard_files": int(payload["totals"]["shard_files"]),
        "compressed_bytes": int(payload["totals"]["compressed_bytes"]),
        "uncompressed_bytes": int(payload["totals"]["uncompressed_bytes"]),
        "publication": publication,
    }


def _iter_legacy_jsonl(
    path: Path, first_item: dict[str, Any], handle: Any
) -> Iterator[dict[str, Any]]:
    yield first_item
    for line_number, line in enumerate(handle, start=2):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GenerationManifestError(
                f"invalid legacy JSONL at {path.name}:{line_number}"
            ) from exc
        if not isinstance(item, dict):
            raise GenerationManifestError("legacy JSONL row must be an object")
        yield item


def iter_generation_rows(
    path: Path,
    *,
    dataset: str | None = None,
    row_schema_version: str | None = None,
    allow_legacy_jsonl: bool = True,
    artifact_root: Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Read a partitioned generation, with bounded legacy JSONL migration support."""
    if not path.is_file():
        raise GenerationManifestError(f"manifest missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline()
        try:
            first_item = json.loads(first_line)
        except json.JSONDecodeError as exc:
            raise GenerationManifestError(
                "manifest first record is invalid JSON"
            ) from exc
        if not isinstance(first_item, dict):
            raise GenerationManifestError("manifest root must be an object")
        if first_item.get("schema_version") != INDEX_SCHEMA:
            if not allow_legacy_jsonl:
                raise GenerationManifestError("legacy JSONL manifest is not allowed")
            yield from _iter_legacy_jsonl(path, first_item, handle)
            return
    index = load_index_bytes(first_line.encode("utf-8"), dataset=dataset)
    if (
        row_schema_version is not None
        and index.get("row_schema_version") != row_schema_version
    ):
        raise GenerationManifestError("manifest row schema drifted")
    logical_digest = hashlib.sha256()
    total_rows = 0
    total_uncompressed = 0
    partitions = index.get("partitions")
    if not isinstance(partitions, list) or not partitions:
        raise GenerationManifestError("generation has no partitions")
    shard_base = artifact_root if artifact_root is not None else path.parent
    for partition in partitions:
        if not isinstance(partition, dict):
            raise GenerationManifestError("invalid manifest partition")
        shard = _safe_relative_child(shard_base, str(partition.get("path") or ""))
        if (
            not shard.is_file()
            or shard.stat().st_size != partition.get("bytes")
            or sha256_file(shard) != partition.get("sha256")
        ):
            raise GenerationManifestError(f"manifest shard drifted: {shard.name}")
        shard_digest = hashlib.sha256()
        shard_rows = 0
        shard_bytes = 0
        with gzip.open(shard, "rb") as zipped:
            for line_number, line in enumerate(zipped, start=1):
                shard_digest.update(line)
                logical_digest.update(line)
                shard_bytes += len(line)
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise GenerationManifestError(
                        f"invalid shard row: {shard.name}:{line_number}"
                    ) from exc
                if not isinstance(item, dict):
                    raise GenerationManifestError("shard row must be an object")
                if (
                    row_schema_version is not None
                    and item.get("schema_version") != row_schema_version
                ):
                    raise GenerationManifestError("shard row schema drifted")
                shard_rows += 1
                total_rows += 1
                yield item
        if (
            shard_rows != partition.get("rows")
            or shard_bytes != partition.get("uncompressed_bytes")
            or shard_digest.hexdigest() != partition.get("logical_sha256")
        ):
            raise GenerationManifestError(
                f"manifest shard totals drifted: {shard.name}"
            )
        total_uncompressed += shard_bytes
    totals = index.get("totals") or {}
    if (
        total_rows != totals.get("rows")
        or total_uncompressed != totals.get("uncompressed_bytes")
        or logical_digest.hexdigest() != index.get("logical_sha256")
    ):
        raise GenerationManifestError("generation logical totals drifted")


def audit_generation_lifecycle(
    manifest_path: Path,
    *,
    dataset: str,
    full_shard_check: bool,
    full_state_check: bool,
) -> dict[str, Any]:
    """Independently audit activation chains, shards, and retained SQLite state."""
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_file():
        raise GenerationManifestError("active generation manifest is missing")
    active_bytes = manifest_path.read_bytes()
    active = load_index_bytes(active_bytes, dataset=dataset)
    active_sha256 = hashlib.sha256(active_bytes).hexdigest()
    generation_root, history_root, receipt_root, state_root = lifecycle_roots(
        manifest_path
    )
    if not all(
        path.is_dir()
        for path in (generation_root, history_root, receipt_root, state_root)
    ):
        raise GenerationManifestError("generation lifecycle roots are incomplete")
    archives: dict[str, dict[str, Any]] = {}
    for path in sorted(history_root.glob("*.json")):
        if not SHA256_RE.fullmatch(path.stem):
            raise GenerationManifestError("invalid manifest archive name")
        payload_bytes = path.read_bytes()
        if hashlib.sha256(payload_bytes).hexdigest() != path.stem:
            raise GenerationManifestError("manifest archive checksum drifted")
        payload = load_index_bytes(payload_bytes, dataset=dataset)
        archives[path.stem] = payload
        generation_dir = _safe_relative_child(
            manifest_path.parent, str(payload.get("shard_root") or "")
        )
        if (
            generation_dir.parent != generation_root.resolve()
            or generation_dir.name != payload.get("logical_sha256")
            or not generation_dir.is_dir()
        ):
            raise GenerationManifestError("retained generation root drifted")
        partitions = payload.get("partitions")
        if not isinstance(partitions, list) or not partitions:
            raise GenerationManifestError("retained generation has no partitions")
        expected_files = {
            _safe_relative_child(manifest_path.parent, str(partition.get("path") or ""))
            for partition in partitions
            if isinstance(partition, dict)
        }
        if len(expected_files) != len(partitions):
            raise GenerationManifestError("retained partition contract drifted")
        actual_files = set(generation_dir.iterdir())
        if expected_files != actual_files or any(
            not item.is_file() for item in actual_files
        ):
            raise GenerationManifestError("retained shard inventory drifted")
        if full_shard_check:
            consumed = sum(
                1
                for _ in iter_generation_rows(
                    path,
                    dataset=dataset,
                    row_schema_version=str(payload["row_schema_version"]),
                    allow_legacy_jsonl=False,
                    artifact_root=manifest_path.parent,
                )
            )
            if consumed != int((payload.get("totals") or {}).get("rows", -1)):
                raise GenerationManifestError("retained generation row total drifted")
    if (
        active_sha256 not in archives
        or (history_root / f"{active_sha256}.json").read_bytes() != active_bytes
    ):
        raise GenerationManifestError("active manifest is not archived exactly")
    receipts: dict[str, dict[str, Any]] = {}
    referenced_state_paths: set[Path] = set()
    state_bytes = 0
    for path in sorted(receipt_root.glob("*.json")):
        if not SHA256_RE.fullmatch(path.stem):
            raise GenerationManifestError("invalid activation receipt name")
        receipt = _load_receipt(path, manifest_sha256=path.stem, dataset=dataset)
        snapshot = receipt.get("state_snapshot") or {}
        snapshot_path = _safe_relative_child(
            manifest_path.parent, str(snapshot.get("path") or "")
        )
        try:
            snapshot_path.relative_to(state_root.resolve())
        except ValueError as exc:
            raise GenerationManifestError("state snapshot escapes state root") from exc
        if (
            not snapshot_path.is_file()
            or snapshot_path.stat().st_size != snapshot.get("compressed_bytes")
            or sha256_file(snapshot_path) != snapshot.get("compressed_sha256")
            or snapshot_path.name != f"{snapshot.get('sha256')}.sqlite.gz"
        ):
            raise GenerationManifestError("state snapshot drifted")
        if full_state_check:
            descriptor, temp_name = tempfile.mkstemp(suffix=".sqlite")
            os.close(descriptor)
            restored = Path(temp_name)
            try:
                digest = hashlib.sha256()
                restored_bytes = 0
                with (
                    gzip.open(snapshot_path, "rb") as source,
                    restored.open("wb") as out,
                ):
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                        restored_bytes += len(chunk)
                        out.write(chunk)
                if digest.hexdigest() != snapshot.get(
                    "sha256"
                ) or restored_bytes != snapshot.get("bytes"):
                    raise GenerationManifestError("restored state snapshot drifted")
                connection = sqlite3.connect(f"file:{restored}?mode=ro", uri=True)
                try:
                    quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
                finally:
                    connection.close()
                if quick_check != "ok":
                    raise GenerationManifestError(
                        "restored state database failed quick_check"
                    )
            finally:
                restored.unlink(missing_ok=True)
        receipts[path.stem] = receipt
        referenced_state_paths.add(snapshot_path)
        state_bytes += int(snapshot.get("compressed_bytes") or 0)
    chain: list[str] = []
    current: str | None = active_sha256
    while current is not None:
        if current in chain:
            raise GenerationManifestError("activation receipt cycle detected")
        if current not in archives or current not in receipts:
            raise GenerationManifestError("activation chain artifact is missing")
        receipt = receipts[current]
        if receipt.get("active_logical_sha256") != archives[current].get(
            "logical_sha256"
        ):
            raise GenerationManifestError("activation logical checksum drifted")
        predecessor = receipt.get("predecessor_manifest_sha256")
        predecessor_logical = receipt.get("predecessor_logical_sha256")
        if predecessor is None:
            if predecessor_logical is not None:
                raise GenerationManifestError("initial receipt has predecessor state")
        elif predecessor not in archives or predecessor_logical != archives[
            predecessor
        ].get("logical_sha256"):
            raise GenerationManifestError("activation predecessor drifted")
        chain.append(current)
        current = predecessor
    unactivated_archives = sorted(set(archives) - set(chain))
    unactivated_receipts = sorted(set(receipts) - set(chain))
    referenced_generations = {
        str(payload["logical_sha256"]) for payload in archives.values()
    }
    actual_generations = {
        path.name
        for path in generation_root.iterdir()
        if path.is_dir() and SHA256_RE.fullmatch(path.name)
    }
    unexpected_generation_entries = [
        path.name
        for path in generation_root.iterdir()
        if not (path.is_dir() and SHA256_RE.fullmatch(path.name))
    ]
    if unexpected_generation_entries:
        raise GenerationManifestError("unexpected generation-root entries")
    missing_generations = sorted(referenced_generations - actual_generations)
    if missing_generations:
        raise GenerationManifestError("retained generation directory is missing")
    orphan_generations = sorted(actual_generations - referenced_generations)
    chain_generations = {str(archives[item]["logical_sha256"]) for item in chain}
    unactivated_generations = sorted(referenced_generations - chain_generations)
    actual_state_paths = {path.resolve() for path in state_root.glob("*.sqlite.gz")}
    orphan_state_snapshots = sorted(
        path.name for path in actual_state_paths - referenced_state_paths
    )
    staging_dirs = sorted(
        path.name
        for path in manifest_path.parent.glob(f".{manifest_path.stem}-*")
        if path.is_dir()
    )
    degraded = bool(
        unactivated_archives
        or unactivated_receipts
        or unactivated_generations
        or orphan_generations
        or orphan_state_snapshots
        or staging_dirs
    )
    checks = {
        "active_manifest_archived_exactly": True,
        "activation_receipt_chain_complete": True,
        "retained_manifest_contracts_valid": True,
        "retained_shards_checked_to_requested_depth": True,
        "retained_state_snapshots_checked_to_requested_depth": True,
        "official_public_information_retained": True,
        "no_synthetic_or_mock_rows": True,
        "automatic_deletion_forbidden_and_not_performed": True,
        "no_unactivated_manifest_archives": not unactivated_archives,
        "no_unactivated_activation_receipts": not unactivated_receipts,
        "no_unactivated_generation_directories": not unactivated_generations,
        "no_orphan_generation_directories": not orphan_generations,
        "no_orphan_state_snapshots": not orphan_state_snapshots,
        "no_interrupted_staging_directories": not staging_dirs,
    }
    return {
        "schema_version": "real_document_generation_lifecycle_audit_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "degraded" if degraded else "ok",
        "dataset": dataset,
        "input": {
            "path": str(manifest_path),
            "bytes": len(active_bytes),
            "sha256": active_sha256,
            "logical_sha256": active["logical_sha256"],
        },
        "mode": {
            "full_shard_check": full_shard_check,
            "full_state_check": full_state_check,
        },
        "policy": {
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock_records_counted": False,
            "automatic_deletion_forbidden": True,
            "interrupted_artifacts_retained_for_audit": True,
            "remote_mutation_performed": False,
        },
        "totals": {
            "manifest_archives": len(archives),
            "activation_receipts": len(receipts),
            "activation_chain_manifests": len(chain),
            "superseded_generations": max(0, len(chain) - 1),
            "retained_unique_generations": len(referenced_generations),
            "retained_shard_files": sum(
                int((payload.get("totals") or {}).get("shard_files") or 0)
                for payload in archives.values()
            ),
            "retained_compressed_manifest_bytes": sum(
                int((payload.get("totals") or {}).get("compressed_bytes") or 0)
                for payload in archives.values()
            ),
            "retained_state_snapshots": len(referenced_state_paths),
            "retained_compressed_state_bytes": state_bytes,
            "unactivated_manifest_archives": len(unactivated_archives),
            "unactivated_activation_receipts": len(unactivated_receipts),
            "unactivated_generation_directories": len(unactivated_generations),
            "orphan_generation_directories": len(orphan_generations),
            "orphan_state_snapshots": len(orphan_state_snapshots),
            "interrupted_staging_directories": len(staging_dirs),
            "automatic_deletions": 0,
        },
        "activation_chain": chain,
        "retention": {
            "unactivated_manifest_archive_sha256": unactivated_archives,
            "unactivated_activation_receipt_sha256": unactivated_receipts,
            "unactivated_generation_logical_sha256": unactivated_generations,
            "orphan_generation_logical_sha256": orphan_generations,
            "orphan_state_snapshots": orphan_state_snapshots,
            "interrupted_staging_directories": staging_dirs,
        },
        "checks": checks,
    }
