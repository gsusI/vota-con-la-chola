"""Audit BOE lineage manifest activation, supersession, and retention state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("etl/data/manifests/boe-document-corpus-lineage-manifest.json")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "boe-document-corpus-generation-audit-20260830.json"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class LifecycleAuditError(RuntimeError):
    """Raised when retained BOE lineage lifecycle evidence is corrupt."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--full-shard-check", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def repo_path(value: str | Path) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise LifecycleAuditError(f"path escapes repository: {value}") from exc
    return candidate


def display_path(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def load_json_bytes(path: Path, *, label: str) -> tuple[bytes, dict[str, Any]]:
    if not path.is_file():
        raise LifecycleAuditError(f"{label} missing: {display_path(path)}")
    payload_bytes = path.read_bytes()
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise LifecycleAuditError(f"{label} is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise LifecycleAuditError(f"{label} root must be an object")
    return payload_bytes, payload


def lifecycle_roots(manifest_path: Path) -> tuple[Path, Path, Path]:
    return (
        manifest_path.parent / f"{manifest_path.stem}-data",
        manifest_path.parent / f"{manifest_path.stem}-history",
        manifest_path.parent / f"{manifest_path.stem}-receipts",
    )


def validate_manifest_archive(
    *,
    path: Path,
    expected_sha256: str,
    generation_root: Path,
    full_shard_check: bool,
) -> dict[str, Any]:
    payload_bytes, payload = load_json_bytes(path, label="BOE lineage manifest archive")
    if hashlib.sha256(payload_bytes).hexdigest() != expected_sha256:
        raise LifecycleAuditError(f"manifest archive checksum drifted: {path.name}")
    policy = payload.get("policy") or {}
    logical_sha256 = str(payload.get("logical_sha256") or "").lower()
    if (
        payload.get("schema_version") != "boe_document_corpus_lineage_manifest_v1"
        or payload.get("layout") != "partitioned_jsonl_gzip_v1"
        or not SHA256_RE.fullmatch(logical_sha256)
        or policy.get("official_public_domain_personal_information_retained")
        is not True
        or policy.get("synthetic_or_mock_records_counted") is not False
        or policy.get("remote_mutation_performed") is not False
    ):
        raise LifecycleAuditError(f"manifest archive contract drifted: {path.name}")
    shard_root = repo_path(str(payload.get("shard_root") or ""))
    expected_root = generation_root / logical_sha256
    if shard_root != expected_root.resolve() or not shard_root.is_dir():
        raise LifecycleAuditError(f"manifest generation root drifted: {path.name}")
    partitions = payload.get("partitions")
    totals = payload.get("totals") or {}
    if not isinstance(partitions, list) or not partitions:
        raise LifecycleAuditError(f"manifest archive has no partitions: {path.name}")
    seen_paths: set[str] = set()
    declared_shard_paths: set[Path] = set()
    compressed_bytes = 0
    rows = 0
    for partition in partitions:
        if not isinstance(partition, dict):
            raise LifecycleAuditError(f"invalid retained partition: {path.name}")
        relative_path = str(partition.get("path") or "")
        if relative_path in seen_paths:
            raise LifecycleAuditError(f"duplicate retained partition: {relative_path}")
        seen_paths.add(relative_path)
        shard_path = repo_path(relative_path)
        declared_shard_paths.add(shard_path)
        try:
            shard_path.relative_to(shard_root)
        except ValueError as exc:
            raise LifecycleAuditError(
                f"retained partition escapes generation: {relative_path}"
            ) from exc
        expected_bytes = partition.get("bytes")
        expected_checksum = str(partition.get("sha256") or "").lower()
        expected_rows = partition.get("rows")
        if (
            not shard_path.is_file()
            or not isinstance(expected_bytes, int)
            or expected_bytes <= 0
            or shard_path.stat().st_size != expected_bytes
            or not SHA256_RE.fullmatch(expected_checksum)
            or not isinstance(expected_rows, int)
            or expected_rows <= 0
        ):
            raise LifecycleAuditError(f"retained partition drifted: {relative_path}")
        if full_shard_check and sha256_file(shard_path) != expected_checksum:
            raise LifecycleAuditError(
                f"retained partition checksum drifted: {relative_path}"
            )
        compressed_bytes += expected_bytes
        rows += expected_rows
    actual_shard_paths = set(shard_root.iterdir())
    if actual_shard_paths != declared_shard_paths or any(
        not path.is_file() for path in actual_shard_paths
    ):
        raise LifecycleAuditError(f"retained generation inventory drifted: {path.name}")
    if (
        rows != totals.get("rows")
        or compressed_bytes != totals.get("compressed_lineage_bytes")
        or len(partitions) != totals.get("shard_files")
    ):
        raise LifecycleAuditError(f"retained manifest totals drifted: {path.name}")
    return {
        "manifest_sha256": expected_sha256,
        "logical_sha256": logical_sha256,
        "path": display_path(path),
        "shard_root": display_path(shard_root),
        "rows": rows,
        "shard_files": len(partitions),
        "compressed_bytes": compressed_bytes,
    }


def validate_receipt(path: Path, expected_sha256: str) -> dict[str, Any]:
    _, payload = load_json_bytes(path, label="BOE lineage activation receipt")
    predecessor = payload.get("predecessor_manifest_sha256")
    if (
        payload.get("schema_version")
        != "boe_document_corpus_lineage_activation_receipt_v1"
        or payload.get("active_manifest_sha256") != expected_sha256
        or not SHA256_RE.fullmatch(str(payload.get("active_logical_sha256") or ""))
        or (predecessor is not None and not SHA256_RE.fullmatch(str(predecessor)))
        or payload.get("superseded_predecessor") is not (predecessor is not None)
        or payload.get("deletion_performed") is not False
        or payload.get("remote_mutation_performed") is not False
        or (payload.get("retention_policy") or {})
        != {
            "manifest_indices_immutable": True,
            "referenced_generations_immutable": True,
            "automatic_deletion_forbidden": True,
            "interrupted_artifacts_retained_for_audit": True,
        }
    ):
        raise LifecycleAuditError(f"activation receipt drifted: {path.name}")
    return payload


def audit_generations(
    manifest_path: Path,
    *,
    full_shard_check: bool,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    active_bytes, _ = load_json_bytes(
        manifest_path, label="active BOE lineage manifest"
    )
    active_sha256 = hashlib.sha256(active_bytes).hexdigest()
    generation_root, history_root, receipt_root = lifecycle_roots(manifest_path)
    if (
        not generation_root.is_dir()
        or not history_root.is_dir()
        or not receipt_root.is_dir()
    ):
        raise LifecycleAuditError("BOE lineage lifecycle roots are incomplete")
    manifest_archives: dict[str, dict[str, Any]] = {}
    for path in sorted(history_root.glob("*.json")):
        if not SHA256_RE.fullmatch(path.stem):
            raise LifecycleAuditError(f"invalid manifest archive name: {path.name}")
        manifest_archives[path.stem] = validate_manifest_archive(
            path=path,
            expected_sha256=path.stem,
            generation_root=generation_root,
            full_shard_check=full_shard_check,
        )
    active_archive = manifest_archives.get(active_sha256)
    if (
        active_archive is None
        or (history_root / f"{active_sha256}.json").read_bytes() != active_bytes
    ):
        raise LifecycleAuditError("active BOE lineage manifest is not archived exactly")
    receipts: dict[str, dict[str, Any]] = {}
    for path in sorted(receipt_root.glob("*.json")):
        if not SHA256_RE.fullmatch(path.stem):
            raise LifecycleAuditError(f"invalid activation receipt name: {path.name}")
        receipts[path.stem] = validate_receipt(path, path.stem)
    activation_chain: list[str] = []
    current: str | None = active_sha256
    while current is not None:
        if current in activation_chain:
            raise LifecycleAuditError("BOE lineage activation receipt cycle detected")
        if current not in manifest_archives:
            raise LifecycleAuditError(
                "activation chain references a missing manifest archive"
            )
        receipt = receipts.get(current)
        if receipt is None:
            raise LifecycleAuditError("activation chain receipt is missing")
        if (
            receipt.get("active_logical_sha256")
            != manifest_archives[current]["logical_sha256"]
        ):
            raise LifecycleAuditError("activation receipt logical checksum drifted")
        predecessor = receipt.get("predecessor_manifest_sha256")
        predecessor_logical = receipt.get("predecessor_logical_sha256")
        if predecessor is None:
            if predecessor_logical is not None:
                raise LifecycleAuditError(
                    "initial activation receipt has predecessor metadata"
                )
        elif (
            predecessor not in manifest_archives
            or predecessor_logical != manifest_archives[predecessor]["logical_sha256"]
        ):
            raise LifecycleAuditError("activation predecessor lineage drifted")
        activation_chain.append(current)
        current = predecessor
    unreferenced_receipts = sorted(set(receipts) - set(activation_chain))
    if unreferenced_receipts:
        raise LifecycleAuditError("unreferenced BOE activation receipts detected")
    unactivated_manifest_archives = sorted(
        set(manifest_archives) - set(activation_chain)
    )
    referenced_generation_names = {
        item["logical_sha256"] for item in manifest_archives.values()
    }
    generation_names: set[str] = set()
    unexpected_generation_entries: list[str] = []
    for path in sorted(generation_root.iterdir()):
        if path.is_dir() and SHA256_RE.fullmatch(path.name):
            generation_names.add(path.name)
        else:
            unexpected_generation_entries.append(display_path(path))
    if unexpected_generation_entries:
        raise LifecycleAuditError("unexpected BOE generation-root entries detected")
    orphan_generation_names = sorted(generation_names - referenced_generation_names)
    missing_generation_names = sorted(referenced_generation_names - generation_names)
    if missing_generation_names:
        raise LifecycleAuditError("retained BOE generation directories are missing")
    active_chain_generation_names = {
        manifest_archives[item]["logical_sha256"] for item in activation_chain
    }
    unactivated_generation_names = sorted(
        referenced_generation_names - active_chain_generation_names
    )
    interrupted_staging_dirs = sorted(
        display_path(path)
        for path in manifest_path.parent.glob(f".{manifest_path.stem}-*")
        if path.is_dir()
    )
    degraded = bool(
        unactivated_manifest_archives
        or unactivated_generation_names
        or orphan_generation_names
        or interrupted_staging_dirs
    )
    checks = {
        "active_manifest_archived_exactly": True,
        "activation_receipt_chain_complete": True,
        "retained_manifest_contracts_valid": True,
        "retained_generation_file_inventory_exact": True,
        "retained_shards_checked_to_requested_depth": True,
        "official_public_information_retained": True,
        "no_synthetic_or_mock_rows": True,
        "automatic_deletion_forbidden_and_not_performed": True,
        "no_unactivated_manifest_archives": not unactivated_manifest_archives,
        "no_unactivated_generation_directories": not unactivated_generation_names,
        "no_orphan_generation_directories": not orphan_generation_names,
        "no_interrupted_staging_directories": not interrupted_staging_dirs,
    }
    unique_generations = {
        item["logical_sha256"]: item for item in manifest_archives.values()
    }
    return {
        "schema_version": "boe_document_corpus_generation_audit_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "degraded" if degraded else "ok",
        "input": {
            "path": display_path(manifest_path),
            "bytes": len(active_bytes),
            "sha256": active_sha256,
            "logical_sha256": active_archive["logical_sha256"],
        },
        "mode": {"full_shard_check": full_shard_check},
        "policy": {
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock_records_counted": False,
            "automatic_deletion_forbidden": True,
            "interrupted_artifacts_retained_for_audit": True,
            "remote_mutation_performed": False,
        },
        "totals": {
            "manifest_archives": len(manifest_archives),
            "activation_receipts": len(receipts),
            "activation_chain_manifests": len(activation_chain),
            "active_generations": 1,
            "superseded_generations": max(0, len(activation_chain) - 1),
            "unactivated_manifest_archives": len(unactivated_manifest_archives),
            "unactivated_generation_directories": len(unactivated_generation_names),
            "orphan_generation_directories": len(orphan_generation_names),
            "interrupted_staging_directories": len(interrupted_staging_dirs),
            "retained_unique_generations": len(unique_generations),
            "retained_shard_files": sum(
                int(item["shard_files"]) for item in unique_generations.values()
            ),
            "retained_compressed_bytes": sum(
                int(item["compressed_bytes"]) for item in unique_generations.values()
            ),
            "automatic_deletions": 0,
        },
        "activation_chain": activation_chain,
        "retention": {
            "unactivated_manifest_archive_sha256": unactivated_manifest_archives,
            "unactivated_generation_logical_sha256": unactivated_generation_names,
            "orphan_generation_logical_sha256": orphan_generation_names,
            "interrupted_staging_directories": interrupted_staging_dirs,
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = audit_generations(
            repo_path(args.manifest),
            full_shard_check=bool(args.full_shard_check),
        )
        atomic_write_json(repo_path(args.report_out), report)
    except (LifecycleAuditError, OSError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    if args.enforce and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
