"""Build and optionally publish the registered real-scale analytical artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.hf_snapshot import (
    ensure_iso_date,
    load_dotenv,
    resolve_setting,
)

SCHEMA_VERSION = "real-scale-origin-bundle-v2"
ARTIFACT_CONTRACT_SCHEMA_VERSION = "real-scale-artifact-contract-v1"
RELEASE_ID_LENGTH = 64
UPLOAD_BATCH_FILES = 250
CORPUS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
DEFAULT_DATASET_NAME = "vota-con-la-chola-data"
PLACEHOLDER_VALUES = {"", "your_hf_token_here", "your_hf_username_here"}


class ScaleOriginError(RuntimeError):
    """Raised when a real-scale artifact cannot be packaged safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScaleOriginError(f"cannot read JSON object {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScaleOriginError(f"JSON root must be an object: {path.name}")
    return payload


def safe_repo_path(repo_root: Path, raw_path: str, label: str) -> Path:
    relative = Path(str(raw_path).strip())
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise ScaleOriginError(f"unsafe {label} path: {raw_path!r}")
    resolved_root = repo_root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ScaleOriginError(f"{label} path escapes repository: {raw_path!r}")
    return resolved


def safe_artifact_relative_path(raw_path: str) -> Path:
    relative = Path(str(raw_path).strip())
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise ScaleOriginError(f"unsafe artifact path: {raw_path!r}")
    return relative


def resolve_dataset_repo(dataset_repo: str, hf_username: str) -> str:
    repo = dataset_repo.strip()
    username = hf_username.strip()
    if not repo:
        if username in PLACEHOLDER_VALUES:
            raise ScaleOriginError(
                "cannot resolve dataset repo: set HF_DATASET_REPO_ID or HF_USERNAME"
            )
        return f"{username}/{DEFAULT_DATASET_NAME}"
    if "/" in repo:
        return repo
    if username in PLACEHOLDER_VALUES:
        raise ScaleOriginError(
            "HF_DATASET_REPO_ID has no owner and HF_USERNAME is not configured"
        )
    return f"{username}/{repo}"


def immutable_snapshot_path(snapshot_date: str, manifest_sha256: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise ScaleOriginError("manifest SHA-256 is invalid")
    return (
        Path("scale")
        / "snapshots"
        / snapshot_date
        / manifest_sha256[:RELEASE_ID_LENGTH]
    )


def declared_artifact_files(
    *, corpus_kind: str, manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    declared: list[dict[str, Any]] = []
    if corpus_kind == "gzip_vote_shards":
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            raise ScaleOriginError("gzip vote manifest has no entries array")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ScaleOriginError("gzip vote manifest contains a non-object entry")
            declared.append(
                {
                    "path": entry.get("shard"),
                    "bytes": entry.get("shard_bytes"),
                    "sha256": entry.get("shard_sha256"),
                }
            )
    elif corpus_kind == "parquet_manifest":
        partitions = manifest.get("partitions")
        if not isinstance(partitions, list):
            raise ScaleOriginError("Parquet manifest has no partitions array")
        for partition in partitions:
            if not isinstance(partition, dict) or not isinstance(
                partition.get("files"), list
            ):
                raise ScaleOriginError("Parquet manifest contains an invalid partition")
            for entry in partition["files"]:
                if not isinstance(entry, dict):
                    raise ScaleOriginError(
                        "Parquet manifest contains a non-object file"
                    )
                declared.append(
                    {
                        "path": entry.get("path"),
                        "bytes": entry.get("bytes"),
                        "sha256": entry.get("sha256"),
                    }
                )
    else:
        raise ScaleOriginError(f"unsupported corpus kind: {corpus_kind!r}")
    return declared


def stage_file(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def artifact_contract_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the stable data/provenance contract, excluding release-state metadata."""
    corpora = manifest.get("corpora")
    files = manifest.get("files")
    if not isinstance(corpora, list) or not isinstance(files, list):
        raise ScaleOriginError("scale manifest has no corpora/files contract")

    data_by_corpus: dict[str, list[dict[str, Any]]] = {}
    for entry in files:
        if not isinstance(entry, dict) or entry.get("kind") != "data":
            continue
        corpus_id = str(entry.get("corpus_id") or "")
        path = str(entry.get("path") or "")
        sha256 = str(entry.get("sha256") or "")
        byte_count = int(entry.get("bytes") or -1)
        if (
            not CORPUS_ID_RE.fullmatch(corpus_id)
            or not path
            or byte_count < 0
            or not re.fullmatch(r"[0-9a-f]{64}", sha256)
        ):
            raise ScaleOriginError("scale manifest contains an invalid data file")
        data_by_corpus.setdefault(corpus_id, []).append(
            {"path": path, "bytes": byte_count, "sha256": sha256}
        )

    corpus_contracts: list[dict[str, Any]] = []
    for corpus in corpora:
        if not isinstance(corpus, dict):
            raise ScaleOriginError("scale manifest contains a non-object corpus")
        corpus_id = str(corpus.get("id") or "")
        if not CORPUS_ID_RE.fullmatch(corpus_id):
            raise ScaleOriginError(
                f"invalid corpus id in scale manifest: {corpus_id!r}"
            )
        manifest_entry = corpus.get("manifest")
        validation_entry = corpus.get("validation")
        if not isinstance(manifest_entry, dict) or not isinstance(
            validation_entry, dict
        ):
            raise ScaleOriginError(
                f"scale manifest corpus lacks validation evidence: {corpus_id}"
            )
        extra_evidence = corpus.get("extra_evidence")
        if not isinstance(extra_evidence, dict):
            raise ScaleOriginError(
                f"scale manifest corpus has invalid extra evidence: {corpus_id}"
            )
        data_files = sorted(data_by_corpus.pop(corpus_id, []), key=lambda x: x["path"])
        corpus_contracts.append(
            {
                "id": corpus_id,
                "kind": str(corpus.get("kind") or ""),
                "rows": int(corpus.get("rows") or 0),
                "files": int(corpus.get("files") or 0),
                "bytes": int(corpus.get("bytes") or 0),
                "source_ids": sorted(
                    str(item) for item in corpus.get("source_ids", [])
                ),
                "official_hosts": sorted(
                    str(item) for item in corpus.get("official_hosts", [])
                ),
                "source_url_rows": int(corpus.get("source_url_rows") or 0),
                "source_url_https_rows": int(corpus.get("source_url_https_rows") or 0),
                "manifest_sha256": str(manifest_entry.get("sha256") or ""),
                "validation_sha256": str(validation_entry.get("sha256") or ""),
                "extra_evidence_sha256": {
                    str(key): str(value.get("sha256") or "")
                    for key, value in sorted(extra_evidence.items())
                    if isinstance(value, dict)
                },
                "data_files": data_files,
            }
        )
    if data_by_corpus:
        raise ScaleOriginError(
            "scale manifest has data for undeclared corpora: "
            + ", ".join(sorted(data_by_corpus))
        )
    corpus_contracts.sort(key=lambda item: item["id"])
    return {
        "schema_version": ARTIFACT_CONTRACT_SCHEMA_VERSION,
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_forbidden": True,
            "official_public_domain_personal_information_retained": True,
        },
        "corpora": corpus_contracts,
    }


def artifact_contract_sha256(manifest: dict[str, Any]) -> str:
    payload = artifact_contract_payload(manifest)
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def publish_scale_origin_bundle(
    *,
    api: Any,
    dataset_repo: str,
    build_root: Path,
    snapshot_date: str,
    operation_factory: Any | None = None,
) -> None:
    """Upload immutable scale files first, then move the public latest pointer."""
    if operation_factory is None:
        from huggingface_hub import CommitOperationAdd  # type: ignore

        operation_factory = CommitOperationAdd

    latest_path = build_root / "scale" / "latest.json"
    bundle_files = sorted(
        path for path in build_root.rglob("*") if path.is_file() and path != latest_path
    )
    batch_total = (len(bundle_files) + UPLOAD_BATCH_FILES - 1) // UPLOAD_BATCH_FILES
    for batch_index, offset in enumerate(
        range(0, len(bundle_files), UPLOAD_BATCH_FILES),
        start=1,
    ):
        batch = bundle_files[offset : offset + UPLOAD_BATCH_FILES]
        operations = [
            operation_factory(
                path_in_repo=path.relative_to(build_root).as_posix(),
                path_or_fileobj=str(path),
            )
            for path in batch
        ]
        api.create_commit(
            repo_id=dataset_repo,
            repo_type="dataset",
            operations=operations,
            commit_message=(
                f"Publish real scale origin snapshot {snapshot_date} "
                f"({batch_index}/{batch_total})"
            ),
        )
    api.upload_file(
        repo_id=dataset_repo,
        repo_type="dataset",
        path_or_fileobj=str(build_root / "scale" / "latest.json"),
        path_in_repo="scale/latest.json",
        commit_message=f"Point to real scale origin snapshot {snapshot_date}",
    )


def build_scale_origin_bundle(
    *,
    repo_root: Path,
    registry_path: Path,
    readiness_path: Path,
    build_root: Path,
    snapshot_date: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    registry_path = registry_path.resolve()
    readiness_path = readiness_path.resolve()
    build_root = build_root.resolve()
    registry = load_json_object(registry_path)
    readiness = load_json_object(readiness_path)

    registry_sha256 = sha256_file(registry_path)
    readiness_sha256 = sha256_file(readiness_path)
    release_generated_at = str(readiness.get("generated_at") or "").strip()
    if not release_generated_at:
        raise ScaleOriginError("scale readiness has no generated_at release timestamp")
    readiness_registry = readiness.get("registry")
    if (
        not isinstance(readiness_registry, dict)
        or readiness_registry.get("sha256") != registry_sha256
    ):
        raise ScaleOriginError(
            "scale readiness does not reference the current registry checksum"
        )
    if readiness.get("status") not in {
        "real_foundation_ready_scale_incomplete",
        "promoted_real_scale_ready",
    }:
        raise ScaleOriginError(
            f"scale readiness is not publishable: {readiness.get('status')!r}"
        )

    registry_corpora = registry.get("corpora")
    readiness_corpora = readiness.get("corpora")
    if not isinstance(registry_corpora, list) or not registry_corpora:
        raise ScaleOriginError("real corpus registry has no corpora")
    if not isinstance(readiness_corpora, list):
        raise ScaleOriginError("scale readiness has no corpora array")
    readiness_by_id = {
        str(item.get("id")): item
        for item in readiness_corpora
        if isinstance(item, dict) and item.get("id")
    }
    registry_ids = [
        str(item.get("id")) for item in registry_corpora if isinstance(item, dict)
    ]
    if set(registry_ids) != set(readiness_by_id):
        raise ScaleOriginError("registry and readiness corpus IDs do not match")

    staging_parent = build_root / ".scale-release-staging"
    snapshot_root = staging_parent / "snapshot"
    snapshot_root.mkdir(parents=True, exist_ok=False)
    bundle_files: list[dict[str, Any]] = []
    corpus_reports: list[dict[str, Any]] = []
    total_data_bytes = 0
    total_data_files = 0
    hardlinks = 0
    copies = 0

    def record_metadata_file(source: Path, relative: Path) -> dict[str, Any]:
        nonlocal hardlinks, copies
        mode = stage_file(source, snapshot_root / relative)
        hardlinks += int(mode == "hardlink")
        copies += int(mode == "copy")
        entry = {
            "path": relative.as_posix(),
            "bytes": int(source.stat().st_size),
            "sha256": sha256_file(source),
            "kind": "metadata",
        }
        bundle_files.append(entry)
        return entry

    registry_entry = record_metadata_file(
        registry_path, Path("real-corpus-registry.json")
    )
    readiness_entry = record_metadata_file(readiness_path, Path("scale-readiness.json"))

    for corpus in registry_corpora:
        if not isinstance(corpus, dict):
            raise ScaleOriginError("registry contains a non-object corpus")
        corpus_id = str(corpus.get("id") or "")
        if not CORPUS_ID_RE.fullmatch(corpus_id):
            raise ScaleOriginError(f"invalid corpus id: {corpus_id!r}")
        readiness_corpus = readiness_by_id[corpus_id]
        if readiness_corpus.get("real_official_data") is not True:
            raise ScaleOriginError(
                f"corpus is not validated real official data: {corpus_id}"
            )
        manifest_path = safe_repo_path(
            repo_root, str(corpus.get("manifest") or ""), f"{corpus_id} manifest"
        )
        validation_path = safe_repo_path(
            repo_root,
            str(corpus.get("validation") or ""),
            f"{corpus_id} validation",
        )
        root_path = safe_repo_path(
            repo_root, str(corpus.get("root") or ""), f"{corpus_id} root"
        )
        manifest = load_json_object(manifest_path)
        validation = load_json_object(validation_path)
        if validation.get("status") != "ok":
            raise ScaleOriginError(
                f"corpus validation is not ok: {corpus_id} status={validation.get('status')!r}"
            )
        corpus_prefix = Path("corpora") / corpus_id
        manifest_entry = record_metadata_file(
            manifest_path, corpus_prefix / "manifest.json"
        )
        validation_entry = record_metadata_file(
            validation_path, corpus_prefix / "validation.json"
        )
        extra_evidence: dict[str, dict[str, Any]] = {}
        for key, file_name in (
            ("incremental_manifest", "incremental-manifest.json"),
            ("incremental_validation", "incremental-validation.json"),
        ):
            raw_path = str(corpus.get(key) or "").strip()
            if raw_path:
                extra_evidence[key] = record_metadata_file(
                    safe_repo_path(repo_root, raw_path, f"{corpus_id} {key}"),
                    corpus_prefix / file_name,
                )

        seen_paths: set[str] = set()
        corpus_data_files = 0
        corpus_data_bytes = 0
        for declared in declared_artifact_files(
            corpus_kind=str(corpus.get("kind") or ""), manifest=manifest
        ):
            relative = safe_artifact_relative_path(str(declared.get("path") or ""))
            relative_text = relative.as_posix()
            if relative_text in seen_paths:
                raise ScaleOriginError(
                    f"duplicate artifact path in {corpus_id}: {relative_text}"
                )
            seen_paths.add(relative_text)
            expected_bytes = int(declared.get("bytes") or -1)
            expected_sha256 = str(declared.get("sha256") or "")
            if expected_bytes < 0 or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
                raise ScaleOriginError(
                    f"invalid file declaration in {corpus_id}: {relative_text}"
                )
            source = (root_path / relative).resolve()
            if root_path != source and root_path not in source.parents:
                raise ScaleOriginError(
                    f"artifact escapes corpus root in {corpus_id}: {relative_text}"
                )
            if not source.is_file():
                raise ScaleOriginError(
                    f"declared artifact is missing in {corpus_id}: {relative_text}"
                )
            actual_bytes = int(source.stat().st_size)
            if actual_bytes != expected_bytes:
                raise ScaleOriginError(
                    f"artifact byte mismatch in {corpus_id}: {relative_text}"
                )
            actual_sha256 = sha256_file(source)
            if actual_sha256 != expected_sha256:
                raise ScaleOriginError(
                    f"artifact checksum mismatch in {corpus_id}: {relative_text}"
                )
            destination_relative = corpus_prefix / "data" / relative
            mode = stage_file(source, snapshot_root / destination_relative)
            hardlinks += int(mode == "hardlink")
            copies += int(mode == "copy")
            bundle_files.append(
                {
                    "path": destination_relative.as_posix(),
                    "bytes": actual_bytes,
                    "sha256": actual_sha256,
                    "kind": "data",
                    "corpus_id": corpus_id,
                }
            )
            corpus_data_files += 1
            corpus_data_bytes += actual_bytes

        expected_files = int(readiness_corpus.get("files") or 0)
        expected_bytes = int(readiness_corpus.get("bytes") or 0)
        if corpus_data_files != expected_files or corpus_data_bytes != expected_bytes:
            raise ScaleOriginError(
                f"readiness artifact totals mismatch for {corpus_id}: "
                f"files={corpus_data_files}/{expected_files} bytes={corpus_data_bytes}/{expected_bytes}"
            )
        total_data_files += corpus_data_files
        total_data_bytes += corpus_data_bytes
        corpus_reports.append(
            {
                "id": corpus_id,
                "kind": corpus.get("kind"),
                "rows": int(readiness_corpus.get("rows") or 0),
                "files": corpus_data_files,
                "bytes": corpus_data_bytes,
                "scale_gate_passed": readiness_corpus.get("scale_gate_passed") is True,
                "promotion_gate_passed": readiness_corpus.get("promotion_gate_passed")
                is True,
                "source_ids": sorted(
                    str(item) for item in readiness_corpus.get("source_ids", [])
                ),
                "official_hosts": sorted(
                    str(item) for item in corpus.get("official_hosts", [])
                ),
                "source_url_rows": int(readiness_corpus.get("source_url_rows") or 0),
                "source_url_https_rows": int(
                    readiness_corpus.get("source_url_https_rows") or 0
                ),
                "manifest": manifest_entry,
                "validation": validation_entry,
                "extra_evidence": extra_evidence,
                "data_prefix": (corpus_prefix / "data").as_posix(),
            }
        )

    manifest_payload = {
        "schema_version": SCHEMA_VERSION,
        "project": "vota-con-la-chola",
        "snapshot_date": snapshot_date,
        "generated_at": release_generated_at,
        "status": "validated_real_origin_bundle",
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_forbidden": True,
            "official_public_domain_personal_information_retained": True,
            "secrets_workstation_traces_and_non_public_data_forbidden": True,
        },
        "source_evidence": {
            "registry": registry_entry,
            "readiness": readiness_entry,
        },
        "summary": {
            "corpora": len(corpus_reports),
            "rows": sum(item["rows"] for item in corpus_reports),
            "data_files": total_data_files,
            "data_bytes": total_data_bytes,
            "million_scale_lanes": sum(
                1 for item in corpus_reports if item["rows"] >= 1_000_000
            ),
            "promoted_lanes": sum(
                1 for item in corpus_reports if item["promotion_gate_passed"]
            ),
        },
        "corpora": corpus_reports,
        "files": sorted(bundle_files, key=lambda item: item["path"]),
    }
    contract_sha256 = artifact_contract_sha256(manifest_payload)
    manifest_payload["artifact_contract"] = {
        "schema_version": ARTIFACT_CONTRACT_SCHEMA_VERSION,
        "sha256": contract_sha256,
    }
    manifest_path = snapshot_root / "manifest.json"
    write_json(manifest_path, manifest_payload)
    manifest_sha256 = sha256_file(manifest_path)

    checksum_entries = [
        (str(entry["sha256"]), str(entry["path"])) for entry in bundle_files
    ]
    checksum_entries.append((manifest_sha256, "manifest.json"))
    checksums_path = snapshot_root / "checksums.sha256"
    checksums_path.write_text(
        "".join(f"{digest}  {path}\n" for digest, path in sorted(checksum_entries)),
        encoding="utf-8",
    )
    release_id = manifest_sha256[:RELEASE_ID_LENGTH]
    snapshot_rel = immutable_snapshot_path(snapshot_date, manifest_sha256)
    final_snapshot_root = build_root / snapshot_rel
    final_snapshot_root.parent.mkdir(parents=True, exist_ok=True)
    if final_snapshot_root.exists():
        raise ScaleOriginError(
            f"immutable release path already exists: {snapshot_rel.as_posix()}"
        )
    os.replace(snapshot_root, final_snapshot_root)
    staging_parent.rmdir()
    latest_payload = {
        "schema_version": SCHEMA_VERSION,
        "project": "vota-con-la-chola",
        "snapshot_date": snapshot_date,
        "release_id": release_id,
        "snapshot_path": snapshot_rel.as_posix(),
        "manifest_sha256": manifest_sha256,
        "artifact_contract_sha256": contract_sha256,
        "corpora": len(corpus_reports),
        "rows": manifest_payload["summary"]["rows"],
        "data_files": total_data_files,
        "data_bytes": total_data_bytes,
        "million_scale_lanes": manifest_payload["summary"]["million_scale_lanes"],
        "promoted_lanes": manifest_payload["summary"]["promoted_lanes"],
        "updated_at": release_generated_at,
    }
    write_json(build_root / "scale" / "latest.json", latest_payload)
    return {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": snapshot_date,
        "release_id": release_id,
        "snapshot_path": snapshot_rel.as_posix(),
        "manifest_sha256": manifest_sha256,
        "artifact_contract_sha256": contract_sha256,
        "registry_sha256": registry_sha256,
        "readiness_sha256": readiness_sha256,
        "corpora": len(corpus_reports),
        "rows": manifest_payload["summary"]["rows"],
        "data_files": total_data_files,
        "data_bytes": total_data_bytes,
        "million_scale_lanes": manifest_payload["summary"]["million_scale_lanes"],
        "promoted_lanes": manifest_payload["summary"]["promoted_lanes"],
        "hardlinks": hardlinks,
        "copies": copies,
        "public_domain_personal_information_retained": True,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="docs/etl/real-corpus-registry.json")
    parser.add_argument(
        "--readiness", default="etl/data/published/scale-readiness-latest.json"
    )
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--dataset-repo", default="")
    parser.add_argument("--hf-username", default="")
    parser.add_argument("--hf-token", default="")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--report-out", default="")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--private", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        snapshot_date = ensure_iso_date(args.snapshot_date)
        registry_path = safe_repo_path(REPO_ROOT, args.registry, "registry")
        readiness_path = safe_repo_path(REPO_ROOT, args.readiness, "readiness")
    except (ScaleOriginError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.out_dir.strip():
        build_root = Path(args.out_dir).resolve()
        if build_root.exists() and any(build_root.iterdir()):
            print(f"ERROR: out-dir must be empty: {build_root}", file=sys.stderr)
            return 2
        build_root.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="vcl-scale-origin-")
        build_root = Path(temporary.name)

    try:
        report = build_scale_origin_bundle(
            repo_root=REPO_ROOT,
            registry_path=registry_path,
            readiness_path=readiness_path,
            build_root=build_root,
            snapshot_date=snapshot_date,
        )
        dataset_repo = ""
        if args.publish:
            dotenv_values = load_dotenv(Path(args.env_file))
            token = resolve_setting("HF_TOKEN", args.hf_token, dotenv_values)
            username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
            raw_repo = resolve_setting(
                "HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values
            )
            dataset_repo = resolve_dataset_repo(raw_repo, username)
            if token in PLACEHOLDER_VALUES:
                raise ScaleOriginError("HF_TOKEN is not configured")
            from huggingface_hub import HfApi  # type: ignore

            api = HfApi(token=token)
            api.create_repo(
                repo_id=dataset_repo,
                repo_type="dataset",
                private=bool(args.private),
                exist_ok=True,
            )
            publish_scale_origin_bundle(
                api=api,
                dataset_repo=dataset_repo,
                build_root=build_root,
                snapshot_date=snapshot_date,
            )
            report["published"] = True
            report["dataset_repo"] = dataset_repo
        else:
            report["published"] = False
        if args.report_out.strip():
            report_path = safe_repo_path(REPO_ROOT, args.report_out, "report")
            write_json(report_path, report)
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        if not args.publish:
            print("Dry run: no remote state changed")
        return 0
    except (OSError, ScaleOriginError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
