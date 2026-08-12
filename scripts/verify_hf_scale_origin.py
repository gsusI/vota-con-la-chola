"""Fail closed unless the public HF scale origin matches local real readiness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
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
    build_scale_origin_bundle,
    immutable_snapshot_path,
    load_json_object,
    resolve_dataset_repo,
    safe_artifact_relative_path,
    safe_repo_path,
    sha256_file,
    write_json,
)


def fetch_json_document(url: str, timeout: float) -> tuple[dict[str, Any], str, bytes]:
    request = Request(
        url,
        headers={
            "User-Agent": "vota-con-la-chola/verify-hf-scale-origin",
            "Accept": "application/json,*/*",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ScaleOriginError(f"invalid JSON at {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScaleOriginError(f"JSON root is not an object at {url}")
    return payload, hashlib.sha256(body).hexdigest(), body


def fetch_json_with_sha256(url: str, timeout: float) -> tuple[dict[str, Any], str]:
    payload, digest, _body = fetch_json_document(url, timeout)
    return payload, digest


def _corpus_contract(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "rows": int(item.get("rows") or 0),
        "files": int(item.get("files") or 0),
        "bytes": int(item.get("bytes") or 0),
    }


def evaluate_origin_parity(
    *,
    local_readiness: dict[str, Any],
    local_readiness_sha256: str,
    local_artifact_contract_sha256: str,
    remote_latest: dict[str, Any],
    remote_manifest: dict[str, Any],
    remote_manifest_sha256: str,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    local_corpora = local_readiness.get("corpora")
    remote_corpora = remote_manifest.get("corpora")
    if not isinstance(local_corpora, list):
        raise ScaleOriginError("local scale readiness has no corpora array")
    if not isinstance(remote_corpora, list):
        raise ScaleOriginError("remote scale manifest has no corpora array")

    expected_snapshot_date = str(remote_latest.get("snapshot_date") or "")
    checks["latest_schema_version"] = remote_latest.get("schema_version")
    checks["manifest_schema_version"] = remote_manifest.get("schema_version")
    if remote_latest.get("schema_version") != SCHEMA_VERSION:
        errors.append("remote scale latest pointer has unsupported schema version")
    if remote_manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("remote scale manifest has unsupported schema version")
    remote_contract = remote_manifest.get("artifact_contract")
    declared_contract_sha256 = (
        str(remote_contract.get("sha256") or "")
        if isinstance(remote_contract, dict)
        else ""
    )
    declared_contract_schema = (
        str(remote_contract.get("schema_version") or "")
        if isinstance(remote_contract, dict)
        else ""
    )
    recomputed_contract_sha256 = artifact_contract_sha256(remote_manifest)
    latest_contract_sha256 = str(remote_latest.get("artifact_contract_sha256") or "")
    checks["artifact_contract"] = {
        "schema_version": declared_contract_schema,
        "declared_sha256": declared_contract_sha256,
        "recomputed_remote_sha256": recomputed_contract_sha256,
        "latest_sha256": latest_contract_sha256,
        "local_sha256": local_artifact_contract_sha256,
    }
    if declared_contract_schema != ARTIFACT_CONTRACT_SCHEMA_VERSION:
        errors.append("remote scale artifact contract has unsupported schema version")
    if declared_contract_sha256 != recomputed_contract_sha256:
        errors.append("remote scale artifact contract checksum is invalid")
    if latest_contract_sha256 != declared_contract_sha256:
        errors.append("remote latest pointer artifact contract checksum differs")
    if declared_contract_sha256 != local_artifact_contract_sha256:
        errors.append("remote scale artifact contract differs from local artifacts")
    checks["snapshot_date"] = expected_snapshot_date
    checks["latest_manifest_sha256"] = str(remote_latest.get("manifest_sha256") or "")
    checks["downloaded_manifest_sha256"] = remote_manifest_sha256
    declared_snapshot_path = str(remote_latest.get("snapshot_path") or "")
    expected_snapshot_path = immutable_snapshot_path(
        expected_snapshot_date, remote_manifest_sha256
    ).as_posix()
    checks["declared_snapshot_path"] = declared_snapshot_path
    checks["expected_immutable_snapshot_path"] = expected_snapshot_path
    checks["immutable_snapshot_path"] = declared_snapshot_path == expected_snapshot_path
    if declared_snapshot_path != expected_snapshot_path:
        errors.append("remote scale snapshot path is not content-addressed")
    if (
        str(remote_latest.get("release_id") or "")
        != remote_manifest_sha256[:RELEASE_ID_LENGTH]
    ):
        errors.append("remote scale release_id does not match manifest checksum")
    if not expected_snapshot_date:
        errors.append("remote scale/latest.json has no snapshot_date")
    if remote_manifest.get("snapshot_date") != expected_snapshot_date:
        errors.append("remote latest and manifest snapshot dates differ")
    if checks["latest_manifest_sha256"] != remote_manifest_sha256:
        errors.append("remote scale manifest checksum differs from scale/latest.json")
    if remote_manifest.get("status") != "validated_real_origin_bundle":
        errors.append(
            "remote scale manifest status is not validated_real_origin_bundle"
        )

    policy = remote_manifest.get("policy")
    required_policy = {
        "official_real_records_only",
        "synthetic_or_mock_records_forbidden",
        "official_public_domain_personal_information_retained",
        "secrets_workstation_traces_and_non_public_data_forbidden",
    }
    policy_ok = isinstance(policy, dict) and all(
        policy.get(key) is True for key in required_policy
    )
    checks["required_policy_passed"] = policy_ok
    if not policy_ok:
        errors.append(
            "remote scale manifest is missing mandatory real/public-data policy"
        )

    source_evidence = remote_manifest.get("source_evidence")
    remote_readiness_sha256 = ""
    remote_registry_sha256 = ""
    if isinstance(source_evidence, dict):
        readiness_entry = source_evidence.get("readiness")
        registry_entry = source_evidence.get("registry")
        if isinstance(readiness_entry, dict):
            remote_readiness_sha256 = str(readiness_entry.get("sha256") or "")
        if isinstance(registry_entry, dict):
            remote_registry_sha256 = str(registry_entry.get("sha256") or "")
    local_registry = local_readiness.get("registry")
    local_registry_sha256 = (
        str(local_registry.get("sha256") or "")
        if isinstance(local_registry, dict)
        else ""
    )
    checks["local_readiness_sha256"] = local_readiness_sha256
    checks["remote_readiness_sha256"] = remote_readiness_sha256
    checks["local_registry_sha256"] = local_registry_sha256
    checks["remote_registry_sha256"] = remote_registry_sha256
    metadata_warnings: list[str] = []
    if remote_readiness_sha256 != local_readiness_sha256:
        metadata_warnings.append(
            "remote scale origin does not contain the current readiness report"
        )
    if not local_registry_sha256 or remote_registry_sha256 != local_registry_sha256:
        metadata_warnings.append(
            "remote scale origin does not contain the current corpus registry"
        )
    local_contracts = sorted(
        (_corpus_contract(item) for item in local_corpora if isinstance(item, dict)),
        key=lambda item: item["id"],
    )
    remote_contracts = sorted(
        (_corpus_contract(item) for item in remote_corpora if isinstance(item, dict)),
        key=lambda item: item["id"],
    )
    checks["local_corpora"] = local_contracts
    checks["remote_corpora"] = remote_contracts
    checks["corpus_contracts_match"] = local_contracts == remote_contracts
    if local_contracts != remote_contracts:
        errors.append(
            "remote corpus row/file/byte contract differs from local readiness"
        )
    local_promotion_states = {
        str(item.get("id") or ""): item.get("promotion_gate_passed") is True
        for item in local_corpora
        if isinstance(item, dict)
    }
    remote_promotion_states = {
        str(item.get("id") or ""): item.get("promotion_gate_passed") is True
        for item in remote_corpora
        if isinstance(item, dict)
    }
    checks["promotion_states_match"] = local_promotion_states == remote_promotion_states
    if not checks["promotion_states_match"]:
        metadata_warnings.append(
            "remote scale origin contains older promotion-state metadata"
        )
    checks["metadata_freshness"] = not metadata_warnings
    checks["metadata_warnings"] = metadata_warnings

    files = remote_manifest.get("files")
    declared_files = len(files) if isinstance(files, list) else -1
    declared_data_files = (
        sum(
            1 for item in files if isinstance(item, dict) and item.get("kind") == "data"
        )
        if isinstance(files, list)
        else -1
    )
    expected_data_files = sum(item["files"] for item in local_contracts)
    checks["declared_bundle_files"] = declared_files
    checks["declared_data_files"] = declared_data_files
    checks["expected_data_files"] = expected_data_files
    if declared_data_files != expected_data_files:
        errors.append("remote manifest data-file inventory is incomplete")

    return checks, errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-repo", default="")
    parser.add_argument("--hf-username", default="")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--readiness", default="etl/data/published/scale-readiness-latest.json"
    )
    parser.add_argument("--registry", default="docs/etl/real-corpus-registry.json")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report: dict[str, Any] = {
        "passed": False,
        "status": "blocked_remote_scale_origin_unverified",
        "errors": [],
    }
    exit_code = 1
    try:
        if args.timeout <= 0:
            raise ScaleOriginError("--timeout must be positive")
        readiness_path = safe_repo_path(REPO_ROOT, args.readiness, "readiness")
        registry_path = safe_repo_path(REPO_ROOT, args.registry, "registry")
        local_readiness = load_json_object(readiness_path)
        local_readiness_sha256 = sha256_file(readiness_path)
        dotenv_values = load_dotenv(Path(args.env_file))
        username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
        raw_repo = resolve_setting(
            "HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values
        )
        dataset_repo = resolve_dataset_repo(raw_repo, username)
        base_url = f"https://huggingface.co/datasets/{dataset_repo}/resolve/main"
        latest_url = f"{base_url}/scale/latest.json"
        remote_latest, _latest_sha256 = fetch_json_with_sha256(latest_url, args.timeout)
        snapshot_date = ensure_iso_date(str(remote_latest.get("snapshot_date") or ""))
        snapshot_path = str(remote_latest.get("snapshot_path") or "").strip()
        safe_snapshot_path = safe_artifact_relative_path(snapshot_path).as_posix()
        if not safe_snapshot_path.startswith("scale/snapshots/"):
            raise ScaleOriginError(
                f"unsafe remote scale snapshot path: {snapshot_path!r}"
            )
        manifest_url = f"{base_url}/{safe_snapshot_path}/manifest.json"
        remote_manifest, remote_manifest_sha256 = fetch_json_with_sha256(
            manifest_url, args.timeout
        )
        with tempfile.TemporaryDirectory(prefix="vcl-scale-verify-") as temp_dir:
            local_bundle_report = build_scale_origin_bundle(
                repo_root=REPO_ROOT,
                registry_path=registry_path,
                readiness_path=readiness_path,
                build_root=Path(temp_dir),
                snapshot_date=snapshot_date,
            )
            local_manifest = load_json_object(
                Path(temp_dir)
                / str(local_bundle_report["snapshot_path"])
                / "manifest.json"
            )
            local_contract_sha256 = artifact_contract_sha256(local_manifest)
        checks, errors = evaluate_origin_parity(
            local_readiness=local_readiness,
            local_readiness_sha256=local_readiness_sha256,
            local_artifact_contract_sha256=local_contract_sha256,
            remote_latest=remote_latest,
            remote_manifest=remote_manifest,
            remote_manifest_sha256=remote_manifest_sha256,
        )
        report.update(
            {
                "dataset_repo": dataset_repo,
                "snapshot_date": remote_latest.get("snapshot_date"),
                "urls": {"latest": latest_url, "manifest": manifest_url},
                "checks": checks,
                "errors": errors,
                "warnings": checks.get("metadata_warnings", []),
                "passed": not errors,
                "status": (
                    "verified_current_scale_origin"
                    if not errors and checks.get("metadata_freshness") is True
                    else "verified_current_scale_origin_metadata_drift"
                    if not errors
                    else "blocked_remote_scale_origin_mismatch"
                ),
            }
        )
        exit_code = 0 if not errors else 1
    except HTTPError as exc:
        report["errors"] = [f"HTTP {exc.code}: {exc.reason}"]
        report["http_status"] = exc.code
        report["status"] = (
            "blocked_remote_scale_origin_missing"
            if exc.code == 404
            else "blocked_remote_scale_origin_http_error"
        )
    except (OSError, ScaleOriginError, URLError, ValueError) as exc:
        report["errors"] = [f"{type(exc).__name__}: {exc}"]
        exit_code = 2

    if args.json_out.strip():
        try:
            report_path = safe_repo_path(REPO_ROOT, args.json_out, "report")
            write_json(report_path, report)
        except (OSError, ScaleOriginError) as exc:
            print(f"ERROR: cannot write report: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
