#!/usr/bin/env python3
"""Generate conservative BOJA legal-change review drafts for Andalucia 2026.

The output is a review-assist artifact, not an automatic merit/blame claim.
Drafts only restate official BOJA fragments already present in the review queue.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.export_andalucia_2026_accountability_snapshot import write_json


DEFAULT_ACCOUNTABILITY = Path("etl/data/published/andalucia-2026-accountability.json")
DEFAULT_EXISTING_REVIEWS = Path("etl/data/seeds/andalucia_2026_boja_impact_reviews.json")
DEFAULT_OUT = Path("etl/data/published/andalucia-2026-boja-impact-review-drafts.json")

NO_MERIT_CLAIM_STATUS = "reviewed_boja_legal_change_no_merit_claim"
UNSUPPORTED_TOPIC_IDS = {"", "sin_tema"}
UNSUPPORTED_ACTION_KINDS = {"", "official_normative_reference"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Andalucia 2026 BOJA legal-change review drafts")
    parser.add_argument("--accountability", default=str(DEFAULT_ACCOUNTABILITY), help="Accountability JSON path")
    parser.add_argument("--existing-reviews", default=str(DEFAULT_EXISTING_REVIEWS), help="Existing BOJA review seed")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Draft review JSON output path")
    parser.add_argument("--reviewed-at", default="", help="Override reviewed_at/generator date")
    parser.add_argument(
        "--max-drafts-per-topic",
        type=int,
        default=0,
        help="Draft cap per topic; 0 means no per-topic cap",
    )
    parser.add_argument(
        "--include-reviewed",
        action="store_true",
        help="Do not skip BOJA items already present in the review seed",
    )
    parser.add_argument(
        "--include-nonblocked-topics",
        action="store_true",
        help="Draft eligible rows outside topics currently blocked by reviewed_boja_missing",
    )
    return parser.parse_args()


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def existing_review_keys(payload: dict[str, Any]) -> set[str]:
    return {
        str(row.get("review_item_id") or "")
        for row in payload.get("reviews") or []
        if isinstance(row, dict) and str(row.get("review_item_id") or "")
    }


def blocked_boja_topics(accountability: dict[str, Any]) -> set[str]:
    topics: set[str] = set()
    for issue in (accountability.get("accountability_readiness") or {}).get("issues") or []:
        if not isinstance(issue, dict):
            continue
        blockers = {str(item) for item in issue.get("blockers") or []}
        if issue.get("primary_blocker") == "reviewed_boja_missing" or "reviewed_boja_missing" in blockers:
            topic_id = str(issue.get("topic_id") or "")
            if topic_id:
                topics.add(topic_id)
    return topics


def boja_review_queue(accountability: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in (accountability.get("boja_norms") or {}).get("impact_review_queue") or []
        if isinstance(row, dict)
    ]


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def short_text(value: Any, *, max_chars: int = 260) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def unsupported_reason(row: dict[str, Any], *, blocked_topics: set[str], include_nonblocked_topics: bool) -> str:
    topic_id = str(row.get("topic_id") or "")
    action_kind = str(row.get("action_kind") or "")
    if topic_id in UNSUPPORTED_TOPIC_IDS:
        return "topic_missing_or_unclassified"
    if blocked_topics and topic_id not in blocked_topics and not include_nonblocked_topics:
        return "topic_not_currently_blocked_by_boja_review"
    if action_kind in UNSUPPORTED_ACTION_KINDS:
        return "action_kind_unsupported"
    if not row.get("source_url") and not row.get("detail_url"):
        return "source_url_missing"
    if not row.get("evidence_excerpt") and not row.get("record_summary"):
        return "evidence_excerpt_missing"
    return ""


def boja_sort_key(row: dict[str, Any], blocked_topics: set[str]) -> tuple[int, int, int, str, str]:
    topic_id = str(row.get("topic_id") or "")
    return (
        0 if topic_id in blocked_topics else 1,
        int_value(row.get("priority_rank"), 999999),
        -int_value(row.get("priority_score"), 0),
        str(row.get("action_kind") or ""),
        str(row.get("review_item_id") or ""),
    )


def reviewed_legal_change_label(row: dict[str, Any]) -> str:
    action = str(row.get("action_kind") or "cambio normativo").replace("_", " ")
    excerpt = short_text(row.get("evidence_excerpt") or row.get("record_summary"), max_chars=180)
    boja_id = str(row.get("boja_id") or "BOJA")
    return short_text(f"{boja_id}: {action}; {excerpt}", max_chars=240)


def review_summary(row: dict[str, Any]) -> str:
    return (
        "Machine draft from the official BOJA impact-review queue. "
        "The BOJA fragment documents {action} for {boja_id}. "
        "This records the official legal-change signal only; it is not execution, outcome, merit or blame."
    ).format(
        action=str(row.get("action_kind") or "official normative reference").replace("_", " "),
        boja_id=row.get("boja_id") or "unknown BOJA item",
    )


def compact_draft_row(row: dict[str, Any], *, reviewed_at: str) -> dict[str, Any]:
    return {
        "review_item_id": str(row.get("review_item_id") or ""),
        "topic_id": str(row.get("topic_id") or ""),
        "topic_label": str(row.get("topic_label") or ""),
        "boja_id": str(row.get("boja_id") or ""),
        "fragment_id": str(row.get("fragment_id") or ""),
        "date": str(row.get("date") or ""),
        "organisation": str(row.get("organisation") or ""),
        "type": str(row.get("type") or ""),
        "action_kind": str(row.get("action_kind") or ""),
        "draft_status": "machine_draft_needs_human_review",
        "review_status": "reviewed_legal_change_only",
        "claim_status": NO_MERIT_CLAIM_STATUS,
        "impact_status": "legal_change_documented_outcome_pending",
        "responsibility_status": "official_publisher_observed",
        "candidate_direction": "unknown",
        "reviewed_legal_change_label": reviewed_legal_change_label(row),
        "source_url": str(row.get("source_url") or ""),
        "detail_url": str(row.get("detail_url") or ""),
        "source_locator": str(row.get("source_locator") or ""),
        "evidence_excerpt": short_text(row.get("evidence_excerpt") or row.get("record_summary"), max_chars=320),
        "review_summary": review_summary(row),
        "review_confidence": "low",
        "reviewed_by": "draft_generator",
        "reviewed_at": reviewed_at,
        "source_evidence": [
            {
                "source_kind": "official_boja_text",
                "source_locator": str(row.get("source_locator") or ""),
                "evidence_excerpt": short_text(
                    row.get("evidence_excerpt") or row.get("record_summary"),
                    max_chars=320,
                ),
            }
        ],
        "open_limitations": [
            "legal_change_only",
            "execution_owner_not_reviewed",
            "budget_execution_not_linked",
            "outcome_not_reviewed",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ],
    }


def generate_draft_boja_reviews(
    accountability: dict[str, Any],
    *,
    existing_keys: set[str],
    reviewed_at: str,
    max_drafts_per_topic: int = 0,
    include_reviewed: bool = False,
    include_nonblocked_topics: bool = False,
) -> dict[str, Any]:
    queue = boja_review_queue(accountability)
    blocked_topics = blocked_boja_topics(accountability)
    drafts: list[dict[str, Any]] = []
    drafted_by_topic: Counter[str] = Counter()
    skipped_existing = 0
    skipped_over_limit = 0
    skipped_by_reason: Counter[str] = Counter()

    for row in sorted(queue, key=lambda item: boja_sort_key(item, blocked_topics)):
        review_item_id = str(row.get("review_item_id") or "")
        topic_id = str(row.get("topic_id") or "")
        if not include_reviewed and review_item_id in existing_keys:
            skipped_existing += 1
            continue
        reason = unsupported_reason(
            row,
            blocked_topics=blocked_topics,
            include_nonblocked_topics=include_nonblocked_topics,
        )
        if reason:
            skipped_by_reason[reason] += 1
            continue
        if max_drafts_per_topic > 0 and drafted_by_topic[topic_id] >= max_drafts_per_topic:
            skipped_over_limit += 1
            continue
        draft = compact_draft_row(row, reviewed_at=reviewed_at)
        if draft["claim_status"] != NO_MERIT_CLAIM_STATUS:
            raise RuntimeError(f"Unsafe draft claim_status: {draft['claim_status']}")
        drafts.append(draft)
        drafted_by_topic[topic_id] += 1

    drafted_topics = set(drafted_by_topic)
    return {
        "schema_version": "andalucia_2026_boja_impact_review_drafts_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "reviewed_at": reviewed_at,
        "generator": "scripts/generate_andalucia_2026_boja_review_drafts.py",
        "review_policy": (
            "Machine drafts only. Promote manually after checking the official BOJA fragment. "
            "Drafts must not publish merit, blame, causality, execution or citizen-impact claims."
        ),
        "status": "drafts_ready" if drafts else "no_drafts",
        "boja_queue_items_total": len(queue),
        "blocked_boja_topics": sorted(blocked_topics),
        "blocked_boja_topics_total": len(blocked_topics),
        "blocked_boja_topics_with_drafts": sorted(blocked_topics & drafted_topics),
        "blocked_boja_topics_with_drafts_total": len(blocked_topics & drafted_topics),
        "blocked_boja_topics_without_drafts": sorted(blocked_topics - drafted_topics),
        "blocked_boja_topics_without_drafts_total": len(blocked_topics - drafted_topics),
        "drafts_total": len(drafts),
        "drafts_by_topic": dict(sorted(drafted_by_topic.items())),
        "skipped_existing_reviews_total": skipped_existing,
        "skipped_over_limit_total": skipped_over_limit,
        "skipped_unsupported_items_total": sum(skipped_by_reason.values()),
        "skipped_unsupported_reasons": [
            {"reason": key, "count": count}
            for key, count in sorted(skipped_by_reason.items(), key=lambda item: (-item[1], item[0]))
        ],
        "drafts": drafts,
    }


def main() -> int:
    args = parse_args()
    reviewed_at = args.reviewed_at or datetime.now(UTC).date().isoformat()
    accountability = load_json_object(Path(args.accountability))
    existing_reviews = load_json_object(Path(args.existing_reviews))
    payload = generate_draft_boja_reviews(
        accountability,
        existing_keys=existing_review_keys(existing_reviews),
        reviewed_at=reviewed_at,
        max_drafts_per_topic=int(args.max_drafts_per_topic),
        include_reviewed=bool(args.include_reviewed),
        include_nonblocked_topics=bool(args.include_nonblocked_topics),
    )
    changed = write_json(Path(args.out), payload)
    print(
        "OK Andalucia 2026 BOJA review drafts -> {out} ({state}); drafts={drafts} blocked_topics_with_drafts={with_drafts} blocked_topics_without_drafts={without_drafts} skipped_existing={existing}".format(
            out=args.out,
            state="updated" if changed else "unchanged",
            drafts=payload["drafts_total"],
            with_drafts=payload["blocked_boja_topics_with_drafts_total"],
            without_drafts=payload["blocked_boja_topics_without_drafts_total"],
            existing=payload["skipped_existing_reviews_total"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
