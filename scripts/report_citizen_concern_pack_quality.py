#!/usr/bin/env python3
"""Machine-readable quality contract for citizen concern packs.

This report scores each configured concern pack with deterministic heuristics:
- topic coverage (topics linked to pack concerns)
- stance clarity vs unknown ratio over pack topic-party cells
- confidence average where any signal exists
- high-stakes topic share

The output is designed for static publication and optional strict gating.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT = Path("docs/gh-pages/citizen/data/citizen.json")
DEFAULT_CONCERNS_CONFIG = Path("ui/citizen/concerns_v1.json")
DEFAULT_OUT = Path("docs/etl/sprints/AI-OPS-78/evidence/citizen_concern_pack_quality_latest.json")

DEFAULT_MIN_TOPICS_PER_PACK = 10
DEFAULT_MIN_CLEAR_CELLS_PCT = 0.70
DEFAULT_MAX_UNKNOWN_CELLS_PCT = 0.30
DEFAULT_MIN_CONFIDENCE_AVG_SIGNAL = 0.50
DEFAULT_MIN_HIGH_STAKES_SHARE = 0.12
DEFAULT_MAX_WEAK_PACKS = 1

STANCE_VALUES = {"support", "oppose", "mixed", "unclear", "no_signal"}
_ID_NORMALIZE_RE = re.compile(r"[^a-z0-9_]+")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _norm_pack_id(v: Any) -> str:
    token = str(v or "").strip().lower()
    token = _ID_NORMALIZE_RE.sub("_", token).strip("_")
    return token


def _load_json_obj(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"expected JSON object at {path}")
    return obj


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen concern-pack quality report")
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--concerns-config", default=str(DEFAULT_CONCERNS_CONFIG))
    ap.add_argument("--min-topics-per-pack", type=int, default=DEFAULT_MIN_TOPICS_PER_PACK)
    ap.add_argument("--min-clear-cells-pct", type=float, default=DEFAULT_MIN_CLEAR_CELLS_PCT)
    ap.add_argument("--max-unknown-cells-pct", type=float, default=DEFAULT_MAX_UNKNOWN_CELLS_PCT)
    ap.add_argument("--min-confidence-avg-signal", type=float, default=DEFAULT_MIN_CONFIDENCE_AVG_SIGNAL)
    ap.add_argument("--min-high-stakes-share", type=float, default=DEFAULT_MIN_HIGH_STAKES_SHARE)
    ap.add_argument("--max-weak-packs", type=int, default=DEFAULT_MAX_WEAK_PACKS)
    ap.add_argument("--strict", action="store_true", help="Fail with exit 4 when status is failed")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Optional JSON output path (empty disables write)")
    return ap.parse_args(argv)


def _build_topic_index(snapshot: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], list[int], int]:
    topics_raw = snapshot.get("topics")
    if not isinstance(topics_raw, list):
        raise ValueError("snapshot.topics must be a list")
    topic_by_id: dict[int, dict[str, Any]] = {}
    topic_ids: list[int] = []
    high_stakes_total = 0
    for row in topics_raw:
        if not isinstance(row, dict):
            continue
        tid_f = _safe_float(row.get("topic_id"))
        if tid_f is None:
            continue
        tid = int(tid_f)
        if tid <= 0:
            continue
        concern_ids = []
        for c in row.get("concern_ids") or []:
            token = str(c or "").strip()
            if token:
                concern_ids.append(token)
        concerns_norm = list(dict.fromkeys(concern_ids))
        is_high = bool(row.get("is_high_stakes"))
        topic_by_id[tid] = {
            "topic_id": tid,
            "concern_ids": concerns_norm,
            "is_high_stakes": is_high,
        }
        topic_ids.append(tid)
        if is_high:
            high_stakes_total += 1
    topic_ids.sort()
    return topic_by_id, topic_ids, int(high_stakes_total)


def _build_party_ids(snapshot: dict[str, Any]) -> list[int]:
    parties_raw = snapshot.get("parties")
    if not isinstance(parties_raw, list):
        raise ValueError("snapshot.parties must be a list")
    out: list[int] = []
    seen: set[int] = set()
    for row in parties_raw:
        if not isinstance(row, dict):
            continue
        pid_f = _safe_float(row.get("party_id"))
        if pid_f is None:
            continue
        pid = int(pid_f)
        if pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    out.sort()
    return out


def _build_position_index(snapshot: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    rows = snapshot.get("party_topic_positions")
    if not isinstance(rows, list):
        raise ValueError("snapshot.party_topic_positions must be a list")
    out: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        tid_f = _safe_float(row.get("topic_id"))
        pid_f = _safe_float(row.get("party_id"))
        if tid_f is None or pid_f is None:
            continue
        tid = int(tid_f)
        pid = int(pid_f)
        if tid <= 0 or pid <= 0:
            continue
        out[(tid, pid)] = row
    return out


def _pack_rows_from_concerns(concerns_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    packs = concerns_cfg.get("packs")
    if not isinstance(packs, list):
        raise ValueError("concerns-config.packs must be a list")
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in packs:
        if not isinstance(row, dict):
            continue
        pid = _norm_pack_id(row.get("id"))
        if not pid or pid in seen_ids:
            continue
        concern_ids: list[str] = []
        for c in row.get("concern_ids") or []:
            token = str(c or "").strip()
            if token:
                concern_ids.append(token)
        concern_ids = list(dict.fromkeys(concern_ids))
        if not concern_ids:
            continue
        seen_ids.add(pid)
        out.append(
            {
                "pack_id": pid,
                "pack_label": str(row.get("label") or pid).strip() or pid,
                "concern_ids": concern_ids,
                "tradeoff": str(row.get("tradeoff") or "").strip(),
            }
        )
    return out


def _quality_score(
    *,
    clear_pct: float,
    unknown_pct: float,
    high_stakes_share: float,
    confidence_avg_signal: float | None,
) -> float:
    conf = float(confidence_avg_signal) if confidence_avg_signal is not None else 0.0
    score = (0.40 * clear_pct) + (0.30 * (1.0 - unknown_pct)) + (0.20 * high_stakes_share) + (0.10 * conf)
    return round(_clamp01(score), 6)


def build_report(
    *,
    snapshot: dict[str, Any],
    concerns_cfg: dict[str, Any],
    min_topics_per_pack: int,
    min_clear_cells_pct: float,
    max_unknown_cells_pct: float,
    min_confidence_avg_signal: float,
    min_high_stakes_share: float,
    max_weak_packs: int,
    snapshot_path: Path,
    concerns_path: Path,
) -> dict[str, Any]:
    topic_by_id, topic_ids_all, high_stakes_total = _build_topic_index(snapshot)
    party_ids = _build_party_ids(snapshot)
    pos_by_key = _build_position_index(snapshot)
    packs = _pack_rows_from_concerns(concerns_cfg)

    pack_rows: list[dict[str, Any]] = []
    weak_pack_ids: list[str] = []

    for pack in packs:
        pack_id = str(pack.get("pack_id") or "")
        concern_set = set(pack.get("concern_ids") or [])
        selected_topic_ids = [
            tid for tid in topic_ids_all if concern_set.intersection(set((topic_by_id.get(tid) or {}).get("concern_ids") or []))
        ]

        topics_total = len(selected_topic_ids)
        high_stakes_topics_total = sum(1 for tid in selected_topic_ids if bool((topic_by_id.get(tid) or {}).get("is_high_stakes")))
        high_stakes_share = (float(high_stakes_topics_total) / float(topics_total)) if topics_total > 0 else 0.0

        stance_counts = {k: 0 for k in sorted(STANCE_VALUES)}
        conf_values: list[float] = []
        for tid in selected_topic_ids:
            for pid in party_ids:
                row = pos_by_key.get((tid, pid))
                stance = str((row or {}).get("stance") or "no_signal")
                if stance not in STANCE_VALUES:
                    stance = "unclear"
                stance_counts[stance] = int(stance_counts.get(stance, 0)) + 1
                if row and stance != "no_signal":
                    conf = _safe_float(row.get("confidence"))
                    if conf is not None:
                        conf_values.append(_clamp01(float(conf)))

        cells_total = int(topics_total * len(party_ids))
        clear_total = int(stance_counts.get("support", 0) + stance_counts.get("oppose", 0) + stance_counts.get("mixed", 0))
        unknown_total = int(stance_counts.get("unclear", 0) + stance_counts.get("no_signal", 0))
        any_signal_total = int(cells_total - int(stance_counts.get("no_signal", 0)))

        clear_pct = (float(clear_total) / float(cells_total)) if cells_total > 0 else 0.0
        unknown_pct = (float(unknown_total) / float(cells_total)) if cells_total > 0 else 0.0
        any_signal_pct = (float(any_signal_total) / float(cells_total)) if cells_total > 0 else 0.0
        confidence_avg_signal = (sum(conf_values) / len(conf_values)) if conf_values else None

        weak_reasons: list[str] = []
        if topics_total < int(min_topics_per_pack):
            weak_reasons.append("topics_below_min")
        if clear_pct < float(min_clear_cells_pct):
            weak_reasons.append("clear_cells_pct_below_min")
        if unknown_pct > float(max_unknown_cells_pct):
            weak_reasons.append("unknown_cells_pct_above_max")
        conf_gate_value = 0.0 if confidence_avg_signal is None else float(confidence_avg_signal)
        if conf_gate_value < float(min_confidence_avg_signal):
            weak_reasons.append("confidence_avg_signal_below_min")
        if high_stakes_share < float(min_high_stakes_share):
            weak_reasons.append("high_stakes_share_below_min")

        weak = bool(weak_reasons)
        if weak:
            weak_pack_ids.append(pack_id)

        row = {
            "pack_id": pack_id,
            "pack_label": str(pack.get("pack_label") or pack_id),
            "concern_ids": list(pack.get("concern_ids") or []),
            "tradeoff": str(pack.get("tradeoff") or ""),
            "topics_total": int(topics_total),
            "high_stakes_topics_total": int(high_stakes_topics_total),
            "high_stakes_share": round(_clamp01(float(high_stakes_share)), 6),
            "cells_total": int(cells_total),
            "stance_counts": {
                "support": int(stance_counts.get("support", 0)),
                "oppose": int(stance_counts.get("oppose", 0)),
                "mixed": int(stance_counts.get("mixed", 0)),
                "unclear": int(stance_counts.get("unclear", 0)),
                "no_signal": int(stance_counts.get("no_signal", 0)),
            },
            "clear_cells_total": int(clear_total),
            "clear_cells_pct": round(_clamp01(float(clear_pct)), 6),
            "unknown_cells_total": int(unknown_total),
            "unknown_cells_pct": round(_clamp01(float(unknown_pct)), 6),
            "any_signal_cells_total": int(any_signal_total),
            "any_signal_cells_pct": round(_clamp01(float(any_signal_pct)), 6),
            "confidence_avg_signal": round(_clamp01(float(confidence_avg_signal)), 6)
            if confidence_avg_signal is not None
            else None,
            "quality_score": _quality_score(
                clear_pct=float(clear_pct),
                unknown_pct=float(unknown_pct),
                high_stakes_share=float(high_stakes_share),
                confidence_avg_signal=confidence_avg_signal,
            ),
            "weak": weak,
            "weak_reasons": weak_reasons,
        }
        pack_rows.append(row)

    weak_packs_total = len(weak_pack_ids)
    checks = {
        "packs_present": bool(len(pack_rows) > 0),
        "weak_packs_within_threshold": bool(weak_packs_total <= int(max_weak_packs)),
    }

    failure_reasons: list[str] = []
    if not checks["packs_present"]:
        failure_reasons.append("packs_missing")
    if not checks["weak_packs_within_threshold"]:
        failure_reasons.append("weak_packs_above_threshold")

    status = "ok" if not failure_reasons else "failed"
    pack_rows.sort(key=lambda x: (-float(x.get("quality_score") or 0.0), str(x.get("pack_id") or "")))

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "paths": {
            "snapshot": str(snapshot_path),
            "concerns_config": str(concerns_path),
        },
        "thresholds": {
            "min_topics_per_pack": int(min_topics_per_pack),
            "min_clear_cells_pct": round(float(min_clear_cells_pct), 6),
            "max_unknown_cells_pct": round(float(max_unknown_cells_pct), 6),
            "min_confidence_avg_signal": round(float(min_confidence_avg_signal), 6),
            "min_high_stakes_share": round(float(min_high_stakes_share), 6),
            "max_weak_packs": int(max_weak_packs),
        },
        "summary": {
            "packs_total": int(len(pack_rows)),
            "weak_packs_total": int(weak_packs_total),
            "weak_pack_ids": sorted(weak_pack_ids),
            "parties_total": int(len(party_ids)),
            "topics_total": int(len(topic_ids_all)),
            "high_stakes_topics_total": int(high_stakes_total),
            "topic_party_cells_total": int(len(topic_ids_all) * len(party_ids)),
        },
        "checks": checks,
        "failure_reasons": failure_reasons,
        "packs": pack_rows,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot_path = Path(str(args.snapshot).strip())
    concerns_path = Path(str(args.concerns_config).strip())
    out_path_raw = str(args.out).strip()

    if not snapshot_path.exists():
        print(json.dumps({"error": f"snapshot not found: {snapshot_path}"}, ensure_ascii=False))
        return 2
    if not concerns_path.exists():
        print(json.dumps({"error": f"concerns-config not found: {concerns_path}"}, ensure_ascii=False))
        return 2
    if int(args.min_topics_per_pack) < 0 or int(args.max_weak_packs) < 0:
        print(json.dumps({"error": "min-topics-per-pack and max-weak-packs must be >= 0"}, ensure_ascii=False))
        return 2

    try:
        snapshot = _load_json_obj(snapshot_path)
        concerns_cfg = _load_json_obj(concerns_path)
        report = build_report(
            snapshot=snapshot,
            concerns_cfg=concerns_cfg,
            min_topics_per_pack=int(args.min_topics_per_pack),
            min_clear_cells_pct=float(args.min_clear_cells_pct),
            max_unknown_cells_pct=float(args.max_unknown_cells_pct),
            min_confidence_avg_signal=float(args.min_confidence_avg_signal),
            min_high_stakes_share=float(args.min_high_stakes_share),
            max_weak_packs=int(args.max_weak_packs),
            snapshot_path=snapshot_path,
            concerns_path=concerns_path,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    if out_path_raw:
        out_path = Path(out_path_raw)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and str(report.get("status") or "") == "failed":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
