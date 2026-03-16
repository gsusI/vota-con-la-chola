#!/usr/bin/env python3
"""Export pending delegated auto-review rows into a focused manual resolution queue."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except Exception:
        return int(default)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def _top_candidates_by_link(
    assist_rows: list[dict[str, str]], *, top_n: int
) -> dict[str, list[dict[str, str]]]:
    by_link: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in assist_rows:
        link_key = _norm(row.get("link_key"))
        if not link_key:
            continue
        by_link[link_key].append(row)

    for key in by_link:
        by_link[key].sort(
            key=lambda row: (
                -_to_int(row.get("candidate_score")),
                _to_int(row.get("candidate_rank_for_link"), default=999999),
                _norm(row.get("candidate_boe_id")),
            )
        )
        by_link[key] = by_link[key][: max(1, int(top_n))]
    return by_link


def _candidate_stub(row: dict[str, str]) -> dict[str, Any]:
    return {
        "candidate_rank_for_link": _to_int(row.get("candidate_rank_for_link"), 0),
        "candidate_boe_id": _norm(row.get("candidate_boe_id")),
        "candidate_score": _to_int(row.get("candidate_score"), 0),
        "candidate_relevance_bucket": _norm(row.get("candidate_relevance_bucket")),
        "role_token_overlap": _to_int(row.get("role_token_overlap"), 0),
        "institution_token_overlap": _to_int(row.get("institution_token_overlap"), 0),
        "candidate_title": _norm(row.get("candidate_title")),
        "candidate_doc_url": _norm(row.get("candidate_doc_url")),
        "candidate_publication_date_iso": _norm(row.get("candidate_publication_date_iso")),
    }


def _capture_query(role: str, institution: str) -> str:
    role_t = _norm(role)
    inst_t = _norm(institution)
    if role_t and inst_t:
        return f"nombramiento {role_t} {inst_t}"
    if role_t:
        return f"nombramiento {role_t}"
    if inst_t:
        return f"nombramiento {inst_t}"
    return "nombramiento"


def build_pending_resolution_rows(
    *,
    auto_review_rows: list[dict[str, str]],
    assist_rows: list[dict[str, str]],
    top_candidates_per_link: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    top_by_link = _top_candidates_by_link(assist_rows, top_n=int(top_candidates_per_link))

    out_rows: list[dict[str, str]] = []
    reasons = Counter()
    links_with_candidates = 0

    for row in auto_review_rows:
        decision = _norm(row.get("decision")).lower()
        if decision != "pending":
            continue

        link_key = _norm(row.get("link_key"))
        top_candidates = top_by_link.get(link_key, [])
        if top_candidates:
            links_with_candidates += 1

        pending_reason = _norm(row.get("review_note"))
        reasons[pending_reason or "(sin_razon)"] += 1

        top_candidates_json = json.dumps([_candidate_stub(c) for c in top_candidates], ensure_ascii=False)

        out_rows.append(
            {
                "link_key": link_key,
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
                "current_evidence_quote": _norm(row.get("current_evidence_quote")),
                "chain_confidence": _norm(row.get("chain_confidence")),
                "reasons_csv": _norm(row.get("reasons_csv")),
                "actionability": _norm(row.get("actionability")),
                "decision": "pending",
                "reviewed_designated_actor_label": _norm(row.get("reviewed_designated_actor_label")),
                "reviewed_appointment_start_date": _norm(row.get("reviewed_appointment_start_date")),
                "reviewed_appointment_end_date": _norm(row.get("reviewed_appointment_end_date")),
                "reviewed_enforcement_evidence_date": _norm(row.get("reviewed_enforcement_evidence_date")),
                "reviewed_source_url": _norm(row.get("reviewed_source_url")),
                "reviewed_evidence_quote": _norm(row.get("reviewed_evidence_quote")),
                "review_note": pending_reason,
                "pending_reason": pending_reason,
                "top_candidates_count": str(len(top_candidates)),
                "top_candidates_json": top_candidates_json,
                "capture_query_primary": _capture_query(
                    _norm(row.get("designated_role_title")),
                    _norm(row.get("delegated_institution_label")),
                ),
                "capture_query_secondary": _capture_query(
                    _norm(row.get("delegated_institution_label")),
                    "",
                ),
                "resolution_note": "",
            }
        )

    out_rows.sort(key=lambda r: (_norm(r.get("delegated_institution_label")), _norm(r.get("link_key"))))

    summary = {
        "status": "ok",
        "pending_rows_total": len(out_rows),
        "links_with_candidates_total": int(links_with_candidates),
        "top_candidates_per_link": int(top_candidates_per_link),
        "pending_reason_counts": dict(sorted(reasons.items())),
    }
    return out_rows, summary


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
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
        "pending_reason",
        "top_candidates_count",
        "top_candidates_json",
        "capture_query_primary",
        "capture_query_secondary",
        "resolution_note",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _norm(row.get(k)) for k in fields})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--auto-review-csv",
        default="docs/etl/sprints/AI-OPS-285/exports/liberty_delegated_person_window_auto_review_decisions_role_aligned_latest.csv",
    )
    ap.add_argument(
        "--review-assist-csv",
        default="docs/etl/sprints/AI-OPS-285/exports/liberty_delegated_person_window_review_assist_deep_latest.csv",
    )
    ap.add_argument("--top-candidates-per-link", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    auto_rows = _read_csv(Path(args.auto_review_csv))
    assist_rows = _read_csv(Path(args.review_assist_csv))

    rows, summary = build_pending_resolution_rows(
        auto_review_rows=auto_rows,
        assist_rows=assist_rows,
        top_candidates_per_link=int(args.top_candidates_per_link),
    )

    out_csv = Path(args.out)
    _write_csv(out_csv, rows)

    payload = {
        "auto_review_csv": _norm(args.auto_review_csv),
        "review_assist_csv": _norm(args.review_assist_csv),
        "out_csv": str(out_csv),
        "summary": summary,
    }
    out_json = Path(args.summary_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
