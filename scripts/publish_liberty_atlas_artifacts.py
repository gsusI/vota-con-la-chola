#!/usr/bin/env python3
"""Publish liberty atlas artifacts into etl/data/published and optional GH Pages export."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SNAPSHOT_JSON = Path("docs/etl/sprints/AI-OPS-118/exports/liberty_restrictions_snapshot_latest.json")
DEFAULT_IRLC_PARQUET = Path("docs/etl/sprints/AI-OPS-124/exports/irlc_by_fragment_latest.parquet")
DEFAULT_ACCOUNTABILITY_PARQUET = Path("docs/etl/sprints/AI-OPS-124/exports/accountability_edges_latest.parquet")
DEFAULT_DIFF_JSON = Path("docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_diff_latest.json")
DEFAULT_CHANGELOG_ENTRY_JSON = Path("docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_changelog_latest.json")
DEFAULT_CHANGELOG_HISTORY_JSONL = Path("docs/etl/runs/liberty_restrictions_snapshot_changelog.jsonl")
DEFAULT_PUBLISHED_DIR = Path("etl/data/published")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_with_meta(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {
        "source_path": str(src),
        "path": str(dst),
        "bytes": int(dst.stat().st_size),
        "sha256": _sha256_file(dst),
    }


def _history_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "entries_total": 0,
            "malformed_lines_total": 0,
            "latest_entry_id": "",
            "latest_snapshot_date": "",
        }
    raw_lines = [line for line in path.read_text(encoding="utf-8").splitlines() if _safe_text(line)]
    malformed = 0
    entries: list[dict[str, Any]] = []
    for line in raw_lines:
        try:
            entries.append(_safe_obj(json.loads(line)))
        except Exception:  # noqa: BLE001
            malformed += 1
    latest = entries[-1] if entries else {}
    return {
        "entries_total": len(entries),
        "malformed_lines_total": malformed,
        "latest_entry_id": _safe_text(latest.get("entry_id")),
        "latest_snapshot_date": _safe_text(latest.get("snapshot_date")),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publish liberty atlas artifacts to published/GH pages folders")
    p.add_argument("--snapshot-json", default=str(DEFAULT_SNAPSHOT_JSON))
    p.add_argument("--irlc-parquet", default=str(DEFAULT_IRLC_PARQUET))
    p.add_argument("--accountability-parquet", default=str(DEFAULT_ACCOUNTABILITY_PARQUET))
    p.add_argument("--diff-json", default=str(DEFAULT_DIFF_JSON))
    p.add_argument("--changelog-entry-json", default=str(DEFAULT_CHANGELOG_ENTRY_JSON))
    p.add_argument("--changelog-history-jsonl", default=str(DEFAULT_CHANGELOG_HISTORY_JSONL))
    p.add_argument("--snapshot-date", default="")
    p.add_argument("--published-dir", default=str(DEFAULT_PUBLISHED_DIR))
    p.add_argument("--allow-missing", action="store_true")
    p.add_argument("--gh-pages-out", default="", help="Optional JSON mirror path (e.g. docs/gh-pages/.../liberty_atlas_release.json)")
    p.add_argument("--out", default="", help="Optional operation report JSON")
    return p.parse_args(argv)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_snapshot_date(cli_value: str, snapshot_payload: dict[str, Any]) -> str:
    token = _safe_text(cli_value)
    if token:
        return token
    return _safe_text(snapshot_payload.get("snapshot_date"))


def _missing_payload(snapshot_date: str, missing_inputs: list[str]) -> dict[str, Any]:
    return {
        "generated_at": now_utc_iso(),
        "status": "missing_inputs",
        "snapshot_date": snapshot_date,
        "missing_inputs": missing_inputs,
        "published_files": [],
        "release_path": "",
        "release_latest_path": "",
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot_json = Path(str(args.snapshot_json))
    irlc_parquet = Path(str(args.irlc_parquet))
    accountability_parquet = Path(str(args.accountability_parquet))
    diff_json = Path(str(args.diff_json))
    changelog_entry_json = Path(str(args.changelog_entry_json))
    changelog_history_jsonl = Path(str(args.changelog_history_jsonl))
    published_dir = Path(str(args.published_dir))

    required_inputs = {
        "snapshot_json": snapshot_json,
        "irlc_parquet": irlc_parquet,
        "accountability_parquet": accountability_parquet,
        "diff_json": diff_json,
        "changelog_entry_json": changelog_entry_json,
        "changelog_history_jsonl": changelog_history_jsonl,
    }
    missing_inputs = [name for name, path in required_inputs.items() if not path.exists()]

    snapshot_payload: dict[str, Any] = {}
    if snapshot_json.exists():
        snapshot_payload = _load_json(snapshot_json)
    snapshot_date = _resolve_snapshot_date(str(args.snapshot_date or ""), snapshot_payload)

    if missing_inputs:
        report = _missing_payload(snapshot_date, missing_inputs)
        if _safe_text(args.gh_pages_out):
            _write_json(Path(str(args.gh_pages_out)), report)
        if _safe_text(args.out):
            _write_json(Path(str(args.out)), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if bool(args.allow_missing) else 2

    if not snapshot_date:
        report = {
            "generated_at": now_utc_iso(),
            "status": "invalid_snapshot_date",
            "snapshot_date": "",
            "error": "snapshot_date vacío (ni --snapshot-date ni snapshot_json.snapshot_date).",
        }
        if _safe_text(args.out):
            _write_json(Path(str(args.out)), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    snapshot_totals = _safe_obj(snapshot_payload.get("totals"))
    schema_version = _safe_text(snapshot_payload.get("schema_version"))
    restrictions_total = int(snapshot_totals.get("restrictions_total") or 0)

    published_dir.mkdir(parents=True, exist_ok=True)
    dated_paths = {
        "snapshot_json": published_dir / f"liberty-restrictions-atlas-{snapshot_date}.json",
        "irlc_parquet": published_dir / f"liberty-restrictions-irlc-by-fragment-{snapshot_date}.parquet",
        "accountability_parquet": published_dir / f"liberty-restrictions-accountability-edges-{snapshot_date}.parquet",
        "diff_json": published_dir / f"liberty-restrictions-diff-{snapshot_date}.json",
        "changelog_entry_json": published_dir / f"liberty-restrictions-changelog-entry-{snapshot_date}.json",
        "changelog_history_jsonl": published_dir / f"liberty-restrictions-changelog-history-{snapshot_date}.jsonl",
    }

    copied_meta = {
        "snapshot_json": _copy_with_meta(snapshot_json, dated_paths["snapshot_json"]),
        "irlc_parquet": _copy_with_meta(irlc_parquet, dated_paths["irlc_parquet"]),
        "accountability_parquet": _copy_with_meta(accountability_parquet, dated_paths["accountability_parquet"]),
        "diff_json": _copy_with_meta(diff_json, dated_paths["diff_json"]),
        "changelog_entry_json": _copy_with_meta(changelog_entry_json, dated_paths["changelog_entry_json"]),
        "changelog_history_jsonl": _copy_with_meta(changelog_history_jsonl, dated_paths["changelog_history_jsonl"]),
    }

    diff_payload = _load_json(diff_json)
    changelog_entry_payload = _load_json(changelog_entry_json)
    changelog_history_stats = _history_stats(changelog_history_jsonl)

    release_payload = {
        "generated_at": now_utc_iso(),
        "status": "ok",
        "snapshot_date": snapshot_date,
        "schema_version": schema_version,
        "snapshot_totals": snapshot_totals,
        "snapshot_restrictions_total": restrictions_total,
        "diff": {
            "status": _safe_text(diff_payload.get("status")),
            "changed_sections_total": int(diff_payload.get("changed_sections_total") or 0),
            "items_added_total": int(diff_payload.get("items_added_total") or 0),
            "items_removed_total": int(diff_payload.get("items_removed_total") or 0),
            "totals_changed": [str(item) for item in _safe_list(diff_payload.get("totals_changed")) if _safe_text(item)],
        },
        "changelog": {
            "entry_id": _safe_text(changelog_entry_payload.get("entry_id")),
            "appended": bool(changelog_entry_payload.get("appended")),
            "history_entries_total": int(changelog_entry_payload.get("history_entries_total") or 0),
            "history_malformed_lines_total": int(changelog_entry_payload.get("history_malformed_lines_total") or 0),
            "history_latest_entry_id": _safe_text(changelog_history_stats.get("latest_entry_id")),
            "history_latest_snapshot_date": _safe_text(changelog_history_stats.get("latest_snapshot_date")),
        },
        "published_files": copied_meta,
    }

    release_path = published_dir / f"liberty-restrictions-atlas-release-{snapshot_date}.json"
    release_latest_path = published_dir / "liberty-restrictions-atlas-release-latest.json"
    _write_json(release_path, release_payload)
    _write_json(release_latest_path, release_payload)

    report = {
        "generated_at": now_utc_iso(),
        "status": "ok",
        "snapshot_date": snapshot_date,
        "schema_version": schema_version,
        "snapshot_restrictions_total": restrictions_total,
        "release_path": str(release_path),
        "release_latest_path": str(release_latest_path),
        "published_files": copied_meta,
        "changelog": release_payload.get("changelog", {}),
        "diff": release_payload.get("diff", {}),
    }

    gh_pages_out = _safe_text(args.gh_pages_out)
    if gh_pages_out:
        _write_json(Path(gh_pages_out), release_payload)

    if _safe_text(args.out):
        _write_json(Path(str(args.out)), report)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

