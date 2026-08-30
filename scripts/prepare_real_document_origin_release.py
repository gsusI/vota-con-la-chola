#!/usr/bin/env python3
"""Prepare an exact append-only public release for the real document-origin packs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.object_store import hash_file
from publicdata_docs.generation_manifest import (
    iter_generation_rows,
    lifecycle_roots,
    load_index_bytes,
    sha256_file,
)
from scripts.pack_real_document_origin import DATASET as PACK_DATASET
from scripts.pack_real_document_origin import ROW_SCHEMA as PACK_ROW_SCHEMA
from scripts.replicate_real_document_origin import DATASET as ORIGIN_DATASET
from scripts.replicate_real_document_origin import utc_now

RELEASE_SCHEMA = "real_document_origin_release_manifest_v1"
UPLOAD_PLAN_SCHEMA = "real_document_origin_upload_plan_v1"
POINTER_SCHEMA = "real_document_origin_release_pointer_v1"
REPORT_SCHEMA = "real_document_origin_release_preparation_v1"
REMOTE_ROOT = "document-origin"


class ReleasePreparationError(RuntimeError):
    """Raised when the exact local real-object generation is not release-ready."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin-manifest",
        default="etl/data/manifests/real-document-origin-replicas.json",
    )
    parser.add_argument(
        "--origin-audit",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-generation-audit.json"
        ),
    )
    parser.add_argument(
        "--pack-manifest",
        default="etl/data/manifests/real-document-origin-packs.json",
    )
    parser.add_argument(
        "--pack-root", default="etl/data/object-origin-packs/real-document-corpus-v1"
    )
    parser.add_argument(
        "--pack-audit",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-pack-generation-audit.json"
        ),
    )
    parser.add_argument(
        "--release-manifest-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-release-manifest.json"
        ),
    )
    parser.add_argument(
        "--upload-plan-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-upload-plan.json"
        ),
    )
    parser.add_argument(
        "--pointer-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-release-latest.json"
        ),
    )
    parser.add_argument(
        "--report-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-release-preparation.json"
        ),
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def repo_path(value: str) -> Path:
    relative = Path(str(value or "").strip())
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise ReleasePreparationError(f"unsafe repository path: {value!r}")
    candidate = (REPO_ROOT / relative).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ReleasePreparationError(f"repository path escapes root: {value}") from exc
    return candidate


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ReleasePreparationError("release source escapes repository") from exc


