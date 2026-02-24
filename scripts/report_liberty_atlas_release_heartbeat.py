#!/usr/bin/env python3
"""Append-only heartbeat for liberty atlas release freshness and drift checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_PUBLISHED_RELEASE_JSON = Path("etl/data/published/liberty-restrictions-atlas-release-latest.json")
DEFAULT_GH_PAGES_RELEASE_JSON = Path("docs/gh-pages/explorer-sources/data/liberty-atlas-release.json")
DEFAULT_CONTINUITY_JSON = Path("docs/etl/sprints/AI-OPS-125/evidence/liberty_atlas_changelog_continuity_latest.json")
DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/liberty_atlas_release_heartbeat.jsonl")
DEFAULT_ENV_FILE = Path(".env")
DEFAULT_HF_TIMEOUT = 20.0
DEFAULT_MAX_SNAPSHOT_AGE_DAYS = 14


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


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        token = _safe_text(item)
        if token:
            out.append(token)
    return out


def _dedupe_ordered(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = _safe_text(value)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return float(default)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json_file(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, f"missing_file:{path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {}, f"invalid_json:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return {}, "invalid_json_root"
    return payload, ""


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def _fetch_json_url(url: str, timeout: float) -> tuple[dict[str, Any], str]:
    req = Request(
        url,
        headers={
            "User-Agent": "vota-con-la-chola/liberty-atlas-release-heartbeat",
            "Accept": "application/json,text/plain,*/*",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urlopen(req, timeout=float(timeout)) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return {}, f"http_error:{exc.code}"
    except URLError as exc:
        return {}, f"url_error:{exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return {}, f"network_error:{type(exc).__name__}"

    try:
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        return {}, f"invalid_remote_json:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return {}, "invalid_remote_json_root"
    return payload, ""


def _parse_date(value: str) -> date | None:
    token = _safe_text(value)
    if not token:
        return None
    try:
        return date.fromisoformat(token)
    except ValueError:
        return None


def _snapshot_age_days(snapshot_date: str) -> int | None:
    d = _parse_date(snapshot_date)
    if d is None:
        return None
    return int((datetime.now(timezone.utc).date() - d).days)


def _canonical_release(payload: dict[str, Any]) -> dict[str, Any]:
    obj = _safe_obj(payload)
    diff = _safe_obj(obj.get("diff"))
    changelog = _safe_obj(obj.get("changelog"))
    return {
        "status": _safe_text(obj.get("status")),
        "snapshot_date": _safe_text(obj.get("snapshot_date")),
        "schema_version": _safe_text(obj.get("schema_version")),
        "snapshot_restrictions_total": _to_int(obj.get("snapshot_restrictions_total"), 0),
        "diff": {
            "status": _safe_text(diff.get("status")),
            "changed_sections_total": _to_int(diff.get("changed_sections_total"), 0),
            "items_added_total": _to_int(diff.get("items_added_total"), 0),
            "items_removed_total": _to_int(diff.get("items_removed_total"), 0),
            "totals_changed": sorted(_safe_list_str(diff.get("totals_changed"))),
        },
        "changelog": {
            "entry_id": _safe_text(changelog.get("entry_id")),
            "history_latest_entry_id": _safe_text(changelog.get("history_latest_entry_id")),
            "history_latest_snapshot_date": _safe_text(changelog.get("history_latest_snapshot_date")),
            "history_entries_total": _to_int(changelog.get("history_entries_total"), 0),
        },
    }


def _release_view(payload: dict[str, Any], source: str) -> dict[str, Any]:
    canonical = _canonical_release(payload)
    snapshot_date = _safe_text(canonical.get("snapshot_date"))
    age_days = _snapshot_age_days(snapshot_date)
    return {
        "source": source,
        "status": _safe_text(canonical.get("status")),
        "snapshot_date": snapshot_date,
        "entry_id": _safe_text(_safe_obj(canonical.get("changelog")).get("entry_id")),
        "history_latest_entry_id": _safe_text(_safe_obj(canonical.get("changelog")).get("history_latest_entry_id")),
        "schema_version": _safe_text(canonical.get("schema_version")),
        "snapshot_restrictions_total": _to_int(canonical.get("snapshot_restrictions_total"), 0),
        "snapshot_age_days": age_days,
        "fingerprint": _sha256_text(json.dumps(canonical, ensure_ascii=True, sort_keys=True)),
    }


def _resolve_hf_repo(repo_cli: str, username_cli: str, dotenv_values: dict[str, str]) -> str:
    repo = (
        _safe_text(repo_cli)
        or _safe_text(os.environ.get("HF_DATASET_REPO_ID"))
        or _safe_text(dotenv_values.get("HF_DATASET_REPO_ID"))
    )
    user = (
        _safe_text(username_cli)
        or _safe_text(os.environ.get("HF_USERNAME"))
        or _safe_text(dotenv_values.get("HF_USERNAME"))
    )
    if not repo:
        return ""
    if "/" in repo:
        return repo
    if not user:
        return ""
    return f"{user}/{repo}"


def _build_hf_url(repo: str) -> str:
    return f"https://huggingface.co/datasets/{repo}/resolve/main/published/liberty-restrictions-atlas-release-latest.json"


def _build_hf_latest_url(repo: str) -> str:
    return f"https://huggingface.co/datasets/{repo}/resolve/main/latest.json"


def _build_hf_snapshot_release_url(repo: str, snapshot_date: str) -> str:
    return (
        f"https://huggingface.co/datasets/{repo}/resolve/main/"
        f"snapshots/{snapshot_date}/published/liberty-restrictions-atlas-release-latest.json"
    )


def _build_hf_snapshot_release_dated_url(repo: str, snapshot_date: str) -> str:
    return (
        f"https://huggingface.co/datasets/{repo}/resolve/main/"
        f"snapshots/{snapshot_date}/published/liberty-restrictions-atlas-release-{snapshot_date}.json"
    )


def _build_hf_release_dated_url(repo: str, snapshot_date: str) -> str:
    return f"https://huggingface.co/datasets/{repo}/resolve/main/published/liberty-restrictions-atlas-release-{snapshot_date}.json"


def _fetch_hf_release(repo: str, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch HF release-latest JSON with dataset-layout-aware fallback.

    Returns:
      payload: release JSON (empty when unavailable)
      meta: diagnostics (urls/errors/snapshot_date)
    """

    meta: dict[str, Any] = {
        "latest_url": "",
        "latest_snapshot_date": "",
        "release_url": "",
        "release_error": "",
        "latest_error": "",
    }
    if not _safe_text(repo):
        meta["release_error"] = "hf_repo_unresolved"
        return {}, meta

    latest_url = _build_hf_latest_url(repo)
    meta["latest_url"] = latest_url
    latest_payload, latest_error = _fetch_json_url(latest_url, timeout=timeout)
    if latest_error:
        meta["latest_error"] = latest_error
        meta["release_error"] = f"latest_error:{latest_error}"
        return {}, meta

    latest_snapshot_date = _safe_text(latest_payload.get("snapshot_date"))
    meta["latest_snapshot_date"] = latest_snapshot_date

    if latest_snapshot_date:
        snap_release_url = _build_hf_snapshot_release_url(repo, latest_snapshot_date)
        release_payload, release_error = _fetch_json_url(snap_release_url, timeout=timeout)
        if not release_error:
            meta["release_url"] = snap_release_url
            return release_payload, meta
        meta["release_error"] = f"snapshot_release_error:{release_error}"

        snap_release_dated_url = _build_hf_snapshot_release_dated_url(repo, latest_snapshot_date)
        release_payload, release_error = _fetch_json_url(snap_release_dated_url, timeout=timeout)
        if not release_error:
            meta["release_url"] = snap_release_dated_url
            meta["release_error"] = ""
            return release_payload, meta
        meta["release_error"] = f"{_safe_text(meta.get('release_error'))};snapshot_release_dated_error:{release_error}"

    fallback_url = _build_hf_url(repo)
    release_payload, release_error = _fetch_json_url(fallback_url, timeout=timeout)
    if not release_error:
        meta["release_url"] = fallback_url
        meta["release_error"] = ""
        return release_payload, meta

    fallback_dated_url = _build_hf_release_dated_url(repo, latest_snapshot_date) if latest_snapshot_date else ""
    if fallback_dated_url:
        dated_payload, dated_error = _fetch_json_url(fallback_dated_url, timeout=timeout)
        if not dated_error:
            meta["release_url"] = fallback_dated_url
            meta["release_error"] = ""
            return dated_payload, meta
        fallback_error = f"fallback_error:{release_error};fallback_dated_error:{dated_error}"
    else:
        fallback_error = f"fallback_error:{release_error}"

    if _safe_text(meta.get("release_error")):
        meta["release_error"] = f"{_safe_text(meta.get('release_error'))};{fallback_error}"
    else:
        meta["release_error"] = fallback_error
    meta["release_url"] = fallback_url or fallback_dated_url
    return {}, meta


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append heartbeat for liberty atlas release freshness/drift")
    p.add_argument("--published-release-json", default=str(DEFAULT_PUBLISHED_RELEASE_JSON))
    p.add_argument("--gh-pages-release-json", default=str(DEFAULT_GH_PAGES_RELEASE_JSON))
    p.add_argument("--continuity-json", default=str(DEFAULT_CONTINUITY_JSON))
    p.add_argument("--heartbeat-jsonl", default=str(DEFAULT_HEARTBEAT_JSONL))
    p.add_argument("--snapshot-date", default="", help="Expected snapshot date (YYYY-MM-DD)")
    p.add_argument("--max-snapshot-age-days", type=int, default=DEFAULT_MAX_SNAPSHOT_AGE_DAYS)
    p.add_argument("--hf-release-json", default="", help="Optional local HF release JSON")
    p.add_argument("--hf-release-json-url", default="", help="Optional HF release URL")
    p.add_argument("--hf-dataset-repo", default="", help="Optional HF dataset repo (owner/name or name)")
    p.add_argument("--hf-username", default="", help="HF username to resolve repo without owner")
    p.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Optional .env file for HF fallback settings")
    p.add_argument("--hf-timeout", type=float, default=DEFAULT_HF_TIMEOUT)
    p.add_argument("--allow-hf-unavailable", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--out", default="")
    return p.parse_args(argv)


def validate_heartbeat(heartbeat: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not _safe_text(heartbeat.get("run_at")):
        reasons.append("missing_run_at")
    if not _safe_text(heartbeat.get("heartbeat_id")):
        reasons.append("missing_heartbeat_id")
    status = _safe_text(heartbeat.get("status")).lower()
    if status not in {"ok", "degraded", "failed"}:
        reasons.append("invalid_status")

    strict_fail_reasons = _safe_list_str(heartbeat.get("strict_fail_reasons"))
    if _to_int(heartbeat.get("strict_fail_count"), -1) != len(strict_fail_reasons):
        reasons.append("strict_fail_count_mismatch")

    warnings = _safe_list_str(heartbeat.get("warnings"))
    if _to_int(heartbeat.get("warning_count"), -1) != len(warnings):
        reasons.append("warning_count_mismatch")

    if _to_int(heartbeat.get("stale_alerts_count"), -1) < 0:
        reasons.append("invalid_stale_alerts_count")
    if _to_int(heartbeat.get("drift_alerts_count"), -1) < 0:
        reasons.append("invalid_drift_alerts_count")

    return _dedupe_ordered(reasons)


def read_history_entries(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    raw = history_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if _safe_text(line)]
    for idx, line in enumerate(lines, start=1):
        try:
            entry = json.loads(line)
            rows.append({"line_no": idx, "malformed_line": False, "entry": _safe_obj(entry)})
        except Exception:  # noqa: BLE001
            rows.append({"line_no": idx, "malformed_line": True, "entry": {}})
    return rows


def history_has_heartbeat(rows: list[dict[str, Any]], heartbeat_id: str) -> bool:
    needle = _safe_text(heartbeat_id)
    if not needle:
        return False
    for row in rows:
        if bool(row.get("malformed_line")):
            continue
        entry = _safe_obj(row.get("entry"))
        if _safe_text(entry.get("heartbeat_id")) == needle:
            return True
    return False


def append_heartbeat(history_path: Path, heartbeat: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(heartbeat, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_heartbeat(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[str]]:
    max_snapshot_age_days = int(args.max_snapshot_age_days)
    if max_snapshot_age_days < 0:
        raise ValueError("--max-snapshot-age-days must be >= 0")
    hf_timeout = float(args.hf_timeout)
    if hf_timeout <= 0:
        raise ValueError("--hf-timeout must be > 0")
    dotenv_values = load_dotenv(Path(str(args.env_file)))

    published_payload, published_error = _load_json_file(Path(str(args.published_release_json)))
    gh_payload, gh_error = _load_json_file(Path(str(args.gh_pages_release_json)))
    continuity_payload, continuity_error = _load_json_file(Path(str(args.continuity_json)))

    strict_fail_reasons: list[str] = []
    warnings: list[str] = []

    if published_error:
        strict_fail_reasons.append(f"published_release_error:{published_error}")
    if gh_error:
        strict_fail_reasons.append(f"gh_pages_release_error:{gh_error}")
    if continuity_error:
        strict_fail_reasons.append(f"continuity_error:{continuity_error}")

    published_view = _release_view(published_payload, source="published") if not published_error else {}
    gh_view = _release_view(gh_payload, source="gh_pages") if not gh_error else {}

    continuity_status = _safe_text(continuity_payload.get("status"))
    continuity_snapshot_date = _safe_text(continuity_payload.get("latest_snapshot_date"))
    continuity_entry_id = _safe_text(continuity_payload.get("latest_entry_id"))
    continuity_chain_ok = bool(_safe_obj(continuity_payload.get("checks")).get("previous_snapshot_chain_ok"))

    if not continuity_error and continuity_status != "ok":
        strict_fail_reasons.append("continuity_status_not_ok")
    if not continuity_error and not continuity_chain_ok:
        strict_fail_reasons.append("continuity_previous_snapshot_chain_not_ok")

    expected_snapshot_date = _safe_text(args.snapshot_date) or _safe_text(published_view.get("snapshot_date"))

    def _release_ok(view: dict[str, Any]) -> bool:
        return _safe_text(view.get("status")) == "ok"

    if published_view and not _release_ok(published_view):
        strict_fail_reasons.append("published_release_status_not_ok")
    if gh_view and not _release_ok(gh_view):
        strict_fail_reasons.append("gh_pages_release_status_not_ok")

    published_gh_parity_ok = False
    if published_view and gh_view:
        published_gh_parity_ok = _safe_text(published_view.get("fingerprint")) == _safe_text(gh_view.get("fingerprint"))
        if not published_gh_parity_ok:
            strict_fail_reasons.append("published_gh_pages_drift_detected")

    hf_payload: dict[str, Any] = {}
    hf_source = ""
    hf_fetch_error = ""
    hf_repo = ""
    hf_url = ""
    hf_latest_url = ""
    hf_latest_snapshot_date = ""

    hf_json_path = _safe_text(args.hf_release_json)
    hf_release_url = _safe_text(args.hf_release_json_url)
    if hf_json_path:
        hf_source = f"file:{hf_json_path}"
        hf_payload, hf_fetch_error = _load_json_file(Path(hf_json_path))
    elif hf_release_url:
        hf_source = hf_release_url
        hf_payload, hf_fetch_error = _fetch_json_url(hf_release_url, timeout=hf_timeout)
    else:
        hf_repo = _resolve_hf_repo(str(args.hf_dataset_repo), str(args.hf_username), dotenv_values)
        if not hf_repo:
            hf_fetch_error = "hf_repo_unresolved"
        else:
            hf_payload, hf_meta = _fetch_hf_release(hf_repo, timeout=hf_timeout)
            hf_url = _safe_text(hf_meta.get("release_url"))
            hf_latest_url = _safe_text(hf_meta.get("latest_url"))
            hf_latest_snapshot_date = _safe_text(hf_meta.get("latest_snapshot_date"))
            hf_fetch_error = _safe_text(hf_meta.get("release_error"))
            hf_source = hf_url or hf_latest_url

    hf_available = not bool(hf_fetch_error)
    hf_view = _release_view(hf_payload, source="hf") if hf_available else {}

    if not hf_available:
        if bool(args.allow_hf_unavailable):
            warnings.append(f"hf_unavailable:{hf_fetch_error}")
        else:
            strict_fail_reasons.append(f"hf_unavailable:{hf_fetch_error}")

    if hf_view and not _release_ok(hf_view):
        strict_fail_reasons.append("hf_release_status_not_ok")

    published_hf_parity_ok: bool | None = None
    gh_hf_parity_ok: bool | None = None
    if published_view and hf_view:
        published_hf_parity_ok = _safe_text(published_view.get("fingerprint")) == _safe_text(hf_view.get("fingerprint"))
        if not published_hf_parity_ok:
            strict_fail_reasons.append("published_hf_drift_detected")
    if gh_view and hf_view:
        gh_hf_parity_ok = _safe_text(gh_view.get("fingerprint")) == _safe_text(hf_view.get("fingerprint"))
        if not gh_hf_parity_ok:
            strict_fail_reasons.append("gh_pages_hf_drift_detected")

    snapshot_surface_dates: dict[str, str] = {
        "published": _safe_text(published_view.get("snapshot_date")),
        "gh_pages": _safe_text(gh_view.get("snapshot_date")),
        "continuity": continuity_snapshot_date,
    }
    if hf_view:
        snapshot_surface_dates["hf"] = _safe_text(hf_view.get("snapshot_date"))

    expected_snapshot_match_ok = True
    if expected_snapshot_date:
        for surface, value in snapshot_surface_dates.items():
            if value and value != expected_snapshot_date:
                expected_snapshot_match_ok = False
                strict_fail_reasons.append(f"snapshot_date_mismatch:{surface}")

    stale_surfaces: list[str] = []
    for surface, view in (("published", published_view), ("gh_pages", gh_view), ("hf", hf_view)):
        if not view:
            continue
        age_days = view.get("snapshot_age_days")
        age_n = _to_int(age_days, -1)
        if age_n >= 0 and age_n > max_snapshot_age_days:
            stale_surfaces.append(surface)
            strict_fail_reasons.append(f"stale_snapshot:{surface}")

    continuity_entry_matches = True
    if continuity_entry_id and published_view:
        continuity_entry_matches = continuity_entry_id == _safe_text(published_view.get("entry_id"))
        if not continuity_entry_matches:
            strict_fail_reasons.append("continuity_entry_id_mismatch_published")

    strict_fail_reasons = _dedupe_ordered(strict_fail_reasons)
    warnings = _dedupe_ordered(warnings)

    drift_alerts_count = 0
    if not published_gh_parity_ok:
        drift_alerts_count += 1
    if published_hf_parity_ok is False:
        drift_alerts_count += 1
    if gh_hf_parity_ok is False:
        drift_alerts_count += 1

    run_at = now_utc_iso()
    heartbeat_id = "|".join(
        [
            run_at,
            expected_snapshot_date,
            _safe_text(published_view.get("fingerprint")),
            _safe_text(gh_view.get("fingerprint")),
            _safe_text(hf_view.get("fingerprint")),
            str(len(strict_fail_reasons)),
        ]
    )

    checks = {
        "published_release_ok": bool(published_view) and _release_ok(published_view),
        "gh_pages_release_ok": bool(gh_view) and _release_ok(gh_view),
        "continuity_ok": (not continuity_error) and continuity_status == "ok" and continuity_chain_ok,
        "published_gh_parity_ok": bool(published_gh_parity_ok),
        "hf_available": bool(hf_available),
        "hf_release_ok_or_allowed": (not hf_available and bool(args.allow_hf_unavailable))
        or (bool(hf_view) and _release_ok(hf_view)),
        "published_hf_parity_ok": published_hf_parity_ok,
        "gh_pages_hf_parity_ok": gh_hf_parity_ok,
        "expected_snapshot_match_ok": bool(expected_snapshot_match_ok),
        "stale_snapshot_ok": len(stale_surfaces) == 0,
        "continuity_entry_matches_published_ok": bool(continuity_entry_matches),
    }

    if strict_fail_reasons:
        status = "failed"
    elif warnings:
        status = "degraded"
    else:
        status = "ok"

    heartbeat = {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "status": status,
        "snapshot_date_expected": expected_snapshot_date,
        "max_snapshot_age_days": max_snapshot_age_days,
        "allow_hf_unavailable": bool(args.allow_hf_unavailable),
        "published": published_view,
        "gh_pages": gh_view,
        "hf": {
            "source": hf_source,
            "dataset_repo": hf_repo,
            "latest_url": hf_latest_url,
            "latest_snapshot_date": hf_latest_snapshot_date,
            "url": hf_url,
            "available": bool(hf_available),
            "fetch_error": hf_fetch_error,
            "release": hf_view,
        },
        "continuity": {
            "path": str(args.continuity_json),
            "status": continuity_status,
            "latest_snapshot_date": continuity_snapshot_date,
            "latest_entry_id": continuity_entry_id,
            "previous_snapshot_chain_ok": continuity_chain_ok,
            "strict_fail_reasons": _safe_list_str(continuity_payload.get("strict_fail_reasons")),
        },
        "checks": checks,
        "stale_surfaces": stale_surfaces,
        "stale_alerts_count": len(stale_surfaces),
        "drift_alerts_count": drift_alerts_count,
        "hf_unavailable": not hf_available,
        "warning_count": len(warnings),
        "warnings": warnings,
        "strict_fail_count": len(strict_fail_reasons),
        "strict_fail_reasons": strict_fail_reasons,
    }
    return heartbeat, strict_fail_reasons, warnings


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input": {
            "published_release_json": str(args.published_release_json),
            "gh_pages_release_json": str(args.gh_pages_release_json),
            "continuity_json": str(args.continuity_json),
            "heartbeat_jsonl": str(args.heartbeat_jsonl),
        },
        "history_size_before": 0,
        "history_size_after": 0,
        "history_malformed_lines_before": 0,
        "appended": False,
        "duplicate_detected": False,
        "validation_errors": [],
        "strict_fail_reasons": [],
        "warnings": [],
        "heartbeat": {},
        "status": "failed",
    }

    heartbeat_path = Path(str(args.heartbeat_jsonl))

    try:
        heartbeat, strict_fail_reasons, warnings = _build_heartbeat(args)
        report["heartbeat"] = heartbeat
        report["strict_fail_reasons"] = strict_fail_reasons
        report["warnings"] = warnings
        report["validation_errors"] = validate_heartbeat(heartbeat)

        history_before = read_history_entries(heartbeat_path)
        report["history_size_before"] = len(history_before)
        report["history_malformed_lines_before"] = sum(1 for row in history_before if bool(row.get("malformed_line")))

        if not report["validation_errors"]:
            report["duplicate_detected"] = history_has_heartbeat(history_before, _safe_text(heartbeat.get("heartbeat_id")))
            if not report["duplicate_detected"]:
                append_heartbeat(heartbeat_path, heartbeat)
                report["appended"] = True

        report["history_size_after"] = int(report["history_size_before"]) + (1 if report["appended"] else 0)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001
        report["status"] = "failed"
        report["strict_fail_reasons"] = [f"runtime_error:{type(exc).__name__}"]
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        print(payload)
        out_token = _safe_text(args.out)
        if out_token:
            _write_json(Path(out_token), report)
        return 3

    heartbeat_status = _safe_text(_safe_obj(report.get("heartbeat")).get("status")).lower()
    strict_fail_reasons = _safe_list_str(report.get("strict_fail_reasons"))
    validation_errors = _safe_list_str(report.get("validation_errors"))

    if validation_errors:
        report["status"] = "failed"
        strict_fail_reasons = _dedupe_ordered(strict_fail_reasons + [f"validation:{x}" for x in validation_errors])
        report["strict_fail_reasons"] = strict_fail_reasons
    elif heartbeat_status == "failed":
        report["status"] = "failed"
    elif heartbeat_status == "degraded":
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_token = _safe_text(args.out)
    if out_token:
        _write_json(Path(out_token), report)

    if bool(args.strict) and _safe_list_str(report.get("strict_fail_reasons")):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
