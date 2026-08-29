#!/usr/bin/env python3
"""Publish observed real-document throughput, resource, and cost coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.name


def source_descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": repo_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def document_fetch_descriptor(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    stable = json.loads(json.dumps(payload))
    (stable.get("meta") or {}).pop("generated_at", None)
    encoded = json.dumps(
        stable, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "path": repo_path(path),
        "semantic_sha256": hashlib.sha256(encoded).hexdigest(),
        "volatile_fields_excluded": ["meta.generated_at"],
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def per_1000(value: int | float, denominator: int) -> float:
    if denominator <= 0:
        raise ValueError("per-1,000 denominator must be positive")
    return round(float(value) * 1000.0 / denominator, 6)


def latest_generated_at(payloads: list[dict[str, Any]]) -> str:
    values: list[datetime] = []
    for payload in payloads:
        raw = str(
            payload.get("generated_at")
            or (payload.get("meta") or {}).get("generated_at")
            or ""
        ).strip()
        if not raw:
            continue
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        values.append(parsed.astimezone(timezone.utc))
    if not values:
        raise ValueError("inputs do not expose generated_at")
    return max(values).replace(microsecond=0).isoformat()


def build_payload(
    *,
    inventory_path: Path,
    extraction_path: Path,
    extraction_validation_path: Path,
    ocr_path: Path,
    ocr_validation_path: Path,
    fetch_path: Path,
    acquisition_run_path: Path,
    acquisition_validation_path: Path,
    generated_at: str,
) -> dict[str, Any]:
    inventory = read_json(inventory_path)
    extraction = read_json(extraction_path)
    extraction_validation = read_json(extraction_validation_path)
    ocr = read_json(ocr_path)
    ocr_validation = read_json(ocr_validation_path)
    fetch = read_json(fetch_path)
    acquisition_run = read_json(acquisition_run_path)
    acquisition_validation = read_json(acquisition_validation_path)

    if inventory.get("schema_version") != "real_document_format_inventory_v4":
        raise ValueError("inventory schema mismatch")
    if extraction.get("schema_version") != "real_document_text_extraction_v1":
        raise ValueError("native extraction schema mismatch")
    if (
        extraction_validation.get("schema_version")
        != "real_document_text_validation_v1"
    ):
        raise ValueError("native validation schema mismatch")
    if ocr.get("schema_version") != "real_document_page_ocr_v1":
        raise ValueError("OCR schema mismatch")
    if ocr_validation.get("schema_version") != "real_document_page_ocr_validation_v1":
        raise ValueError("OCR validation schema mismatch")
    if (fetch.get("meta") or {}).get(
        "schema_version"
    ) != "document_fetch_operations_v1":
        raise ValueError("document fetch schema mismatch")
    if acquisition_run.get("schema_version") != "document_fetch_queue_run_v3":
        raise ValueError("fresh acquisition run schema mismatch")
    acquisition_validation_schema = acquisition_validation.get("schema_version")
    if acquisition_validation_schema not in {
        "real_document_fetch_cohort_validation_v1",
        "real_document_fetch_scale_cohort_validation_v2",
    }:
        raise ValueError("fresh acquisition validation schema mismatch")

    inventory_totals = inventory.get("totals") or {}
    extraction_run = extraction.get("run") or {}
    extraction_totals = extraction.get("totals") or {}
    extraction_performance = extraction.get("performance") or {}
    ocr_run = ocr.get("run") or {}
    ocr_totals = ocr.get("totals") or {}
    ocr_performance = ocr.get("performance") or {}
    fetch_queue = fetch.get("queue") or {}
    fetch_documents = fetch.get("documents") or {}
    acquisition_totals = acquisition_run.get("totals") or {}
    acquisition_performance = acquisition_run.get("performance") or {}
    acquisition_checks = acquisition_validation.get("checks") or {}

    extracted_objects = int(extraction_run.get("succeeded") or 0)
    ocr_pages = int(ocr_run.get("succeeded") or 0)
    fetched_documents = int(fetch_documents.get("fetched_succeeded_total") or 0)
    acquisition_documents = int(acquisition_totals.get("succeeded") or 0)
    file_instances = int(inventory_totals.get("files") or 0)
    if (
        min(
            extracted_objects,
            ocr_pages,
            fetched_documents,
            acquisition_documents,
            file_instances,
        )
        <= 0
    ):
        raise ValueError("real observed cohorts must all be non-empty")

    native_failures = int(extraction_run.get("dead") or 0)
    ocr_failures = int(ocr_run.get("dead") or 0)
    fetch_dead = int((fetch_queue.get("state_counts") or {}).get("dead") or 0)
    native_raw_bytes = int(extraction_run.get("raw_bytes_succeeded") or 0)
    native_text_chars = int(extraction_totals.get("native_text_chars") or 0)
    native_text_cas_bytes = int(extraction_totals.get("text_cas_bytes") or 0)
    ocr_text_cas_bytes = int(ocr_totals.get("ocr_text_cas_bytes") or 0)

    checks = {
        "official_real_documents_only": all(
            (payload.get("policy") or {}).get("official_real_documents_only") is True
            for payload in (extraction, ocr, acquisition_validation)
        ),
        "synthetic_or_mock_records_absent": (
            (extraction.get("policy") or {}).get("synthetic_or_mock_records_counted")
            is False
            and (ocr.get("policy") or {}).get("synthetic_or_mock_records_counted")
            is False
            and (fetch.get("policy") or {}).get("synthetic_or_mock_records")
            == "forbidden"
            and (acquisition_validation.get("policy") or {}).get(
                "synthetic_or_mock_records_counted"
            )
            is False
        ),
        "public_domain_personal_information_retained": (
            (extraction.get("policy") or {}).get(
                "official_public_domain_personal_information_retained"
            )
            is True
            and (ocr.get("policy") or {}).get(
                "official_public_domain_personal_information_retained"
            )
            is True
            and (fetch.get("policy") or {}).get("public_domain_personal_information")
            == "retained"
            and (acquisition_validation.get("policy") or {}).get(
                "official_public_domain_personal_information_retained"
            )
            is True
        ),
        "native_physical_run_complete": (
            extraction.get("status") == "ok"
            and extraction_validation.get("status") == "ok"
            and extracted_objects
            == int(extraction_totals.get("distinct_content_objects") or 0)
            and bool(extraction_performance.get("cold_state_and_output"))
        ),
        "ocr_physical_run_complete": (
            ocr.get("status") == "ok"
            and ocr_validation.get("status") == "ok"
            and ocr_pages == int(ocr_totals.get("candidate_pages") or 0)
            and bool(ocr_performance.get("cold_state_and_output"))
        ),
        "acquisition_queue_reconciled": (
            int(fetch_queue.get("items_total") or 0)
            == int(fetch_queue.get("terminal_total") or 0)
            + int(fetch_queue.get("unfinished_total") or 0)
        ),
        "fresh_acquisition_physical_run_complete": (
            acquisition_run.get("status") == "ok"
            and acquisition_validation.get("status") == "ok"
            and acquisition_validation.get("errors") == []
            and int(acquisition_totals.get("claimed") or 0) == acquisition_documents
            and int(acquisition_totals.get("retried") or 0) == 0
            and int(acquisition_totals.get("dead") or 0) == 0
            and int(acquisition_checks.get("fresh_files_rehashed") or 0)
            == acquisition_documents
            and (
                acquisition_checks.get("immutable_byte_hash_parity") is True
                if acquisition_validation_schema
                == "real_document_fetch_cohort_validation_v1"
                else (
                    acquisition_checks.get("prior_capture_byte_hash_integrity")
                    is True
                    and acquisition_checks.get("fresh_source_contract_parity") is True
                    and acquisition_checks.get("fresh_content_hash_self_consistency")
                    is True
                )
            )
        ),
        "monetary_cost_not_fabricated": True,
    }

    return {
        "meta": {
            "schema_version": "document_factory_economics_v1",
            "generated_at": generated_at,
            "status": "partial_measured_local",
            "measurement_basis": "physical_real_official_cohorts",
        },
        "policy": {
            "synthetic_or_mock_records": "forbidden",
            "public_domain_personal_information": "retained",
            "unmeasured_values": "null_not_zero",
            "local_measurements_are_not_provider_forecasts": True,
            "one_million_projection_published": False,
        },
        "inputs": {
            "inventory": source_descriptor(inventory_path),
            "native_extraction": source_descriptor(extraction_path),
            "native_validation": source_descriptor(extraction_validation_path),
            "page_ocr": source_descriptor(ocr_path),
            "page_ocr_validation": source_descriptor(ocr_validation_path),
            "document_fetch_operations": document_fetch_descriptor(fetch_path, fetch),
            "fresh_acquisition_run": source_descriptor(acquisition_run_path),
            "fresh_acquisition_validation": source_descriptor(
                acquisition_validation_path
            ),
        },
        "acquisition": {
            "measurement_status": "cold_physical_real_multihost_cohort",
            "cohort_id": str(acquisition_validation.get("cohort_id") or ""),
            "cohort_semantic_sha256": str(
                acquisition_validation.get("cohort_semantic_sha256") or ""
            ),
            "official_hosts": sorted((acquisition_validation.get("hosts") or {}).keys()),
            "documents_attempted": int(acquisition_totals.get("claimed") or 0),
            "documents_succeeded": acquisition_documents,
            "network_requests_started": int(
                acquisition_performance.get("network_requests_started") or 0
            ),
            "bytes_received": int(acquisition_totals.get("bytes_received") or 0),
            "cpu_seconds": float(acquisition_performance.get("cpu_seconds") or 0),
            "peak_rss_bytes": int(acquisition_performance.get("peak_rss_bytes") or 0),
            "elapsed_seconds": float(
                acquisition_performance.get("elapsed_seconds") or 0
            ),
            "retries": int(acquisition_totals.get("retried") or 0),
            "failures": int(acquisition_checks.get("host_failures") or 0),
            "source_contract_rows": int(
                acquisition_checks.get("source_contract_rows") or 0
            ),
            "content_exact_matches": int(
                (acquisition_validation.get("content_drift") or {}).get(
                    "exact_matches"
                )
                or 0
            ),
            "content_drifted_rows": int(
                (acquisition_validation.get("content_drift") or {}).get(
                    "drifted_rows"
                )
                or 0
            ),
            "official_revisions_preserved": (
                (acquisition_validation.get("policy") or {}).get(
                    "official_content_revisions_preserved_and_measured"
                )
                is True
            ),
            "workers": int(acquisition_run.get("workers") or 0),
            "per_host_workers": int(acquisition_run.get("per_host_workers") or 0),
            "per_host_min_interval_ms": int(
                (acquisition_run.get("host_policy") or {}).get(
                    "per_host_min_interval_ms"
                )
                or 0
            ),
            "per_1000_succeeded": {
                "network_requests_started": per_1000(
                    int(acquisition_performance.get("network_requests_started") or 0),
                    acquisition_documents,
                ),
                "bytes_received": per_1000(
                    int(acquisition_totals.get("bytes_received") or 0),
                    acquisition_documents,
                ),
                "elapsed_seconds": per_1000(
                    float(acquisition_performance.get("elapsed_seconds") or 0),
                    acquisition_documents,
                ),
                "cpu_seconds": per_1000(
                    float(acquisition_performance.get("cpu_seconds") or 0),
                    acquisition_documents,
                ),
                "failures": per_1000(
                    int(acquisition_checks.get("host_failures") or 0),
                    acquisition_documents,
                ),
            },
        },
        "historical_acquisition_queue": {
            "measurement_status": "historical_queue_state",
            "official_urls_total": int(fetch_documents.get("official_urls_total") or 0),
            "documents_succeeded": fetched_documents,
            "terminal_dead": fetch_dead,
            "unfinished": int(fetch_queue.get("unfinished_total") or 0),
            "queue_attempts": int(fetch_queue.get("attempts_total") or 0),
            "bytes_received": int(fetch_documents.get("bytes_received") or 0),
        },
        "native_extraction": {
            "measurement_status": "cold_physical_run",
            "distinct_content_objects": extracted_objects,
            "file_instances": int(extraction_totals.get("file_instances") or 0),
            "failures": native_failures,
            "raw_content_bytes_processed": native_raw_bytes,
            "native_text_chars": native_text_chars,
            "native_text_cas_bytes": native_text_cas_bytes,
            "elapsed_seconds": float(
                extraction_performance.get("elapsed_seconds") or 0
            ),
            "cpu_seconds": float(extraction_performance.get("cpu_seconds") or 0),
            "peak_rss_bytes_self": int(
                extraction_performance.get("peak_rss_bytes_self") or 0
            ),
            "workers": int(extraction_performance.get("workers") or 0),
            "per_1000_distinct_content_objects": {
                "raw_content_bytes_processed": per_1000(
                    native_raw_bytes, extracted_objects
                ),
                "native_text_chars": per_1000(native_text_chars, extracted_objects),
                "native_text_cas_bytes": per_1000(
                    native_text_cas_bytes, extracted_objects
                ),
                "elapsed_seconds": per_1000(
                    float(extraction_performance.get("elapsed_seconds") or 0),
                    extracted_objects,
                ),
                "cpu_seconds": per_1000(
                    float(extraction_performance.get("cpu_seconds") or 0),
                    extracted_objects,
                ),
                "failures": per_1000(native_failures, extracted_objects),
            },
        },
        "page_ocr": {
            "measurement_status": "cold_physical_run",
            "documents": int(ocr_totals.get("documents") or 0),
            "candidate_pages": ocr_pages,
            "failures": ocr_failures,
            "ocr_text_chars": int(ocr_totals.get("ocr_text_chars") or 0),
            "ocr_text_cas_bytes": ocr_text_cas_bytes,
            "elapsed_seconds": float(ocr_performance.get("elapsed_seconds") or 0),
            "elapsed_worker_seconds": float(
                ocr_totals.get("elapsed_worker_seconds") or 0
            ),
            "cpu_seconds_parent_and_children": float(
                ocr_performance.get("cpu_seconds") or 0
            ),
            "peak_rss_bytes_self": int(ocr_performance.get("peak_rss_bytes_self") or 0),
            "peak_rss_bytes_child_max": int(
                ocr_performance.get("peak_rss_bytes_child_max") or 0
            ),
            "workers": int(ocr_performance.get("workers") or 0),
            "per_1000_candidate_pages": {
                "ocr_text_chars": per_1000(
                    int(ocr_totals.get("ocr_text_chars") or 0), ocr_pages
                ),
                "ocr_text_cas_bytes": per_1000(ocr_text_cas_bytes, ocr_pages),
                "elapsed_seconds": per_1000(
                    float(ocr_performance.get("elapsed_seconds") or 0), ocr_pages
                ),
                "elapsed_worker_seconds": per_1000(
                    float(ocr_totals.get("elapsed_worker_seconds") or 0), ocr_pages
                ),
                "cpu_seconds_parent_and_children": per_1000(
                    float(ocr_performance.get("cpu_seconds") or 0), ocr_pages
                ),
                "failures": per_1000(ocr_failures, ocr_pages),
            },
        },
        "storage": {
            "file_instances": file_instances,
            "raw_document_bytes": int(inventory_totals.get("bytes") or 0),
            "native_text_cas_bytes": native_text_cas_bytes,
            "ocr_candidate_pages": ocr_pages,
            "ocr_text_cas_bytes": ocr_text_cas_bytes,
            "per_1000_file_instances": {
                "raw_document_bytes": per_1000(
                    int(inventory_totals.get("bytes") or 0), file_instances
                ),
                "native_text_cas_bytes": per_1000(
                    native_text_cas_bytes, file_instances
                ),
            },
            "per_1000_ocr_candidate_pages": {
                "ocr_text_cas_bytes": per_1000(ocr_text_cas_bytes, ocr_pages)
            },
        },
        "monetary_cost": {
            "measurement_status": "unknown_not_measured",
            "currency": None,
            "actual_amount": None,
            "cost_per_1000_documents": None,
            "cost_per_1000_ocr_pages": None,
            "provider_rates_present": False,
            "invoice_or_meter_present": False,
            "reason": (
                "No approved provider rate, invoice, energy meter, or labor ledger is "
                "bound to these physical local runs; zero would be fabricated."
            ),
        },
        "measurement_gaps": [
            "No actual monetary meter or provider invoice is bound to the measured cohorts.",
            (
                "Fresh acquisition telemetry covers 100 BOE objects on one official host, "
                "not yet 1k/10k/100k cohorts across representative hosts and formats."
            ),
            (
                "The 100k stored corpus is not yet representative across every source, "
                "format, language, scan quality, and host."
            ),
            "Human OCR quality review remains incomplete at 0/40 decisions.",
        ],
        "checks": checks,
        "scale_claim": {
            "capacity_class": str(inventory.get("capacity_class") or ""),
            "physical_native_objects_measured": extracted_objects,
            "physical_ocr_pages_measured": ocr_pages,
            "one_million_documents_processed": extracted_objects >= 1_000_000,
            "promoted_for_one_million_operation": False,
            "next_gate": (
                "scale exact request telemetry through representative 1000_10000_100000 "
                "host cohorts and bind actual monetary cost before one million"
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--native-extraction", required=True)
    parser.add_argument("--native-validation", required=True)
    parser.add_argument("--page-ocr", required=True)
    parser.add_argument("--page-ocr-validation", required=True)
    parser.add_argument("--document-fetch-operations", required=True)
    parser.add_argument("--fresh-acquisition-run", required=True)
    parser.add_argument("--fresh-acquisition-validation", required=True)
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--evidence-out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = [
        Path(args.inventory),
        Path(args.native_extraction),
        Path(args.native_validation),
        Path(args.page_ocr),
        Path(args.page_ocr_validation),
        Path(args.document_fetch_operations),
        Path(args.fresh_acquisition_run),
        Path(args.fresh_acquisition_validation),
    ]
    try:
        payloads = [read_json(path) for path in paths]
        generated_at = str(args.generated_at or "").strip() or latest_generated_at(
            payloads[:5]
        )
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        payload = build_payload(
            inventory_path=paths[0],
            extraction_path=paths[1],
            extraction_validation_path=paths[2],
            ocr_path=paths[3],
            ocr_validation_path=paths[4],
            fetch_path=paths[5],
            acquisition_run_path=paths[6],
            acquisition_validation_path=paths[7],
            generated_at=generated_at,
        )
        atomic_write_json(Path(args.out), payload)
        if str(args.evidence_out or "").strip():
            atomic_write_json(Path(args.evidence_out), payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR document-factory economics export: {exc}")
        return 2
    print(
        "OK document-factory economics -> "
        f"{args.out} (native={payload['native_extraction']['distinct_content_objects']} "
        f"ocr_pages={payload['page_ocr']['candidate_pages']} "
        f"monetary={payload['monetary_cost']['measurement_status']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
