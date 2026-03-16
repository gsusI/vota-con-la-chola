#!/usr/bin/env python3
"""Export a fresh Senado retry packet using canonical packet-only dedupe.

This utility codifies the operational contract used in recent Senado retries:
- input: actionable pool CSV (typically exported from missing initiative docs)
- dedupe: exclude only URLs already present in prior retry packet CSVs
- output: bounded fresh packet CSV + JSON summary for evidence/gates
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _display_path(path: Path) -> str:
    if not path.is_absolute():
        return str(path)
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return path.name


def _find_doc_url(row: dict[str, Any]) -> str:
    candidates = ("doc_url", "url", "source_doc_url", "capture_url")
    for k in candidates:
        value = str(row.get(k) or "").strip()
        if value:
            return value
    for k, value in row.items():
        key = str(k or "").strip().lower()
        if "url" not in key:
            continue
        token = str(value or "").strip()
        if token:
            return token
    return ""


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = [str(x or "").strip() for x in (reader.fieldnames or []) if str(x or "").strip()]
        rows: list[dict[str, str]] = []
        for row in reader:
            if not isinstance(row, dict):
                continue
            out: dict[str, str] = {}
            for k, v in row.items():
                kk = str(k or "").strip()
                if not kk:
                    continue
                out[kk] = str(v or "").strip()
            rows.append(out)
    return fieldnames, rows


def _load_pool_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    fieldnames, raw_rows = _read_csv_rows(path)
    out: list[dict[str, str]] = []
    for row in raw_rows:
        doc_url = _find_doc_url(row)
        if not doc_url:
            continue
        item = dict(row)
        item["doc_url"] = doc_url
        out.append(item)
    return fieldnames, out


def _load_refs_file(path: Path) -> list[Path]:
    refs: list[Path] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        token = str(line or "").strip()
        if not token or token.startswith("#"):
            continue
        refs.append(Path(token))
    return refs


def _expand_packet_paths(
    *,
    packet_csv: list[str],
    packet_csv_glob: list[str],
    packet_csv_refs_file: str,
    packet_csv_refs_file_only: bool,
) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()

    def add_path(path: Path) -> None:
        p = path
        try:
            key = str(p.resolve())
        except Exception:  # noqa: BLE001
            key = str(p)
        if key in seen:
            return
        seen.add(key)
        out.append(p)

    refs_file = str(packet_csv_refs_file or "").strip()
    refs_listed: list[Path] = []
    if refs_file:
        refs_path = Path(refs_file)
        if not refs_path.exists():
            raise FileNotFoundError(f"packet_csv_refs_file_not_found: {refs_path}")
        refs_listed = _load_refs_file(refs_path)

    if bool(packet_csv_refs_file_only):
        if not refs_listed:
            raise ValueError("packet_csv_refs_file_only_requires_non_empty_refs_file")
        for ref in refs_listed:
            add_path(ref)
    else:
        for token in packet_csv:
            tt = str(token or "").strip()
            if tt:
                add_path(Path(tt))

        for pattern in packet_csv_glob:
            pp = str(pattern or "").strip()
            if not pp:
                continue
            for matched in sorted(glob.glob(pp, recursive=True)):
                add_path(Path(matched))

        for ref in refs_listed:
            add_path(ref)

    existing = [p for p in out if p.exists() and p.is_file()]
    existing.sort(key=lambda p: _display_path(p))
    return existing


def _load_used_urls(packet_paths: list[Path]) -> tuple[set[str], list[dict[str, Any]]]:
    used_urls: set[str] = set()
    packet_stats: list[dict[str, Any]] = []
    for p in packet_paths:
        total_rows = 0
        valid_url_rows = 0
        unique_urls_before = len(used_urls)
        try:
            _, rows = _read_csv_rows(p)
            for row in rows:
                total_rows += 1
                url = _find_doc_url(row)
                if not url:
                    continue
                valid_url_rows += 1
                used_urls.add(url)
        except Exception as exc:  # noqa: BLE001
            packet_stats.append(
                {
                    "path": _display_path(p),
                    "status": "error",
                    "error": str(exc),
                    "rows_total": 0,
                    "rows_with_doc_url": 0,
                    "new_unique_urls": 0,
                }
            )
            continue

        packet_stats.append(
            {
                "path": _display_path(p),
                "status": "ok",
                "rows_total": int(total_rows),
                "rows_with_doc_url": int(valid_url_rows),
                "new_unique_urls": int(len(used_urls) - unique_urls_before),
            }
        )
    return used_urls, packet_stats


def _write_csv(path: Path, *, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base = [f for f in fieldnames if f and f != "fresh_rank"]
    if "doc_url" not in base:
        base.append("doc_url")
    final_fields = ["fresh_rank", *base]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=final_fields)
        w.writeheader()
        for idx, row in enumerate(rows, start=1):
            payload = {"fresh_rank": str(idx)}
            payload.update({k: str(row.get(k, "") or "") for k in base})
            w.writerow(payload)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export Senado fresh retry packet using packet-only dedupe")
    p.add_argument("--pool-csv", required=True, help="Actionable pool CSV (must include doc_url or url-like column)")
    p.add_argument("--packet-csv", action="append", default=[], help="Existing retry packet CSV (repeatable)")
    p.add_argument(
        "--packet-csv-glob",
        action="append",
        default=[],
        help="Glob for existing retry packet CSVs (repeatable, supports **)",
    )
    p.add_argument(
        "--packet-csv-refs-file",
        default="",
        help="Text file listing existing retry packet CSV paths (one per line)",
    )
    p.add_argument(
        "--packet-csv-refs-file-only",
        action="store_true",
        help="Use only packet refs listed in --packet-csv-refs-file (ignores --packet-csv/--packet-csv-glob)",
    )
    p.add_argument("--max-rows", type=int, default=80, help="Max fresh rows to emit (0 = unlimited)")
    p.add_argument("--strict-min-fresh-rows", type=int, default=1)
    p.add_argument("--out", required=True, help="JSON summary output path")
    p.add_argument("--csv-out", required=True, help="Fresh packet CSV output path")
    p.add_argument("--used-urls-out", default="", help="Optional text output for deduped used URLs")
    p.add_argument("--used-packet-refs-out", default="", help="Optional text output for resolved packet refs")
    p.add_argument("--strict", action="store_true", help="Exit 4 when summary status != ok")
    return p.parse_args(argv)


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[dict[str, str]]]:
    pool_csv = Path(str(args.pool_csv))
    if not pool_csv.exists() or not pool_csv.is_file():
        raise FileNotFoundError(f"pool_csv_not_found: {pool_csv}")

    pool_fieldnames, pool_rows = _load_pool_rows(pool_csv)
    packet_paths = _expand_packet_paths(
        packet_csv=list(args.packet_csv or []),
        packet_csv_glob=list(args.packet_csv_glob or []),
        packet_csv_refs_file=str(args.packet_csv_refs_file or ""),
        packet_csv_refs_file_only=bool(args.packet_csv_refs_file_only),
    )
    used_urls, packet_stats = _load_used_urls(packet_paths)

    max_rows = max(0, int(args.max_rows or 0))
    hard_cap = max_rows if max_rows > 0 else 1_000_000_000
    seen_fresh: set[str] = set()
    fresh_rows: list[dict[str, str]] = []
    excluded_used = 0
    excluded_duplicate_in_pool = 0
    for row in pool_rows:
        doc_url = str(row.get("doc_url") or "")
        if not doc_url:
            continue
        if doc_url in used_urls:
            excluded_used += 1
            continue
        if doc_url in seen_fresh:
            excluded_duplicate_in_pool += 1
            continue
        if len(fresh_rows) >= hard_cap:
            break
        fresh_rows.append(dict(row))
        seen_fresh.add(doc_url)

    checks = {
        "has_pool_rows": bool(len(pool_rows) > 0),
        "fresh_rows_min_met": bool(len(fresh_rows) >= max(0, int(args.strict_min_fresh_rows or 0))),
    }
    strict_fail_reasons: list[str] = []
    if not checks["has_pool_rows"]:
        strict_fail_reasons.append("no_pool_rows")
    if not checks["fresh_rows_min_met"]:
        strict_fail_reasons.append("fresh_rows_below_min")
    if len(pool_rows) > 0 and len(fresh_rows) == 0 and excluded_used > 0:
        strict_fail_reasons.append("packet_exhausted_by_canonical_dedupe")

    status = "ok" if all(bool(v) for v in checks.values()) else "degraded"

    report = {
        "generated_at": now_utc_iso(),
        "status": status,
        "selection_method": "retry_packet_only_dedup",
        "pool_csv": _display_path(pool_csv),
        "totals": {
            "pool_rows_total": int(len(pool_rows)),
            "pool_unique_urls_total": int(len({str(r.get('doc_url') or '') for r in pool_rows if str(r.get('doc_url') or '')})),
            "used_packet_files_total": int(len(packet_paths)),
            "used_urls_total": int(len(used_urls)),
            "excluded_used_urls_total": int(excluded_used),
            "excluded_duplicate_in_pool_total": int(excluded_duplicate_in_pool),
            "fresh_rows_total": int(len(fresh_rows)),
        },
        "limits": {
            "max_rows": int(max_rows),
            "strict_min_fresh_rows": int(max(0, int(args.strict_min_fresh_rows or 0))),
        },
        "checks": checks,
        "strict_fail_reasons": strict_fail_reasons,
        "packet_sources": packet_stats,
    }
    used_lines = sorted(used_urls)
    return report, used_lines, fresh_rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = Path(str(args.out))
    csv_out_path = Path(str(args.csv_out))
    used_urls_out = Path(str(args.used_urls_out)) if str(args.used_urls_out or "").strip() else None
    used_refs_out = Path(str(args.used_packet_refs_out)) if str(args.used_packet_refs_out or "").strip() else None

    try:
        report, used_lines, fresh_rows = build_report(args)
    except FileNotFoundError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    pool_fieldnames, _ = _load_pool_rows(Path(str(args.pool_csv)))
    _write_csv(csv_out_path, fieldnames=pool_fieldnames, rows=fresh_rows)

    if used_urls_out is not None:
        _write_lines(used_urls_out, used_lines)
    if used_refs_out is not None:
        refs = [str(item.get("path") or "") for item in (report.get("packet_sources") or []) if item.get("path")]
        _write_lines(used_refs_out, refs)

    if bool(args.strict) and str(report.get("status") or "") != "ok":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
