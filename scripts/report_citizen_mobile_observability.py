#!/usr/bin/env python3
"""Machine-readable mobile observability contract for /citizen latency.

Observability v1:
- input_to_render_p50_ms
- input_to_render_p90_ms
- input_to_render_p95_ms (informational)
- sample_count

Supports telemetry from:
- pre-aggregated JSON summaries
- raw events JSONL exported from the static /citizen app
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MIN_SAMPLES = 20
DEFAULT_MAX_INPUT_TO_RENDER_P50_MS = 180.0
DEFAULT_MAX_INPUT_TO_RENDER_P90_MS = 450.0

_MOBILE_LATENCY_EVENT_NAMES = {
    "input_to_render",
    "input_to_render_ms",
    "input_to_compare_render",
    "input_to_compare_render_ms",
    "compare_render_latency",
    "citizen_input_to_render",
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen mobile observability latency report")
    ap.add_argument("--telemetry-json", default="", help="Optional telemetry summary JSON path")
    ap.add_argument("--telemetry-events-jsonl", default="", help="Optional telemetry events JSONL path")
    ap.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    ap.add_argument("--max-input-to-render-p50-ms", type=float, default=DEFAULT_MAX_INPUT_TO_RENDER_P50_MS)
    ap.add_argument("--max-input-to-render-p90-ms", type=float, default=DEFAULT_MAX_INPUT_TO_RENDER_P90_MS)
    ap.add_argument("--strict", action="store_true", help="Fail (exit 4) when status is failed")
    ap.add_argument(
        "--strict-require-complete",
        action="store_true",
        help="With --strict, also fail when status is degraded (missing metrics or too few samples).",
    )
    ap.add_argument("--out", default="", help="Optional JSON output path")
    return ap.parse_args(argv)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _norm_token(v: Any) -> str:
    return str(v or "").strip().lower().replace("-", "_").replace(" ", "_")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("expected JSON object")
    return obj


def _extract_metric_from_summary(obj: dict[str, Any], paths: list[tuple[str, ...]]) -> float | None:
    for p in paths:
        cur: Any = obj
        ok = True
        for key in p:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if not ok:
            continue
        fv = _safe_float(cur)
        if fv is not None:
            return fv
    return None


def _extract_count_from_summary(obj: dict[str, Any], paths: list[tuple[str, ...]]) -> int | None:
    for p in paths:
        cur: Any = obj
        ok = True
        for key in p:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if not ok:
            continue
        iv = _safe_int(cur)
        if iv is not None:
            return iv
    return None


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return float(xs[0])
    qq = 0.0 if q < 0.0 else (1.0 if q > 1.0 else float(q))
    rank = qq * float(len(xs) - 1)
    lo = int(rank)
    hi = lo + 1
    if hi >= len(xs):
        return float(xs[-1])
    frac = rank - float(lo)
    return float(xs[lo] + (xs[hi] - xs[lo]) * frac)


def _read_telemetry_summary(path: Path) -> dict[str, Any]:
    obj = _load_json(path)
    p50 = _extract_metric_from_summary(
        obj,
        [
            ("input_to_render_p50_ms",),
            ("metrics", "input_to_render_p50_ms"),
            ("kpis", "input_to_render_p50_ms"),
        ],
    )
    p90 = _extract_metric_from_summary(
        obj,
        [
            ("input_to_render_p90_ms",),
            ("metrics", "input_to_render_p90_ms"),
            ("kpis", "input_to_render_p90_ms"),
        ],
    )
    p95 = _extract_metric_from_summary(
        obj,
        [
            ("input_to_render_p95_ms",),
            ("metrics", "input_to_render_p95_ms"),
            ("kpis", "input_to_render_p95_ms"),
        ],
    )
    sample_count = _extract_count_from_summary(
        obj,
        [
            ("sample_count",),
            ("telemetry", "sample_count"),
            ("metrics", "sample_count"),
            ("counts", "sample_count"),
        ],
    )
    events_total = _extract_count_from_summary(obj, [("events_total",), ("telemetry", "events_total")])
    parse_errors = _extract_count_from_summary(obj, [("parse_errors",), ("telemetry", "parse_errors")])
    return {
        "input_to_render_p50_ms": round(float(p50), 6) if p50 is not None else None,
        "input_to_render_p90_ms": round(float(p90), 6) if p90 is not None else None,
        "input_to_render_p95_ms": round(float(p95), 6) if p95 is not None else None,
        "sample_count": sample_count,
        "events_total": events_total,
        "parse_errors": parse_errors,
        "source_breakdown": None,
        "source": "telemetry_json",
    }


def _read_telemetry_events_jsonl(path: Path) -> dict[str, Any]:
    samples: list[float] = []
    parse_errors = 0
    events_total = 0
    source_counts: dict[str, int] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        ln = line.strip()
        if not ln:
            continue
        events_total += 1
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if not isinstance(row, dict):
            parse_errors += 1
            continue

        event_name = ""
        for key in ("metric", "metric_name", "event", "event_name", "name", "type", "action"):
            token = _norm_token(row.get(key))
            if token:
                event_name = token
                break

        value_ms = None
        for key in ("value_ms", "latency_ms", "input_to_render_ms", "duration_ms", "elapsed_ms", "ms"):
            vv = _safe_float(row.get(key))
            if vv is not None:
                value_ms = float(vv)
                break

        if event_name and event_name not in _MOBILE_LATENCY_EVENT_NAMES:
            continue
        if value_ms is None:
            parse_errors += 1
            continue
        if value_ms < 0.0 or value_ms > 120_000.0:
            parse_errors += 1
            continue

        samples.append(float(value_ms))
        source = str(row.get("source") or "").strip().lower() or "unknown"
        source_counts[source] = int(source_counts.get(source) or 0) + 1

    p50 = _percentile(samples, 0.50)
    p90 = _percentile(samples, 0.90)
    p95 = _percentile(samples, 0.95)

    return {
        "input_to_render_p50_ms": round(float(p50), 6) if p50 is not None else None,
        "input_to_render_p90_ms": round(float(p90), 6) if p90 is not None else None,
        "input_to_render_p95_ms": round(float(p95), 6) if p95 is not None else None,
        "sample_count": len(samples),
        "events_total": events_total,
        "parse_errors": parse_errors,
        "source_breakdown": dict(sorted(source_counts.items())),
        "source": "telemetry_events_jsonl",
    }


def _merge_telemetry(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    out = dict(primary)
    for key in (
        "input_to_render_p50_ms",
        "input_to_render_p90_ms",
        "input_to_render_p95_ms",
        "sample_count",
        "events_total",
        "parse_errors",
        "source_breakdown",
    ):
        if out.get(key) is None and secondary.get(key) is not None:
            out[key] = secondary.get(key)
    return out


def build_report(
    *,
    telemetry_summary: dict[str, Any] | None,
    telemetry_events: dict[str, Any] | None,
    telemetry_json_path: Path | None,
    telemetry_events_path: Path | None,
    min_samples: int,
    max_input_to_render_p50_ms: float,
    max_input_to_render_p90_ms: float,
) -> dict[str, Any]:
    telemetry_merged: dict[str, Any] = {
        "input_to_render_p50_ms": None,
        "input_to_render_p90_ms": None,
        "input_to_render_p95_ms": None,
        "sample_count": None,
        "events_total": None,
        "parse_errors": None,
        "source_breakdown": None,
    }
    telemetry_sources: list[str] = []
    if telemetry_summary is not None:
        telemetry_merged = _merge_telemetry(telemetry_merged, telemetry_summary)
        telemetry_sources.append(str(telemetry_summary.get("source") or "telemetry_json"))
    if telemetry_events is not None:
        telemetry_merged = _merge_telemetry(telemetry_merged, telemetry_events)
        telemetry_sources.append(str(telemetry_events.get("source") or "telemetry_events_jsonl"))

    p50 = _safe_float(telemetry_merged.get("input_to_render_p50_ms"))
    p90 = _safe_float(telemetry_merged.get("input_to_render_p90_ms"))
    p95 = _safe_float(telemetry_merged.get("input_to_render_p95_ms"))
    sample_count = _safe_int(telemetry_merged.get("sample_count"))

    missing_metrics: list[str] = []
    degraded_reasons: list[str] = []
    failure_reasons: list[str] = []

    if p50 is None:
        missing_metrics.append("input_to_render_p50_ms")
    if p90 is None:
        missing_metrics.append("input_to_render_p90_ms")
    if p95 is None:
        missing_metrics.append("input_to_render_p95_ms")

    if sample_count is None or sample_count <= 0:
        degraded_reasons.append("telemetry_missing")
    elif sample_count < int(min_samples):
        degraded_reasons.append("sample_count_below_minimum")

    p50_ok: bool | None = None
    if p50 is not None:
        p50_ok = float(p50) <= float(max_input_to_render_p50_ms)
        if not p50_ok:
            failure_reasons.append("input_to_render_p50_above_threshold")

    p90_ok: bool | None = None
    if p90 is not None:
        p90_ok = float(p90) <= float(max_input_to_render_p90_ms)
        if not p90_ok:
            failure_reasons.append("input_to_render_p90_above_threshold")

    status = "ok"
    if failure_reasons:
        status = "failed"
    elif missing_metrics or degraded_reasons:
        status = "degraded"

    checks: dict[str, Any] = {
        "telemetry_available": bool(sample_count is not None and sample_count > 0),
        "sample_count_meets_minimum": None if sample_count is None else bool(sample_count >= int(min_samples)),
        "input_to_render_p50_within_threshold": p50_ok,
        "input_to_render_p90_within_threshold": p90_ok,
        "contract_complete": bool(
            status == "ok"
            and sample_count is not None
            and sample_count >= int(min_samples)
            and p50 is not None
            and p90 is not None
            and p95 is not None
        ),
    }

    return {
        "generated_at": now_utc_iso(),
        "telemetry_json_path": str(telemetry_json_path) if telemetry_json_path else None,
        "telemetry_events_jsonl_path": str(telemetry_events_path) if telemetry_events_path else None,
        "telemetry_sources": sorted(set(telemetry_sources)),
        "telemetry": {
            "sample_count": sample_count,
            "events_total": _safe_int(telemetry_merged.get("events_total")),
            "parse_errors": _safe_int(telemetry_merged.get("parse_errors")),
            "source_breakdown": telemetry_merged.get("source_breakdown") or {},
        },
        "metrics": {
            "input_to_render_p50_ms": round(float(p50), 6) if p50 is not None else None,
            "input_to_render_p90_ms": round(float(p90), 6) if p90 is not None else None,
            "input_to_render_p95_ms": round(float(p95), 6) if p95 is not None else None,
        },
        "thresholds": {
            "min_samples": int(min_samples),
            "max_input_to_render_p50_ms": round(float(max_input_to_render_p50_ms), 6),
            "max_input_to_render_p90_ms": round(float(max_input_to_render_p90_ms), 6),
        },
        "checks": checks,
        "missing_metrics": sorted(set(missing_metrics)),
        "degraded_reasons": sorted(set(degraded_reasons)),
        "failure_reasons": sorted(set(failure_reasons)),
        "status": status,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    telemetry_json_path = Path(str(args.telemetry_json).strip()) if str(args.telemetry_json).strip() else None
    if telemetry_json_path is not None and not telemetry_json_path.exists():
        print(json.dumps({"error": f"telemetry-json not found: {telemetry_json_path}"}, ensure_ascii=False))
        return 2

    telemetry_events_path = (
        Path(str(args.telemetry_events_jsonl).strip()) if str(args.telemetry_events_jsonl).strip() else None
    )
    if telemetry_events_path is not None and not telemetry_events_path.exists():
        print(json.dumps({"error": f"telemetry-events-jsonl not found: {telemetry_events_path}"}, ensure_ascii=False))
        return 2

    if telemetry_json_path is None and telemetry_events_path is None:
        print(json.dumps({"error": "set --telemetry-json and/or --telemetry-events-jsonl"}, ensure_ascii=False))
        return 2

    try:
        telemetry_summary = _read_telemetry_summary(telemetry_json_path) if telemetry_json_path is not None else None
        telemetry_events = (
            _read_telemetry_events_jsonl(telemetry_events_path) if telemetry_events_path is not None else None
        )
        report = build_report(
            telemetry_summary=telemetry_summary,
            telemetry_events=telemetry_events,
            telemetry_json_path=telemetry_json_path,
            telemetry_events_path=telemetry_events_path,
            min_samples=int(args.min_samples),
            max_input_to_render_p50_ms=float(args.max_input_to_render_p50_ms),
            max_input_to_render_p90_ms=float(args.max_input_to_render_p90_ms),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if str(args.out).strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    status = str(report.get("status") or "")
    if bool(args.strict):
        if status == "failed":
            return 4
        if bool(args.strict_require_complete) and status != "ok":
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
