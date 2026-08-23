#!/usr/bin/env python3
"""Verify the trusted signature and live subject of the current HF snapshot."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.hf_snapshot import load_dotenv, resolve_setting
from publicdata_publish.snapshot_attestation import (
    SnapshotAttestationError,
    sha256_bytes,
    verify_signed_attestation,
    write_json_canonical,
)
from scripts.publicar_hf_scale_snapshot import (
    resolve_dataset_repo,
    safe_artifact_relative_path,
    safe_repo_path,
)


def fetch_bytes(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "vota-con-la-chola/verify-snapshot-attestation",
            "Accept": "application/json,*/*",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-repo", default="")
    parser.add_argument("--hf-username", default="")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--allowed-signers", required=True)
    parser.add_argument("--signer-identity", default="vclc-snapshot-release-2026")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report: dict[str, object] = {
        "schema_version": "vclc_live_snapshot_attestation_verification_v1",
        "status": "error",
        "passed": False,
        "errors": [],
    }
    try:
        if args.timeout <= 0:
            raise SnapshotAttestationError("--timeout must be positive")
        allowed_signers = Path(args.allowed_signers).resolve()
        if not allowed_signers.is_file():
            raise SnapshotAttestationError(
                f"trusted allowed_signers file not found: {allowed_signers}"
            )
        dotenv_values = load_dotenv(Path(args.env_file))
        username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
        raw_repo = resolve_setting(
            "HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values
        )
        dataset_repo = resolve_dataset_repo(raw_repo, username)
        base_url = f"https://huggingface.co/datasets/{dataset_repo}/resolve/main"
        latest_url = f"{base_url}/scale/latest.json"
        latest_body = fetch_bytes(latest_url, args.timeout)
        latest = json.loads(latest_body)
        if not isinstance(latest, dict):
            raise SnapshotAttestationError("scale/latest.json root is not an object")
        attestation_meta = latest.get("attestation")
        if not isinstance(attestation_meta, dict):
            raise SnapshotAttestationError(
                "scale/latest.json has no signed attestation pointer"
            )
        paths = {
            name: safe_artifact_relative_path(
                str(attestation_meta.get(name) or "")
            ).as_posix()
            for name in ("attestation", "signature", "public_key")
        }
        snapshot_path = safe_artifact_relative_path(
            str(latest.get("snapshot_path") or "")
        ).as_posix()
        manifest_rel = f"{snapshot_path}/manifest.json"
        urls = {
            "latest": latest_url,
            "manifest": f"{base_url}/{manifest_rel}",
            **{name: f"{base_url}/{path}" for name, path in paths.items()},
        }
        with tempfile.TemporaryDirectory(prefix="vclc-live-attestation-") as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = temp_root / "manifest.json"
            attestation_path = temp_root / "attestation.json"
            signature_path = temp_root / "attestation.json.sig"
            public_key_path = temp_root / "signing-key.pub"
            manifest_path.write_bytes(fetch_bytes(urls["manifest"], args.timeout))
            attestation_path.write_bytes(fetch_bytes(urls["attestation"], args.timeout))
            signature_path.write_bytes(fetch_bytes(urls["signature"], args.timeout))
            public_key_path.write_bytes(fetch_bytes(urls["public_key"], args.timeout))
            verification = verify_signed_attestation(
                manifest_path=manifest_path,
                attestation_path=attestation_path,
                signature_path=signature_path,
                allowed_signers_path=allowed_signers,
                signer_identity=args.signer_identity,
            )
            errors = list(verification["errors"])
            if sha256_bytes(attestation_path.read_bytes()) != str(
                attestation_meta.get("attestation_sha256") or ""
            ):
                errors.append("live attestation checksum differs from latest pointer")
            if sha256_bytes(signature_path.read_bytes()) != str(
                attestation_meta.get("signature_sha256") or ""
            ):
                errors.append("live signature checksum differs from latest pointer")
            if sha256_bytes(manifest_path.read_bytes()) != str(
                latest.get("manifest_sha256") or ""
            ):
                errors.append("live manifest checksum differs from latest pointer")
            report = {
                "schema_version": "vclc_live_snapshot_attestation_verification_v1",
                "status": "verified_live_signed_snapshot" if not errors else "error",
                "passed": not errors,
                "dataset_repo": dataset_repo,
                "snapshot_date": latest.get("snapshot_date"),
                "snapshot_path": snapshot_path,
                "urls": urls,
                "errors": errors,
                "checks": verification["checks"],
                "policy": {
                    "official_real_records_only": True,
                    "synthetic_or_mock_records": False,
                    "official_public_domain_personal_information_retained": True,
                },
            }
        exit_code = 0 if report["passed"] else 1
    except (OSError, SnapshotAttestationError, ValueError, json.JSONDecodeError) as exc:
        report["errors"] = [f"{type(exc).__name__}: {exc}"]
        exit_code = 2
    if args.json_out.strip():
        try:
            report_path = safe_repo_path(REPO_ROOT, args.json_out, "report")
            write_json_canonical(report_path, report)
        except (OSError, SnapshotAttestationError) as exc:
            print(f"ERROR: cannot write report: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
