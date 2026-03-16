#!/usr/bin/env python3
"""Rotate labels from historical programas precision samples into a fresh sample."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


STRICT_FAIL_EXIT = 4
VALID_LABELS = {"true_positive", "false_positive"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-in", required=True, help="Fresh sample CSV to enrich")
    parser.add_argument(
        "--labels-in",
        required=True,
        action="append",
        help="Historical labeled CSV (repeatable; first wins on conflicts)",
    )
    parser.add_argument("--out", required=True, help="Output labeled CSV path")
    parser.add_argument("--summary-out", default="", help="Optional JSON summary path")
    parser.add_argument(
        "--max-unlabeled",
        type=int,
        default=-1,
        help="Strict threshold for remaining unlabeled rows (-1 disables)",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on strict failures")
    return parser.parse_args(argv)


def _norm_label(raw: Any) -> str:
    return str(raw or "").strip().lower()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _build_label_map(paths: list[Path]) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], int]:
    label_map: dict[str, dict[str, str]] = {}
    conflicts: list[dict[str, str]] = []
    invalid_labels = 0
    for path in paths:
        for row in _load_csv(path):
            evidence_id = str(row.get("evidence_id") or "").strip()
            if not evidence_id:
                continue
            label = _norm_label(row.get("manual_label"))
            if not label:
                continue
            if label not in VALID_LABELS:
                invalid_labels += 1
                continue
            note = str(row.get("manual_note") or "").strip()
            new_payload = {
                "manual_label": label,
                "manual_note": note,
                "source_file": path.as_posix(),
            }
            if evidence_id in label_map:
                prev = label_map[evidence_id]
                if str(prev.get("manual_label")) != label:
                    conflicts.append(
                        {
                            "evidence_id": evidence_id,
                            "kept_label": str(prev.get("manual_label") or ""),
                            "kept_source_file": str(prev.get("source_file") or ""),
                            "dropped_label": label,
                            "dropped_source_file": path.as_posix(),
                        }
                    )
                continue
            label_map[evidence_id] = new_payload
    return label_map, conflicts, invalid_labels


def _carry_forward(
    *,
    sample_rows: list[dict[str, str]],
    label_map: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    out_rows: list[dict[str, str]] = []
    pre_labeled = 0
    carried = 0
    unresolved = 0
    invalid_sample_labels = 0
    by_party: dict[str, dict[str, int]] = {}
    carried_ids: list[str] = []
    unresolved_ids: list[str] = []

    for row in sample_rows:
        out = dict(row)
        party = str(out.get("party_name") or "").strip() or "unknown"
        if party not in by_party:
            by_party[party] = {"total": 0, "labeled": 0, "unlabeled": 0, "carried": 0}
        by_party[party]["total"] += 1

        evidence_id = str(out.get("evidence_id") or "").strip()
        existing = _norm_label(out.get("manual_label"))
        has_existing = bool(existing)
        if has_existing and existing not in VALID_LABELS:
            invalid_sample_labels += 1

        if has_existing and existing in VALID_LABELS:
            pre_labeled += 1
            by_party[party]["labeled"] += 1
            out_rows.append(out)
            continue

        hist = label_map.get(evidence_id)
        if hist is not None:
            carried += 1
            carried_ids.append(evidence_id)
            out["manual_label"] = str(hist.get("manual_label") or "")
            note = str(hist.get("manual_note") or "").strip()
            src = Path(str(hist.get("source_file") or "")).name
            carry_note = f"carry_forward:{src}"
            out["manual_note"] = f"{note} | {carry_note}".strip(" |") if note else carry_note
            by_party[party]["labeled"] += 1
            by_party[party]["carried"] += 1
            out_rows.append(out)
            continue

        unresolved += 1
        unresolved_ids.append(evidence_id)
        out["manual_label"] = ""
        out["manual_note"] = str(out.get("manual_note") or "")
        by_party[party]["unlabeled"] += 1
        out_rows.append(out)

    summary = {
        "sample_total": len(sample_rows),
        "pre_labeled_rows": pre_labeled,
        "carried_forward_rows": carried,
        "unlabeled_rows": unresolved,
        "invalid_sample_labels": invalid_sample_labels,
        "by_party": by_party,
        "carried_forward_evidence_ids": sorted(set(carried_ids)),
        "unlabeled_evidence_ids": sorted(set(unresolved_ids)),
    }
    return out_rows, summary


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "party_name",
        "source_url",
        "evidence_id",
        "excerpt",
        "manual_label",
        "manual_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(row.get(k) or "") for k in fieldnames})


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sample_in = Path(args.sample_in)
    labels_in = [Path(p) for p in args.labels_in]
    out_path = Path(args.out)
    summary_out = Path(args.summary_out) if str(args.summary_out or "").strip() else None
    max_unlabeled = int(args.max_unlabeled)

    if not sample_in.exists():
        print(f"ERROR: sample CSV not found: {sample_in}")
        return 2
    missing = [p.as_posix() for p in labels_in if not p.exists()]
    if missing:
        print(f"ERROR: label CSV missing: {', '.join(missing)}")
        return 2

    sample_rows = _load_csv(sample_in)
    label_map, conflicts, invalid_historical_labels = _build_label_map(labels_in)
    out_rows, summary = _carry_forward(sample_rows=sample_rows, label_map=label_map)
    summary["sample_file"] = sample_in.as_posix()
    summary["labels_sources"] = [p.as_posix() for p in labels_in]
    summary["label_map_size"] = len(label_map)
    summary["label_conflicts_total"] = len(conflicts)
    summary["label_conflicts"] = conflicts
    summary["invalid_historical_labels"] = invalid_historical_labels
    strict_fail_reasons: list[str] = []
    if int(summary.get("invalid_historical_labels") or 0) > 0:
        strict_fail_reasons.append("invalid_historical_labels")
    if int(summary.get("invalid_sample_labels") or 0) > 0:
        strict_fail_reasons.append("invalid_sample_labels")
    if max_unlabeled >= 0 and int(summary.get("unlabeled_rows") or 0) > max_unlabeled:
        strict_fail_reasons.append("max_unlabeled_exceeded")
    if int(summary.get("label_conflicts_total") or 0) > 0:
        strict_fail_reasons.append("label_conflicts_detected")
    summary["strict_fail_reasons"] = strict_fail_reasons
    summary["status"] = "ok" if not strict_fail_reasons else "degraded"

    _write_csv(out_path, out_rows)
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if bool(args.strict) and strict_fail_reasons:
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
