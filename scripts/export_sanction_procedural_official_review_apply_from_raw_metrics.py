#!/usr/bin/env python3
"""Build apply-ready official procedural KPI rows from raw source-level metrics."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIN_EVIDENCE_QUOTE_LEN = 20
DEFAULT_SOURCE_ID = "boe_api_legal"
DEFAULT_PERIOD_GRANULARITY = "year"

_REQUIRED_HEADERS: tuple[str, ...] = (
    "sanction_source_id",
    "period_date",
    "source_url",
    "evidence_date",
    "evidence_quote",
    "recurso_presentado_count",
    "recurso_estimado_count",
    "anulaciones_formales_count",
    "resolution_delay_p90_days",
)

_APPLY_FIELDNAMES: tuple[str, ...] = (
    "sanction_source_id",
    "kpi_id",
    "period_date",
    "period_granularity",
    "value",
    "numerator",
    "denominator",
    "source_url",
    "evidence_date",
    "evidence_quote",
    "source_id",
    "source_record_id",
    "metric_key",
    "raw_row_key",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _slug(value: Any) -> str:
    out: list[str] = []
    prev_dash = False
    for ch in _norm(value).lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    token = "".join(out).strip("-")
    return token or "na"


def _to_float(raw: Any) -> float | None:
    token = _norm(raw)
    if not token:
        return None
    return float(token)


def _fmt_float(raw: float | None) -> str:
    if raw is None:
        return ""
    return format(float(raw), ".12g")


def _is_yyyy_mm_dd(value: str) -> bool:
    token = _norm(value)
    if not token:
        return False
    try:
        datetime.strptime(token, "%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return False
    return True


def _metric_key(*, kpi_id: str, sanction_source_id: str, period_date: str, period_granularity: str) -> str:
    return "|".join([_norm(kpi_id), _norm(sanction_source_id), _norm(period_date), _norm(period_granularity)])


def _default_source_record_id(*, sanction_source_id: str, period_date: str, period_granularity: str) -> str:
    return ":".join(
        [
            "official_review_raw",
            _slug(sanction_source_id),
            _slug(period_date),
            _slug(period_granularity),
        ]
    )


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


def _reason_priority(reason: str) -> int:
    if reason in {"missing_required_metadata", "invalid_numeric", "missing_required_headers"}:
        return 100
    if reason in {"invalid_evidence_date", "short_evidence_quote"}:
        return 90
    if reason in {"non_positive_recurso_presentado_count", "non_positive_resolution_delay_p90_days"}:
        return 80
    if reason in {"negative_component_count", "rate_out_of_range"}:
        return 70
    if reason == "duplicate_metric_key":
        return 60
    return 30


def build_apply_rows(
    *,
    headers: list[str],
    rows: list[dict[str, str]],
    default_source_id: str,
    default_period_granularity: str,
) -> dict[str, Any]:
    header_set = {_norm(h) for h in headers if _norm(h)}
    missing_headers = [h for h in _REQUIRED_HEADERS if h not in header_set]

    counts: dict[str, int] = {
        "rows_seen": 0,
        "rows_emitted": 0,
        "rows_rejected": 0,
        "kpi_rows_emitted": 0,
        "rows_rejected_missing_required_metadata": 0,
        "rows_rejected_invalid_evidence_date": 0,
        "rows_rejected_short_evidence_quote": 0,
        "rows_rejected_invalid_numeric": 0,
        "rows_rejected_non_positive_recurso_presentado_count": 0,
        "rows_rejected_negative_component_count": 0,
        "rows_rejected_non_positive_resolution_delay_p90_days": 0,
        "rows_rejected_rate_out_of_range": 0,
        "rows_rejected_duplicate_metric_key": 0,
    }

    apply_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    metric_key_seen: set[str] = set()

    for idx, raw in enumerate(rows, start=2):
        counts["rows_seen"] += 1
        reasons: list[str] = []

        sanction_source_id = _norm(raw.get("sanction_source_id"))
        period_date = _norm(raw.get("period_date"))
        period_granularity = _norm(raw.get("period_granularity")) or _norm(default_period_granularity) or "year"
        source_url = _norm(raw.get("source_url"))
        evidence_date = _norm(raw.get("evidence_date"))
        evidence_quote = _norm(raw.get("evidence_quote"))
        source_id = _norm(raw.get("source_id")) or _norm(default_source_id) or DEFAULT_SOURCE_ID

        if not sanction_source_id or not period_date or not source_url or not evidence_date or not evidence_quote:
            reasons.append("missing_required_metadata")
            counts["rows_rejected_missing_required_metadata"] += 1

        if evidence_date and not _is_yyyy_mm_dd(evidence_date):
            reasons.append("invalid_evidence_date")
            counts["rows_rejected_invalid_evidence_date"] += 1

        if evidence_quote and len(evidence_quote) < MIN_EVIDENCE_QUOTE_LEN:
            reasons.append("short_evidence_quote")
            counts["rows_rejected_short_evidence_quote"] += 1

        try:
            recurso_presentado_count = _to_float(raw.get("recurso_presentado_count"))
            recurso_estimado_count = _to_float(raw.get("recurso_estimado_count"))
            anulaciones_formales_count = _to_float(raw.get("anulaciones_formales_count"))
            resolution_delay_p90_days = _to_float(raw.get("resolution_delay_p90_days"))
        except Exception:
            reasons.append("invalid_numeric")
            counts["rows_rejected_invalid_numeric"] += 1
            recurso_presentado_count = None
            recurso_estimado_count = None
            anulaciones_formales_count = None
            resolution_delay_p90_days = None

        if (
            recurso_presentado_count is None
            or recurso_estimado_count is None
            or anulaciones_formales_count is None
            or resolution_delay_p90_days is None
        ) and "invalid_numeric" not in reasons:
            reasons.append("invalid_numeric")
            counts["rows_rejected_invalid_numeric"] += 1

        if recurso_presentado_count is not None and recurso_presentado_count <= 0:
            reasons.append("non_positive_recurso_presentado_count")
            counts["rows_rejected_non_positive_recurso_presentado_count"] += 1

        if (
            recurso_estimado_count is not None
            and recurso_estimado_count < 0
            or anulaciones_formales_count is not None
            and anulaciones_formales_count < 0
        ):
            reasons.append("negative_component_count")
            counts["rows_rejected_negative_component_count"] += 1

        if resolution_delay_p90_days is not None and resolution_delay_p90_days <= 0:
            reasons.append("non_positive_resolution_delay_p90_days")
            counts["rows_rejected_non_positive_resolution_delay_p90_days"] += 1

        recurso_estimation_rate: float | None = None
        formal_annulment_rate: float | None = None
        if recurso_presentado_count is not None and recurso_presentado_count > 0:
            if recurso_estimado_count is not None:
                recurso_estimation_rate = recurso_estimado_count / recurso_presentado_count
            if anulaciones_formales_count is not None:
                formal_annulment_rate = anulaciones_formales_count / recurso_presentado_count

        if (
            recurso_estimation_rate is not None
            and (recurso_estimation_rate < 0 or recurso_estimation_rate > 1)
            or formal_annulment_rate is not None
            and (formal_annulment_rate < 0 or formal_annulment_rate > 1)
        ):
            reasons.append("rate_out_of_range")
            counts["rows_rejected_rate_out_of_range"] += 1

        base_source_record_id = _norm(raw.get("source_record_id")) or _default_source_record_id(
            sanction_source_id=sanction_source_id,
            period_date=period_date,
            period_granularity=period_granularity,
        )
        row_key = _norm(raw.get("raw_row_key")) or f"line:{idx}"

        kpi_specs = [
            {
                "kpi_id": "kpi:recurso_estimation_rate",
                "value": recurso_estimation_rate,
                "numerator": recurso_estimado_count,
                "denominator": recurso_presentado_count,
            },
            {
                "kpi_id": "kpi:formal_annulment_rate",
                "value": formal_annulment_rate,
                "numerator": anulaciones_formales_count,
                "denominator": recurso_presentado_count,
            },
            {
                "kpi_id": "kpi:resolution_delay_p90_days",
                "value": resolution_delay_p90_days,
                "numerator": None,
                "denominator": None,
            },
        ]

        row_metric_keys = [
            _metric_key(
                kpi_id=str(spec["kpi_id"]),
                sanction_source_id=sanction_source_id,
                period_date=period_date,
                period_granularity=period_granularity,
            )
            for spec in kpi_specs
        ]
        if any(key in metric_key_seen for key in row_metric_keys):
            reasons.append("duplicate_metric_key")
            counts["rows_rejected_duplicate_metric_key"] += 1

        if reasons:
            counts["rows_rejected"] += 1
            rejected_rows.append(
                {
                    **raw,
                    "_csv_line": idx,
                    "_reason": "|".join(sorted(set(reasons))),
                    "_priority": max(_reason_priority(reason) for reason in set(reasons)),
                }
            )
            continue

        for spec, metric_key in zip(kpi_specs, row_metric_keys):
            kpi_id = str(spec["kpi_id"])
            row = {
                "sanction_source_id": sanction_source_id,
                "kpi_id": kpi_id,
                "period_date": period_date,
                "period_granularity": period_granularity,
                "value": _fmt_float(spec["value"]),
                "numerator": _fmt_float(spec["numerator"]),
                "denominator": _fmt_float(spec["denominator"]),
                "source_url": source_url,
                "evidence_date": evidence_date,
                "evidence_quote": evidence_quote,
                "source_id": source_id,
                "source_record_id": f"{base_source_record_id}:{_slug(kpi_id)}",
                "metric_key": metric_key,
                "raw_row_key": row_key,
            }
            apply_rows.append(row)
            metric_key_seen.add(metric_key)

        counts["rows_emitted"] += 1
        counts["kpi_rows_emitted"] += len(kpi_specs)

    checks = {
        "headers_complete": len(missing_headers) == 0,
        "input_rows_present": counts["rows_seen"] > 0,
        "rows_emitted_present": counts["rows_emitted"] > 0,
        "rows_rejected_zero": counts["rows_rejected"] == 0,
    }

    if missing_headers:
        status = "failed"
    elif counts["rows_emitted"] == 0:
        status = "degraded"
    elif counts["rows_rejected"] > 0:
        status = "degraded"
    else:
        status = "ok"

    coverage = {
        "rows_emitted_pct": round((counts["rows_emitted"] / counts["rows_seen"]) if counts["rows_seen"] else 0.0, 6),
        "rows_rejected_pct": round((counts["rows_rejected"] / counts["rows_seen"]) if counts["rows_seen"] else 0.0, 6),
        "kpi_rows_per_input_row": round(
            (counts["kpi_rows_emitted"] / counts["rows_emitted"]) if counts["rows_emitted"] else 0.0, 6
        ),
    }

    rejected_rows.sort(
        key=lambda row: (-int(row.get("_priority") or 0), int(row.get("_csv_line") or 0), _norm(row.get("_reason")))
    )

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "required_headers": list(_REQUIRED_HEADERS),
        "headers_present": headers,
        "missing_headers": missing_headers,
        "default_source_id": _norm(default_source_id) or DEFAULT_SOURCE_ID,
        "default_period_granularity": _norm(default_period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        "totals": counts,
        "coverage": coverage,
        "checks": checks,
        "apply_rows": apply_rows,
        "rejected_rows": rejected_rows,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Export apply-ready official procedural KPI rows from raw source-level metrics CSV"
    )
    ap.add_argument("--in", dest="in_file", required=True)
    ap.add_argument("--out", required=True, help="Output apply CSV path")
    ap.add_argument("--rejected-csv-out", default="", help="Optional rejected-row CSV output path")
    ap.add_argument("--out-json", default="", help="Optional JSON summary output path")
    ap.add_argument("--default-source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--default-period-granularity", default=DEFAULT_PERIOD_GRANULARITY)
    ap.add_argument("--strict", action="store_true", help="Exit non-zero when status is not ok")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.in_file)
    if not in_path.exists():
        print(json.dumps({"error": f"input csv not found: {in_path}"}, ensure_ascii=False))
        return 2

    headers, rows = _read_csv(in_path)
    report = build_apply_rows(
        headers=headers,
        rows=rows,
        default_source_id=_norm(args.default_source_id) or DEFAULT_SOURCE_ID,
        default_period_granularity=_norm(args.default_period_granularity) or DEFAULT_PERIOD_GRANULARITY,
    )

    apply_rows = list(report.pop("apply_rows", []))
    rejected_rows = list(report.pop("rejected_rows", []))

    out_path = Path(args.out)
    _write_csv(out_path, list(_APPLY_FIELDNAMES), apply_rows)

    if _norm(args.rejected_csv_out):
        rejected_headers = list(headers) + ["_csv_line", "_reason", "_priority"]
        _write_csv(Path(args.rejected_csv_out), rejected_headers, rejected_rows)

    payload = {
        **report,
        "input_csv": str(in_path),
        "output_csv": str(out_path),
        "rejected_csv_out": _norm(args.rejected_csv_out),
        "strict": bool(args.strict),
        "apply_rows_preview": apply_rows[:20],
        "rejected_rows_preview": rejected_rows[:20],
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out_json):
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if bool(args.strict) and str(payload.get("status")) != "ok":
        return 4
    return 0 if str(payload.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
