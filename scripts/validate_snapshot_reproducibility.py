#!/usr/bin/env python3
"""Validate one published signed scale release from real evidence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class ReproducibilityValidationError(RuntimeError):
    """Raised when a signed release evidence set is inconsistent."""


def load_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproducibilityValidationError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReproducibilityValidationError(f"{path.name} root must be an object")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_reproducibility_evidence(
    *,
    manifest: dict[str, Any],
    manifest_sha256: str,
    publish: dict[str, Any],
    live_signature: dict[str, Any],
    live_parity: dict[str, Any],
    diff: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    summary = manifest.get("summary")
    artifact_contract = manifest.get("artifact_contract")
    policy = manifest.get("policy")
    signature_checks = live_signature.get("checks")
    parity_checks = live_parity.get("checks")
    file_diff = diff.get("files")
    after_diff = diff.get("after")
    attestation = publish.get("attestation")

    for label, value in (
        ("manifest summary", summary),
        ("manifest artifact contract", artifact_contract),
        ("manifest policy", policy),
        ("live signature checks", signature_checks),
        ("live parity checks", parity_checks),
        ("file diff", file_diff),
        ("diff after", after_diff),
        ("publish attestation", attestation),
    ):
        _require(isinstance(value, dict), f"{label} is missing", errors)

    summary = summary if isinstance(summary, dict) else {}
    artifact_contract = artifact_contract if isinstance(artifact_contract, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    signature_checks = signature_checks if isinstance(signature_checks, dict) else {}
    parity_checks = parity_checks if isinstance(parity_checks, dict) else {}
    file_diff = file_diff if isinstance(file_diff, dict) else {}
    after_diff = after_diff if isinstance(after_diff, dict) else {}
    attestation = attestation if isinstance(attestation, dict) else {}

    _require(publish.get("status") == "ok", "publish status is not ok", errors)
    _require(publish.get("published") is True, "release was not published", errors)
    _require(publish.get("signed") is True, "release was not signed", errors)
    _require(
        attestation.get("status") == "signed_and_verified",
        "publisher did not verify the signature",
        errors,
    )
    _require(
        live_signature.get("status") == "verified_live_signed_snapshot"
        and live_signature.get("passed") is True
        and not live_signature.get("errors"),
        "live signature verification failed",
        errors,
    )
    _require(
        signature_checks.get("signature_verified") is True,
        "trusted live signature is not verified",
        errors,
    )
    _require(
        live_parity.get("status") == "verified_current_scale_origin"
        and live_parity.get("passed") is True
        and not live_parity.get("errors")
        and not live_parity.get("warnings"),
        "live origin parity failed",
        errors,
    )
    for key in (
        "corpus_contracts_match",
        "immutable_snapshot_path",
        "metadata_freshness",
        "promotion_states_match",
        "required_policy_passed",
    ):
        _require(
            parity_checks.get(key) is True, f"live parity check failed: {key}", errors
        )

    declared_manifest_sha256 = str(publish.get("manifest_sha256") or "")
    _require(
        manifest_sha256 == declared_manifest_sha256,
        "local evidence manifest hash differs from publish report",
        errors,
    )
    _require(
        declared_manifest_sha256 == str(attestation.get("manifest_sha256") or ""),
        "publish and attestation manifest hashes differ",
        errors,
    )
    _require(
        declared_manifest_sha256
        == str(parity_checks.get("downloaded_manifest_sha256") or ""),
        "published and live manifest hashes differ",
        errors,
    )
    _require(
        declared_manifest_sha256 == str(after_diff.get("manifest_sha256") or ""),
        "published and diff target manifest hashes differ",
        errors,
    )
    declared_contract_sha256 = str(artifact_contract.get("sha256") or "")
    _require(
        declared_contract_sha256 == str(publish.get("artifact_contract_sha256") or ""),
        "manifest and publish artifact contracts differ",
        errors,
    )
    _require(
        declared_contract_sha256
        == str(attestation.get("artifact_contract_sha256") or ""),
        "manifest and attestation artifact contracts differ",
        errors,
    )
    _require(
        manifest.get("schema_version") == "real-scale-origin-bundle-v2",
        "unsupported scale manifest schema",
        errors,
    )
    _require(
        artifact_contract.get("schema_version") == "real-scale-artifact-contract-v1",
        "unsupported artifact contract schema",
        errors,
    )
    _require(
        manifest.get("status") == "validated_real_origin_bundle",
        "manifest is not a validated real-origin bundle",
        errors,
    )
    for key in (
        "official_real_records_only",
        "synthetic_or_mock_records_forbidden",
        "official_public_domain_personal_information_retained",
        "secrets_workstation_traces_and_non_public_data_forbidden",
    ):
        _require(
            policy.get(key) is True, f"mandatory policy is not true: {key}", errors
        )

    for key in (
        "corpora",
        "rows",
        "data_files",
        "data_bytes",
        "million_scale_lanes",
        "promoted_lanes",
    ):
        _require(
            int(summary.get(key) or 0) == int(publish.get(key) or 0),
            f"manifest and publish totals differ: {key}",
            errors,
        )
    _require(
        int(summary.get("rows") or 0) >= 1_000_000,
        "release is below one million rows",
        errors,
    )
    _require(
        int(summary.get("million_scale_lanes") or 0) >= 1,
        "release has no million-scale lane",
        errors,
    )
    _require(diff.get("status") == "ok", "manifest diff status is not ok", errors)
    _require(
        int(file_diff.get("removed") or 0) == 0, "release removes artifacts", errors
    )
    _require(
        bool(
            str(attestation.get("public_key_fingerprint") or "").startswith("SHA256:")
        ),
        "release has no signing-key fingerprint",
        errors,
    )

    return {
        "schema_version": "vclc_snapshot_reproducibility_validation_v1",
        "status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors": errors,
        "release": {
            "snapshot_date": manifest.get("snapshot_date"),
            "manifest_sha256": declared_manifest_sha256,
            "artifact_contract_sha256": declared_contract_sha256,
            "signer_identity": attestation.get("signer_identity"),
            "public_key_fingerprint": attestation.get("public_key_fingerprint"),
            "corpora": int(summary.get("corpora") or 0),
            "rows": int(summary.get("rows") or 0),
            "data_files": int(summary.get("data_files") or 0),
            "data_bytes": int(summary.get("data_bytes") or 0),
            "million_scale_lanes": int(summary.get("million_scale_lanes") or 0),
        },
        "change": {
            "added_files": int(file_diff.get("added") or 0),
            "changed_files": int(file_diff.get("changed") or 0),
            "removed_files": int(file_diff.get("removed") or 0),
            "unchanged_files": int(file_diff.get("unchanged") or 0),
            "bytes_delta": int(file_diff.get("bytes_delta") or 0),
        },
        "checks": {
            "published": publish.get("published") is True,
            "signed": publish.get("signed") is True,
            "trusted_signature_verified": signature_checks.get("signature_verified")
            is True,
            "live_origin_matches_local_contract": parity_checks.get(
                "corpus_contracts_match"
            )
            is True,
            "live_metadata_current": parity_checks.get("metadata_freshness") is True,
            "immutable_path_verified": parity_checks.get("immutable_snapshot_path")
            is True,
            "official_public_domain_personal_information_retained": policy.get(
                "official_public_domain_personal_information_retained"
            )
            is True,
            "synthetic_or_mock_records": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--publish-report", required=True)
    parser.add_argument("--live-signature", required=True)
    parser.add_argument("--live-parity", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest_path = Path(args.manifest)
        report = validate_reproducibility_evidence(
            manifest=load_object(manifest_path),
            manifest_sha256=sha256_file(manifest_path),
            publish=load_object(Path(args.publish_report)),
            live_signature=load_object(Path(args.live_signature)),
            live_parity=load_object(Path(args.live_parity)),
            diff=load_object(Path(args.diff)),
        )
    except (OSError, ReproducibilityValidationError, ValueError) as exc:
        report = {
            "schema_version": "vclc_snapshot_reproducibility_validation_v1",
            "status": "error",
            "passed": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
