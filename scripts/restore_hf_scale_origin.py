"""Restore a published real-scale HF bundle with bounded parallel downloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.hf_snapshot import ensure_iso_date, load_dotenv, resolve_setting
from publicdata_publish.snapshot_attestation import (
    ATTESTATION_SCHEMA_VERSION,
    SIGNATURE_NAMESPACE,
    SnapshotAttestationError,
    sha256_bytes,
    verify_signed_attestation,
)
from scripts.publicar_hf_scale_snapshot import (
    ARTIFACT_CONTRACT_SCHEMA_VERSION,
    RELEASE_ID_LENGTH,
    SCHEMA_VERSION,
    ScaleOriginError,
    artifact_contract_sha256,
    immutable_snapshot_path,
    resolve_dataset_repo,
    safe_artifact_relative_path,
    safe_repo_path,
    sha256_file,
    write_json,
)
from scripts.verify_hf_scale_origin import fetch_json_document

DEFAULT_ALLOWED_SIGNERS = "docs/ops/keys/vclc-snapshot-release-2026.allowed_signers"
DEFAULT_SIGNER_IDENTITY = "vclc-snapshot-release-2026"
RESTORED_ATTESTATION_PATHS = {
    "attestation": "attestation/attestation.json",
    "signature": "attestation/attestation.json.sig",
    "public_key": "attestation/signing-key.pub",
}
MAX_INVENTORY_FINDINGS = 100


def destination_state(destination: Path) -> dict[str, Any]:
    """Describe destination before a restore without changing it."""
    destination = Path(destination)
    if not destination.exists():
        return {
            "existed": False,
            "empty": True,
            "entries": 0,
            "files": 0,
            "directories": 0,
            "symlinks": 0,
            "bytes": 0,
        }
    if destination.is_symlink() or not destination.is_dir():
        raise ScaleOriginError("restore destination must be a real directory")
    files = directories = symlinks = byte_count = 0
    for path in destination.rglob("*"):
        if path.is_symlink():
            symlinks += 1
        elif path.is_dir():
            directories += 1
        elif path.is_file():
            files += 1
            byte_count += int(path.stat().st_size)
    entries = files + directories + symlinks
    return {
        "existed": True,
        "empty": entries == 0,
        "entries": entries,
        "files": files,
        "directories": directories,
        "symlinks": symlinks,
        "bytes": byte_count,
    }


def require_empty_destination(destination: Path) -> dict[str, Any]:
    state = destination_state(destination)
    if state["empty"] is not True:
        raise ScaleOriginError("clean-room restore destination is not empty")
    return state


def safe_destination_child(destination: Path, raw_relative: str) -> Path:
    """Resolve one restore target without following a descendant symlink."""
    restored_root = destination.resolve()
    relative = safe_artifact_relative_path(raw_relative)
    candidate = restored_root / relative
    resolved = candidate.resolve()
    if restored_root not in resolved.parents:
        raise ScaleOriginError(f"restore target escapes destination: {raw_relative!r}")
    current = candidate
    while current != restored_root:
        if current.is_symlink():
            raise ScaleOriginError(
                f"restore target contains a symlink: {raw_relative!r}"
            )
        current = current.parent
    return candidate


def audit_destination_files(
    *, destination: Path, expected_files: set[str]
) -> dict[str, Any]:
    """Compare a restored directory with one exact file allowlist."""
    restored_root = destination.resolve()
    missing = set(expected_files)
    actual_files = 0
    actual_bytes = 0
    symlinks: list[str] = []
    symlink_count = 0
    undeclared_files: list[str] = []
    undeclared_count = 0
    for path in restored_root.rglob("*"):
        relative = path.relative_to(restored_root).as_posix()
        if path.is_symlink():
            symlink_count += 1
            if len(symlinks) < MAX_INVENTORY_FINDINGS:
                symlinks.append(relative)
        elif path.is_file():
            actual_files += 1
            actual_bytes += int(path.stat().st_size)
            if relative in missing:
                missing.remove(relative)
            else:
                undeclared_count += 1
                if len(undeclared_files) < MAX_INVENTORY_FINDINGS:
                    undeclared_files.append(relative)
    missing_count = len(missing)
    return {
        "expected_files": len(expected_files),
        "actual_files": actual_files,
        "actual_bytes": actual_bytes,
        "missing_files_count": missing_count,
        "missing_files": sorted(missing)[:MAX_INVENTORY_FINDINGS],
        "undeclared_files_count": undeclared_count,
        "undeclared_files": sorted(undeclared_files),
        "symlinks_count": symlink_count,
        "symlinks": sorted(symlinks),
        "findings_limit": MAX_INVENTORY_FINDINGS,
        "passed": missing_count == 0
        and undeclared_count == 0
        and symlink_count == 0
        and actual_files == len(expected_files),
    }


def fetch_bytes(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "vota-con-la-chola/restore-hf-scale-origin",
            "Accept": "application/octet-stream,*/*",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def verify_restore_attestation_files(
    *,
    manifest_path: Path,
    attestation_path: Path,
    signature_path: Path,
    public_key_path: Path,
    allowed_signers_path: Path,
    signer_identity: str,
    manifest_url: str,
    snapshot_path: str,
    snapshot_date: str,
    attestation_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify signed restore subject plus optional mutable-pointer bindings."""
    verification = verify_signed_attestation(
        manifest_path=manifest_path,
        attestation_path=attestation_path,
        signature_path=signature_path,
        allowed_signers_path=allowed_signers_path,
        signer_identity=signer_identity,
        expected_manifest_url=manifest_url,
        expected_snapshot_path=snapshot_path,
        expected_snapshot_date=snapshot_date,
        discovery_public_key_path=public_key_path,
    )
    errors = list(verification.get("errors") or [])
    expected_paths = {
        "attestation": f"{snapshot_path}/attestation/attestation.json",
        "signature": f"{snapshot_path}/attestation/attestation.json.sig",
        "public_key": f"{snapshot_path}/attestation/signing-key.pub",
    }
    if attestation_meta is not None:
        if attestation_meta.get("schema_version") != ATTESTATION_SCHEMA_VERSION:
            errors.append("latest pointer attestation schema is unsupported")
        for name, expected_path in expected_paths.items():
            if attestation_meta.get(name) != expected_path:
                errors.append(f"latest pointer {name} path escapes selected snapshot")
        if attestation_meta.get("signer_identity") != signer_identity:
            errors.append("latest pointer signer identity differs")
        if attestation_meta.get("signature_namespace") != SIGNATURE_NAMESPACE:
            errors.append("latest pointer signature namespace differs")
        checks = verification.get("checks")
        checks = checks if isinstance(checks, dict) else {}
        for name, path, check_key in (
            ("attestation", attestation_path, "attestation_sha256"),
            ("signature", signature_path, "signature_sha256"),
        ):
            declared = str(attestation_meta.get(f"{name}_sha256") or "")
            try:
                actual = sha256_bytes(path.read_bytes())
            except OSError as exc:
                errors.append(f"restored {name} cannot be read: {exc}")
                continue
            if declared != actual or checks.get(check_key) != actual:
                errors.append(f"latest pointer {name} checksum differs")
        if attestation_meta.get("public_key_fingerprint") != checks.get(
            "attested_public_key_fingerprint"
        ):
            errors.append("latest pointer public-key fingerprint differs")
    verification["errors"] = errors
    verification["passed"] = not errors
    verification["status"] = "ok" if not errors else "error"
    verification["remote_paths"] = expected_paths
    return verification


