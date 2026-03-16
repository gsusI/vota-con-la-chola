#!/usr/bin/env python3
"""Build actionable queue for delegated enforcement person/window gaps."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db


STRICT_FAIL_EXIT = 4
DEFAULT_INSTITUTION_HINT_TERMS = (
    "ministerio,direccion,dirección,agencia,delegacion,delegación,delegaciones,"
    "subdelegacion,subdelegación,subdelegaciones,inspeccion,inspección,organismo,"
    "gobierno,dgt,aeat,itss"
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_lc(value: Any) -> str:
    return _norm(value).lower()


def _parse_csv_list(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        value = token.strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _parse_iso_date(raw: str) -> datetime | None:
    value = _norm(raw)
    if not value:
        return None
    value10 = value[:10]
    try:
        return datetime.strptime(value10, "%Y-%m-%d")
    except ValueError:
        return None


def _looks_institutional(label: str, hints: list[str]) -> bool:
    value = _norm_lc(label)
    if not value:
        return False
    return any(term in value for term in hints)


def _is_accepted_non_nominative_actor(
    *,
    designated_actor_label: str,
    evidence_quote: str,
) -> bool:
    actor = _norm_lc(designated_actor_label)
    quote = _norm_lc(evidence_quote)
    if not actor or "(" not in actor or ")" not in actor:
        return False
    return "approved_non_nominative_unit_from_" in quote


def _pick_latest_rows_by_fragment(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    # Keep one effective row per fragment (latest updated_at), preserving raw rows for observability.
    ordered = sorted(
        rows,
        key=lambda r: (
            _norm(r.get("updated_at")),
            _norm(r.get("link_key")),
        ),
        reverse=True,
    )
    keep: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in ordered:
        fragment_id = _norm(row.get("fragment_id"))
        if not fragment_id:
            continue
        if fragment_id in seen:
            continue
        seen.add(fragment_id)
        keep.append(row)
    dropped = max(0, len(rows) - len(keep))
    return keep, dropped


def build_queue_report(
    conn,
    *,
    limit: int,
    institution_hint_terms: list[str],
    max_actionable_rows: int,
    dedupe_fragment_latest: bool,
) -> dict[str, Any]:
    raw_rows = conn.execute(
        """
        SELECT
          l.link_key,
          l.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          COALESCE(l.delegating_actor_label, '') AS delegating_actor_label,
          COALESCE(l.delegated_institution_label, '') AS delegated_institution_label,
          COALESCE(l.designated_role_title, '') AS designated_role_title,
          COALESCE(l.designated_actor_label, '') AS designated_actor_label,
          COALESCE(l.appointment_start_date, '') AS appointment_start_date,
          COALESCE(l.appointment_end_date, '') AS appointment_end_date,
          COALESCE(l.enforcement_action_label, '') AS enforcement_action_label,
          COALESCE(l.enforcement_evidence_date, '') AS enforcement_evidence_date,
          COALESCE(l.source_url, '') AS source_url,
          COALESCE(l.evidence_quote, '') AS evidence_quote,
          COALESCE(l.updated_at, '') AS updated_at,
          COALESCE(l.chain_confidence, 0.0) AS chain_confidence
        FROM liberty_delegated_enforcement_links l
        JOIN legal_norm_fragments f ON f.fragment_id = l.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        ORDER BY l.chain_confidence ASC, l.fragment_id ASC, l.link_key ASC
        """
    ).fetchall()
    rows = [dict(r) for r in raw_rows]
    dropped_duplicate_rows = 0
    if bool(dedupe_fragment_latest):
        rows, dropped_duplicate_rows = _pick_latest_rows_by_fragment(rows)

    by_reason: dict[str, int] = {}
    queue_rows_all: list[dict[str, Any]] = []
    missing_designated_actor_total = 0
    institutional_designated_actor_total = 0
    missing_appointment_start_total = 0
    invalid_or_inverted_window_total = 0
    missing_enforcement_evidence_total = 0

    for row in rows:
        designated_actor_label = _norm(row["designated_actor_label"])
        appointment_start = _norm(row["appointment_start_date"])
        appointment_end = _norm(row["appointment_end_date"])
        enforcement_evidence_date = _norm(row["enforcement_evidence_date"])
        evidence_quote = _norm(row["evidence_quote"])

        reasons: list[str] = []
        if not designated_actor_label:
            reasons.append("missing_designated_actor")
            missing_designated_actor_total += 1
        elif _looks_institutional(designated_actor_label, institution_hint_terms) and not _is_accepted_non_nominative_actor(
            designated_actor_label=designated_actor_label,
            evidence_quote=evidence_quote,
        ):
            reasons.append("institutional_designated_actor")
            institutional_designated_actor_total += 1

        start_dt = _parse_iso_date(appointment_start)
        end_dt = _parse_iso_date(appointment_end)
        if not appointment_start:
            reasons.append("missing_appointment_start_date")
            missing_appointment_start_total += 1
        elif start_dt is None:
            reasons.append("invalid_appointment_start_date")
            invalid_or_inverted_window_total += 1

        if appointment_end and end_dt is None:
            reasons.append("invalid_appointment_end_date")
            invalid_or_inverted_window_total += 1
        elif start_dt is not None and end_dt is not None and end_dt < start_dt:
            reasons.append("appointment_window_inverted")
            invalid_or_inverted_window_total += 1

        evidence_dt = _parse_iso_date(enforcement_evidence_date)
        if not enforcement_evidence_date:
            reasons.append("missing_enforcement_evidence_date")
            missing_enforcement_evidence_total += 1
        elif evidence_dt is None:
            reasons.append("invalid_enforcement_evidence_date")

        if not reasons:
            continue
        for reason in reasons:
            by_reason[reason] = int(by_reason.get(reason, 0)) + 1

        queue_rows_all.append(
            {
                "link_key": _norm(row["link_key"]),
                "fragment_id": _norm(row["fragment_id"]),
                "norm_id": _norm(row["norm_id"]),
                "boe_id": _norm(row["boe_id"]),
                "norm_title": _norm(row["norm_title"]),
                "fragment_label": _norm(row["fragment_label"]),
                "delegating_actor_label": _norm(row["delegating_actor_label"]),
                "delegated_institution_label": _norm(row["delegated_institution_label"]),
                "designated_role_title": _norm(row["designated_role_title"]),
                "designated_actor_label": designated_actor_label,
                "appointment_start_date": appointment_start,
                "appointment_end_date": appointment_end,
                "enforcement_action_label": _norm(row["enforcement_action_label"]),
                "enforcement_evidence_date": enforcement_evidence_date,
                "chain_confidence": float(row["chain_confidence"] or 0.0),
                "source_url": _norm(row["source_url"]),
                "evidence_quote": evidence_quote,
                "reasons": reasons,
            }
        )

    actionable_queue_rows = len(queue_rows_all)
    queue_rows = queue_rows_all[: max(0, int(limit))] if int(limit) > 0 else queue_rows_all

    checks = {
        "delegated_links_present": len(rows) > 0,
        "actionable_queue_materialized": actionable_queue_rows >= 0,
        "max_actionable_rows_gate": int(max_actionable_rows) < 0 or actionable_queue_rows <= int(max_actionable_rows),
        "fragment_latest_dedupe_applied": bool(dedupe_fragment_latest),
    }
    gate_passed = all(checks.values())

    strict_fail_reasons: list[str] = []
    if not checks["delegated_links_present"]:
        strict_fail_reasons.append("no_delegated_links")
    if not checks["max_actionable_rows_gate"]:
        strict_fail_reasons.append("actionable_rows_above_threshold")

    if not checks["delegated_links_present"]:
        status = "failed"
    elif gate_passed:
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "strict_fail_reasons": strict_fail_reasons,
        "institution_hint_terms": institution_hint_terms,
        "gate": {
            "passed": gate_passed,
            "thresholds": {
                "max_actionable_rows": int(max_actionable_rows),
            },
        },
        "checks": checks,
        "totals": {
            "links_total_raw": len(raw_rows),
            "links_total_effective": len(rows),
            "links_total": len(rows),
            "duplicate_rows_dropped_total": int(dropped_duplicate_rows),
            "actionable_queue_rows": actionable_queue_rows,
            "missing_designated_actor_total": missing_designated_actor_total,
            "institutional_designated_actor_total": institutional_designated_actor_total,
            "missing_appointment_start_total": missing_appointment_start_total,
            "invalid_or_inverted_window_total": invalid_or_inverted_window_total,
            "missing_enforcement_evidence_total": missing_enforcement_evidence_total,
        },
        "by_reason": by_reason,
        "queue_rows": queue_rows,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "link_key",
        "fragment_id",
        "norm_id",
        "boe_id",
        "norm_title",
        "fragment_label",
        "delegating_actor_label",
        "delegated_institution_label",
        "designated_role_title",
        "designated_actor_label",
        "appointment_start_date",
        "appointment_end_date",
        "enforcement_action_label",
        "enforcement_evidence_date",
        "chain_confidence",
        "source_url",
        "evidence_quote",
        "reasons",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["reasons"] = "|".join(row.get("reasons", []))
            writer.writerow(out)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--institution-hint-terms", default=DEFAULT_INSTITUTION_HINT_TERMS)
    ap.add_argument("--max-actionable-rows", type=int, default=-1)
    ap.add_argument("--dedupe-fragment-latest", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--queue-csv-out", default="")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    conn = open_db(Path(args.db))
    try:
        report = build_queue_report(
            conn,
            limit=int(args.limit),
            institution_hint_terms=_parse_csv_list(args.institution_hint_terms),
            max_actionable_rows=int(args.max_actionable_rows),
            dedupe_fragment_latest=bool(args.dedupe_fragment_latest),
        )
    finally:
        conn.close()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if str(args.queue_csv_out or "").strip():
        _write_csv(Path(args.queue_csv_out), list(report.get("queue_rows", [])))

    if args.strict and str(report.get("status")) != "ok":
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
