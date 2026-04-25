#!/usr/bin/env python3
"""Exporta un feed estatico para /obstruction-tracker/."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


DEFAULT_STATUS_JSON = Path("ui/gh-pages-next/public/explorer-sources/data/status.json")
DEFAULT_BLOCKERS_LOG = Path("docs/etl/name-and-shame-access-blockers.md")
DEFAULT_REPO_BLOB_BASE = "https://github.com/gsusI/vota-con-la-chola/blob/main"


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_markdown_cell(value: Any) -> str:
    text = safe_text(value)
    while text.startswith("`") and text.endswith("`") and len(text) >= 2:
        text = text[1:-1].strip()
    return text


def parse_iso_datetime(value: str) -> datetime | None:
    text = safe_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def derive_freshness_tier(snapshot_generated_at: str, reference_generated_at: str) -> dict[str, Any]:
    snapshot_dt = parse_iso_datetime(snapshot_generated_at)
    generated_dt = parse_iso_datetime(reference_generated_at)
    if not snapshot_dt or not generated_dt:
        return {
            "tier": "unknown",
            "label": "desconocida",
            "should_warn": True,
            "data_age_days": None,
            "detail": "desconocida · faltan fechas consistentes para evaluar la frescura",
        }

    if generated_dt < snapshot_dt:
        return {
            "tier": "future",
            "label": "futura",
            "should_warn": True,
            "data_age_days": (snapshot_dt - generated_dt).days,
            "detail": "futura · inconsistencia temporal detectada; no usar para claims concluyentes hasta corregir el snapshot",
        }

    age_days = (generated_dt - snapshot_dt).days
    if age_days <= 7:
        return {
            "tier": "fresh",
            "label": "reciente",
            "should_warn": False,
            "data_age_days": age_days,
            "detail": "reciente · sin advertencia de antiguedad",
        }
    if age_days <= 30:
        return {
            "tier": "aging",
            "label": "vigente",
            "should_warn": True,
            "data_age_days": age_days,
            "detail": f"vigente · con advertencia de antiguedad ({age_days} dias) por no refresco reciente",
        }
    return {
        "tier": "stale",
        "label": "antigua",
        "should_warn": True,
        "data_age_days": age_days,
        "detail": f"antigua · la evidencia puede haber cambiado de forma material desde el corte ({age_days} dias)",
    }


def split_reference_list(value: Any) -> list[str]:
    text = clean_markdown_cell(value)
    if not text:
        return []
    return [clean_markdown_cell(part) for part in text.split(";") if clean_markdown_cell(part)]


def build_repo_blob_url(repo_blob_base: str, ref: str) -> str:
    raw = clean_markdown_cell(ref)
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    line_anchor = ""
    path = raw
    if ":" in raw and raw.rsplit(":", 1)[1].isdigit():
        path, line = raw.rsplit(":", 1)
        line_anchor = f"#L{line}"
    encoded_path = "/".join(quote(part) for part in path.split("/"))
    return f"{repo_blob_base.rstrip('/')}/{encoded_path}{line_anchor}"


def build_artifact_links(refs: list[str], repo_blob_base: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for ref in refs:
        raw = clean_markdown_cell(ref)
        if not raw or raw in seen:
            continue
        seen.add(raw)
        label = raw
        if ":" in raw and raw.rsplit(":", 1)[1].isdigit():
            path, line = raw.rsplit(":", 1)
            label = f"{Path(path).name}:L{line}"
        elif not raw.startswith("http://") and not raw.startswith("https://"):
            label = Path(raw).name or raw
        items.append(
            {
                "path": raw,
                "label": label,
                "url": build_repo_blob_url(repo_blob_base, raw),
            }
        )
    return items


def parse_name_and_shame_log(path: Path, repo_blob_base: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == "## Incident Log")
    except StopIteration:
        return []

    header: list[str] | None = None
    incidents: list[dict[str, Any]] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if not line.strip().startswith("|"):
            continue
        cells = [clean_markdown_cell(cell) for cell in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(cell.startswith("---") for cell in cells):
            continue
        if len(cells) != len(header):
            continue
        row = {header[index]: cells[index] for index in range(len(header))}
        evidence_refs = split_reference_list(row.get("evidence"))
        tracker_refs = split_reference_list(row.get("tracker_rows_impacted"))
        resolution_refs = split_reference_list(row.get("resolution_evidence"))
        incidents.append(
            {
                "incident_id": clean_markdown_cell(row.get("incident_id")),
                "first_seen_utc": clean_markdown_cell(row.get("first_seen_utc")),
                "last_seen_utc": clean_markdown_cell(row.get("last_seen_utc")),
                "organism": clean_markdown_cell(row.get("organism")),
                "source_id": clean_markdown_cell(row.get("source_id")),
                "endpoint_or_page": clean_markdown_cell(row.get("endpoint_or_page")),
                "failure_mode": clean_markdown_cell(row.get("failure_mode")),
                "status": clean_markdown_cell(row.get("status")),
                "next_escalation": clean_markdown_cell(row.get("next_escalation")),
                "evidence": build_artifact_links(evidence_refs, repo_blob_base),
                "tracker_rows_impacted": build_artifact_links(tracker_refs, repo_blob_base),
                "resolution_evidence": build_artifact_links(resolution_refs, repo_blob_base),
            }
        )
    return incidents


def incident_signal_code(failure_mode: str) -> str:
    text = clean_markdown_cell(failure_mode).lower()
    if "403" in text:
        return "http_403"
    if "challenge" in text or "waf" in text or "cloudflare" in text:
        return "waf_or_challenge"
    if "500" in text:
        return "http_500"
    if "html" in text or "anti-scraping" in text or "anti-bot" in text:
        return "anti_html"
    return "other"


def status_label(state: str) -> str:
    mapping = {
        "ok": "ok",
        "missing": "missing",
        "not_run": "not_run",
        "partial": "partial",
        "error": "error",
        "degraded": "degraded",
        "unknown": "unknown",
        "running": "running",
    }
    return mapping.get(clean_markdown_cell(state).lower(), "unknown")


def pick_latest_timestamp(values: list[str]) -> str:
    parsed = [(parse_iso_datetime(value), value) for value in values if clean_markdown_cell(value)]
    parsed = [item for item in parsed if item[0] is not None]
    if not parsed:
        return ""
    parsed.sort(key=lambda item: item[0])
    return parsed[-1][1]


def matches_obstruction_signal(source: dict[str, Any]) -> bool:
    message = clean_markdown_cell(source.get("last_message")).lower()
    if "403" in message or "challenge" in message or "anti-bot" in message or "anti-scraping" in message or "imperva" in message:
        return True
    flags = source.get("flags") or {}
    return bool(flags.get("blocked_note"))


def build_blocked_source_rows(
    status_payload: dict[str, Any],
    incidents: list[dict[str, Any]],
    repo_blob_base: str,
) -> list[dict[str, Any]]:
    source_lookup = {clean_markdown_cell(source.get("source_id")): source for source in status_payload.get("sources") or []}
    open_incidents = [incident for incident in incidents if clean_markdown_cell(incident.get("status")).upper() == "OPEN"]
    incidents_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    blocked_source_ids: set[str] = set()

    for incident in open_incidents:
        source_id = clean_markdown_cell(incident.get("source_id"))
        if source_id:
            incidents_by_source[source_id].append(incident)
            blocked_source_ids.add(source_id)

    for source in status_payload.get("sources") or []:
        source_id = clean_markdown_cell(source.get("source_id"))
        if source_id and matches_obstruction_signal(source):
            blocked_source_ids.add(source_id)

    rows: list[dict[str, Any]] = []
    for source_id in sorted(blocked_source_ids):
        source = source_lookup.get(source_id, {})
        source_incidents = sorted(
            incidents_by_source.get(source_id, []),
            key=lambda item: parse_iso_datetime(item.get("last_seen_utc") or "") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        latest_incident = source_incidents[0] if source_incidents else {}
        evidence_links = build_artifact_links(
            [link.get("path") for incident in source_incidents for link in incident.get("evidence", [])],
            repo_blob_base,
        )
        tracker_links = build_artifact_links(
            [link.get("path") for incident in source_incidents for link in incident.get("tracker_rows_impacted", [])],
            repo_blob_base,
        )
        desired = bool(source.get("desired"))
        progress = source.get("progress") or {}
        target = int(progress.get("target") or 0)
        loaded = int(progress.get("loaded") or 0)
        gap = max(target - loaded, 0)
        last_change_at = pick_latest_timestamp(
            [
                clean_markdown_cell(source.get("last_seen_at")),
                clean_markdown_cell(latest_incident.get("last_seen_utc")),
                clean_markdown_cell(latest_incident.get("first_seen_utc")),
            ]
        )
        source_url = clean_markdown_cell(source.get("default_url")) or clean_markdown_cell(source.get("last_source_url"))
        explorer_href = f"/explorer-sources/?q={quote(source_id)}"
        rows.append(
            {
                "source_id": source_id,
                "source_name": clean_markdown_cell(source.get("source_name")) or source_id,
                "domain": clean_markdown_cell(source.get("domain")),
                "scope": clean_markdown_cell(source.get("scope")),
                "desired": desired,
                "current_health_state": status_label(source.get("state")),
                "current_health_label": clean_markdown_cell(source.get("state")) or "unknown",
                "tracker_status": clean_markdown_cell((source.get("tracker") or {}).get("status")),
                "tracker_block_note": clean_markdown_cell((source.get("tracker") or {}).get("bloque")),
                "incident_count": len(source_incidents),
                "latest_incident_id": clean_markdown_cell(latest_incident.get("incident_id")),
                "latest_failure_mode": clean_markdown_cell(latest_incident.get("failure_mode")),
                "latest_failure_signal": incident_signal_code(latest_incident.get("failure_mode") or ""),
                "last_change_at": last_change_at,
                "affected_coverage": {
                    "loaded": loaded,
                    "target": target,
                    "gap": gap,
                    "percent": int(progress.get("percent") or 0) if progress.get("percent") is not None else None,
                },
                "warehouse": source.get("warehouse") or {},
                "source_url": source_url,
                "source_url_public": build_repo_blob_url(repo_blob_base, source_url) if source_url.startswith("docs/") else source_url,
                "explorer_sources_path": explorer_href,
                "evidence": evidence_links,
                "tracker_rows_impacted": tracker_links,
                "incidents": source_incidents,
            }
        )

    rows.sort(
        key=lambda item: (
            0 if item.get("current_health_state") != "ok" else 1,
            -(item.get("incident_count") or 0),
            -(item.get("affected_coverage", {}).get("gap") or 0),
            item.get("source_name") or "",
        )
    )
    return rows


def load_status_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(
    status_payload: dict[str, Any],
    incidents: list[dict[str, Any]],
    *,
    generated_at: str,
    status_json_path: str,
    blockers_log_path: str,
    repo_blob_base: str,
) -> dict[str, Any]:
    open_incidents = [incident for incident in incidents if clean_markdown_cell(incident.get("status")).upper() == "OPEN"]
    blocked_sources = build_blocked_source_rows(status_payload, incidents, repo_blob_base)
    signal_counts = Counter(incident_signal_code(incident.get("failure_mode") or "") for incident in open_incidents)
    desired_total = int((status_payload.get("summary") or {}).get("desired") or 0)
    desired_progress = (status_payload.get("summary") or {}).get("desired_progress") or {}
    affected_desired_sources = [item for item in blocked_sources if item.get("desired")]
    affected_target = sum(int((item.get("affected_coverage") or {}).get("target") or 0) for item in affected_desired_sources)
    affected_loaded = sum(int((item.get("affected_coverage") or {}).get("loaded") or 0) for item in affected_desired_sources)
    affected_gap = sum(int((item.get("affected_coverage") or {}).get("gap") or 0) for item in affected_desired_sources)
    total_target = int(desired_progress.get("target") or 0)
    last_change_at = pick_latest_timestamp(
        [
            clean_markdown_cell(status_payload.get("generated_at")),
            *[clean_markdown_cell(item.get("last_change_at")) for item in blocked_sources],
        ]
    )
    freshness = derive_freshness_tier(clean_markdown_cell(status_payload.get("generated_at")), generated_at)

    return {
        "meta": {
            "schema_version": "obstruction_tracker_v1",
            "generated_at": generated_at,
            "source_snapshot_generated_at": clean_markdown_cell(status_payload.get("generated_at")),
            "status_json_path": status_json_path,
            "blockers_log_path": blockers_log_path,
            "repo_blob_base": repo_blob_base,
            "freshness": freshness,
        },
        "summary": {
            "source_health": status_payload.get("summary") or {},
            "obstruction": {
                "open_incidents_total": len(open_incidents),
                "blocked_sources_total": len(blocked_sources),
                "blocked_desired_sources_total": len(affected_desired_sources),
                "distinct_organisms_total": len({clean_markdown_cell(item.get("organism")) for item in open_incidents if clean_markdown_cell(item.get("organism"))}),
                "signal_counts": dict(signal_counts),
                "evidence_artifacts_total": sum(len(item.get("evidence") or []) for item in open_incidents),
            },
            "affected_coverage": {
                "desired_sources_total": desired_total,
                "affected_desired_sources_total": len(affected_desired_sources),
                "affected_desired_sources_pct": round((len(affected_desired_sources) * 100) / desired_total) if desired_total else None,
                "desired_progress_target": total_target,
                "affected_target": affected_target,
                "affected_loaded": affected_loaded,
                "affected_gap": affected_gap,
                "affected_target_share_pct": round((affected_target * 100) / total_target) if total_target else None,
            },
            "last_change_at": last_change_at,
        },
        "blocked_sources": blocked_sources,
        "incidents": open_incidents,
        "audit_links": {
            "explorer_sources": "/explorer-sources/",
            "status_json": status_json_path,
            "name_and_shame_log": build_repo_blob_url(repo_blob_base, blockers_log_path),
            "tracker_log": build_repo_blob_url(repo_blob_base, "docs/etl/e2e-scrape-load-tracker.md"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta feed JSON para obstruction tracker")
    parser.add_argument("--status-json", default=str(DEFAULT_STATUS_JSON), help="Ruta al status.json fuente")
    parser.add_argument("--blockers-log", default=str(DEFAULT_BLOCKERS_LOG), help="Ruta al markdown Name & Shame")
    parser.add_argument("--out", required=True, help="Ruta de salida JSON")
    parser.add_argument("--generated-at", default="", help="Timestamp ISO8601 de generacion")
    parser.add_argument(
        "--repo-blob-base",
        default=DEFAULT_REPO_BLOB_BASE,
        help="Base URL para enlaces publicos a artefactos del repo",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status_json_path = Path(args.status_json)
    blockers_log_path = Path(args.blockers_log)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not status_json_path.exists():
        print(f"ERROR: no existe el status-json -> {status_json_path}")
        return 2
    if not blockers_log_path.exists():
        print(f"ERROR: no existe el blockers-log -> {blockers_log_path}")
        return 2

    generated_at = clean_markdown_cell(args.generated_at) or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status_payload = load_status_payload(status_json_path)
    incidents = parse_name_and_shame_log(blockers_log_path, clean_markdown_cell(args.repo_blob_base) or DEFAULT_REPO_BLOB_BASE)
    payload = build_payload(
        status_payload,
        incidents,
        generated_at=generated_at,
        status_json_path=f"/{status_json_path.as_posix().lstrip('./')}",
        blockers_log_path=blockers_log_path.as_posix(),
        repo_blob_base=clean_markdown_cell(args.repo_blob_base) or DEFAULT_REPO_BLOB_BASE,
    )
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "OK obstruction tracker snapshot -> "
        f"{out_path} (blocked_sources={len(payload.get('blocked_sources') or [])} incidents={len(payload.get('incidents') or [])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
