#!/usr/bin/env python3
"""Generate conservative issue-level review drafts for Andalucia 2026.

Drafts document citizen direction and observed legislative actors from already
reviewed vote signals. They do not score merit, blame, causality or impact.
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
DEFAULT_EXISTING_REVIEWS = Path("etl/data/seeds/andalucia_2026_issue_reviews.json")
DEFAULT_OUT = Path("etl/data/published/andalucia-2026-issue-review-drafts.json")

NO_MERIT_CLAIM_STATUS = "issue_vote_direction_actor_review_no_merit_or_blame"
ELIGIBLE_GAPS = {"missing_citizen_direction", "missing_responsible_actor", "missing_execution_responsible_actor"}
BLOCKED_SCORE_KEYS = {
    "score",
    "impact_score",
    "merit_score",
    "blame_score",
    "accountability_score",
    "responsibility_score",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Andalucia 2026 issue review drafts")
    parser.add_argument("--accountability", default=str(DEFAULT_ACCOUNTABILITY), help="Accountability JSON path")
    parser.add_argument("--existing-reviews", default=str(DEFAULT_EXISTING_REVIEWS), help="Existing issue review seed")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Draft review JSON output path")
    parser.add_argument("--reviewed-at", default="", help="Override reviewed_at/generator date")
    parser.add_argument("--include-reviewed", action="store_true", help="Do not skip topics already in the seed")
    return parser.parse_args()


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def existing_review_topics(payload: dict[str, Any]) -> set[str]:
    return {
        str(row.get("topic_id") or "")
        for row in payload.get("reviews") or []
        if isinstance(row, dict) and str(row.get("topic_id") or "")
    }


def issue_packets(accountability: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in (accountability.get("issue_accountability_packets") or {}).get("packets") or []
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


def reviewed_vote_summary(packet: dict[str, Any]) -> str:
    votes = packet.get("reviewed_vote_samples") or []
    if not votes:
        return "sin voto revisado"
    first = votes[0] if isinstance(votes[0], dict) else {}
    numexp = str(first.get("numexp") or "expediente parlamentario")
    outcome = str(first.get("effect_outcome") or "").replace("_", " ")
    if len(votes) == 1:
        return f"{numexp}: {outcome or 'resultado oficial revisado'}"
    return f"{len(votes)} votos revisados; primer expediente {numexp}: {outcome or 'resultado oficial revisado'}"


def compact_vote_ref(sample: dict[str, Any]) -> dict[str, Any]:
    title = short_text(sample.get("title"), max_chars=180)
    numexp = str(sample.get("numexp") or "")
    outcome = str(sample.get("effect_outcome") or "").replace("_", " ")
    excerpt_parts = [part for part in (numexp, title, outcome) if part]
    return {
        "source_kind": "official_vote_pdf_text",
        "source_id": str(sample.get("review_item_id") or sample.get("vote_event_id") or ""),
        "source_url": str(sample.get("source_url") or ""),
        "source_locator": str(sample.get("vote_event_id") or sample.get("review_item_id") or ""),
        "evidence_excerpt": short_text("; ".join(excerpt_parts), max_chars=220),
    }


def compact_claim_ref(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "observed_legislative_responsibility_claim",
        "source_id": str(sample.get("claim_id") or ""),
        "source_url": str(sample.get("source_url") or ""),
        "source_locator": str(sample.get("claim_id") or ""),
        "evidence_excerpt": short_text(sample.get("statement"), max_chars=220),
    }


def draft_limitations(packet: dict[str, Any]) -> list[str]:
    limitations = [
        "legislative_vote_signal_only",
        "execution_owner_not_reviewed",
        "budget_execution_not_linked",
        "outcome_not_reviewed",
        "causal_impact_not_claimed",
        "merit_blame_not_scored",
    ]
    if int_value(packet.get("reviewed_vote_boja_expected_total")) <= 0:
        limitations.insert(1, "boja_not_expected_for_reviewed_vote_effects")
    return limitations


def eligible_issue_packet(
    packet: dict[str, Any],
    *,
    existing_topics: set[str],
    include_reviewed: bool = False,
) -> tuple[bool, str]:
    topic_id = str(packet.get("topic_id") or "")
    if not topic_id or topic_id == "sin_tema":
        return False, "topic_missing_or_unclassified"
    if topic_id in existing_topics and not include_reviewed:
        return False, "topic_already_has_issue_review"
    open_gaps = {str(gap) for gap in packet.get("open_gaps") or [] if gap}
    if not open_gaps & ELIGIBLE_GAPS:
        return False, "no_direction_or_actor_gap"
    if int_value(packet.get("reviewed_vote_items_total")) <= 0:
        return False, "reviewed_vote_missing"
    if int_value(packet.get("observed_responsibility_claims_total")) <= 0:
        return False, "observed_responsibility_claim_missing"
    if int_value(packet.get("reviewed_vote_boja_expected_total")) > int_value(
        packet.get("reviewed_boja_legal_changes_total")
    ):
        return False, "boja_expected_but_missing"
    return True, ""


def compact_draft_issue_review(packet: dict[str, Any], *, reviewed_at: str) -> dict[str, Any]:
    topic_id = str(packet.get("topic_id") or "")
    topic_label = str(packet.get("topic_label") or topic_id)
    vote_refs = [
        compact_vote_ref(row)
        for row in packet.get("reviewed_vote_samples") or []
        if isinstance(row, dict)
    ][:4]
    claim_refs = [
        compact_claim_ref(row)
        for row in packet.get("observed_responsibility_claim_samples") or []
        if isinstance(row, dict)
    ][:4]
    vote_summary = reviewed_vote_summary(packet)
    observed_claims_total = int_value(packet.get("observed_responsibility_claims_total"))
    return {
        "review_id": f"andalucia-2026-issue-review-draft-{topic_id}-001",
        "topic_id": topic_id,
        "topic_label": topic_label,
        "draft_status": "machine_draft_needs_human_review",
        "review_status": "reviewed_issue_vote_direction_and_actor_partial",
        "claim_status": NO_MERIT_CLAIM_STATUS,
        "interpretation_status": "legislative_vote_actor_signal_documented_execution_outcome_pending",
        "citizen_direction_status": "direction_partially_reviewed_outcome_pending",
        "citizen_direction_label": (
            f"Senal parlamentaria revisada para {topic_label}: {vote_summary}. "
            "Direccion ciudadana pendiente de ejecucion, outcome y revision humana final."
        ),
        "responsible_actor_status": "responsible_actor_partially_observed",
        "responsible_actor_label": (
            f"El paquete contiene {observed_claims_total} claims observados de posicion legislativa "
            "por partido/candidato. Esto observa actores parlamentarios, no ejecucion administrativa ni impacto."
        ),
        "execution_owner_status": "execution_owner_not_reviewed",
        "execution_owner_label": "",
        "budget_execution_status": "budget_execution_not_linked",
        "budget_execution_label": "",
        "outcome_status": "outcome_not_linked",
        "merit_blame_status": "closed_pending_execution_and_outcomes",
        "review_summary": (
            f"Draft machine-assisted para {topic_label}: hay votos oficiales revisados y posiciones "
            "legislativas observadas. La fila solo propone cerrar direccion/actor parlamentario parcial; "
            "no documenta entrega, beneficiarios, ejecucion, outcome, causalidad, merito ni culpa."
        ),
        "review_confidence": "low",
        "reviewed_by": "draft_generator",
        "reviewed_at": reviewed_at,
        "evidence_refs": vote_refs + claim_refs,
        "execution_refs": [],
        "budget_refs": [],
        "open_limitations": draft_limitations(packet),
    }


def unsafe_draft_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    limitations = {str(item) for item in row.get("open_limitations") or [] if isinstance(item, str)}
    if str(row.get("claim_status") or "") != NO_MERIT_CLAIM_STATUS:
        reasons.append("claim_status_not_no_merit_or_blame")
    if str(row.get("citizen_direction_status") or "") != "direction_partially_reviewed_outcome_pending":
        reasons.append("citizen_direction_not_partial")
    if str(row.get("responsible_actor_status") or "") != "responsible_actor_partially_observed":
        reasons.append("responsible_actor_not_partial")
    if str(row.get("execution_owner_status") or "") != "execution_owner_not_reviewed":
        reasons.append("execution_owner_should_remain_unreviewed")
    if str(row.get("budget_execution_status") or "") != "budget_execution_not_linked":
        reasons.append("budget_execution_should_remain_unlinked")
    if str(row.get("outcome_status") or "") != "outcome_not_linked":
        reasons.append("outcome_should_remain_unlinked")
    if "merit_blame_not_scored" not in limitations:
        reasons.append("missing_merit_blame_not_scored_limitation")
    if "causal_impact_not_claimed" not in limitations:
        reasons.append("missing_causal_impact_not_claimed_limitation")
    for key in BLOCKED_SCORE_KEYS:
        if row.get(key) not in (None, "", []):
            reasons.append(f"blocked_score_field:{key}")
    return reasons


def generate_issue_review_drafts(
    accountability: dict[str, Any],
    *,
    existing_topics: set[str],
    reviewed_at: str,
    include_reviewed: bool = False,
) -> dict[str, Any]:
    drafts: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    blocked_topics: list[dict[str, Any]] = []

    for packet in sorted(issue_packets(accountability), key=lambda row: str(row.get("topic_id") or "")):
        eligible, reason = eligible_issue_packet(
            packet,
            existing_topics=existing_topics,
            include_reviewed=include_reviewed,
        )
        if not eligible:
            skipped[reason] += 1
            continue
        draft = compact_draft_issue_review(packet, reviewed_at=reviewed_at)
        unsafe = unsafe_draft_reasons(draft)
        if unsafe:
            skipped["unsafe_draft"] += 1
            blocked_topics.append(
                {
                    "topic_id": draft["topic_id"],
                    "topic_label": draft["topic_label"],
                    "unsafe_reasons": unsafe,
                }
            )
            continue
        drafts.append(draft)

    by_topic = Counter(str(row.get("topic_id") or "") for row in drafts)
    return {
        "schema_version": "andalucia_2026_issue_review_drafts_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "reviewed_at": reviewed_at,
        "status": "drafts_ready" if drafts else "no_drafts",
        "claim_status": "issue_review_assist_only_no_merit_or_blame",
        "drafts_total": len(drafts),
        "draft_topics_total": len(by_topic),
        "drafts_by_topic": [
            {"topic_id": key, "count": count}
            for key, count in sorted(by_topic.items(), key=lambda item: (-item[1], item[0]))
        ],
        "skipped_counts": [
            {"key": key, "count": count}
            for key, count in sorted(skipped.items(), key=lambda item: (-item[1], item[0]))
        ],
        "blocked_topics": blocked_topics,
        "drafts": drafts,
    }


def main() -> int:
    args = parse_args()
    accountability = load_json_object(Path(args.accountability))
    existing_reviews = load_json_object(Path(args.existing_reviews))
    reviewed_at = args.reviewed_at or datetime.now(UTC).date().isoformat()
    payload = generate_issue_review_drafts(
        accountability,
        existing_topics=existing_review_topics(existing_reviews),
        reviewed_at=reviewed_at,
        include_reviewed=bool(args.include_reviewed),
    )
    write_json(Path(args.out), payload)
    print(
        "OK Andalucia 2026 issue review drafts -> {out} (updated); drafts={drafts} topics={topics} status={status}".format(
            out=args.out,
            drafts=payload["drafts_total"],
            topics=payload["draft_topics_total"],
            status=payload["status"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
