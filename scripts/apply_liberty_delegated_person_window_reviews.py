#!/usr/bin/env python3
"""Apply reviewed delegated person/window decisions into seed."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any

try:
    from scripts.export_liberty_delegated_person_window_review_queue import _seed_link_key
    from scripts.validate_liberty_delegated_enforcement_seed import validate_seed
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for direct script execution
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    from scripts.export_liberty_delegated_person_window_review_queue import _seed_link_key
    from scripts.validate_liberty_delegated_enforcement_seed import validate_seed

ALLOWED_DECISIONS = {"approved", "ignored", "pending"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _parse_date(value: str) -> datetime | None:
    token = _norm(value)
    if not token:
        return None
    token10 = token[:10]
    try:
        return datetime.strptime(token10, "%Y-%m-%d")
    except ValueError:
        return None


def _read_seed(seed_path: Path) -> dict[str, Any]:
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("seed root must be object")
    links = raw.get("links")
    if not isinstance(links, list):
        raise ValueError("seed.links must be list")
    return raw


def _write_seed(seed_doc: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(seed_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_csv_rows(in_path: Path) -> list[dict[str, str]]:
    with in_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return []
        return [{str(k or ""): str(v or "") for k, v in row.items()} for row in reader]


def apply_review_decisions(
    seed_doc: dict[str, Any],
    *,
    rows: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    methodology = seed_doc.get("methodology")
    method_version = _norm(methodology.get("method_version")) if isinstance(methodology, dict) else ""
    if not method_version:
        method_version = "delegated_enforcement_v1"

    links = seed_doc.get("links")
    assert isinstance(links, list)
    by_key: dict[str, dict[str, Any]] = {}
    for row in links:
        if not isinstance(row, dict):
            continue
        key = _seed_link_key(method_version, row)
        if key:
            by_key[key] = row

    counts: dict[str, int] = {
        "rows_seen": len(rows),
        "rows_with_decision": 0,
        "approved_rows": 0,
        "ignored_rows": 0,
        "pending_rows": 0,
        "updated_rows": 0,
        "skipped_blank_decision": 0,
        "skipped_invalid_decision": 0,
        "skipped_missing_link_key": 0,
        "skipped_link_not_found": 0,
        "skipped_invalid_date": 0,
        "skipped_inverted_window": 0,
        "skipped_empty_designated_actor_after_review": 0,
    }
    failures: list[str] = []

    for row in rows:
        decision = _norm(row.get("decision")).lower()
        if not decision:
            counts["skipped_blank_decision"] += 1
            continue
        if decision not in ALLOWED_DECISIONS:
            counts["skipped_invalid_decision"] += 1
            continue
        counts["rows_with_decision"] += 1
        if decision == "ignored":
            counts["ignored_rows"] += 1
            continue
        if decision == "pending":
            counts["pending_rows"] += 1
            continue
        counts["approved_rows"] += 1

        link_key = _norm(row.get("link_key"))
        if not link_key:
            counts["skipped_missing_link_key"] += 1
            continue
        seed_link = by_key.get(link_key)
        if seed_link is None:
            counts["skipped_link_not_found"] += 1
            continue

        reviewed_start = _norm(row.get("reviewed_appointment_start_date"))
        reviewed_end = _norm(row.get("reviewed_appointment_end_date"))
        reviewed_evidence_date = _norm(row.get("reviewed_enforcement_evidence_date"))

        if reviewed_start and _parse_date(reviewed_start) is None:
            counts["skipped_invalid_date"] += 1
            failures.append(f"invalid reviewed_appointment_start_date for {link_key}: {reviewed_start!r}")
            continue
        if reviewed_end and _parse_date(reviewed_end) is None:
            counts["skipped_invalid_date"] += 1
            failures.append(f"invalid reviewed_appointment_end_date for {link_key}: {reviewed_end!r}")
            continue
        if reviewed_evidence_date and _parse_date(reviewed_evidence_date) is None:
            counts["skipped_invalid_date"] += 1
            failures.append(f"invalid reviewed_enforcement_evidence_date for {link_key}: {reviewed_evidence_date!r}")
            continue

        start_dt = _parse_date(reviewed_start) or _parse_date(seed_link.get("appointment_start_date"))
        end_dt = _parse_date(reviewed_end) or _parse_date(seed_link.get("appointment_end_date"))
        if start_dt is not None and end_dt is not None and end_dt < start_dt:
            counts["skipped_inverted_window"] += 1
            failures.append(f"inverted appointment window for {link_key}")
            continue

        changed = False
        for csv_col, seed_col in (
            ("reviewed_designated_actor_label", "designated_actor_label"),
            ("reviewed_appointment_start_date", "appointment_start_date"),
            ("reviewed_appointment_end_date", "appointment_end_date"),
            ("reviewed_enforcement_evidence_date", "enforcement_evidence_date"),
            ("reviewed_source_url", "source_url"),
            ("reviewed_evidence_quote", "evidence_quote"),
        ):
            token = _norm(row.get(csv_col))
            if not token:
                continue
            if token != _norm(seed_link.get(seed_col)):
                seed_link[seed_col] = token
                changed = True

        review_note = _norm(row.get("review_note"))
        if review_note:
            current_quote = _norm(seed_link.get("evidence_quote"))
            merged = f"{current_quote} | review:{review_note}" if current_quote else f"review:{review_note}"
            if merged != current_quote:
                seed_link["evidence_quote"] = merged
                changed = True

        if not _norm(seed_link.get("designated_actor_label")):
            counts["skipped_empty_designated_actor_after_review"] += 1
            failures.append(f"designated_actor_label remains empty for {link_key}")
            continue

        if changed:
            counts["updated_rows"] += 1

    seed_doc["generated_at"] = now_utc_iso()
    return seed_doc, {"counts": counts, "failures": failures}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", default="etl/data/seeds/liberty_delegated_enforcement_seed_v1.json")
    ap.add_argument("--in", dest="in_file", required=True)
    ap.add_argument("--seed-out", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    seed_path = Path(args.seed)
    in_path = Path(args.in_file)
    seed_out_path = Path(args.seed_out) if _norm(args.seed_out) else seed_path
    out_path = Path(args.out) if _norm(args.out) else None

    if not seed_path.exists():
        raise SystemExit(f"seed not found: {seed_path}")
    if not in_path.exists():
        raise SystemExit(f"input csv not found: {in_path}")

    seed_doc = _read_seed(seed_path)
    rows = _read_csv_rows(in_path)
    updated_seed_doc, apply_meta = apply_review_decisions(seed_doc, rows=rows)

    with TemporaryDirectory() as td:
        candidate = Path(td) / "candidate_seed.json"
        _write_seed(updated_seed_doc, candidate)
        validation_report = validate_seed(candidate)

    payload = {
        "seed_path": str(seed_path),
        "seed_out_path": str(seed_out_path),
        "input_csv": str(in_path),
        "dry_run": bool(args.dry_run),
        "apply": apply_meta,
        "validation": {
            "valid": bool(validation_report.get("valid")),
            "errors_count": int(validation_report.get("errors_count", 0)),
            "warnings_count": int(validation_report.get("warnings_count", 0)),
            "errors": list(validation_report.get("errors", [])),
            "warnings": list(validation_report.get("warnings", [])),
        },
    }

    if bool(validation_report.get("valid")) and not bool(args.dry_run):
        _write_seed(updated_seed_doc, seed_out_path)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if bool(validation_report.get("valid")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
