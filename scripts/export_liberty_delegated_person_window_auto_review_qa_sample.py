#!/usr/bin/env python3
"""Export a stratified manual-QA sample for delegated auto-review approvals."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
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


def _parse_boe_id_from_review_note(review_note: str) -> str:
    token = _norm(review_note)
    if not token:
        return ""
    match = re.search(
        r"approved(?:_non_nominative_unit)?_from_(BOE-[A-Z]-\d+-\d+)",
        token,
    )
    if match:
        return _norm(match.group(1))
    return ""


def _assist_indexes(
    assist_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, list[dict[str, str]]]]:
    by_link_and_boe: dict[tuple[str, str], dict[str, str]] = {}
    by_link: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in assist_rows:
        link_key = _norm(row.get("link_key"))
        if not link_key:
            continue
        boe_id = _norm(row.get("candidate_boe_id"))
        if boe_id:
            by_link_and_boe[(link_key, boe_id)] = row
        by_link[link_key].append(row)

    for key in by_link:
        by_link[key].sort(
            key=lambda item: (
                -_to_int(item.get("candidate_score")),
                _to_int(item.get("candidate_rank_for_link"), default=999999),
                _norm(item.get("candidate_boe_id")),
            )
        )
    return by_link_and_boe, by_link


def _candidate_for_decision(
    decision_row: dict[str, str],
    *,
    by_link_and_boe: dict[tuple[str, str], dict[str, str]],
    by_link: dict[str, list[dict[str, str]]],
) -> dict[str, str]:
    link_key = _norm(decision_row.get("link_key"))
    review_note = _norm(decision_row.get("review_note"))
    boe_id = _parse_boe_id_from_review_note(review_note)
    if link_key and boe_id:
        hit = by_link_and_boe.get((link_key, boe_id))
        if hit is not None:
            return hit
    if link_key and by_link.get(link_key):
        return by_link[link_key][0]
    return {}


def _institution_key(row: dict[str, str]) -> str:
    value = _norm(row.get("delegated_institution_label"))
    return value if value else "(sin_institucion)"


def _sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            -_to_int(row.get("selected_candidate_score")),
            _norm(row.get("selected_candidate_relevance_bucket")),
            _norm(row.get("link_key")),
        ),
    )


def stratified_sample(rows: list[dict[str, str]], *, sample_size: int) -> list[dict[str, str]]:
    if sample_size < 1:
        raise ValueError("sample_size must be >= 1")
    if len(rows) <= sample_size:
        return _sort_rows(rows)

    by_inst: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_inst[_institution_key(row)].append(row)
    for key in by_inst:
        by_inst[key] = _sort_rows(by_inst[key])

    institutions = sorted(by_inst.keys(), key=lambda key: (-len(by_inst[key]), key.lower(), key))

    selected: list[dict[str, str]] = []
    used: set[str] = set()

    # First pass: at most one row per institution to guarantee stratification.
    for inst in institutions:
        if len(selected) >= sample_size:
            break
        bucket = by_inst[inst]
        if not bucket:
            continue
        row = bucket.pop(0)
        key = _norm(row.get("link_key"))
        if key in used:
            continue
        used.add(key)
        selected.append(row)

    # Round-robin over remaining rows until sample_size is reached.
    while len(selected) < sample_size:
        progress = False
        for inst in institutions:
            if len(selected) >= sample_size:
                break
            bucket = by_inst[inst]
            while bucket:
                row = bucket.pop(0)
                key = _norm(row.get("link_key"))
                if key in used:
                    continue
                used.add(key)
                selected.append(row)
                progress = True
                break
        if not progress:
            break

    return selected


def build_qa_sample_rows(
    *,
    auto_review_rows: list[dict[str, str]],
    assist_rows: list[dict[str, str]],
    sample_size: int,
    only_approved: bool,
    review_note_contains: str = "",
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    by_link_and_boe, by_link = _assist_indexes(assist_rows)

    base_rows: list[dict[str, str]] = []
    note_filter = _norm(review_note_contains).lower()
    rows_excluded_by_review_note_filter_total = 0
    for row in auto_review_rows:
        decision = _norm(row.get("decision")).lower()
        if only_approved and decision != "approved":
            continue
        if note_filter and note_filter not in _norm(row.get("review_note")).lower():
            rows_excluded_by_review_note_filter_total += 1
            continue
        candidate = _candidate_for_decision(row, by_link_and_boe=by_link_and_boe, by_link=by_link)
        boe_from_note = _parse_boe_id_from_review_note(_norm(row.get("review_note")))
        selected_boe_id = _norm(candidate.get("candidate_boe_id")) or boe_from_note

        base_rows.append(
            {
                "qa_sample_rank": "",
                "qa_stratum_institution": _institution_key(row),
                "auto_decision": _norm(row.get("decision")),
                "link_key": _norm(row.get("link_key")),
                "fragment_id": _norm(row.get("fragment_id")),
                "norm_id": _norm(row.get("norm_id")),
                "boe_id": _norm(row.get("boe_id")),
                "delegating_actor_label": _norm(row.get("delegating_actor_label")),
                "delegated_institution_label": _norm(row.get("delegated_institution_label")),
                "designated_role_title": _norm(row.get("designated_role_title")),
                "reviewed_designated_actor_label": _norm(row.get("reviewed_designated_actor_label")),
                "reviewed_enforcement_evidence_date": _norm(row.get("reviewed_enforcement_evidence_date")),
                "reviewed_source_url": _norm(row.get("reviewed_source_url")),
                "reviewed_evidence_quote": _norm(row.get("reviewed_evidence_quote")),
                "review_note": _norm(row.get("review_note")),
                "selected_candidate_boe_id": selected_boe_id,
                "selected_candidate_score": _norm(candidate.get("candidate_score")),
                "selected_candidate_relevance_bucket": _norm(candidate.get("candidate_relevance_bucket")),
                "selected_candidate_role_token_overlap": _norm(candidate.get("role_token_overlap")),
                "selected_candidate_institution_token_overlap": _norm(candidate.get("institution_token_overlap")),
                "selected_candidate_department": _norm(candidate.get("candidate_department")),
                "selected_candidate_title": _norm(candidate.get("candidate_title")),
                "selected_candidate_person_hint": _norm(candidate.get("candidate_person_hint")),
                "selected_candidate_publication_date_iso": _norm(candidate.get("candidate_publication_date_iso")),
                "selected_candidate_doc_url": _norm(candidate.get("candidate_doc_url")),
                "qa_decision": "",
                "qa_note": "",
            }
        )

    sampled = stratified_sample(base_rows, sample_size=sample_size)
    for idx, row in enumerate(sampled, start=1):
        row["qa_sample_rank"] = str(idx)

    by_institution_total: dict[str, int] = defaultdict(int)
    by_institution_sampled: dict[str, int] = defaultdict(int)
    for row in base_rows:
        by_institution_total[_institution_key(row)] += 1
    for row in sampled:
        by_institution_sampled[_institution_key(row)] += 1

    summary: dict[str, Any] = {
        "status": "ok",
        "rows_considered_total": len(base_rows),
        "sample_rows_total": len(sampled),
        "sample_size_requested": int(sample_size),
        "only_approved": bool(only_approved),
        "review_note_contains": note_filter,
        "rows_excluded_by_review_note_filter_total": rows_excluded_by_review_note_filter_total,
        "institutions_total": len(by_institution_total),
        "institutions_sampled_total": len(by_institution_sampled),
        "rows_total_by_institution": dict(sorted(by_institution_total.items())),
        "sample_rows_by_institution": dict(sorted(by_institution_sampled.items())),
        "sample_covers_all_rows": len(sampled) == len(base_rows),
    }
    return sampled, summary


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "qa_sample_rank",
        "qa_stratum_institution",
        "auto_decision",
        "link_key",
        "fragment_id",
        "norm_id",
        "boe_id",
        "delegating_actor_label",
        "delegated_institution_label",
        "designated_role_title",
        "reviewed_designated_actor_label",
        "reviewed_enforcement_evidence_date",
        "reviewed_source_url",
        "reviewed_evidence_quote",
        "review_note",
        "selected_candidate_boe_id",
        "selected_candidate_score",
        "selected_candidate_relevance_bucket",
        "selected_candidate_role_token_overlap",
        "selected_candidate_institution_token_overlap",
        "selected_candidate_department",
        "selected_candidate_title",
        "selected_candidate_person_hint",
        "selected_candidate_publication_date_iso",
        "selected_candidate_doc_url",
        "qa_decision",
        "qa_note",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _norm(row.get(k)) for k in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--auto-review-csv",
        default="docs/etl/sprints/AI-OPS-282/exports/liberty_delegated_person_window_auto_review_decisions_latest.csv",
    )
    ap.add_argument(
        "--review-assist-csv",
        default="docs/etl/sprints/AI-OPS-281/exports/liberty_delegated_person_window_review_assist_latest.csv",
    )
    ap.add_argument("--sample-size", type=int, default=8)
    ap.add_argument("--include-non-approved", action="store_true")
    ap.add_argument(
        "--review-note-contains",
        default="",
        help="optional lowercase/uppercase-insensitive substring filter on review_note",
    )
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out", required=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    auto_review_rows = _read_csv(Path(args.auto_review_csv))
    assist_rows = _read_csv(Path(args.review_assist_csv))

    rows, summary = build_qa_sample_rows(
        auto_review_rows=auto_review_rows,
        assist_rows=assist_rows,
        sample_size=int(args.sample_size),
        only_approved=not bool(args.include_non_approved),
        review_note_contains=_norm(args.review_note_contains),
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
