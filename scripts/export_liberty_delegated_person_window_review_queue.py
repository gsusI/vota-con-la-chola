#!/usr/bin/env python3
"""Export review queue for delegated person/window remediation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.report_liberty_delegated_person_window_queue import (
    DEFAULT_INSTITUTION_HINT_TERMS,
    _parse_csv_list,
    build_queue_report,
)


STRICT_FAIL_EXIT = 4


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _seed_link_key(method_version: str, row: dict[str, Any]) -> str:
    given = _norm(row.get("link_key"))
    if given:
        return given
    return "|".join(
        [
            method_version,
            _norm(row.get("fragment_id")),
            _norm(row.get("delegating_actor_label")),
            _norm(row.get("delegated_institution_label")),
            _norm(row.get("designated_actor_label")),
            _norm(row.get("source_url")),
        ]
    )


def _load_seed(seed_path: Path) -> dict[str, Any]:
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("seed root must be object")
    return raw


def _seed_index(seed_doc: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    methodology = seed_doc.get("methodology")
    if isinstance(methodology, dict):
        method_version = _norm(methodology.get("method_version")) or "delegated_enforcement_v1"
    else:
        method_version = "delegated_enforcement_v1"
    links = seed_doc.get("links")
    out: dict[str, dict[str, Any]] = {}
    if isinstance(links, list):
        for row in links:
            if not isinstance(row, dict):
                continue
            key = _seed_link_key(method_version, row)
            if key:
                out[key] = row
    return out, method_version


def _is_actionable_reason(reason: str) -> bool:
    reason_norm = _norm(reason)
    if not reason_norm:
        return False
    return reason_norm in {
        "missing_designated_actor",
        "missing_appointment_start_date",
        "invalid_appointment_start_date",
        "invalid_appointment_end_date",
        "appointment_window_inverted",
        "missing_enforcement_evidence_date",
        "invalid_enforcement_evidence_date",
        "institutional_designated_actor",
    }


def build_review_rows(
    *,
    queue_report: dict[str, Any],
    seed_doc: dict[str, Any],
    only_actionable: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed_idx, method_version = _seed_index(seed_doc)
    by_reason: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    actionable_rows_total = 0
    missing_seed_links_total = 0

    queue_rows = queue_report.get("queue_rows")
    if not isinstance(queue_rows, list):
        queue_rows = []

    for raw in queue_rows:
        if not isinstance(raw, dict):
            continue
        link_key = _norm(raw.get("link_key"))
        reasons = raw.get("reasons")
        reasons_list = [str(v) for v in reasons] if isinstance(reasons, list) else []
        actionable = any(_is_actionable_reason(reason) for reason in reasons_list)
        if only_actionable and not actionable:
            continue
        if actionable:
            actionable_rows_total += 1
        for reason in reasons_list:
            token = _norm(reason)
            if token:
                by_reason[token] = int(by_reason.get(token, 0)) + 1

        seed_row = seed_idx.get(link_key)
        if seed_row is None:
            missing_seed_links_total += 1
            seed_row = {}

        row = {
            "link_key": link_key,
            "fragment_id": _norm(raw.get("fragment_id")),
            "norm_id": _norm(raw.get("norm_id")),
            "boe_id": _norm(raw.get("boe_id")),
            "delegating_actor_label": _norm(raw.get("delegating_actor_label")),
            "delegated_institution_label": _norm(raw.get("delegated_institution_label")),
            "designated_role_title": _norm(raw.get("designated_role_title")),
            "current_designated_actor_label": _norm(seed_row.get("designated_actor_label") or raw.get("designated_actor_label")),
            "current_appointment_start_date": _norm(seed_row.get("appointment_start_date") or raw.get("appointment_start_date")),
            "current_appointment_end_date": _norm(seed_row.get("appointment_end_date") or raw.get("appointment_end_date")),
            "current_enforcement_evidence_date": _norm(
                seed_row.get("enforcement_evidence_date") or raw.get("enforcement_evidence_date")
            ),
            "current_source_url": _norm(seed_row.get("source_url") or raw.get("source_url")),
            "current_evidence_quote": _norm(seed_row.get("evidence_quote")),
            "chain_confidence": float(raw.get("chain_confidence") or 0.0),
            "reasons_csv": "|".join(sorted(set(reasons_list))),
            "actionability": "actionable" if actionable else "informational",
            "decision": "",
            "reviewed_designated_actor_label": "",
            "reviewed_appointment_start_date": "",
            "reviewed_appointment_end_date": "",
            "reviewed_enforcement_evidence_date": "",
            "reviewed_source_url": "",
            "reviewed_evidence_quote": "",
            "review_note": "",
        }
        rows.append(row)

    summary = {
        "status": "ok",
        "rows_total": len(rows),
        "actionable_rows_total": actionable_rows_total,
        "missing_seed_links_total": missing_seed_links_total,
        "only_actionable": bool(only_actionable),
        "method_version": method_version,
        "queue_status": _norm(queue_report.get("status")),
        "queue_actionable_rows_total": int(queue_report.get("totals", {}).get("actionable_queue_rows", 0)),
        "by_reason": by_reason,
    }
    return rows, summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
        "current_evidence_quote",
        "chain_confidence",
        "reasons_csv",
        "actionability",
        "decision",
        "reviewed_designated_actor_label",
        "reviewed_appointment_start_date",
        "reviewed_appointment_end_date",
        "reviewed_enforcement_evidence_date",
        "reviewed_source_url",
        "reviewed_evidence_quote",
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
    ap.add_argument("--only-actionable", action="store_true")
    ap.add_argument("--strict-empty-actionable", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seed_path = Path(args.seed)
    seed_doc = _load_seed(seed_path)

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

    rows, summary = build_review_rows(
        queue_report=queue_report,
        seed_doc=seed_doc,
        only_actionable=bool(args.only_actionable),
    )

    out_csv = Path(args.out)
    _write_csv(out_csv, rows)
    summary_payload = {
        "db_path": str(Path(args.db)),
        "seed_path": str(seed_path),
        "queue": {
            "status": _norm(queue_report.get("status")),
            "totals": queue_report.get("totals", {}),
            "strict_fail_reasons": queue_report.get("strict_fail_reasons", []),
        },
        "review_queue": summary,
    }
    out_json = Path(args.summary_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))

    if bool(args.strict_empty_actionable) and int(summary.get("actionable_rows_total", 0)) > 0:
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
