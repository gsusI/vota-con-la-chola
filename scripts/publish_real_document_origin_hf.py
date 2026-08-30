#!/usr/bin/env python3
"""Validate or publish the exact real document-origin release to Hugging Face."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.object_store import hash_file
from publicdata_publish.hf_snapshot import load_dotenv, resolve_setting
from scripts.prepare_real_document_origin_release import (
    POINTER_SCHEMA,
    RELEASE_SCHEMA,
    UPLOAD_PLAN_SCHEMA,
    atomic_write,
    utc_now,
)

REPORT_SCHEMA = "real_document_origin_hf_publication_v1"
PLACEHOLDER_VALUES = {"", "changeme", "replace-me", "your-token-here"}


class OriginPublicationError(RuntimeError):
    """Raised when an append-only publication invariant fails."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upload-plan",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-upload-plan.json"
        ),
    )
    parser.add_argument("--dataset-repo", default="")
    parser.add_argument("--hf-username", default="")
    parser.add_argument("--hf-token", default="")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--report-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-hf-publish-dry-run.json"
        ),
    )
    parser.add_argument("--remote-preflight", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--authorize-remote-write", action="store_true")
    parser.add_argument("--batch-files", type=int, default=4)
    parser.add_argument("--batch-bytes", type=int, default=500 * 1024 * 1024)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def repo_path(value: str, label: str) -> Path:
    relative = Path(str(value or "").strip())
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise OriginPublicationError(f"unsafe {label}: {value!r}")
    candidate = (REPO_ROOT / relative).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise OriginPublicationError(f"{label} escapes repository: {value}") from exc
    return candidate


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OriginPublicationError(f"cannot load {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OriginPublicationError(f"{label} root is not an object")
    return payload


def validate_relative_path(value: str, label: str) -> str:
    relative = Path(str(value or "").strip())
    if (
        not str(relative)
        or relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
    ):
        raise OriginPublicationError(f"unsafe {label}: {value!r}")
    return relative.as_posix()


def resolve_dataset_repo(raw_repo: str, username: str) -> str:
    repo = str(raw_repo or "").strip().strip("/")
    owner = str(username or "").strip().strip("/")
    if not repo:
        if not owner:
            raise OriginPublicationError(
                "cannot resolve dataset repo: set HF_DATASET_REPO_ID or HF_USERNAME"
            )
        repo = f"{owner}/vota-con-la-chola-data"
    elif "/" not in repo:
        if not owner:
            raise OriginPublicationError(
                "HF_DATASET_REPO_ID has no owner and HF_USERNAME is not configured"
            )
        repo = f"{owner}/{repo}"
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise OriginPublicationError(f"invalid Hugging Face dataset repo: {repo!r}")
    return repo


def validate_local_upload_plan(plan_path: Path) -> dict[str, Any]:
    plan = load_json(plan_path, "upload plan")
    if plan.get("schema_version") != UPLOAD_PLAN_SCHEMA:
        raise OriginPublicationError("upload plan schema drifted")
    policy = plan.get("policy") or {}
    required_policy = {
        "append_only": True,
        "delete_operations_forbidden": True,
        "immutable_manifest_uploaded_after_data": True,
        "latest_pointer_uploaded_last": True,
        "resume_requires_remote_checksum_parity": True,
    }
    if any(policy.get(key) is not value for key, value in required_policy.items()):
        raise OriginPublicationError("upload plan append-only policy drifted")
    release_prefix = validate_relative_path(
        str(plan.get("release_prefix") or ""), "release prefix"
    )
    if not release_prefix.startswith("document-origin/snapshots/"):
        raise OriginPublicationError(
            "release prefix is not immutable/content-addressed"
        )
    release_id = str(plan.get("release_id") or "")
    if len(release_id) != 64 or release_prefix.split("/")[-1] != release_id:
        raise OriginPublicationError("release identity drifted")

    immutable = plan.get("immutable_files")
    if not isinstance(immutable, list) or not immutable:
        raise OriginPublicationError("upload plan has no immutable files")
    local_files: list[dict[str, Any]] = []
    remote_paths: set[str] = set()
    for position, raw in enumerate(immutable):
        if not isinstance(raw, dict):
            raise OriginPublicationError("upload plan file descriptor drifted")
        source_path = validate_relative_path(
            str(raw.get("source_path") or ""), "source path"
        )
        release_path = validate_relative_path(
            str(raw.get("release_path") or ""), "release path"
        )
        remote_path = f"{release_prefix}/{release_path}"
        if remote_path in remote_paths:
            raise OriginPublicationError(f"duplicate remote path: {remote_path}")
        source = repo_path(source_path, "source path")
        if not source.is_file():
            raise OriginPublicationError(
                f"local release file is missing: {source_path}"
            )
        actual_sha256, actual_bytes = hash_file(source)
        if actual_sha256 != str(raw.get("sha256") or "") or actual_bytes != int(
            raw.get("bytes") or -1
        ):
            raise OriginPublicationError(f"local release file drifted: {source_path}")
        local_files.append(
            {
                "position": position,
                "source_path": source_path,
                "source": source,
                "remote_path": remote_path,
                "bytes": actual_bytes,
                "sha256": actual_sha256,
                "kind": str(raw.get("kind") or ""),
            }
        )
        remote_paths.add(remote_path)

    controls: dict[str, dict[str, Any]] = {}
    for key, expected_schema in (
        ("release_manifest", RELEASE_SCHEMA),
        ("latest_pointer", POINTER_SCHEMA),
    ):
        raw = plan.get(key)
        if not isinstance(raw, dict):
            raise OriginPublicationError(f"upload plan {key} descriptor drifted")
        source_path = validate_relative_path(
            str(raw.get("source_path") or ""), f"{key} source path"
        )
        remote_path = validate_relative_path(
            str(raw.get("remote_path") or ""), f"{key} remote path"
        )
        if key == "release_manifest" and remote_path != (
            f"{release_prefix}/release-manifest.json"
        ):
            raise OriginPublicationError(
                "release manifest is outside immutable release"
            )
        if key == "latest_pointer" and remote_path != "document-origin/latest.json":
            raise OriginPublicationError("latest pointer path drifted")
        source = repo_path(source_path, f"{key} source path")
        payload = load_json(source, key)
        actual_sha256, actual_bytes = hash_file(source)
        if (
            payload.get("schema_version") != expected_schema
            or payload.get("release_id") != release_id
            or payload.get("release_prefix") != release_prefix
            or actual_sha256 != str(raw.get("sha256") or "")
            or actual_bytes != int(raw.get("bytes") or -1)
        ):
            raise OriginPublicationError(f"{key} identity or checksum drifted")
        controls[key] = {
            "source_path": source_path,
            "source": source,
            "remote_path": remote_path,
            "bytes": actual_bytes,
            "sha256": actual_sha256,
        }

    release_manifest = load_json(
        controls["release_manifest"]["source"], "release manifest"
    )
    manifest_files = release_manifest.get("files")
    manifest_contract = [
        {
            "release_path": item["remote_path"][len(release_prefix) + 1 :],
            "bytes": item["bytes"],
            "sha256": item["sha256"],
            "kind": item["kind"],
        }
        for item in local_files
    ]
    if manifest_files != manifest_contract:
        raise OriginPublicationError(
            "release manifest inventory drifted from upload plan"
        )
    if (release_manifest.get("policy") or {}).get(
        "official_public_domain_personal_information_retained"
    ) is not True:
        raise OriginPublicationError("public-domain identity retention policy drifted")
    if (release_manifest.get("policy") or {}).get(
        "synthetic_or_mock_records_forbidden"
    ) is not True:
        raise OriginPublicationError("real-record-only policy drifted")
    return {
        "plan": plan,
        "release_id": release_id,
        "release_prefix": release_prefix,
        "immutable_files": local_files,
        "release_manifest": controls["release_manifest"],
        "latest_pointer": controls["latest_pointer"],
        "total_files": len(local_files),
        "total_bytes": sum(int(item["bytes"]) for item in local_files),
    }


def batches(
    items: list[dict[str, Any]], *, max_files: int, max_bytes: int
) -> Iterable[list[dict[str, Any]]]:
    if max_files < 1 or max_bytes < 1:
        raise OriginPublicationError("upload batch limits must be positive")
    current: list[dict[str, Any]] = []
    current_bytes = 0
    for item in items:
        item_bytes = int(item["bytes"])
        if item_bytes > max_bytes:
            raise OriginPublicationError(
                f"one release file exceeds batch byte limit: {item['remote_path']}"
            )
        if current and (
            len(current) >= max_files or current_bytes + item_bytes > max_bytes
        ):
            yield current
            current = []
            current_bytes = 0
        current.append(item)
        current_bytes += item_bytes
    if current:
        yield current


def _entry_value(entry: Any, key: str, default: Any = None) -> Any:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _lfs_sha256(entry: Any) -> str:
    lfs = _entry_value(entry, "lfs")
    if isinstance(lfs, dict):
        return str(lfs.get("sha256") or "")
    return str(getattr(lfs, "sha256", "") or "")


def list_remote_files(
    api: Any,
    *,
    dataset_repo: str,
    path_in_repo: str,
    revision: str = "main",
) -> dict[str, dict[str, Any]]:
    try:
        entries = api.list_repo_tree(
            repo_id=dataset_repo,
            path_in_repo=path_in_repo,
            recursive=True,
            expand=True,
            repo_type="dataset",
            revision=revision,
        )
        result: dict[str, dict[str, Any]] = {}
        for entry in entries:
            entry_type = str(_entry_value(entry, "type", ""))
            path = str(_entry_value(entry, "path", ""))
            if entry_type != "file" or not path:
                continue
            result[path] = {
                "bytes": int(_entry_value(entry, "size", 0) or 0),
                "lfs_sha256": _lfs_sha256(entry),
            }
        return result
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 404:
            return {}
        raise OriginPublicationError(
            f"cannot list remote path {path_in_repo}: {type(exc).__name__}: {exc}"
        ) from exc


def remote_sha256(
    *,
    dataset_repo: str,
    remote_path: str,
    revision: str,
    token: str,
    timeout: float,
) -> tuple[str, int]:
    quoted_repo = "/".join(
        urllib.parse.quote(part, safe="") for part in dataset_repo.split("/")
    )
    quoted_revision = urllib.parse.quote(revision, safe="")
    quoted_path = urllib.parse.quote(remote_path, safe="/")
    url = (
        f"https://huggingface.co/datasets/{quoted_repo}/resolve/"
        f"{quoted_revision}/{quoted_path}?download=true"
    )
    headers = {"User-Agent": "vota-con-la-chola-origin-verifier/1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    digest = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
    except (OSError, urllib.error.URLError) as exc:
        raise OriginPublicationError(
            f"cannot verify remote file {remote_path}: {type(exc).__name__}: {exc}"
        ) from exc
    return digest.hexdigest(), size


def classify_remote_inventory(
    *,
    expected: list[dict[str, Any]],
    remote: dict[str, dict[str, Any]],
    dataset_repo: str,
    revision: str,
    token: str,
    timeout: float,
) -> dict[str, Any]:
    expected_by_path = {str(item["remote_path"]): item for item in expected}
    missing: list[str] = []
    exact: list[str] = []
    conflicts: list[dict[str, Any]] = []
    for path, item in expected_by_path.items():
        observed = remote.get(path)
        if observed is None:
            missing.append(path)
            continue
        observed_bytes = int(observed.get("bytes") or 0)
        observed_sha256 = str(observed.get("lfs_sha256") or "")
        if observed_bytes != int(item["bytes"]):
            conflicts.append(
                {
                    "path": path,
                    "reason": "bytes_mismatch",
                    "expected_bytes": int(item["bytes"]),
                    "observed_bytes": observed_bytes,
                }
            )
            continue
        if not observed_sha256:
            observed_sha256, downloaded_bytes = remote_sha256(
                dataset_repo=dataset_repo,
                remote_path=path,
                revision=revision,
                token=token,
                timeout=timeout,
            )
            if downloaded_bytes != observed_bytes:
                conflicts.append(
                    {
                        "path": path,
                        "reason": "downloaded_bytes_mismatch",
                        "expected_bytes": observed_bytes,
                        "observed_bytes": downloaded_bytes,
                    }
                )
                continue
        if observed_sha256 != str(item["sha256"]):
            conflicts.append(
                {
                    "path": path,
                    "reason": "sha256_mismatch",
                    "expected_sha256": str(item["sha256"]),
                    "observed_sha256": observed_sha256,
                }
            )
            continue
        exact.append(path)
    unexpected = sorted(set(remote) - set(expected_by_path))
    return {
        "expected_files": len(expected),
        "exact_files": len(exact),
        "missing_files": len(missing),
        "conflict_files": len(conflicts),
        "unexpected_files": len(unexpected),
        "missing_paths": sorted(missing),
        "conflicts": conflicts,
        "unexpected_paths": unexpected,
    }


def remote_preflight(
    *,
    api: Any,
    validated: dict[str, Any],
    dataset_repo: str,
    token: str,
    timeout: float,
    revision: str = "main",
) -> dict[str, Any]:
    try:
        info = api.repo_info(
            repo_id=dataset_repo, repo_type="dataset", revision=revision
        )
    except Exception as exc:
        raise OriginPublicationError(
            f"dataset repo is unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    resolved_revision = str(getattr(info, "sha", "") or revision)
    remote = list_remote_files(
        api,
        dataset_repo=dataset_repo,
        path_in_repo=validated["release_prefix"],
        revision=resolved_revision,
    )
    immutable_expected = list(validated["immutable_files"])
    manifest_expected = dict(validated["release_manifest"])
    release_expected = [*immutable_expected, manifest_expected]
    classification = classify_remote_inventory(
        expected=release_expected,
        remote=remote,
        dataset_repo=dataset_repo,
        revision=resolved_revision,
        token=token,
        timeout=timeout,
    )
    pointer_remote = list_remote_files(
        api,
        dataset_repo=dataset_repo,
        path_in_repo=validated["latest_pointer"]["remote_path"],
        revision=resolved_revision,
    )
    pointer_classification = classify_remote_inventory(
        expected=[validated["latest_pointer"]],
        remote=pointer_remote,
        dataset_repo=dataset_repo,
        revision=resolved_revision,
        token=token,
        timeout=timeout,
    )
    return {
        "repo": dataset_repo,
        "revision": resolved_revision,
        "release": classification,
        "latest_pointer": pointer_classification,
        "append_only_safe": (
            classification["conflict_files"] == 0
            and classification["unexpected_files"] == 0
        ),
        "release_exact": (
            classification["exact_files"] == len(release_expected)
            and classification["missing_files"] == 0
            and classification["conflict_files"] == 0
            and classification["unexpected_files"] == 0
        ),
        "pointer_exact": (
            pointer_classification["exact_files"] == 1
            and pointer_classification["missing_files"] == 0
            and pointer_classification["conflict_files"] == 0
        ),
    }


def upload_batches(
    *,
    api: Any,
    dataset_repo: str,
    files: list[dict[str, Any]],
    max_files: int,
    max_bytes: int,
    release_id: str,
    commit_log: list[str],
) -> None:
    from huggingface_hub import CommitOperationAdd  # type: ignore

    grouped = list(batches(files, max_files=max_files, max_bytes=max_bytes))
    for batch_index, batch in enumerate(grouped, start=1):
        operations = [
            CommitOperationAdd(
                path_in_repo=str(item["remote_path"]),
                path_or_fileobj=str(item["source"]),
            )
            for item in batch
        ]
        result = api.create_commit(
            repo_id=dataset_repo,
            repo_type="dataset",
            operations=operations,
            commit_message=(
                f"Add real document origin {release_id[:12]} "
                f"({batch_index}/{len(grouped)})"
            ),
        )
        commit_log.append(str(getattr(result, "oid", "") or ""))


def write_report(path: Path, report: dict[str, Any]) -> None:
    atomic_write(
        path,
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8")
        + b"\n",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.publish and not args.authorize_remote_write:
        raise OriginPublicationError(
            "--publish requires --authorize-remote-write; remote mutation is fenced"
        )
    if args.authorize_remote_write and not args.publish:
        raise OriginPublicationError(
            "--authorize-remote-write is only valid together with --publish"
        )
    plan_path = repo_path(args.upload_plan, "upload plan")
    report_path = repo_path(args.report_out, "report output")
    validated = validate_local_upload_plan(plan_path)
    dotenv_values = load_dotenv(Path(args.env_file))
    raw_repo = resolve_setting("HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values)
    username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
    token = resolve_setting("HF_TOKEN", args.hf_token, dotenv_values)
    need_remote = bool(args.remote_preflight or args.publish)
    dataset_repo = resolve_dataset_repo(raw_repo, username) if need_remote else ""
    if args.publish and token.strip().lower() in PLACEHOLDER_VALUES:
        raise OriginPublicationError("HF_TOKEN is required for authorized publication")

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "generated_at": utc_now(),
        "mode": "publish" if args.publish else "dry_run",
        "status": "ready_for_authorized_publication",
        "authorized": bool(args.publish and args.authorize_remote_write),
        "remote_preflight_performed": False,
        "remote_publication_performed": False,
        "durable_public_origin_proven": False,
        "independent_remote_restore_proven": False,
        "release_id": validated["release_id"],
        "release_prefix": validated["release_prefix"],
        "dataset_repo": dataset_repo,
        "summary": {
            "immutable_files": validated["total_files"],
            "immutable_bytes": validated["total_bytes"],
            "release_manifest_bytes": validated["release_manifest"]["bytes"],
            "latest_pointer_bytes": validated["latest_pointer"]["bytes"],
        },
        "checks": {
            "all_local_files_rehashed": True,
            "local_release_inventory_exact": True,
            "append_only_no_delete_contract": True,
            "immutable_manifest_order_enforced": True,
            "latest_pointer_order_enforced": True,
            "official_public_domain_personal_information_retained": True,
            "no_synthetic_or_mock_records": True,
            "no_remote_mutation_without_explicit_authorization": True,
        },
        "remote": None,
        "commits": [],
    }
    if not need_remote:
        report["next_action"] = (
            "Run read-only remote preflight. After explicit release authority, run "
            "publication with both --publish and --authorize-remote-write."
        )
        write_report(report_path, report)
        return report

    from huggingface_hub import HfApi  # type: ignore

    api = HfApi(token=token or None)
    before = remote_preflight(
        api=api,
        validated=validated,
        dataset_repo=dataset_repo,
        token=token,
        timeout=args.timeout,
    )
    report["remote_preflight_performed"] = True
    report["remote"] = {"before": before}
    report["checks"]["remote_has_no_immutable_conflicts"] = bool(
        before["append_only_safe"]
    )
    if not before["append_only_safe"]:
        report["status"] = "blocked_remote_conflict"
        report["next_action"] = (
            "Stop. Investigate unexpected or checksum-conflicting immutable paths; "
            "never overwrite or delete them automatically."
        )
        write_report(report_path, report)
        return report
    if (
        before["release"]["exact_files"] > 0
        and before["release"]["missing_files"] > 0
        and validated["release_manifest"]["remote_path"]
        not in before["release"]["missing_paths"]
    ):
        raise OriginPublicationError(
            "remote release manifest exists before all immutable files; invariant broken"
        )
    if not args.publish:
        if before["release_exact"] and before["pointer_exact"]:
            report["status"] = "already_published_exact"
            report["durable_public_origin_proven"] = True
        report["next_action"] = (
            "Obtain explicit release authority, then publish missing immutable files; "
            "the release manifest and latest pointer remain ordered last."
        )
        write_report(report_path, report)
        return report

    try:
        missing_paths = set(before["release"]["missing_paths"])
        missing_immutable = [
            item
            for item in validated["immutable_files"]
            if item["remote_path"] in missing_paths
        ]
        upload_batches(
            api=api,
            dataset_repo=dataset_repo,
            files=missing_immutable,
            max_files=args.batch_files,
            max_bytes=args.batch_bytes,
            release_id=validated["release_id"],
            commit_log=report["commits"],
        )
        if validated["release_manifest"]["remote_path"] in missing_paths:
            manifest_result = api.upload_file(
                repo_id=dataset_repo,
                repo_type="dataset",
                path_or_fileobj=str(validated["release_manifest"]["source"]),
                path_in_repo=validated["release_manifest"]["remote_path"],
                commit_message=(
                    f"Seal real document origin {validated['release_id'][:12]} manifest"
                ),
            )
            report["commits"].append(str(getattr(manifest_result, "oid", "") or ""))

        sealed = remote_preflight(
            api=api,
            validated=validated,
            dataset_repo=dataset_repo,
            token=token,
            timeout=args.timeout,
        )
        report["remote"]["sealed_release"] = sealed
        if not sealed["release_exact"]:
            raise OriginPublicationError(
                "remote immutable release parity failed; latest pointer was not changed"
            )
        if not sealed["pointer_exact"]:
            pointer_result = api.upload_file(
                repo_id=dataset_repo,
                repo_type="dataset",
                path_or_fileobj=str(validated["latest_pointer"]["source"]),
                path_in_repo=validated["latest_pointer"]["remote_path"],
                commit_message=(
                    f"Activate real document origin {validated['release_id'][:12]}"
                ),
            )
            report["commits"].append(str(getattr(pointer_result, "oid", "") or ""))

        final = remote_preflight(
            api=api,
            validated=validated,
            dataset_repo=dataset_repo,
            token=token,
            timeout=args.timeout,
        )
        report["remote"]["final"] = final
        if not final["release_exact"] or not final["pointer_exact"]:
            raise OriginPublicationError("final remote parity failed")
    except Exception as exc:
        report["status"] = "publication_interrupted"
        report["remote_publication_performed"] = bool(report["commits"])
        report["durable_public_origin_proven"] = False
        report["interruption"] = {
            "error_type": type(exc).__name__,
            "recorded_commit_ids": len(report["commits"]),
            "resume_contract": (
                "rerun read-only preflight; accept only exact immutable checksum "
                "parity and upload only missing files"
            ),
        }
        report["next_action"] = (
            "Do not delete or overwrite immutable paths. Rerun read-only preflight, "
            "verify completed remote checksums, then resume only missing files."
        )
        write_report(report_path, report)
        raise OriginPublicationError(
            "authorized publication interrupted; resumable progress report persisted"
        ) from exc
    report["status"] = "published_exact"
    report["remote_publication_performed"] = True
    report["durable_public_origin_proven"] = True
    report["checks"]["remote_release_parity_exact"] = True
    report["checks"]["latest_pointer_parity_exact"] = True
    report["next_action"] = (
        "Run an isolated remote restore and validate all object/member checksums "
        "before claiming independent disaster recovery."
    )
    write_report(report_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run(args)
    except (OSError, OriginPublicationError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.enforce and report["status"] not in {
        "ready_for_authorized_publication",
        "already_published_exact",
        "published_exact",
    }:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
