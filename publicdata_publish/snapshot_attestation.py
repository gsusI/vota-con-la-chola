"""Cryptographic attestations and exact diffs for real snapshot manifests."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ATTESTATION_SCHEMA_VERSION = "vclc_snapshot_attestation_v1"
DIFF_SCHEMA_VERSION = "vclc_scale_manifest_diff_v1"
SIGNATURE_NAMESPACE = "vota-con-la-chola-snapshot-v1"
REQUIRED_PUBLIC_DATA_POLICY = (
    "official_real_records_only",
    "synthetic_or_mock_records_forbidden",
    "official_public_domain_personal_information_retained",
    "secrets_workstation_traces_and_non_public_data_forbidden",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SIGNER_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{2,127}$")


class SnapshotAttestationError(RuntimeError):
    """Raised when an attestation cannot be created or verified safely."""


def now_utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file_or_empty(path: Path) -> str:
    try:
        return sha256_file(path)
    except OSError:
        return ""


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotAttestationError(
            f"cannot read JSON object {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise SnapshotAttestationError(f"JSON root must be an object: {path}")
    return payload


def write_json_canonical(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload))


def _require_sha256(value: Any, label: str) -> str:
    digest = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(digest):
        raise SnapshotAttestationError(f"invalid {label} SHA-256")
    return digest


def _require_signer_identity(value: str) -> str:
    identity = value.strip()
    if not SIGNER_IDENTITY_RE.fullmatch(identity):
        raise SnapshotAttestationError("invalid signer identity")
    return identity


def normalize_public_key(public_key: str) -> str:
    fields = public_key.strip().split()
    if len(fields) < 2 or fields[0] != "ssh-ed25519":
        raise SnapshotAttestationError("snapshot signing key must be ssh-ed25519")
    try:
        decoded = base64.b64decode(fields[1], validate=True)
    except ValueError as exc:
        raise SnapshotAttestationError("invalid SSH public key encoding") from exc
    if not decoded:
        raise SnapshotAttestationError("empty SSH public key")
    comment = f" {fields[2]}" if len(fields) >= 3 else ""
    return f"{fields[0]} {fields[1]}{comment}\n"


def public_key_fingerprint(public_key: str) -> str:
    fields = normalize_public_key(public_key).split()
    decoded = base64.b64decode(fields[1])
    digest = base64.b64encode(hashlib.sha256(decoded).digest()).decode("ascii")
    return "SHA256:" + digest.rstrip("=")


def derive_public_key(private_key_path: Path) -> str:
    if not private_key_path.is_file():
        raise SnapshotAttestationError(
            f"private signing key not found: {private_key_path}"
        )
    completed = subprocess.run(
        ["ssh-keygen", "-y", "-f", str(private_key_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "ssh-keygen could not read the private key"
        raise SnapshotAttestationError(detail)
    return normalize_public_key(completed.stdout)


def allowed_signers_line(*, signer_identity: str, public_key: str) -> str:
    identity = _require_signer_identity(signer_identity)
    fields = normalize_public_key(public_key).split()
    return f'{identity} namespaces="{SIGNATURE_NAMESPACE}" {fields[0]} {fields[1]}\n'


def trusted_public_key_fingerprints(
    *, allowed_signers_path: Path, signer_identity: str
) -> list[str]:
    """Return independently trusted Ed25519 fingerprints for one signer."""
    identity = _require_signer_identity(signer_identity)
    try:
        lines = allowed_signers_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SnapshotAttestationError(
            f"cannot read trusted allowed_signers: {exc}"
        ) from exc
    fingerprints: set[str] = set()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            fields = shlex.split(line)
        except ValueError as exc:
            raise SnapshotAttestationError(
                f"invalid allowed_signers line {line_number}: {exc}"
            ) from exc
        if not fields or identity not in fields[0].split(","):
            continue
        try:
            key_index = fields.index("ssh-ed25519")
        except ValueError as exc:
            raise SnapshotAttestationError(
                f"trusted signer {identity} does not use ssh-ed25519"
            ) from exc
        if key_index + 1 >= len(fields):
            raise SnapshotAttestationError(
                f"trusted signer {identity} has no public key payload"
            )
        namespace_options = [
            field.removeprefix("namespaces=")
            for field in fields[1:key_index]
            if field.startswith("namespaces=")
        ]
        if SIGNATURE_NAMESPACE not in {
            namespace for option in namespace_options for namespace in option.split(",")
        }:
            raise SnapshotAttestationError(
                f"trusted signer {identity} does not allow snapshot namespace"
            )
        fingerprints.add(public_key_fingerprint(f"ssh-ed25519 {fields[key_index + 1]}"))
    if not fingerprints:
        raise SnapshotAttestationError(f"trusted signer identity not found: {identity}")
    return sorted(fingerprints)


def build_snapshot_attestation(
    *,
    manifest: dict[str, Any],
    manifest_sha256: str,
    manifest_url: str,
    snapshot_path: str,
    signer_identity: str,
    public_key: str,
    issued_at: str,
) -> dict[str, Any]:
    digest = _require_sha256(manifest_sha256, "manifest")
    identity = _require_signer_identity(signer_identity)
    normalized_key = normalize_public_key(public_key)
    policy = manifest.get("policy")
    if not isinstance(policy, dict) or any(
        policy.get(key) is not True for key in REQUIRED_PUBLIC_DATA_POLICY
    ):
        raise SnapshotAttestationError(
            "manifest is missing mandatory real/public-data policy"
        )
    artifact_contract = manifest.get("artifact_contract")
    if not isinstance(artifact_contract, dict):
        raise SnapshotAttestationError("manifest has no artifact contract")
    contract_sha256 = _require_sha256(
        artifact_contract.get("sha256"), "artifact contract"
    )
    schema_version = str(manifest.get("schema_version") or "").strip()
    contract_schema_version = str(artifact_contract.get("schema_version") or "").strip()
    snapshot_date = str(manifest.get("snapshot_date") or "").strip()
    if not schema_version or not contract_schema_version or not snapshot_date:
        raise SnapshotAttestationError(
            "manifest is missing schema or snapshot version stamps"
        )
    if not manifest_url.startswith("https://"):
        raise SnapshotAttestationError("manifest URL must use HTTPS")
    if (
        not snapshot_path.startswith("scale/snapshots/")
        or ".." in Path(snapshot_path).parts
    ):
        raise SnapshotAttestationError("unsafe immutable snapshot path")
    summary = manifest.get("summary")
    if not isinstance(summary, dict):
        raise SnapshotAttestationError("manifest has no summary")

    return {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "project": "vota-con-la-chola",
        "predicate_type": "https://votaconlachola.org/schemas/snapshot-attestation/v1",
        "issued_at": issued_at,
        "subject": {
            "name": "scale-origin-manifest",
            "uri": manifest_url,
            "digest": {"sha256": digest},
            "snapshot_date": snapshot_date,
            "snapshot_path": snapshot_path,
        },
        "build_contract": {
            "manifest_schema_version": schema_version,
            "artifact_contract_schema_version": contract_schema_version,
            "artifact_contract_sha256": contract_sha256,
        },
        "summary": {
            "corpora": int(summary.get("corpora") or 0),
            "rows": int(summary.get("rows") or 0),
            "data_files": int(summary.get("data_files") or 0),
            "data_bytes": int(summary.get("data_bytes") or 0),
            "million_scale_lanes": int(summary.get("million_scale_lanes") or 0),
            "promoted_lanes": int(summary.get("promoted_lanes") or 0),
        },
        "policy": {key: True for key in REQUIRED_PUBLIC_DATA_POLICY},
        "signer": {
            "identity": identity,
            "key_type": "ssh-ed25519",
            "public_key_fingerprint": public_key_fingerprint(normalized_key),
            "signature_namespace": SIGNATURE_NAMESPACE,
        },
        "verification": {
            "algorithm": "ssh-ed25519",
            "canonicalization": "RFC8785-inspired sorted compact JSON plus LF",
            "command": (
                "ssh-keygen -Y verify -f <allowed_signers> -I <identity> "
                f"-n {SIGNATURE_NAMESPACE} -s attestation.json.sig"
            ),
        },
    }


def sign_attestation(
    *, attestation_path: Path, private_key_path: Path, signature_path: Path
) -> None:
    expected_signature = Path(str(attestation_path) + ".sig")
    if expected_signature.exists():
        expected_signature.unlink()
    completed = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "sign",
            "-f",
            str(private_key_path),
            "-n",
            SIGNATURE_NAMESPACE,
            str(attestation_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not expected_signature.is_file():
        detail = completed.stderr.strip() or "ssh-keygen did not create a signature"
        raise SnapshotAttestationError(detail)
    signature_path.parent.mkdir(parents=True, exist_ok=True)
    if signature_path != expected_signature:
        signature_path.write_bytes(expected_signature.read_bytes())
        expected_signature.unlink()


def verify_attestation_signature(
    *,
    attestation_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    signer_identity: str,
) -> str:
    identity = _require_signer_identity(signer_identity)
    completed = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(allowed_signers_path),
            "-I",
            identity,
            "-n",
            SIGNATURE_NAMESPACE,
            "-s",
            str(signature_path),
        ],
        input=attestation_path.read_bytes(),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SnapshotAttestationError(
            detail or "snapshot signature verification failed"
        )
    return completed.stdout.decode("utf-8", errors="replace").strip()


def create_signed_attestation(
    *,
    manifest_path: Path,
    manifest_url: str,
    snapshot_path: str,
    private_key_path: Path,
    signer_identity: str,
    issued_at: str,
    out_dir: Path,
) -> dict[str, Any]:
    manifest = load_json_object(manifest_path)
    public_key = derive_public_key(private_key_path)
    manifest_sha256 = sha256_file(manifest_path)
    attestation = build_snapshot_attestation(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        manifest_url=manifest_url,
        snapshot_path=snapshot_path,
        signer_identity=signer_identity,
        public_key=public_key,
        issued_at=issued_at,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    attestation_path = out_dir / "attestation.json"
    signature_path = out_dir / "attestation.json.sig"
    public_key_path = out_dir / "signing-key.pub"
    allowed_signers_path = out_dir / "allowed_signers"
    write_json_canonical(attestation_path, attestation)
    public_key_path.write_text(public_key, encoding="utf-8")
    allowed_signers_path.write_text(
        allowed_signers_line(
            signer_identity=signer_identity,
            public_key=public_key,
        ),
        encoding="utf-8",
    )
    sign_attestation(
        attestation_path=attestation_path,
        private_key_path=private_key_path,
        signature_path=signature_path,
    )
    verification_output = verify_attestation_signature(
        attestation_path=attestation_path,
        signature_path=signature_path,
        allowed_signers_path=allowed_signers_path,
        signer_identity=signer_identity,
    )
    return {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "status": "signed_and_verified",
        "manifest_sha256": manifest_sha256,
        "artifact_contract_sha256": attestation["build_contract"][
            "artifact_contract_sha256"
        ],
        "attestation_sha256": sha256_file(attestation_path),
        "signature_sha256": sha256_file(signature_path),
        "public_key_fingerprint": attestation["signer"]["public_key_fingerprint"],
        "signer_identity": signer_identity,
        "signature_namespace": SIGNATURE_NAMESPACE,
        "verification_output": verification_output,
        "files": {
            "attestation": attestation_path.name,
            "signature": signature_path.name,
            "public_key": public_key_path.name,
            "allowed_signers": allowed_signers_path.name,
        },
    }


def verify_signed_attestation(
    *,
    manifest_path: Path,
    attestation_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    signer_identity: str,
    expected_manifest_url: str | None = None,
    expected_snapshot_path: str | None = None,
    expected_snapshot_date: str | None = None,
    discovery_public_key_path: Path | None = None,
) -> dict[str, Any]:
    manifest = load_json_object(manifest_path)
    attestation = load_json_object(attestation_path)
    errors: list[str] = []
    manifest_sha256 = sha256_file(manifest_path)
    if attestation.get("schema_version") != ATTESTATION_SCHEMA_VERSION:
        errors.append("unsupported attestation schema version")
    subject = attestation.get("subject")
    declared_manifest_sha256 = ""
    if isinstance(subject, dict) and isinstance(subject.get("digest"), dict):
        declared_manifest_sha256 = str(subject["digest"].get("sha256") or "")
    if declared_manifest_sha256 != manifest_sha256:
        errors.append("attested manifest checksum does not match downloaded manifest")
    if not isinstance(subject, dict):
        subject = {}
        errors.append("attestation subject is missing")
    if subject.get("name") != "scale-origin-manifest":
        errors.append("attestation subject name is invalid")
    if (
        expected_manifest_url is not None
        and subject.get("uri") != expected_manifest_url
    ):
        errors.append("attested manifest URL does not match selected release")
    if (
        expected_snapshot_path is not None
        and subject.get("snapshot_path") != expected_snapshot_path
    ):
        errors.append("attested snapshot path does not match selected release")
    manifest_snapshot_date = str(manifest.get("snapshot_date") or "")
    if subject.get("snapshot_date") != manifest_snapshot_date:
        errors.append("attested snapshot date does not match manifest")
    if (
        expected_snapshot_date is not None
        and subject.get("snapshot_date") != expected_snapshot_date
    ):
        errors.append("attested snapshot date does not match selected release")
    artifact_contract = manifest.get("artifact_contract")
    build_contract = attestation.get("build_contract")
    if not isinstance(artifact_contract, dict) or not isinstance(build_contract, dict):
        errors.append("artifact contract is missing")
    elif artifact_contract.get("sha256") != build_contract.get(
        "artifact_contract_sha256"
    ):
        errors.append("attested artifact contract does not match manifest")
    if isinstance(artifact_contract, dict) and isinstance(build_contract, dict):
        if build_contract.get("manifest_schema_version") != manifest.get(
            "schema_version"
        ):
            errors.append("attested manifest schema does not match manifest")
        if build_contract.get(
            "artifact_contract_schema_version"
        ) != artifact_contract.get("schema_version"):
            errors.append("attested artifact contract schema does not match manifest")
    attestation_policy = attestation.get("policy")
    manifest_policy = manifest.get("policy")
    if not isinstance(attestation_policy, dict) or any(
        attestation_policy.get(key) is not True for key in REQUIRED_PUBLIC_DATA_POLICY
    ):
        errors.append("attestation is missing mandatory real/public-data policy")
    if not isinstance(manifest_policy, dict) or any(
        manifest_policy.get(key) is not True for key in REQUIRED_PUBLIC_DATA_POLICY
    ):
        errors.append("manifest is missing mandatory real/public-data policy")
    manifest_summary = manifest.get("summary")
    attestation_summary = attestation.get("summary")
    summary_keys = (
        "corpora",
        "rows",
        "data_files",
        "data_bytes",
        "million_scale_lanes",
        "promoted_lanes",
    )
    if not isinstance(manifest_summary, dict) or not isinstance(
        attestation_summary, dict
    ):
        errors.append("attestation or manifest summary is missing")
    elif any(
        int(attestation_summary.get(key) or 0) != int(manifest_summary.get(key) or 0)
        for key in summary_keys
    ):
        errors.append("attested summary does not match manifest")
    signer = attestation.get("signer")
    if not isinstance(signer, dict) or signer.get("identity") != signer_identity:
        errors.append("attestation signer identity does not match trusted identity")
        signer = {}
    if signer.get("key_type") != "ssh-ed25519":
        errors.append("attestation signer key type is unsupported")
    if signer.get("signature_namespace") != SIGNATURE_NAMESPACE:
        errors.append("attestation signature namespace is invalid")
    claimed_fingerprint = str(signer.get("public_key_fingerprint") or "")
    trusted_fingerprints: list[str] = []
    try:
        trusted_fingerprints = trusted_public_key_fingerprints(
            allowed_signers_path=allowed_signers_path,
            signer_identity=signer_identity,
        )
        if claimed_fingerprint not in trusted_fingerprints:
            errors.append("attestation key fingerprint is not independently trusted")
    except (OSError, SnapshotAttestationError) as exc:
        errors.append(f"trusted signer policy failed: {exc}")
    discovery_fingerprint = ""
    if discovery_public_key_path is not None:
        try:
            discovery_fingerprint = public_key_fingerprint(
                discovery_public_key_path.read_text(encoding="utf-8")
            )
            if discovery_fingerprint != claimed_fingerprint:
                errors.append("published discovery key differs from attested signer")
            if discovery_fingerprint not in trusted_fingerprints:
                errors.append("published discovery key is not independently trusted")
        except (OSError, SnapshotAttestationError) as exc:
            errors.append(f"published discovery key validation failed: {exc}")
    signature_verified = False
    verification_output = ""
    try:
        verification_output = verify_attestation_signature(
            attestation_path=attestation_path,
            signature_path=signature_path,
            allowed_signers_path=allowed_signers_path,
            signer_identity=signer_identity,
        )
        signature_verified = True
        verified_fingerprint_match = re.search(
            r"\bkey (SHA256:[A-Za-z0-9+/]+)", verification_output
        )
        if verified_fingerprint_match is None:
            errors.append("verified signing-key fingerprint is unavailable")
        elif verified_fingerprint_match.group(1) != claimed_fingerprint:
            errors.append("verified signing key differs from attested fingerprint")
    except (OSError, SnapshotAttestationError) as exc:
        errors.append(f"signature verification failed: {exc}")
    return {
        "schema_version": "vclc_snapshot_attestation_verification_v1",
        "status": "ok" if not errors else "error",
        "passed": not errors,
        "errors": errors,
        "checks": {
            "manifest_sha256": manifest_sha256,
            "attestation_sha256": sha256_file_or_empty(attestation_path),
            "signature_sha256": sha256_file_or_empty(signature_path),
            "signature_verified": signature_verified,
            "signer_identity": signer_identity,
            "trusted_public_key_fingerprints": trusted_fingerprints,
            "attested_public_key_fingerprint": claimed_fingerprint,
            "discovery_public_key_fingerprint": discovery_fingerprint,
            "signature_namespace": SIGNATURE_NAMESPACE,
            "subject_manifest_url": subject.get("uri"),
            "subject_snapshot_path": subject.get("snapshot_path"),
            "subject_snapshot_date": subject.get("snapshot_date"),
            "verification_output": verification_output,
            "official_real_records_only": isinstance(manifest_policy, dict)
            and manifest_policy.get("official_real_records_only") is True,
            "synthetic_or_mock_records": False,
            "official_public_domain_personal_information_retained": isinstance(
                manifest_policy, dict
            )
            and manifest_policy.get(
                "official_public_domain_personal_information_retained"
            )
            is True,
        },
    }


def _normalized_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise SnapshotAttestationError("scale manifest has no files array")
    normalized: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict):
            raise SnapshotAttestationError("scale manifest contains a non-object file")
        path = str(item.get("path") or "")
        sha256 = _require_sha256(item.get("sha256"), f"file {path}")
        if not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise SnapshotAttestationError(f"unsafe manifest file path: {path!r}")
        normalized.append(
            {
                "path": path,
                "sha256": sha256,
                "bytes": int(item.get("bytes") or 0),
                "kind": str(item.get("kind") or ""),
                "corpus_id": str(item.get("corpus_id") or ""),
            }
        )
    normalized.sort(key=lambda item: item["path"])
    if any(
        normalized[index - 1]["path"] == normalized[index]["path"]
        for index in range(1, len(normalized))
    ):
        raise SnapshotAttestationError("scale manifest contains duplicate file paths")
    return normalized


def diff_scale_manifests(
    *,
    before_path: Path,
    after_path: Path,
    max_samples: int = 25,
) -> dict[str, Any]:
    if max_samples < 0:
        raise SnapshotAttestationError("max_samples must be non-negative")
    before = load_json_object(before_path)
    after = load_json_object(after_path)
    before_files = _normalized_files(before)
    after_files = _normalized_files(after)
    added = removed = changed = unchanged = 0
    samples: dict[str, list[Any]] = {"added": [], "removed": [], "changed": []}
    before_bytes = sum(item["bytes"] for item in before_files)
    after_bytes = sum(item["bytes"] for item in after_files)
    left = right = 0
    while left < len(before_files) or right < len(after_files):
        if left >= len(before_files):
            item = after_files[right]
            added += 1
            if len(samples["added"]) < max_samples:
                samples["added"].append(item["path"])
            right += 1
            continue
        if right >= len(after_files):
            item = before_files[left]
            removed += 1
            if len(samples["removed"]) < max_samples:
                samples["removed"].append(item["path"])
            left += 1
            continue
        before_item = before_files[left]
        after_item = after_files[right]
        if before_item["path"] < after_item["path"]:
            removed += 1
            if len(samples["removed"]) < max_samples:
                samples["removed"].append(before_item["path"])
            left += 1
        elif after_item["path"] < before_item["path"]:
            added += 1
            if len(samples["added"]) < max_samples:
                samples["added"].append(after_item["path"])
            right += 1
        else:
            if (
                before_item["sha256"] == after_item["sha256"]
                and before_item["bytes"] == after_item["bytes"]
            ):
                unchanged += 1
            else:
                changed += 1
                if len(samples["changed"]) < max_samples:
                    samples["changed"].append(
                        {
                            "path": before_item["path"],
                            "before_sha256": before_item["sha256"],
                            "after_sha256": after_item["sha256"],
                            "before_bytes": before_item["bytes"],
                            "after_bytes": after_item["bytes"],
                        }
                    )
            left += 1
            right += 1

    before_contract = before.get("artifact_contract")
    after_contract = after.get("artifact_contract")
    before_contract_sha = (
        str(before_contract.get("sha256") or "")
        if isinstance(before_contract, dict)
        else ""
    )
    after_contract_sha = (
        str(after_contract.get("sha256") or "")
        if isinstance(after_contract, dict)
        else ""
    )
    before_corpora = {
        str(item.get("id") or ""): item
        for item in before.get("corpora", [])
        if isinstance(item, dict) and item.get("id")
    }
    after_corpora = {
        str(item.get("id") or ""): item
        for item in after.get("corpora", [])
        if isinstance(item, dict) and item.get("id")
    }
    corpus_added = sorted(set(after_corpora) - set(before_corpora))
    corpus_removed = sorted(set(before_corpora) - set(after_corpora))
    corpus_changed = []
    corpus_unchanged = []
    for corpus_id in sorted(set(before_corpora) & set(after_corpora)):
        before_item = before_corpora[corpus_id]
        after_item = after_corpora[corpus_id]
        keys = ("kind", "rows", "files", "bytes", "source_ids", "official_hosts")
        if any(before_item.get(key) != after_item.get(key) for key in keys):
            corpus_changed.append(corpus_id)
        else:
            corpus_unchanged.append(corpus_id)

    before_policy = before.get("policy")
    after_policy = after.get("policy")
    policy_ok = all(
        isinstance(policy, dict)
        and all(policy.get(key) is True for key in REQUIRED_PUBLIC_DATA_POLICY)
        for policy in (before_policy, after_policy)
    )
    return {
        "schema_version": DIFF_SCHEMA_VERSION,
        "status": "ok",
        "before": {
            "path": before_path.name,
            "manifest_sha256": sha256_file(before_path),
            "schema_version": before.get("schema_version"),
            "artifact_contract_sha256": before_contract_sha,
            "snapshot_date": before.get("snapshot_date"),
        },
        "after": {
            "path": after_path.name,
            "manifest_sha256": sha256_file(after_path),
            "schema_version": after.get("schema_version"),
            "artifact_contract_sha256": after_contract_sha,
            "snapshot_date": after.get("snapshot_date"),
        },
        "artifact_contract_changed": before_contract_sha != after_contract_sha,
        "files": {
            "before_total": len(before_files),
            "after_total": len(after_files),
            "unchanged": unchanged,
            "added": added,
            "removed": removed,
            "changed": changed,
            "before_bytes": before_bytes,
            "after_bytes": after_bytes,
            "bytes_delta": after_bytes - before_bytes,
            "samples": samples,
        },
        "corpora": {
            "before_total": len(before_corpora),
            "after_total": len(after_corpora),
            "unchanged": corpus_unchanged,
            "added": corpus_added,
            "removed": corpus_removed,
            "changed": corpus_changed,
        },
        "policy": {
            "official_real_records_only": policy_ok,
            "synthetic_or_mock_records": False,
            "official_public_domain_personal_information_retained": policy_ok,
        },
    }
