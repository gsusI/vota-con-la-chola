#!/usr/bin/env python3
"""Validate the public transparency dashboard feed independently."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


HEX_64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_FRESHNESS = {"fresh", "aging", "stale", "future", "unknown"}
ECONOMICS_OPTIONAL_BENCHMARK_CHECKS = {
    "native_cold_output_benchmark_available",
    "ocr_cold_output_benchmark_available",
}
ECONOMICS_REQUIRED_CHECKS = {
    "official_real_documents_only",
    "synthetic_or_mock_records_absent",
    "public_domain_personal_information_retained",
    "native_current_full_physical_run_complete",
    "ocr_current_full_physical_run_complete",
    "acquisition_queue_reconciled",
    "fresh_acquisition_physical_run_complete",
    "monetary_cost_not_fabricated",
}
REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ECONOMICS_SOURCE_PATH = Path(
    "ui/site/public/transparency/data/document-factory-economics.json"
)
EXPECTED_ECONOMICS_SOURCE_URL = "/transparency/data/document-factory-economics.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bound_economics_source(
    source_ref: Any,
) -> tuple[Path | None, dict[str, Any] | None, str | None]:
    raw = str(source_ref or "").strip()
    expected = EXPECTED_ECONOMICS_SOURCE_PATH.as_posix()
    if raw != expected:
        return None, None, f"document economics source_path must be {expected}"
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        return None, None, "document economics source_path is unsafe"
    candidate = (REPO_ROOT / relative).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None, None, "document economics source_path escapes repository"
    if not candidate.is_file():
        return None, None, "document economics source artifact is missing"
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, None, f"document economics source artifact is invalid: {exc}"
    if not isinstance(payload, dict):
        return None, None, "document economics source artifact must be an object"
    return candidate, payload, None


def parse_iso(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def is_link(value: Any) -> bool:
    raw = str(value or "").strip()
    return raw.startswith("/") or raw.startswith("https://")


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


def validate(path: Path, max_bytes: int) -> dict[str, Any]:
    errors: list[str] = []
    size = path.stat().st_size if path.is_file() else 0
    if not path.is_file():
        return {"status": "error", "checks": {"file_size_bytes": 0}, "errors": [f"missing feed: {path}"]}
    if size > max_bytes:
        errors.append(f"feed exceeds max bytes: {size} > {max_bytes}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "error", "checks": {"file_size_bytes": size}, "errors": [f"invalid JSON: {exc}"]}

    meta = payload.get("meta") or {}
    policy = payload.get("policy") or {}
    if meta.get("schema_version") != "transparency_dashboard_v1":
        errors.append("schema_version must be transparency_dashboard_v1")
    if not parse_iso(meta.get("generated_at")):
        errors.append("meta.generated_at must be ISO-8601")
    expected_policy = {
        "synthetic_or_mock_records": "forbidden",
        "placeholder_releases": "forbidden",
        "public_domain_personal_information": "retained",
        "metric_trace_required": True,
    }
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            errors.append(f"policy.{key} must be {expected!r}")

    metrics = payload.get("metrics") or []
    metric_ids: set[str] = set()
    for index, metric in enumerate(metrics):
        metric_id = str(metric.get("id") or "").strip()
        if not metric_id or metric_id in metric_ids:
            errors.append(f"metrics[{index}].id missing or duplicate")
        metric_ids.add(metric_id)
        if not isinstance(metric.get("value"), int) or int(metric.get("value") or 0) < 0:
            errors.append(f"metrics[{index}].value must be a non-negative integer")
        if not str(metric.get("source_path") or "").strip():
            errors.append(f"metrics[{index}].source_path missing")
        if not is_link(metric.get("source_url")):
            errors.append(f"metrics[{index}].source_url missing or invalid")
    required_metric_ids = {
        "sources_ok",
        "sources_degraded",
        "sources_not_run",
        "open_obstructions",
        "obstruction_evidence",
        "validated_real_corpora",
        "real_million_scale_lanes",
        "promoted_lanes",
        "published_snapshot_rows",
        "published_snapshot_files",
        "document_fetch_official_urls",
        "document_fetch_terminal",
        "document_fetch_unfinished",
        "document_native_objects_measured",
        "document_ocr_pages_measured",
        "document_acquisition_objects_measured",
        "document_acquisition_requests_measured",
        "document_acquisition_wall_ms_per_1000",
        "document_native_wall_ms_per_1000",
        "document_ocr_cpu_ms_per_1000",
    }
    missing_metrics = sorted(required_metric_ids - metric_ids)
    if missing_metrics:
        errors.append("missing metrics: " + ", ".join(missing_metrics))

    source_health = payload.get("source_health") or {}
    source_summary = source_health.get("summary") or {}
    state_total = sum(int(source_summary.get(key) or 0) for key in ("ok", "degraded", "not_run", "partial", "error", "running", "unknown"))
    if state_total != int(source_summary.get("present") or 0):
        errors.append("source health states do not reconcile to present")
    if int(source_summary.get("present") or 0) + int(source_summary.get("missing") or 0) != int(source_summary.get("desired") or 0):
        errors.append("source present + missing does not reconcile to desired")
    source_freshness = source_health.get("freshness") or {}
    if source_freshness.get("tier") not in ALLOWED_FRESHNESS:
        errors.append("source_health.freshness.tier invalid")
    if not HEX_64.fullmatch(str(source_health.get("source_sha256") or "")):
        errors.append("source_health.source_sha256 invalid")

    obstruction = payload.get("obstruction") or {}
    if int(obstruction.get("open_incidents_total") or 0) <= 0:
        errors.append("obstruction requires at least one current real incident")
    if int(obstruction.get("blocked_sources_total") or 0) <= 0:
        errors.append("obstruction requires at least one affected source")
    if int(obstruction.get("evidence_files_total") or 0) <= 0:
        errors.append("obstruction requires public evidence files")
    for key in ("source_sha256", "evidence_manifest_sha256"):
        if not HEX_64.fullmatch(str(obstruction.get(key) or "")):
            errors.append(f"obstruction.{key} invalid")

    readiness = payload.get("scale_readiness") or {}
    readiness_summary = readiness.get("summary") or {}
    if int(readiness_summary.get("validated_real_corpora") or 0) > int(readiness_summary.get("registered_real_corpora") or 0):
        errors.append("validated real corpora exceeds registered corpora")
    if int(readiness_summary.get("promoted_lanes") or 0) > int(readiness_summary.get("real_million_scale_lanes") or 0):
        errors.append("promoted lanes exceeds million-scale lanes")
    if not HEX_64.fullmatch(str(readiness.get("source_sha256") or "")):
        errors.append("scale_readiness.source_sha256 invalid")

    snapshot = payload.get("published_snapshot") or {}
    corpora = snapshot.get("corpora") or []
    if not snapshot.get("verification_passed"):
        errors.append("published snapshot verification must pass")
    if not HEX_64.fullmatch(str(snapshot.get("release_id") or "")):
        errors.append("published snapshot release_id must be a SHA-256")
    if int(snapshot.get("corpora_total") or 0) != len(corpora):
        errors.append("published snapshot corpora_total mismatch")
    if int(snapshot.get("rows_total") or 0) != sum(int(item.get("rows") or 0) for item in corpora):
        errors.append("published snapshot rows_total mismatch")
    if int(snapshot.get("data_files_total") or 0) != sum(int(item.get("files") or 0) for item in corpora):
        errors.append("published snapshot data_files_total mismatch")
    if int(snapshot.get("data_bytes_total") or 0) != sum(int(item.get("bytes") or 0) for item in corpora):
        errors.append("published snapshot data_bytes_total mismatch")
    if not is_link(snapshot.get("pointer_url")) or not is_link(snapshot.get("manifest_url")):
        errors.append("published snapshot pointer/manifest URL missing")
    if snapshot.get("metadata_freshness") is False and not snapshot.get("warnings"):
        errors.append("metadata drift must expose warnings")
    if (snapshot.get("freshness") or {}).get("tier") not in ALLOWED_FRESHNESS:
        errors.append("published_snapshot.freshness.tier invalid")

    document_fetch = payload.get("document_fetch") or {}
    document_queue = document_fetch.get("queue") or {}
    document_summary = document_fetch.get("documents") or {}
    document_integrity = document_fetch.get("integrity") or {}
    document_claim = document_fetch.get("scale_claim") or {}
    document_states = document_queue.get("state_counts") or {}
    document_items = int(document_queue.get("items_total") or 0)
    document_terminal = int(document_queue.get("terminal_total") or 0)
    document_unfinished = int(document_queue.get("unfinished_total") or 0)
    if document_items <= 0:
        errors.append("document fetch requires real official queue items")
    if document_terminal + document_unfinished != document_items:
        errors.append("document fetch terminal + unfinished does not reconcile")
    if document_terminal != int(document_states.get("succeeded") or 0) + int(
        document_states.get("dead") or 0
    ):
        errors.append("document fetch terminal states do not reconcile")
    if document_unfinished != int(document_states.get("pending") or 0) + int(
        document_states.get("leased") or 0
    ):
        errors.append("document fetch unfinished states do not reconcile")
    if int(document_summary.get("official_urls_total") or 0) != document_items:
        errors.append("official document URLs do not reconcile to queue items")
    if int(document_summary.get("fetched_succeeded_total") or 0) != int(
        document_states.get("succeeded") or 0
    ):
        errors.append("document fetch successes do not reconcile")
    if int(document_integrity.get("orphan_partial_files_total") or 0) != 0:
        errors.append("document fetch has orphan partial files")
    if document_integrity.get("official_host_allowlist_passed") is not True:
        errors.append("document fetch official host allowlist must pass")
    if document_claim.get("one_million_documents_processed") != (
        document_terminal >= 1_000_000
    ):
        errors.append("document one-million claim is unsupported")
    if document_claim.get("promoted_for_unbounded_operation") is not False:
        errors.append("document fetch unbounded promotion is unsupported")
    if not HEX_64.fullmatch(str(document_fetch.get("source_sha256") or "")):
        errors.append("document_fetch.source_sha256 invalid")
    if not is_link(document_fetch.get("source_url")):
        errors.append("document_fetch.source_url missing")

    economics = payload.get("document_factory_economics") or {}
    acquisition_economics = economics.get("acquisition") or {}
    native_economics = economics.get("native_extraction") or {}
    ocr_economics = economics.get("page_ocr") or {}
    money = economics.get("monetary_cost") or {}
    economics_claim = economics.get("scale_claim") or {}
    if economics.get("status") != "partial_measured_local":
        errors.append("document economics must preserve partial local status")
    if int(native_economics.get("distinct_content_objects") or 0) <= 100_000:
        errors.append("document economics lacks the real 100k native cohort")
    acquisition_documents = int(
        acquisition_economics.get("documents_succeeded") or 0
    )
    if acquisition_documents < 1_000:
        errors.append(
            "document economics lacks a fresh real acquisition cohort of at least 1,000 objects"
        )
    if (
        int(acquisition_economics.get("network_requests_started") or 0)
        < acquisition_documents
    ):
        errors.append("document economics lacks exact fresh request telemetry")
    if int(acquisition_economics.get("failures") or 0) != 0:
        errors.append("document fresh acquisition cohort contains failures")
    if (
        acquisition_economics.get("measurement_status")
        != "cold_physical_real_multihost_cohort"
    ):
        errors.append("document fresh acquisition status mismatch")
    if acquisition_economics.get("official_hosts") != [
        "www.boe.es",
        "www.parlamentodeandalucia.es",
    ]:
        errors.append("document fresh acquisition host set mismatch")
    if acquisition_economics.get("official_revisions_preserved") is not True:
        errors.append("document fresh acquisition revision policy mismatch")
    if int(ocr_economics.get("candidate_pages") or 0) <= 0:
        errors.append("document economics lacks real OCR pages")
    if int(native_economics.get("failures") or 0) != 0:
        errors.append("document native physical cohort contains failures")
    if int(ocr_economics.get("failures") or 0) != 0:
        errors.append("document OCR physical cohort contains failures")
    if money.get("measurement_status") != "unknown_not_measured":
        errors.append("document monetary cost must remain explicitly unknown")
    for key in (
        "currency",
        "actual_amount",
        "cost_per_1000_documents",
        "cost_per_1000_ocr_pages",
    ):
        if money.get(key) is not None:
            errors.append(f"unmeasured document monetary field {key} must be null")
    if economics_claim.get("one_million_documents_processed") is not False:
        errors.append("document economics makes unsupported million claim")
    if economics_claim.get("promoted_for_one_million_operation") is not False:
        errors.append("document economics makes unsupported promotion claim")
    economics_checks = economics.get("checks") or {}
    if not isinstance(economics_checks, dict) or not economics_checks:
        errors.append("document economics checks missing")
    else:
        missing_economics_checks = sorted(
            (ECONOMICS_REQUIRED_CHECKS | ECONOMICS_OPTIONAL_BENCHMARK_CHECKS)
            - economics_checks.keys()
        )
        if missing_economics_checks:
            errors.append(
                "document economics checks missing: "
                + ", ".join(missing_economics_checks)
            )
        for key in sorted(ECONOMICS_REQUIRED_CHECKS):
            if economics_checks.get(key) is not True:
                errors.append(f"document economics integrity check failed: {key}")
        for key in sorted(ECONOMICS_OPTIONAL_BENCHMARK_CHECKS):
            if not isinstance(economics_checks.get(key), bool):
                errors.append(f"document economics benchmark check invalid: {key}")
    source_path, source_economics, source_error = load_bound_economics_source(
        economics.get("source_path")
    )
    if source_error:
        errors.append(source_error)
    elif source_path is not None and source_economics is not None:
        expected_source_sha256 = sha256_file(source_path)
        if economics.get("source_sha256") != expected_source_sha256:
            errors.append("document_factory_economics.source_sha256 mismatch")
        expected_projection = {
            "status": str((source_economics.get("meta") or {}).get("status") or ""),
            "acquisition": source_economics.get("acquisition") or {},
            "historical_acquisition_queue": source_economics.get(
                "historical_acquisition_queue"
            )
            or {},
            "native_extraction": source_economics.get("native_extraction") or {},
            "page_ocr": source_economics.get("page_ocr") or {},
            "storage": source_economics.get("storage") or {},
            "monetary_cost": source_economics.get("monetary_cost") or {},
            "measurement_gaps": source_economics.get("measurement_gaps") or [],
            "checks": source_economics.get("checks") or {},
            "scale_claim": source_economics.get("scale_claim") or {},
        }
        observed_projection = {
            key: economics.get(key) for key in expected_projection
        }
        if observed_projection != expected_projection:
            errors.append("document economics projection does not match bound source")
    if economics.get("source_url") != EXPECTED_ECONOMICS_SOURCE_URL:
        errors.append("document_factory_economics.source_url mismatch")

    releases = payload.get("recent_changes") or []
    release_ids: set[str] = set()
    dates: list[str] = []
    for index, release in enumerate(releases):
        release_id = str(release.get("id") or "").strip()
        if not release_id or release_id in release_ids:
            errors.append(f"recent_changes[{index}].id missing or duplicate")
        release_ids.add(release_id)
        release_date = str(release.get("date") or "")
        dates.append(release_date)
        if not parse_iso(release_date):
            errors.append(f"recent_changes[{index}].date invalid")
        if not release.get("public_routes") or any(not str(route).startswith("/") for route in release.get("public_routes") or []):
            errors.append(f"recent_changes[{index}].public_routes invalid")
        note = release.get("note") or {}
        if not is_link(note.get("url")) or not HEX_64.fullmatch(str(note.get("sha256") or "")):
            errors.append(f"recent_changes[{index}].note trace invalid")
        if not release.get("evidence"):
            errors.append(f"recent_changes[{index}].evidence empty")
        for evidence_index, evidence in enumerate(release.get("evidence") or []):
            if not is_link(evidence.get("url")) or not HEX_64.fullmatch(str(evidence.get("sha256") or "")):
                errors.append(f"recent_changes[{index}].evidence[{evidence_index}] trace invalid")
    if dates != sorted(dates, reverse=True):
        errors.append("recent_changes must be newest first")
    headline = payload.get("headline") or {}
    if releases and headline.get("latest_release_id") != releases[0].get("id"):
        errors.append("headline latest_release_id mismatch")
    if snapshot.get("release_id") != headline.get("latest_snapshot_release_id"):
        errors.append("headline latest_snapshot_release_id mismatch")

    metric_values = {metric.get("id"): metric.get("value") for metric in metrics}
    expected_values = {
        "sources_ok": int(source_summary.get("ok") or 0),
        "sources_degraded": int(source_summary.get("degraded") or 0),
        "sources_not_run": int(source_summary.get("not_run") or 0),
        "open_obstructions": int(obstruction.get("open_incidents_total") or 0),
        "obstruction_evidence": int(obstruction.get("evidence_files_total") or 0),
        "validated_real_corpora": int(readiness_summary.get("validated_real_corpora") or 0),
        "real_million_scale_lanes": int(readiness_summary.get("real_million_scale_lanes") or 0),
        "promoted_lanes": int(readiness_summary.get("promoted_lanes") or 0),
        "published_snapshot_rows": int(snapshot.get("rows_total") or 0),
        "published_snapshot_files": int(snapshot.get("data_files_total") or 0),
        "document_fetch_official_urls": int(
            document_summary.get("official_urls_total") or 0
        ),
        "document_fetch_terminal": document_terminal,
        "document_fetch_unfinished": document_unfinished,
        "document_native_objects_measured": int(
            native_economics.get("distinct_content_objects") or 0
        ),
        "document_ocr_pages_measured": int(
            ocr_economics.get("candidate_pages") or 0
        ),
        "document_acquisition_objects_measured": int(
            acquisition_economics.get("documents_succeeded") or 0
        ),
        "document_acquisition_requests_measured": int(
            acquisition_economics.get("network_requests_started") or 0
        ),
        "document_acquisition_wall_ms_per_1000": round(
            float(
                (acquisition_economics.get("per_1000_succeeded") or {}).get(
                    "elapsed_seconds"
                )
                or 0
            )
            * 1000
        ),
        "document_native_wall_ms_per_1000": round(
            float(
                (native_economics.get("per_1000_distinct_content_objects") or {}).get(
                    "elapsed_seconds"
                )
                or 0
            )
            * 1000
        ),
        "document_ocr_cpu_ms_per_1000": round(
            float(
                (ocr_economics.get("per_1000_candidate_pages") or {}).get(
                    "cpu_seconds_parent_and_children"
                )
                or 0
            )
            * 1000
        ),
    }
    for metric_id, expected in expected_values.items():
        if metric_values.get(metric_id) != expected:
            errors.append(f"metric {metric_id} does not reconcile to its section")

    return {
        "status": "ok" if not errors else "error",
        "checks": {
            "schema_version": meta.get("schema_version"),
            "file_size_bytes": size,
            "max_bytes": max_bytes,
            "metrics_total": len(metrics),
            "releases_total": len(releases),
            "sources_present": int(source_summary.get("present") or 0),
            "open_incidents_total": int(obstruction.get("open_incidents_total") or 0),
            "published_snapshot_rows": int(snapshot.get("rows_total") or 0),
            "published_snapshot_files": int(snapshot.get("data_files_total") or 0),
            "document_fetch_official_urls": int(
                document_summary.get("official_urls_total") or 0
            ),
            "document_fetch_terminal": document_terminal,
            "document_fetch_unfinished": document_unfinished,
            "document_native_objects_measured": int(
                native_economics.get("distinct_content_objects") or 0
            ),
            "document_ocr_pages_measured": int(
                ocr_economics.get("candidate_pages") or 0
            ),
            "document_acquisition_objects_measured": int(
                acquisition_economics.get("documents_succeeded") or 0
            ),
            "document_acquisition_requests_measured": int(
                acquisition_economics.get("network_requests_started") or 0
            ),
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate(Path(args.path), int(args.max_bytes))
    if args.out:
        atomic_write_json(Path(args.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
