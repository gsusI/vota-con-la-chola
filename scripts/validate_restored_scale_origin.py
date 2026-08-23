#!/usr/bin/env python3
"""Validate every selected corpus in a restored public scale-origin bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.publicar_hf_scale_snapshot import (
    ARTIFACT_CONTRACT_SCHEMA_VERSION,
    RELEASE_ID_LENGTH,
    SCHEMA_VERSION,
    ScaleOriginError,
    artifact_contract_sha256,
    immutable_snapshot_path,
    load_json_object,
    safe_artifact_relative_path,
    sha256_file,
    write_json,
)
from scripts.restore_hf_scale_origin import (
    DEFAULT_ALLOWED_SIGNERS,
    DEFAULT_SIGNER_IDENTITY,
    RESTORED_ATTESTATION_PATHS,
    audit_destination_files,
    selected_manifest_files,
    verify_restore_attestation_files,
)

ValidationFunction = Callable[..., dict[str, Any]]


def parse_csv_set(raw_value: str) -> set[str]:
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def safe_child(root: Path, raw_relative: str, label: str) -> Path:
    relative = safe_artifact_relative_path(raw_relative)
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ScaleOriginError(f"{label} escapes restored root: {raw_relative!r}")
    return resolved


def audit_restored_inventory(
    *,
    root: Path,
    manifest: dict[str, Any],
    corpus_ids: set[str],
    reference_file_name: str,
    include_remote_latest: bool = False,
    include_signed_attestation: bool = False,
) -> dict[str, Any]:
    """Require an isolated restore to contain only selected declared files."""
    expected = {
        str(item["path"]) for item in selected_manifest_files(manifest, corpus_ids)
    }
    expected.update({"manifest.json", reference_file_name})
    if include_remote_latest:
        expected.add("remote-latest.json")
    if include_signed_attestation:
        expected.update(RESTORED_ATTESTATION_PATHS.values())
    return audit_destination_files(destination=root, expected_files=expected)


def semantic_validators() -> dict[str, ValidationFunction]:
    from publicdata_publish.accountability_partition_validation import (
        validate_accountability_partitions,
    )
    from publicdata_publish.actor_mandate_partition_validation import (
        validate_actor_mandate_partitions,
    )
    from publicdata_publish.candidate_occurrence_partition_validation import (
        validate_candidate_occurrence_partitions,
    )
    from publicdata_publish.indicator_partition_validation import (
        validate_indicator_partitions,
    )
    from publicdata_publish.money_partition_validation import validate_money_partitions
    from publicdata_publish.semantic_partition_validation import (
        validate_semantic_partitions,
    )

    return {
        "accountability_ledger": validate_accountability_partitions,
        "actor_mandates": validate_actor_mandate_partitions,
        "candidate_occurrences": validate_candidate_occurrence_partitions,
        "indicator_observations": validate_indicator_partitions,
        "member_votes": validate_semantic_partitions,
        "public_money_facts": validate_money_partitions,
    }


def vote_validator() -> ValidationFunction:
    from scripts.validate_member_vote_shards import validate_shards

    return validate_shards


def corpus_result_summary(
    *, corpus: dict[str, Any], validation: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    corpus_id = str(corpus.get("id") or "")
    kind = str(corpus.get("kind") or "")
    totals = validation.get("totals")
    if not isinstance(totals, dict):
        raise ScaleOriginError(f"validator returned no totals for {corpus_id}")
    if kind == "gzip_vote_shards":
        rows = int(totals.get("member_votes") or 0)
        files = int(totals.get("entries") or 0)
        data_bytes = int(totals.get("bytes") or 0)
        private_findings = int(totals.get("payloads_with_private_path_tokens") or 0)
    elif kind == "parquet_manifest":
        rows = int(totals.get("rows") or 0)
        files = int(totals.get("files") or 0)
        data_bytes = int(totals.get("parquet_bytes") or 0)
        private_findings = int(totals.get("private_token_findings") or 0)
    else:
        raise ScaleOriginError(f"unsupported corpus kind for {corpus_id}: {kind!r}")

    declared = {
        "rows": int(corpus.get("rows") or 0),
        "files": int(corpus.get("files") or 0),
        "bytes": int(corpus.get("bytes") or 0),
    }
    actual = {"rows": rows, "files": files, "bytes": data_bytes}
    checks = {
        "validator_status_ok": validation.get("status") == "ok",
        "rows_match_release": rows == declared["rows"],
        "files_match_release": files == declared["files"],
        "bytes_match_release": data_bytes == declared["bytes"],
        "no_private_tokens": private_findings == 0,
    }
    errors = [
        f"{corpus_id}: {name} failed" for name, passed in checks.items() if not passed
    ]
    performance = validation.get("performance")
    summary = {
        "id": corpus_id,
        "kind": kind,
        "lane": validation.get("lane"),
        "status": "ok" if not errors else "failed",
        "declared": declared,
        "actual": actual,
        "private_token_findings": private_findings,
        "checks": checks,
    }
    if isinstance(performance, dict):
        summary["performance"] = performance
    return summary, errors


def validate_restored_bundle(
    *,
    root: Path,
    registry_path: Path | None,
    corpus_ids: set[str],
    batch_rows: int,
    max_peak_rss_mb: float,
    require_isolated: bool = False,
    require_signed: bool = False,
    allowed_signers_path: Path | None = None,
    signer_identity: str = DEFAULT_SIGNER_IDENTITY,
    validators: dict[str, ValidationFunction] | None = None,
    shard_validator: ValidationFunction | None = None,
) -> dict[str, Any]:
    requested_root = Path(root)
    if require_isolated and requested_root.is_symlink():
        raise ScaleOriginError("isolated validation root must not be a symlink")
    restored_root = requested_root.resolve()
    if require_isolated and registry_path is not None:
        raise ScaleOriginError(
            "isolated validation requires bundled registry; omit registry override"
        )
    manifest_path = restored_root / "manifest.json"
    reference_path = restored_root / "restore-reference.json"
    if not reference_path.is_file():
        reference_path = restored_root / "remote-latest.json"
    if require_isolated and reference_path.name != "restore-reference.json":
        raise ScaleOriginError(
            "isolated validation requires an exact restore-reference.json"
        )
    if require_isolated and (manifest_path.is_symlink() or reference_path.is_symlink()):
        raise ScaleOriginError("isolated validation control files must not be symlinks")
    manifest = load_json_object(manifest_path)
    latest = load_json_object(reference_path)
    errors: list[str] = []
    signed_required = bool(require_signed or require_isolated)

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("restored manifest schema is unsupported")
    if latest.get("schema_version") != SCHEMA_VERSION:
        errors.append("restored latest-pointer schema is unsupported")
    manifest_sha256 = sha256_file(manifest_path)
    if latest.get("manifest_sha256") != manifest_sha256:
        errors.append("restored manifest checksum differs from restore reference")
    snapshot_date = str(latest.get("snapshot_date") or "")
    try:
        expected_snapshot_path = immutable_snapshot_path(snapshot_date, manifest_sha256)
    except ScaleOriginError as exc:
        errors.append(str(exc))
        expected_snapshot_path = Path("invalid")
    if str(latest.get("snapshot_path") or "") != expected_snapshot_path.as_posix():
        errors.append("restored reference is not content-addressed")
    if str(latest.get("release_id") or "") != manifest_sha256[:RELEASE_ID_LENGTH]:
        errors.append("restored release_id differs from manifest checksum")

    artifact_contract = manifest.get("artifact_contract")
    contract_sha256 = artifact_contract_sha256(manifest)
    if not isinstance(artifact_contract, dict):
        errors.append("restored manifest has no artifact contract")
    else:
        if artifact_contract.get("schema_version") != ARTIFACT_CONTRACT_SCHEMA_VERSION:
            errors.append("restored artifact contract schema is unsupported")
        if artifact_contract.get("sha256") != contract_sha256:
            errors.append("restored artifact contract checksum is invalid")
    if latest.get("artifact_contract_sha256") != contract_sha256:
        errors.append("restored reference artifact contract differs")

    raw_corpora = manifest.get("corpora")
    if not isinstance(raw_corpora, list):
        raise ScaleOriginError("restored manifest has no corpora array")
    corpora = {
        str(item.get("id") or ""): item
        for item in raw_corpora
        if isinstance(item, dict) and item.get("id")
    }
    selected_ids = set(corpus_ids) if corpus_ids else set(corpora)
    unknown = selected_ids - set(corpora)
    if unknown:
        raise ScaleOriginError("unknown corpus IDs: " + ", ".join(sorted(unknown)))

    selection_mode = str(latest.get("selection_mode") or "")
    remote_pointer_checks: dict[str, bool] = {}
    remote_pointer_validation_required = selection_mode == "latest_pointer" and (
        require_isolated or bool(latest.get("remote_latest_sha256"))
    )
    if remote_pointer_validation_required:
        remote_pointer_path = restored_root / "remote-latest.json"
        if require_isolated and remote_pointer_path.is_symlink():
            raise ScaleOriginError(
                "isolated validation remote latest capture must not be a symlink"
            )
        remote_pointer = load_json_object(remote_pointer_path)
        remote_pointer_checks["checksum_matches_capture"] = sha256_file(
            remote_pointer_path
        ) == str(latest.get("remote_latest_sha256") or "")
        for key in (
            "schema_version",
            "project",
            "snapshot_date",
            "release_id",
            "snapshot_path",
            "manifest_sha256",
            "artifact_contract_sha256",
        ):
            remote_pointer_checks[f"{key}_matches_reference"] = remote_pointer.get(
                key
            ) == latest.get(key)
        if signed_required:
            reference_attestation = latest.get("attestation")
            expected_remote_attestation = (
                {
                    key: value
                    for key, value in reference_attestation.items()
                    if key != "restored_files"
                }
                if isinstance(reference_attestation, dict)
                else None
            )
            remote_pointer_checks["attestation_matches_reference"] = (
                remote_pointer.get("attestation") == expected_remote_attestation
            )
        errors.extend(
            f"remote latest capture check failed: {name}"
            for name, passed in remote_pointer_checks.items()
            if not passed
        )
    inventory = audit_restored_inventory(
        root=restored_root,
        manifest=manifest,
        corpus_ids=selected_ids,
        reference_file_name=reference_path.name,
        include_remote_latest=selection_mode == "latest_pointer",
        include_signed_attestation=signed_required,
    )
    if require_isolated and inventory["passed"] is not True:
        errors.extend(
            f"isolated restore missing file: {path}"
            for path in inventory["missing_files"][:20]
        )
        errors.extend(
            f"isolated restore has undeclared file: {path}"
            for path in inventory["undeclared_files"][:20]
        )
        errors.extend(
            f"isolated restore has symlink: {path}"
            for path in inventory["symlinks"][:20]
        )
    if require_isolated and inventory["symlinks_count"]:
        raise ScaleOriginError("isolated restore contains symlinks")

    attestation_verification: dict[str, Any] | None = None
    if signed_required:
        attestation_meta = latest.get("attestation")
        if not isinstance(attestation_meta, dict):
            raise ScaleOriginError(
                "isolated validation requires restored attestation metadata"
            )
        restored_files = attestation_meta.get("restored_files")
        if restored_files != RESTORED_ATTESTATION_PATHS:
            raise ScaleOriginError(
                "restored attestation file contract is missing or unsupported"
            )
        manifest_url = str(latest.get("manifest_url") or "")
        if not manifest_url.startswith("https://"):
            raise ScaleOriginError("restored reference has no HTTPS manifest URL")
        effective_allowed_signers = (
            allowed_signers_path
            if allowed_signers_path is not None
            else REPO_ROOT / DEFAULT_ALLOWED_SIGNERS
        )
        if not effective_allowed_signers.is_file():
            raise ScaleOriginError("trusted allowed_signers file is missing")
        attestation_verification = verify_restore_attestation_files(
            manifest_path=manifest_path,
            attestation_path=restored_root / RESTORED_ATTESTATION_PATHS["attestation"],
            signature_path=restored_root / RESTORED_ATTESTATION_PATHS["signature"],
            public_key_path=restored_root / RESTORED_ATTESTATION_PATHS["public_key"],
            allowed_signers_path=effective_allowed_signers,
            signer_identity=signer_identity,
            manifest_url=manifest_url,
            snapshot_path=str(latest.get("snapshot_path") or ""),
            snapshot_date=str(latest.get("snapshot_date") or ""),
            attestation_meta=attestation_meta,
        )
        if attestation_verification.get("passed") is not True:
            raise ScaleOriginError(
                "restored signed attestation failed: "
                + "; ".join(
                    str(item) for item in attestation_verification.get("errors", [])
                )
            )

    effective_registry_path = (
        registry_path or restored_root / "real-corpus-registry.json"
    )
    registry = load_json_object(effective_registry_path)
    registry_items = {
        str(item.get("id") or ""): item
        for item in registry.get("corpora", [])
        if isinstance(item, dict) and item.get("id")
    }
    missing_registry = selected_ids - set(registry_items)
    if missing_registry:
        raise ScaleOriginError(
            "selected corpora missing from registry: "
            + ", ".join(sorted(missing_registry))
        )

    selected_files = selected_manifest_files(manifest, selected_ids)
    restored_file_errors: list[str] = []
    restored_files_valid = 0
    restored_bytes_valid = 0
    for entry in selected_files:
        path = safe_child(restored_root, str(entry["path"]), "restored file")
        if not path.is_file():
            restored_file_errors.append(f"missing restored file: {entry['path']}")
            continue
        size = int(path.stat().st_size)
        digest = sha256_file(path)
        if size != int(entry["bytes"]) or digest != str(entry["sha256"]):
            restored_file_errors.append(f"restored checksum mismatch: {entry['path']}")
            continue
        restored_files_valid += 1
        restored_bytes_valid += size
    errors.extend(restored_file_errors[:20])

    validator_map = validators if validators is not None else semantic_validators()
    effective_shard_validator = shard_validator or vote_validator()
    results: list[dict[str, Any]] = []
    for corpus_id in sorted(selected_ids):
        corpus = corpora[corpus_id]
        kind = str(corpus.get("kind") or "")
        corpus_manifest_entry = corpus.get("manifest")
        if not isinstance(corpus_manifest_entry, dict):
            raise ScaleOriginError(f"missing corpus manifest entry for {corpus_id}")
        corpus_manifest_path = safe_child(
            restored_root,
            str(corpus_manifest_entry.get("path") or ""),
            f"{corpus_id} manifest",
        )
        data_root = safe_child(
            restored_root,
            str(corpus.get("data_prefix") or ""),
            f"{corpus_id} data",
        )
        if kind == "gzip_vote_shards":
            validation = effective_shard_validator(
                corpus_manifest_path, shard_root=data_root
            )
        elif kind == "parquet_manifest":
            corpus_manifest = load_json_object(corpus_manifest_path)
            lane = str(corpus_manifest.get("lane") or "")
            validator = validator_map.get(lane)
            if validator is None:
                raise ScaleOriginError(
                    f"unsupported semantic lane for {corpus_id}: {lane!r}"
                )
            validation = validator(
                root=data_root,
                manifest_path=corpus_manifest_path,
                batch_rows=batch_rows,
                min_rows=int(registry_items[corpus_id].get("minimum_real_rows") or 1),
                max_peak_rss_mb=max_peak_rss_mb,
            )
            validation["lane"] = lane
        else:
            raise ScaleOriginError(f"unsupported corpus kind: {kind!r}")
        summary, corpus_errors = corpus_result_summary(
            corpus=corpus, validation=validation
        )
        results.append(summary)
        errors.extend(corpus_errors)

    declared_rows = sum(int(corpora[item].get("rows") or 0) for item in selected_ids)
    declared_data_files = sum(
        int(corpora[item].get("files") or 0) for item in selected_ids
    )
    declared_data_bytes = sum(
        int(corpora[item].get("bytes") or 0) for item in selected_ids
    )
    validated_rows = sum(int(item["actual"]["rows"]) for item in results)
    validated_data_files = sum(int(item["actual"]["files"]) for item in results)
    validated_data_bytes = sum(int(item["actual"]["bytes"]) for item in results)
    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        policy = {}
    aggregate_checks = {
        "selected_restored_files_valid": restored_files_valid == len(selected_files),
        "selected_restored_bytes_valid": restored_bytes_valid
        == sum(int(item["bytes"]) for item in selected_files),
        "corpora_valid": all(item["status"] == "ok" for item in results),
        "rows_match_release": validated_rows == declared_rows,
        "data_files_match_release": validated_data_files == declared_data_files,
        "data_bytes_match_release": validated_data_bytes == declared_data_bytes,
        "official_real_records_only": policy.get("official_real_records_only") is True,
        "synthetic_or_mock_records_forbidden": policy.get(
            "synthetic_or_mock_records_forbidden"
        )
        is True,
        "official_public_domain_personal_information_retained": policy.get(
            "official_public_domain_personal_information_retained"
        )
        is True,
    }
    if require_isolated:
        aggregate_checks.update(
            {
                "bundled_registry_used": registry_path is None,
                "isolated_inventory_exact": inventory["passed"] is True,
                "no_undeclared_files": inventory["undeclared_files_count"] == 0,
                "no_symlinks": inventory["symlinks_count"] == 0,
                "signed_origin_verified": attestation_verification is not None
                and attestation_verification.get("passed") is True,
                "remote_pointer_capture_valid": all(remote_pointer_checks.values())
                if remote_pointer_validation_required
                else True,
            }
        )
    errors.extend(
        f"aggregate check failed: {name}"
        for name, passed in aggregate_checks.items()
        if not passed
    )
    return {
        "schema_version": "restored_scale_origin_validation_v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "ok" if not errors else "failed",
        "root_name": restored_root.name,
        "reference_file": reference_path.name,
        "selection_mode": latest.get("selection_mode", "legacy_latest_pointer"),
        "snapshot_date": manifest.get("snapshot_date"),
        "release_id": manifest_sha256,
        "artifact_contract_sha256": contract_sha256,
        "selected_corpus_ids": sorted(selected_ids),
        "signed_attestation_required": signed_required,
        "signed_attestation_verified": attestation_verification is not None
        and attestation_verification.get("passed") is True,
        "attestation": (
            {
                "status": attestation_verification.get("status"),
                "attestation_sha256": attestation_verification.get("checks", {}).get(
                    "attestation_sha256"
                ),
                "signature_sha256": attestation_verification.get("checks", {}).get(
                    "signature_sha256"
                ),
                "signer_identity": attestation_verification.get("checks", {}).get(
                    "signer_identity"
                ),
                "public_key_fingerprint": attestation_verification.get(
                    "checks", {}
                ).get("attested_public_key_fingerprint"),
                "errors": attestation_verification.get("errors", []),
            }
            if attestation_verification is not None
            else None
        ),
        "remote_latest_capture": {
            "required": remote_pointer_validation_required,
            "checks": remote_pointer_checks,
            "passed": all(remote_pointer_checks.values())
            if remote_pointer_validation_required
            else True,
        },
        "publish_eligible": False,
        "public_promotion_eligible": False,
        "isolation": {
            "required": bool(require_isolated),
            "registry_source": (
                "restored_bundle" if registry_path is None else "external_override"
            ),
            **inventory,
        },
        "totals": {
            "corpora": len(results),
            "rows": validated_rows,
            "data_files": validated_data_files,
            "data_bytes": validated_data_bytes,
            "restored_files": len(selected_files),
            "restored_bytes": sum(int(item["bytes"]) for item in selected_files),
            "bundle_files": inventory["actual_files"],
            "bundle_bytes": inventory["actual_bytes"],
            "restored_files_checksum_valid": restored_files_valid,
            "restored_bytes_checksum_valid": restored_bytes_valid,
        },
        "checks": aggregate_checks,
        "corpora": results,
        "errors": errors[:100],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--registry", default="")
    parser.add_argument("--corpus-ids", default="")
    parser.add_argument("--batch-rows", type=int, default=10_000)
    parser.add_argument("--max-peak-rss-mb", type=float, default=1536.0)
    parser.add_argument("--report-out", default="")
    parser.add_argument(
        "--require-isolated",
        action="store_true",
        help="require exact inventory, bundled registry, and signed-origin proof",
    )
    parser.add_argument(
        "--require-signed",
        action="store_true",
        help="re-verify restored attestation files against the trusted signer policy",
    )
    parser.add_argument("--allowed-signers", default=DEFAULT_ALLOWED_SIGNERS)
    parser.add_argument("--signer-identity", default=DEFAULT_SIGNER_IDENTITY)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.batch_rows <= 0 or args.max_peak_rss_mb <= 0:
            raise ScaleOriginError("batch rows and RSS ceiling must be positive")
        allowed_signers_path = Path(args.allowed_signers)
        if not allowed_signers_path.is_absolute():
            allowed_signers_path = REPO_ROOT / allowed_signers_path
        report = validate_restored_bundle(
            root=Path(args.root),
            registry_path=Path(args.registry) if args.registry.strip() else None,
            corpus_ids=parse_csv_set(args.corpus_ids),
            batch_rows=args.batch_rows,
            max_peak_rss_mb=args.max_peak_rss_mb,
            require_isolated=bool(args.require_isolated),
            require_signed=bool(args.require_signed),
            allowed_signers_path=allowed_signers_path,
            signer_identity=args.signer_identity,
        )
    except (
        OSError,
        ScaleOriginError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        report = {
            "schema_version": "restored_scale_origin_validation_v1",
            "status": "failed",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    if args.report_out.strip():
        try:
            write_json(Path(args.report_out), report)
        except OSError as exc:
            print(f"ERROR: cannot write report: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 1 if args.enforce and report.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
