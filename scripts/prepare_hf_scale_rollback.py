"""Prepare a fail-closed, read-only rollback plan for the public HF scale pointer."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.hf_snapshot import load_dotenv, resolve_setting
from scripts.publicar_hf_scale_snapshot import (
    ARTIFACT_CONTRACT_SCHEMA_VERSION,
    RELEASE_ID_LENGTH,
    SCHEMA_VERSION,
    ScaleOriginError,
    artifact_contract_sha256,
    immutable_snapshot_path,
    load_json_object,
    resolve_dataset_repo,
    safe_artifact_relative_path,
    safe_repo_path,
    sha256_file,
    write_json,
)
from scripts.verify_hf_scale_origin import fetch_json_document

PLAN_SCHEMA_VERSION = "hf_scale_rollback_plan_v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_POLICY = {
    "official_real_records_only",
    "synthetic_or_mock_records_forbidden",
    "official_public_domain_personal_information_retained",
    "secrets_workstation_traces_and_non_public_data_forbidden",
}


def _summary(manifest: dict[str, Any]) -> dict[str, int]:
    raw = manifest.get("summary")
    if not isinstance(raw, dict):
        raise ScaleOriginError("scale manifest has no summary object")
    return {
        "corpora": int(raw.get("corpora") or 0),
        "rows": int(raw.get("rows") or 0),
        "data_files": int(raw.get("data_files") or 0),
        "data_bytes": int(raw.get("data_bytes") or 0),
        "million_scale_lanes": int(raw.get("million_scale_lanes") or 0),
        "promoted_lanes": int(raw.get("promoted_lanes") or 0),
    }


def _corpus_contracts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    corpora = manifest.get("corpora")
    if not isinstance(corpora, list):
        raise ScaleOriginError("scale manifest has no corpora array")
    contracts = []
    for item in corpora:
        if not isinstance(item, dict):
            raise ScaleOriginError("scale manifest has a non-object corpus")
        contracts.append(
            {
                "id": str(item.get("id") or ""),
                "rows": int(item.get("rows") or 0),
                "files": int(item.get("files") or 0),
                "bytes": int(item.get("bytes") or 0),
            }
        )
    return sorted(contracts, key=lambda item: item["id"])


def _manifest_checks(
    manifest: dict[str, Any], manifest_sha256: str, snapshot_path: str
) -> dict[str, bool]:
    snapshot_date = str(manifest.get("snapshot_date") or "")
    artifact_contract = manifest.get("artifact_contract")
    declared_contract = (
        str(artifact_contract.get("sha256") or "")
        if isinstance(artifact_contract, dict)
        else ""
    )
    declared_contract_schema = (
        str(artifact_contract.get("schema_version") or "")
        if isinstance(artifact_contract, dict)
        else ""
    )
    policy = manifest.get("policy")
    files = manifest.get("files")
    return {
        "schema_supported": manifest.get("schema_version") == SCHEMA_VERSION,
        "status_validated": manifest.get("status") == "validated_real_origin_bundle",
        "immutable_path_matches_manifest": snapshot_path
        == immutable_snapshot_path(snapshot_date, manifest_sha256).as_posix(),
        "artifact_contract_schema_supported": declared_contract_schema
        == ARTIFACT_CONTRACT_SCHEMA_VERSION,
        "artifact_contract_checksum_valid": declared_contract
        == artifact_contract_sha256(manifest),
        "required_real_data_policy": isinstance(policy, dict)
        and all(policy.get(key) is True for key in REQUIRED_POLICY),
        "bundle_file_inventory_present": isinstance(files, list) and bool(files),
    }


def _evidence_ref(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _all_true(checks: dict[str, Any]) -> bool:
    return all(value is True for value in checks.values())


def prepare_rollback_plan(
    *,
    dataset_repo: str,
    target_snapshot_path: str,
    restore_report_path: Path,
    validation_report_path: Path,
    live_verification_path: Path,
    timeout: float,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ScaleOriginError("--timeout must be positive")
    target_snapshot = safe_artifact_relative_path(target_snapshot_path).as_posix()
    if not re.fullmatch(
        r"scale/snapshots/\d{4}-\d{2}-\d{2}/[0-9a-f]{64}", target_snapshot
    ):
        raise ScaleOriginError(
            "target snapshot path is not immutable/content-addressed"
        )

    restore = load_json_object(restore_report_path)
    validation = load_json_object(validation_report_path)
    live_verification = load_json_object(live_verification_path)
    base_url = f"https://huggingface.co/datasets/{dataset_repo}/resolve/main"
    latest_url = f"{base_url}/scale/latest.json"
    current_latest, current_pointer_sha256, _latest_bytes = fetch_json_document(
        latest_url, timeout
    )
    current_snapshot = safe_artifact_relative_path(
        str(current_latest.get("snapshot_path") or "")
    ).as_posix()
    if not current_snapshot.startswith("scale/snapshots/"):
        raise ScaleOriginError("current pointer does not name an immutable snapshot")
    current_manifest_url = f"{base_url}/{current_snapshot}/manifest.json"
    current_manifest, current_manifest_sha256, _current_manifest_bytes = (
        fetch_json_document(current_manifest_url, timeout)
    )
    target_manifest_url = f"{base_url}/{target_snapshot}/manifest.json"
    target_manifest, target_manifest_sha256, _target_manifest_bytes = (
        fetch_json_document(target_manifest_url, timeout)
    )

    current_manifest_checks = _manifest_checks(
        current_manifest, current_manifest_sha256, current_snapshot
    )
    target_manifest_checks = _manifest_checks(
        target_manifest, target_manifest_sha256, target_snapshot
    )
    target_release_id = target_manifest_sha256[:RELEASE_ID_LENGTH]
    current_release_id = current_manifest_sha256[:RELEASE_ID_LENGTH]
    current_summary = _summary(current_manifest)
    target_summary = _summary(target_manifest)
    current_contract = str(current_manifest["artifact_contract"]["sha256"])
    target_contract = str(target_manifest["artifact_contract"]["sha256"])
    current_corpora = _corpus_contracts(current_manifest)
    target_corpora = _corpus_contracts(target_manifest)
    target_files = target_manifest.get("files")
    target_bundle_files = len(target_files) if isinstance(target_files, list) else -1
    target_bundle_bytes = (
        sum(
            int(item.get("bytes") or 0)
            for item in target_files
            if isinstance(item, dict)
        )
        if isinstance(target_files, list)
        else -1
    )

    pointer_checks = {
        "schema_supported": current_latest.get("schema_version") == SCHEMA_VERSION,
        "release_matches_manifest": current_latest.get("release_id")
        == current_release_id,
        "manifest_sha256_matches": current_latest.get("manifest_sha256")
        == current_manifest_sha256,
        "snapshot_path_matches": current_snapshot
        == immutable_snapshot_path(
            str(current_latest.get("snapshot_date") or ""),
            current_manifest_sha256,
        ).as_posix(),
        "artifact_contract_matches": current_latest.get("artifact_contract_sha256")
        == current_contract,
    }
    restore_checks = {
        "status_verified": restore.get("status") == "restored_checksums_verified",
        "errors_absent": restore.get("errors") == [],
        "explicit_immutable_selection": restore.get("selection_mode")
        == "explicit_immutable_snapshot",
        "snapshot_path_matches": restore.get("snapshot_path") == target_snapshot,
        "manifest_sha256_matches": restore.get("manifest_sha256")
        == target_manifest_sha256,
        "artifact_contract_matches": restore.get("artifact_contract_sha256")
        == target_contract,
        "files_match_manifest": int(restore.get("files") or -1) == target_bundle_files,
        "bytes_match_manifest": int(restore.get("bytes") or -1) == target_bundle_bytes,
        "public_domain_identity_retained": restore.get(
            "public_domain_personal_information_retained"
        )
        is True,
    }
    validation_totals = validation.get("totals")
    validation_checks_payload = validation.get("checks")
    validation_checks = {
        "status_ok": validation.get("status") == "ok",
        "errors_absent": validation.get("errors") == [],
        "release_matches": validation.get("release_id") == target_release_id,
        "artifact_contract_matches": validation.get("artifact_contract_sha256")
        == target_contract,
        "rows_match": isinstance(validation_totals, dict)
        and int(validation_totals.get("rows") or -1) == target_summary["rows"],
        "data_files_match": isinstance(validation_totals, dict)
        and int(validation_totals.get("data_files") or -1)
        == target_summary["data_files"],
        "data_bytes_match": isinstance(validation_totals, dict)
        and int(validation_totals.get("data_bytes") or -1)
        == target_summary["data_bytes"],
        "all_corpora_valid": isinstance(validation_checks_payload, dict)
        and validation_checks_payload.get("corpora_valid") is True,
        "official_real_only": isinstance(validation_checks_payload, dict)
        and validation_checks_payload.get("official_real_records_only") is True,
        "synthetic_or_mock_forbidden": isinstance(validation_checks_payload, dict)
        and validation_checks_payload.get("synthetic_or_mock_records_forbidden")
        is True,
        "public_domain_identity_retained": isinstance(validation_checks_payload, dict)
        and validation_checks_payload.get(
            "official_public_domain_personal_information_retained"
        )
        is True,
    }
    parity_checks = {
        "different_release_ids": current_release_id != target_release_id,
        "artifact_contract_unchanged": current_contract == target_contract,
        "summary_unchanged": current_summary == target_summary,
        "corpus_contracts_unchanged": current_corpora == target_corpora,
        "snapshot_date_unchanged": current_manifest.get("snapshot_date")
        == target_manifest.get("snapshot_date"),
    }
    live_checks = {
        "verification_passed": live_verification.get("passed") is True,
        "dataset_repo_matches": live_verification.get("dataset_repo") == dataset_repo,
        "current_manifest_matches": isinstance(live_verification.get("checks"), dict)
        and live_verification["checks"].get("downloaded_manifest_sha256")
        == current_manifest_sha256,
    }
    checks = {
        "current_pointer": pointer_checks,
        "current_manifest": current_manifest_checks,
        "target_manifest": target_manifest_checks,
        "restore_evidence": restore_checks,
        "full_validation_evidence": validation_checks,
        "current_target_data_parity": parity_checks,
        "live_verification_evidence": live_checks,
    }
    failed_checks = [
        f"{group}.{name}"
        for group, group_checks in checks.items()
        for name, passed in group_checks.items()
        if passed is not True
    ]
    current_date = date.fromisoformat(str(current_manifest.get("snapshot_date")))
    target_date = date.fromisoformat(str(target_manifest.get("snapshot_date")))
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    proposed_pointer = {
        "schema_version": SCHEMA_VERSION,
        "project": "vota-con-la-chola",
        "snapshot_date": str(target_manifest.get("snapshot_date")),
        "release_id": target_release_id,
        "snapshot_path": target_snapshot,
        "manifest_sha256": target_manifest_sha256,
        "artifact_contract_sha256": target_contract,
        **target_summary,
        "updated_at": "SET_TO_ACTIVATION_TIME_UTC",
    }
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": (
            "rollback_candidate_ready_authorization_required"
            if not failed_checks
            else "blocked_rollback_candidate_invalid"
        ),
        "dataset_repo": dataset_repo,
        "operation": {
            "kind": "pointer_only_rollback",
            "remote_method_during_plan": "GET_only",
            "immutable_upload_required": False,
            "mutation_performed": False,
        },
        "current": {
            "latest_url": latest_url,
            "pointer_sha256": current_pointer_sha256,
            "release_id": current_release_id,
            "snapshot_path": current_snapshot,
            "manifest_url": current_manifest_url,
            "manifest_sha256": current_manifest_sha256,
            "artifact_contract_sha256": current_contract,
            "summary": current_summary,
        },
        "target": {
            "release_id": target_release_id,
            "snapshot_path": target_snapshot,
            "manifest_url": target_manifest_url,
            "manifest_sha256": target_manifest_sha256,
            "artifact_contract_sha256": target_contract,
            "summary": target_summary,
        },
        "delta": {
            "rows": target_summary["rows"] - current_summary["rows"],
            "data_files": target_summary["data_files"] - current_summary["data_files"],
            "data_bytes": target_summary["data_bytes"] - current_summary["data_bytes"],
            "snapshot_date_days": (target_date - current_date).days,
            "artifact_contract_changed": current_contract != target_contract,
        },
        "rpo": {
            "formal_rpo_defined": False,
            "status": "not_defined",
            "reason": "No publication cadence or maximum acceptable data-loss interval is approved; zero measured data-contract delta is not a formal RPO.",
            "measured_snapshot_date_delta_days": (target_date - current_date).days,
            "measured_row_delta": target_summary["rows"] - current_summary["rows"],
        },
        "supersession": {
            "status": "planned_not_activated",
            "current_release_if_activated": "superseded_pointer_target",
            "target_release_if_activated": "current_pointer_target",
            "preserve_both_immutable_releases": True,
            "immutable_deletion_allowed": False,
            "reason_required_at_activation": True,
            "operator_and_timestamp_required": True,
            "verification_outcome_required": True,
        },
        "evidence": {
            "restore": _evidence_ref(restore_report_path),
            "full_validation": _evidence_ref(validation_report_path),
            "live_verification": _evidence_ref(live_verification_path),
        },
        "checks": checks,
        "failed_checks": failed_checks,
        "activation": {
            "authorized": False,
            "pointer_write_authorized": False,
            "mutation_performed": False,
            "compare_and_swap": {
                "expected_current_pointer_sha256": current_pointer_sha256,
                "expected_current_release_id": current_release_id,
                "expected_current_manifest_sha256": current_manifest_sha256,
                "abort_if_any_expected_value_changes": True,
            },
            "proposed_pointer_fields": proposed_pointer,
            "required_steps": [
                "Obtain explicit maintainer authorization for the exact target release.",
                "Re-fetch scale/latest.json and abort unless all compare-and-swap expectations still match.",
                "Re-fetch the target manifest and abort unless its SHA-256 still matches.",
                "Run the public-artifact hygiene gate against the exact planned pointer.",
                "Write only scale/latest.json; do not alter immutable snapshot files.",
                "Immediately verify pointer, manifest, artifact contract, corpus totals, and public availability.",
                "Record supersession reason, operator, activation timestamp, verification result, and rollback outcome.",
            ],
        },
        "public_domain_personal_information_retained": True,
        "errors": failed_checks,
    }


def validate_plan_artifact(plan: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        errors.append("unsupported plan schema")
    if plan.get("status") != "rollback_candidate_ready_authorization_required":
        errors.append("plan is not ready for explicit authorization")
    operation = plan.get("operation")
    activation = plan.get("activation")
    if (
        not isinstance(operation, dict)
        or operation.get("mutation_performed") is not False
    ):
        errors.append("plan does not prove mutation_performed=false")
    if not isinstance(activation, dict) or activation.get("authorized") is not False:
        errors.append("plan does not require explicit authorization")
    supersession = plan.get("supersession")
    if (
        not isinstance(supersession, dict)
        or supersession.get("immutable_deletion_allowed") is not False
        or supersession.get("preserve_both_immutable_releases") is not True
    ):
        errors.append("plan does not preserve both immutable releases")
    if plan.get("failed_checks") != [] or plan.get("errors") != []:
        errors.append("plan contains failed checks")
    evidence = plan.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("plan has no evidence bindings")
        return errors
    for name, item in evidence.items():
        if not isinstance(item, dict):
            errors.append(f"invalid evidence entry: {name}")
            continue
        try:
            path = safe_repo_path(repo_root, str(item.get("path") or ""), name)
        except ScaleOriginError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"missing evidence file: {name}")
            continue
        if int(item.get("bytes") or -1) != path.stat().st_size:
            errors.append(f"evidence byte mismatch: {name}")
        if item.get("sha256") != sha256_file(path):
            errors.append(f"evidence checksum mismatch: {name}")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-repo", default="")
    parser.add_argument("--hf-username", default="")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--target-snapshot-path", required=True)
    parser.add_argument("--restore-report", required=True)
    parser.add_argument("--validation-report", required=True)
    parser.add_argument("--live-verification", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        dotenv_values = load_dotenv(Path(args.env_file))
        username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
        raw_repo = resolve_setting(
            "HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values
        )
        dataset_repo = resolve_dataset_repo(raw_repo, username)
        restore_report = safe_repo_path(
            REPO_ROOT, args.restore_report, "restore report"
        )
        validation_report = safe_repo_path(
            REPO_ROOT, args.validation_report, "validation report"
        )
        live_verification = safe_repo_path(
            REPO_ROOT, args.live_verification, "live verification"
        )
        out_path = safe_repo_path(REPO_ROOT, args.out, "rollback plan")
        plan = prepare_rollback_plan(
            dataset_repo=dataset_repo,
            target_snapshot_path=args.target_snapshot_path,
            restore_report_path=restore_report,
            validation_report_path=validation_report,
            live_verification_path=live_verification,
            timeout=args.timeout,
        )
        write_json(out_path, plan)
        validation_errors = validate_plan_artifact(plan, REPO_ROOT)
        print(
            json.dumps(
                {
                    "status": plan["status"],
                    "current_release_id": plan["current"]["release_id"],
                    "target_release_id": plan["target"]["release_id"],
                    "failed_checks": plan["failed_checks"],
                    "validation_errors": validation_errors,
                    "mutation_performed": False,
                    "out": out_path.relative_to(REPO_ROOT).as_posix(),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        if args.enforce and (plan["failed_checks"] or validation_errors):
            return 1
        return 0
    except (HTTPError, OSError, ScaleOriginError, URLError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
