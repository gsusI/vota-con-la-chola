#!/usr/bin/env python3
"""Valida el contrato publico y acotado de /obstruction-tracker/."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.privacy import collect_findings


DEFAULT_MAX_BYTES = 5_000_000
REQUIRED_POLICY = {
    "data_origin": "official_real_records_only",
    "synthetic_or_mock_records": "forbidden",
    "public_domain_personal_information": "retained",
}
PRIVATE_PATH_MARKERS = ("/Users/", "/home/", "file://")


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def has_private_path(value: Any) -> bool:
    text = safe_text(value)
    return any(marker in text for marker in PRIVATE_PATH_MARKERS)


def validate_artifact_links(
    links: Any,
    *,
    context: str,
    errors: list[str],
    evidence_root: Path | None = None,
) -> None:
    if not isinstance(links, list):
        errors.append(f"{context}: expected list")
        return
    seen: set[str] = set()
    for index, link in enumerate(links):
        prefix = f"{context}[{index}]"
        if not isinstance(link, dict):
            errors.append(f"{prefix}: expected object")
            continue
        path = safe_text(link.get("path"))
        label = safe_text(link.get("label"))
        url = safe_text(link.get("url"))
        repository_url = safe_text(link.get("repository_url"))
        if not path or not label or not url:
            errors.append(f"{prefix}: path, label and url are required")
        if path in seen:
            errors.append(f"{prefix}: duplicate path {path}")
        seen.add(path)
        if "`" in path or "`" in url:
            errors.append(f"{prefix}: markdown delimiter leaked")
        if has_private_path(path) or has_private_path(url):
            errors.append(f"{prefix}: private workstation path leaked")
        if path.startswith(("http://", "https://")):
            if not url.startswith("https://"):
                errors.append(f"{prefix}: external evidence URL must use https")
        elif not url.startswith("/obstruction-tracker/evidence/"):
            errors.append(f"{prefix}: repository evidence must use the public evidence bundle")
        if repository_url and not repository_url.startswith("https://"):
            errors.append(f"{prefix}: repository_url must use https")
        if evidence_root and url.startswith("/obstruction-tracker/evidence/"):
            public_path = unquote(urlsplit(url).path).removeprefix("/obstruction-tracker/evidence/")
            if not public_path or "/" in public_path or not (evidence_root / public_path).is_file():
                errors.append(f"{prefix}: bundled evidence file is missing")


def validate_incidents(
    incidents: Any,
    *,
    expected_status: str | None,
    context: str,
    errors: list[str],
    evidence_root: Path | None = None,
) -> set[str]:
    if not isinstance(incidents, list):
        errors.append(f"{context}: expected list")
        return set()
    ids: set[str] = set()
    required = (
        "incident_id",
        "first_seen_utc",
        "last_seen_utc",
        "organism",
        "source_id",
        "endpoint_or_page",
        "failure_mode",
        "status",
        "next_escalation",
    )
    for index, incident in enumerate(incidents):
        prefix = f"{context}[{index}]"
        if not isinstance(incident, dict):
            errors.append(f"{prefix}: expected object")
            continue
        incident_id = safe_text(incident.get("incident_id"))
        if not incident_id:
            errors.append(f"{prefix}: incident_id is required")
        elif incident_id in ids:
            errors.append(f"{prefix}: duplicate incident_id {incident_id}")
        ids.add(incident_id)
        for key in required:
            if not safe_text(incident.get(key)):
                errors.append(f"{prefix}: {key} is required")
        if expected_status and safe_text(incident.get("status")).upper() != expected_status:
            errors.append(f"{prefix}: status must be {expected_status}")
        if not safe_text(incident.get("first_seen_utc")).endswith("Z"):
            errors.append(f"{prefix}: first_seen_utc must be UTC")
        if not safe_text(incident.get("last_seen_utc")).endswith("Z"):
            errors.append(f"{prefix}: last_seen_utc must be UTC")
        evidence = incident.get("evidence")
        validate_artifact_links(evidence, context=f"{prefix}.evidence", errors=errors, evidence_root=evidence_root)
        if not evidence:
            errors.append(f"{prefix}: at least one evidence artifact is required")
        validate_artifact_links(
            incident.get("tracker_rows_impacted"),
            context=f"{prefix}.tracker_rows_impacted",
            errors=errors,
            evidence_root=evidence_root,
        )
        validate_artifact_links(
            incident.get("resolution_evidence"),
            context=f"{prefix}.resolution_evidence",
            errors=errors,
            evidence_root=evidence_root,
        )
    return ids


def validate_scale_readiness(readiness: Any, errors: list[str]) -> None:
    if not isinstance(readiness, dict):
        errors.append("scale_readiness: expected object")
        return
    summary = readiness.get("summary") or {}
    corpora = readiness.get("corpora") or []
    gaps = readiness.get("gaps") or []
    status = safe_text(readiness.get("status"))
    if not status:
        errors.append("scale_readiness.status is required")
    if status == "not_ready":
        foundation = readiness.get("foundation") or {}
        failure = readiness.get("failure") or {}
        if foundation.get("ready") is not False:
            errors.append("scale_readiness not_ready requires foundation.ready=false")
        if not safe_text(failure.get("kind")) or not safe_text(failure.get("reason")):
            errors.append("scale_readiness not_ready requires an exact failure")
        if summary or corpora or gaps:
            errors.append(
                "scale_readiness validation failure cannot expose unvalidated summary rows"
            )
        return
    if integer(summary.get("registered_real_corpora")) != len(corpora):
        errors.append("scale_readiness registered_real_corpora does not match corpora")
    validated = sum(1 for corpus in corpora if safe_text(corpus.get("status")).startswith("validated_real"))
    if integer(summary.get("validated_real_corpora")) != validated:
        errors.append("scale_readiness validated_real_corpora does not reconcile")
    million_lanes = sum(1 for corpus in corpora if integer(corpus.get("rows")) >= 1_000_000)
    if integer(summary.get("real_million_scale_lanes")) != million_lanes:
        errors.append("scale_readiness real_million_scale_lanes does not reconcile")
    promoted = sum(1 for corpus in corpora if bool(corpus.get("promotion_gate_passed")))
    if integer(summary.get("promoted_lanes")) != promoted:
        errors.append("scale_readiness promoted_lanes does not reconcile")
    if integer(summary.get("open_gaps")) != len(gaps):
        errors.append("scale_readiness open_gaps does not match gaps")
    corpus_ids = [safe_text(corpus.get("id")) for corpus in corpora]
    gap_ids = [safe_text(gap.get("id")) for gap in gaps]
    if not corpora or any(not item for item in corpus_ids) or len(corpus_ids) != len(set(corpus_ids)):
        errors.append("scale_readiness corpus ids must be non-empty and unique")
    if any(integer(corpus.get("rows")) < 0 or not corpus.get("source_ids") for corpus in corpora):
        errors.append("scale_readiness corpora require non-negative real rows and source_ids")
    if any(not item for item in gap_ids) or len(gap_ids) != len(set(gap_ids)):
        errors.append("scale_readiness gap ids must be non-empty and unique")


def validate_evidence_bundle(evidence_root: Path, errors: list[str]) -> dict[str, int]:
    manifest_path = evidence_root / "manifest.json"
    if not manifest_path.is_file():
        errors.append("evidence bundle manifest is missing")
        return {"files_total": 0, "files_sanitized": 0}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"evidence bundle manifest is invalid: {exc}")
        return {"files_total": 0, "files_sanitized": 0}
    if safe_text(manifest.get("schema_version")) != "obstruction_evidence_bundle_v1":
        errors.append("evidence bundle schema_version is invalid")
    files = manifest.get("files") or []
    public_names: set[str] = set()
    for index, item in enumerate(files):
        prefix = f"evidence_manifest.files[{index}]"
        source_path = safe_text(item.get("source_path"))
        public_file = safe_text(item.get("public_file"))
        if not source_path or Path(source_path).is_absolute() or ".." in Path(source_path).parts:
            errors.append(f"{prefix}: source_path must be repo-relative")
            continue
        if not public_file or "/" in public_file or public_file in public_names:
            errors.append(f"{prefix}: public_file must be unique and flat")
            continue
        public_names.add(public_file)
        source = Path(source_path)
        public = evidence_root / public_file
        if not source.is_file() or not public.is_file():
            errors.append(f"{prefix}: source or public file is missing")
            continue
        source_bytes = source.read_bytes()
        public_bytes = public.read_bytes()
        if integer(item.get("source_bytes")) != len(source_bytes) or safe_text(item.get("source_sha256")) != hashlib.sha256(source_bytes).hexdigest():
            errors.append(f"{prefix}: source bytes or hash drifted")
        if integer(item.get("public_bytes")) != len(public_bytes) or safe_text(item.get("public_sha256")) != hashlib.sha256(public_bytes).hexdigest():
            errors.append(f"{prefix}: public bytes or hash drifted")
        if item.get("official_public_information_retained") is not True:
            errors.append(f"{prefix}: public information retention policy missing")
    summary = manifest.get("summary") or {}
    if integer(summary.get("files_total")) != len(files):
        errors.append("evidence bundle files_total does not reconcile")
    if integer(summary.get("files_sanitized")) != sum(1 for item in files if item.get("sanitized") is True):
        errors.append("evidence bundle files_sanitized does not reconcile")
    actual_public_files = {item.name for item in evidence_root.iterdir() if item.is_file() and item.name != "manifest.json"}
    if actual_public_files != public_names:
        errors.append("evidence bundle contains missing or unregistered files")
    privacy_findings, _files_scanned = collect_findings([evidence_root])
    if privacy_findings:
        errors.append(f"evidence bundle has {len(privacy_findings)} publication hygiene findings")
    return {
        "files_total": len(files),
        "files_sanitized": sum(1 for item in files if item.get("sanitized") is True),
    }


def validate_payload(
    payload: dict[str, Any],
    *,
    file_size_bytes: int,
    max_bytes: int,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    meta = payload.get("meta") or {}
    policy = payload.get("policy") or {}
    summary = payload.get("summary") or {}
    obstruction = summary.get("obstruction") or {}
    blocked_sources = payload.get("blocked_sources") or []

    if safe_text(meta.get("schema_version")) != "obstruction_tracker_v2":
        errors.append("meta.schema_version must be obstruction_tracker_v2")
    if safe_text(meta.get("status_json_path")) != "/explorer-sources/data/status.json":
        errors.append("meta.status_json_path must use the public canonical route")
    if safe_text((payload.get("audit_links") or {}).get("self")) != "/obstruction-tracker/data/obstructions.json":
        errors.append("audit_links.self is not canonical")
    if safe_text((meta.get("freshness") or {}).get("tier")) not in {"fresh", "aging", "stale", "future", "unknown"}:
        errors.append("meta.freshness.tier is invalid")
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    if has_private_path(serialized_payload):
        errors.append("payload leaks a private workstation path")
    if "`" in serialized_payload:
        errors.append("payload leaks markdown code delimiters into public copy")
    for key, expected in REQUIRED_POLICY.items():
        if safe_text(policy.get(key)) != expected:
            errors.append(f"policy.{key} must be {expected}")
    if file_size_bytes > max_bytes:
        errors.append(f"payload exceeds byte budget: {file_size_bytes} > {max_bytes}")

    open_ids = validate_incidents(
        payload.get("incidents"),
        expected_status="OPEN",
        context="incidents",
        errors=errors,
        evidence_root=evidence_root,
    )
    history_ids = validate_incidents(
        payload.get("incident_history"),
        expected_status=None,
        context="incident_history",
        errors=errors,
        evidence_root=evidence_root,
    )
    if not open_ids.issubset(history_ids):
        errors.append("open incident ids are not a subset of incident history")
    resolved_total = sum(1 for item in payload.get("incident_history") or [] if safe_text(item.get("status")).upper() == "RESOLVED")
    if integer(obstruction.get("open_incidents_total")) != len(open_ids):
        errors.append("open_incidents_total does not reconcile")
    if integer(obstruction.get("resolved_incidents_total")) != resolved_total:
        errors.append("resolved_incidents_total does not reconcile")
    if integer(obstruction.get("historical_incidents_total")) != len(history_ids):
        errors.append("historical_incidents_total does not reconcile")
    evidence_total = sum(len(item.get("evidence") or []) for item in payload.get("incidents") or [])
    if integer(obstruction.get("evidence_artifacts_total")) != evidence_total:
        errors.append("evidence_artifacts_total does not reconcile")

    source_ids = [safe_text(item.get("source_id")) for item in blocked_sources]
    if any(not item for item in source_ids) or len(source_ids) != len(set(source_ids)):
        errors.append("blocked source ids must be non-empty and unique")
    if integer(obstruction.get("blocked_sources_total")) != len(blocked_sources):
        errors.append("blocked_sources_total does not reconcile")
    if sum(integer(item.get("incident_count")) for item in blocked_sources) != len(open_ids):
        errors.append("blocked source incident counts do not reconcile")
    for index, source in enumerate(blocked_sources):
        prefix = f"blocked_sources[{index}]"
        incident_ids = {safe_text(item.get("incident_id")) for item in source.get("incidents") or []}
        if integer(source.get("incident_count")) != len(incident_ids):
            errors.append(f"{prefix}: incident_count does not match incidents")
        if not incident_ids.issubset(open_ids):
            errors.append(f"{prefix}: contains unknown incident ids")
        validate_artifact_links(
            source.get("evidence"),
            context=f"{prefix}.evidence",
            errors=errors,
            evidence_root=evidence_root,
        )
        validate_artifact_links(
            source.get("tracker_rows_impacted"),
            context=f"{prefix}.tracker_rows_impacted",
            errors=errors,
            evidence_root=evidence_root,
        )

    validate_scale_readiness(payload.get("scale_readiness"), errors)
    evidence_checks = validate_evidence_bundle(evidence_root, errors) if evidence_root else {"files_total": 0, "files_sanitized": 0}
    if evidence_root and integer(obstruction.get("evidence_source_files_total")) != evidence_checks["files_total"]:
        errors.append("evidence_source_files_total does not match evidence bundle")
    return {
        "status": "ok" if not errors else "error",
        "checks": {
            "schema_version": safe_text(meta.get("schema_version")),
            "file_size_bytes": file_size_bytes,
            "max_bytes": max_bytes,
            "open_incidents_total": len(open_ids),
            "historical_incidents_total": len(history_ids),
            "blocked_sources_total": len(blocked_sources),
            "real_corpora_total": len((payload.get("scale_readiness") or {}).get("corpora") or []),
            "evidence_files_total": evidence_checks["files_total"],
            "evidence_files_sanitized": evidence_checks["files_sanitized"],
        },
        "errors": errors,
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
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
    parser = argparse.ArgumentParser(description="Valida el feed publico del obstruction tracker")
    parser.add_argument("--path", required=True, help="Ruta del feed JSON")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="Presupuesto maximo de bytes")
    parser.add_argument("--out", default="", help="Reporte JSON opcional")
    parser.add_argument("--evidence-root", default="", help="Directorio del bundle publico de evidencia")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: no existe el feed -> {path}")
        return 2
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: JSON invalido -> {exc}")
        return 2
    evidence_root = Path(args.evidence_root) if safe_text(args.evidence_root) else None
    report = validate_payload(
        payload,
        file_size_bytes=path.stat().st_size,
        max_bytes=args.max_bytes,
        evidence_root=evidence_root,
    )
    if args.out:
        atomic_write_json(Path(args.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
