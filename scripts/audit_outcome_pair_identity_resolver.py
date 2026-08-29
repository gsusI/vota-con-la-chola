#!/usr/bin/env python3
"""Audit real public-name resolution for every C2B Senate action."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.outcome_pair_partitions import (
    EXPECTED_MEMBER_COMPONENT_ROOT_SHA256,
    EXPECTED_SOURCE_COUNTS,
    EXPECTED_SOURCE_DATABASE_SHA256,
)
from publicdata_publish.semantic_contracts import (
    private_token_findings,
    safe_child,
    sha256_file,
)

REPORT_SCHEMA = "outcome_pair_identity_resolver_audit_v1"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _stream_add(digest: Any, value: Any) -> None:
    encoded = _canonical_bytes(value)
    digest.update(struct.pack(">Q", len(encoded)))
    digest.update(encoded)


def _stream_root(contract: str, count: int, digest: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(
            {
                "contract_version": contract,
                "row_count": count,
                "stream_sha256": digest.hexdigest(),
            }
        )
    ).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON root must be an object: {path.name}")
    return payload


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                allow_nan=False,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def audit(args: argparse.Namespace) -> dict[str, Any]:
    plan_db = Path(args.plan_db)
    source_manifest_path = Path(args.source_manifest)
    registry_path = Path(args.registry)
    member_manifest_path = Path(args.member_manifest)
    member_validation_path = Path(args.member_validation)
    shard_root = Path(args.shard_root)
    required = (
        plan_db,
        source_manifest_path,
        registry_path,
        member_manifest_path,
        member_validation_path,
    )
    if any(not path.is_file() for path in required) or not shard_root.is_dir():
        raise FileNotFoundError("one or more identity resolver inputs are missing")
    if sha256_file(plan_db) != EXPECTED_SOURCE_DATABASE_SHA256:
        raise ValueError("C2B plan database differs from pinned real source")

    source_manifest = _load_object(source_manifest_path)
    member_component_root = str(
        source_manifest.get("roots", {})
        .get("input_component_roots", {})
        .get("members", "")
    )
    if member_component_root != EXPECTED_MEMBER_COMPONENT_ROOT_SHA256:
        raise ValueError("C2B member component root drifted")
    registry = _load_object(registry_path)
    entries = [
        item
        for item in list(registry.get("corpora") or [])
        if isinstance(item, dict) and item.get("id") == "member_votes"
    ]
    if len(entries) != 1:
        raise ValueError("member-vote registry entry is missing or duplicated")
    registry_entry = entries[0]
    if not (
        registry_entry.get("durable_public_origin") is True
        and registry_entry.get("clean_room_restore") is True
        and registry_entry.get("manifest")
        == "etl/data/published/member-vote-shard-manifest-latest.json"
        and registry_entry.get("validation")
        == "etl/data/published/member-vote-shard-validation-latest.json"
    ):
        raise ValueError("member-vote durable resolver registry contract failed")

    member_manifest = _load_object(member_manifest_path)
    member_validation = _load_object(member_validation_path)
    manifest_entries = list(member_manifest.get("entries") or [])
    by_action = {
        (str(item["source_id"]), str(item["vote_event_id"])): item
        for item in manifest_entries
    }
    if len(by_action) != len(manifest_entries):
        raise ValueError("member-vote shard manifest has duplicate action keys")
    if not (
        member_manifest.get("schema_version") == "member_vote_event_shards_v1"
        and member_manifest.get("bounded_delivery_gate_passed") is True
        and int(member_manifest.get("events_total") or 0) == 8373
        and int(member_manifest.get("member_votes_total") or 0) == 1809222
        and member_validation.get("schema_version") == "member_vote_shard_validation_v1"
        and member_validation.get("status") == "ok"
        and all(dict(member_validation.get("checks") or {}).values())
    ):
        raise ValueError("member-vote shard evidence has not passed")

    connection = sqlite3.connect(f"file:{plan_db.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        actions = connection.execute(
            "SELECT source_id,action_id,member_vote_count,official_name_count,"
            "participant_projection_sha256 FROM outcome_pair_plan_actions "
            "ORDER BY source_id,action_id"
        )
        action_count = 0
        source_member_votes = 0
        source_official_names = 0
        resolver_member_votes = 0
        resolver_names: set[str] = set()
        missing_actions = 0
        count_mismatches = 0
        private_findings = 0
        action_digest = hashlib.sha256()
        mismatch_digest = hashlib.sha256()
        for row in actions:
            action_count += 1
            key = (str(row["source_id"]), str(row["action_id"]))
            manifest_entry = by_action.get(key)
            if manifest_entry is None:
                missing_actions += 1
                continue
            shard_path = safe_child(shard_root, str(manifest_entry["shard"]))
            if shard_path is None or not shard_path.is_file():
                raise ValueError("member-vote action shard is unsafe or missing")
            if int(shard_path.stat().st_size) != int(
                manifest_entry["shard_bytes"]
            ) or sha256_file(shard_path) != str(manifest_entry["shard_sha256"]):
                raise ValueError("member-vote action shard checksum mismatch")
            with gzip.open(shard_path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                raise TypeError("member-vote action shard root must be an object")
            event = dict(payload.get("event") or {})
            member_votes = list(payload.get("member_votes") or [])
            if (
                event.get("source_id") != key[0]
                or event.get("vote_event_id") != key[1]
                or len(member_votes) != int(manifest_entry["member_votes"])
            ):
                raise ValueError("member-vote action shard identity mismatch")
            for member_vote in member_votes:
                if not isinstance(member_vote, dict):
                    raise TypeError("member-vote row must be an object")
                official_name = str(member_vote.get("member_name") or "").strip()
                member_source = dict(member_vote.get("source") or {})
                if (
                    not official_name
                    or member_source.get("source_id") != key[0]
                    or member_source.get("source_record_id") != key[1]
                ):
                    raise ValueError("member-vote public identity is not resolvable")
                resolver_names.add(official_name)
                private_findings += private_token_findings(member_vote)
            source_count = int(row["member_vote_count"])
            resolver_count = len(member_votes)
            source_member_votes += source_count
            source_official_names += int(row["official_name_count"])
            resolver_member_votes += resolver_count
            coverage_row = {
                "source_id": key[0],
                "action_id": key[1],
                "source_member_vote_count": source_count,
                "source_official_name_count": int(row["official_name_count"]),
                "source_participant_projection_sha256": str(
                    row["participant_projection_sha256"]
                ),
                "resolver_member_vote_count": resolver_count,
                "resolver_shard_sha256": str(manifest_entry["shard_sha256"]),
            }
            _stream_add(action_digest, coverage_row)
            if source_count != resolver_count:
                count_mismatches += 1
                _stream_add(mismatch_digest, coverage_row)
    finally:
        connection.close()

    checks = {
        "exact_real_c2b_actions": action_count == EXPECTED_SOURCE_COUNTS["actions"],
        "all_action_ids_resolved": missing_actions == 0,
        "expected_count_mismatches_preserved": count_mismatches == 64,
        "exact_source_member_vote_rows": source_member_votes
        == EXPECTED_SOURCE_COUNTS["member_votes_source_resolved"],
        "exact_source_official_name_rows": source_official_names
        == EXPECTED_SOURCE_COUNTS["member_votes_source_resolved"],
        "resolver_public_names_present": len(resolver_names) > 0,
        "resolver_member_votes_present": resolver_member_votes > 0,
        "no_private_tokens": private_findings == 0,
        "durable_registry_entry": True,
        "member_vote_manifest_validated": True,
    }
    if not all(checks.values()):
        failed = [key for key, passed in checks.items() if not passed]
        raise RuntimeError("identity resolver audit failed: " + ", ".join(failed))
    return {
        "schema_version": REPORT_SCHEMA,
        "status": "passed",
        "checks": checks,
        "counts": {
            "actions": action_count,
            "missing_actions": missing_actions,
            "count_mismatches": count_mismatches,
            "source_member_votes": source_member_votes,
            "source_official_name_rows": source_official_names,
            "resolver_member_votes": resolver_member_votes,
            "resolver_distinct_official_names": len(resolver_names),
            "private_token_findings": private_findings,
        },
        "roots": {
            "source_database_sha256": EXPECTED_SOURCE_DATABASE_SHA256,
            "source_member_component_root_sha256": member_component_root,
            "registry_sha256": sha256_file(registry_path),
            "registry_entry_sha256": hashlib.sha256(
                _canonical_bytes(registry_entry)
            ).hexdigest(),
            "member_vote_manifest_sha256": sha256_file(member_manifest_path),
            "member_vote_validation_sha256": sha256_file(member_validation_path),
            "action_resolution_root_sha256": _stream_root(
                "outcome_pair_action_identity_resolution_v1",
                action_count,
                action_digest,
            ),
            "count_mismatch_root_sha256": _stream_root(
                "outcome_pair_action_identity_count_mismatch_v1",
                count_mismatches,
                mismatch_digest,
            ),
        },
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_names_retained": True,
            "action_locator_resolved": True,
            "exact_source_participant_projection_resolved": False,
        },
        "artifacts": {
            "plan_database": _repo_path(plan_db),
            "registry": _repo_path(registry_path),
            "member_vote_manifest": _repo_path(member_manifest_path),
            "member_vote_validation": _repo_path(member_validation_path),
            "shard_root": _repo_path(shard_root),
        },
        "limitations": [
            "The durable shard corpus resolves every C2B action and retains exact public names, but 64 action member counts differ from the pinned C2B source.",
            "The pinned C2B member component root remains authoritative for exact participant projection until that exact 119,116-row source is durably restorable.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-db", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--member-manifest", required=True)
    parser.add_argument("--member-validation", required=True)
    parser.add_argument("--shard-root", required=True)
    parser.add_argument("--report-out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_out = Path(args.report_out)
    try:
        report = audit(args)
        _atomic_write(report_out, report)
    except Exception as exc:  # noqa: BLE001 - CLI boundary must persist fail-closed status
        _atomic_write(
            report_out,
            {
                "schema_version": REPORT_SCHEMA,
                "status": "failed",
                "error_code": "outcome_pair_identity_resolver_audit_failed_fail_closed",
                "error_type": type(exc).__name__,
                "success_report_invalidated": True,
                "exact_source_participant_projection_resolved": False,
            },
        )
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            report,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
