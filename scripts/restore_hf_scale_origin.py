"""Restore a published real-scale HF bundle with bounded parallel downloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.hf_snapshot import ensure_iso_date, load_dotenv, resolve_setting
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
        destination = destination_root / entry["path"]
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
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report: dict[str, Any] = {"status": "failed", "errors": []}
    try:
        if args.workers <= 0 or args.timeout <= 0 or args.min_free_bytes < 0:
            raise ScaleOriginError(
                "workers/timeout must be positive and min-free nonnegative"
            )
        destination = safe_repo_path(REPO_ROOT, args.destination, "destination")
        corpus_ids = {
            item.strip() for item in args.corpus_ids.split(",") if item.strip()
        }
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
        requested_snapshot_path = args.snapshot_path.strip()
        if requested_snapshot_path:
            snapshot_path = safe_artifact_relative_path(
                requested_snapshot_path
            ).as_posix()
            selection_mode = "explicit_immutable_snapshot"
        else:
            remote_latest, _latest_sha256, latest_bytes = fetch_json_document(
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
            "preflight": preflight,
            "status": preflight["status"],
            "errors": [],
        }
        if preflight["status"] != "ok":
            raise ScaleOriginError("insufficient storage for bounded restore")

        started = time.monotonic()
        downloaded_files = 0
        downloaded_bytes = 0
        reused_files = 0
        reused_bytes = 0
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for entry in files:
                relative = safe_artifact_relative_path(entry["path"])
                future = executor.submit(
                    download_file,
                    url=f"{base_url}/{snapshot_path}/{relative.as_posix()}",
                    destination=destination / relative,
                    expected_bytes=entry["bytes"],
                    expected_sha256=entry["sha256"],
                    timeout=args.timeout,
                )
                futures[future] = relative.as_posix()
            for future in as_completed(futures):
                result = future.result()
                if result["status"] == "reused":
                    reused_files += 1
                    reused_bytes += int(result["bytes"])
                else:
                    downloaded_files += 1
                    downloaded_bytes += int(result["bytes"])

        (destination / "manifest.json").write_bytes(manifest_bytes)
        write_json(destination / "restore-reference.json", restore_reference)
        if latest_bytes is not None:
            (destination / "remote-latest.json").write_bytes(latest_bytes)
        report.update(
            {
                "status": "restored_checksums_verified",
                "files": len(files),
                "bytes": sum(int(item["bytes"]) for item in files),
                "downloaded_files": downloaded_files,
                "downloaded_bytes": downloaded_bytes,
                "reused_files": reused_files,
                "reused_bytes": reused_bytes,
                "elapsed_seconds": round(time.monotonic() - started, 6),
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
    except (OSError, ScaleOriginError, URLError, ValueError) as exc:
        report["errors"] = [f"{type(exc).__name__}: {exc}"]
        exit_code = 1
    if args.report_out.strip():
        try:
            report_path = safe_repo_path(REPO_ROOT, args.report_out, "report")
            write_json(report_path, report)
        except (OSError, ScaleOriginError) as exc:
            print(f"ERROR: cannot write report: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
