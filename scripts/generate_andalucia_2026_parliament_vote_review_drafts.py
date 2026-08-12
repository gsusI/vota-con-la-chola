#!/usr/bin/env python3
"""Generate conservative parliament vote-review drafts for Andalucia 2026.

The output is a review-assist artifact, not an automatic merit/blame claim.
Drafts only restate official vote results already present in the review queue.
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

from scripts.export_andalucia_2026_accountability_snapshot import stable_slug, write_json


DEFAULT_ACCOUNTABILITY = Path("etl/data/published/andalucia-2026-accountability.json")
DEFAULT_EXISTING_REVIEWS = Path("etl/data/seeds/andalucia_2026_parliament_vote_reviews.json")
DEFAULT_OUT = Path("etl/data/published/andalucia-2026-parliament-vote-review-drafts.json")

NO_MERIT_CLAIM_STATUS = "official_vote_result_review_no_merit_or_blame"
UNSUPPORTED_TOPIC_IDS = {"", "sin_tema"}
UNSUPPORTED_LEGAL_EFFECT_KINDS = {"", "unclassified_vote"}

LEGAL_EFFECT_KIND_PRIORITY = {
    "law_final_approval_vote_passed": 0,
    "law_final_approval_vote_rejected": 0,
    "decree_law_validation_vote_passed": 1,
    "decree_law_validation_vote_not_passed_or_derogation_supported": 1,
    "parliament_work_body_creation_vote_rejected": 2,
    "legislative_bill_vote_rejected": 2,
    "motion_resolution_vote_passed": 3,
    "motion_resolution_vote_rejected": 3,
    "nonbinding_resolution_vote_passed": 4,
    "nonbinding_resolution_vote_rejected": 4,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate conservative Andalucia 2026 parliament vote-review drafts"
    )
    parser.add_argument("--accountability", default=str(DEFAULT_ACCOUNTABILITY), help="Accountability JSON path")
    parser.add_argument("--existing-reviews", default=str(DEFAULT_EXISTING_REVIEWS), help="Existing parliament vote review seed")
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
        help="Do not skip vote items already present in the review seed",
    )
    parser.add_argument(
        "--include-nonblocked-topics",
        action="store_true",
        help="Draft eligible rows outside topics currently blocked by reviewed_vote_missing",
    )
    return parser.parse_args()


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def existing_review_keys(payload: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for row in payload.get("reviews") or []:
        if not isinstance(row, dict):
            continue
        review_item_id = str(row.get("review_item_id") or "")
        vote_event_id = str(row.get("vote_event_id") or "")
        if review_item_id:
            keys.add(f"review_item_id:{review_item_id}")
        if vote_event_id:
            keys.add(f"vote_event_id:{vote_event_id}")
    return keys


def vote_item_keys(row: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    review_item_id = str(row.get("review_item_id") or "")
    vote_event_id = str(row.get("vote_event_id") or "")
    if review_item_id:
        keys.add(f"review_item_id:{review_item_id}")
    if vote_event_id:
        keys.add(f"vote_event_id:{vote_event_id}")
    return keys


def blocked_vote_topics(accountability: dict[str, Any]) -> set[str]:
    topics: set[str] = set()
    for issue in (accountability.get("accountability_readiness") or {}).get("issues") or []:
        if not isinstance(issue, dict):
            continue
        blockers = {str(item) for item in issue.get("blockers") or []}
        if issue.get("primary_blocker") == "reviewed_vote_missing" or "reviewed_vote_missing" in blockers:
            topic_id = str(issue.get("topic_id") or "")
            if topic_id:
                topics.add(topic_id)
    return topics


def parliament_vote_queue(accountability: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in (accountability.get("parliament_activity") or {}).get("vote_impact_review_queue") or []
        if isinstance(row, dict)
    ]


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def outcome_for_vote(row: dict[str, Any]) -> tuple[str, str]:
    legal_effect_kind = str(row.get("legal_effect_kind") or "")
    majority_side = str(row.get("majority_side") or "")
    if legal_effect_kind == "decree_law_validation_vote_passed" and majority_side == "si":
        return "observed_decree_law_validation_vote", "decree_law_validated_by_majority_yes"
    if majority_side == "si" and legal_effect_kind.endswith("_passed"):
        return "observed_approval_vote", "approved_by_majority_yes"
    if majority_side == "no" and (
        legal_effect_kind.endswith("_rejected")
        or legal_effect_kind.endswith("_not_passed_or_derogation_supported")
    ):
        return "observed_rejection_vote", "rejected_by_majority_no"
    return "", ""


def unsupported_reason(row: dict[str, Any], *, blocked_topics: set[str], include_nonblocked_topics: bool) -> str:
    topic_id = str(row.get("topic_id") or "")
    legal_effect_kind = str(row.get("legal_effect_kind") or "")
    majority_side = str(row.get("majority_side") or "")
    legal_effect_status, effect_outcome = outcome_for_vote(row)
    if topic_id in UNSUPPORTED_TOPIC_IDS:
        return "topic_missing_or_unclassified"
    if blocked_topics and topic_id not in blocked_topics and not include_nonblocked_topics:
        return "topic_not_currently_blocked_by_vote_review"
    if legal_effect_kind in UNSUPPORTED_LEGAL_EFFECT_KINDS:
        return "legal_effect_kind_unsupported"
    if majority_side not in {"si", "no"}:
        return "majority_side_unsupported"
    if not legal_effect_status or not effect_outcome:
        return "vote_outcome_mapping_unsupported"
    if int_value(row.get("total_si")) + int_value(row.get("total_no")) <= 0:
        return "vote_totals_missing"
    return ""


def vote_sort_key(row: dict[str, Any], blocked_topics: set[str]) -> tuple[int, int, int, int, str]:
    topic_id = str(row.get("topic_id") or "")
    return (
        0 if topic_id in blocked_topics else 1,
        LEGAL_EFFECT_KIND_PRIORITY.get(str(row.get("legal_effect_kind") or ""), 99),
        int_value(row.get("priority_rank"), 999999),
        int_value(row.get("vote_number"), 999999),
        str(row.get("vote_event_id") or row.get("review_item_id") or ""),
    )


def short_text(value: Any, *, max_chars: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def evidence_excerpt(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("numexp") or "").strip(),
        f"votacion numero {row.get('vote_number') or ''}".strip(),
        f"total si {int_value(row.get('total_si'))}",
        f"total no {int_value(row.get('total_no'))}",
        f"total abstenciones {int_value(row.get('total_abstenciones'))}",
        f"mayoria {row.get('majority_side') or ''}".strip(),
    ]
    title = short_text(row.get("title"), max_chars=160)
    if title:
        parts.append(title)
    return "; ".join(part for part in parts if part)


def review_summary(row: dict[str, Any]) -> str:
    return (
        "Machine draft from the official parliament vote queue. "
        "Official PDF data records {yes} si / {no} no / {abst} abstenciones on vote {vote_number} "
        "for {numexp}. This observes party positions only; it is not impact, merit or blame."
    ).format(
        yes=int_value(row.get("total_si")),
        no=int_value(row.get("total_no")),
        abst=int_value(row.get("total_abstenciones")),
        vote_number=row.get("vote_number") or "",
        numexp=row.get("numexp") or "unknown expediente",
    )


def compact_draft_row(row: dict[str, Any], *, reviewed_at: str) -> dict[str, Any]:
    legal_effect_status, effect_outcome = outcome_for_vote(row)
    return {
        "review_item_id": str(row.get("review_item_id") or ""),
        "vote_event_id": str(row.get("vote_event_id") or ""),
        "topic_id": str(row.get("topic_id") or ""),
        "topic_label": str(row.get("topic_label") or ""),
        "topic_source": str(row.get("topic_source") or ""),
        "draft_status": "machine_draft_needs_human_review",
        "review_status": "reviewed_vote_result_only",
        "claim_status": NO_MERIT_CLAIM_STATUS,
        "legal_effect_status": legal_effect_status,
        "legal_effect_kind": str(row.get("legal_effect_kind") or ""),
        "legal_effect_label": str(row.get("legal_effect_label") or ""),
        "legal_effect_confidence": str(row.get("legal_effect_confidence") or ""),
        "effect_outcome": effect_outcome,
        "impact_status": "outcome_not_reviewed",
        "responsibility_status": "party_positions_observed",
        "candidate_direction": "unknown",
        "reviewed_issue_label": str(row.get("topic_label") or ""),
        "date": str(row.get("date") or ""),
        "session_number": str(row.get("session_number") or ""),
        "vote_number": str(row.get("vote_number") or ""),
        "numexp": str(row.get("numexp") or ""),
        "title": str(row.get("title") or ""),
        "majority_side": str(row.get("majority_side") or ""),
        "total_si": int_value(row.get("total_si")),
        "total_no": int_value(row.get("total_no")),
        "total_abstenciones": int_value(row.get("total_abstenciones")),
        "total_blancos": int_value(row.get("total_blancos")),
        "party_positions_summary": str(row.get("party_positions_summary") or ""),
        "source_url": str(row.get("source_url") or ""),
        "initiative_source_url": str(row.get("initiative_source_url") or ""),
        "source_locator": str(row.get("source_locator") or ""),
        "review_summary": review_summary(row),
        "review_confidence": "low",
        "reviewed_by": "draft_generator",
        "reviewed_at": reviewed_at,
        "source_evidence": [
            {
                "source_kind": "official_vote_pdf_text",
                "source_locator": str(row.get("source_locator") or ""),
                "evidence_excerpt": evidence_excerpt(row),
            }
        ],
        "open_limitations": [
            "legal_effect_auto_triage_needs_human_review",
            "citizen_direction_not_reviewed",
            "outcome_not_reviewed",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ],
    }


def generate_draft_parliament_vote_reviews(
    accountability: dict[str, Any],
    *,
    existing_keys: set[str],
    reviewed_at: str,
    max_drafts_per_topic: int = 0,
    include_reviewed: bool = False,
    include_nonblocked_topics: bool = False,
) -> dict[str, Any]:
    queue = parliament_vote_queue(accountability)
    blocked_topics = blocked_vote_topics(accountability)
    drafts: list[dict[str, Any]] = []
    drafted_by_topic: Counter[str] = Counter()
    skipped_existing = 0
    skipped_over_limit = 0
    skipped_by_reason: Counter[str] = Counter()

    for row in sorted(queue, key=lambda item: vote_sort_key(item, blocked_topics)):
        topic_id = str(row.get("topic_id") or "")
        if not include_reviewed and vote_item_keys(row) & existing_keys:
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
        "schema_version": "andalucia_2026_parliament_vote_review_drafts_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "reviewed_at": reviewed_at,
        "generator": "scripts/generate_andalucia_2026_parliament_vote_review_drafts.py",
        "review_policy": (
            "Machine drafts only. Promote manually after checking the official vote row. "
            "Drafts must not publish merit, blame, causality or citizen-impact claims."
        ),
        "status": "drafts_ready" if drafts else "no_drafts",
        "vote_queue_items_total": len(queue),
        "blocked_vote_topics": sorted(blocked_topics),
        "blocked_vote_topics_total": len(blocked_topics),
        "blocked_vote_topics_with_drafts": sorted(blocked_topics & drafted_topics),
        "blocked_vote_topics_with_drafts_total": len(blocked_topics & drafted_topics),
        "blocked_vote_topics_without_drafts": sorted(blocked_topics - drafted_topics),
        "blocked_vote_topics_without_drafts_total": len(blocked_topics - drafted_topics),
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
    payload = generate_draft_parliament_vote_reviews(
        accountability,
        existing_keys=existing_review_keys(existing_reviews),
        reviewed_at=reviewed_at,
        max_drafts_per_topic=int(args.max_drafts_per_topic),
        include_reviewed=bool(args.include_reviewed),
        include_nonblocked_topics=bool(args.include_nonblocked_topics),
    )
    changed = write_json(Path(args.out), payload)
    print(
        "OK Andalucia 2026 parliament vote review drafts -> {out} ({state}); drafts={drafts} blocked_topics_with_drafts={with_drafts} blocked_topics_without_drafts={without_drafts} skipped_existing={existing}".format(
            out=args.out,
            state="updated" if changed else "unchanged",
            drafts=payload["drafts_total"],
            with_drafts=payload["blocked_vote_topics_with_drafts_total"],
            without_drafts=payload["blocked_vote_topics_without_drafts_total"],
            existing=payload["skipped_existing_reviews_total"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
