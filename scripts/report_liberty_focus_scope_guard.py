#!/usr/bin/env python3
"""Scope guard for liberty focus policy under degraded focus gate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATUS_JSON = Path("docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_status_latest.json")
DEFAULT_CHANGED_PATHS_FILE = Path("docs/etl/runs/liberty_focus_changed_paths.txt")

DEFAULT_ALWAYS_ALLOWED_PATHS = (
    ".github/workflows/etl-tracker-gate.yml",
    "docs/etl/e2e-scrape-load-tracker.md",
    "docs/etl/name-and-shame-access-blockers.md",
    "docs/roadmap-tecnico.md",
    "justfile",
)

DEFAULT_RIGHTS_PREFIXES = (
    "etl/data/seeds/liberty_",
    "scripts/export_liberty_",
    "scripts/import_liberty_",
    "scripts/publish_liberty_",
    "scripts/report_liberty_",
    "scripts/validate_liberty_",
    "tests/test_export_liberty_",
    "tests/test_import_liberty_",
    "tests/test_publish_liberty_",
    "tests/test_report_liberty_",
    "tests/test_validate_liberty_",
)

DEFAULT_RIGHTS_TOKENS = (
    "liberty",
    "restriction",
    "restrictions",
    "irlc",
    "atlas",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _normalize_path(path: str) -> str:
    token = _safe_text(path).replace("\\", "/")
    while token.startswith("./"):
        token = token[2:]
    return token


def _dedupe_paths(paths: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        token = _normalize_path(raw)
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _read_changed_paths(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    rows: list[str] = []
    for line in raw.splitlines():
        token = _safe_text(line)
        if not token:
            continue
        if token.startswith("#"):
            continue
        rows.append(token)
    return rows


def _is_rights_related_path(
    path: str,
    *,
    always_allowed_paths: tuple[str, ...],
    rights_prefixes: tuple[str, ...],
    rights_tokens: tuple[str, ...],
) -> tuple[bool, str]:
    normalized = _normalize_path(path)
    lower = normalized.lower()

    for item in always_allowed_paths:
        if lower == _normalize_path(item).lower():
            return True, "always_allowed"

    for prefix in rights_prefixes:
        token = _normalize_path(prefix).lower()
        if token and lower.startswith(token):
            return True, "rights_prefix"

    for token in rights_tokens:
        if _safe_text(token).lower() and _safe_text(token).lower() in lower:
            return True, "rights_token"

    return False, "outside_rights_scope"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Guard non-Derechos scope changes while liberty focus gate is degraded")
    p.add_argument("--status-json", default=str(DEFAULT_STATUS_JSON))
    p.add_argument("--changed-paths-file", default=str(DEFAULT_CHANGED_PATHS_FILE))
    p.add_argument("--changed-path", action="append", default=[])
    p.add_argument("--allow-path", action="append", default=[])
    p.add_argument("--allow-prefix", action="append", default=[])
    p.add_argument("--strict", action="store_true")
    p.add_argument("--out", default="")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    status_json = Path(str(args.status_json))
    changed_paths_file = Path(str(args.changed_paths_file))

    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input": {
            "status_json": str(status_json),
            "changed_paths_file": str(changed_paths_file),
        },
        "status_doc_status": "",
        "focus_gate_passed": None,
        "focus_gate_state": "unknown",
        "changed_paths_total": 0,
        "allowed_paths_total": 0,
        "non_rights_paths_total": 0,
        "changed_paths": [],
        "allowed_paths": [],
        "non_rights_paths": [],
        "checks": {
            "status_json_exists_ok": False,
            "status_json_valid_ok": False,
            "changed_paths_file_exists_ok": False,
            "focus_gate_known_ok": False,
            "degraded_scope_ok": False,
        },
        "strict_fail_reasons": [],
        "status": "failed",
    }

    if not status_json.exists():
        print(json.dumps({"error": f"status json not found: {status_json}"}, ensure_ascii=False))
        return 2
    report["checks"]["status_json_exists_ok"] = True

    if not changed_paths_file.exists():
        print(json.dumps({"error": f"changed paths file not found: {changed_paths_file}"}, ensure_ascii=False))
        return 2
    report["checks"]["changed_paths_file_exists_ok"] = True

    try:
        status_doc = json.loads(status_json.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid status json: {exc}"}, ensure_ascii=False))
        return 3

    if not isinstance(status_doc, dict):
        print(json.dumps({"error": "invalid status json: root must be object"}, ensure_ascii=False))
        return 3
    report["checks"]["status_json_valid_ok"] = True

    status_token = _safe_text(status_doc.get("status")).lower()
    focus_gate_passed = _to_bool_or_none(_safe_obj(status_doc.get("focus_gate")).get("passed"))

    report["status_doc_status"] = status_token
    report["focus_gate_passed"] = focus_gate_passed
    report["checks"]["focus_gate_known_ok"] = focus_gate_passed is not None

    if focus_gate_passed is False or status_token in {"degraded", "failed"}:
        focus_gate_state = "degraded"
    elif focus_gate_passed is True and status_token in {"ok", ""}:
        focus_gate_state = "ok"
    else:
        focus_gate_state = "unknown"
    report["focus_gate_state"] = focus_gate_state

    changed_paths = _dedupe_paths(_read_changed_paths(changed_paths_file) + list(args.changed_path or []))
    report["changed_paths"] = changed_paths
    report["changed_paths_total"] = len(changed_paths)

    always_allowed_paths = tuple(_dedupe_paths(list(DEFAULT_ALWAYS_ALLOWED_PATHS) + list(args.allow_path or [])))
    rights_prefixes = tuple(_dedupe_paths(list(DEFAULT_RIGHTS_PREFIXES) + list(args.allow_prefix or [])))

    allowed_paths: list[dict[str, str]] = []
    non_rights_paths: list[dict[str, str]] = []
    for changed in changed_paths:
        allowed, reason = _is_rights_related_path(
            changed,
            always_allowed_paths=always_allowed_paths,
            rights_prefixes=rights_prefixes,
            rights_tokens=DEFAULT_RIGHTS_TOKENS,
        )
        row = {"path": changed, "reason": reason}
        if allowed:
            allowed_paths.append(row)
        else:
            non_rights_paths.append(row)

    report["allowed_paths"] = allowed_paths
    report["allowed_paths_total"] = len(allowed_paths)
    report["non_rights_paths"] = non_rights_paths
    report["non_rights_paths_total"] = len(non_rights_paths)

    degraded_scope_ok = not (focus_gate_state == "degraded" and len(non_rights_paths) > 0)
    report["checks"]["degraded_scope_ok"] = degraded_scope_ok

    strict_fail_reasons: list[str] = []
    if not report["checks"]["status_json_valid_ok"]:
        strict_fail_reasons.append("status_json_invalid")
    if not report["checks"]["focus_gate_known_ok"]:
        strict_fail_reasons.append("focus_gate_unknown")
    if not report["checks"]["degraded_scope_ok"]:
        strict_fail_reasons.append("non_rights_changes_under_degraded_focus")

    report["strict_fail_reasons"] = strict_fail_reasons

    if strict_fail_reasons:
        report["status"] = "failed"
    elif focus_gate_state == "degraded":
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if _safe_text(args.out):
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)

    if bool(args.strict) and strict_fail_reasons:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
