#!/usr/bin/env python3
"""Validate whether manual Senado captures produced a usable cookie/session lever."""

from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STRICT_FAIL_EXIT = 4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _display(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


def _is_access_denied(title: str, html: str) -> bool:
    t = (title or "").strip().lower()
    h = (html or "").strip().lower()
    if "access denied" in t:
        return True
    if "you don't have permission to access" in h:
        return True
    if "request id:" in h and "access denied" in h:
        return True
    if "just a moment" in t and "_cf_chl_opt" in h:
        return True
    return False


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _capture_row(meta_path: Path, *, cookie_domain_contains: str) -> dict[str, Any]:
    meta = _load_json(meta_path)
    result = meta.get("result") or {}
    title = str(result.get("title") or "")
    final_url = str(result.get("final_url") or "")
    html_len = int(result.get("html_len") or 0)

    base_name = meta_path.name
    if base_name.endswith(".meta.json"):
        prefix = base_name[: -len(".meta.json")]
    else:
        prefix = meta_path.stem
    html_path = meta_path.with_name(f"{prefix}.html")
    cookie_path = meta_path.with_name(f"{prefix}.cookies.json")

    html = ""
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8", errors="replace")
    denied = _is_access_denied(title, html)

    cookies_total = 0
    cookies_domain_total = 0
    if cookie_path.exists():
        try:
            cookies = _load_json(cookie_path)
            if isinstance(cookies, list):
                cookies_total = len(cookies)
                token = cookie_domain_contains.strip().lower()
                cookies_domain_total = len(
                    [
                        row
                        for row in cookies
                        if isinstance(row, dict)
                        and token in str((row.get("domain") or "")).strip().lower()
                    ]
                )
        except Exception:  # noqa: BLE001
            cookies_total = 0
            cookies_domain_total = 0

    return {
        "meta_file": _display(meta_path),
        "html_file": _display(html_path),
        "cookie_file": _display(cookie_path),
        "result_status": str(result.get("status") or ""),
        "title": title,
        "final_url": final_url,
        "html_len": html_len,
        "access_denied_detected": denied,
        "cookies_total": cookies_total,
        "cookies_domain_total": cookies_domain_total,
        "usable_capture": (not denied) and (cookies_domain_total > 0),
    }


def build_report(
    *,
    captures_glob: str,
    cookie_domain_contains: str,
    min_captures: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for raw in sorted(glob.glob(captures_glob)):
        p = Path(raw)
        if p.is_file() and p.suffix == ".json" and p.name.endswith(".meta.json"):
            try:
                rows.append(_capture_row(p, cookie_domain_contains=cookie_domain_contains))
            except Exception as exc:  # noqa: BLE001
                rows.append(
                    {
                        "meta_file": _display(p),
                        "error": f"{type(exc).__name__}: {exc}",
                        "usable_capture": False,
                        "access_denied_detected": False,
                        "cookies_total": 0,
                        "cookies_domain_total": 0,
                    }
                )

    captures_total = len(rows)
    usable_total = sum(1 for row in rows if bool(row.get("usable_capture")))
    denied_total = sum(1 for row in rows if bool(row.get("access_denied_detected")))
    cookies_domain_total = sum(int(row.get("cookies_domain_total") or 0) for row in rows)

    checks = {
        "has_min_captures": captures_total >= max(0, int(min_captures)),
        "has_usable_capture": usable_total > 0,
    }
    reasons: list[str] = []
    if not checks["has_min_captures"]:
        reasons.append("insufficient_captures")
    if not checks["has_usable_capture"]:
        reasons.append("no_usable_capture")
    status = "ok" if all(checks.values()) else "degraded"

    return {
        "generated_at": _now_iso(),
        "status": status,
        "captures_glob": captures_glob,
        "cookie_domain_contains": cookie_domain_contains,
        "thresholds": {"min_captures": int(min_captures)},
        "totals": {
            "captures_total": captures_total,
            "usable_captures_total": usable_total,
            "access_denied_captures_total": denied_total,
            "cookies_domain_total": cookies_domain_total,
        },
        "checks": checks,
        "strict_fail_reasons": reasons,
        "captures": rows,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--captures-glob",
        required=True,
        help="Glob pattern for *.meta.json capture files (e.g. etl/data/raw/manual/senado_*_*.meta.json).",
    )
    parser.add_argument("--cookie-domain-contains", default="senado.es")
    parser.add_argument("--min-captures", type=int, default=1)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        captures_glob=str(args.captures_glob),
        cookie_domain_contains=str(args.cookie_domain_contains),
        min_captures=int(args.min_captures),
    )
    out = str(args.out or "").strip()
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and str(report.get("status")) != "ok":
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