def restored_attestation_metadata(
    verification: dict[str, Any], *, snapshot_path: str
) -> dict[str, Any]:
    checks = verification.get("checks")
    checks = checks if isinstance(checks, dict) else {}
    return {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "attestation": f"{snapshot_path}/attestation/attestation.json",
        "signature": f"{snapshot_path}/attestation/attestation.json.sig",
        "public_key": f"{snapshot_path}/attestation/signing-key.pub",
        "attestation_sha256": checks.get("attestation_sha256"),
        "signature_sha256": checks.get("signature_sha256"),
        "public_key_fingerprint": checks.get("attested_public_key_fingerprint"),
        "signer_identity": checks.get("signer_identity"),
        "signature_namespace": checks.get("signature_namespace"),
        "restored_files": dict(RESTORED_ATTESTATION_PATHS),
    }


def fetch_and_verify_restore_attestation(
    *,
    base_url: str,
    manifest_bytes: bytes,
    manifest_url: str,
    snapshot_path: str,
    snapshot_date: str,
    allowed_signers_path: Path,
    signer_identity: str,
    timeout: float,
    attestation_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    expected_paths = {
        "attestation": f"{snapshot_path}/attestation/attestation.json",
        "signature": f"{snapshot_path}/attestation/attestation.json.sig",
        "public_key": f"{snapshot_path}/attestation/signing-key.pub",
    }
    with tempfile.TemporaryDirectory(prefix="vclc-restore-attestation-") as temp_dir:
        temp_root = Path(temp_dir)
        local_paths = {
            "manifest": temp_root / "manifest.json",
            "attestation": temp_root / "attestation.json",
            "signature": temp_root / "attestation.json.sig",
            "public_key": temp_root / "signing-key.pub",
        }
        local_paths["manifest"].write_bytes(manifest_bytes)
        for name in ("attestation", "signature", "public_key"):
            local_paths[name].write_bytes(
                fetch_bytes(f"{base_url}/{expected_paths[name]}", timeout)
            )
        verification = verify_restore_attestation_files(
            manifest_path=local_paths["manifest"],
            attestation_path=local_paths["attestation"],
            signature_path=local_paths["signature"],
            public_key_path=local_paths["public_key"],
            allowed_signers_path=allowed_signers_path,
            signer_identity=signer_identity,
            manifest_url=manifest_url,
            snapshot_path=snapshot_path,
            snapshot_date=snapshot_date,
            attestation_meta=attestation_meta,
        )
        verification["_verified_artifact_bytes"] = {
            name: local_paths[name].read_bytes()
            for name in ("attestation", "signature", "public_key")
        }
    if verification.get("passed") is not True:
        raise ScaleOriginError(
            "signed restore attestation failed: "
            + "; ".join(str(item) for item in verification.get("errors", []))
        )
    return verification


def selected_manifest_files(
    manifest: dict[str, Any], corpus_ids: set[str]
) -> list[dict[str, Any]]:
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise ScaleOriginError("remote scale manifest has no files array")
    known_ids = {
        str(item.get("id"))
        for item in manifest.get("corpora", [])
        if isinstance(item, dict) and item.get("id")
    }
    unknown = corpus_ids - known_ids
    if unknown:
        raise ScaleOriginError("unknown corpus IDs: " + ", ".join(sorted(unknown)))
    selected: list[dict[str, Any]] = []
    for entry in raw_files:
        if not isinstance(entry, dict):
            raise ScaleOriginError("remote scale manifest contains a non-object file")
        relative = safe_artifact_relative_path(str(entry.get("path") or ""))
        parts = relative.parts
        entry_corpus = parts[1] if len(parts) >= 2 and parts[0] == "corpora" else ""
        if corpus_ids and entry_corpus and entry_corpus not in corpus_ids:
            continue
        if (
            corpus_ids
            and not entry_corpus
            and relative.as_posix()
            not in {
                "real-corpus-registry.json",
                "scale-readiness.json",
            }
        ):
            continue
        expected_bytes = int(entry.get("bytes") or -1)
        expected_sha256 = str(entry.get("sha256") or "")
        if expected_bytes < 0 or len(expected_sha256) != 64:
            raise ScaleOriginError(
                f"invalid remote file declaration: {relative.as_posix()}"
            )
        selected.append(
            {
                "path": relative.as_posix(),
                "bytes": expected_bytes,
                "sha256": expected_sha256,
                "kind": entry.get("kind"),
                "corpus_id": entry_corpus,
            }
        )
    selected.sort(key=lambda item: item["path"])
    return selected


def restore_preflight(
    *, destination_root: Path, files: list[dict[str, Any]], min_free_bytes: int
) -> dict[str, Any]:
    missing_bytes = 0
    reusable_files = 0
    reusable_bytes = 0
    for entry in files:
        destination = safe_destination_child(destination_root, entry["path"])
        if (
            destination.is_file()
            and int(destination.stat().st_size) == entry["bytes"]
            and sha256_file(destination) == entry["sha256"]
        ):
            reusable_files += 1
            reusable_bytes += entry["bytes"]
        else:
            missing_bytes += entry["bytes"]
    destination_root.mkdir(parents=True, exist_ok=True)
    free_bytes = int(shutil.disk_usage(destination_root).free)
    required_bytes = int(min_free_bytes) + missing_bytes
    return {
        "status": "ok" if free_bytes >= required_bytes else "blocked_storage",
        "files": len(files),
        "bytes": sum(int(item["bytes"]) for item in files),
        "reusable_files": reusable_files,
        "reusable_bytes": reusable_bytes,
        "missing_files": len(files) - reusable_files,
        "missing_bytes": missing_bytes,
        "free_bytes": free_bytes,
        "minimum_free_after_restore_bytes": int(min_free_bytes),
        "required_bytes": required_bytes,
        "headroom_bytes": free_bytes - required_bytes,
    }


def validate_restore_reference(
    *,
    manifest: dict[str, Any],
    manifest_sha256: str,
    snapshot_path: str,
    selection_mode: str,
) -> dict[str, Any]:
    """Build a normalized pointer for latest or explicit immutable recovery."""
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ScaleOriginError(
            f"unsupported scale origin schema: {manifest.get('schema_version')!r}"
        )
    snapshot_date = ensure_iso_date(str(manifest.get("snapshot_date") or ""))
    expected_snapshot_path = immutable_snapshot_path(
        snapshot_date, manifest_sha256
    ).as_posix()
    if snapshot_path != expected_snapshot_path:
        raise ScaleOriginError(
            "remote snapshot path is not content-addressed by manifest checksum"
        )
    artifact_contract = manifest.get("artifact_contract")
    if (
        not isinstance(artifact_contract, dict)
        or artifact_contract.get("schema_version") != ARTIFACT_CONTRACT_SCHEMA_VERSION
    ):
        raise ScaleOriginError("unsupported scale artifact contract schema")
    contract_sha256 = artifact_contract_sha256(manifest)
    if artifact_contract.get("sha256") != contract_sha256:
        raise ScaleOriginError("remote scale artifact contract checksum is invalid")
    return {
        "schema_version": SCHEMA_VERSION,
        "project": manifest.get("project"),
        "snapshot_date": snapshot_date,
        "release_id": manifest_sha256[:RELEASE_ID_LENGTH],
        "snapshot_path": snapshot_path,
        "manifest_sha256": manifest_sha256,
        "artifact_contract_sha256": contract_sha256,
        "selection_mode": selection_mode,
    }


def download_file(
    *,
    url: str,
    destination: Path,
    expected_bytes: int,
    expected_sha256: str,
    timeout: float,
) -> dict[str, Any]:
    if (
        destination.is_file()
        and int(destination.stat().st_size) == expected_bytes
        and sha256_file(destination) == expected_sha256
    ):
        return {"status": "reused", "bytes": expected_bytes}
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.partial-{os.getpid()}")
    digest = hashlib.sha256()
    written = 0
    request = Request(
        url,
        headers={
            "User-Agent": "vota-con-la-chola/restore-hf-scale-origin",
            "Accept": "application/octet-stream,*/*",
        },
    )
    try:
        with (
            urlopen(request, timeout=timeout) as response,
            partial.open("wb") as handle,
        ):
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > expected_bytes:
                    raise ScaleOriginError(
                        f"download exceeds declared bytes: {destination.name}"
                    )
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if written != expected_bytes:
            raise ScaleOriginError(
                f"download byte mismatch: {destination.name} {written}/{expected_bytes}"
            )
        if digest.hexdigest() != expected_sha256:
            raise ScaleOriginError(f"download checksum mismatch: {destination.name}")
        os.replace(partial, destination)
        return {"status": "downloaded", "bytes": written}
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def download_manifest_files_bounded(
    *,
    base_url: str,
    snapshot_path: str,
    destination: Path,
    files: list[dict[str, Any]],
    workers: int,
    timeout: float,
) -> dict[str, int]:
    """Download with O(workers) queued futures, even for huge manifests."""
    iterator = iter(files)
    pending: dict[Future[dict[str, Any]], str] = {}
    downloaded_files = downloaded_bytes = reused_files = reused_bytes = 0
    max_pending = 0
    window = max(workers, workers * 2)

    def submit_one(executor: ThreadPoolExecutor) -> bool:
        nonlocal max_pending
        try:
            entry = next(iterator)
        except StopIteration:
            return False
        relative = safe_artifact_relative_path(entry["path"])
        future = executor.submit(
            download_file,
            url=f"{base_url}/{snapshot_path}/{relative.as_posix()}",
            destination=safe_destination_child(destination, relative.as_posix()),
            expected_bytes=entry["bytes"],
            expected_sha256=entry["sha256"],
            timeout=timeout,
        )
        pending[future] = relative.as_posix()
        max_pending = max(max_pending, len(pending))
        return True

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for _ in range(window):
            if not submit_one(executor):
                break
        while pending:
            completed, _not_done = wait(
                pending,
                return_when=FIRST_COMPLETED,
            )
            for future in completed:
                pending.pop(future)
                result = future.result()
                if result["status"] == "reused":
                    reused_files += 1
                    reused_bytes += int(result["bytes"])
                else:
                    downloaded_files += 1
                    downloaded_bytes += int(result["bytes"])
                submit_one(executor)
    return {
        "downloaded_files": downloaded_files,
        "downloaded_bytes": downloaded_bytes,
        "reused_files": reused_files,
        "reused_bytes": reused_bytes,
        "max_pending_downloads": max_pending,
        "download_queue_limit": window,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-repo", default="")
    parser.add_argument("--hf-username", default="")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--destination", required=True)
    parser.add_argument(
        "--snapshot-path",
        default="",
        help=(
            "restore an explicit immutable scale/snapshots/<date>/<sha256> release "
            "instead of following scale/latest.json"
        ),
    )
    parser.add_argument("--corpus-ids", default="")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--min-free-bytes", type=int, default=10 * 1024**3)
    parser.add_argument("--allowed-signers", default=DEFAULT_ALLOWED_SIGNERS)
    parser.add_argument("--signer-identity", default=DEFAULT_SIGNER_IDENTITY)
    parser.add_argument(
        "--require-signed",
        action="store_true",
        help="verify and retain the signed snapshot attestation",
    )
    parser.add_argument(
        "--require-empty-destination",
        action="store_true",
        help="enforce a no-reuse clean-room restore; implies --require-signed",
    )
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report: dict[str, Any] = {"status": "failed", "errors": []}
    report_path: Path | None = None
    report_path_rejected = False
    try:
        if args.workers <= 0 or args.timeout <= 0 or args.min_free_bytes < 0:
            raise ScaleOriginError(
                "workers/timeout must be positive and min-free nonnegative"
            )
        destination = safe_repo_path(REPO_ROOT, args.destination, "destination")
        if args.report_out.strip():
            report_path = safe_repo_path(REPO_ROOT, args.report_out, "report")
            if args.require_empty_destination and (
                report_path == destination or destination in report_path.parents
            ):
                report_path_rejected = True
                raise ScaleOriginError(
                    "clean-room restore report must be outside destination"
                )
        initial_destination = (
            require_empty_destination(destination)
            if args.require_empty_destination
            else destination_state(destination)
        )
        corpus_ids = {
            item.strip() for item in args.corpus_ids.split(",") if item.strip()
        }
        signed_required = bool(args.require_signed or args.require_empty_destination)
        allowed_signers_path: Path | None = None
        if signed_required:
            allowed_signers_path = safe_repo_path(
                REPO_ROOT, args.allowed_signers, "allowed signers"
            )
            if not allowed_signers_path.is_file():
                raise ScaleOriginError("trusted allowed_signers file is missing")
        dotenv_values = load_dotenv(Path(args.env_file))
        username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
        raw_repo = resolve_setting(
            "HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values
        )
        dataset_repo = resolve_dataset_repo(raw_repo, username)
        base_url = f"https://huggingface.co/datasets/{dataset_repo}/resolve/main"
        latest_url = f"{base_url}/scale/latest.json"
        remote_latest: dict[str, Any] | None = None
        latest_bytes: bytes | None = None
        latest_sha256: str | None = None
        requested_snapshot_path = args.snapshot_path.strip()
        if requested_snapshot_path:
            snapshot_path = safe_artifact_relative_path(
                requested_snapshot_path
            ).as_posix()
            selection_mode = "explicit_immutable_snapshot"
        else:
            remote_latest, latest_sha256, latest_bytes = fetch_json_document(
                latest_url, args.timeout
            )
            if remote_latest.get("schema_version") != SCHEMA_VERSION:
                raise ScaleOriginError(
                    "unsupported scale latest-pointer schema: "
                    f"{remote_latest.get('schema_version')!r}"
                )
            snapshot_path = safe_artifact_relative_path(
                str(remote_latest.get("snapshot_path") or "")
            ).as_posix()
            selection_mode = "latest_pointer"
        if not snapshot_path.startswith("scale/snapshots/"):
            raise ScaleOriginError(f"unsafe remote snapshot path: {snapshot_path!r}")
        manifest_url = f"{base_url}/{snapshot_path}/manifest.json"
        manifest, manifest_sha256, manifest_bytes = fetch_json_document(
            manifest_url, args.timeout
        )
        restore_reference = validate_restore_reference(
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            snapshot_path=snapshot_path,
            selection_mode=selection_mode,
        )
        contract_sha256 = str(restore_reference["artifact_contract_sha256"])
        if remote_latest is not None:
            if remote_latest.get("artifact_contract_sha256") != contract_sha256:
                raise ScaleOriginError(
                    "remote latest pointer artifact contract checksum differs"
                )
            if manifest_sha256 != remote_latest.get("manifest_sha256"):
                raise ScaleOriginError(
                    "remote manifest checksum differs from latest pointer"
                )
            if remote_latest.get("snapshot_date") != restore_reference["snapshot_date"]:
                raise ScaleOriginError(
                    "remote latest and manifest snapshot dates differ"
                )
            if remote_latest.get("release_id") != restore_reference["release_id"]:
                raise ScaleOriginError(
                    "remote release_id does not match manifest checksum"
                )
        attestation_verification: dict[str, Any] | None = None
        attestation_artifacts: dict[str, bytes] = {}
        if signed_required:
            attestation_meta = (
                remote_latest.get("attestation")
                if isinstance(remote_latest, dict)
                else None
            )
            if remote_latest is not None and not isinstance(attestation_meta, dict):
                raise ScaleOriginError(
                    "latest pointer has no signed attestation metadata"
                )
            assert allowed_signers_path is not None
            attestation_verification = fetch_and_verify_restore_attestation(
                base_url=base_url,
                manifest_bytes=manifest_bytes,
                manifest_url=manifest_url,
                snapshot_path=snapshot_path,
                snapshot_date=str(restore_reference["snapshot_date"]),
                allowed_signers_path=allowed_signers_path,
                signer_identity=args.signer_identity,
                timeout=args.timeout,
                attestation_meta=(
                    attestation_meta if isinstance(attestation_meta, dict) else None
                ),
            )
            raw_artifacts = attestation_verification.pop("_verified_artifact_bytes", {})
            if not isinstance(raw_artifacts, dict) or set(raw_artifacts) != set(
                RESTORED_ATTESTATION_PATHS
            ):
                raise ScaleOriginError(
                    "verified attestation artifacts were not retained for restore"
                )
            if not all(isinstance(value, bytes) for value in raw_artifacts.values()):
                raise ScaleOriginError("verified attestation artifact is not bytes")
            attestation_artifacts = raw_artifacts
            restore_reference.update(
                {
                    "dataset_repo": dataset_repo,
                    "manifest_url": manifest_url,
                    "attestation": restored_attestation_metadata(
                        attestation_verification,
                        snapshot_path=snapshot_path,
                    ),
                }
            )
            if latest_sha256 is not None:
                restore_reference["remote_latest_sha256"] = latest_sha256
        files = selected_manifest_files(manifest, corpus_ids)
        preflight = restore_preflight(
            destination_root=destination,
            files=files,
            min_free_bytes=args.min_free_bytes,
        )
        report = {
            "schema_version": "real-scale-origin-restore-v1",
            "dataset_repo": dataset_repo,
            "snapshot_date": restore_reference["snapshot_date"],
            "snapshot_path": snapshot_path,
            "selection_mode": selection_mode,
            "selected_corpus_ids": sorted(corpus_ids),
            "manifest_sha256": manifest_sha256,
            "artifact_contract_sha256": contract_sha256,
            "remote_method": "GET_only",
            "credentials_used": False,
            "remote_mutation": False,
            "signed_attestation_required": signed_required,
            "signed_attestation_verified": (
                attestation_verification is not None
                and attestation_verification.get("passed") is True
            ),
            "attestation": (
                {
                    "status": attestation_verification.get("status"),
                    "attestation_sha256": attestation_verification.get(
                        "checks", {}
                    ).get("attestation_sha256"),
                    "signature_sha256": attestation_verification.get("checks", {}).get(
                        "signature_sha256"
                    ),
                    "signer_identity": attestation_verification.get("checks", {}).get(
                        "signer_identity"
                    ),
                    "public_key_fingerprint": attestation_verification.get(
                        "checks", {}
                    ).get("attested_public_key_fingerprint"),
                    "signature_namespace": attestation_verification.get(
                        "checks", {}
                    ).get("signature_namespace"),
                    "errors": attestation_verification.get("errors", []),
                }
                if attestation_verification is not None
                else None
            ),
            "isolation": {
                "empty_destination_required": bool(args.require_empty_destination),
                "destination_initial_state": initial_destination,
            },
            "preflight": preflight,
            "status": preflight["status"],
            "errors": [],
            "publish_eligible": False,
            "public_promotion_eligible": False,
        }
        if preflight["status"] != "ok":
            raise ScaleOriginError("insufficient storage for bounded restore")

        started = time.monotonic()
        download_summary = download_manifest_files_bounded(
            base_url=base_url,
            snapshot_path=snapshot_path,
            destination=destination,
            files=files,
            workers=args.workers,
            timeout=args.timeout,
        )
        downloaded_files = download_summary["downloaded_files"]
        downloaded_bytes = download_summary["downloaded_bytes"]
        reused_files = download_summary["reused_files"]
        reused_bytes = download_summary["reused_bytes"]

        safe_destination_child(destination, "manifest.json").write_bytes(manifest_bytes)
        write_json(
            safe_destination_child(destination, "restore-reference.json"),
            restore_reference,
        )
        if latest_bytes is not None:
            safe_destination_child(destination, "remote-latest.json").write_bytes(
                latest_bytes
            )
        for name, relative in RESTORED_ATTESTATION_PATHS.items():
            if name not in attestation_artifacts:
                continue
            control_path = safe_destination_child(destination, relative)
            control_path.parent.mkdir(parents=True, exist_ok=True)
            control_path.write_bytes(attestation_artifacts[name])
        partial_files = sorted(
            path.relative_to(destination).as_posix()
            for path in destination.rglob("*")
            if path.is_file() and ".partial-" in path.name
        )
        if partial_files:
            raise ScaleOriginError("partial restore files remain after completion")
        if args.require_empty_destination and reused_files != 0:
            raise ScaleOriginError("clean-room restore unexpectedly reused files")
        expected_files = {str(entry["path"]) for entry in files}
        expected_files.update({"manifest.json", "restore-reference.json"})
        if latest_bytes is not None:
            expected_files.add("remote-latest.json")
        if signed_required:
            expected_files.update(RESTORED_ATTESTATION_PATHS.values())
        inventory = audit_destination_files(
            destination=destination,
            expected_files=expected_files,
        )
        if args.require_empty_destination and inventory["passed"] is not True:
            raise ScaleOriginError(
                "clean-room restore inventory is not exact: "
                f"missing={inventory['missing_files'][:5]} "
                f"undeclared={inventory['undeclared_files'][:5]} "
                f"symlinks={inventory['symlinks'][:5]}"
            )
        report.update(
            {
                "status": "restored_checksums_verified",
                "files": len(files),
                "bytes": sum(int(item["bytes"]) for item in files),
                "bundle_files": inventory["actual_files"],
                "bundle_bytes": inventory["actual_bytes"],
                "control_files": inventory["actual_files"] - len(files),
                "downloaded_files": downloaded_files,
                "downloaded_bytes": downloaded_bytes,
                "reused_files": reused_files,
                "reused_bytes": reused_bytes,
                "max_pending_downloads": download_summary["max_pending_downloads"],
                "download_queue_limit": download_summary["download_queue_limit"],
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "partial_files": partial_files,
                "inventory": inventory,
                "clean_room_restore": bool(args.require_empty_destination)
                and reused_files == 0
                and initial_destination["empty"] is True
                and signed_required
                and inventory["passed"] is True,
                "public_domain_personal_information_retained": True,
            }
        )
        exit_code = 0
    except HTTPError as exc:
        report["status"] = (
            "blocked_remote_scale_origin_missing"
            if exc.code == 404
            else "blocked_remote_scale_origin_http_error"
        )
        report["errors"] = [f"HTTP {exc.code}: {exc.reason}"]
        exit_code = 1
    except (
        OSError,
        ScaleOriginError,
        SnapshotAttestationError,
        URLError,
        ValueError,
    ) as exc:
        if report.get("status") == "ok":
            report["status"] = "failed"
        report["errors"] = [f"{type(exc).__name__}: {exc}"]
        exit_code = 1
    if args.report_out.strip() and not report_path_rejected:
        try:
            if report_path is None:
                report_path = safe_repo_path(REPO_ROOT, args.report_out, "report")
            write_json(report_path, report)
        except (OSError, ScaleOriginError) as exc:
            print(f"ERROR: cannot write report: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
