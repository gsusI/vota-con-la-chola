#!/usr/bin/env python3
"""Independently validate member-vote shard manifest, bytes, and payload totals."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_large_vote_snapshot import is_public_http_url


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate member-vote event shards")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--shard-root", required=True)
    parser.add_argument("--report-out", default="")
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_shards(manifest_path: Path, *, shard_root: Path) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    entries = list(manifest.get("entries") or [])
    totals = {
        "entries": len(entries),
        "files_present": 0,
        "checksums_valid": 0,
        "payloads_valid": 0,
        "member_votes": 0,
        "member_votes_with_source_record": 0,
        "member_votes_with_public_source_url": 0,
        "payloads_with_private_path_tokens": 0,
        "bytes": 0,
    }
    errors: list[dict[str, object]] = []
    seen_events: set[str] = set()
    for entry in entries:
        event_id = str(entry.get("vote_event_id") or "")
        shard = Path(shard_root) / str(entry.get("shard") or "")
        if not shard.is_file():
            if len(errors) < 20:
                errors.append({"vote_event_id": event_id, "error": "missing_shard"})
            continue
        totals["files_present"] += 1
        size = int(shard.stat().st_size)
        totals["bytes"] += size
        digest = _sha256_file(shard)
        if size != int(entry.get("shard_bytes") or -1) or digest != str(
            entry.get("shard_sha256") or ""
        ):
            if len(errors) < 20:
                errors.append({"vote_event_id": event_id, "error": "bytes_or_checksum"})
            continue
        totals["checksums_valid"] += 1
        try:
            with gzip.open(shard, "rt", encoding="utf-8") as handle:
                item = json.load(handle)
            serialized = json.dumps(item, ensure_ascii=True)
            if any(
                token in serialized
                for token in ("/Users/", "file:///", "/home/", "C:\\\\Users\\\\")
            ):
                totals["payloads_with_private_path_tokens"] += 1
            payload_event_id = str(dict(item.get("event") or {}).get("vote_event_id") or "")
            member_votes = len(list(item.get("member_votes") or []))
            if (
                payload_event_id != event_id
                or member_votes != int(entry["member_votes"])
                or event_id in seen_events
            ):
                raise ValueError("payload identity/count mismatch")
            seen_events.add(event_id)
            totals["member_votes"] += member_votes
            for member in list(item.get("member_votes") or []):
                source = dict(member.get("source") or {})
                if source.get("source_record_pk") is not None and str(
                    source.get("source_record_id") or ""
                ):
                    totals["member_votes_with_source_record"] += 1
                if is_public_http_url(source.get("source_url")):
                    totals["member_votes_with_public_source_url"] += 1
            totals["payloads_valid"] += 1
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if len(errors) < 20:
                errors.append(
                    {
                        "vote_event_id": event_id,
                        "error": f"invalid_payload: {type(exc).__name__}",
                    }
                )
    checks = {
        "all_files_present": totals["files_present"] == len(entries),
        "all_checksums_valid": totals["checksums_valid"] == len(entries),
        "all_payloads_valid": totals["payloads_valid"] == len(entries),
        "event_total_matches": len(entries) == int(manifest.get("events_total") or -1),
        "member_vote_total_matches": totals["member_votes"]
        == int(manifest.get("member_votes_total") or -1),
        "shard_byte_total_matches": totals["bytes"]
        == int(manifest.get("shard_bytes_total") or -1),
        "member_source_record_coverage_at_least_99_pct": totals[
            "member_votes_with_source_record"
        ]
        >= totals["member_votes"] * 0.99,
        "member_public_source_url_coverage_at_least_99_pct": totals[
            "member_votes_with_public_source_url"
        ]
        >= totals["member_votes"] * 0.99,
        "no_private_path_tokens": totals["payloads_with_private_path_tokens"] == 0,
    }
    return {
        "schema_version": "member_vote_shard_validation_v1",
        "status": "ok" if all(checks.values()) else "failed",
        "manifest": Path(manifest_path).name,
        "checks": checks,
        "totals": totals,
        "error_samples": errors,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        print(f"ERROR: manifest not found: {manifest_path.name}", file=sys.stderr)
        return 2
    try:
        report = validate_shards(manifest_path, shard_root=Path(args.shard_root))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if str(args.report_out or "").strip():
        out_path = Path(args.report_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 1 if args.enforce and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
