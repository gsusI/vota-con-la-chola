#!/usr/bin/env python3
"""Bounded-memory audit of a large published parliamentary vote snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlsplit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit large vote JSON snapshot")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument(
        "--out",
        default="etl/data/published/member-vote-million-audit-latest.json",
    )
    parser.add_argument(
        "--shard-manifest",
        default="etl/data/published/member-vote-shard-manifest-latest.json",
    )
    parser.add_argument("--min-member-votes", type=int, default=1_000_000)
    parser.add_argument("--min-source-url-pct", type=float, default=0.99)
    parser.add_argument("--min-source-hash-pct", type=float, default=0.99)
    parser.add_argument("--min-source-record-pk-pct", type=float, default=0.99)
    parser.add_argument("--min-person-id-pct", type=float, default=0.95)
    parser.add_argument("--min-reconciled-events-pct", type=float, default=0.95)
    parser.add_argument("--max-duplicate-member-rate", type=float, default=0.0)
    parser.add_argument("--max-other-choice-rate", type=float, default=0.001)
    parser.add_argument("--max-public-artifact-bytes", type=int, default=100 * 1024 * 1024)
    parser.add_argument("--chunk-chars", type=int, default=1024 * 1024)
    parser.add_argument("--max-item-chars", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--enforce-promotion", action="store_true")
    return parser.parse_args(argv)


def _seek_items_array(handle: TextIO, *, chunk_chars: int) -> str:
    marker = '"items"'
    buffer = ""
    while True:
        chunk = handle.read(int(chunk_chars))
        if not chunk:
            raise ValueError("snapshot has no top-level items array")
        buffer += chunk
        marker_index = buffer.find(marker)
        if marker_index >= 0:
            array_index = buffer.find("[", marker_index + len(marker))
            if array_index >= 0:
                return buffer[array_index + 1 :]
        if len(buffer) > len(marker) + int(chunk_chars):
            buffer = buffer[-(len(marker) + 32) :]


def iter_snapshot_items(
    path: Path,
    *,
    chunk_chars: int = 1024 * 1024,
    max_item_chars: int = 16 * 1024 * 1024,
) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    with Path(path).open("r", encoding="utf-8") as handle:
        buffer = _seek_items_array(handle, chunk_chars=chunk_chars)
        while True:
            buffer = buffer.lstrip()
            if buffer.startswith(","):
                buffer = buffer[1:].lstrip()
            if buffer.startswith("]"):
                return
            try:
                value, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk = handle.read(int(chunk_chars))
                if not chunk:
                    raise ValueError("truncated or invalid item in snapshot")
                buffer += chunk
                if len(buffer) > int(max_item_chars):
                    raise ValueError("snapshot item exceeds max_item_chars")
                continue
            if not isinstance(value, dict):
                raise ValueError("every items entry must be an object")
            yield value
            buffer = buffer[end:]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_rss_mb() -> float:
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return round(rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024, 2)


def _choice_bucket(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return {
        "sí": "yes",
        "si": "yes",
        "yes": "yes",
        "no": "no",
        "abstención": "abstain",
        "abstencion": "abstain",
        "abstain": "abstain",
        "no vota": "no_vote",
        "no votan": "no_vote",
        "no_vote": "no_vote",
        "ausente": "absent",
        "absent": "absent",
    }.get(normalized, "other")


def is_public_http_url(value: object) -> bool:
    parsed = urlsplit(str(value or "").strip())
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def canonical_public_source_url(source: dict[str, Any]) -> str | None:
    source_url = str(source.get("source_url") or "").strip()
    if is_public_http_url(source_url):
        return source_url
    source_record_id = str(source.get("source_record_id") or "").strip()
    if source_record_id.startswith("url:") and is_public_http_url(
        source_record_id[4:]
    ):
        return source_record_id[4:]
    return None


def source_matches_parent_event(
    member_source: dict[str, Any], event_source: dict[str, Any]
) -> bool:
    member_source_id = str(member_source.get("source_id") or "").strip()
    event_source_id = str(event_source.get("source_id") or "").strip()
    return bool(member_source_id and member_source_id == event_source_id)


def audit_snapshot(
    path: Path,
    *,
    min_member_votes: int,
    min_source_url_pct: float,
    min_source_hash_pct: float,
    min_source_record_pk_pct: float,
    min_reconciled_events_pct: float,
    max_duplicate_member_rate: float,
    max_public_artifact_bytes: int,
    shard_manifest_path: Path | None = None,
    min_person_id_pct: float = 0.95,
    max_other_choice_rate: float = 0.001,
    chunk_chars: int = 1024 * 1024,
    max_item_chars: int = 16 * 1024 * 1024,
) -> dict[str, Any]:
    path = Path(path)
    totals: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    choice_counts: Counter[str] = Counter()
    raw_choice_counts: Counter[str] = Counter()
    reconciliation_by_source: Counter[str] = Counter()
    reconciliation_samples: list[dict[str, object]] = []
    event_ids: set[str] = set()
    duplicate_event_ids = 0
    for item in iter_snapshot_items(
        path,
        chunk_chars=chunk_chars,
        max_item_chars=max_item_chars,
    ):
        totals["events"] += 1
        event = dict(item.get("event") or {})
        event_source = dict(item.get("source") or {})
        event_id = str(event.get("vote_event_id") or "")
        if not event_id or event_id in event_ids:
            duplicate_event_ids += 1
        if event_id:
            event_ids.add(event_id)
        source_counts[str(event.get("source_id") or "unknown")] += 1
        member_votes = list(item.get("member_votes") or [])
        seen_member_keys: set[tuple[str, str, str]] = set()
        event_choices: Counter[str] = Counter()
        for member in member_votes:
            totals["member_votes"] += 1
            source = dict(member.get("source") or {})
            parent_source_matches = source_matches_parent_event(source, event_source)
            if canonical_public_source_url(source):
                totals["source_url_direct_public"] += 1
                totals["source_url_effective_public"] += 1
            elif parent_source_matches and canonical_public_source_url(event_source):
                totals["source_url_parent_inherited"] += 1
                totals["source_url_effective_public"] += 1
            totals["source_hash"] += 1 if str(source.get("source_hash") or "") else 0
            direct_source_record = source.get("source_record_pk") is not None
            if direct_source_record:
                totals["source_record_pk_direct"] += 1
                totals["source_record_lineage_effective"] += 1
            else:
                member_source_id = str(source.get("source_id") or "")
                event_source_id = str(event_source.get("source_id") or "")
                member_source_url = str(source.get("source_url") or "")
                parent_lineage_complete = bool(
                    event_source.get("source_record_pk") is not None
                    and str(event_source.get("source_record_id") or "")
                    and str(event_source.get("source_hash") or "")
                    and member_source_id
                    and member_source_id == event_source_id
                    and member_source_url
                    and parent_source_matches
                )
                if parent_lineage_complete:
                    totals["source_record_parent_inherited"] += 1
                    totals["source_record_lineage_effective"] += 1
                else:
                    totals["source_record_lineage_missing_or_mismatch"] += 1
            totals["person_id"] += 1 if member.get("person_id") is not None else 0
            bucket = _choice_bucket(member.get("vote_choice"))
            raw_choice_counts[str(member.get("vote_choice") or "")] += 1
            choice_counts[bucket] += 1
            event_choices[bucket] += 1
            member_key = (
                str(member.get("seat") or ""),
                str(member.get("member_name_normalized") or ""),
                str(member.get("member_name") or ""),
            )
            if member_key in seen_member_keys:
                totals["duplicate_member_rows"] += 1
            seen_member_keys.add(member_key)
        if member_votes:
            expected = {
                "yes": int(event.get("totals_yes") or 0),
                "no": int(event.get("totals_no") or 0),
                "abstain": int(event.get("totals_abstain") or 0),
                "no_vote": int(event.get("totals_no_vote") or 0),
            }
            comparison_keys = list(expected)
            if event.get("totals_absent") is not None:
                expected["absent"] = int(event.get("totals_absent") or 0)
                comparison_keys.append("absent")
                totals["events_absent_totals_available"] += 1
            else:
                totals["events_absent_totals_unavailable"] += 1
            totals["member_votes_absent_observed"] += int(event_choices["absent"])
            totals_available = bool(
                sum(expected.values()) > 0 or int(event.get("totals_present") or 0) > 0
            )
            if not totals_available:
                totals["events_totals_unavailable"] += 1
                reconciliation_by_source[
                    f"{event.get('source_id') or 'unknown'}:totals_unavailable"
                ] += 1
                continue
            if all(event_choices[key] == expected[key] for key in comparison_keys):
                totals["events_reconciled"] += 1
                reconciliation_by_source[f"{event.get('source_id') or 'unknown'}:reconciled"] += 1
            else:
                totals["events_not_reconciled"] += 1
                reconciliation_by_source[f"{event.get('source_id') or 'unknown'}:not_reconciled"] += 1
                if len(reconciliation_samples) < 20:
                    reconciliation_samples.append(
                        {
                            "vote_event_id": event_id,
                            "source_id": str(event.get("source_id") or "unknown"),
                            "expected": expected,
                            "observed": dict(event_choices),
                            "member_votes": len(member_votes),
                        }
                    )

    member_votes_total = int(totals["member_votes"])
    events_with_votes = int(totals["events_reconciled"] + totals["events_not_reconciled"])

    def pct(value: int, denominator: int) -> float:
        return round(value / denominator, 6) if denominator else 0.0

    coverage = {
        "source_url_direct_public_pct": pct(
            int(totals["source_url_direct_public"]), member_votes_total
        ),
        "source_url_parent_inherited_pct": pct(
            int(totals["source_url_parent_inherited"]), member_votes_total
        ),
        "source_url_effective_public_pct": pct(
            int(totals["source_url_effective_public"]), member_votes_total
        ),
        "source_hash_pct": pct(int(totals["source_hash"]), member_votes_total),
        "source_record_pk_direct_pct": pct(
            int(totals["source_record_pk_direct"]), member_votes_total
        ),
        "source_record_parent_inherited_pct": pct(
            int(totals["source_record_parent_inherited"]), member_votes_total
        ),
        "source_record_lineage_effective_pct": pct(
            int(totals["source_record_lineage_effective"]), member_votes_total
        ),
        "source_record_lineage_missing_or_mismatch_rate": pct(
            int(totals["source_record_lineage_missing_or_mismatch"]),
            member_votes_total,
        ),
        "person_id_pct": pct(int(totals["person_id"]), member_votes_total),
        "events_reconciled_pct": pct(
            int(totals["events_reconciled"]), events_with_votes
        ),
        "duplicate_member_rate": pct(
            int(totals["duplicate_member_rows"]), member_votes_total
        ),
        "other_choice_rate": pct(int(choice_counts["other"]), member_votes_total),
    }
    file_bytes = int(path.stat().st_size)
    file_sha256 = _sha256_file(path)
    shard_delivery: dict[str, object] | None = None
    bounded_delivery_shape = file_bytes <= int(max_public_artifact_bytes)
    bounded_public_artifact = bounded_delivery_shape
    if shard_manifest_path is not None and Path(shard_manifest_path).is_file():
        shard_manifest = json.loads(Path(shard_manifest_path).read_text(encoding="utf-8"))
        matching_snapshot = (
            str(shard_manifest.get("source_snapshot_sha256") or "") == file_sha256
            and int(shard_manifest.get("member_votes_total") or 0) == member_votes_total
            and int(shard_manifest.get("events_total") or 0) == int(totals["events"])
        )
        bounded_delivery_shape = matching_snapshot and bool(
            shard_manifest.get("bounded_delivery_gate_passed")
        )
        published = str(shard_manifest.get("publication_status") or "") == "published"
        bounded_public_artifact = bounded_delivery_shape and published
        shard_delivery = {
            "manifest": Path(shard_manifest_path).name,
            "matching_snapshot": matching_snapshot,
            "bounded_delivery_shape": bounded_delivery_shape,
            "publication_status": str(
                shard_manifest.get("publication_status") or "unknown"
            ),
            "index_bytes": int(shard_manifest.get("index_bytes") or 0),
            "shard_bytes_total": int(shard_manifest.get("shard_bytes_total") or 0),
            "max_shard_bytes": int(shard_manifest.get("max_shard_bytes") or 0),
        }
    checks = {
        "million_real_member_votes_observed": member_votes_total >= int(min_member_votes),
        "unique_event_ids": duplicate_event_ids == 0,
        "source_url_coverage": coverage["source_url_effective_public_pct"]
        >= float(min_source_url_pct),
        "source_hash_coverage": coverage["source_hash_pct"] >= float(min_source_hash_pct),
        "source_record_lineage_coverage": coverage[
            "source_record_lineage_effective_pct"
        ]
        >= float(min_source_record_pk_pct),
        "person_id_coverage": coverage["person_id_pct"] >= float(min_person_id_pct),
        "event_total_reconciliation": coverage["events_reconciled_pct"]
        >= float(min_reconciled_events_pct),
        "duplicate_member_rate": coverage["duplicate_member_rate"]
        <= float(max_duplicate_member_rate),
        "recognized_vote_choices": coverage["other_choice_rate"]
        <= float(max_other_choice_rate),
        "bounded_delivery_shape": bounded_delivery_shape,
        "bounded_public_artifact": bounded_public_artifact,
    }
    observed = bool(checks["million_real_member_votes_observed"])
    promoted = observed and all(checks.values())
    return {
        "schema_version": "large_vote_snapshot_audit_v3",
        "status": (
            "promoted"
            if promoted
            else "observed_not_promoted"
            if observed
            else "below_million"
        ),
        "snapshot_file": path.name,
        "file_bytes": file_bytes,
        "file_sha256": file_sha256,
        "peak_rss_mb": _peak_rss_mb(),
        "totals": {
            "events": int(totals["events"]),
            "unique_event_ids": len(event_ids),
            "duplicate_event_ids": duplicate_event_ids,
            "member_votes": member_votes_total,
            "member_votes_with_direct_source_record": int(
                totals["source_record_pk_direct"]
            ),
            "member_votes_with_parent_event_source_record": int(
                totals["source_record_parent_inherited"]
            ),
            "member_votes_without_effective_source_record": int(
                totals["source_record_lineage_missing_or_mismatch"]
            ),
            "duplicate_member_rows": int(totals["duplicate_member_rows"]),
            "events_reconciled": int(totals["events_reconciled"]),
            "events_not_reconciled": int(totals["events_not_reconciled"]),
            "events_totals_unavailable": int(totals["events_totals_unavailable"]),
            "events_absent_totals_available": int(
                totals["events_absent_totals_available"]
            ),
            "events_absent_totals_unavailable": int(
                totals["events_absent_totals_unavailable"]
            ),
            "member_votes_absent_observed": int(
                totals["member_votes_absent_observed"]
            ),
        },
        "coverage": coverage,
        "source_event_counts": dict(sorted(source_counts.items())),
        "vote_choice_counts": dict(sorted(choice_counts.items())),
        "raw_vote_choice_counts": dict(sorted(raw_choice_counts.items())),
        "reconciliation_by_source": dict(sorted(reconciliation_by_source.items())),
        "reconciliation_samples": reconciliation_samples,
        "shard_delivery": shard_delivery,
        "checks": checks,
        "promotion_gate_passed": promoted,
        "limitations": [
            "This audits the published JSON artifact, not the upstream fetch run or current canonical SQLite database.",
            "A million observed member-vote objects does not promote identity, document, money, outcome, review, or public-delivery lanes.",
            "Member-vote lineage may be inherited only from its containing vote event when source ids match and the event has a source record id, primary key, and hash; direct and inherited coverage remain separate metrics.",
            "Absent members are a distinct Senate category, not a no-vote ballot. Absence totals are reconciled only when totals_absent is present in the event artifact; older snapshots still report observed absences separately.",
            "A bounded shard/index alternative may satisfy delivery shape locally, but promotion still requires durable public publication and checksum verification.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.snapshot)
    if not path.is_file():
        print(f"ERROR: snapshot not found: {path.name}", file=sys.stderr)
        return 2
    try:
        report = audit_snapshot(
            path,
            min_member_votes=int(args.min_member_votes),
            min_source_url_pct=float(args.min_source_url_pct),
            min_source_hash_pct=float(args.min_source_hash_pct),
            min_source_record_pk_pct=float(args.min_source_record_pk_pct),
            min_reconciled_events_pct=float(args.min_reconciled_events_pct),
            max_duplicate_member_rate=float(args.max_duplicate_member_rate),
            max_public_artifact_bytes=int(args.max_public_artifact_bytes),
            shard_manifest_path=Path(args.shard_manifest),
            min_person_id_pct=float(args.min_person_id_pct),
            max_other_choice_rate=float(args.max_other_choice_rate),
            chunk_chars=int(args.chunk_chars),
            max_item_chars=int(args.max_item_chars),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "member_votes": report["totals"]["member_votes"],
                "out": out_path.name,
            },
            sort_keys=True,
        )
    )
    if args.enforce_promotion and not bool(report["promotion_gate_passed"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
