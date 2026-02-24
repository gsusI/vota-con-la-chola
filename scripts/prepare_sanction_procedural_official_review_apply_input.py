#!/usr/bin/env python3
"""Prepare apply-ready CSV from official procedural-review template by filtering empty rows."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = (
    "sanction_source_id",
    "kpi_id",
    "period_date",
    "source_url",
    "evidence_date",
    "evidence_quote",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = [str(h or "") for h in (reader.fieldnames or [])]
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({str(k or ""): str(v or "") for k, v in row.items()})
    return headers, rows


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def build_prepare_report(
    *,
    headers: list[str],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    header_set = {_norm(h) for h in headers if _norm(h)}
    missing_headers = [h for h in REQUIRED_FIELDS if h not in header_set]
    if "value" not in header_set:
        missing_headers.append("value")
    # ensure unique order
    dedup_missing: list[str] = []
    for h in missing_headers:
        if h not in dedup_missing:
            dedup_missing.append(h)

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    counts = {
        "rows_seen": 0,
        "rows_kept": 0,
        "rows_rejected": 0,
        "rows_rejected_missing_value": 0,
        "rows_rejected_missing_required_metadata": 0,
    }

    for idx, row in enumerate(rows, start=2):
        counts["rows_seen"] += 1
        reasons: list[str] = []

        value = _norm(row.get("value"))
        if not value:
            reasons.append("missing_value")
            counts["rows_rejected_missing_value"] += 1

        for field in REQUIRED_FIELDS:
            if not _norm(row.get(field)):
                reasons.append("missing_required_metadata")
                counts["rows_rejected_missing_required_metadata"] += 1
                break

        if reasons:
            counts["rows_rejected"] += 1
            rejected.append(
                {
                    **row,
                    "_csv_line": idx,
                    "_reason": "|".join(sorted(set(reasons))),
                }
            )
            continue

        kept.append(dict(row))
        counts["rows_kept"] += 1

    checks = {
        "headers_complete": len(dedup_missing) == 0,
        "rows_kept_present": counts["rows_kept"] > 0,
        "rows_rejected_visible": counts["rows_rejected"] > 0,
    }
    if dedup_missing:
        status = "failed"
    elif counts["rows_kept"] == 0:
        status = "degraded"
    else:
        status = "ok"

    coverage = {
        "rows_kept_pct": round((counts["rows_kept"] / counts["rows_seen"]) if counts["rows_seen"] else 0.0, 6),
        "rows_rejected_pct": round((counts["rows_rejected"] / counts["rows_seen"]) if counts["rows_seen"] else 0.0, 6),
    }

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "required_fields": list(REQUIRED_FIELDS) + ["value"],
        "headers_present": headers,
        "missing_headers": dedup_missing,
        "totals": counts,
        "coverage": coverage,
        "checks": checks,
        "kept_rows": kept,
        "rejected_rows": rejected,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Prepare apply-ready CSV by filtering rows without value/required metadata"
    )
    ap.add_argument("--in", dest="in_file", required=True)
    ap.add_argument("--out", required=True, help="Prepared CSV with rows kept")
    ap.add_argument("--rejected-csv-out", default="", help="Optional rejected-row queue CSV")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero when no rows kept or headers missing")
    ap.add_argument("--out-json", default="", help="Optional summary JSON output")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.in_file)
    if not in_path.exists():
        print(json.dumps({"error": f"input csv not found: {in_path}"}, ensure_ascii=False))
        return 2

    headers, rows = _read_csv(in_path)
    report = build_prepare_report(headers=headers, rows=rows)

    kept_rows = list(report.pop("kept_rows", []))
    rejected_rows = list(report.pop("rejected_rows", []))

    out_path = Path(args.out)
    _write_csv(out_path, headers, kept_rows)

    if _norm(args.rejected_csv_out):
        rejected_headers = list(headers) + ["_csv_line", "_reason"]
        _write_csv(Path(args.rejected_csv_out), rejected_headers, rejected_rows)

    payload = {
        **report,
        "input_csv": str(in_path),
        "output_csv": str(out_path),
        "rows_kept_preview": kept_rows[:20],
        "rows_rejected_preview": rejected_rows[:20],
        "strict": bool(args.strict),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out_json):
        json_path = Path(args.out_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if bool(args.strict):
        if str(payload.get("status")) != "ok":
            return 4
    return 0 if str(payload.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
