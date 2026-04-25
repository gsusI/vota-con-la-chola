#!/usr/bin/env python3
"""Report progress of manual Senado captures against target queue."""

from __future__ import annotations

import argparse
import csv
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


STRICT_FAIL_EXIT = 4
DEFAULT_TARGETS_CSV = Path("docs/etl/sprints/AI-OPS-299/exports/senado_manual_capture_targets_latest.csv")
DEFAULT_OUT = Path("docs/etl/sprints/AI-OPS-300/evidence/senado_manual_capture_target_progress_latest.json")
DEFAULT_CSV_OUT = Path("docs/etl/sprints/AI-OPS-300/exports/senado_manual_capture_target_progress_latest.csv")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _display(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _normalize_url_exact(url: str) -> str:
    token = str(url or "").strip()
    if not token:
        return ""
    parsed = urlsplit(token)
    scheme = str(parsed.scheme or "").lower()
    netloc = str(parsed.netloc or "").lower()
    path = str(parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query_items = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    query = urlencode(query_items, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def _normalize_url_path(url: str) -> str:
    token = str(url or "").strip()
    if not token:
        return ""
    parsed = urlsplit(token)
    scheme = str(parsed.scheme or "").lower()
    netloc = str(parsed.netloc or "").lower()
    path = str(parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))


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


def _parse_dt(value: Any) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None
    try:
        fixed = token.replace("Z", "+00:00")
        dt = datetime.fromisoformat(fixed)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _capture_row(meta_path: Path, *, cookie_domain_contains: str) -> dict[str, Any]:
    meta = _load_json(meta_path)
    result = meta.get("result") if isinstance(meta, dict) else {}
    result = result if isinstance(result, dict) else {}

    final_url = str(result.get("final_url") or meta.get("url") or "").strip()
    title = str(result.get("title") or "")
    ended_at = _parse_dt(result.get("ended_at"))

    base_name = meta_path.name
    prefix = base_name[: -len(".meta.json")] if base_name.endswith(".meta.json") else meta_path.stem
    html_path = meta_path.with_name(f"{prefix}.html")
    cookie_path = meta_path.with_name(f"{prefix}.cookies.json")

    html = ""
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8", errors="replace")

    cookies_total = 0
    cookies_domain_total = 0
    if cookie_path.exists():
        try:
            cookies = _load_json(cookie_path)
            if isinstance(cookies, list):
                cookies_total = len(cookies)
                domain_token = str(cookie_domain_contains or "").strip().lower()
                cookies_domain_total = len(
                    [
                        c
                        for c in cookies
                        if isinstance(c, dict)
                        and domain_token in str((c.get("domain") or "")).strip().lower()
                    ]
                )
        except Exception:  # noqa: BLE001
            cookies_total = 0
            cookies_domain_total = 0

    denied = _is_access_denied(title, html)
    usable = (not denied) and (cookies_domain_total > 0)

    if ended_at is None:
        ended_at = datetime.fromtimestamp(meta_path.stat().st_mtime, tz=timezone.utc)

    return {
        "meta_file": _display(meta_path),
        "html_file": _display(html_path),
        "cookie_file": _display(cookie_path),
        "final_url": final_url,
        "final_url_exact_key": _normalize_url_exact(final_url),
        "final_url_path_key": _normalize_url_path(final_url),
        "title": title,
        "access_denied_detected": bool(denied),
        "cookies_total": int(cookies_total),
        "cookies_domain_total": int(cookies_domain_total),
        "usable_capture": bool(usable),
        "ended_at": ended_at.isoformat(),
        "ended_at_epoch": float(ended_at.timestamp()),
    }


def _pick_newer(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if existing is None:
        return candidate
    if float(candidate.get("ended_at_epoch") or 0.0) >= float(existing.get("ended_at_epoch") or 0.0):
        return candidate
    return existing


def _load_capture_index(
    *,
    captures_glob: str,
    cookie_domain_contains: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    exact_index: dict[str, dict[str, Any]] = {}
    path_index: dict[str, dict[str, Any]] = {}

    for raw in sorted(glob.glob(captures_glob)):
        p = Path(raw)
        if not p.is_file() or not p.name.endswith(".meta.json"):
            continue
        try:
            row = _capture_row(p, cookie_domain_contains=cookie_domain_contains)
            rows.append(row)
            ek = str(row.get("final_url_exact_key") or "")
            pk = str(row.get("final_url_path_key") or "")
            if ek:
                exact_index[ek] = _pick_newer(exact_index.get(ek), row)
            if pk:
                path_index[pk] = _pick_newer(path_index.get(pk), row)
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "meta_file": _display(p),
                    "error": f"{type(exc).__name__}: {exc}",
                    "usable_capture": False,
                    "access_denied_detected": False,
                    "cookies_total": 0,
                    "cookies_domain_total": 0,
                    "ended_at": "",
                    "ended_at_epoch": 0.0,
                }
            )

    return rows, exact_index, path_index


def _load_targets(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not isinstance(row, dict):
                continue
            capture_url = str(row.get("capture_url") or "").strip()
            if not capture_url:
                continue
            rows.append(
                {
                    "target_rank": _to_int(row.get("target_rank"), 0),
                    "target_id": str(row.get("target_id") or ""),
                    "target_kind": str(row.get("target_kind") or ""),
                    "cohort": str(row.get("cohort") or ""),
                    "initiative_id": str(row.get("initiative_id") or ""),
                    "capture_url": capture_url,
                    "reason": str(row.get("reason") or ""),
                    "suggested_label": str(row.get("suggested_label") or ""),
                    "suggested_command": str(row.get("suggested_command") or ""),
                }
            )
    rows.sort(key=lambda r: (int(r.get("target_rank") or 0), str(r.get("target_id") or "")))
    return rows


def build_report(
    *,
    targets_csv: Path,
    captures_glob: str,
    cookie_domain_contains: str,
    strict_min_covered_targets: int,
    strict_min_usable_targets: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not targets_csv.exists():
        return (
            {
                "generated_at": _now_iso(),
                "status": "failed",
                "error": "targets_csv_not_found",
                "targets_csv": _display(targets_csv),
            },
            [],
        )

    targets = _load_targets(targets_csv)
    captures, exact_index, path_index = _load_capture_index(
        captures_glob=captures_glob,
        cookie_domain_contains=cookie_domain_contains,
    )

    rows: list[dict[str, Any]] = []
    for target in targets:
        capture_url = str(target.get("capture_url") or "")
        ekey = _normalize_url_exact(capture_url)
        pkey = _normalize_url_path(capture_url)

        matched = exact_index.get(ekey)
        strategy = "exact"
        if matched is None and pkey:
            matched = path_index.get(pkey)
            if matched is not None:
                strategy = "path"

        out = dict(target)
        out["matched"] = bool(matched is not None)
        out["match_strategy"] = strategy if matched is not None else "none"
        if matched is None:
            out.update(
                {
                    "matched_meta_file": "",
                    "matched_final_url": "",
                    "matched_ended_at": "",
                    "matched_access_denied": 0,
                    "matched_cookies_domain_total": 0,
                    "matched_usable_capture": 0,
                }
            )
        else:
            out.update(
                {
                    "matched_meta_file": str(matched.get("meta_file") or ""),
                    "matched_final_url": str(matched.get("final_url") or ""),
                    "matched_ended_at": str(matched.get("ended_at") or ""),
                    "matched_access_denied": 1 if bool(matched.get("access_denied_detected")) else 0,
                    "matched_cookies_domain_total": _to_int(matched.get("cookies_domain_total"), 0),
                    "matched_usable_capture": 1 if bool(matched.get("usable_capture")) else 0,
                }
            )
        rows.append(out)

    targets_total = len(rows)
    matched_targets_total = sum(1 for r in rows if bool(r.get("matched")))
    usable_targets_total = sum(1 for r in rows if _to_int(r.get("matched_usable_capture"), 0) > 0)
    access_denied_matched_total = sum(1 for r in rows if _to_int(r.get("matched_access_denied"), 0) > 0)

    checks = {
        "has_targets": targets_total > 0,
        "covered_targets_min_met": matched_targets_total >= max(0, int(strict_min_covered_targets)),
        "usable_targets_min_met": usable_targets_total >= max(0, int(strict_min_usable_targets)),
    }
    reasons: list[str] = []
    if not checks["has_targets"]:
        reasons.append("no_targets")
    if not checks["covered_targets_min_met"]:
        reasons.append("covered_targets_below_min")
    if not checks["usable_targets_min_met"]:
        reasons.append("usable_targets_below_min")

    status = "ok" if all(checks.values()) else "degraded"

    report = {
        "generated_at": _now_iso(),
        "status": status,
        "targets_csv": _display(targets_csv),
        "captures_glob": captures_glob,
        "cookie_domain_contains": cookie_domain_contains,
        "thresholds": {
            "strict_min_covered_targets": max(0, int(strict_min_covered_targets)),
            "strict_min_usable_targets": max(0, int(strict_min_usable_targets)),
        },
        "totals": {
            "targets_total": targets_total,
            "matched_targets_total": matched_targets_total,
            "unmatched_targets_total": max(0, targets_total - matched_targets_total),
            "usable_targets_total": usable_targets_total,
            "access_denied_matched_targets_total": access_denied_matched_total,
            "matched_with_domain_cookies_total": sum(
                1 for r in rows if _to_int(r.get("matched_cookies_domain_total"), 0) > 0
            ),
            "capture_files_total": len(captures),
            "coverage_pct": round((matched_targets_total / targets_total), 6) if targets_total > 0 else 0.0,
            "usable_coverage_pct": round((usable_targets_total / targets_total), 6) if targets_total > 0 else 0.0,
        },
        "checks": checks,
        "strict_fail_reasons": reasons,
        "sample_unmatched_targets": [
            {
                "target_rank": r.get("target_rank"),
                "target_id": r.get("target_id"),
                "cohort": r.get("cohort"),
                "capture_url": r.get("capture_url"),
            }
            for r in rows
            if not bool(r.get("matched"))
        ][:20],
    }
    return report, rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_rank",
        "target_id",
        "target_kind",
        "cohort",
        "initiative_id",
        "capture_url",
        "reason",
        "suggested_label",
        "matched",
        "match_strategy",
        "matched_meta_file",
        "matched_final_url",
        "matched_ended_at",
        "matched_access_denied",
        "matched_cookies_domain_total",
        "matched_usable_capture",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV))
    p.add_argument(
        "--captures-glob",
        default="etl/data/raw/manual/senado*_cookie_refresh_*.meta.json",
        help="Glob pattern for manual capture meta files",
    )
    p.add_argument("--cookie-domain-contains", default="senado.es")
    p.add_argument("--strict-min-covered-targets", type=int, default=1)
    p.add_argument("--strict-min-usable-targets", type=int, default=1)
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--csv-out", default=str(DEFAULT_CSV_OUT))
    p.add_argument("--strict", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = Path(str(args.out))
    csv_out_path = Path(str(args.csv_out))

    report, rows = build_report(
        targets_csv=Path(str(args.targets_csv)),
        captures_glob=str(args.captures_glob),
        cookie_domain_contains=str(args.cookie_domain_contains),
        strict_min_covered_targets=max(0, int(args.strict_min_covered_targets or 0)),
        strict_min_usable_targets=max(0, int(args.strict_min_usable_targets or 0)),
    )

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")
    _write_csv(csv_out_path, rows)

    if str(report.get("status") or "") == "failed":
        return 3
    if bool(args.strict) and str(report.get("status") or "") != "ok":
        return STRICT_FAIL_EXIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
