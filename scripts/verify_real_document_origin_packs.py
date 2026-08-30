#!/usr/bin/env python3
"""Fully rehash every object inside the deterministic real-document origin packs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, BinaryIO

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.generation_manifest import (
    iter_generation_rows,
    load_index_bytes,
    sha256_file,
)
from scripts.pack_real_document_origin import DATASET, MEMBER_SCHEMA, ROW_SCHEMA
from scripts.replicate_real_document_origin import safe_child, utc_now


class PackVerificationError(RuntimeError):
    """Raised when a pack or one of its real objects cannot be reconstructed."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", default="etl/data/manifests/real-document-origin-packs.json"
    )
    parser.add_argument(
        "--pack-root", default="etl/data/object-origin-packs/real-document-corpus-v1"
    )
    parser.add_argument("--max-object-bytes", type=int, default=2 * 1024**3)
    parser.add_argument(
        "--report-out",
        default=(
            "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "real-document-origin-pack-validation.json"
        ),
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def read_exact_hash(handle: BinaryIO, *, expected_bytes: int, max_bytes: int) -> str:
    if expected_bytes < 0 or expected_bytes > max_bytes:
        raise PackVerificationError("pack member violates object byte ceiling")
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = handle.read(min(1024 * 1024, expected_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > expected_bytes or total > max_bytes:
            raise PackVerificationError("pack member exceeds declared bytes")
        digest.update(chunk)
    if total != expected_bytes:
        raise PackVerificationError("pack member byte count drifted")
    return digest.hexdigest()


def iter_member_manifest(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PackVerificationError(
                    f"member manifest JSON drifted at line {line_no}"
                ) from exc
            if (
                not isinstance(row, dict)
                or row.get("schema_version") != MEMBER_SCHEMA
                or row.get("official_public_domain_personal_information_retained")
                is not True
                or row.get("synthetic_or_mock") is not False
            ):
                raise PackVerificationError("member manifest policy drifted")
            yield row


def verify_pack(
    descriptor: dict[str, Any], *, pack_root: Path, max_object_bytes: int
) -> dict[str, Any]:
    archive_path = safe_child(pack_root, str(descriptor["archive_path"]))
    member_manifest_path = safe_child(
        pack_root, str(descriptor["member_manifest_path"])
    )
    if (
        not archive_path.is_file()
        or archive_path.stat().st_size != int(descriptor["archive_bytes"])
        or sha256_file(archive_path) != descriptor["archive_sha256"]
        or not member_manifest_path.is_file()
        or member_manifest_path.stat().st_size
        != int(descriptor["member_manifest_bytes"])
        or sha256_file(member_manifest_path) != descriptor["member_manifest_sha256"]
    ):
        raise PackVerificationError("pack artifact checksum or byte count drifted")

    objects = payload_bytes = 0
    by_class: dict[str, int] = {}
    logical_digest = hashlib.sha256()
    previous_member_no = -1
    with tarfile.open(archive_path, mode="r|gz") as archive:
        for row in iter_member_manifest(member_manifest_path):
            encoded = (
                json.dumps(
                    row, ensure_ascii=True, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            ).encode("utf-8")
            logical_digest.update(encoded)
            member = archive.next()
            if member is None or not member.isfile():
                raise PackVerificationError("pack archive member inventory drifted")
            member_no = int(row["member_no"])
            if (
                int(row["pack_no"]) != int(descriptor["pack_no"])
                or member_no != previous_member_no + 1
                or member.name != row["member_name"]
                or member.size != int(row["bytes"])
            ):
                raise PackVerificationError("pack member order or identity drifted")
            source = archive.extractfile(member)
            if source is None:
                raise PackVerificationError("pack member cannot be restored")
            with source:
                actual_sha256 = read_exact_hash(
                    source,
                    expected_bytes=int(row["bytes"]),
                    max_bytes=max_object_bytes,
                )
            if actual_sha256 != row["blob_sha256"]:
                raise PackVerificationError("restored pack member checksum drifted")
            previous_member_no = member_no
            objects += 1
            payload_bytes += int(row["bytes"])
            object_class = str(row["object_class"])
            by_class[object_class] = by_class.get(object_class, 0) + 1
        if archive.next() is not None:
            raise PackVerificationError("pack archive contains undeclared members")
    if (
        objects != int(descriptor["object_count"])
        or payload_bytes != int(descriptor["payload_bytes"])
        or logical_digest.hexdigest() != descriptor["member_manifest_logical_sha256"]
    ):
        raise PackVerificationError("pack logical totals drifted")
    return {"objects": objects, "payload_bytes": payload_bytes, "by_class": by_class}


def verify_all(
    *, manifest: Path, pack_root: Path, max_object_bytes: int
) -> dict[str, Any]:
    index = load_index_bytes(manifest.read_bytes(), dataset=DATASET)
    policy = index.get("policy") or {}
    if (
        policy.get("deterministic_archives") is not True
        or policy.get("pack_rows_and_payload_bytes_bounded") is not True
        or policy.get("exact_origin_generation_bound") is not True
    ):
        raise PackVerificationError("pack generation policy drifted")
    packs = objects = payload_bytes = archive_bytes = member_manifest_bytes = 0
    by_class: dict[str, int] = {}
    source_manifest_sha256 = ""
    previous_pack_no = -1
    for raw_descriptor in iter_generation_rows(
        manifest,
        dataset=DATASET,
        row_schema_version=ROW_SCHEMA,
        allow_legacy_jsonl=False,
    ):
        descriptor = dict(raw_descriptor)
        if (
            descriptor.get("synthetic_or_mock") is not False
            or descriptor.get("official_public_domain_personal_information_retained")
            is not True
        ):
            raise PackVerificationError("pack descriptor policy drifted")
        pack_no = int(descriptor["pack_no"])
        if pack_no != previous_pack_no + 1:
            raise PackVerificationError("pack descriptor order drifted")
        current_source_sha = str(descriptor["source_origin_manifest_sha256"])
        if source_manifest_sha256 and current_source_sha != source_manifest_sha256:
            raise PackVerificationError("pack source generation identity drifted")
        source_manifest_sha256 = current_source_sha
        verified = verify_pack(
            descriptor, pack_root=pack_root, max_object_bytes=max_object_bytes
        )
        packs += 1
        objects += int(verified["objects"])
        payload_bytes += int(verified["payload_bytes"])
        archive_bytes += int(descriptor["archive_bytes"])
        member_manifest_bytes += int(descriptor["member_manifest_bytes"])
        for key, value in verified["by_class"].items():
            by_class[key] = by_class.get(key, 0) + int(value)
        previous_pack_no = pack_no
    if packs < 1 or objects < 1:
        raise PackVerificationError("pack generation is empty")
    return {
        "packs": packs,
        "objects": objects,
        "payload_bytes": payload_bytes,
        "archive_bytes": archive_bytes,
        "member_manifest_bytes": member_manifest_bytes,
        "objects_by_class": by_class,
        "source_origin_manifest_sha256": source_manifest_sha256,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = Path(args.manifest)
    started = time.monotonic()
    try:
        if not manifest.is_file() or int(args.max_object_bytes) < 1:
            raise PackVerificationError(
                "pack manifest and positive object bound required"
            )
        totals = verify_all(
            manifest=manifest,
            pack_root=Path(args.pack_root),
            max_object_bytes=int(args.max_object_bytes),
        )
        report = {
            "schema_version": "real_document_origin_pack_validation_v1",
            "generated_at": utc_now(),
            "status": "ok",
            "durable_public_origin_proven": False,
            "remote_restore_proven": False,
            "remote_publication_performed": False,
            "policy": {
                "official_public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
                "every_packed_object_fully_rehashed": True,
                "immutable_publication_package_only": True,
            },
            "manifest": {
                "path": manifest.name,
                "sha256": sha256_file(manifest),
            },
            "verified": totals,
            "performance": {
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "max_object_bytes": int(args.max_object_bytes),
            },
            "checks": {
                "all_pack_artifacts_rehashed": True,
                "all_members_restored_and_rehashed": True,
                "source_origin_generation_single_and_exact": True,
                "official_public_domain_personal_information_retained": True,
                "no_synthetic_or_mock_records": True,
                "no_remote_publication_or_restore_claimed": True,
            },
            "next_action": (
                "After explicit release authority, upload these immutable packs and exact "
                "control artifacts without deletion, then repeat full verification from an "
                "independent clean machine."
            ),
        }
        write_report(Path(args.report_out), report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        return 0
    except (OSError, PackVerificationError, RuntimeError, tarfile.TarError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
