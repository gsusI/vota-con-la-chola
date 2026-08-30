#!/usr/bin/env python3
"""Exporta un feed estatico para /obstruction-tracker/."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.sanitize import redact_sensitive_text


DEFAULT_STATUS_JSON = Path("ui/gh-pages-next/public/explorer-sources/data/status.json")
DEFAULT_BLOCKERS_LOG = Path("docs/etl/name-and-shame-access-blockers.md")
DEFAULT_READINESS_JSON = Path("etl/data/published/scale-readiness-latest.json")
DEFAULT_REPO_BLOB_BASE = "https://github.com/gsusI/vota-con-la-chola/blob/main"
DEFAULT_PUBLIC_STATUS_PATH = "/explorer-sources/data/status.json"
DEFAULT_PUBLIC_EVIDENCE_BASE = "/obstruction-tracker/evidence"


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_markdown_cell(value: Any) -> str:
    return safe_text(value).replace("`", "").strip()


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
    text = safe_text(value)
    if not text:
        return []
    refs: list[str] = []
    for part in text.split(";"):
        candidates = re.findall(r"`([^`]+)`", part)
        if not candidates:
            candidates = [clean_markdown_cell(part)]
        for candidate in candidates:
            ref = clean_markdown_cell(candidate)
            if not ref or ref.lower() in {"n/a", "na", "none", "-"}:
                continue
            if ref.startswith(("http://", "https://")) or ("/" in ref and " " not in ref):
                ref_path, _line = split_path_line(ref)
                if not ref.startswith(("http://", "https://")) and Path(ref_path).is_dir():
                    refs.extend(
                        item.as_posix()
                        for item in sorted(Path(ref_path).rglob("*"))
                        if item.is_file()
                    )
                else:
                    refs.append(ref)
    return refs


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


def split_path_line(ref: str) -> tuple[str, str]:
    raw = clean_markdown_cell(ref)
    if ":" in raw and raw.rsplit(":", 1)[1].isdigit():
        return raw.rsplit(":", 1)
    return raw, ""


def public_evidence_filename(ref: str) -> str:
    source_path, _line = split_path_line(ref)
    digest = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(source_path).name).strip("-.") or "evidence"
    return f"{digest}-{safe_name}.txt"


def build_public_evidence_url(public_evidence_base: str, ref: str) -> str:
    _source_path, line = split_path_line(ref)
    suffix = f"#L{line}" if line else ""
    return f"{public_evidence_base.rstrip('/')}/{quote(public_evidence_filename(ref))}{suffix}"


def build_artifact_links(
    refs: list[str],
    repo_blob_base: str,
    public_evidence_base: str = "",
) -> list[dict[str, str]]:
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
        repository_url = build_repo_blob_url(repo_blob_base, raw)
        public_url = (
            build_public_evidence_url(public_evidence_base, raw)
            if public_evidence_base and not raw.startswith(("http://", "https://"))
            else repository_url
        )
        items.append({"path": raw, "label": label, "url": public_url, "repository_url": repository_url})
    return items


def parse_name_and_shame_log(
    path: Path,
    repo_blob_base: str,
    public_evidence_base: str = "",
) -> list[dict[str, Any]]:
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
                "evidence": build_artifact_links(evidence_refs, repo_blob_base, public_evidence_base),
                "tracker_rows_impacted": build_artifact_links(tracker_refs, repo_blob_base, public_evidence_base),
                "resolution_evidence": build_artifact_links(resolution_refs, repo_blob_base, public_evidence_base),
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
    public_evidence_base: str,
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
            public_evidence_base,
        )
        tracker_links = build_artifact_links(
            [link.get("path") for incident in source_incidents for link in incident.get("tracker_rows_impacted", [])],
            repo_blob_base,
            public_evidence_base,
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


def build_scale_readiness_summary(payload: dict[str, Any]) -> dict[str, Any]:
    corpora = []
    for corpus in payload.get("corpora") or []:
        corpora.append(
            {
                "id": clean_markdown_cell(corpus.get("id")),
                "label": clean_markdown_cell(corpus.get("label")),
                "rows": int(corpus.get("rows") or 0),
                "status": clean_markdown_cell(corpus.get("status")),
                "scale_gate_passed": bool(corpus.get("scale_gate_passed")),
                "promotion_gate_passed": bool(corpus.get("promotion_gate_passed")),
                "source_ids": [clean_markdown_cell(item) for item in corpus.get("source_ids") or []],
                "next_gate": clean_markdown_cell(corpus.get("next_gate")),
            }
        )

    gaps = []
    for gap in payload.get("gaps") or []:
        gaps.append(
            {
                "id": clean_markdown_cell(gap.get("id")),
                "status": clean_markdown_cell(gap.get("status")),
                "current_real_rows": int(gap.get("current_real_rows") or 0),
                "target_real_rows": int(gap.get("target_real_rows") or 0),
                "next_action": clean_markdown_cell(gap.get("next_action")),
            }
        )

    foundation = payload.get("foundation") or {}
    failure = payload.get("failure") or {}
    return {
        "status": clean_markdown_cell(payload.get("status")),
        "foundation": {
            "ready": foundation.get("ready") is True,
            "meaning": clean_markdown_cell(foundation.get("meaning")),
        },
        "failure": {
            "kind": clean_markdown_cell(failure.get("kind")),
            "reason": clean_markdown_cell(failure.get("reason")),
        }
        if failure
        else {},
        "summary": payload.get("summary") or {},
        "corpora": corpora,
        "gaps": gaps,
    }


def build_payload(
    status_payload: dict[str, Any],
    incidents: list[dict[str, Any]],
    *,
    readiness_payload: dict[str, Any] | None,
    generated_at: str,
    public_status_path: str,
    status_json_evidence_path: str,
    blockers_log_path: str,
    readiness_json_path: str,
    repo_blob_base: str,
    public_evidence_base: str = DEFAULT_PUBLIC_EVIDENCE_BASE,
) -> dict[str, Any]:
    open_incidents = [incident for incident in incidents if clean_markdown_cell(incident.get("status")).upper() == "OPEN"]
    resolved_incidents = [
        incident for incident in incidents if clean_markdown_cell(incident.get("status")).upper() == "RESOLVED"
    ]
    blocked_sources = build_blocked_source_rows(status_payload, incidents, repo_blob_base, public_evidence_base)
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
            "schema_version": "obstruction_tracker_v2",
            "generated_at": generated_at,
            "source_snapshot_generated_at": clean_markdown_cell(status_payload.get("generated_at")),
            "status_json_path": public_status_path,
            "status_json_evidence_path": status_json_evidence_path,
            "blockers_log_path": blockers_log_path,
            "readiness_json_path": readiness_json_path,
            "repo_blob_base": repo_blob_base,
            "freshness": freshness,
        },
        "policy": {
            "data_origin": "official_real_records_only",
            "synthetic_or_mock_records": "forbidden",
            "public_domain_personal_information": "retained",
            "excluded_material": [
                "credentials_and_secrets",
                "private_session_material",
                "workstation_identifiers",
                "non_public_personal_information",
            ],
        },
        "summary": {
            "source_health": status_payload.get("summary") or {},
            "obstruction": {
                "open_incidents_total": len(open_incidents),
                "resolved_incidents_total": len(resolved_incidents),
                "historical_incidents_total": len(incidents),
                "blocked_sources_total": len(blocked_sources),
                "blocked_desired_sources_total": len(affected_desired_sources),
                "distinct_organisms_total": len({clean_markdown_cell(item.get("organism")) for item in open_incidents if clean_markdown_cell(item.get("organism"))}),
                "signal_counts": dict(signal_counts),
                "evidence_artifacts_total": sum(len(item.get("evidence") or []) for item in open_incidents),
                "evidence_source_files_total": len(
                    {
                        split_path_line(link.get("path") or "")[0]
                        for item in incidents
                        for key in ("evidence", "tracker_rows_impacted", "resolution_evidence")
                        for link in item.get(key) or []
                        if link.get("path") and not safe_text(link.get("path")).startswith(("http://", "https://"))
                    }
                ),
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
        "scale_readiness": build_scale_readiness_summary(readiness_payload or {}),
        "blocked_sources": blocked_sources,
        "incidents": open_incidents,
        "incident_history": incidents,
        "audit_links": {
            "self": "/obstruction-tracker/data/obstructions.json",
            "explorer_sources": "/explorer-sources/",
            "status_json": public_status_path,
            "name_and_shame_log": build_repo_blob_url(repo_blob_base, blockers_log_path),
            "tracker_log": build_repo_blob_url(repo_blob_base, "docs/etl/e2e-scrape-load-tracker.md"),
            "scale_readiness": build_repo_blob_url(repo_blob_base, readiness_json_path),
            "evidence_manifest": f"{public_evidence_base.rstrip('/')}/manifest.json",
        },
    }


def canonicalize_public_evidence_text(value: str) -> str:
    """Return stable text bytes without changing evidence-bearing characters."""

    lines = value.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    return "\n".join(line.rstrip(" \t") for line in lines) + "\n"


def export_public_evidence_bundle(incidents: list[dict[str, Any]], out_dir: Path) -> dict[str, Any]:
    source_paths: set[str] = set()
    for incident in incidents:
        for key in ("evidence", "tracker_rows_impacted", "resolution_evidence"):
            for link in incident.get(key) or []:
                ref = safe_text(link.get("path"))
                source_path, _line = split_path_line(ref)
                if source_path and not source_path.startswith(("http://", "https://")):
                    source_paths.add(source_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    expected_names: set[str] = {"manifest.json"}
    files: list[dict[str, Any]] = []
    for source_path in sorted(source_paths):
        source = Path(source_path)
        if source.is_absolute() or ".." in source.parts or not source.is_file():
            raise ValueError(f"invalid or missing evidence path: {source_path}")
        raw = source.read_bytes()
        try:
            source_text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"evidence is not UTF-8 text: {source_path}") from exc
        # GitHub Pages may normalize CRLF text files when committing the static
        # tree. Build the manifest from canonical LF bytes so its digest remains
        # identical before and after publication.
        source_normalized = source_text.replace("\r\n", "\n").replace("\r", "\n")
        public_text = redact_sensitive_text(source_normalized)
        public_text = public_text.replace("file:///Users/<redacted-user>", "<redacted-local-root>")
        public_text = public_text.replace("/Users/<redacted-user>", "<redacted-local-root>")
        public_text = public_text.replace("/home/<redacted-user>", "<redacted-local-root>")
        public_text = canonicalize_public_evidence_text(public_text)
        filename = public_evidence_filename(source_path)
        expected_names.add(filename)
        destination = out_dir / filename
        atomic_write_bytes(destination, public_text.encode("utf-8"))
        files.append(
            {
                "source_path": source_path,
                "public_file": filename,
                "source_bytes": len(raw),
                "public_bytes": destination.stat().st_size,
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "public_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "sanitized": public_text != source_normalized,
                "official_public_information_retained": True,
            }
        )

    for existing in out_dir.iterdir():
        if existing.is_file() and existing.name not in expected_names:
            existing.unlink()

    manifest = {
        "schema_version": "obstruction_evidence_bundle_v1",
        "policy": {
            "official_public_information_retained": True,
            "credentials_private_sessions_and_workstation_paths_redacted": True,
        },
        "summary": {
            "files_total": len(files),
            "files_sanitized": sum(1 for item in files if item["sanitized"]),
            "source_bytes_total": sum(int(item["source_bytes"]) for item in files),
            "public_bytes_total": sum(int(item["public_bytes"]) for item in files),
        },
        "files": files,
    }
    atomic_write_json(out_dir / "manifest.json", manifest)
    return manifest


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta feed JSON para obstruction tracker")
    parser.add_argument("--status-json", default=str(DEFAULT_STATUS_JSON), help="Ruta al status.json fuente")
    parser.add_argument("--blockers-log", default=str(DEFAULT_BLOCKERS_LOG), help="Ruta al markdown Name & Shame")
    parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON), help="Ruta al reporte de escala real")
    parser.add_argument(
        "--public-status-path",
        default=DEFAULT_PUBLIC_STATUS_PATH,
        help="Ruta publica canonica del status.json",
    )
    parser.add_argument("--out", required=True, help="Ruta de salida JSON")
    parser.add_argument("--evidence-dir", default="", help="Directorio para copias publicas sanitizadas")
    parser.add_argument(
        "--public-evidence-base",
        default=DEFAULT_PUBLIC_EVIDENCE_BASE,
        help="Ruta publica base del bundle de evidencia",
    )
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
    readiness_json_path = Path(args.readiness_json)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not status_json_path.exists():
        print(f"ERROR: no existe el status-json -> {status_json_path}")
        return 2
    if not blockers_log_path.exists():
        print(f"ERROR: no existe el blockers-log -> {blockers_log_path}")
        return 2
    if not readiness_json_path.exists():
        print(f"ERROR: no existe el readiness-json -> {readiness_json_path}")
        return 2

    generated_at = clean_markdown_cell(args.generated_at) or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status_payload = load_status_payload(status_json_path)
    readiness_payload = load_status_payload(readiness_json_path)
    public_evidence_base = clean_markdown_cell(args.public_evidence_base) or DEFAULT_PUBLIC_EVIDENCE_BASE
    incidents = parse_name_and_shame_log(
        blockers_log_path,
        clean_markdown_cell(args.repo_blob_base) or DEFAULT_REPO_BLOB_BASE,
        public_evidence_base,
    )
    evidence_manifest = None
    if clean_markdown_cell(args.evidence_dir):
        evidence_manifest = export_public_evidence_bundle(incidents, Path(args.evidence_dir))
    payload = build_payload(
        status_payload,
        incidents,
        readiness_payload=readiness_payload,
        generated_at=generated_at,
        public_status_path=clean_markdown_cell(args.public_status_path) or DEFAULT_PUBLIC_STATUS_PATH,
        status_json_evidence_path=status_json_path.as_posix(),
        blockers_log_path=blockers_log_path.as_posix(),
        readiness_json_path=readiness_json_path.as_posix(),
        repo_blob_base=clean_markdown_cell(args.repo_blob_base) or DEFAULT_REPO_BLOB_BASE,
        public_evidence_base=public_evidence_base,
    )
    atomic_write_json(out_path, payload)
    print(
        "OK obstruction tracker snapshot -> "
        f"{out_path} (blocked_sources={len(payload.get('blocked_sources') or [])} "
        f"incidents={len(payload.get('incidents') or [])} "
        f"evidence_files={int((evidence_manifest or {}).get('summary', {}).get('files_total') or 0)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
