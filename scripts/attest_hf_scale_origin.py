#!/usr/bin/env python3
"""Sign and optionally publish an attestation for the current HF scale snapshot."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.hf_snapshot import load_dotenv, resolve_setting
from publicdata_publish.snapshot_attestation import (
    ATTESTATION_SCHEMA_VERSION,
    SIGNATURE_NAMESPACE,
    SnapshotAttestationError,
    create_signed_attestation,
    now_utc_iso,
    sha256_bytes,
    write_json_canonical,
)
from scripts.publicar_hf_scale_snapshot import (
    PLACEHOLDER_VALUES,
    ScaleOriginError,
    immutable_snapshot_path,
    resolve_dataset_repo,
    safe_artifact_relative_path,
    safe_repo_path,
)


def fetch_bytes(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "vota-con-la-chola/snapshot-attestation",
            "Accept": "application/json,*/*",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_json_object(body: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SnapshotAttestationError(f"invalid JSON for {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SnapshotAttestationError(f"JSON root must be an object for {label}")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-repo", default="")
    parser.add_argument("--hf-username", default="")
    parser.add_argument("--hf-token", default="")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--signer-identity", default="vclc-snapshot-release-2026")
    parser.add_argument("--issued-at", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--report-out", default="")
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        if args.timeout <= 0:
            raise SnapshotAttestationError("--timeout must be positive")
        private_key_path = Path(args.private_key).resolve()
        dotenv_values = load_dotenv(Path(args.env_file))
        username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
        raw_repo = resolve_setting(
            "HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values
        )
        dataset_repo = resolve_dataset_repo(raw_repo, username)
        base_url = f"https://huggingface.co/datasets/{dataset_repo}/resolve/main"
        latest_url = f"{base_url}/scale/latest.json"
        latest_body = fetch_bytes(latest_url, args.timeout)
        latest = parse_json_object(latest_body, "scale/latest.json")
        snapshot_path = safe_artifact_relative_path(
            str(latest.get("snapshot_path") or "")
        ).as_posix()
        manifest_url = f"{base_url}/{snapshot_path}/manifest.json"
        manifest_body = fetch_bytes(manifest_url, args.timeout)
        manifest_sha256 = sha256_bytes(manifest_body)
        if manifest_sha256 != str(latest.get("manifest_sha256") or ""):
            raise SnapshotAttestationError(
                "downloaded manifest checksum differs from scale/latest.json"
            )
        expected_snapshot_path = immutable_snapshot_path(
            str(latest.get("snapshot_date") or ""), manifest_sha256
        ).as_posix()
        if snapshot_path != expected_snapshot_path:
            raise SnapshotAttestationError(
                "scale/latest.json does not point to the content-addressed manifest path"
            )

        if args.out_dir.strip():
            out_dir = Path(args.out_dir).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            temporary = tempfile.TemporaryDirectory(prefix="vclc-snapshot-attestation-")
            out_dir = Path(temporary.name)
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_bytes(manifest_body)
        issued_at = args.issued_at.strip() or now_utc_iso()
        signed = create_signed_attestation(
            manifest_path=manifest_path,
            manifest_url=manifest_url,
            snapshot_path=snapshot_path,
            private_key_path=private_key_path,
            signer_identity=args.signer_identity,
            issued_at=issued_at,
            out_dir=out_dir,
        )
        attestation_prefix = f"{snapshot_path}/attestation"
        remote_paths = {
            "attestation": f"{attestation_prefix}/attestation.json",
            "signature": f"{attestation_prefix}/attestation.json.sig",
            "public_key": f"{attestation_prefix}/signing-key.pub",
        }
        latest["attestation"] = {
            "schema_version": ATTESTATION_SCHEMA_VERSION,
            "attestation_sha256": signed["attestation_sha256"],
            "signature_sha256": signed["signature_sha256"],
            "public_key_fingerprint": signed["public_key_fingerprint"],
            "signer_identity": signed["signer_identity"],
            "signature_namespace": SIGNATURE_NAMESPACE,
            **remote_paths,
        }
        latest_with_attestation_path = out_dir / "latest.json"
        write_json_canonical(latest_with_attestation_path, latest)

        published = False
        if args.publish:
            token = resolve_setting("HF_TOKEN", args.hf_token, dotenv_values)
            if token in PLACEHOLDER_VALUES:
                raise SnapshotAttestationError("HF_TOKEN is not configured")
            from huggingface_hub import CommitOperationAdd, HfApi  # type: ignore

            api = HfApi(token=token)
            operations = [
                CommitOperationAdd(
                    path_in_repo=remote_paths["attestation"],
                    path_or_fileobj=str(out_dir / "attestation.json"),
                ),
                CommitOperationAdd(
                    path_in_repo=remote_paths["signature"],
                    path_or_fileobj=str(out_dir / "attestation.json.sig"),
                ),
                CommitOperationAdd(
                    path_in_repo=remote_paths["public_key"],
                    path_or_fileobj=str(out_dir / "signing-key.pub"),
                ),
            ]
            api.create_commit(
                repo_id=dataset_repo,
                repo_type="dataset",
                operations=operations,
                commit_message=(
                    "Attach signed provenance to scale snapshot "
                    f"{latest.get('snapshot_date')}"
                ),
            )
            api.upload_file(
                repo_id=dataset_repo,
                repo_type="dataset",
                path_or_fileobj=str(latest_with_attestation_path),
                path_in_repo="scale/latest.json",
                commit_message="Point scale latest to signed provenance",
            )
            published = True

        report = {
            "schema_version": "vclc_snapshot_attestation_publish_v1",
            "status": "published_signed_and_verified"
            if published
            else "built_signed_and_verified",
            "published": published,
            "dataset_repo": dataset_repo,
            "snapshot_date": latest.get("snapshot_date"),
            "snapshot_path": snapshot_path,
            "manifest_url": manifest_url,
            "manifest_sha256": manifest_sha256,
            "artifact_contract_sha256": signed["artifact_contract_sha256"],
            "attestation": latest["attestation"],
            "policy": {
                "official_real_records_only": True,
                "synthetic_or_mock_records": False,
                "official_public_domain_personal_information_retained": True,
                "private_key_published": False,
            },
        }
        if args.report_out.strip():
            report_path = safe_repo_path(REPO_ROOT, args.report_out, "report")
            write_json_canonical(report_path, report)
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    except (OSError, ScaleOriginError, SnapshotAttestationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
