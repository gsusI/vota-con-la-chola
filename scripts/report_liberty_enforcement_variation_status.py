#!/usr/bin/env python3
"""Report territorial enforcement variation for liberty restrictions."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _to_float(v: Any) -> float:
    try:
        return float(v or 0.0)
    except Exception:
        return 0.0


def build_status_report(
    conn: sqlite3.Connection,
    *,
    top_n: int = 20,
    sanction_rate_spread_pct_min: float = 0.35,
    annulment_rate_spread_pp_min: float = 0.08,
    delay_spread_days_min: float = 45.0,
    target_coverage_min: float = 0.6,
    multi_territory_coverage_min: float = 0.6,
) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM liberty_enforcement_methodologies) AS methodologies_total,
          (SELECT COUNT(*) FROM liberty_enforcement_observations) AS observations_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_enforcement_observations) AS fragments_with_observations_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_restriction_assessments) AS target_fragments_total,
          (SELECT COUNT(*) FROM (
             SELECT fragment_id
             FROM liberty_enforcement_observations
             GROUP BY fragment_id
             HAVING COUNT(DISTINCT territory_key) >= 2
           )) AS fragments_with_multi_territory_total
        """
    ).fetchone()

    fragment_rows = conn.execute(
        """
        WITH by_fragment AS (
          SELECT
            o.fragment_id,
            COUNT(DISTINCT o.territory_key) AS territories_total,
            MIN(o.sanction_rate_per_1000) AS sanction_rate_min,
            MAX(o.sanction_rate_per_1000) AS sanction_rate_max,
            MIN(o.annulment_rate) AS annulment_rate_min,
            MAX(o.annulment_rate) AS annulment_rate_max,
            MIN(o.resolution_delay_p90_days) AS delay_min,
            MAX(o.resolution_delay_p90_days) AS delay_max,
            SUM(COALESCE(o.sample_size, 0)) AS sample_size_total
          FROM liberty_enforcement_observations o
          GROUP BY o.fragment_id
        )
        SELECT
          b.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(n.title, '') AS norm_title,
          COALESCE(f.fragment_label, '') AS fragment_label,
          b.territories_total,
          b.sanction_rate_min,
          b.sanction_rate_max,
          b.annulment_rate_min,
          b.annulment_rate_max,
          b.delay_min,
          b.delay_max,
          b.sample_size_total
        FROM by_fragment b
        JOIN legal_norm_fragments f ON f.fragment_id = b.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        ORDER BY b.fragment_id ASC
        """
    ).fetchall()

    per_fragment: list[dict[str, Any]] = []
    high_variation: list[dict[str, Any]] = []
    spread_acc_rate = 0.0
    spread_acc_annul = 0.0
    spread_acc_delay = 0.0

    for row in fragment_rows:
        sanction_min = _to_float(row["sanction_rate_min"])
        sanction_max = _to_float(row["sanction_rate_max"])
        annul_min = _to_float(row["annulment_rate_min"])
        annul_max = _to_float(row["annulment_rate_max"])
        delay_min = _to_float(row["delay_min"])
        delay_max = _to_float(row["delay_max"])

        spread_rate_pct = ((sanction_max - sanction_min) / sanction_max) if sanction_max > 0 else 0.0
        spread_annul_pp = annul_max - annul_min
        spread_delay_days = delay_max - delay_min
        is_high = (
            spread_rate_pct >= float(sanction_rate_spread_pct_min)
            or spread_annul_pp >= float(annulment_rate_spread_pp_min)
            or spread_delay_days >= float(delay_spread_days_min)
        )

        entry = {
            "fragment_id": _norm(row["fragment_id"]),
            "norm_id": _norm(row["norm_id"]),
            "boe_id": _norm(row["boe_id"]),
            "norm_title": _norm(row["norm_title"]),
            "fragment_label": _norm(row["fragment_label"]),
            "territories_total": int(row["territories_total"] or 0),
            "sanction_rate_min": round(sanction_min, 6),
            "sanction_rate_max": round(sanction_max, 6),
            "sanction_rate_spread_pct": round(spread_rate_pct, 6),
            "annulment_rate_min": round(annul_min, 6),
            "annulment_rate_max": round(annul_max, 6),
            "annulment_rate_spread_pp": round(spread_annul_pp, 6),
            "resolution_delay_p90_min_days": round(delay_min, 6),
            "resolution_delay_p90_max_days": round(delay_max, 6),
            "resolution_delay_spread_days": round(spread_delay_days, 6),
            "sample_size_total": int(row["sample_size_total"] or 0),
            "high_variation": bool(is_high),
        }
        per_fragment.append(entry)
        spread_acc_rate += spread_rate_pct
        spread_acc_annul += spread_annul_pp
        spread_acc_delay += spread_delay_days
        if is_high:
            high_variation.append(entry)

    per_fragment_sorted = sorted(
        per_fragment,
        key=lambda x: (
            -float(x["sanction_rate_spread_pct"]),
            -float(x["annulment_rate_spread_pp"]),
            -float(x["resolution_delay_spread_days"]),
            str(x["fragment_id"]),
        ),
    )
    high_variation_sorted = [x for x in per_fragment_sorted if bool(x["high_variation"])][: max(0, int(top_n))]

    missing_rows = conn.execute(
        """
        SELECT
          a.fragment_id,
          f.norm_id,
          COALESCE(n.boe_id, '') AS boe_id,
          COALESCE(f.fragment_label, '') AS fragment_label
        FROM liberty_restriction_assessments a
        JOIN legal_norm_fragments f ON f.fragment_id = a.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        LEFT JOIN liberty_enforcement_observations o ON o.fragment_id = a.fragment_id
        WHERE o.fragment_id IS NULL
        ORDER BY f.norm_id ASC, a.fragment_id ASC
        LIMIT 20
        """
    ).fetchall()
    missing_sample = [
        {
            "fragment_id": _norm(r["fragment_id"]),
            "norm_id": _norm(r["norm_id"]),
            "boe_id": _norm(r["boe_id"]),
            "fragment_label": _norm(r["fragment_label"]),
        }
        for r in missing_rows
    ]

    target_fragments_total = int(totals["target_fragments_total"] or 0)
    fragments_with_observations_total = int(totals["fragments_with_observations_total"] or 0)
    fragments_with_multi_territory_total = int(totals["fragments_with_multi_territory_total"] or 0)

    coverage = {
        "target_fragment_coverage_pct": round(
            (fragments_with_observations_total / target_fragments_total) if target_fragments_total else 0.0,
            6,
        ),
        "multi_territory_coverage_pct": round(
            (fragments_with_multi_territory_total / target_fragments_total) if target_fragments_total else 0.0,
            6,
        ),
        "high_variation_fragment_pct": round(
            (len(high_variation) / fragments_with_multi_territory_total) if fragments_with_multi_territory_total else 0.0,
            6,
        ),
        "avg_sanction_rate_spread_pct": round(
            (spread_acc_rate / len(per_fragment)) if per_fragment else 0.0,
            6,
        ),
        "avg_annulment_rate_spread_pp": round(
            (spread_acc_annul / len(per_fragment)) if per_fragment else 0.0,
            6,
        ),
        "avg_resolution_delay_spread_days": round(
            (spread_acc_delay / len(per_fragment)) if per_fragment else 0.0,
            6,
        ),
    }

    checks = {
        "enforcement_variation_started": int(totals["observations_total"] or 0) > 0,
        "target_coverage_gate": coverage["target_fragment_coverage_pct"] >= float(target_coverage_min),
        "multi_territory_gate": coverage["multi_territory_coverage_pct"] >= float(multi_territory_coverage_min),
    }
    gate_passed = checks["target_coverage_gate"] and checks["multi_territory_gate"]

    if int(totals["observations_total"] or 0) == 0:
        status = "failed"
    elif gate_passed:
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "totals": {
            "methodologies_total": int(totals["methodologies_total"] or 0),
            "observations_total": int(totals["observations_total"] or 0),
            "fragments_with_observations_total": fragments_with_observations_total,
            "target_fragments_total": target_fragments_total,
            "fragments_with_multi_territory_total": fragments_with_multi_territory_total,
            "high_variation_fragments_total": len(high_variation),
        },
        "coverage": coverage,
        "checks": checks,
        "gate": {
            "passed": gate_passed,
            "thresholds": {
                "target_coverage_min": float(target_coverage_min),
                "multi_territory_coverage_min": float(multi_territory_coverage_min),
                "sanction_rate_spread_pct_min": float(sanction_rate_spread_pct_min),
                "annulment_rate_spread_pp_min": float(annulment_rate_spread_pp_min),
                "delay_spread_days_min": float(delay_spread_days_min),
            },
        },
        "high_variation_sample": high_variation_sorted,
        "missing_fragment_sample": missing_sample,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report territorial enforcement variation status")
    ap.add_argument("--db", required=True)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--sanction-rate-spread-pct-min", type=float, default=0.35)
    ap.add_argument("--annulment-rate-spread-pp-min", type=float, default=0.08)
    ap.add_argument("--delay-spread-days-min", type=float, default=45.0)
    ap.add_argument("--target-coverage-min", type=float, default=0.6)
    ap.add_argument("--multi-territory-coverage-min", type=float, default=0.6)
    ap.add_argument("--enforce-gate", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_status_report(
            conn,
            top_n=int(args.top_n),
            sanction_rate_spread_pct_min=float(args.sanction_rate_spread_pct_min),
            annulment_rate_spread_pp_min=float(args.annulment_rate_spread_pp_min),
            delay_spread_days_min=float(args.delay_spread_days_min),
            target_coverage_min=float(args.target_coverage_min),
            multi_territory_coverage_min=float(args.multi_territory_coverage_min),
        )
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if str(report.get("status")) == "failed":
        return 1
    if bool(args.enforce_gate) and not bool(report.get("gate", {}).get("passed")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
