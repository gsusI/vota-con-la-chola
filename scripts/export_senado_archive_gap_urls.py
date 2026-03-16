#!/usr/bin/env python3
"""Export structured Senado archive-gap URLs from retry evidence JSON files.

Targets failures like:
  url=<...> -> HTTPStatusError: archive fallback: no snapshot candidates
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_NO_SNAPSHOT_TOKEN = "archive fallback: no snapshot candidates"
_URL_FAIL_RE = re.compile(r"^url=(?P<url>https?://\S+)\s+->\s+", re.I)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if isinstance(obj, dict):
        return obj
    return None


def _extract_url_from_failure(msg: str) -> str:
    token = str(msg or "").strip()
    if not token or _NO_SNAPSHOT_TOKEN not in token:
        return ""
    m = _URL_FAIL_RE.match(token)
    if not m:
        return ""
    return str(m.group("url") or "").strip()


def _url_kind(url: str) -> str:
    u = str(url or "")
    if "detalleiniciativa/index.html" in u:
        return "detalleiniciativa"
    if "ficopendataservlet" in u:
        return "ficopendataservlet"
    if "/iniciativas/enmiendas/index.html" in u:
        return "enmiendas_index"
    return "other"


def _parse_url_fields(url: str) -> dict[str, str]:
    parsed = urlparse(str(url or ""))
    q = parse_qs(parsed.query or "", keep_blank_values=True)

    def qv(key: str) -> str:
        vals = q.get(key) or []
        return str(vals[0] or "").strip() if vals else ""

    return {
        "url": str(url or "").strip(),
        "url_kind": _url_kind(url),
        "host": str(parsed.netloc or "").strip().lower(),
        "path": str(parsed.path or "").strip(),
        "legis": qv("legis"),
        "tipo_ex": qv("tipoEx") or qv("id1"),
        "num_ex": qv("numEx") or qv("id2"),
        "tipo_fich": qv("tipoFich"),
    }


def _expand_inputs(files: list[str], globs: list[str]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for token in files:
        p = Path(str(token or "").strip())
        if not p:
            continue
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if p.exists() and p.is_file():
            out.append(p)
    for pattern in globs:
        for matched in sorted(glob.glob(str(pattern or ""), recursive=True)):
            p = Path(matched)
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            if p.exists() and p.is_file():
                out.append(p)
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export structured archive-gap URLs from Senado retry evidence")
    p.add_argument("--retry-json", action="append", default=[], help="Retry evidence JSON path (repeatable)")
    p.add_argument("--retry-json-glob", action="append", default=[], help="Glob for retry evidence JSON files")
    p.add_argument("--strict-min-rows", type=int, default=1)
    p.add_argument("--out", required=True, help="Summary JSON output")
    p.add_argument("--csv-out", required=True, help="Archive-gap URLs CSV output")
    p.add_argument("--strict", action="store_true")
    return p.parse_args(argv)


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, str]]]:
    paths = _expand_inputs(list(args.retry_json or []), list(args.retry_json_glob or []))
    files_total = len(paths)
    files_parsed = 0
    archive_no_snapshot_failures_total = 0

    by_url_count: dict[str, int] = defaultdict(int)
    by_url_files: dict[str, set[str]] = defaultdict(set)

    for path in paths:
        obj = _read_json(path)
        if obj is None:
            continue
        files_parsed += 1
        failures = obj.get("failures")
        if not isinstance(failures, list):
            continue
        for raw in failures:
            url = _extract_url_from_failure(str(raw or ""))
            if not url:
                continue
            archive_no_snapshot_failures_total += 1
            by_url_count[url] += 1
            by_url_files[url].add(str(path))

    rows: list[dict[str, str]] = []
    for url, count in sorted(by_url_count.items(), key=lambda kv: (-kv[1], kv[0])):
        base = _parse_url_fields(url)
        files = sorted(by_url_files.get(url) or [])
        row = {
            **base,
            "failures": str(int(count)),
            "source_files": str(len(files)),
            "source_files_joined": "|".join(files),
        }
        rows.append(row)

    checks = {
        "has_inputs": bool(files_total > 0),
        "has_rows": bool(len(rows) >= max(0, int(args.strict_min_rows or 0))),
    }
    status = "ok" if all(bool(v) for v in checks.values()) else "degraded"
    strict_fail_reasons: list[str] = []
    if not checks["has_inputs"]:
        strict_fail_reasons.append("no_input_files")
    if not checks["has_rows"]:
        strict_fail_reasons.append("rows_below_min")

    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "status": status,
        "inputs": {
            "files_total": int(files_total),
            "files_parsed": int(files_parsed),
        },
        "totals": {
            "archive_no_snapshot_failures_total": int(archive_no_snapshot_failures_total),
            "unique_urls_total": int(len(rows)),
        },
        "limits": {
            "strict_min_rows": int(max(0, int(args.strict_min_rows or 0))),
        },
        "checks": checks,
        "strict_fail_reasons": strict_fail_reasons,
        "sample_urls": [r["url"] for r in rows[:20]],
    }
    return report, rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "url",
        "url_kind",
        "host",
        "path",
        "legis",
        "tipo_ex",
        "num_ex",
        "tipo_fich",
        "failures",
        "source_files",
        "source_files_joined",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: str(row.get(k, "") or "") for k in fieldnames})


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = Path(str(args.out))
    csv_out = Path(str(args.csv_out))

    report, rows = build_report(args)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")
    _write_csv(csv_out, rows)

    if bool(args.strict) and str(report.get("status") or "") != "ok":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
