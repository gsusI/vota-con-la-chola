#!/usr/bin/env python3
"""Report continuity checks for liberty atlas changelog history."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_CHANGELOG_JSONL = Path("docs/etl/runs/liberty_restrictions_snapshot_changelog.jsonl")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check continuity of liberty atlas changelog history")
    p.add_argument("--changelog-jsonl", default=str(DEFAULT_CHANGELOG_JSONL))
    p.add_argument("--snapshot-date", default="", help="Expected latest snapshot_date")
    p.add_argument("--release-json", default="", help="Optional release JSON to cross-check latest entry")
    p.add_argument("--strict", action="store_true", help="Exit code 4 when status != ok")
    p.add_argument("--out", default="", help="Optional report JSON path")
    return p.parse_args(argv)


def _read_changelog(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if _safe_text(line)]
    entries: list[dict[str, Any]] = []
    malformed = 0
    for line_no, raw in enumerate(lines, start=1):
        try:
            payload = _safe_obj(json.loads(raw))
            payload["_line_no"] = line_no
            entries.append(payload)
        except Exception:  # noqa: BLE001
            malformed += 1
    return entries, malformed


def build_report(
    entries: list[dict[str, Any]],
    *,
    malformed_lines_total: int,
    expected_snapshot_date: str,
    release_payload: dict[str, Any] | None,
    release_path: str,
    changelog_path: str,
) -> dict[str, Any]:
    strict_fail_reasons: list[str] = []

    if not entries:
        strict_fail_reasons.append("empty_history")
    if malformed_lines_total > 0:
        strict_fail_reasons.append("malformed_history_lines")

    entry_ids: list[str] = []
    run_at_values: list[str] = []
    snapshot_dates: list[str] = []
    continuity_breaks: list[dict[str, Any]] = []
    self_referential_previous_snapshot_entries = 0

    previous_snapshot_date = ""
    for idx, entry in enumerate(entries):
        entry_id = _safe_text(entry.get("entry_id"))
        snapshot_date = _safe_text(entry.get("snapshot_date"))
        previous_entry_snapshot = _safe_text(entry.get("previous_snapshot_date"))
        run_at = _safe_text(entry.get("run_at"))

        if entry_id:
            entry_ids.append(entry_id)
        if run_at:
            run_at_values.append(run_at)
        if snapshot_date:
            snapshot_dates.append(snapshot_date)

        if idx == 0:
            previous_snapshot_date = snapshot_date
            continue

        if previous_entry_snapshot and previous_entry_snapshot != previous_snapshot_date:
            # Allow idempotent reruns where previous_snapshot_date points to the same
            # snapshot_date as the current entry (self-loop on same release).
            if snapshot_date and previous_entry_snapshot == snapshot_date:
                self_referential_previous_snapshot_entries += 1
            else:
                continuity_breaks.append(
                    {
                        "line_no": int(entry.get("_line_no") or 0),
                        "entry_id": entry_id,
                        "expected_previous_snapshot_date": previous_snapshot_date,
                        "actual_previous_snapshot_date": previous_entry_snapshot,
                    }
                )
        previous_snapshot_date = snapshot_date or previous_snapshot_date

    if len(entry_ids) != len(set(entry_ids)):
        strict_fail_reasons.append("duplicate_entry_id")
    if run_at_values and run_at_values != sorted(run_at_values):
        strict_fail_reasons.append("run_at_not_monotonic")
    if continuity_breaks:
        strict_fail_reasons.append("previous_snapshot_chain_break")

    latest_entry = entries[-1] if entries else {}
    latest_snapshot_date = _safe_text(latest_entry.get("snapshot_date"))
    latest_entry_id = _safe_text(latest_entry.get("entry_id"))
    expected = _safe_text(expected_snapshot_date) or latest_snapshot_date
    if expected and latest_snapshot_date != expected:
        strict_fail_reasons.append("latest_snapshot_date_mismatch")

    release_checks: dict[str, Any] = {"provided": bool(release_payload)}
    if release_payload is not None:
        release_snapshot_date = _safe_text(release_payload.get("snapshot_date"))
        release_status = _safe_text(release_payload.get("status"))
        release_entry_id = _safe_text(_safe_obj(release_payload.get("changelog")).get("entry_id"))
        release_history_latest_entry_id = _safe_text(
            _safe_obj(release_payload.get("changelog")).get("history_latest_entry_id")
        )

        release_checks.update(
            {
                "path": release_path,
                "status": release_status,
                "snapshot_date": release_snapshot_date,
                "entry_id": release_entry_id,
                "history_latest_entry_id": release_history_latest_entry_id,
            }
        )

        if release_status not in {"ok", "missing_inputs"}:
            strict_fail_reasons.append("release_status_invalid")
        if release_snapshot_date and expected and release_snapshot_date != expected:
            strict_fail_reasons.append("release_snapshot_date_mismatch")
        if latest_entry_id and release_entry_id and release_entry_id != latest_entry_id:
            strict_fail_reasons.append("release_entry_id_mismatch")
        if latest_entry_id and release_history_latest_entry_id and release_history_latest_entry_id != latest_entry_id:
            strict_fail_reasons.append("release_history_latest_entry_id_mismatch")

    checks = {
        "history_nonempty": bool(entries),
        "malformed_lines_ok": malformed_lines_total == 0,
        "entry_ids_unique": len(entry_ids) == len(set(entry_ids)),
        "run_at_monotonic": (not run_at_values) or (run_at_values == sorted(run_at_values)),
        "previous_snapshot_chain_ok": not continuity_breaks,
        "latest_snapshot_matches_expected": (not expected) or (latest_snapshot_date == expected),
        "release_consistent": not any(reason.startswith("release_") for reason in strict_fail_reasons),
    }

    status = "ok" if not strict_fail_reasons else "failed"
    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "changelog_path": changelog_path,
        "expected_snapshot_date": expected,
        "entries_total": len(entries),
        "malformed_lines_total": int(malformed_lines_total),
        "latest_entry_id": latest_entry_id,
        "latest_snapshot_date": latest_snapshot_date,
        "checks": checks,
        "continuity_breaks": continuity_breaks,
        "self_referential_previous_snapshot_entries": int(self_referential_previous_snapshot_entries),
        "release_checks": release_checks,
        "strict_fail_reasons": strict_fail_reasons,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    changelog_path = Path(str(args.changelog_jsonl))
    entries, malformed = _read_changelog(changelog_path)

    release_payload: dict[str, Any] | None = None
    release_path = _safe_text(args.release_json)
    if release_path:
        p = Path(release_path)
        if p.exists():
            try:
                release_payload = _safe_obj(json.loads(p.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                release_payload = {"status": "invalid_json"}
        else:
            release_payload = {"status": "missing_release_json"}

    report = build_report(
        entries,
        malformed_lines_total=malformed,
        expected_snapshot_date=_safe_text(args.snapshot_date),
        release_payload=release_payload,
        release_path=release_path,
        changelog_path=str(changelog_path),
    )

    if _safe_text(args.out):
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if bool(args.strict) and _safe_text(report.get("status")) != "ok":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
