#!/usr/bin/env python3
"""Report reproducible status of Senado cookie/session lever readiness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STRICT_FAIL_EXIT = 4


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        txt = value.strip().lower()
        return txt in {"1", "true", "yes", "y", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return None
        try:
            return int(float(txt))
        except ValueError:
            return None
    return None


def _cookie_fingerprint_part(cookie: dict[str, Any]) -> str:
    name = str(cookie.get("name") or "").strip()
    domain = str(cookie.get("domain") or "").strip().lower()
    path = str(cookie.get("path") or "/").strip() or "/"
    secure = "1" if _as_bool(cookie.get("secure")) else "0"
    http_only = "1" if _as_bool(cookie.get("httpOnly")) else "0"
    same_site = str(cookie.get("sameSite") or "").strip().lower()
    expires = _as_int(cookie.get("expires"))
    expires_bucket = "session" if (expires is None or expires <= 0) else "persistent"
    return "|".join([name, domain, path, secure, http_only, same_site, expires_bucket])


@dataclass(frozen=True)
class CookieEval:
    total: int
    domain_total: int
    persistent_total: int
    unexpired_persistent_total: int
    session_total: int
    secure_total: int
    http_only_total: int
    names: list[str]
    domain_names: list[str]
    fingerprint: str


def _evaluate_cookies(
    cookies: list[dict[str, Any]], *, domain_contains: str, now_ts: int
) -> CookieEval:
    domain_token = domain_contains.strip().lower()
    domain_cookies: list[dict[str, Any]] = []
    for row in cookies:
        domain = str(row.get("domain") or "").strip().lower()
        if not domain_token or domain_token in domain:
            domain_cookies.append(row)

    persistent_total = 0
    unexpired_persistent_total = 0
    session_total = 0
    secure_total = 0
    http_only_total = 0
    names: set[str] = set()
    domain_names: set[str] = set()
    fingerprint_parts: list[str] = []

    for row in domain_cookies:
        names.add(str(row.get("name") or "").strip())
        domain_names.add(str(row.get("domain") or "").strip().lower())
        if _as_bool(row.get("secure")):
            secure_total += 1
        if _as_bool(row.get("httpOnly")):
            http_only_total += 1
        expires = _as_int(row.get("expires"))
        if expires is None or expires <= 0:
            session_total += 1
        else:
            persistent_total += 1
            if expires > now_ts:
                unexpired_persistent_total += 1
        fingerprint_parts.append(_cookie_fingerprint_part(row))

    fingerprint = hashlib.sha256("\n".join(sorted(fingerprint_parts)).encode("utf-8")).hexdigest()
    return CookieEval(
        total=len(cookies),
        domain_total=len(domain_cookies),
        persistent_total=persistent_total,
        unexpired_persistent_total=unexpired_persistent_total,
        session_total=session_total,
        secure_total=secure_total,
        http_only_total=http_only_total,
        names=sorted(n for n in names if n),
        domain_names=sorted(n for n in domain_names if n),
        fingerprint=fingerprint,
    )


def build_report(
    *,
    cookie_file: Path,
    domain_contains: str,
    max_age_hours: float,
    min_domain_cookies: int,
    min_unexpired_persistent_cookies: int,
) -> dict[str, Any]:
    now = _now_utc()
    now_ts = int(now.timestamp())
    try:
        raw = json.loads(cookie_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "generated_at": now.isoformat(timespec="seconds"),
            "status": "failed",
            "error": f"invalid_json:{exc}",
            "cookie_file": _display_path(cookie_file),
        }
    if not isinstance(raw, list):
        return {
            "generated_at": now.isoformat(timespec="seconds"),
            "status": "failed",
            "error": "cookie_file_must_be_json_array",
            "cookie_file": _display_path(cookie_file),
        }

    cookies: list[dict[str, Any]] = []
    for row in raw:
        if isinstance(row, dict):
            cookies.append(row)

    stat = cookie_file.stat()
    file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    file_age_hours = max(0.0, (now - file_mtime).total_seconds() / 3600.0)
    evaluation = _evaluate_cookies(cookies, domain_contains=domain_contains, now_ts=now_ts)

    checks = {
        "has_domain_cookies": evaluation.domain_total >= max(0, int(min_domain_cookies)),
        "file_age_within_threshold": file_age_hours <= float(max_age_hours),
        "has_unexpired_persistent_cookies": evaluation.unexpired_persistent_total
        >= max(0, int(min_unexpired_persistent_cookies)),
    }
    reasons: list[str] = []
    if not checks["has_domain_cookies"]:
        reasons.append("no_domain_cookies")
    if not checks["file_age_within_threshold"]:
        reasons.append("cookie_file_stale")
    if not checks["has_unexpired_persistent_cookies"]:
        reasons.append("no_unexpired_persistent_cookies")
    status = "ok" if all(checks.values()) else "degraded"

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "status": status,
        "cookie_file": _display_path(cookie_file),
        "domain_contains": domain_contains,
        "thresholds": {
            "max_age_hours": float(max_age_hours),
            "min_domain_cookies": int(min_domain_cookies),
            "min_unexpired_persistent_cookies": int(min_unexpired_persistent_cookies),
        },
        "file": {
            "modified_at": file_mtime.isoformat(timespec="seconds"),
            "age_hours": round(file_age_hours, 3),
            "size_bytes": int(stat.st_size),
        },
        "cookies": {
            "total": evaluation.total,
            "domain_total": evaluation.domain_total,
            "persistent_total": evaluation.persistent_total,
            "unexpired_persistent_total": evaluation.unexpired_persistent_total,
            "session_total": evaluation.session_total,
            "secure_total": evaluation.secure_total,
            "http_only_total": evaluation.http_only_total,
            "domain_names": evaluation.domain_names,
            "cookie_names": evaluation.names,
            "structural_fingerprint_sha256": evaluation.fingerprint,
        },
        "checks": checks,
        "no_new_lever": status != "ok",
        "strict_fail_reasons": reasons,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cookie-file", required=True, help="Playwright-style cookies JSON file.")
    parser.add_argument("--domain-contains", default="senado.es", help="Domain token filter.")
    parser.add_argument("--max-age-hours", type=float, default=24.0, help="Freshness threshold.")
    parser.add_argument(
        "--min-domain-cookies", type=int, default=1, help="Minimum cookies for selected domain."
    )
    parser.add_argument(
        "--min-unexpired-persistent-cookies",
        type=int,
        default=1,
        help="Minimum unexpired persistent cookies required for lever readiness.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless status=ok.")
    parser.add_argument("--out", default="", help="Optional JSON output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cookie_file = Path(args.cookie_file)
    if not cookie_file.exists():
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "cookie_file_not_found",
                    "cookie_file": _display_path(cookie_file),
                },
                ensure_ascii=False,
            )
        )
        return STRICT_FAIL_EXIT if args.strict else 0

    report = build_report(
        cookie_file=cookie_file,
        domain_contains=str(args.domain_contains),
        max_age_hours=float(args.max_age_hours),
        min_domain_cookies=int(args.min_domain_cookies),
        min_unexpired_persistent_cookies=int(args.min_unexpired_persistent_cookies),
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
