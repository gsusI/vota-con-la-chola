#!/usr/bin/env python3
"""Export the public transparency dashboard from real, traceable project artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


DEFAULT_STATUS_JSON = Path("ui/gh-pages-next/public/explorer-sources/data/status.json")
DEFAULT_OBSTRUCTION_JSON = Path("ui/gh-pages-next/public/obstruction-tracker/data/obstructions.json")
DEFAULT_READINESS_JSON = Path("etl/data/published/scale-readiness-latest.json")
DEFAULT_ORIGIN_VERIFICATION_JSON = Path(
    "docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/live-scale-origin-parity.json"
)
DEFAULT_RELEASE_REGISTRY_JSON = Path("docs/release-notes/releases.json")
DEFAULT_DOCUMENT_FETCH_OPERATIONS_JSON = Path(
    "ui/gh-pages-next/public/transparency/data/document-fetch-operations.json"
)
DEFAULT_REPO_BLOB_BASE = "https://github.com/gsusI/vota-con-la-chola/blob/main"
DEFAULT_PUBLIC_STATUS_URL = "/explorer-sources/data/status.json"
DEFAULT_PUBLIC_OBSTRUCTION_URL = "/obstruction-tracker/data/obstructions.json"
DEFAULT_PUBLIC_DOCUMENT_FETCH_OPERATIONS_URL = (
    "/transparency/data/document-fetch-operations.json"
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if len(raw) == 10:
            return datetime.combine(date.fromisoformat(raw), time.min, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def freshness(source_at: Any, reference_at: Any) -> dict[str, Any]:
    source = parse_datetime(source_at)
    reference = parse_datetime(reference_at)
    if source is None or reference is None:
        return {
            "tier": "unknown",
            "label": "desconocida",
            "data_age_days": None,
            "should_warn": True,
            "detail": "Faltan fechas consistentes para evaluar la frescura.",
        }
    age_seconds = (reference - source).total_seconds()
    if age_seconds < 0:
        return {
            "tier": "future",
            "label": "futura",
            "data_age_days": -1,
            "should_warn": True,
            "detail": "Inconsistencia temporal: el corte fuente es posterior a la generación.",
        }
    age_days = int(age_seconds // 86400)
    if age_days <= 7:
        tier, label, warning = "fresh", "reciente", False
        detail = f"Corte reciente: {age_days} días de antigüedad."
    elif age_days <= 30:
        tier, label, warning = "aging", "vigente", True
        detail = f"Corte vigente con advertencia: {age_days} días sin refresco."
    else:
        tier, label, warning = "stale", "antigua", True
        detail = f"Corte antiguo: {age_days} días; la evidencia puede haber cambiado materialmente."
    return {
        "tier": tier,
        "label": label,
        "data_age_days": age_days,
        "should_warn": warning,
        "detail": detail,
    }


def repo_blob_url(base: str, path: str) -> str:
    encoded = "/".join(quote(part) for part in Path(path).as_posix().split("/"))
    return f"{base.rstrip('/')}/{encoded}"


def require_path(path_value: Any, *, field: str) -> Path:
    path = Path(str(path_value or "").strip())
    if path.is_absolute() or ".." in path.parts or not path.is_file():
        raise ValueError(f"{field} must reference an existing repository file: {path}")
    return path


def build_releases(registry: dict[str, Any], repo_blob_base: str) -> list[dict[str, Any]]:
    if registry.get("schema_version") != "public_release_registry_v1":
        raise ValueError("release registry schema must be public_release_registry_v1")
    releases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(registry.get("releases") or []):
        release_id = str(raw.get("id") or "").strip()
        if not release_id or release_id in seen:
            raise ValueError(f"release[{index}] has missing or duplicate id")
        seen.add(release_id)
        release_date = str(raw.get("date") or "").strip()
        if parse_datetime(release_date) is None:
            raise ValueError(f"release[{index}] has invalid date")
        note_path = require_path(raw.get("note_path"), field=f"release[{index}].note_path")
        note_text = note_path.read_text(encoding="utf-8")
        expected_heading = f"# {str(raw.get('title') or '').strip()}"
        if not note_text.startswith(expected_heading):
            raise ValueError(f"release[{index}] title does not match note heading")
        public_routes = [str(value).strip() for value in raw.get("public_routes") or []]
        if not public_routes or any(not value.startswith("/") for value in public_routes):
            raise ValueError(f"release[{index}] requires repository-relative public routes")
        evidence = []
        for evidence_index, evidence_value in enumerate(raw.get("evidence_paths") or []):
            evidence_path = require_path(
                evidence_value,
                field=f"release[{index}].evidence_paths[{evidence_index}]",
            )
            evidence.append(
                {
                    "path": evidence_path.as_posix(),
                    "url": repo_blob_url(repo_blob_base, evidence_path.as_posix()),
                    "sha256": sha256_file(evidence_path),
                }
            )
        releases.append(
            {
                "id": release_id,
                "date": release_date,
                "status": str(raw.get("status") or "").strip(),
                "title": str(raw.get("title") or "").strip(),
                "summary": str(raw.get("summary") or "").strip(),
                "public_routes": public_routes,
                "note": {
                    "path": note_path.as_posix(),
                    "url": repo_blob_url(repo_blob_base, note_path.as_posix()),
                    "bytes": note_path.stat().st_size,
                    "sha256": sha256_file(note_path),
                },
                "evidence": evidence,
            }
        )
    releases.sort(key=lambda item: (item["date"], item["id"]), reverse=True)
    return releases


def traced_metric(
    metric_id: str,
    label: str,
    value: int,
    unit: str,
    source_path: str,
    source_url: str,
) -> dict[str, Any]:
    return {
        "id": metric_id,
        "label": label,
        "value": int(value),
        "unit": unit,
        "source_path": source_path,
        "source_url": source_url,
    }


def build_payload(
    *,
    status: dict[str, Any],
    obstruction: dict[str, Any],
    readiness: dict[str, Any],
    origin: dict[str, Any],
    document_fetch: dict[str, Any],
    releases: list[dict[str, Any]],
    generated_at: str,
    status_path: str,
    obstruction_path: str,
    readiness_path: str,
    origin_path: str,
    document_fetch_path: str,
    release_registry_path: str,
    repo_blob_base: str,
) -> dict[str, Any]:
    status_summary = status.get("summary") or {}
    obstruction_summary = (obstruction.get("summary") or {}).get("obstruction") or {}
    obstruction_manifest_path = "ui/gh-pages-next/public/obstruction-tracker/evidence/manifest.json"
    obstruction_manifest = read_json(Path(obstruction_manifest_path))
    readiness_summary = readiness.get("summary") or {}
    checks = origin.get("checks") or {}
    remote_corpora = checks.get("remote_corpora") or []
    published_rows = sum(int(item.get("rows") or 0) for item in remote_corpora)
    published_files = sum(int(item.get("files") or 0) for item in remote_corpora)
    published_bytes = sum(int(item.get("bytes") or 0) for item in remote_corpora)
    snapshot_date = str(origin.get("snapshot_date") or checks.get("snapshot_date") or "").strip()
    source_freshness = freshness(status.get("generated_at"), generated_at)
    snapshot_freshness = freshness(snapshot_date, generated_at)
    status_url = DEFAULT_PUBLIC_STATUS_URL
    obstruction_url = DEFAULT_PUBLIC_OBSTRUCTION_URL
    evidence_manifest_url = "/obstruction-tracker/evidence/manifest.json"
    readiness_url = repo_blob_url(repo_blob_base, readiness_path)
    origin_evidence_url = repo_blob_url(repo_blob_base, origin_path)
    document_queue = document_fetch.get("queue") or {}
    document_summary = document_fetch.get("documents") or {}
    document_fetch_url = DEFAULT_PUBLIC_DOCUMENT_FETCH_OPERATIONS_URL

    metrics = [
        traced_metric("sources_ok", "Fuentes OK", status_summary.get("ok") or 0, "fuentes", status_path, status_url),
        traced_metric("sources_degraded", "Fuentes degradadas", status_summary.get("degraded") or 0, "fuentes", status_path, status_url),
        traced_metric("sources_not_run", "Fuentes no ejecutadas", status_summary.get("not_run") or 0, "fuentes", status_path, status_url),
        traced_metric("open_obstructions", "Incidencias abiertas", obstruction_summary.get("open_incidents_total") or 0, "incidencias", obstruction_path, obstruction_url),
        traced_metric("obstruction_evidence", "Evidencias públicas", (obstruction_manifest.get("summary") or {}).get("files_total") or 0, "ficheros", obstruction_manifest_path, evidence_manifest_url),
        traced_metric("validated_real_corpora", "Corpus reales validados", readiness_summary.get("validated_real_corpora") or 0, "corpora", readiness_path, readiness_url),
        traced_metric("real_million_scale_lanes", "Lanes de millón", readiness_summary.get("real_million_scale_lanes") or 0, "lanes", readiness_path, readiness_url),
        traced_metric("promoted_lanes", "Lanes promovidas", readiness_summary.get("promoted_lanes") or 0, "lanes", readiness_path, readiness_url),
        traced_metric("published_snapshot_rows", "Filas en origen público", published_rows, "filas", origin_path, checks.get("declared_snapshot_path") and (origin.get("urls") or {}).get("manifest") or origin_evidence_url),
        traced_metric("published_snapshot_files", "Ficheros de datos públicos", published_files, "ficheros", origin_path, (origin.get("urls") or {}).get("manifest") or origin_evidence_url),
        traced_metric("document_fetch_official_urls", "Documentos oficiales en cola", document_summary.get("official_urls_total") or 0, "documentos", document_fetch_path, document_fetch_url),
        traced_metric("document_fetch_terminal", "Descargas con estado terminal", document_queue.get("terminal_total") or 0, "documentos", document_fetch_path, document_fetch_url),
        traced_metric("document_fetch_unfinished", "Descargas pendientes", document_queue.get("unfinished_total") or 0, "documentos", document_fetch_path, document_fetch_url),
    ]

    return {
        "meta": {
            "schema_version": "transparency_dashboard_v1",
            "generated_at": generated_at,
            "source_status_generated_at": status.get("generated_at"),
            "latest_release_date": releases[0]["date"] if releases else None,
            "freshness_contract": "docs/method/truth-contract.md#estados-de-frescura",
        },
        "policy": {
            "data_origin": "official_real_records_and_verified_project_releases_only",
            "synthetic_or_mock_records": "forbidden",
            "placeholder_releases": "forbidden",
            "public_domain_personal_information": "retained",
            "metric_trace_required": True,
        },
        "headline": {
            "last_refresh_at": status.get("generated_at"),
            "latest_snapshot_date": snapshot_date,
            "latest_snapshot_release_id": checks.get("latest_manifest_sha256"),
            "latest_release_id": releases[0]["id"] if releases else None,
            "latest_release_date": releases[0]["date"] if releases else None,
        },
        "metrics": metrics,
        "source_health": {
            "summary": {
                key: int(status_summary.get(key) or 0)
                for key in ("desired", "present", "missing", "ok", "degraded", "not_run", "partial", "error", "running", "unknown")
            },
            "freshness": source_freshness,
            "source_path": status_path,
            "source_url": status_url,
            "source_sha256": sha256_file(Path(status_path)),
        },
        "obstruction": {
            "open_incidents_total": int(obstruction_summary.get("open_incidents_total") or 0),
            "blocked_sources_total": int(obstruction_summary.get("blocked_sources_total") or 0),
            "evidence_files_total": int((obstruction_manifest.get("summary") or {}).get("files_total") or 0),
            "source_path": obstruction_path,
            "source_url": obstruction_url,
            "source_sha256": sha256_file(Path(obstruction_path)),
            "evidence_manifest_url": evidence_manifest_url,
            "evidence_manifest_sha256": sha256_file(Path(obstruction_manifest_path)),
        },
        "scale_readiness": {
            "status": str(readiness.get("status") or ""),
            "summary": {
                key: int(readiness_summary.get(key) or 0)
                for key in ("registered_real_corpora", "validated_real_corpora", "real_million_scale_lanes", "promoted_lanes", "open_gaps")
            },
            "source_path": readiness_path,
            "source_url": readiness_url,
            "source_sha256": sha256_file(Path(readiness_path)),
        },
        "published_snapshot": {
            "verification_status": str(origin.get("status") or ""),
            "verification_passed": bool(origin.get("passed")),
            "metadata_freshness": bool(checks.get("metadata_freshness")),
            "warnings": [str(item) for item in origin.get("warnings") or []],
            "dataset_repo": str(origin.get("dataset_repo") or ""),
            "snapshot_date": snapshot_date,
            "release_id": str(checks.get("latest_manifest_sha256") or ""),
            "schema_version": str(checks.get("latest_schema_version") or ""),
            "snapshot_path": str(checks.get("declared_snapshot_path") or ""),
            "corpora_total": len(remote_corpora),
            "rows_total": published_rows,
            "data_files_total": published_files,
            "data_bytes_total": published_bytes,
            "corpora": remote_corpora,
            "freshness": snapshot_freshness,
            "pointer_url": (origin.get("urls") or {}).get("latest"),
            "manifest_url": (origin.get("urls") or {}).get("manifest"),
            "verification_evidence_path": origin_path,
            "verification_evidence_url": origin_evidence_url,
            "verification_evidence_sha256": sha256_file(Path(origin_path)),
        },
        "document_fetch": {
            "operational_contract_status": str(
                (document_fetch.get("scale_claim") or {}).get(
                    "operational_contract_status"
                )
                or ""
            ),
            "queue": document_queue,
            "documents": document_summary,
            "worker_policy": document_fetch.get("worker_policy") or {},
            "integrity": document_fetch.get("integrity") or {},
            "scale_claim": document_fetch.get("scale_claim") or {},
            "hosts": document_fetch.get("hosts") or [],
            "source_path": document_fetch_path,
            "source_url": document_fetch_url,
            "source_sha256": sha256_file(Path(document_fetch_path)),
        },
        "recent_changes": releases,
        "audit_links": {
            "self": "/transparency/data/transparency.json",
            "source_status": status_url,
            "obstruction_tracker": "/obstruction-tracker/",
            "obstruction_feed": obstruction_url,
            "document_fetch_operations": document_fetch_url,
            "release_registry": repo_blob_url(repo_blob_base, release_registry_path),
            "roadmap": repo_blob_url(repo_blob_base, "ROADMAP.md"),
            "technical_roadmap": repo_blob_url(repo_blob_base, "docs/roadmap-tecnico.md"),
            "operational_tracker": repo_blob_url(repo_blob_base, "docs/etl/e2e-scrape-load-tracker.md"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-json", default=str(DEFAULT_STATUS_JSON))
    parser.add_argument("--obstruction-json", default=str(DEFAULT_OBSTRUCTION_JSON))
    parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    parser.add_argument("--origin-verification-json", default=str(DEFAULT_ORIGIN_VERIFICATION_JSON))
    parser.add_argument("--release-registry-json", default=str(DEFAULT_RELEASE_REGISTRY_JSON))
    parser.add_argument(
        "--document-fetch-operations-json",
        default=str(DEFAULT_DOCUMENT_FETCH_OPERATIONS_JSON),
    )
    parser.add_argument("--repo-blob-base", default=DEFAULT_REPO_BLOB_BASE)
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_paths = {
        "status": Path(args.status_json),
        "obstruction": Path(args.obstruction_json),
        "readiness": Path(args.readiness_json),
        "origin": Path(args.origin_verification_json),
        "releases": Path(args.release_registry_json),
        "document_fetch": Path(args.document_fetch_operations_json),
    }
    missing = [f"{key}={path}" for key, path in source_paths.items() if not path.is_file()]
    if missing:
        print("ERROR missing transparency source: " + ", ".join(missing))
        return 2
    generated_at = str(args.generated_at or "").strip() or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if parse_datetime(generated_at) is None:
        print(f"ERROR invalid generated-at: {generated_at}")
        return 2
    try:
        release_registry = read_json(source_paths["releases"])
        releases = build_releases(release_registry, args.repo_blob_base)
        payload = build_payload(
            status=read_json(source_paths["status"]),
            obstruction=read_json(source_paths["obstruction"]),
            readiness=read_json(source_paths["readiness"]),
            origin=read_json(source_paths["origin"]),
            document_fetch=read_json(source_paths["document_fetch"]),
            releases=releases,
            generated_at=generated_at,
            status_path=source_paths["status"].as_posix(),
            obstruction_path=source_paths["obstruction"].as_posix(),
            readiness_path=source_paths["readiness"].as_posix(),
            origin_path=source_paths["origin"].as_posix(),
            document_fetch_path=source_paths["document_fetch"].as_posix(),
            release_registry_path=source_paths["releases"].as_posix(),
            repo_blob_base=args.repo_blob_base,
        )
        atomic_write_json(Path(args.out), payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR transparency export: {exc}")
        return 2
    print(
        "OK transparency dashboard snapshot -> "
        f"{args.out} (metrics={len(payload['metrics'])} releases={len(payload['recent_changes'])} "
        f"snapshot_rows={payload['published_snapshot']['rows_total']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
