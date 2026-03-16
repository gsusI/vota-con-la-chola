#!/usr/bin/env python3
"""Export prioritized scraping targets for delegated person/window backlog."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_liberty_delegated_person_window_review_queue import build_review_rows
from scripts.report_liberty_delegated_person_window_queue import (
    DEFAULT_INSTITUTION_HINT_TERMS,
    _parse_csv_list,
    build_queue_report,
)

STRICT_FAIL_EXIT = 4


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _reasons_set(raw: str) -> set[str]:
    return {token for token in (_norm(raw).split("|")) if token}


def _priority_score(reasons: set[str], chain_confidence: float) -> int:
    score = 0
    if "missing_designated_actor" in reasons:
        score += 40
    if "institutional_designated_actor" in reasons:
        score += 30
    if "missing_enforcement_evidence_date" in reasons:
        score += 20
    if "missing_appointment_start_date" in reasons:
        score += 10
    if "invalid_appointment_start_date" in reasons or "invalid_appointment_end_date" in reasons:
        score += 10
    if "appointment_window_inverted" in reasons:
        score += 15
    # Lower confidence rows are treated as more fragile and get a small bump.
    if chain_confidence < 0.65:
        score += 5
    return score


def _packet_key(institution: str) -> str:
    token = _norm(institution).lower()
    compact = "".join(ch if ch.isalnum() else "-" for ch in token).strip("-")
    return compact or "sin-institucion"


def _search_query_primary(row: dict[str, Any]) -> str:
    return (
        f'site:boe.es "{_norm(row.get("delegated_institution_label"))}" '
        f'"{_norm(row.get("designated_role_title"))}" nombramiento'
    )


def _search_query_secondary(row: dict[str, Any]) -> str:
    boe_id = _norm(row.get("boe_id"))
    enforcement_action = _norm(row.get("enforcement_action_label"))
    role = _norm(row.get("designated_role_title"))
    token = enforcement_action or role
    if boe_id:
        return f'site:boe.es "{boe_id}" "{token}" resolucion'
    return f'site:boe.es "{token}" resolucion sancionadora'


def _scrape_goal(reasons: set[str]) -> str:
    parts: list[str] = []
    if "missing_designated_actor" in reasons or "institutional_designated_actor" in reasons:
        parts.append("identificar persona titular del cargo con nombramiento oficial")
    if "missing_enforcement_evidence_date" in reasons:
        parts.append("capturar fecha y evidencia primaria de acto de enforcement")
    if "missing_appointment_start_date" in reasons:
        parts.append("capturar fecha de inicio del nombramiento")
    if not parts:
        return "verificar trazabilidad persona/cargo"
    return "; ".join(parts)


def build_scrape_targets(
    *,
    review_rows: list[dict[str, Any]],
    min_priority_score: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    by_reason: dict[str, int] = {}
    by_packet: dict[str, int] = {}

    for row in review_rows:
        reasons = _reasons_set(_norm(row.get("reasons_csv")))
        chain_confidence = float(row.get("chain_confidence") or 0.0)
        priority = _priority_score(reasons, chain_confidence)
        if priority < int(min_priority_score):
            continue

        for reason in reasons:
            by_reason[reason] = int(by_reason.get(reason, 0)) + 1

        packet_key = _packet_key(_norm(row.get("delegated_institution_label")))
        by_packet[packet_key] = int(by_packet.get(packet_key, 0)) + 1

        target = {
            "link_key": _norm(row.get("link_key")),
            "packet_key": packet_key,
            "priority_score": priority,
            "fragment_id": _norm(row.get("fragment_id")),
            "norm_id": _norm(row.get("norm_id")),
            "boe_id": _norm(row.get("boe_id")),
            "delegating_actor_label": _norm(row.get("delegating_actor_label")),
            "delegated_institution_label": _norm(row.get("delegated_institution_label")),
            "designated_role_title": _norm(row.get("designated_role_title")),
            "current_designated_actor_label": _norm(row.get("current_designated_actor_label")),
            "current_appointment_start_date": _norm(row.get("current_appointment_start_date")),
            "current_appointment_end_date": _norm(row.get("current_appointment_end_date")),
            "current_enforcement_evidence_date": _norm(row.get("current_enforcement_evidence_date")),
            "current_source_url": _norm(row.get("current_source_url")),
            "reasons_csv": "|".join(sorted(reasons)),
            "scrape_goal": _scrape_goal(reasons),
            "search_query_primary": _search_query_primary(row),
            "search_query_secondary": _search_query_secondary(row),
            "suggested_source_1": "https://www.boe.es/",
            "suggested_source_2": _norm(row.get("current_source_url")),
            "review_status": "pending",
            "review_note": "",
        }
        targets.append(target)

    targets.sort(
        key=lambda item: (
            -int(item.get("priority_score") or 0),
            _norm(item.get("delegated_institution_label")),
            _norm(item.get("link_key")),
        )
    )
    for idx, row in enumerate(targets, start=1):
        row["priority_rank"] = idx

    summary = {
        "status": "ok",
        "targets_total": len(targets),
        "packets_total": len(by_packet),
        "min_priority_score": int(min_priority_score),
        "by_reason": by_reason,
        "by_packet": by_packet,
        "top_priority_score": int(targets[0]["priority_score"]) if targets else 0,
        "lowest_priority_score": int(targets[-1]["priority_score"]) if targets else 0,
    }
    return targets, summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "priority_rank",
        "priority_score",
        "packet_key",
        "link_key",
        "fragment_id",
        "norm_id",
        "boe_id",
        "delegating_actor_label",
        "delegated_institution_label",
        "designated_role_title",
        "current_designated_actor_label",
        "current_appointment_start_date",
        "current_appointment_end_date",
        "current_enforcement_evidence_date",
        "current_source_url",
        "reasons_csv",
        "scrape_goal",
        "search_query_primary",
        "search_query_secondary",
        "suggested_source_1",
        "suggested_source_2",
        "review_status",
        "review_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/liberty_delegated_enforcement_seed_v1.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--institution-hint-terms", default=DEFAULT_INSTITUTION_HINT_TERMS)
    ap.add_argument("--min-priority-score", type=int, default=1)
    ap.add_argument("--strict-min-targets", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seed_path = Path(args.seed)
    seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))

    conn = open_db(Path(args.db))
    try:
        queue_report = build_queue_report(
            conn,
            limit=int(args.limit),
            institution_hint_terms=_parse_csv_list(args.institution_hint_terms),
            max_actionable_rows=-1,
        )
    finally:
        conn.close()

    review_rows, review_summary = build_review_rows(
        queue_report=queue_report,
        seed_doc=seed_doc,
        only_actionable=True,
    )
    targets, scrape_summary = build_scrape_targets(
        review_rows=review_rows,
        min_priority_score=int(args.min_priority_score),
    )

    out_csv = Path(args.out)
    _write_csv(out_csv, targets)

    payload = {
        "db_path": str(Path(args.db)),
        "seed_path": str(seed_path),
        "queue": {
            "status": _norm(queue_report.get("status")),
            "totals": queue_report.get("totals", {}),
            "strict_fail_reasons": queue_report.get("strict_fail_reasons", []),
        },
        "review_queue": review_summary,
        "scrape_targets": scrape_summary,
    }

    out_json = Path(args.summary_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if int(args.strict_min_targets) > 0 and int(scrape_summary.get("targets_total", 0)) < int(args.strict_min_targets):
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
