#!/usr/bin/env python3
"""Independently validate public real-document economics and per-1,000 math."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


HEX_64 = re.compile(r"^[0-9a-f]{64}$")
INVENTORY_SCHEMA_VERSION = "real_document_format_inventory_v7_xlsx_contract_bound"
NATIVE_EXTRACTION_ALGORITHM_VERSION = (
    "document_extraction_v4_pdf_markup_xlsx_phonetic_bounded"
)
NATIVE_CURRENT_FULL_CHECK = "native_current_full_physical_run_complete"
NATIVE_COLD_OUTPUT_CHECK = "native_cold_output_benchmark_available"
OCR_CURRENT_FULL_CHECK = "ocr_current_full_physical_run_complete"
OCR_COLD_OUTPUT_CHECK = "ocr_cold_output_benchmark_available"
COLD_OUTPUT_GAP = (
    "Current full real native extraction completed against a pre-existing output "
    "root; measured telemetry is valid for this warm-output run, but no current "
    "cold-output benchmark is available."
)
COLD_OUTPUT_NEXT_GATE = (
    "repeat current full real native extraction with empty state and output roots "
    "to establish a cold-output benchmark"
)
OCR_COLD_OUTPUT_GAP = (
    "Current full real page OCR completed against a pre-existing output root; "
    "measured telemetry is valid for this warm-output run, but no current OCR "
    "cold-output benchmark is available."
)
OCR_COLD_OUTPUT_NEXT_GATE = (
    "repeat current full real page OCR with empty state and output roots to "
    "establish a cold-output benchmark"
)
REQUIRED_INTEGRITY_CHECKS = frozenset(
    {
        "official_real_documents_only",
        "synthetic_or_mock_records_absent",
        "public_domain_personal_information_retained",
        NATIVE_CURRENT_FULL_CHECK,
        OCR_CURRENT_FULL_CHECK,
        "acquisition_queue_reconciled",
        "fresh_acquisition_physical_run_complete",
        "monetary_cost_not_fabricated",
    }
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


def input_descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
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
        "path": path.as_posix(),
        "semantic_sha256": hashlib.sha256(encoded).hexdigest(),
        "volatile_fields_excluded": ["meta.generated_at"],
    }


def scaled(value: int | float, denominator: int) -> float:
    return round(float(value) * 1000.0 / denominator, 6)


def close(actual: Any, expected: float) -> bool:
    return (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and math.isclose(float(actual), expected, rel_tol=0, abs_tol=0.000001)
    )


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


def validate(
    *,
    artifact_path: Path,
    evidence_path: Path,
    inventory_path: Path,
    extraction_path: Path,
    extraction_validation_path: Path,
    ocr_path: Path,
    ocr_validation_path: Path,
    fetch_path: Path,
    acquisition_run_path: Path,
    acquisition_validation_path: Path,
    max_bytes: int,
) -> dict[str, Any]:
    errors: list[str] = []
    size = artifact_path.stat().st_size if artifact_path.is_file() else 0
    if not artifact_path.is_file():
        return {
            "status": "error",
            "checks": {"file_size_bytes": 0},
            "errors": ["public artifact missing"],
        }
    if size > max_bytes:
        errors.append(f"artifact exceeds max bytes: {size} > {max_bytes}")
    try:
        artifact = read_json(artifact_path)
        evidence = read_json(evidence_path)
        inventory = read_json(inventory_path)
        extraction = read_json(extraction_path)
        extraction_validation = read_json(extraction_validation_path)
        ocr = read_json(ocr_path)
        ocr_validation = read_json(ocr_validation_path)
        fetch = read_json(fetch_path)
        acquisition_run = read_json(acquisition_run_path)
        acquisition_validation = read_json(acquisition_validation_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "error",
            "checks": {"file_size_bytes": size},
            "errors": [str(exc)],
        }

    if artifact != evidence:
        errors.append("public artifact and evidence copy differ")
    meta = artifact.get("meta") or {}
    policy = artifact.get("policy") or {}
    try:
        datetime.fromisoformat(
            str(meta.get("generated_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        errors.append("meta.generated_at is invalid")
    if meta.get("schema_version") != "document_factory_economics_v1":
        errors.append("schema_version mismatch")
    if meta.get("status") != "partial_measured_local":
        errors.append("status must preserve the partial local-only boundary")
    expected_policy = {
        "synthetic_or_mock_records": "forbidden",
        "public_domain_personal_information": "retained",
        "unmeasured_values": "null_not_zero",
        "local_measurements_are_not_provider_forecasts": True,
        "one_million_projection_published": False,
    }
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            errors.append(f"policy.{key} mismatch")
    if (
        inventory.get("schema_version") != INVENTORY_SCHEMA_VERSION
        or inventory.get("status") != "ok"
    ):
        errors.append("inventory schema or status mismatch")
    if (
        extraction.get("schema_version") != "real_document_text_extraction_v1"
        or extraction.get("extraction_algorithm_version")
        != NATIVE_EXTRACTION_ALGORITHM_VERSION
    ):
        errors.append("native extraction schema or algorithm mismatch")
    if (
        extraction_validation.get("schema_version")
        != "real_document_text_validation_v2"
        or extraction_validation.get("extraction_algorithm_version")
        != NATIVE_EXTRACTION_ALGORITHM_VERSION
    ):
        errors.append("native validation schema or algorithm mismatch")
    if acquisition_run.get("schema_version") != "document_fetch_queue_run_v3":
        errors.append("fresh acquisition run schema mismatch")
    if acquisition_run.get("status") != "ok":
        errors.append("fresh acquisition run status mismatch")
    acquisition_validation_schema = acquisition_validation.get("schema_version")
    if (
        acquisition_validation_schema
        not in {
            "real_document_fetch_cohort_validation_v1",
            "real_document_fetch_scale_cohort_validation_v2",
            "real_document_fetch_scale_cohort_validation_v3",
        }
        or acquisition_validation.get("status") != "ok"
        or acquisition_validation.get("errors") != []
    ):
        errors.append("fresh acquisition independent validation failed")

    input_paths = {
        "inventory": inventory_path,
        "native_extraction": extraction_path,
        "native_validation": extraction_validation_path,
        "page_ocr": ocr_path,
        "page_ocr_validation": ocr_validation_path,
        "document_fetch_operations": fetch_path,
        "fresh_acquisition_run": acquisition_run_path,
        "fresh_acquisition_validation": acquisition_validation_path,
    }
    inputs = artifact.get("inputs") or {}
    for key, path in input_paths.items():
        descriptor = inputs.get(key) or {}
        if key == "document_fetch_operations":
            expected_descriptor = document_fetch_descriptor(path, fetch)
            if descriptor != expected_descriptor:
                errors.append("inputs.document_fetch_operations semantic hash mismatch")
            continue
        if descriptor.get("bytes") != path.stat().st_size:
            errors.append(f"inputs.{key}.bytes mismatch")
        if descriptor.get("sha256") != sha256_file(path):
            errors.append(f"inputs.{key}.sha256 mismatch")
        if not HEX_64.fullmatch(str(descriptor.get("sha256") or "")):
            errors.append(f"inputs.{key}.sha256 invalid")
        published_path = Path(str(descriptor.get("path") or ""))
        if published_path.is_absolute() or ".." in published_path.parts:
            errors.append(f"inputs.{key}.path is not repository-safe")

    extraction_run = extraction.get("run") or {}
    extraction_totals = extraction.get("totals") or {}
    extraction_perf = extraction.get("performance") or {}
    extraction_validation_totals = extraction_validation.get("totals") or {}
    extraction_validation_checks = extraction_validation.get("checks") or {}
    ocr_run = ocr.get("run") or {}
    ocr_totals = ocr.get("totals") or {}
    ocr_perf = ocr.get("performance") or {}
    ocr_validation_totals = ocr_validation.get("totals") or {}
    ocr_validation_checks = ocr_validation.get("checks") or {}
    fetch_queue = fetch.get("queue") or {}
    fetch_docs = fetch.get("documents") or {}
    inventory_totals = inventory.get("totals") or {}
    acquisition_run_totals = acquisition_run.get("totals") or {}
    acquisition_run_perf = acquisition_run.get("performance") or {}
    acquisition_validation_checks = acquisition_validation.get("checks") or {}
    acquisition_validation_inputs = acquisition_validation.get("inputs") or {}
    if (acquisition_validation_inputs.get("run_report") or {}).get(
        "sha256"
    ) != sha256_file(acquisition_run_path):
        errors.append("fresh acquisition validation run input drifted")

    native = artifact.get("native_extraction") or {}
    native_denominator = int(extraction_run.get("succeeded") or 0)
    inventory_file_instances = int(inventory_totals.get("files") or 0)
    inventory_distinct_objects = int(
        inventory_totals.get("distinct_content_objects") or 0
    )
    extraction_file_instances = int(extraction_totals.get("file_instances") or 0)
    extraction_distinct_objects = int(
        extraction_totals.get("distinct_content_objects") or 0
    )
    validation_file_instances = int(
        extraction_validation_totals.get("file_instances") or 0
    )
    validation_distinct_objects = int(
        extraction_validation_totals.get("distinct_content_objects") or 0
    )
    native_counts_reconcile = (
        inventory_file_instances
        == extraction_file_instances
        == validation_file_instances
        and inventory_distinct_objects
        == extraction_distinct_objects
        == validation_distinct_objects
        == native_denominator
        == int(extraction_run.get("claimed") or 0)
    )
    if not native_counts_reconcile:
        errors.append(
            "inventory, extraction, and native validation file/distinct counts "
            "do not reconcile"
        )
    native_current_full_physical_run_complete = (
        native_counts_reconcile
        and extraction.get("status") == "ok"
        and extraction_validation.get("status") == "ok"
        and bool(extraction_validation_checks)
        and all(value is True for value in extraction_validation_checks.values())
        and int(extraction_run.get("dead") or 0) == 0
        and int(extraction_run.get("retried") or 0) == 0
    )
    if not native_current_full_physical_run_complete:
        errors.append("current full native physical run is incomplete")
    native_cold_output_benchmark_available = (
        extraction_perf.get("cold_state_and_output") is True
    )
    expected_native_measurement_status = (
        "cold_physical_run"
        if native_cold_output_benchmark_available
        else "current_full_real_warm_output_run"
    )
    if native.get("measurement_status") != expected_native_measurement_status:
        errors.append("native extraction measurement status mismatch")
    if (
        native.get("cold_state_and_output")
        is not native_cold_output_benchmark_available
    ):
        errors.append("native cold-state telemetry mismatch")
    native_expected = {
        "raw_content_bytes_processed": int(
            extraction_run.get("raw_bytes_succeeded") or 0
        ),
        "native_text_chars": int(extraction_totals.get("native_text_chars") or 0),
        "native_text_cas_bytes": int(extraction_totals.get("text_cas_bytes") or 0),
        "elapsed_seconds": float(extraction_perf.get("elapsed_seconds") or 0),
        "cpu_seconds": float(extraction_perf.get("cpu_seconds") or 0),
        "failures": int(extraction_run.get("dead") or 0),
    }
    if (
        native_denominator <= 0
        or native.get("distinct_content_objects") != native_denominator
    ):
        errors.append("native physical denominator mismatch")
    native_per_1000 = native.get("per_1000_distinct_content_objects") or {}
    for key, value in native_expected.items():
        if native.get(key) != value:
            errors.append(f"native_extraction.{key} mismatch")
        if native_denominator > 0 and not close(
            native_per_1000.get(key), scaled(value, native_denominator)
        ):
            errors.append(f"native per-1,000 {key} mismatch")
    if native.get("peak_rss_bytes_self") != int(
        extraction_perf.get("peak_rss_bytes_self") or 0
    ):
        errors.append("native peak RSS mismatch")
    if extraction.get("status") != "ok" or extraction_validation.get("status") != "ok":
        errors.append("native producer or independent validation is not ok")

    page_ocr = artifact.get("page_ocr") or {}
    ocr_denominator = int(ocr_run.get("succeeded") or 0)
    ocr_current_full_physical_run_complete = (
        ocr.get("status") == "ok"
        and ocr_validation.get("status") == "ok"
        and bool(ocr_validation_checks)
        and all(value is True for value in ocr_validation_checks.values())
        and ocr_denominator == int(ocr_totals.get("candidate_pages") or 0)
        and ocr_denominator
        == int(ocr_validation_totals.get("candidate_pages") or 0)
        and int(ocr_run.get("claimed") or 0) == ocr_denominator
        and int(ocr_run.get("dead") or 0) == 0
        and int(ocr_run.get("retried") or 0) == 0
    )
    if not ocr_current_full_physical_run_complete:
        errors.append("current full OCR physical run is incomplete")
    ocr_cold_output_benchmark_available = (
        ocr_perf.get("cold_state_and_output") is True
    )
    expected_ocr_measurement_status = (
        "cold_physical_run"
        if ocr_cold_output_benchmark_available
        else "current_full_real_warm_output_run"
    )
    if page_ocr.get("measurement_status") != expected_ocr_measurement_status:
        errors.append("OCR measurement status mismatch")
    if (
        page_ocr.get("cold_state_and_output")
        is not ocr_cold_output_benchmark_available
    ):
        errors.append("OCR cold-state telemetry mismatch")
    ocr_expected = {
        "ocr_text_chars": int(ocr_totals.get("ocr_text_chars") or 0),
        "ocr_text_cas_bytes": int(ocr_totals.get("ocr_text_cas_bytes") or 0),
        "elapsed_seconds": float(ocr_perf.get("elapsed_seconds") or 0),
        "elapsed_worker_seconds": float(ocr_totals.get("elapsed_worker_seconds") or 0),
        "cpu_seconds_parent_and_children": float(ocr_perf.get("cpu_seconds") or 0),
        "failures": int(ocr_run.get("dead") or 0),
    }
    if ocr_denominator <= 0 or page_ocr.get("candidate_pages") != ocr_denominator:
        errors.append("OCR physical denominator mismatch")
    ocr_per_1000 = page_ocr.get("per_1000_candidate_pages") or {}
    for key, value in ocr_expected.items():
        if page_ocr.get(key) != value:
            errors.append(f"page_ocr.{key} mismatch")
        if ocr_denominator > 0 and not close(
            ocr_per_1000.get(key), scaled(value, ocr_denominator)
        ):
            errors.append(f"OCR per-1,000 {key} mismatch")
    for key in ("peak_rss_bytes_self", "peak_rss_bytes_child_max"):
        if page_ocr.get(key) != int(ocr_perf.get(key) or 0):
            errors.append(f"OCR {key} mismatch")
    if ocr.get("status") != "ok" or ocr_validation.get("status") != "ok":
        errors.append("OCR producer or independent validation is not ok")

    acquisition = artifact.get("acquisition") or {}
    acquisition_denominator = int(acquisition_run_totals.get("succeeded") or 0)
    acquisition_expected = {
        "network_requests_started": int(
            acquisition_run_perf.get("network_requests_started") or 0
        ),
        "bytes_received": int(acquisition_run_totals.get("bytes_received") or 0),
        "elapsed_seconds": float(acquisition_run_perf.get("elapsed_seconds") or 0),
        "cpu_seconds": float(acquisition_run_perf.get("cpu_seconds") or 0),
        "failures": int(acquisition_validation_checks.get("host_failures") or 0),
    }
    acquisition_per_1000 = acquisition.get("per_1000_succeeded") or {}
    if (
        acquisition_denominator <= 0
        or acquisition.get("documents_succeeded") != acquisition_denominator
        or acquisition.get("documents_attempted")
        != int(acquisition_run_totals.get("claimed") or 0)
    ):
        errors.append("acquisition denominator mismatch")
    for key, value in acquisition_expected.items():
        if acquisition.get(key) != value:
            errors.append(f"acquisition.{key} mismatch")
        if acquisition_denominator > 0 and not close(
            acquisition_per_1000.get(key), scaled(value, acquisition_denominator)
        ):
            errors.append(f"acquisition per-1,000 {key} mismatch")
    if (
        acquisition.get("measurement_status")
        != "cold_physical_real_multihost_cohort"
    ):
        errors.append("fresh acquisition measurement status mismatch")
    if acquisition.get("peak_rss_bytes") != int(
        acquisition_run_perf.get("peak_rss_bytes") or 0
    ):
        errors.append("fresh acquisition peak RSS mismatch")
    if acquisition.get("cohort_id") != acquisition_validation.get("cohort_id"):
        errors.append("fresh acquisition cohort identity mismatch")
    if acquisition.get("cohort_semantic_sha256") != acquisition_validation.get(
        "cohort_semantic_sha256"
    ):
        errors.append("fresh acquisition cohort semantic hash mismatch")
    expected_hosts = sorted((acquisition_validation.get("hosts") or {}).keys())
    if acquisition.get("official_hosts") != expected_hosts:
        errors.append("fresh acquisition official hosts mismatch")
    if acquisition.get("source_contract_rows") != int(
        acquisition_validation_checks.get("source_contract_rows") or 0
    ):
        errors.append("fresh acquisition source-contract rows mismatch")
    content_drift = acquisition_validation.get("content_drift") or {}
    if acquisition.get("content_exact_matches") != int(
        content_drift.get("exact_matches") or 0
    ):
        errors.append("fresh acquisition exact-match rows mismatch")
    if acquisition.get("content_drifted_rows") != int(
        content_drift.get("drifted_rows") or 0
    ):
        errors.append("fresh acquisition drift rows mismatch")
    if acquisition.get("official_revisions_preserved") is not (
        (acquisition_validation.get("policy") or {}).get(
            "official_content_revisions_preserved_and_measured"
        )
        is True
    ):
        errors.append("fresh acquisition revision policy mismatch")

    historical = artifact.get("historical_acquisition_queue") or {}
    fetch_denominator = int(fetch_docs.get("fetched_succeeded_total") or 0)
    historical_expected = {
        "official_urls_total": int(fetch_docs.get("official_urls_total") or 0),
        "documents_succeeded": fetch_denominator,
        "queue_attempts": int(fetch_queue.get("attempts_total") or 0),
        "bytes_received": int(fetch_docs.get("bytes_received") or 0),
        "terminal_dead": int((fetch_queue.get("state_counts") or {}).get("dead") or 0),
        "unfinished": int(fetch_queue.get("unfinished_total") or 0),
    }
    if historical.get("measurement_status") != "historical_queue_state":
        errors.append("historical acquisition status mismatch")
    for key, value in historical_expected.items():
        if historical.get(key) != value:
            errors.append(f"historical_acquisition_queue.{key} mismatch")

    storage = artifact.get("storage") or {}
    file_instances = int(inventory_totals.get("files") or 0)
    if storage.get("file_instances") != file_instances:
        errors.append("storage file instance denominator mismatch")
    storage_per_1000 = storage.get("per_1000_file_instances") or {}
    for key, value in {
        "raw_document_bytes": int(inventory_totals.get("bytes") or 0),
        "native_text_cas_bytes": int(extraction_totals.get("text_cas_bytes") or 0),
    }.items():
        if storage.get(key) != value:
            errors.append(f"storage.{key} mismatch")
        if file_instances > 0 and not close(
            storage_per_1000.get(key), scaled(value, file_instances)
        ):
            errors.append(f"storage per-1,000 {key} mismatch")

    money = artifact.get("monetary_cost") or {}
    if money.get("measurement_status") != "unknown_not_measured":
        errors.append("monetary cost status must remain unknown_not_measured")
    for key in (
        "currency",
        "actual_amount",
        "cost_per_1000_documents",
        "cost_per_1000_ocr_pages",
    ):
        if money.get(key) is not None:
            errors.append(f"unmeasured monetary field {key} must be null")
    if (
        money.get("provider_rates_present") is not False
        or money.get("invoice_or_meter_present") is not False
    ):
        errors.append("unverified rates or invoices claimed")

    checks = artifact.get("checks") or {}
    if not isinstance(checks, dict) or not checks:
        errors.append("producer checks missing")
    else:
        missing_integrity_checks = sorted(REQUIRED_INTEGRITY_CHECKS - checks.keys())
        if missing_integrity_checks:
            errors.append(
                "producer integrity/completeness checks missing: "
                + ", ".join(missing_integrity_checks)
            )
        if checks.get(NATIVE_CURRENT_FULL_CHECK) is not (
            native_current_full_physical_run_complete
        ):
            errors.append("producer current-full native completion check mismatch")
        if checks.get(NATIVE_COLD_OUTPUT_CHECK) is not (
            native_cold_output_benchmark_available
        ):
            errors.append("producer cold-output benchmark check mismatch")
        if checks.get(OCR_CURRENT_FULL_CHECK) is not (
            ocr_current_full_physical_run_complete
        ):
            errors.append("producer current-full OCR completion check mismatch")
        if checks.get(OCR_COLD_OUTPUT_CHECK) is not (
            ocr_cold_output_benchmark_available
        ):
            errors.append("producer OCR cold-output benchmark check mismatch")
        for key, value in checks.items():
            if key in {NATIVE_COLD_OUTPUT_CHECK, OCR_COLD_OUTPUT_CHECK}:
                continue
            if value is not True:
                errors.append(f"producer integrity/completeness check failed: {key}")

    measurement_gaps = artifact.get("measurement_gaps")
    if (
        not isinstance(measurement_gaps, list)
        or not measurement_gaps
        or not all(
            isinstance(value, str) and value.strip() for value in measurement_gaps
        )
    ):
        errors.append("measurement gaps must be a non-empty string list")
        measurement_gaps = []
    if native_cold_output_benchmark_available:
        if COLD_OUTPUT_GAP in measurement_gaps:
            errors.append("cold-output gap contradicts cold native telemetry")
    elif COLD_OUTPUT_GAP not in measurement_gaps:
        errors.append("warm-output native run must disclose missing cold benchmark")
    if ocr_cold_output_benchmark_available:
        if OCR_COLD_OUTPUT_GAP in measurement_gaps:
            errors.append("OCR cold-output gap contradicts cold telemetry")
    elif OCR_COLD_OUTPUT_GAP not in measurement_gaps:
        errors.append("warm-output OCR run must disclose missing cold benchmark")

    scale_claim = artifact.get("scale_claim") or {}
    if scale_claim.get("one_million_documents_processed") != (
        native_denominator >= 1_000_000
    ):
        errors.append("one-million claim mismatch")
    if scale_claim.get("promoted_for_one_million_operation") is not False:
        errors.append("unsupported one-million promotion")
    next_gate = str(scale_claim.get("next_gate") or "")
    if native_cold_output_benchmark_available:
        if COLD_OUTPUT_NEXT_GATE in next_gate:
            errors.append("next gate contradicts available cold-output benchmark")
    elif COLD_OUTPUT_NEXT_GATE not in next_gate:
        errors.append("next gate omits required cold-output benchmark run")
    if ocr_cold_output_benchmark_available:
        if OCR_COLD_OUTPUT_NEXT_GATE in next_gate:
            errors.append("next gate contradicts available OCR cold-output benchmark")
    elif OCR_COLD_OUTPUT_NEXT_GATE not in next_gate:
        errors.append("next gate omits required OCR cold-output benchmark run")
    if "one million distinct real content objects" not in next_gate:
        errors.append("next gate omits independently validated one-million real corpus")

    return {
        "schema_version": "document_factory_economics_validation_v1",
        "status": "ok" if not errors else "error",
        "inputs": {
            "public_artifact": input_descriptor(artifact_path),
            "evidence_copy": input_descriptor(evidence_path),
            "inventory": input_descriptor(inventory_path),
            "native_extraction": input_descriptor(extraction_path),
            "native_validation": input_descriptor(extraction_validation_path),
            "page_ocr": input_descriptor(ocr_path),
            "page_ocr_validation": input_descriptor(ocr_validation_path),
            "document_fetch_operations": document_fetch_descriptor(fetch_path, fetch),
            "fresh_acquisition_run": input_descriptor(acquisition_run_path),
            "fresh_acquisition_validation": input_descriptor(
                acquisition_validation_path
            ),
        },
        "checks": {
            "file_size_bytes": size,
            "max_bytes": max_bytes,
            "native_objects": native_denominator,
            "native_file_instances": inventory_file_instances,
            "native_counts_reconciled": native_counts_reconcile,
            NATIVE_CURRENT_FULL_CHECK: native_current_full_physical_run_complete,
            NATIVE_COLD_OUTPUT_CHECK: native_cold_output_benchmark_available,
            OCR_CURRENT_FULL_CHECK: ocr_current_full_physical_run_complete,
            OCR_COLD_OUTPUT_CHECK: ocr_cold_output_benchmark_available,
            "ocr_pages": ocr_denominator,
            "fresh_acquisition_documents_succeeded": acquisition_denominator,
            "fresh_acquisition_network_requests": int(
                acquisition_run_perf.get("network_requests_started") or 0
            ),
            "historical_fetch_documents_succeeded": fetch_denominator,
            "input_hashes_verified": not any("inputs." in error for error in errors),
            "per_1000_math_verified": not any("per-1,000" in error for error in errors),
            "unmeasured_cost_remains_null": not any(
                "monetary" in error for error in errors
            ),
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True)
    parser.add_argument("--evidence-path", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--native-extraction", required=True)
    parser.add_argument("--native-validation", required=True)
    parser.add_argument("--page-ocr", required=True)
    parser.add_argument("--page-ocr-validation", required=True)
    parser.add_argument("--document-fetch-operations", required=True)
    parser.add_argument("--fresh-acquisition-run", required=True)
    parser.add_argument("--fresh-acquisition-validation", required=True)
    parser.add_argument("--max-bytes", type=int, default=500_000)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate(
        artifact_path=Path(args.path),
        evidence_path=Path(args.evidence_path),
        inventory_path=Path(args.inventory),
        extraction_path=Path(args.native_extraction),
        extraction_validation_path=Path(args.native_validation),
        ocr_path=Path(args.page_ocr),
        ocr_validation_path=Path(args.page_ocr_validation),
        fetch_path=Path(args.document_fetch_operations),
        acquisition_run_path=Path(args.fresh_acquisition_run),
        acquisition_validation_path=Path(args.fresh_acquisition_validation),
        max_bytes=int(args.max_bytes),
    )
    atomic_write_json(Path(args.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
