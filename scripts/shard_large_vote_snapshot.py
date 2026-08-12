#!/usr/bin/env python3
"""Convert a monolithic vote snapshot into bounded deterministic event shards."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_large_vote_snapshot import (  # noqa: E402
    canonical_public_source_url,
    is_public_http_url,
    iter_snapshot_items,
    source_matches_parent_event,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shard large vote snapshot by event")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument(
        "--shard-root", default="etl/data/derived/member-vote-shards"
    )
    parser.add_argument(
        "--manifest-out",
        default="etl/data/published/member-vote-shard-manifest-latest.json",
    )
    parser.add_argument("--max-index-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--max-shard-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--max-members-per-shard", type=int, default=1_000)
    parser.add_argument(
        "--source-provenance-overrides",
        help="Official capture sidecar used to repair known source provenance",
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_gzip_json_atomic(path: Path, value: object) -> tuple[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with partial.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
                payload = json.dumps(
                    value,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                zipped.write(payload)
            raw.flush()
            os.fsync(raw.fileno())
        digest = _sha256_file(partial)
        size = int(partial.stat().st_size)
        if path.is_file() and _sha256_file(path) == digest:
            partial.unlink()
        else:
            os.replace(partial, path)
        return digest, size
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _load_source_provenance_overrides(
    metadata_path: Path | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    if metadata_path is None:
        return {}, None
    path = Path(metadata_path)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or metadata.get("schema_version") != (
        "official-capture-source-v1"
    ):
        raise ValueError("unsupported source provenance override schema")
    if metadata.get("semantic_match_after_declared_capture_changes") is not True:
        raise ValueError("source provenance override lacks semantic verification")
    event_id = str(metadata.get("vote_event_id") or "").strip()
    source_url = str(metadata.get("source_url") or "").strip()
    captured_sha = str(metadata.get("captured_payload_sha256") or "").strip()
    official_sha = str(metadata.get("official_payload_sha256") or "").strip()
    parsed = urlparse(source_url)
    if (
        not event_id
        or parsed.scheme != "https"
        or parsed.hostname != "www.congreso.es"
        or "/webpublica/opendata/votaciones/" not in parsed.path
        or not parsed.path.endswith(".json")
    ):
        raise ValueError("invalid official source provenance override")
    if len(captured_sha) != 64 or len(official_sha) != 64:
        raise ValueError("source provenance override lacks SHA-256 values")
    suffix = ".source.json"
    capture_path = Path(str(path)[: -len(suffix)]) if str(path).endswith(suffix) else None
    if capture_path is None or not capture_path.is_file():
        raise ValueError("source provenance override capture is missing")
    if _sha256_file(capture_path) != captured_sha:
        raise ValueError("source provenance override capture checksum mismatch")
    try:
        portable_path = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        portable_path = path.name
    contract = {
        "path": portable_path,
        "sha256": _sha256_file(path),
        "entries": 1,
        "all_entries_applied": False,
    }
    return {event_id: metadata}, contract


def _apply_source_provenance_override(
    item: dict[str, Any], override: dict[str, Any]
) -> int:
    event = dict(item.get("event") or {})
    event_id = str(event.get("vote_event_id") or "").strip()
    if event_id != str(override.get("vote_event_id") or "").strip():
        raise ValueError("source provenance override event mismatch")
    source = dict(item.get("source") or {})
    source["source_url"] = str(override["source_url"])
    source["source_url_scope"] = "verified_official_capture"
    source["official_payload_sha256"] = str(
        override["official_payload_sha256"]
    )
    source["captured_payload_sha256"] = str(
        override["captured_payload_sha256"]
    )
    item["source"] = source
    if not str(event.get("legislature") or "").strip():
        match = re.search(r"/Leg(\d+)/", str(override["source_url"]))
        if match:
            event["legislature"] = str(int(match.group(1)))
    item["event"] = event
    return len(list(item.get("member_votes") or []))


def _make_member_lineage_explicit(item: dict[str, Any]) -> dict[str, int]:
    event_source = dict(item.get("source") or {})
    stats = {
        "member_votes": 0,
        "source_record_inherited": 0,
        "source_record_unresolved": 0,
        "public_source_url_inherited": 0,
        "public_source_url_unresolved": 0,
    }
    for member in list(item.get("member_votes") or []):
        stats["member_votes"] += 1
        source = dict(member.get("source") or {})
        parent_matches = source_matches_parent_event(source, event_source)
        if source.get("source_record_pk") is None and parent_matches:
            source["source_record_pk"] = event_source.get("source_record_pk")
            source["source_record_id"] = event_source.get("source_record_id")
            source["source_record_scope"] = "parent_vote_event"
            stats["source_record_inherited"] += 1
        if source.get("source_record_pk") is None:
            stats["source_record_unresolved"] += 1
        if not is_public_http_url(source.get("source_url")):
            parent_public_url = canonical_public_source_url(event_source)
            if parent_matches and parent_public_url:
                source["source_url"] = parent_public_url
                source["source_url_scope"] = "parent_vote_event"
                stats["public_source_url_inherited"] += 1
            else:
                stats["public_source_url_unresolved"] += 1
        member["source"] = source
    return stats


def _promote_source_record_urls(value: object) -> int:
    promoted = 0
    if isinstance(value, dict):
        public_url = canonical_public_source_url(value)
        if public_url and not is_public_http_url(value.get("source_url")):
            value["source_url"] = public_url
            value["source_url_scope"] = "source_record_id"
            promoted += 1
        for child in value.values():
            promoted += _promote_source_record_urls(child)
    elif isinstance(value, list):
        for child in value:
            promoted += _promote_source_record_urls(child)
    return promoted


def _redact_non_public_source_urls(value: object) -> int:
    redacted = 0
    if isinstance(value, dict):
        for key, child in list(value.items()):
            if key in {"source_url", "source_default_url"} and child:
                if not is_public_http_url(child):
                    value[key] = None
                    redacted += 1
                continue
            redacted += _redact_non_public_source_urls(child)
    elif isinstance(value, list):
        for child in value:
            redacted += _redact_non_public_source_urls(child)
    return redacted


def shard_snapshot(
    snapshot_path: Path,
    *,
    shard_root: Path,
    manifest_out: Path,
    max_index_bytes: int,
    max_shard_bytes: int,
    max_members_per_shard: int,
    source_provenance_overrides: Path | None = None,
) -> dict[str, Any]:
    snapshot_path = Path(snapshot_path)
    snapshot_key = snapshot_path.stem
    output_root = Path(shard_root) / snapshot_key
    entries: list[dict[str, object]] = []
    seen_events: set[str] = set()
    total_member_votes = 0
    total_shard_bytes = 0
    max_observed_shard_bytes = 0
    max_observed_members = 0
    provenance_overrides, provenance_override_contract = (
        _load_source_provenance_overrides(source_provenance_overrides)
    )
    applied_override_events: set[str] = set()
    lineage_totals = {
        "member_votes": 0,
        "source_record_inherited": 0,
        "source_record_unresolved": 0,
        "public_source_url_inherited": 0,
        "public_source_url_unresolved": 0,
        "non_public_source_urls_redacted": 0,
        "source_record_urls_promoted": 0,
        "official_capture_override_events": 0,
        "official_capture_override_member_votes": 0,
    }
    for item in iter_snapshot_items(snapshot_path):
        event = dict(item.get("event") or {})
        event_id = str(event.get("vote_event_id") or "").strip()
        if not event_id:
            raise ValueError("event missing vote_event_id")
        if event_id in seen_events:
            raise ValueError(f"duplicate vote_event_id: {event_id}")
        seen_events.add(event_id)
        override = provenance_overrides.get(event_id)
        if override is not None:
            overridden_members = _apply_source_provenance_override(item, override)
            applied_override_events.add(event_id)
            lineage_totals["official_capture_override_events"] += 1
            lineage_totals["official_capture_override_member_votes"] += int(
                overridden_members
            )
            event = dict(item.get("event") or {})
        lineage_totals["source_record_urls_promoted"] += _promote_source_record_urls(
            item
        )
        item_lineage = _make_member_lineage_explicit(item)
        for key, value in item_lineage.items():
            lineage_totals[key] += int(value)
        lineage_totals["non_public_source_urls_redacted"] += (
            _redact_non_public_source_urls(item)
        )
        event_hash = hashlib.sha256(event_id.encode()).hexdigest()
        relative_path = Path(event_hash[:2]) / f"{event_hash}.json.gz"
        destination = output_root / relative_path
        digest, shard_bytes = _write_gzip_json_atomic(destination, item)
        member_votes = len(list(item.get("member_votes") or []))
        total_member_votes += member_votes
        total_shard_bytes += shard_bytes
        max_observed_shard_bytes = max(max_observed_shard_bytes, shard_bytes)
        max_observed_members = max(max_observed_members, member_votes)
        entries.append(
            {
                "vote_event_id": event_id,
                "source_id": str(event.get("source_id") or ""),
                "vote_date": str(event.get("vote_date") or ""),
                "legislature": str(event.get("legislature") or ""),
                "title": str(event.get("title") or "")[:500],
                "member_votes": member_votes,
                "shard": (Path(snapshot_key) / relative_path).as_posix(),
                "shard_bytes": shard_bytes,
                "shard_sha256": digest,
            }
        )
    unapplied_overrides = sorted(set(provenance_overrides) - applied_override_events)
    if unapplied_overrides:
        raise ValueError(
            "source provenance overrides did not match snapshot events: "
            + ", ".join(unapplied_overrides)
        )
    if provenance_override_contract is not None:
        provenance_override_contract["all_entries_applied"] = True
        provenance_override_contract["events_applied"] = len(
            applied_override_events
        )
    manifest = {
        "schema_version": "member_vote_event_shards_v1",
        "source_snapshot": snapshot_path.name,
        "source_snapshot_sha256": _sha256_file(snapshot_path),
        "events_total": len(entries),
        "member_votes_total": total_member_votes,
        "shard_bytes_total": total_shard_bytes,
        "max_shard_bytes": max_observed_shard_bytes,
        "max_members_per_shard": max_observed_members,
        "compression": "gzip",
        "publication_status": "local_generated_not_published",
        "lineage": lineage_totals,
        "source_provenance_overrides": provenance_override_contract,
        "entries": entries,
    }
    checks = {
        "index_bytes": True,
        "max_shard_bytes": max_observed_shard_bytes <= int(max_shard_bytes),
        "max_members_per_shard": max_observed_members <= int(max_members_per_shard),
        "unique_event_shards": len(entries) == len(seen_events),
        "member_source_record_coverage_at_least_99_pct": (
            lineage_totals["source_record_unresolved"]
            <= lineage_totals["member_votes"] * 0.01
        ),
        "member_public_source_url_coverage_at_least_99_pct": (
            lineage_totals["public_source_url_unresolved"]
            <= lineage_totals["member_votes"] * 0.01
        ),
    }
    manifest["checks"] = checks
    manifest["index_bytes"] = 0
    manifest["bounded_delivery_gate_passed"] = False
    final_encoded = b""
    for _ in range(4):
        final_encoded = (
            json.dumps(
                manifest,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        manifest["index_bytes"] = len(final_encoded)
        manifest["checks"]["index_bytes"] = len(final_encoded) <= int(max_index_bytes)
        manifest["bounded_delivery_gate_passed"] = all(
            manifest["checks"].values()
        )
    final_encoded = (
        json.dumps(
            manifest,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    manifest_out = Path(manifest_out)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    partial = manifest_out.with_name(
        f".{manifest_out.name}.{uuid.uuid4().hex}.partial"
    )
    try:
        partial.write_bytes(final_encoded)
        os.replace(partial, manifest_out)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot_path = Path(args.snapshot)
    if not snapshot_path.is_file():
        print(f"ERROR: snapshot not found: {snapshot_path.name}", file=sys.stderr)
        return 2
    try:
        manifest = shard_snapshot(
            snapshot_path,
            shard_root=Path(args.shard_root),
            manifest_out=Path(args.manifest_out),
            max_index_bytes=int(args.max_index_bytes),
            max_shard_bytes=int(args.max_shard_bytes),
            max_members_per_shard=int(args.max_members_per_shard),
            source_provenance_overrides=(
                Path(args.source_provenance_overrides)
                if args.source_provenance_overrides
                else None
            ),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": (
                    "ok" if manifest["bounded_delivery_gate_passed"] else "failed"
                ),
                "events": manifest["events_total"],
                "member_votes": manifest["member_votes_total"],
                "manifest": Path(args.manifest_out).name,
            },
            sort_keys=True,
        )
    )
    if args.enforce and not bool(manifest["bounded_delivery_gate_passed"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