def safe_relative(value: str, label: str) -> str:
    relative = Path(str(value or "").strip())
    if (
        not str(relative)
        or relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
    ):
        raise ReleasePreparationError(f"unsafe {label}: {value!r}")
    return relative.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleasePreparationError(f"cannot load {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleasePreparationError(f"JSON root is not an object: {path.name}")
    return payload


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def inventory_identity(files: list[dict[str, Any]]) -> str:
    contract = [
        {
            "release_path": item["release_path"],
            "bytes": item["bytes"],
            "sha256": item["sha256"],
            "kind": item["kind"],
        }
        for item in files
    ]
    encoded = json.dumps(
        contract, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ReleaseInventory:
    def __init__(self) -> None:
        self.files: list[dict[str, Any]] = []
        self._release_paths: set[str] = set()
        self._source_paths: set[str] = set()

    def add(
        self,
        *,
        source: Path,
        release_path: str,
        kind: str,
        expected_sha256: str | None = None,
        expected_bytes: int | None = None,
    ) -> None:
        release_path = safe_relative(release_path, "release path")
        source_path = display_path(source)
        if release_path in self._release_paths:
            raise ReleasePreparationError(f"duplicate release path: {release_path}")
        if source_path in self._source_paths:
            raise ReleasePreparationError(f"duplicate release source: {source_path}")
        if not source.is_file():
            raise ReleasePreparationError(f"release source is missing: {source_path}")
        actual_sha256, actual_bytes = hash_file(source)
        if expected_sha256 is not None and actual_sha256 != expected_sha256:
            raise ReleasePreparationError(
                f"release source checksum drifted: {source_path}"
            )
        if expected_bytes is not None and actual_bytes != int(expected_bytes):
            raise ReleasePreparationError(
                f"release source bytes drifted: {source_path}"
            )
        self.files.append(
            {
                "source_path": source_path,
                "release_path": release_path,
                "bytes": actual_bytes,
                "sha256": actual_sha256,
                "kind": kind,
            }
        )
        self._release_paths.add(release_path)
        self._source_paths.add(source_path)

    def sorted(self) -> list[dict[str, Any]]:
        return sorted(self.files, key=lambda item: item["release_path"])


def add_lifecycle(
    inventory: ReleaseInventory,
    *,
    manifest_path: Path,
    audit_path: Path,
    dataset: str,
    release_prefix: str,
) -> dict[str, int]:
    audit = load_json(audit_path)
    active_bytes = manifest_path.read_bytes()
    active_sha256 = hashlib.sha256(active_bytes).hexdigest()
    active_index = load_index_bytes(active_bytes, dataset=dataset)
    audit_input = audit.get("input") or {}
    checks = audit.get("checks") or {}
    if (
        audit.get("schema_version") != "real_document_generation_lifecycle_audit_v1"
        or audit.get("status") != "ok"
        or audit.get("dataset") != dataset
        or not checks
        or not all(value is True for value in checks.values())
        or audit_input.get("sha256") != active_sha256
        or audit_input.get("bytes") != len(active_bytes)
        or audit_input.get("logical_sha256") != active_index.get("logical_sha256")
    ):
        raise ReleasePreparationError(f"{dataset} lifecycle audit drifted")
    chain = audit.get("activation_chain")
    if not isinstance(chain, list) or not chain or chain[0] != active_sha256:
        raise ReleasePreparationError(f"{dataset} activation chain drifted")
    generation_root, history_root, receipt_root, state_root = lifecycle_roots(
        manifest_path
    )
    inventory.add(
        source=manifest_path,
        release_path=f"{release_prefix}/live-index.json",
        kind=f"{dataset}_live_index",
        expected_sha256=active_sha256,
        expected_bytes=len(active_bytes),
    )
    shards = states = 0
    for manifest_sha256 in chain:
        manifest_sha256 = str(manifest_sha256)
        history = history_root / f"{manifest_sha256}.json"
        receipt = receipt_root / f"{manifest_sha256}.json"
        archived_bytes = history.read_bytes()
        if hashlib.sha256(archived_bytes).hexdigest() != manifest_sha256:
            raise ReleasePreparationError(f"{dataset} history checksum drifted")
        index = load_index_bytes(archived_bytes, dataset=dataset)
        logical_sha256 = str(index["logical_sha256"])
        inventory.add(
            source=history,
            release_path=f"{release_prefix}/history/{history.name}",
            kind=f"{dataset}_history_index",
            expected_sha256=manifest_sha256,
        )
        receipt_payload = load_json(receipt)
        if receipt_payload.get("active_manifest_sha256") != manifest_sha256:
            raise ReleasePreparationError(f"{dataset} receipt identity drifted")
        inventory.add(
            source=receipt,
            release_path=f"{release_prefix}/receipts/{receipt.name}",
            kind=f"{dataset}_activation_receipt",
        )
        for partition in index.get("partitions") or []:
            if not isinstance(partition, dict):
                raise ReleasePreparationError(f"{dataset} partition descriptor drifted")
            source = (manifest_path.parent / str(partition["path"])).resolve()
            try:
                source.relative_to(generation_root.resolve())
            except ValueError as exc:
                raise ReleasePreparationError(
                    f"{dataset} generation shard escapes root"
                ) from exc
            inventory.add(
                source=source,
                release_path=(
                    f"{release_prefix}/generations/{logical_sha256}/{source.name}"
                ),
                kind=f"{dataset}_generation_shard",
                expected_sha256=str(partition["sha256"]),
                expected_bytes=int(partition["bytes"]),
            )
            shards += 1
        state = receipt_payload.get("state_snapshot") or {}
        state_source = (manifest_path.parent / str(state.get("path") or "")).resolve()
        try:
            state_source.relative_to(state_root.resolve())
        except ValueError as exc:
            raise ReleasePreparationError(f"{dataset} state escapes root") from exc
        inventory.add(
            source=state_source,
            release_path=f"{release_prefix}/state/{state_source.name}",
            kind=f"{dataset}_state_snapshot",
            expected_sha256=str(state["compressed_sha256"]),
            expected_bytes=int(state["compressed_bytes"]),
        )
        states += 1
    return {"manifests": len(chain), "shards": shards, "state_snapshots": states}


def prepare_release(args: argparse.Namespace) -> dict[str, Any]:
    origin_manifest = repo_path(args.origin_manifest)
    pack_manifest = repo_path(args.pack_manifest)
    pack_root = repo_path(args.pack_root)
    origin_audit = repo_path(args.origin_audit)
    pack_audit = repo_path(args.pack_audit)
    release_manifest_out = repo_path(args.release_manifest_out)
    upload_plan_out = repo_path(args.upload_plan_out)
    pointer_out = repo_path(args.pointer_out)
    report_out = repo_path(args.report_out)
    pack_index = load_index_bytes(pack_manifest.read_bytes(), dataset=PACK_DATASET)
    origin_index = load_index_bytes(
        origin_manifest.read_bytes(), dataset=ORIGIN_DATASET
    )
    origin_manifest_sha256 = sha256_file(origin_manifest)
    pack_manifest_sha256 = sha256_file(pack_manifest)
    inventory = ReleaseInventory()
    packs = objects = payload_bytes = archive_bytes = member_manifest_bytes = 0
    for descriptor in iter_generation_rows(
        pack_manifest,
        dataset=PACK_DATASET,
        row_schema_version=PACK_ROW_SCHEMA,
        allow_legacy_jsonl=False,
    ):
        if descriptor.get("synthetic_or_mock") is not False:
            raise ReleasePreparationError("pack manifest contains non-real descriptor")
        if descriptor.get("source_origin_manifest_sha256") != origin_manifest_sha256:
            raise ReleasePreparationError("pack descriptor source generation drifted")
        archive_relative = safe_relative(
            str(descriptor["archive_path"]), "pack archive path"
        )
        member_relative = safe_relative(
            str(descriptor["member_manifest_path"]), "member manifest path"
        )
        inventory.add(
            source=(pack_root / archive_relative).resolve(),
            release_path=f"data/{archive_relative}",
            kind="document_object_pack",
            expected_sha256=str(descriptor["archive_sha256"]),
            expected_bytes=int(descriptor["archive_bytes"]),
        )
        inventory.add(
            source=(pack_root / member_relative).resolve(),
            release_path=f"data/{member_relative}",
            kind="document_object_member_manifest",
            expected_sha256=str(descriptor["member_manifest_sha256"]),
            expected_bytes=int(descriptor["member_manifest_bytes"]),
        )
        packs += 1
        objects += int(descriptor["object_count"])
        payload_bytes += int(descriptor["payload_bytes"])
        archive_bytes += int(descriptor["archive_bytes"])
        member_manifest_bytes += int(descriptor["member_manifest_bytes"])
    origin_lifecycle = add_lifecycle(
        inventory,
        manifest_path=origin_manifest,
        audit_path=origin_audit,
        dataset=ORIGIN_DATASET,
        release_prefix="controls/origin",
    )
    pack_lifecycle = add_lifecycle(
        inventory,
        manifest_path=pack_manifest,
        audit_path=pack_audit,
        dataset=PACK_DATASET,
        release_prefix="controls/packs",
    )
    evidence_paths = (
        args.origin_audit,
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-replication.json",
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-clean-restore.json",
        args.pack_audit,
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-packaging.json",
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-origin-pack-validation.json",
    )
    for value in evidence_paths:
        source = repo_path(value)
        inventory.add(
            source=source,
            release_path=f"evidence/{source.name}",
            kind="validation_evidence",
        )
    files = inventory.sorted()
    release_id = inventory_identity(files)
    release_prefix = (
        f"{REMOTE_ROOT}/snapshots/{origin_manifest_sha256}/"
        f"{pack_manifest_sha256}/{release_id}"
    )
    release_manifest = {
        "schema_version": RELEASE_SCHEMA,
        "project": "vota-con-la-chola",
        "release_id": release_id,
        "release_prefix": release_prefix,
        "source_origin_manifest": {
            "sha256": origin_manifest_sha256,
            "logical_sha256": origin_index["logical_sha256"],
        },
        "pack_manifest": {
            "sha256": pack_manifest_sha256,
            "logical_sha256": pack_index["logical_sha256"],
        },
        "summary": {
            "packs": packs,
            "objects": objects,
            "payload_bytes": payload_bytes,
            "archive_bytes": archive_bytes,
            "member_manifest_bytes": member_manifest_bytes,
            "release_files": len(files),
            "release_bytes": sum(int(item["bytes"]) for item in files),
        },
        "lifecycle": {"origin": origin_lifecycle, "packs": pack_lifecycle},
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_forbidden": True,
            "official_public_domain_personal_information_retained": True,
            "append_only_immutable_release": True,
            "automatic_deletion_forbidden": True,
            "latest_pointer_activated_last": True,
        },
        "files": [
            {key: item[key] for key in ("release_path", "bytes", "sha256", "kind")}
            for item in files
        ],
    }
    release_manifest_bytes = canonical_bytes(release_manifest)
    release_manifest_sha256 = hashlib.sha256(release_manifest_bytes).hexdigest()
    pointer = {
        "schema_version": POINTER_SCHEMA,
        "project": "vota-con-la-chola",
        "release_id": release_id,
        "release_prefix": release_prefix,
        "release_manifest_path": f"{release_prefix}/release-manifest.json",
        "release_manifest_sha256": release_manifest_sha256,
        "source_origin_manifest_sha256": origin_manifest_sha256,
        "pack_manifest_sha256": pack_manifest_sha256,
        "packs": packs,
        "objects": objects,
        "payload_bytes": payload_bytes,
        "updated_at": load_json(
            repo_path(
                "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
                "real-document-origin-packaging.json"
            )
        ).get("generated_at"),
        "policy": {
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock_records_counted": False,
            "immutable_release_files": True,
            "pointer_activated_after_remote_parity": True,
        },
    }
    pointer_bytes = canonical_bytes(pointer)
    atomic_write(release_manifest_out, release_manifest_bytes)
    atomic_write(pointer_out, pointer_bytes)
    upload_plan = {
        "schema_version": UPLOAD_PLAN_SCHEMA,
        "release_id": release_id,
        "release_prefix": release_prefix,
        "immutable_files": files,
        "release_manifest": {
            "source_path": display_path(release_manifest_out),
            "remote_path": f"{release_prefix}/release-manifest.json",
            "bytes": len(release_manifest_bytes),
            "sha256": release_manifest_sha256,
        },
        "latest_pointer": {
            "source_path": display_path(pointer_out),
            "remote_path": f"{REMOTE_ROOT}/latest.json",
            "bytes": len(pointer_bytes),
            "sha256": hashlib.sha256(pointer_bytes).hexdigest(),
        },
        "policy": {
            "append_only": True,
            "delete_operations_forbidden": True,
            "immutable_manifest_uploaded_after_data": True,
            "latest_pointer_uploaded_last": True,
            "resume_requires_remote_checksum_parity": True,
        },
    }
    atomic_write(upload_plan_out, canonical_bytes(upload_plan))
    report = {
        "schema_version": REPORT_SCHEMA,
        "generated_at": utc_now(),
        "status": "ready_for_authorized_publication",
        "authorized": False,
        "remote_preflight_performed": False,
        "remote_publication_performed": False,
        "durable_public_origin_proven": False,
        "independent_remote_restore_proven": False,
        "release_id": release_id,
        "release_prefix": release_prefix,
        "summary": release_manifest["summary"],
        "release_manifest": {
            "path": display_path(release_manifest_out),
            "bytes": len(release_manifest_bytes),
            "sha256": release_manifest_sha256,
        },
        "upload_plan": {
            "path": display_path(upload_plan_out),
            "bytes": upload_plan_out.stat().st_size,
            "sha256": sha256_file(upload_plan_out),
        },
        "latest_pointer": {
            "path": display_path(pointer_out),
            "bytes": len(pointer_bytes),
            "sha256": hashlib.sha256(pointer_bytes).hexdigest(),
        },
        "checks": {
            "exact_source_origin_generation_bound": True,
            "exact_pack_generation_bound": True,
            "all_pack_and_control_files_rehashed": True,
            "release_inventory_paths_unique": True,
            "release_identity_content_addressed": True,
            "append_only_no_delete_contract": True,
            "official_public_domain_personal_information_retained": True,
            "no_synthetic_or_mock_records": True,
            "no_remote_mutation_claimed": True,
        },
        "policy": release_manifest["policy"],
        "next_action": (
            "Run the publisher dry-run and read-only remote preflight. After explicit "
            "release authority, upload immutable files, upload the release manifest, "
            "verify exact remote parity, and move the latest pointer last."
        ),
    }
    atomic_write(
        report_out,
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8")
        + b"\n",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = prepare_release(args)
    except (OSError, ReleasePreparationError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.enforce and report["status"] != "ready_for_authorized_publication":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
