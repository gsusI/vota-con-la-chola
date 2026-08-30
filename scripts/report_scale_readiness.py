#!/usr/bin/env python3
"""Audit scale readiness using only captured records from official sources."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DISALLOWED_HOSTS = {"example.com", "example.org", "localhost", "127.0.0.1", "0.0.0.0"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReadinessError(RuntimeError):
    """Raised when evidence cannot support a real-data readiness claim."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(file_path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(file_path: Path) -> dict[str, Any]:
    if not file_path.is_file():
        raise ReadinessError(
            f"missing evidence file: {file_path.relative_to(REPO_ROOT)}"
        )
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessError(
            f"invalid JSON evidence: {file_path.relative_to(REPO_ROOT)}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReadinessError(
            f"evidence must be a JSON object: {file_path.relative_to(REPO_ROOT)}"
        )
    return payload


def repo_path(value: str) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ReadinessError(f"evidence path escapes repository: {value}") from exc
    return candidate


def evidence_reference(file_path: Path) -> dict[str, Any]:
    return {
        "path": file_path.relative_to(REPO_ROOT).as_posix(),
        "bytes": file_path.stat().st_size,
        "sha256": sha256_file(file_path),
    }


def obstruction_projection_descriptor(
    file_path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    policy = payload.get("policy") or {}
    open_incidents = []
    for row in payload.get("incidents") or []:
        if not isinstance(row, dict) or row.get("status") != "OPEN":
            continue
        open_incidents.append(
            {
                "incident_id": str(row.get("incident_id") or ""),
                "status": "OPEN",
                "endpoint_or_page": str(row.get("endpoint_or_page") or ""),
            }
        )
    open_incidents.sort(key=lambda row: (row["incident_id"], row["endpoint_or_page"]))
    projection = {
        "schema_version": "obstruction_classification_projection_v1",
        "policy": {
            "data_origin": policy.get("data_origin"),
            "synthetic_or_mock_records": policy.get("synthetic_or_mock_records"),
            "public_domain_personal_information": policy.get(
                "public_domain_personal_information"
            ),
        },
        "open_incidents": open_incidents,
    }
    body = json.dumps(
        projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "path": file_path.relative_to(REPO_ROOT).as_posix(),
        "descriptor_kind": "canonical_json_projection",
        "projection_schema": projection["schema_version"],
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "open_incidents": len(open_incidents),
    }


def reject_disallowed_evidence(value: Any, location: str = "root") -> None:
    """Reject metadata markers that describe generated or loopback-only evidence."""
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered.endswith("_capacity_only") and child is True:
                raise ReadinessError(
                    f"generated-only evidence marker at {location}.{key}"
                )
            if (
                lowered in {"controlled_local_http_only", "fixture_only", "mock_only"}
                and child is True
            ):
                raise ReadinessError(
                    f"non-official evidence marker at {location}.{key}"
                )
            reject_disallowed_evidence(child, f"{location}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            reject_disallowed_evidence(child, f"{location}[{index}]")
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(
            token in lowered
            for token in ("example.org", "example.com", "localhost", "127.0.0.1")
        ):
            raise ReadinessError(f"non-official endpoint at {location}")


def checks_pass(payload: dict[str, Any], *, require_status: bool) -> bool:
    checks = payload.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or not all(value is True for value in checks.values())
    ):
        return False
    return not require_status or payload.get("status") == "ok"


def official_host(url: str, allowed_hosts: set[str]) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host or host in DISALLOWED_HOSTS:
        raise ReadinessError(f"source URL is not an official HTTP origin: {url}")
    if host not in allowed_hosts:
        raise ReadinessError(f"source URL host is outside registry allowlist: {host}")
    return host


def manifest_files(manifest: dict[str, Any]) -> Iterable[dict[str, Any]]:
    partitions = manifest.get("partitions")
    if not isinstance(partitions, list):
        raise ReadinessError("semantic manifest has no partitions array")
    for partition in partitions:
        if not isinstance(partition, dict) or not isinstance(
            partition.get("files"), list
        ):
            raise ReadinessError("semantic manifest partition has no files array")
        yield from partition["files"]


def validate_semantic_files(
    root: Path,
    manifest: dict[str, Any],
    *,
    allowed_source_ids: set[str],
    allowed_hosts: set[str],
    inspect_provenance: bool,
) -> dict[str, Any]:
    try:
        from pyarrow import parquet
    except ImportError as exc:
        raise ReadinessError(
            "pyarrow is required for full real-row validation"
        ) from exc

    if not root.is_dir():
        raise ReadinessError(
            f"missing semantic artifact root: {root.relative_to(REPO_ROOT)}"
        )

    declared_paths: set[str] = set()
    observed_sources: set[str] = set()
    observed_hosts: set[str] = set()
    total_rows = 0
    source_url_https_rows = 0
    total_bytes = 0
    total_files = 0

    for file_spec in manifest_files(manifest):
        relative = str(file_spec.get("path") or "")
        if not relative or relative in declared_paths:
            raise ReadinessError(
                f"missing or duplicate semantic file path: {relative!r}"
            )
        declared_paths.add(relative)
        file_path = (root / relative).resolve()
        try:
            file_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ReadinessError(
                f"semantic file escapes artifact root: {relative}"
            ) from exc
        if not file_path.is_file():
            raise ReadinessError(
                f"missing semantic file: {file_path.relative_to(REPO_ROOT)}"
            )
        observed_bytes = file_path.stat().st_size
        if observed_bytes != int(file_spec.get("bytes", -1)):
            raise ReadinessError(f"semantic file byte mismatch: {relative}")
        if sha256_file(file_path) != file_spec.get("sha256"):
            raise ReadinessError(f"semantic file checksum mismatch: {relative}")

        parquet_file = parquet.ParquetFile(file_path)
        file_rows = parquet_file.metadata.num_rows
        if file_rows != int(file_spec.get("rows", -1)):
            raise ReadinessError(f"semantic file row mismatch: {relative}")
        total_rows += file_rows
        total_bytes += observed_bytes
        total_files += 1

        if not inspect_provenance:
            continue
        names = set(parquet_file.schema_arrow.names)
        if not {"source_id", "source_url"}.issubset(names):
            raise ReadinessError(f"semantic file lacks provenance columns: {relative}")
        for batch in parquet_file.iter_batches(
            columns=["source_id", "source_url"], batch_size=65_536
        ):
            source_ids = batch.column(0).to_pylist()
            source_urls = batch.column(1).to_pylist()
            for source_id, source_url in zip(source_ids, source_urls, strict=True):
                if source_id not in allowed_source_ids:
                    raise ReadinessError(
                        f"unregistered source_id {source_id!r} in {relative}"
                    )
                if not isinstance(source_url, str) or not source_url:
                    raise ReadinessError(f"missing source_url in {relative}")
                observed_sources.add(source_id)
                observed_hosts.add(official_host(source_url, allowed_hosts))
                if urlparse(source_url).scheme == "https":
                    source_url_https_rows += 1

    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.parquet")
        if path.is_file()
    }
    if actual_paths != declared_paths:
        missing = sorted(declared_paths - actual_paths)[:3]
        extra = sorted(actual_paths - declared_paths)[:3]
        raise ReadinessError(
            f"semantic file inventory mismatch; missing={missing}, extra={extra}"
        )

    totals = manifest.get("totals") or {}
    expected = {
        "rows": total_rows,
        "files": total_files,
        "parquet_bytes": total_bytes,
    }
    for key, observed in expected.items():
        if int(totals.get(key, -1)) != observed:
            raise ReadinessError(
                f"semantic manifest total mismatch for {key}: {totals.get(key)} != {observed}"
            )

    return {
        "rows": total_rows,
        "source_url_rows": total_rows,
        "source_url_https_rows": source_url_https_rows
        if inspect_provenance
        else total_rows,
        "files": total_files,
        "bytes": total_bytes,
        "source_ids": sorted(observed_sources),
        "official_hosts": sorted(observed_hosts),
    }


def validate_member_vote_shard(
    file_path: Path,
    entry: dict[str, Any],
    *,
    allowed_source_ids: set[str],
    allowed_hosts: set[str],
) -> tuple[int, int, int, set[str], set[str]]:
    if file_path.stat().st_size != int(entry.get("shard_bytes", -1)):
        raise ReadinessError(
            f"vote shard byte mismatch: {file_path.relative_to(REPO_ROOT)}"
        )
    if sha256_file(file_path) != entry.get("shard_sha256"):
        raise ReadinessError(
            f"vote shard checksum mismatch: {file_path.relative_to(REPO_ROOT)}"
        )
    try:
        with gzip.open(file_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessError(
            f"invalid vote shard: {file_path.relative_to(REPO_ROOT)}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or not isinstance(
        payload.get("member_votes"), list
    ):
        raise ReadinessError(
            f"vote shard has invalid payload contract: {file_path.relative_to(REPO_ROOT)}"
        )
    member_votes = payload["member_votes"]
    if len(member_votes) != int(entry.get("member_votes", -1)):
        raise ReadinessError(
            f"vote shard member count mismatch: {file_path.relative_to(REPO_ROOT)}"
        )

    source_ids: set[str] = set()
    hosts: set[str] = set()
    source_url_rows = 0
    source_url_https_rows = 0
    event = payload.get("event") or {}
    event_source_id = event.get("source_id")
    if event_source_id:
        if event_source_id not in allowed_source_ids:
            raise ReadinessError(f"unregistered vote source_id {event_source_id!r}")
        source_ids.add(event_source_id)
    for member_vote in member_votes:
        source = member_vote.get("source") if isinstance(member_vote, dict) else None
        if not isinstance(source, dict):
            raise ReadinessError(
                f"vote member lacks source lineage: {file_path.relative_to(REPO_ROOT)}"
            )
        source_id = source.get("source_id")
        source_url = source.get("source_url")
        source_record_id = source.get("source_record_id")
        if source_id not in allowed_source_ids or not source_record_id:
            raise ReadinessError(
                f"vote member has invalid source lineage: {file_path.relative_to(REPO_ROOT)}"
            )
        source_ids.add(source_id)
        if source_url:
            hosts.add(official_host(str(source_url), allowed_hosts))
            source_url_rows += 1
            if urlparse(str(source_url)).scheme == "https":
                source_url_https_rows += 1
    return len(member_votes), source_url_rows, source_url_https_rows, source_ids, hosts


def validate_member_vote_corpus(
    root: Path,
    manifest: dict[str, Any],
    *,
    allowed_source_ids: set[str],
    allowed_hosts: set[str],
) -> dict[str, Any]:
    if not root.is_dir():
        raise ReadinessError(
            f"missing vote artifact root: {root.relative_to(REPO_ROOT)}"
        )
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ReadinessError("vote manifest has no entries")
    rows = 0
    source_url_rows = 0
    source_url_https_rows = 0
    total_bytes = 0
    sources: set[str] = set()
    hosts: set[str] = set()
    declared: set[str] = set()
    for entry in entries:
        relative = str(entry.get("shard") or "")
        if not relative or relative in declared:
            raise ReadinessError(f"missing or duplicate vote shard path: {relative!r}")
        declared.add(relative)
        file_path = (root / relative).resolve()
        try:
            file_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ReadinessError(
                f"vote shard escapes artifact root: {relative}"
            ) from exc
        if not file_path.is_file():
            raise ReadinessError(f"missing vote shard: {relative}")
        (
            shard_rows,
            shard_source_url_rows,
            shard_https_rows,
            shard_sources,
            shard_hosts,
        ) = validate_member_vote_shard(
            file_path,
            entry,
            allowed_source_ids=allowed_source_ids,
            allowed_hosts=allowed_hosts,
        )
        rows += shard_rows
        source_url_rows += shard_source_url_rows
        source_url_https_rows += shard_https_rows
        total_bytes += file_path.stat().st_size
        sources.update(shard_sources)
        hosts.update(shard_hosts)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.json.gz")
        if path.is_file()
    }
    if actual != declared:
        raise ReadinessError("vote shard file inventory does not match manifest")
    if rows != int(manifest.get("member_votes_total", -1)):
        raise ReadinessError("vote manifest row total does not match actual payloads")
    if total_bytes != int(manifest.get("shard_bytes_total", -1)):
        raise ReadinessError("vote manifest byte total does not match actual files")
    if len(entries) != int(manifest.get("events_total", -1)):
        raise ReadinessError("vote manifest event total does not match entries")
    lineage = manifest.get("lineage") or {}
    expected_source_url_rows = int(lineage.get("member_votes", -1)) - int(
        lineage.get("public_source_url_unresolved", -1)
    )
    if source_url_rows != expected_source_url_rows:
        raise ReadinessError(
            "vote manifest public source URL total does not match actual payloads"
        )
    return {
        "rows": rows,
        "source_url_rows": source_url_rows,
        "source_url_https_rows": source_url_https_rows,
        "files": len(entries),
        "bytes": total_bytes,
        "source_ids": sorted(sources),
        "official_hosts": sorted(hosts),
    }


def validate_replay(
    corpus: dict[str, Any], *, allowed_source_ids: set[str], allowed_hosts: set[str]
) -> dict[str, Any]:
    incremental_manifest_path = repo_path(corpus["incremental_manifest"])
    incremental_validation_path = repo_path(corpus["incremental_validation"])
    replay_root = repo_path(corpus["replay_root"])
    incremental_manifest = load_json(incremental_manifest_path)
    incremental_validation = load_json(incremental_validation_path)
    reject_disallowed_evidence(incremental_manifest, corpus["incremental_manifest"])
    reject_disallowed_evidence(incremental_validation, corpus["incremental_validation"])
    if not checks_pass(incremental_manifest, require_status=False):
        raise ReadinessError(f"incremental manifest checks failed: {corpus['id']}")
    if not checks_pass(incremental_validation, require_status=True):
        raise ReadinessError(f"incremental validation checks failed: {corpus['id']}")
    observed = validate_semantic_files(
        replay_root,
        incremental_manifest,
        allowed_source_ids=allowed_source_ids,
        allowed_hosts=allowed_hosts,
        inspect_provenance=False,
    )
    contract = incremental_manifest.get("incremental_contract") or {}
    expected_partitions = int(
        (incremental_manifest.get("totals") or {}).get("partitions", -1)
    )
    replay_ok = (
        int(contract.get("partitions_reused", -1)) == expected_partitions
        and int(contract.get("partitions_rebuilt", -1)) == 0
        and int(contract.get("files_hardlinked", -1)) == observed["files"]
        and int(contract.get("files_copied", -1)) == 0
    )
    if not replay_ok:
        raise ReadinessError(f"unchanged replay contract failed: {corpus['id']}")
    return {
        "passed": True,
        "root": replay_root.relative_to(REPO_ROOT).as_posix(),
        "manifest": evidence_reference(incremental_manifest_path),
        "validation": evidence_reference(incremental_validation_path),
        "partitions_reused": expected_partitions,
        "files_hardlinked": observed["files"],
    }


def audit_corpus(corpus: dict[str, Any]) -> dict[str, Any]:
    corpus_id = str(corpus.get("id") or "")
    allowed_source_ids = set(corpus.get("official_source_ids") or [])
    allowed_hosts = set(corpus.get("official_hosts") or [])
    if not corpus_id or not allowed_source_ids or not allowed_hosts:
        raise ReadinessError(
            f"corpus registry entry lacks identity/origin allowlists: {corpus_id!r}"
        )
    root = repo_path(corpus["root"])
    manifest_path = repo_path(corpus["manifest"])
    validation_path = repo_path(corpus["validation"])
    manifest = load_json(manifest_path)
    validation = load_json(validation_path)
    reject_disallowed_evidence(manifest, corpus["manifest"])
    reject_disallowed_evidence(validation, corpus["validation"])
    if not checks_pass(manifest, require_status=False):
        raise ReadinessError(f"manifest checks failed: {corpus_id}")
    if not checks_pass(validation, require_status=True):
        raise ReadinessError(f"validation checks failed: {corpus_id}")

    if corpus["kind"] == "parquet_manifest":
        observed = validate_semantic_files(
            root,
            manifest,
            allowed_source_ids=allowed_source_ids,
            allowed_hosts=allowed_hosts,
            inspect_provenance=True,
        )
    elif corpus["kind"] == "gzip_vote_shards":
        observed = validate_member_vote_corpus(
            root,
            manifest,
            allowed_source_ids=allowed_source_ids,
            allowed_hosts=allowed_hosts,
        )
    else:
        raise ReadinessError(f"unsupported corpus kind: {corpus['kind']}")

    validation_rows = int(
        (validation.get("totals") or {}).get(
            "rows", (validation.get("totals") or {}).get("member_votes", -1)
        )
    )
    if validation_rows != observed["rows"]:
        raise ReadinessError(f"validation row total mismatch: {corpus_id}")
    min_rows = int(corpus["minimum_real_rows"])
    scale_gate_passed = observed["rows"] >= min_rows
    replay = None
    if all(
        corpus.get(key)
        for key in ("replay_root", "incremental_manifest", "incremental_validation")
    ):
        replay = validate_replay(
            corpus, allowed_source_ids=allowed_source_ids, allowed_hosts=allowed_hosts
        )

    promotion_checks = {
        "minimum_real_rows": scale_gate_passed,
        "complete_public_source_url": observed["source_url_rows"] == observed["rows"],
        "https_source_urls_only": observed["source_url_https_rows"]
        == observed["source_url_rows"],
        "representative_scope": corpus.get("representative_scope") is True,
        "durable_public_origin": corpus.get("durable_public_origin") is True,
        "clean_room_restore": corpus.get("clean_room_restore") is True,
        "corrections_workflow": corpus.get("corrections_workflow") is True,
    }
    return {
        "id": corpus_id,
        "label": corpus["label"],
        "kind": corpus["kind"],
        "status": "validated_real_artifact",
        "real_official_data": True,
        "root": root.relative_to(REPO_ROOT).as_posix(),
        "rows": observed["rows"],
        "source_url_rows": observed["source_url_rows"],
        "source_url_https_rows": observed["source_url_https_rows"],
        "source_url_coverage": round(observed["source_url_rows"] / observed["rows"], 8)
        if observed["rows"]
        else 0.0,
        "files": observed["files"],
        "bytes": observed["bytes"],
        "minimum_real_rows": min_rows,
        "scale_gate_passed": scale_gate_passed,
        "source_ids": observed["source_ids"],
        "official_hosts": observed["official_hosts"],
        "manifest": evidence_reference(manifest_path),
        "validation": evidence_reference(validation_path),
        "unchanged_replay": replay,
        "promotion_checks": promotion_checks,
        "promotion_gate_passed": all(promotion_checks.values()),
        "limitations": list(corpus.get("limitations") or []),
        "next_gate": corpus["next_gate"],
    }


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReadinessError(f"{label} must be a non-negative integer")
    return value


def audit_document_provenance_gap(
    gap: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    json_keys = (
        "inventory",
        "audit",
        "queue",
        "wayback_recovery",
        "boe_corpus",
        "boe_manifest_validation",
        "boe_generation_audit",
        "native_extraction",
        "native_validation",
        "native_generation_audit",
        "text_locators",
        "text_locator_validation",
        "text_locator_generation_audit",
        "document_profile",
        "document_profile_validation",
        "document_profile_generation_audit",
        "page_ocr",
        "page_ocr_validation",
        "page_ocr_generation_audit",
        "local_origin_replication",
        "local_origin_generation_audit",
        "local_origin_clean_restore",
        "local_origin_packaging",
        "local_origin_pack_validation",
        "local_origin_pack_generation_audit",
        "local_origin_release_manifest",
        "local_origin_release_upload_plan",
        "local_origin_release_pointer",
        "local_origin_release_preparation",
        "local_origin_hf_publication_preflight",
        "ocr_review",
        "ocr_review_validation",
        "fetch_cohort",
        "fetch_preflight",
        "fetch_run",
        "fetch_validation",
        "source_universe",
        "source_universe_validation",
        "economics",
        "economics_evidence",
        "economics_validation",
    )
    path_keys = (
        *json_keys,
        "wayback_manifest",
        "wayback_checkpoint",
        "boe_manifest",
        "ocr_review_csv",
    )
    evidence_paths = {key: repo_path(str(contract.get(key) or "")) for key in path_keys}
    payloads = {key: load_json(evidence_paths[key]) for key in json_keys}
    for key, payload in payloads.items():
        reject_disallowed_evidence(payload, contract[key])

    inventory = payloads["inventory"]
    audit = payloads["audit"]
    queue = payloads["queue"]
    wayback_recovery = payloads["wayback_recovery"]
    boe_corpus = payloads["boe_corpus"]
    boe_manifest_validation = payloads["boe_manifest_validation"]
    boe_generation_audit = payloads["boe_generation_audit"]
    native_extraction = payloads["native_extraction"]
    native_validation = payloads["native_validation"]
    native_generation_audit = payloads["native_generation_audit"]
    native_current_manifest = native_extraction.get("manifest") or {}
    text_locators = payloads["text_locators"]
    text_locator_validation = payloads["text_locator_validation"]
    text_locator_generation_audit = payloads["text_locator_generation_audit"]
    document_profile = payloads["document_profile"]
    document_profile_validation = payloads["document_profile_validation"]
    document_profile_generation_audit = payloads["document_profile_generation_audit"]
    page_ocr = payloads["page_ocr"]
    page_ocr_validation = payloads["page_ocr_validation"]
    page_ocr_generation_audit = payloads["page_ocr_generation_audit"]
    local_origin_replication = payloads["local_origin_replication"]
    local_origin_generation_audit = payloads["local_origin_generation_audit"]
    local_origin_clean_restore = payloads["local_origin_clean_restore"]
    local_origin_packaging = payloads["local_origin_packaging"]
    local_origin_pack_validation = payloads["local_origin_pack_validation"]
    local_origin_pack_generation_audit = payloads["local_origin_pack_generation_audit"]
    local_origin_release_manifest = payloads["local_origin_release_manifest"]
    local_origin_release_upload_plan = payloads["local_origin_release_upload_plan"]
    local_origin_release_pointer = payloads["local_origin_release_pointer"]
    local_origin_release_preparation = payloads["local_origin_release_preparation"]
    local_origin_hf_publication_preflight = payloads[
        "local_origin_hf_publication_preflight"
    ]
    ocr_review = payloads["ocr_review"]
    ocr_review_validation = payloads["ocr_review_validation"]
    fetch_cohort = payloads["fetch_cohort"]
    fetch_preflight = payloads["fetch_preflight"]
    fetch_run = payloads["fetch_run"]
    fetch_validation = payloads["fetch_validation"]
    source_universe = payloads["source_universe"]
    source_universe_validation = payloads["source_universe_validation"]
    economics = payloads["economics"]
    economics_evidence = payloads["economics_evidence"]
    economics_validation = payloads["economics_validation"]
    if inventory.get("schema_version") != "real_document_format_inventory_v4":
        raise ReadinessError("document gap inventory contract version mismatch")
    if audit.get("schema_version") != "real_document_provenance_audit_v13":
        raise ReadinessError("document gap audit contract version mismatch")
    if queue.get("schema_version") != "document_provenance_gap_queue_v1":
        raise ReadinessError("document gap queue contract version mismatch")
    if inventory.get("status") != "ok":
        raise ReadinessError("document gap inventory is not clean")
    if not (audit.get("checks") or {}).get("integrity_passed"):
        raise ReadinessError("document gap provenance integrity failed")
    if queue.get("status") != "ok" or not all(
        value is True for value in (queue.get("checks") or {}).values()
    ):
        raise ReadinessError("document gap queue checks failed")
    if (
        wayback_recovery.get("schema_version") != "wayback_document_lineage_report_v1"
        or wayback_recovery.get("status") not in {"ok", "partial"}
        or not all(
            value is True for value in (wayback_recovery.get("checks") or {}).values()
        )
    ):
        raise ReadinessError("document Wayback recovery checks failed")
    wayback_policy = wayback_recovery.get("policy") or {}
    if (
        wayback_policy.get("synthetic_or_mock_records_counted") is not False
        or wayback_policy.get("public_domain_personal_information_retained") is not True
        or wayback_policy.get("remote_mutation_performed") is not False
    ):
        raise ReadinessError("document Wayback recovery policy failed")
    inventory_totals = inventory.get("totals") or {}
    audit_totals = audit.get("totals") or {}
    queue_totals = queue.get("totals") or {}
    eligible_files = _require_nonnegative_int(
        inventory_totals.get("files"), "document inventory files"
    )
    compared_file_totals = {
        eligible_files,
        _require_nonnegative_int(audit_totals.get("files"), "document audit files"),
        _require_nonnegative_int(
            queue_totals.get("files_scanned"), "document queue files"
        ),
        _require_nonnegative_int(
            gap.get("current_real_rows"), "document gap current_real_rows"
        ),
    }
    if len(compared_file_totals) != 1:
        raise ReadinessError(
            "document gap file totals drifted across registry/inventory/audit/queue"
        )
    if (
        boe_corpus.get("schema_version") != "boe_document_corpus_report_v1"
        or boe_corpus.get("status") != "ok"
    ):
        raise ReadinessError("BOE document corpus contract failed")
    boe_policy = boe_corpus.get("policy") or {}
    if (
        boe_policy.get("synthetic_or_mock_records_counted") is not False
        or boe_policy.get("official_public_domain_personal_information_retained")
        is not True
        or boe_policy.get("remote_mutation_performed") is not False
    ):
        raise ReadinessError("BOE document corpus real-data policy failed")
    processing_contracts = {
        "native_extraction": ("real_document_text_extraction_v1", {"ok"}),
        "native_validation": ("real_document_text_validation_v1", {"ok"}),
        "native_generation_audit": (
            "real_document_generation_lifecycle_audit_v1",
            {"ok"},
        ),
        "text_locators": ("real_document_text_locator_extraction_v1", {"ok"}),
        "text_locator_validation": (
            "real_document_text_locator_validation_v1",
            {"ok"},
        ),
        "text_locator_generation_audit": (
            "real_document_generation_lifecycle_audit_v1",
            {"ok"},
        ),
        "document_profile": (
            "real_document_language_encryption_profile_v2",
            {"ok"},
        ),
        "document_profile_validation": (
            "real_document_language_encryption_validation_v2",
            {"ok"},
        ),
        "document_profile_generation_audit": (
            "real_document_generation_lifecycle_audit_v1",
            {"ok"},
        ),
        "page_ocr": ("real_document_page_ocr_v1", {"ok"}),
        "page_ocr_validation": ("real_document_page_ocr_validation_v1", {"ok"}),
        "page_ocr_generation_audit": (
            "real_document_generation_lifecycle_audit_v1",
            {"ok"},
        ),
        "local_origin_replication": (
            "real_document_origin_replication_v1",
            {"ok"},
        ),
        "local_origin_generation_audit": (
            "real_document_generation_lifecycle_audit_v1",
            {"ok"},
        ),
        "local_origin_clean_restore": (
            "real_document_origin_clean_restore_v1",
            {"ok"},
        ),
        "local_origin_packaging": (
            "real_document_origin_packaging_v1",
            {"ok"},
        ),
        "local_origin_pack_validation": (
            "real_document_origin_pack_validation_v1",
            {"ok"},
        ),
        "local_origin_pack_generation_audit": (
            "real_document_generation_lifecycle_audit_v1",
            {"ok"},
        ),
        "ocr_review": (
            "real_document_page_ocr_human_review_queue_v1",
            {"ready_for_human_review"},
        ),
        "ocr_review_validation": (
            "real_document_page_ocr_human_review_validation_v1",
            {"pending_human_review", "complete"},
        ),
    }
    for key, (schema_version, allowed_statuses) in processing_contracts.items():
        payload = payloads[key]
        if payload.get("schema_version") != schema_version:
            raise ReadinessError(f"document {key} contract version mismatch")
        if payload.get("status") not in allowed_statuses or not all(
            value is True for value in (payload.get("checks") or {}).values()
        ):
            raise ReadinessError(f"document {key} checks failed")
        policy = payload.get("policy") or {}
        if (
            policy.get("synthetic_or_mock_records_counted") is not False
            or policy.get("official_public_domain_personal_information_retained")
            is not True
        ):
            raise ReadinessError(f"document {key} real-data policy failed")

    for key, payload, expected_dataset, producer in (
        (
            "native_generation_audit",
            native_generation_audit,
            "native_text",
            native_extraction,
        ),
        (
            "text_locator_generation_audit",
            text_locator_generation_audit,
            "native_text_locator",
            text_locators,
        ),
        (
            "document_profile_generation_audit",
            document_profile_generation_audit,
            "document_profile",
            document_profile,
        ),
        (
            "page_ocr_generation_audit",
            page_ocr_generation_audit,
            "page_ocr",
            page_ocr,
        ),
        (
            "local_origin_generation_audit",
            local_origin_generation_audit,
            "real_document_origin_replicas",
            local_origin_replication,
        ),
        (
            "local_origin_pack_generation_audit",
            local_origin_pack_generation_audit,
            "real_document_origin_packs",
            local_origin_packaging,
        ),
    ):
        lifecycle_input = payload.get("input") or {}
        lifecycle_mode = payload.get("mode") or {}
        lifecycle_policy = payload.get("policy") or {}
        lifecycle_totals = payload.get("totals") or {}
        producer_manifest = producer.get("manifest") or {}
        if (
            payload.get("dataset") != expected_dataset
            or lifecycle_mode.get("full_shard_check") is not True
            or lifecycle_mode.get("full_state_check") is not True
            or lifecycle_input.get("path") != producer_manifest.get("path")
            or lifecycle_input.get("sha256") != producer_manifest.get("sha256")
            or lifecycle_input.get("bytes") != producer_manifest.get("bytes")
            or lifecycle_input.get("logical_sha256")
            != producer_manifest.get("logical_sha256")
            or lifecycle_policy.get("synthetic_or_mock_records_counted") is not False
            or lifecycle_policy.get(
                "official_public_domain_personal_information_retained"
            )
            is not True
            or lifecycle_policy.get("automatic_deletion_forbidden") is not True
            or lifecycle_policy.get("remote_mutation_performed") is not False
            or lifecycle_totals.get("unactivated_manifest_archives") != 0
            or lifecycle_totals.get("unactivated_activation_receipts") != 0
            or lifecycle_totals.get("unactivated_generation_directories") != 0
            or lifecycle_totals.get("orphan_generation_directories") != 0
            or lifecycle_totals.get("orphan_state_snapshots") != 0
            or lifecycle_totals.get("interrupted_staging_directories") != 0
            or lifecycle_totals.get("automatic_deletions") != 0
            or int(lifecycle_totals.get("retained_state_snapshots") or 0) < 1
        ):
            raise ReadinessError(f"document {key} lifecycle contract failed")

    origin_manifest = local_origin_replication.get("manifest") or {}
    origin_inputs = local_origin_replication.get("inputs") or {}
    origin_seeded = local_origin_replication.get("seeded") or {}
    origin_states = local_origin_replication.get("state_counts") or {}
    restore_manifest = local_origin_clean_restore.get("manifest") or {}
    restored = local_origin_clean_restore.get("restored") or {}
    expected_origin_classes = {
        "raw_document": 120_757,
        "native_text": 119_338,
        "ocr_text": 131,
    }
    if (
        local_origin_replication.get("backend") != "filesystem"
        or local_origin_replication.get("durable_public_origin_proven") is not False
        or local_origin_replication.get("clean_room_restore_proven") is not False
        or (local_origin_replication.get("policy") or {}).get(
            "remote_publication_performed"
        )
        is not False
        or origin_seeded.get("total") != sum(expected_origin_classes.values())
        or {key: origin_seeded.get(key) for key in expected_origin_classes}
        != expected_origin_classes
        or origin_states != {"succeeded": sum(expected_origin_classes.values())}
        or origin_manifest.get("rows") != sum(expected_origin_classes.values())
        or origin_inputs.get("native_manifest_sha256")
        != native_current_manifest.get("sha256")
        or origin_inputs.get("ocr_manifest_sha256")
        != (page_ocr.get("manifest") or {}).get("sha256")
        or local_origin_clean_restore.get("backend") != "filesystem"
        or local_origin_clean_restore.get("durable_public_origin_proven") is not False
        or local_origin_clean_restore.get("clean_room_restore_mechanics_proven")
        is not True
        or local_origin_clean_restore.get("remote_publication_performed") is not False
        or restore_manifest.get("sha256") != origin_manifest.get("sha256")
        or restore_manifest.get("rows") != origin_manifest.get("rows")
        or restore_manifest.get("objects_by_class") != expected_origin_classes
        or restored.get("objects") != origin_manifest.get("rows")
        or restored.get("objects_by_class") != expected_origin_classes
        or restored.get("bytes") != restore_manifest.get("bytes")
    ):
        raise ReadinessError("document local origin and clean-restore contract failed")

    pack_plan = local_origin_packaging.get("plan") or {}
    pack_states = local_origin_packaging.get("state_counts") or {}
    pack_packed = local_origin_packaging.get("packed") or {}
    pack_manifest = local_origin_packaging.get("manifest") or {}
    pack_validation_manifest = local_origin_pack_validation.get("manifest") or {}
    pack_verified = local_origin_pack_validation.get("verified") or {}
    if (
        local_origin_packaging.get("durable_public_origin_proven") is not False
        or local_origin_packaging.get("remote_publication_performed") is not False
        or pack_plan.get("objects") != sum(expected_origin_classes.values())
        or pack_plan.get("payload_bytes") != restore_manifest.get("bytes")
        or pack_plan.get("packs") != 25
        or int(pack_plan.get("max_objects") or 0) > 10_000
        or int(pack_plan.get("max_payload_bytes") or 0) > 448 * 1024 * 1024
        or pack_states != {"succeeded": pack_plan.get("packs")}
        or pack_manifest.get("rows") != pack_plan.get("packs")
        or (local_origin_packaging.get("inputs") or {}).get("origin_manifest_sha256")
        != origin_manifest.get("sha256")
        or local_origin_pack_validation.get("durable_public_origin_proven") is not False
        or local_origin_pack_validation.get("remote_restore_proven") is not False
        or local_origin_pack_validation.get("remote_publication_performed") is not False
        or pack_validation_manifest.get("sha256") != pack_manifest.get("sha256")
        or pack_verified.get("packs") != pack_plan.get("packs")
        or pack_verified.get("objects") != pack_plan.get("objects")
        or pack_verified.get("payload_bytes") != pack_plan.get("payload_bytes")
        or pack_verified.get("archive_bytes") != pack_packed.get("archive_bytes")
        or pack_verified.get("member_manifest_bytes")
        != pack_packed.get("member_manifest_bytes")
        or pack_verified.get("objects_by_class") != expected_origin_classes
        or pack_verified.get("source_origin_manifest_sha256")
        != origin_manifest.get("sha256")
    ):
        raise ReadinessError("document immutable local pack contract failed")

    release_summary = local_origin_release_manifest.get("summary") or {}
    release_policy = local_origin_release_manifest.get("policy") or {}
    release_preparation_summary = local_origin_release_preparation.get("summary") or {}
    release_preparation_policy = local_origin_release_preparation.get("policy") or {}
    release_preparation_checks = local_origin_release_preparation.get("checks") or {}
    upload_plan_policy = local_origin_release_upload_plan.get("policy") or {}
    release_pointer_policy = local_origin_release_pointer.get("policy") or {}
    release_files = local_origin_release_manifest.get("files") or []
    release_file_bytes = sum(
        _require_nonnegative_int(row.get("bytes"), "document origin release file bytes")
        for row in release_files
    )
    if (
        local_origin_release_manifest.get("schema_version")
        != "real_document_origin_release_manifest_v1"
        or local_origin_release_upload_plan.get("schema_version")
        != "real_document_origin_upload_plan_v1"
        or local_origin_release_pointer.get("schema_version")
        != "real_document_origin_release_pointer_v1"
        or local_origin_release_preparation.get("schema_version")
        != "real_document_origin_release_preparation_v1"
        or local_origin_release_preparation.get("status")
        != "ready_for_authorized_publication"
        or local_origin_release_preparation.get("authorized") is not False
        or local_origin_release_preparation.get("remote_preflight_performed")
        is not False
        or local_origin_release_preparation.get("remote_publication_performed")
        is not False
        or local_origin_release_preparation.get("durable_public_origin_proven")
        is not False
        or local_origin_release_preparation.get("independent_remote_restore_proven")
        is not False
        or not release_preparation_checks
        or not all(value is True for value in release_preparation_checks.values())
        or local_origin_release_manifest.get("release_id")
        != local_origin_release_upload_plan.get("release_id")
        or local_origin_release_manifest.get("release_id")
        != local_origin_release_pointer.get("release_id")
        or local_origin_release_manifest.get("release_id")
        != local_origin_release_preparation.get("release_id")
        or local_origin_release_manifest.get("release_prefix")
        != local_origin_release_upload_plan.get("release_prefix")
        or local_origin_release_manifest.get("release_prefix")
        != local_origin_release_pointer.get("release_prefix")
        or release_summary != release_preparation_summary
        or release_summary.get("packs") != pack_plan.get("packs")
        or release_summary.get("objects") != pack_plan.get("objects")
        or release_summary.get("payload_bytes") != pack_plan.get("payload_bytes")
        or release_summary.get("archive_bytes") != pack_packed.get("archive_bytes")
        or release_summary.get("member_manifest_bytes")
        != pack_packed.get("member_manifest_bytes")
        or _require_nonnegative_int(
            release_summary.get("release_files"), "document origin release files"
        )
        <= 0
        or _require_nonnegative_int(
            release_summary.get("release_bytes"), "document origin release bytes"
        )
        <= 0
        or release_summary.get("release_bytes") != release_file_bytes
        or len(release_files) != release_summary.get("release_files")
        or len(local_origin_release_upload_plan.get("immutable_files") or [])
        != release_summary.get("release_files")
        or release_policy.get("official_real_records_only") is not True
        or release_policy.get("synthetic_or_mock_records_forbidden") is not True
        or release_policy.get("official_public_domain_personal_information_retained")
        is not True
        or release_policy.get("append_only_immutable_release") is not True
        or release_policy.get("automatic_deletion_forbidden") is not True
        or release_policy.get("latest_pointer_activated_last") is not True
        or release_preparation_policy != release_policy
        or upload_plan_policy.get("append_only") is not True
        or upload_plan_policy.get("delete_operations_forbidden") is not True
        or upload_plan_policy.get("immutable_manifest_uploaded_after_data") is not True
        or upload_plan_policy.get("latest_pointer_uploaded_last") is not True
        or upload_plan_policy.get("resume_requires_remote_checksum_parity") is not True
        or release_pointer_policy.get(
            "official_public_domain_personal_information_retained"
        )
        is not True
        or release_pointer_policy.get("synthetic_or_mock_records_counted") is not False
        or release_pointer_policy.get("immutable_release_files") is not True
        or release_pointer_policy.get("pointer_activated_after_remote_parity")
        is not True
    ):
        raise ReadinessError("document origin release preparation contract failed")
    for report_key, artifact_key in (
        ("release_manifest", "local_origin_release_manifest"),
        ("upload_plan", "local_origin_release_upload_plan"),
        ("latest_pointer", "local_origin_release_pointer"),
    ):
        descriptor = local_origin_release_preparation.get(report_key) or {}
        artifact_path = evidence_paths[artifact_key]
        if (
            descriptor.get("path") != contract[artifact_key]
            or descriptor.get("sha256") != sha256_file(artifact_path)
            or descriptor.get("bytes") != artifact_path.stat().st_size
        ):
            raise ReadinessError(
                f"document origin release {report_key} evidence drifted"
            )

    hf_checks = local_origin_hf_publication_preflight.get("checks") or {}
    hf_summary = local_origin_hf_publication_preflight.get("summary") or {}
    hf_remote = (local_origin_hf_publication_preflight.get("remote") or {}).get(
        "before"
    ) or {}
    hf_release = hf_remote.get("release") or {}
    hf_pointer = hf_remote.get("latest_pointer") or {}
    if (
        local_origin_hf_publication_preflight.get("schema_version")
        != "real_document_origin_hf_publication_v1"
        or local_origin_hf_publication_preflight.get("mode") != "dry_run"
        or local_origin_hf_publication_preflight.get("status")
        != "ready_for_authorized_publication"
        or local_origin_hf_publication_preflight.get("authorized") is not False
        or local_origin_hf_publication_preflight.get("remote_preflight_performed")
        is not True
        or local_origin_hf_publication_preflight.get("remote_publication_performed")
        is not False
        or local_origin_hf_publication_preflight.get("durable_public_origin_proven")
        is not False
        or local_origin_hf_publication_preflight.get(
            "independent_remote_restore_proven"
        )
        is not False
        or local_origin_hf_publication_preflight.get("commits") != []
        or not str(local_origin_hf_publication_preflight.get("dataset_repo") or "")
        or local_origin_hf_publication_preflight.get("release_id")
        != local_origin_release_manifest.get("release_id")
        or local_origin_hf_publication_preflight.get("release_prefix")
        != local_origin_release_manifest.get("release_prefix")
        or not hf_checks
        or not all(value is True for value in hf_checks.values())
        or hf_summary.get("immutable_files") != release_summary.get("release_files")
        or hf_summary.get("immutable_bytes") != release_summary.get("release_bytes")
        or hf_summary.get("release_manifest_bytes")
        != evidence_paths["local_origin_release_manifest"].stat().st_size
        or hf_summary.get("latest_pointer_bytes")
        != evidence_paths["local_origin_release_pointer"].stat().st_size
        or hf_remote.get("append_only_safe") is not True
        or hf_remote.get("release_exact") is not False
        or hf_remote.get("pointer_exact") is not False
        or hf_release.get("expected_files") != release_summary.get("release_files") + 1
        or hf_release.get("exact_files") != 0
        or hf_release.get("missing_files") != release_summary.get("release_files") + 1
        or hf_release.get("conflict_files") != 0
        or hf_release.get("unexpected_files") != 0
        or hf_pointer.get("expected_files") != 1
        or hf_pointer.get("exact_files") != 0
        or hf_pointer.get("missing_files") != 1
        or hf_pointer.get("conflict_files") != 0
        or hf_pointer.get("unexpected_files") != 0
    ):
        raise ReadinessError("document origin HF dry-run/preflight contract failed")

    fetch_policy = fetch_cohort.get("policy") or {}
    fetch_run_totals = fetch_run.get("totals") or {}
    fetch_run_performance = fetch_run.get("performance") or {}
    fetch_validation_checks = fetch_validation.get("checks") or {}
    fetch_selection = fetch_cohort.get("selection") or {}
    fetch_expected_rows = int(fetch_selection.get("rows") or 0)
    fetch_cohort_schema = fetch_cohort.get("schema_version")
    if fetch_cohort_schema == "real_document_fetch_scale_cohort_v2":
        fetch_manifest_rows = len(fetch_cohort.get("rows") or [])
        partitioned_manifest_ok = fetch_expected_rows == 1_000
    elif fetch_cohort_schema == "real_document_fetch_scale_cohort_v3":
        row_manifest = fetch_cohort.get("row_manifest") or {}
        fetch_manifest_rows = int(row_manifest.get("rows") or 0)
        partitioned_manifest_ok = (
            row_manifest.get("layout") == "partitioned_jsonl_gzip_v1"
            and len(row_manifest.get("partitions") or []) > 0
        )
    else:
        fetch_manifest_rows = 0
        partitioned_manifest_ok = False
    if (
        fetch_cohort.get("status") != "ready"
        or fetch_expected_rows < 1_000
        or fetch_manifest_rows != fetch_expected_rows
        or not partitioned_manifest_ok
        or fetch_policy.get("official_real_documents_only") is not True
        or fetch_policy.get("synthetic_or_mock_records_counted") is not False
        or fetch_policy.get("official_public_domain_personal_information_retained")
        is not True
        or fetch_policy.get("known_blocked_rows_selected") != 0
        or fetch_policy.get("official_content_revisions_preserved_and_measured")
        is not True
        or sum(int(value) for value in (fetch_selection.get("hosts") or {}).values())
        != fetch_expected_rows
    ):
        raise ReadinessError("fresh document acquisition cohort contract failed")
    fetch_preflight_checks = fetch_preflight.get("checks") or {}
    if fetch_cohort_schema == "real_document_fetch_scale_cohort_v3" and (
        fetch_preflight.get("schema_version")
        != "real_document_fetch_scale_cohort_preflight_validation_v1"
        or fetch_preflight.get("status") != "ok"
        or fetch_preflight.get("errors") != []
        or int(fetch_preflight.get("error_count") or 0) != 0
        or fetch_preflight.get("cohort_id") != fetch_cohort.get("cohort_id")
        or fetch_preflight.get("cohort_semantic_sha256")
        != fetch_cohort.get("cohort_semantic_sha256")
        or int(fetch_preflight_checks.get("cohort_rows") or 0) != fetch_expected_rows
        or int(fetch_preflight_checks.get("prior_files_rehashed") or 0)
        != fetch_expected_rows
        or int(fetch_preflight_checks.get("source_contract_rows") or 0)
        != fetch_expected_rows
        or int(fetch_preflight_checks.get("known_blocked_host_rows") or 0) != 0
        or int(fetch_preflight_checks.get("preexisting_fetch_rows") or 0) != 0
        or int(fetch_preflight_checks.get("preexisting_document_rows") or 0) != 0
    ):
        raise ReadinessError("fresh document acquisition preflight failed")
    if (
        fetch_run.get("schema_version") != "document_fetch_queue_run_v3"
        or fetch_run.get("status") != "ok"
        or int(fetch_run_totals.get("claimed") or 0) != fetch_expected_rows
        or int(fetch_run_totals.get("succeeded") or 0) != fetch_expected_rows
        or int(fetch_run_totals.get("retried") or 0) != 0
        or int(fetch_run_totals.get("dead") or 0) != 0
        or int(fetch_run_performance.get("network_requests_started") or 0)
        < fetch_expected_rows
        or int(fetch_run_performance.get("network_requests_started") or 0)
        > int(fetch_run_performance.get("network_request_upper_bound") or 0)
    ):
        raise ReadinessError("fresh document acquisition physical run failed")
    if (
        fetch_validation.get("schema_version")
        not in {
            "real_document_fetch_scale_cohort_validation_v2",
            "real_document_fetch_scale_cohort_validation_v3",
        }
        or fetch_validation.get("status") != "ok"
        or fetch_validation.get("errors") != []
        or int(fetch_validation.get("error_count") or 0) != 0
        or int(fetch_validation_checks.get("prior_files_rehashed") or 0)
        != fetch_expected_rows
        or int(fetch_validation_checks.get("fresh_files_rehashed") or 0)
        != fetch_expected_rows
        or fetch_validation_checks.get("prior_capture_byte_hash_integrity") is not True
        or fetch_validation_checks.get("fresh_source_contract_parity") is not True
        or fetch_validation_checks.get("fresh_content_hash_self_consistency")
        is not True
    ):
        raise ReadinessError("fresh document acquisition validation failed")
    fetch_validation_inputs = fetch_validation.get("inputs") or {}
    fetch_preflight_inputs = fetch_preflight.get("inputs") or {}
    if (
        (fetch_validation_inputs.get("manifest") or {}).get("sha256")
        != sha256_file(evidence_paths["fetch_cohort"])
        or (fetch_validation_inputs.get("run_report") or {}).get("sha256")
        != sha256_file(evidence_paths["fetch_run"])
        or (
            fetch_cohort_schema == "real_document_fetch_scale_cohort_v3"
            and (fetch_preflight_inputs.get("manifest") or {}).get("sha256")
            != sha256_file(evidence_paths["fetch_cohort"])
        )
    ):
        raise ReadinessError("fresh document acquisition validation inputs drifted")

    source_universe_policy = source_universe.get("policy") or {}
    source_universe_summary = source_universe.get("summary") or {}
    source_universe_checks = source_universe.get("checks") or {}
    source_universe_edge_counts = source_universe.get("edge_counts") or {}
    source_target_urls = _require_nonnegative_int(
        source_universe_summary.get("numeric_target_urls"),
        "document source universe numeric target",
    )
    source_eligible_urls = _require_nonnegative_int(
        source_universe_summary.get("contract_eligible_physically_healthy_https_urls"),
        "document source universe eligible HTTPS URLs",
    )
    source_target_gap = _require_nonnegative_int(
        source_universe_summary.get("numeric_target_gap_urls"),
        "document source universe target gap",
    )
    source_unique_https_urls = _require_nonnegative_int(
        source_universe_summary.get("unique_https_urls"),
        "document source universe unique HTTPS URLs",
    )
    if (
        source_universe.get("schema_version") != "real_document_source_universe_v1"
        or source_universe.get("status")
        not in {
            "blocked_below_numeric_target",
            "ready_for_numeric_cohort_preparation",
        }
        or source_universe.get("errors") != []
        or source_universe_policy.get("official_real_urls_only") is not True
        or source_universe_policy.get("synthetic_or_mock_records_counted") is not False
        or source_universe_policy.get(
            "official_public_domain_personal_information_retained"
        )
        is not True
        or source_universe_policy.get("network_requests_performed") != 0
        or source_universe_policy.get("known_blocked_hosts_reprobed") is not False
        or source_universe_policy.get("representativeness_inferred") is not False
        or not source_universe_checks
        or not all(value is True for value in source_universe_checks.values())
        or source_target_urls != 100_000
        or source_target_gap != max(0, source_target_urls - source_eligible_urls)
        or source_universe_summary.get("numeric_target_available")
        != (source_eligible_urls >= source_target_urls)
        or source_universe_summary.get("representative_cohort_status")
        != "decision_required_dec_01"
        or sum(
            int((row or {}).get("contract_eligible_https_urls") or 0)
            for row in source_universe.get("hosts") or []
        )
        != source_eligible_urls
        or sum(
            int(value)
            for value in (source_universe.get("category_https_urls") or {}).values()
        )
        != source_unique_https_urls
    ):
        raise ReadinessError("document source universe contract failed")
    source_universe_inputs = source_universe.get("inputs") or {}
    audit_edge_manifest = audit.get("edge_manifest") or {}
    for key in (
        "provenance_audit",
        "edge_manifest",
        "host_health",
        "acquisition_validation",
    ):
        input_descriptor = source_universe_inputs.get(key) or {}
        input_path = repo_path(str(input_descriptor.get("path") or ""))
        if (
            input_descriptor.get("sha256") != sha256_file(input_path)
            or int(input_descriptor.get("bytes") or -1) != input_path.stat().st_size
        ):
            raise ReadinessError(f"document source universe {key} input drifted")
    obstruction_descriptor = source_universe_inputs.get("obstruction_snapshot") or {}
    obstruction_path = repo_path(str(obstruction_descriptor.get("path") or ""))
    if obstruction_descriptor != obstruction_projection_descriptor(
        obstruction_path, load_json(obstruction_path)
    ):
        raise ReadinessError(
            "document source universe obstruction classification input drifted"
        )
    if (
        (source_universe_inputs.get("provenance_audit") or {}).get("sha256")
        != sha256_file(evidence_paths["audit"])
        or (source_universe_inputs.get("acquisition_validation") or {}).get("sha256")
        != sha256_file(evidence_paths["fetch_validation"])
        or (source_universe_inputs.get("edge_manifest") or {}).get("sha256")
        != audit_edge_manifest.get("sha256")
        or int(source_universe_edge_counts.get("edge_rows") or 0)
        != int(audit_edge_manifest.get("rows") or -1)
    ):
        raise ReadinessError("document source universe authority inputs drifted")
    source_validation_checks = source_universe_validation.get("checks") or {}
    source_validation_summary = source_universe_validation.get("summary") or {}
    source_validation_inputs = source_universe_validation.get("inputs") or {}
    source_validation_eligible_urls = _require_nonnegative_int(
        source_validation_summary.get(
            "contract_eligible_physically_healthy_https_urls"
        ),
        "document source universe validation eligible HTTPS URLs",
    )
    source_validation_target_gap = _require_nonnegative_int(
        source_validation_summary.get("numeric_target_gap_urls"),
        "document source universe validation numeric target gap",
    )
    if (
        source_universe_validation.get("schema_version")
        != "real_document_source_universe_validation_v1"
        or source_universe_validation.get("status") != "ok"
        or source_universe_validation.get("errors") != []
        or (source_validation_inputs.get("report") or {}).get("sha256")
        != sha256_file(evidence_paths["source_universe"])
        or (source_validation_inputs.get("edge_manifest") or {}).get("sha256")
        != audit_edge_manifest.get("sha256")
        or int(source_validation_checks.get("edge_rows_replayed") or 0)
        != int(source_universe_edge_counts.get("edge_rows") or -1)
        or int(source_validation_checks.get("unique_https_urls_replayed") or 0)
        != source_unique_https_urls
        or not all(
            source_validation_checks.get(key) is True
            for key in (
                "input_descriptors_exact",
                "host_counts_exact",
                "contract_eligible_urls_exact",
                "physical_health_bound",
                "numeric_target_math_exact",
                "representativeness_not_inferred",
                "real_data_policy_enforced",
            )
        )
        or source_validation_eligible_urls != source_eligible_urls
        or source_validation_target_gap != source_target_gap
    ):
        raise ReadinessError("document source universe independent validation failed")

    economics_meta = economics.get("meta") or {}
    economics_policy = economics.get("policy") or {}
    if (
        economics_meta.get("schema_version") != "document_factory_economics_v1"
        or economics_meta.get("status") != "partial_measured_local"
        or not all(value is True for value in (economics.get("checks") or {}).values())
        or economics_policy.get("synthetic_or_mock_records") != "forbidden"
        or economics_policy.get("public_domain_personal_information") != "retained"
        or economics_policy.get("unmeasured_values") != "null_not_zero"
        or economics != economics_evidence
    ):
        raise ReadinessError("document economics contract failed")
    if (
        economics_validation.get("schema_version")
        != "document_factory_economics_validation_v1"
        or economics_validation.get("status") != "ok"
        or economics_validation.get("errors") != []
    ):
        raise ReadinessError("document economics independent validation failed")
    economics_validation_inputs = economics_validation.get("inputs") or {}
    if (
        (economics_validation_inputs.get("public_artifact") or {}).get("sha256")
        != sha256_file(evidence_paths["economics"])
        or (economics_validation_inputs.get("evidence_copy") or {}).get("sha256")
        != sha256_file(evidence_paths["economics_evidence"])
        or (economics_validation_inputs.get("fresh_acquisition_run") or {}).get(
            "sha256"
        )
        != sha256_file(evidence_paths["fetch_run"])
        or (economics_validation_inputs.get("fresh_acquisition_validation") or {}).get(
            "sha256"
        )
        != sha256_file(evidence_paths["fetch_validation"])
    ):
        raise ReadinessError("document economics validation inputs have drifted")

    verified_files = _require_nonnegative_int(
        audit_totals.get("verified_checksum_files"),
        "document verified checksum files",
    )
    public_url_files = _require_nonnegative_int(
        audit_totals.get("files_with_public_url"),
        "document public URL files",
    )
    unlinked_files = _require_nonnegative_int(
        audit_totals.get("unlinked"), "document unlinked files"
    )
    checksum_gap_files = _require_nonnegative_int(
        queue_totals.get("checksum_lineage_gaps"),
        "document checksum lineage gaps",
    )
    public_url_gap_files = _require_nonnegative_int(
        queue_totals.get("public_url_gaps"),
        "document public URL gaps",
    )
    queue_rows = _require_nonnegative_int(
        queue_totals.get("queue_rows"), "document queue rows"
    )
    if verified_files + checksum_gap_files != eligible_files:
        raise ReadinessError("document checksum coverage does not balance")
    if public_url_files + public_url_gap_files != eligible_files:
        raise ReadinessError("document public URL coverage does not balance")
    if unlinked_files != checksum_gap_files:
        raise ReadinessError(
            "document audit unlinked total does not match checksum gaps"
        )
    if not (
        max(checksum_gap_files, public_url_gap_files)
        <= queue_rows
        <= checksum_gap_files + public_url_gap_files
    ):
        raise ReadinessError("document remediation queue does not balance gap union")

    inventory_manifest = inventory.get("manifest") or {}
    audit_inventory = audit.get("inventory") or {}
    if inventory_manifest.get("sha256") != audit_inventory.get(
        "sha256"
    ) or inventory_manifest.get("rows") != audit_inventory.get("rows"):
        raise ReadinessError("document inventory and provenance audit drifted")
    queue_audit = (queue.get("inputs") or {}).get("audit_report") or {}
    if queue_audit.get("sha256") != sha256_file(evidence_paths["audit"]):
        raise ReadinessError("document queue was not built from the current audit")
    wayback_inputs = wayback_recovery.get("inputs") or {}
    wayback_gap_queue = wayback_inputs.get("gap_queue") or {}
    queue_artifact = queue.get("queue") or {}
    if wayback_gap_queue.get("sha256") != queue_artifact.get(
        "sha256"
    ) or wayback_gap_queue.get("bytes") != queue_artifact.get("bytes"):
        raise ReadinessError("Wayback recovery did not use the current gap queue")
    wayback_manifest = wayback_recovery.get("manifest") or {}
    wayback_manifest_path = evidence_paths["wayback_manifest"]
    if (
        wayback_manifest.get("path") != contract["wayback_manifest"]
        or wayback_manifest.get("sha256") != sha256_file(wayback_manifest_path)
        or wayback_manifest.get("bytes") != wayback_manifest_path.stat().st_size
    ):
        raise ReadinessError("Wayback recovery manifest has drifted")
    wayback_checkpoint = wayback_recovery.get("checkpoint") or {}
    wayback_checkpoint_path = evidence_paths["wayback_checkpoint"]
    if (
        wayback_checkpoint.get("path") != contract["wayback_checkpoint"]
        or wayback_checkpoint.get("sha256") != sha256_file(wayback_checkpoint_path)
        or wayback_checkpoint.get("bytes") != wayback_checkpoint_path.stat().st_size
    ):
        raise ReadinessError("Wayback recovery checkpoint has drifted")
    checkpoint_rows: list[dict[str, Any]] = []
    with wayback_checkpoint_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                checkpoint_row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReadinessError(
                    f"invalid Wayback checkpoint row {line_number}: {exc}"
                ) from exc
            if not isinstance(checkpoint_row, dict):
                raise ReadinessError(
                    f"Wayback checkpoint row {line_number} is not an object"
                )
            if (
                checkpoint_row.get("schema_version") != "wayback_document_checkpoint_v1"
                or checkpoint_row.get("record_type")
                not in {
                    "metadata",
                    "target",
                    "target_path",
                    "cdx_query",
                    "archive_candidate",
                }
                or checkpoint_row.get("synthetic_or_mock_records_counted") is not False
                or checkpoint_row.get("public_domain_personal_information_retained")
                is not True
                or checkpoint_row.get("remote_mutation_performed") is not False
            ):
                raise ReadinessError(
                    f"Wayback checkpoint row {line_number} violates policy"
                )
            reject_disallowed_evidence(
                checkpoint_row, f"Wayback checkpoint row {line_number}"
            )
            checkpoint_rows.append(checkpoint_row)
    if len(checkpoint_rows) != wayback_checkpoint.get("rows"):
        raise ReadinessError("Wayback checkpoint row count has drifted")
    boe_manifest = boe_corpus.get("manifest") or {}
    boe_manifest_path = evidence_paths["boe_manifest"]
    if (
        boe_manifest.get("path") != contract["boe_manifest"]
        or boe_manifest.get("schema_version")
        != "boe_document_corpus_lineage_manifest_v1"
        or boe_manifest.get("layout") != "partitioned_jsonl_gzip_v1"
        or boe_manifest.get("sha256") != sha256_file(boe_manifest_path)
        or boe_manifest.get("bytes") != boe_manifest_path.stat().st_size
    ):
        raise ReadinessError("BOE document corpus manifest has drifted")
    boe_documents = boe_corpus.get("documents") or {}
    boe_rows = _require_nonnegative_int(boe_documents.get("rows"), "BOE document rows")
    if (
        boe_rows < 1
        or boe_manifest.get("rows") != boe_rows
        or boe_manifest.get("distinct_content_objects")
        != boe_documents.get("distinct_content_objects")
        or boe_manifest.get("document_bytes") != boe_documents.get("bytes")
    ):
        raise ReadinessError("BOE document corpus totals do not reconcile")
    boe_manifest_validation_input = boe_manifest_validation.get("input") or {}
    boe_manifest_validation_totals = boe_manifest_validation.get("totals") or {}
    if (
        boe_manifest_validation.get("schema_version")
        != "boe_document_corpus_lineage_validation_v1"
        or boe_manifest_validation.get("status") != "ok"
        or not all(
            value is True
            for value in (boe_manifest_validation.get("checks") or {}).values()
        )
        or (boe_manifest_validation.get("mode") or {}).get("full_raw_check") is not True
        or boe_manifest_validation_input.get("path") != contract["boe_manifest"]
        or boe_manifest_validation_input.get("sha256") != boe_manifest.get("sha256")
        or boe_manifest_validation_input.get("bytes") != boe_manifest.get("bytes")
        or boe_manifest_validation_totals.get("rows") != boe_rows
        or boe_manifest_validation_totals.get("document_bytes")
        != boe_documents.get("bytes")
        or boe_manifest_validation_totals.get("distinct_content_objects")
        != boe_documents.get("distinct_content_objects")
        or boe_manifest_validation_totals.get("logical_sha256")
        != boe_manifest.get("logical_sha256")
        or boe_manifest_validation_totals.get("shard_files")
        != boe_manifest.get("shard_files")
    ):
        raise ReadinessError("BOE partitioned manifest validation failed")
    boe_generation_input = boe_generation_audit.get("input") or {}
    boe_generation_policy = boe_generation_audit.get("policy") or {}
    boe_generation_totals = boe_generation_audit.get("totals") or {}
    if (
        boe_generation_audit.get("schema_version")
        != "boe_document_corpus_generation_audit_v1"
        or boe_generation_audit.get("status") != "ok"
        or not all(
            value is True
            for value in (boe_generation_audit.get("checks") or {}).values()
        )
        or (boe_generation_audit.get("mode") or {}).get("full_shard_check") is not True
        or boe_generation_input.get("path") != contract["boe_manifest"]
        or boe_generation_input.get("sha256") != boe_manifest.get("sha256")
        or boe_generation_input.get("bytes") != boe_manifest.get("bytes")
        or boe_generation_input.get("logical_sha256")
        != boe_manifest.get("logical_sha256")
        or boe_generation_policy.get("synthetic_or_mock_records_counted") is not False
        or boe_generation_policy.get(
            "official_public_domain_personal_information_retained"
        )
        is not True
        or boe_generation_policy.get("automatic_deletion_forbidden") is not True
        or boe_generation_policy.get("remote_mutation_performed") is not False
        or boe_generation_totals.get("active_generations") != 1
        or boe_generation_totals.get("unactivated_manifest_archives") != 0
        or boe_generation_totals.get("unactivated_generation_directories") != 0
        or boe_generation_totals.get("orphan_generation_directories") != 0
        or boe_generation_totals.get("interrupted_staging_directories") != 0
        or boe_generation_totals.get("automatic_deletions") != 0
    ):
        raise ReadinessError("BOE generation lifecycle audit failed")
    boe_audit_manifests = audit.get("boe_document_corpus_lineage_manifests") or []
    if (
        len(boe_audit_manifests) != 1
        or boe_audit_manifests[0].get("sha256") != boe_manifest.get("sha256")
        or boe_audit_manifests[0].get("accepted_checksum_captures") != boe_rows
    ):
        raise ReadinessError("provenance audit did not load the BOE corpus manifest")
    wayback_audit_manifests = audit.get("wayback_document_lineage_manifests") or []
    if len(wayback_audit_manifests) != 1 or wayback_audit_manifests[0].get(
        "sha256"
    ) != wayback_manifest.get("sha256"):
        raise ReadinessError("provenance audit did not load the Wayback manifest")
    wayback_totals = wayback_recovery.get("totals") or {}
    seeded_gap_files = _require_nonnegative_int(
        wayback_totals.get("eligible_gap_file_instances"),
        "Wayback eligible gap files",
    )
    unseeded_gap_files = _require_nonnegative_int(
        wayback_totals.get("unseeded_gap_file_instances"),
        "Wayback unseeded gap files",
    )
    exact_archive_relations = _require_nonnegative_int(
        wayback_totals.get("exact_archive_relations"),
        "Wayback exact archive relations",
    )
    checkpoint_counts: dict[str, int] = {}
    checkpoint_target_keys: set[str] = set()
    checkpoint_path_target_keys: set[str] = set()
    for checkpoint_row in checkpoint_rows:
        record_type = str(checkpoint_row["record_type"])
        checkpoint_counts[record_type] = checkpoint_counts.get(record_type, 0) + 1
        if record_type == "target":
            if (
                checkpoint_row.get("source_id")
                not in {"europarl_meps", "senado_votaciones"}
                or not isinstance(checkpoint_row.get("expected_sha256"), str)
                or len(checkpoint_row["expected_sha256"]) != 64
                or not isinstance(checkpoint_row.get("expected_bytes"), int)
                or checkpoint_row["expected_bytes"] <= 0
                or not isinstance(checkpoint_row.get("target_key"), str)
                or len(checkpoint_row["target_key"]) != 64
            ):
                raise ReadinessError("Wayback checkpoint contains an invalid target")
            checkpoint_target_keys.add(checkpoint_row["target_key"])
        if record_type == "target_path":
            capture_path = PurePosixPath(str(checkpoint_row.get("capture_path") or ""))
            if (
                capture_path.is_absolute()
                or ".." in capture_path.parts
                or not checkpoint_row.get("target_key")
            ):
                raise ReadinessError(
                    "Wayback checkpoint contains an invalid target path"
                )
            checkpoint_path_target_keys.add(str(checkpoint_row["target_key"]))
        if (
            record_type == "archive_candidate"
            and checkpoint_row.get("downloaded_sha256") not in {None, ""}
            and (
                not isinstance(checkpoint_row.get("downloaded_sha256"), str)
                or len(checkpoint_row["downloaded_sha256"]) != 64
            )
        ):
            raise ReadinessError(
                "Wayback checkpoint contains an invalid downloaded checksum"
            )
    queue_by_source = queue.get("by_source_group") or {}
    evidence_seeded_queue_files = _require_nonnegative_int(
        (queue_by_source.get("europarl_meps") or {}).get("rows"),
        "Europarliament archive-seeded gaps",
    ) + _require_nonnegative_int(
        (queue_by_source.get("manual") or {}).get("rows"),
        "Senate archive-seeded gaps",
    )
    if (
        seeded_gap_files != evidence_seeded_queue_files
        or seeded_gap_files + unseeded_gap_files != queue_rows
        or wayback_manifest.get("rows") != exact_archive_relations
        or wayback_audit_manifests[0].get("accepted_checksum_relations")
        != exact_archive_relations
        or checkpoint_counts.get("target", 0)
        != wayback_totals.get("unique_expected_content_targets")
        or checkpoint_counts.get("target_path", 0) != seeded_gap_files
        or checkpoint_counts.get("archive_candidate", 0)
        != wayback_totals.get("archive_candidates_indexed")
        or checkpoint_counts.get("metadata", 0) != 1
        or checkpoint_path_target_keys != checkpoint_target_keys
        or checkpoint_counts.get("cdx_query", 0)
        != sum(
            (wayback_recovery.get("state") or {}).get("cdx_query_states", {}).values()
        )
        or checkpoint_counts.get("archive_candidate", 0)
        != sum(
            (wayback_recovery.get("state") or {}).get("candidate_states", {}).values()
        )
    ):
        raise ReadinessError("Wayback recovery totals do not reconcile")

    distinct_content = _require_nonnegative_int(
        inventory_totals.get("distinct_content_objects"),
        "document distinct content objects",
    )
    excluded_non_real = _require_nonnegative_int(
        inventory_totals.get("excluded_non_real_files"),
        "document excluded non-real files",
    )
    excluded_transport_failures = _require_nonnegative_int(
        inventory_totals.get("excluded_non_accountability_capture_files"),
        "document excluded transport-failure captures",
    )
    raw_document_files_discovered = _require_nonnegative_int(
        inventory_totals.get("raw_document_files_discovered"),
        "raw document files discovered",
    )
    if raw_document_files_discovered != (
        eligible_files + excluded_non_real + excluded_transport_failures
    ):
        raise ReadinessError("document discovery and eligibility totals do not balance")
    inventory_checks = inventory.get("checks") or {}
    if not inventory_checks.get(
        "transport_failures_excluded_from_accountability_scale"
    ):
        raise ReadinessError(
            "document transport failures are not excluded from accountability scale"
        )
    if not inventory_checks.get("sample_content_fingerprints_excluded"):
        raise ReadinessError(
            "document copied sample-content fingerprints are not excluded"
        )
    text_artifacts = audit.get("text_artifacts") or {}
    text_artifacts_verified = _require_nonnegative_int(
        text_artifacts.get("checksum_verified"),
        "document text artifacts verified",
    )

    native_totals = native_extraction.get("totals") or {}
    native_validation_totals = native_validation.get("totals") or {}
    native_file_instances = _require_nonnegative_int(
        native_totals.get("file_instances"), "native text file instances"
    )
    native_distinct_content = _require_nonnegative_int(
        native_totals.get("distinct_content_objects"),
        "native text distinct content objects",
    )
    native_chars = _require_nonnegative_int(
        native_totals.get("native_text_chars"), "native text characters"
    )
    native_truncated = _require_nonnegative_int(
        native_totals.get("native_truncated_objects"),
        "native text truncated objects",
    )
    native_cas_files = _require_nonnegative_int(
        native_totals.get("text_cas_files"), "native text CAS files"
    )
    if native_file_instances != eligible_files:
        raise ReadinessError("native text file instances do not cover the inventory")
    if native_distinct_content != distinct_content:
        raise ReadinessError("native text content objects do not cover the inventory")
    if native_truncated:
        raise ReadinessError("native text extraction contains truncated objects")
    native_validation_expected = {
        "file_instances": native_file_instances,
        "distinct_content_objects": native_distinct_content,
        "native_text_chars": native_chars,
        "native_truncated_objects": 0,
        "raw_files_checksum_verified": eligible_files,
        "text_cas_objects_checksum_verified": native_cas_files,
        "text_cas_files_observed": native_cas_files,
        "provenance_gap_instances": unlinked_files,
        "public_url_instances": public_url_files,
    }
    for key, expected in native_validation_expected.items():
        if (
            _require_nonnegative_int(
                native_validation_totals.get(key), f"native validation {key}"
            )
            != expected
        ):
            raise ReadinessError(f"native validation {key} does not reconcile")
    native_retained_cas_expected = _require_nonnegative_int(
        native_validation_totals.get(
            "text_cas_files_expected_across_retained_generations"
        ),
        "native retained text CAS expected",
    )
    native_retained_cas_observed = _require_nonnegative_int(
        native_validation_totals.get(
            "text_cas_files_observed_across_retained_generations"
        ),
        "native retained text CAS observed",
    )
    if (
        native_retained_cas_expected != native_retained_cas_observed
        or native_retained_cas_expected < native_cas_files
        or _require_nonnegative_int(
            native_totals.get("text_cas_files_observed_across_retained_generations"),
            "native producer retained text CAS observed",
        )
        != native_retained_cas_observed
    ):
        raise ReadinessError("native retained CAS generations do not reconcile")
    native_report_input = (native_validation.get("inputs") or {}).get(
        "extraction_report"
    ) or {}
    if native_report_input.get("sha256") != sha256_file(
        evidence_paths["native_extraction"]
    ):
        raise ReadinessError("native validation was not built from the current run")

    locator_totals = text_locators.get("totals") or {}
    locator_validation_totals = text_locator_validation.get("totals") or {}
    locator_inputs = text_locators.get("inputs") or {}
    locator_validation_inputs = text_locator_validation.get("inputs") or {}
    locator_manifest = text_locators.get("manifest") or {}
    locator_native_input = locator_inputs.get("native_manifest") or {}
    locator_validation_native_input = (
        locator_validation_inputs.get("native_manifest") or {}
    )
    locator_validation_manifest_input = (
        locator_validation_inputs.get("locator_manifest") or {}
    )
    locator_validation_report_input = (
        locator_validation_inputs.get("locator_report") or {}
    )
    locator_content_rows = _require_nonnegative_int(
        locator_totals.get("content_locator_rows"), "native text content locators"
    )
    locator_instance_rows = _require_nonnegative_int(
        locator_totals.get("instance_locator_rows"), "native text instance locators"
    )
    locator_pdf_pages = _require_nonnegative_int(
        locator_totals.get("pdf_page_locators"), "native text PDF page locators"
    )
    locator_span_rows = _require_nonnegative_int(
        locator_totals.get("normalized_text_span_locators"),
        "native text normalized-span locators",
    )
    if (
        _require_nonnegative_int(
            locator_totals.get("file_instances"), "locator file instances"
        )
        != native_file_instances
        or _require_nonnegative_int(
            locator_totals.get("distinct_content_objects"),
            "locator distinct content objects",
        )
        != native_distinct_content
        or _require_nonnegative_int(
            locator_totals.get("native_text_chars"), "locator native text chars"
        )
        != native_chars
        or locator_content_rows != locator_pdf_pages + locator_span_rows
        or locator_manifest.get("rows") != locator_instance_rows
        or locator_native_input.get("path") != native_current_manifest.get("path")
        or locator_native_input.get("sha256")
        != native_current_manifest.get("sha256")
        or locator_validation_native_input.get("path")
        != native_current_manifest.get("path")
        or locator_validation_native_input.get("sha256")
        != native_current_manifest.get("sha256")
        or locator_validation_manifest_input.get("sha256")
        != locator_manifest.get("sha256")
        or locator_validation_manifest_input.get("logical_sha256")
        != locator_manifest.get("logical_sha256")
        or locator_validation_report_input.get("sha256")
        != sha256_file(evidence_paths["text_locators"])
        or locator_validation_report_input.get("bytes")
        != evidence_paths["text_locators"].stat().st_size
    ):
        raise ReadinessError("native text locator inputs or totals drifted")
    for key, expected in {
        "native_file_instances": native_file_instances,
        "distinct_content_objects": native_distinct_content,
        "content_objects_replayed": native_distinct_content,
        "replayed_content_locator_rows": locator_content_rows,
        "expected_instance_locator_rows": locator_instance_rows,
        "observed_instance_locator_rows": locator_instance_rows,
        "missing_rows": 0,
        "unexpected_rows": 0,
        "mismatched_rows": 0,
        "validation_failures": 0,
    }.items():
        if (
            _require_nonnegative_int(
                locator_validation_totals.get(key), f"text locator validation {key}"
            )
            != expected
        ):
            raise ReadinessError(f"text locator validation {key} does not reconcile")

    profile_totals = document_profile.get("totals") or {}
    profile_validation_totals = document_profile_validation.get("totals") or {}
    profile_inputs = document_profile.get("inputs") or {}
    profile_validation_inputs = document_profile_validation.get("inputs") or {}
    profile_manifest = document_profile.get("manifest") or {}
    profile_validation_manifest = (
        profile_validation_inputs.get("profile_manifest") or {}
    )
    profile_validation_report = profile_validation_inputs.get("profile_report") or {}
    native_profile_input = profile_inputs.get("native_manifest") or {}
    machine_status_counts = (
        document_profile.get("by_machine_language_status_content_objects") or {}
    )
    language_evidence_counts = (
        document_profile.get("by_language_evidence_status_content_objects") or {}
    )
    language_review_counts = (
        document_profile.get("by_language_review_status_content_objects") or {}
    )
    encryption_counts = (
        document_profile.get("by_encryption_status_file_instances") or {}
    )
    profile_file_instances = _require_nonnegative_int(
        profile_totals.get("file_instances"), "document profile file instances"
    )
    profile_distinct_content = _require_nonnegative_int(
        profile_totals.get("distinct_content_objects"),
        "document profile distinct content objects",
    )
    profile_pdf_instances = _require_nonnegative_int(
        profile_totals.get("pdf_file_instances"), "document profile PDF instances"
    )
    profile_machine_candidates = _require_nonnegative_int(
        profile_totals.get("machine_language_candidate_file_instances"),
        "document profile machine-language candidates",
    )
    profile_unknown_language = _require_nonnegative_int(
        profile_totals.get("unknown_language_file_instances"),
        "document profile unknown-language instances",
    )
    if (
        profile_file_instances != eligible_files
        or profile_distinct_content != distinct_content
        or profile_pdf_instances
        != _require_nonnegative_int(inventory_totals.get("pdf_files"), "PDF files")
        or profile_machine_candidates + profile_unknown_language != eligible_files
        or sum(
            _require_nonnegative_int(value, "machine-language status count")
            for value in machine_status_counts.values()
        )
        != distinct_content
        or sum(
            _require_nonnegative_int(value, "language evidence count")
            for value in language_evidence_counts.values()
        )
        != distinct_content
        or language_review_counts != {"unreviewed": distinct_content}
        or sum(
            _require_nonnegative_int(value, "encryption status count")
            for value in encryption_counts.values()
        )
        != eligible_files
        or _require_nonnegative_int(
            encryption_counts.get("encrypted"), "encrypted PDF instances"
        )
        + _require_nonnegative_int(
            encryption_counts.get("not_encrypted"), "unencrypted PDF instances"
        )
        != profile_pdf_instances
    ):
        raise ReadinessError("document language/encryption profile totals drifted")
    if (
        native_profile_input.get("sha256") != native_current_manifest.get("sha256")
        or native_profile_input.get("path") != native_current_manifest.get("path")
        or profile_validation_manifest.get("sha256") != profile_manifest.get("sha256")
        or profile_validation_manifest.get("logical_sha256")
        != profile_manifest.get("logical_sha256")
        or profile_validation_report.get("sha256")
        != sha256_file(evidence_paths["document_profile"])
        or profile_validation_report.get("bytes")
        != evidence_paths["document_profile"].stat().st_size
        or _require_nonnegative_int(
            profile_validation_totals.get("native_file_instances"),
            "document profile validation native instances",
        )
        != eligible_files
        or _require_nonnegative_int(
            profile_validation_totals.get("profile_file_instances"),
            "document profile validation profile instances",
        )
        != eligible_files
        or _require_nonnegative_int(
            profile_validation_totals.get("distinct_content_objects"),
            "document profile validation content objects",
        )
        != distinct_content
        or _require_nonnegative_int(
            profile_validation_totals.get("content_objects_rehashed_and_reclassified"),
            "document profile replayed content objects",
        )
        != distinct_content
        or profile_validation_totals.get("file_set_mismatches") != 0
        or profile_validation_totals.get("validation_failures") != 0
    ):
        raise ReadinessError("document language/encryption validation drifted")

    expected_ocr_pages = _require_nonnegative_int(
        inventory_totals.get("pdf_pages_empty"), "empty PDF pages"
    ) + _require_nonnegative_int(
        inventory_totals.get("pdf_pages_sparse_ocr_candidate"),
        "sparse PDF pages",
    )
    if (
        _require_nonnegative_int(
            native_totals.get("ocr_candidate_pages"), "native OCR candidate pages"
        )
        != expected_ocr_pages
    ):
        raise ReadinessError("native OCR routing does not reconcile to inventory")
    page_ocr_totals = page_ocr.get("totals") or {}
    page_ocr_validation_totals = page_ocr_validation.get("totals") or {}
    ocr_pages = _require_nonnegative_int(
        page_ocr_totals.get("candidate_pages"), "OCR candidate pages"
    )
    ocr_documents = _require_nonnegative_int(
        page_ocr_totals.get("documents"), "OCR documents"
    )
    ocr_chars = _require_nonnegative_int(
        page_ocr_totals.get("ocr_text_chars"), "OCR text characters"
    )
    ocr_improved_pages = _require_nonnegative_int(
        page_ocr_totals.get("pages_improved_over_native_by_50_chars"),
        "OCR materially improved pages",
    )
    ocr_cas_files = _require_nonnegative_int(
        page_ocr_totals.get("ocr_text_cas_files"), "OCR text CAS files"
    )
    if ocr_pages != expected_ocr_pages:
        raise ReadinessError("OCR pages do not cover every routed candidate")
    for key, expected in {
        "candidate_pages": ocr_pages,
        "documents": ocr_documents,
        "ocr_text_chars": ocr_chars,
        "pages_improved_over_native_by_50_chars": ocr_improved_pages,
        "source_documents_checksum_verified": ocr_documents,
        "ocr_text_cas_objects_checksum_verified": ocr_cas_files,
        "ocr_text_cas_files_observed": ocr_cas_files,
    }.items():
        if (
            _require_nonnegative_int(
                page_ocr_validation_totals.get(key), f"OCR validation {key}"
            )
            != expected
        ):
            raise ReadinessError(f"OCR validation {key} does not reconcile")
    native_manifest = (native_validation.get("inputs") or {}).get("manifest") or {}
    ocr_native_manifest = (page_ocr.get("inputs") or {}).get("native_manifest") or {}
    if (
        ocr_native_manifest.get("sha256") != native_manifest.get("sha256")
        or ocr_native_manifest.get("rows") != eligible_files
    ):
        raise ReadinessError("OCR was not built from the current native manifest")
    ocr_report_input = (page_ocr_validation.get("inputs") or {}).get("ocr_report") or {}
    if ocr_report_input.get("sha256") != sha256_file(evidence_paths["page_ocr"]):
        raise ReadinessError("OCR validation was not built from the current run")

    ocr_manifest = page_ocr.get("manifest") or {}
    review_input = ocr_review.get("input") or {}
    if (
        review_input.get("sha256") != ocr_manifest.get("sha256")
        or review_input.get("rows") != ocr_pages
    ):
        raise ReadinessError("OCR review queue does not bind the current manifest")
    review_queue = ocr_review.get("queue") or {}
    review_csv_path = evidence_paths["ocr_review_csv"]
    review_validation_inputs = ocr_review_validation.get("inputs") or {}
    review_queue_report_input = review_validation_inputs.get("queue_report") or {}
    review_csv_input = review_validation_inputs.get("review_csv") or {}
    if (
        review_queue_report_input.get("sha256")
        != sha256_file(evidence_paths["ocr_review"])
        or review_csv_input.get("sha256") != sha256_file(review_csv_path)
        or review_csv_input.get("bytes") != review_csv_path.stat().st_size
    ):
        raise ReadinessError("OCR human-review validation inputs have drifted")
    with review_csv_path.open(newline="", encoding="utf-8") as handle:
        review_reader = csv.DictReader(handle)
        review_fields = list(review_reader.fieldnames or [])
        review_rows = list(review_reader)
    required_review_fields = {
        "review_id",
        "source_group",
        "document_sha256",
        "document_path",
        "page_number",
        "review_decision",
        "review_notes",
        "reviewer_id",
        "reviewed_at",
    }
    if not review_rows or not required_review_fields.issubset(review_fields):
        raise ReadinessError("OCR human-review CSV contract is incomplete")
    if any(
        not row["review_id"]
        or len(row["document_sha256"]) != 64
        or not row["document_path"]
        or not row["page_number"].isdigit()
        for row in review_rows
    ):
        raise ReadinessError("OCR human-review CSV contains invalid real-page rows")
    review_field_names = {
        "review_decision",
        "review_notes",
        "reviewer_id",
        "reviewed_at",
    }
    assignment_fields = [
        field for field in review_fields if field not in review_field_names
    ]
    assignment_digest = hashlib.sha256()
    for row in review_rows:
        assignment_digest.update(
            json.dumps(
                {field: row[field] for field in assignment_fields},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        assignment_digest.update(b"\n")
    if assignment_digest.hexdigest() != review_queue.get(
        "assignment_sha256"
    ) or assignment_digest.hexdigest() != review_csv_input.get("assignment_sha256"):
        raise ReadinessError("OCR human-review assignments have drifted")
    review_validation_totals = ocr_review_validation.get("totals") or {}
    reviews_completed = _require_nonnegative_int(
        review_validation_totals.get("human_reviews_completed"),
        "OCR human reviews completed",
    )
    reviews_pending = _require_nonnegative_int(
        review_validation_totals.get("human_reviews_pending"),
        "OCR human reviews pending",
    )
    if len(review_rows) != _require_nonnegative_int(
        review_validation_totals.get("review_rows"), "OCR review rows"
    ) or reviews_completed + reviews_pending != len(review_rows):
        raise ReadinessError("OCR human-review totals do not reconcile")
    observed_completed = sum(
        bool(row["review_decision"].strip()) for row in review_rows
    )
    if observed_completed != reviews_completed:
        raise ReadinessError("OCR human-review decisions do not match the report")
    allowed_decisions = set(
        (ocr_review.get("review") or {}).get("allowed_decisions") or []
    )
    for row in review_rows:
        decision = row["review_decision"].strip()
        human_fields = (
            row["review_notes"].strip(),
            row["reviewer_id"].strip(),
            row["reviewed_at"].strip(),
        )
        if decision and (decision not in allowed_decisions or not all(human_fields)):
            raise ReadinessError("OCR completed review row is incomplete or invalid")
        if not decision and any(human_fields):
            raise ReadinessError("OCR pending review row has stray human fields")
    ocr_status_counts = (page_ocr.get("state") or {}).get("ocr_status_counts") or {}
    ocr_text_pages = _require_nonnegative_int(
        ocr_status_counts.get("ocr_text_extracted"), "OCR text pages"
    )
    ocr_no_text_pages = _require_nonnegative_int(
        ocr_status_counts.get("ocr_no_text"), "OCR no-text pages"
    )
    if ocr_text_pages + ocr_no_text_pages != ocr_pages:
        raise ReadinessError("OCR terminal statuses do not balance candidate pages")
    native_economics = economics.get("native_extraction") or {}
    ocr_economics = economics.get("page_ocr") or {}
    acquisition_economics = economics.get("acquisition") or {}
    monetary_economics = economics.get("monetary_cost") or {}
    if (
        not isinstance(native_economics.get("distinct_content_objects"), int)
        or native_economics.get("distinct_content_objects", 0) <= 0
        or not isinstance(ocr_economics.get("candidate_pages"), int)
        or ocr_economics.get("candidate_pages", 0) <= 0
        or acquisition_economics.get("documents_succeeded") != fetch_expected_rows
        or int(acquisition_economics.get("network_requests_started") or 0)
        < fetch_expected_rows
        or int(acquisition_economics.get("network_requests_started") or 0)
        > int(fetch_run_performance.get("network_request_upper_bound") or 0)
        or acquisition_economics.get("failures") != 0
        or acquisition_economics.get("official_hosts")
        != sorted((fetch_selection.get("hosts") or {}).keys())
        or acquisition_economics.get("official_revisions_preserved") is not True
        or acquisition_economics.get("cohort_semantic_sha256")
        != fetch_validation.get("cohort_semantic_sha256")
        or monetary_economics.get("measurement_status") != "unknown_not_measured"
        or monetary_economics.get("actual_amount") is not None
        or monetary_economics.get("cost_per_1000_documents") is not None
        or monetary_economics.get("cost_per_1000_ocr_pages") is not None
    ):
        raise ReadinessError(
            "document economics totals or unknown-cost boundary drifted"
        )
    if not all(value is True for value in (boe_corpus.get("checks") or {}).values()):
        raise ReadinessError("BOE document corpus checks failed")
    return {
        "eligible_real_files": eligible_files,
        "distinct_content_objects": distinct_content,
        "excluded_fixture_or_sample_files": excluded_non_real,
        "excluded_transport_failure_captures": excluded_transport_failures,
        "raw_document_files_discovered": raw_document_files_discovered,
        "verified_checksum_files": verified_files,
        "public_url_files": public_url_files,
        "provenance_coverage": round(verified_files / eligible_files, 8)
        if eligible_files
        else 0.0,
        "unlinked_files": unlinked_files,
        "checksum_lineage_gap_files": checksum_gap_files,
        "public_url_gap_files": public_url_gap_files,
        "remediation_queue_rows": queue_rows,
        "wayback_evidence_seeded_gap_files": seeded_gap_files,
        "wayback_unseeded_gap_files": unseeded_gap_files,
        "wayback_unique_content_targets": _require_nonnegative_int(
            wayback_totals.get("unique_expected_content_targets"),
            "Wayback unique content targets",
        ),
        "wayback_archive_candidates_indexed": _require_nonnegative_int(
            wayback_totals.get("archive_candidates_indexed"),
            "Wayback archive candidates indexed",
        ),
        "wayback_portable_checkpoint_rows": len(checkpoint_rows),
        "wayback_exact_archive_relations": exact_archive_relations,
        "boe_document_corpus_rows": boe_rows,
        "boe_document_corpus_bytes": _require_nonnegative_int(
            boe_documents.get("bytes"), "BOE document bytes"
        ),
        "boe_retained_lineage_generations": _require_nonnegative_int(
            boe_generation_totals.get("retained_unique_generations"),
            "BOE retained lineage generations",
        ),
        "boe_superseded_lineage_generations": _require_nonnegative_int(
            boe_generation_totals.get("superseded_generations"),
            "BOE superseded lineage generations",
        ),
        "boe_lineage_automatic_deletions": _require_nonnegative_int(
            boe_generation_totals.get("automatic_deletions"),
            "BOE lineage automatic deletions",
        ),
        "text_artifacts_checksum_verified": text_artifacts_verified,
        "native_text_file_instances": native_file_instances,
        "native_text_distinct_content_objects": native_distinct_content,
        "native_text_characters": native_chars,
        "native_text_truncated_objects": native_truncated,
        "native_text_cas_objects_checksum_verified": native_cas_files,
        "native_text_retained_cas_objects_checksum_verified": (
            native_retained_cas_observed
        ),
        "native_text_retained_generations": _require_nonnegative_int(
            (native_generation_audit.get("totals") or {}).get(
                "retained_unique_generations"
            ),
            "native text retained generations",
        ),
        "native_text_retained_state_snapshots": _require_nonnegative_int(
            (native_generation_audit.get("totals") or {}).get(
                "retained_state_snapshots"
            ),
            "native text retained state snapshots",
        ),
        "native_text_locator_content_rows": locator_content_rows,
        "native_text_locator_instance_rows": locator_instance_rows,
        "native_text_locator_pdf_pages": locator_pdf_pages,
        "native_text_locator_normalized_spans": locator_span_rows,
        "native_text_locator_replayed_content_objects": _require_nonnegative_int(
            locator_validation_totals.get("content_objects_replayed"),
            "native text locator replayed content objects",
        ),
        "native_text_locator_retained_generations": _require_nonnegative_int(
            (text_locator_generation_audit.get("totals") or {}).get(
                "retained_unique_generations"
            ),
            "native text locator retained generations",
        ),
        "document_profile_file_instances": profile_file_instances,
        "document_profile_distinct_content_objects": profile_distinct_content,
        "document_profile_machine_language_candidates": profile_machine_candidates,
        "document_profile_unknown_language_instances": profile_unknown_language,
        "document_profile_pdf_instances": profile_pdf_instances,
        "document_profile_encrypted_pdf_instances": _require_nonnegative_int(
            profile_totals.get("encrypted_pdf_file_instances"),
            "document profile encrypted PDF instances",
        ),
        "document_profile_replayed_content_objects": _require_nonnegative_int(
            profile_validation_totals.get("content_objects_rehashed_and_reclassified"),
            "document profile replayed content objects",
        ),
        "document_profile_retained_generations": _require_nonnegative_int(
            (document_profile_generation_audit.get("totals") or {}).get(
                "retained_unique_generations"
            ),
            "document profile retained generations",
        ),
        "document_profile_superseded_generations": _require_nonnegative_int(
            (document_profile_generation_audit.get("totals") or {}).get(
                "superseded_generations"
            ),
            "document profile superseded generations",
        ),
        "ocr_documents": ocr_documents,
        "ocr_candidate_pages": ocr_pages,
        "ocr_text_pages": ocr_text_pages,
        "ocr_no_text_pages": ocr_no_text_pages,
        "ocr_text_characters": ocr_chars,
        "ocr_material_gain_pages": ocr_improved_pages,
        "ocr_text_cas_objects_checksum_verified": ocr_cas_files,
        "ocr_retained_generations": _require_nonnegative_int(
            (page_ocr_generation_audit.get("totals") or {}).get(
                "retained_unique_generations"
            ),
            "OCR retained generations",
        ),
        "ocr_retained_state_snapshots": _require_nonnegative_int(
            (page_ocr_generation_audit.get("totals") or {}).get(
                "retained_state_snapshots"
            ),
            "OCR retained state snapshots",
        ),
        "ocr_human_review_rows": len(review_rows),
        "ocr_human_reviews_completed": reviews_completed,
        "ocr_human_reviews_pending": reviews_pending,
        "ocr_human_review_batch_complete": (
            (ocr_review_validation.get("gates") or {}).get("batch_complete") is True
        ),
        "ocr_human_review_promotion_ready": (
            (ocr_review_validation.get("gates") or {}).get("promotion_ready") is True
        ),
        "fresh_acquisition_documents": int(
            acquisition_economics.get("documents_succeeded") or 0
        ),
        "fresh_acquisition_network_requests": int(
            acquisition_economics.get("network_requests_started") or 0
        ),
        "fresh_acquisition_bytes": int(
            acquisition_economics.get("bytes_received") or 0
        ),
        "fresh_acquisition_wall_seconds_per_1000": float(
            (acquisition_economics.get("per_1000_succeeded") or {}).get(
                "elapsed_seconds"
            )
            or 0
        ),
        "fresh_acquisition_cpu_seconds_per_1000": float(
            (acquisition_economics.get("per_1000_succeeded") or {}).get("cpu_seconds")
            or 0
        ),
        "official_source_unique_public_urls": _require_nonnegative_int(
            source_universe_summary.get("unique_public_urls"),
            "document source universe unique public URLs",
        ),
        "official_source_unique_https_urls": source_unique_https_urls,
        "contract_eligible_physically_healthy_https_urls": source_eligible_urls,
        "numeric_100k_source_url_gap": source_target_gap,
        "numeric_100k_source_url_gate_passed": source_eligible_urls
        >= source_target_urls,
        "representative_source_universe_status": source_universe_summary.get(
            "representative_cohort_status"
        ),
        "native_wall_seconds_per_1000": float(
            (native_economics.get("per_1000_distinct_content_objects") or {}).get(
                "elapsed_seconds"
            )
            or 0
        ),
        "native_cpu_seconds_per_1000": float(
            (native_economics.get("per_1000_distinct_content_objects") or {}).get(
                "cpu_seconds"
            )
            or 0
        ),
        "ocr_wall_seconds_per_1000_pages": float(
            (ocr_economics.get("per_1000_candidate_pages") or {}).get("elapsed_seconds")
            or 0
        ),
        "ocr_cpu_seconds_per_1000_pages": float(
            (ocr_economics.get("per_1000_candidate_pages") or {}).get(
                "cpu_seconds_parent_and_children"
            )
            or 0
        ),
        "document_monetary_cost_status": monetary_economics.get("measurement_status"),
        "document_network_requests_measured": True,
        "local_origin_release_id": local_origin_release_manifest.get("release_id"),
        "local_origin_release_files": release_summary.get("release_files"),
        "local_origin_release_bytes": release_summary.get("release_bytes"),
        "local_origin_release_remote_preflight_performed": True,
        "local_origin_release_remote_conflicts": hf_release.get("conflict_files"),
        "local_origin_release_remote_unexpected_files": hf_release.get(
            "unexpected_files"
        ),
        "local_origin_release_remote_publication_performed": False,
        "local_origin_release_durable_public_origin_proven": False,
        "evidence": {
            key: evidence_reference(path) for key, path in evidence_paths.items()
        },
    }


def audit_gap(gap: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(gap, dict) or not gap.get("id"):
        raise ReadinessError("real corpus registry has an invalid gap entry")
    result = dict(gap)
    if result.get("current_evidence"):
        result["evidence"] = result.pop("current_evidence")
    _require_nonnegative_int(result.get("current_real_rows"), "gap current_real_rows")
    target = _require_nonnegative_int(
        result.get("target_real_rows"), "gap target_real_rows"
    )
    if target < 1:
        raise ReadinessError("gap target_real_rows must be positive")
    evidence_refs = result.get("evidence_refs") or []
    if not isinstance(evidence_refs, list):
        raise ReadinessError(f"gap evidence_refs must be a list: {result['id']}")
    if evidence_refs:
        result["evidence_files"] = [
            evidence_reference(repo_path(str(reference))) for reference in evidence_refs
        ]

    contract = result.get("evidence_contract")
    if contract is None:
        return result
    if not isinstance(contract, dict):
        raise ReadinessError(f"gap evidence_contract must be an object: {result['id']}")
    if contract.get("kind") == "document_accountability_v2":
        result["metrics"] = audit_document_provenance_gap(result, contract)
        return result
    if contract.get("kind") in {
        "boe_candidate_accountability_v1",
        "boe_candidate_accountability_v2",
    }:
        semantic_contract = contract.get("kind") == "boe_candidate_accountability_v2"
        report_path = repo_path(str(contract.get("report") or ""))
        correction_report_path = repo_path(str(contract.get("correction_report") or ""))
        database_path = repo_path(str(contract.get("database") or ""))
        report = load_json(report_path)
        correction_report = load_json(correction_report_path)
        if (
            report.get("schema_version") != "boe_election_candidates_run_v1"
            or report.get("status") != "ok"
            or not checks_pass(report, require_status=True)
        ):
            raise ReadinessError("BOE candidate report contract failed")
        policy = report.get("policy") or {}
        required_policy = {
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "identity_fields_removed": 0,
            "cross_source_person_identity_inferred": False,
            "official_corrections_explicit": True,
            "remote_mutation_performed": False,
        }
        if any(
            policy.get(key) != expected for key, expected in required_policy.items()
        ):
            raise ReadinessError("BOE candidate policy contract failed")
        if not isinstance(policy.get("pending_official_corrections_explicit"), bool):
            raise ReadinessError("BOE candidate pending-correction policy is missing")
        if (
            correction_report.get("schema_version")
            != "boe_candidate_correction_materialization_v2"
            or correction_report.get("status") != "ok"
            or not checks_pass(correction_report, require_status=True)
        ):
            raise ReadinessError("BOE candidate correction materialization failed")
        correction_policy = correction_report.get("policy") or {}
        required_correction_policy = {
            "base_proclamation_rows_mutated": False,
            "official_public_domain_personal_information_retained": True,
            "identity_fields_removed": 0,
            "cross_source_person_identity_inferred": False,
            "synthetic_or_mock_records_counted": False,
            "pending_correction_evidence_excluded_from_effective_state": True,
            "remote_mutation_performed": False,
        }
        if any(
            correction_policy.get(key) != expected
            for key, expected in required_correction_policy.items()
        ):
            raise ReadinessError("BOE candidate correction policy contract failed")
        totals = report.get("totals") or {}
        correction_totals = correction_report.get("totals") or {}
        expected_counts = {
            "documents": _require_nonnegative_int(
                totals.get("documents"), "BOE candidate documents"
            ),
            "candidacies": _require_nonnegative_int(
                totals.get("candidacies"), "BOE candidacies"
            ),
            "candidates": _require_nonnegative_int(
                totals.get("candidates"), "BOE candidate occurrences"
            ),
            "correction_documents": _require_nonnegative_int(
                totals.get("distinct_correction_documents"),
                "BOE candidate correction documents",
            ),
            "correction_targets": _require_nonnegative_int(
                totals.get("correction_target_relations"),
                "BOE candidate correction targets",
            ),
            "correction_paragraphs": _require_nonnegative_int(
                totals.get("correction_paragraphs"),
                "BOE candidate correction paragraphs",
            ),
        }
        expected_effective_candidates = _require_nonnegative_int(
            correction_totals.get("effective_candidates"),
            "BOE effective candidate occurrences",
        )
        if expected_effective_candidates != int(result["current_real_rows"]):
            raise ReadinessError("BOE candidate registry count drifted")
        if not database_path.is_file():
            raise ReadinessError("BOE candidate database is missing")
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        try:
            observed_counts = {
                "documents": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM boe_election_candidate_documents"
                    ).fetchone()[0]
                ),
                "candidacies": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM boe_election_candidacies"
                    ).fetchone()[0]
                ),
                "candidates": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM boe_election_candidate_occurrences"
                    ).fetchone()[0]
                ),
                "correction_documents": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM boe_election_candidate_correction_documents"
                    ).fetchone()[0]
                ),
                "correction_targets": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM boe_election_candidate_correction_targets"
                    ).fetchone()[0]
                ),
                "correction_paragraphs": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM boe_election_candidate_correction_paragraphs"
                    ).fetchone()[0]
                ),
            }
            reviewed_base_counts = {
                "documents": int(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_candidate_documents
                        WHERE correction_state IN ('none_declared', 'applied')
                        """
                    ).fetchone()[0]
                ),
                "candidacies": int(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_candidacies AS candidacy
                        JOIN boe_election_candidate_documents AS document
                          ON document.document_id=candidacy.document_id
                        WHERE document.correction_state IN (
                          'none_declared', 'applied'
                        )
                        """
                    ).fetchone()[0]
                ),
                "candidates": int(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM boe_election_candidate_occurrences AS candidate
                        JOIN boe_election_candidate_documents AS document
                          ON document.document_id=candidate.document_id
                        WHERE document.correction_state IN (
                          'none_declared', 'applied'
                        )
                        """
                    ).fetchone()[0]
                ),
            }
            pending_base_counts = {
                key: observed_counts[key] - reviewed_base_counts[key]
                for key in ("documents", "candidacies", "candidates")
            }
            missing_public_identity = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM boe_election_candidate_occurrences
                    WHERE TRIM(full_name) = '' OR TRIM(source_text_exact) = ''
                       OR source_url NOT LIKE 'https://www.boe.es/%'
                       OR source_record_pk IS NULL
                    """
                ).fetchone()[0]
            )
            unapplied_corrections = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM boe_election_candidate_correction_documents
                    WHERE application_state = 'captured_unapplied'
                    """
                ).fetchone()[0]
            )
            applied_corrections = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM boe_election_candidate_correction_documents
                    WHERE application_state = 'applied'
                    """
                ).fetchone()[0]
            )
            correction_operations = int(
                connection.execute(
                    "SELECT COUNT(*) FROM boe_election_candidate_correction_operations"
                ).fetchone()[0]
            )
            referenced_correction_paragraphs = {
                (str(correction_document_id), int(paragraph_number))
                for correction_document_id, paragraph_numbers_json in connection.execute(
                    """
                    SELECT correction_document_id, evidence_paragraph_numbers_json
                    FROM boe_election_candidate_correction_operations
                    """
                )
                for paragraph_number in json.loads(str(paragraph_numbers_json))
            }
            correction_paragraphs_referenced = len(referenced_correction_paragraphs)
            reviewed_correction_paragraphs = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM boe_election_candidate_correction_paragraphs AS paragraph
                    JOIN boe_election_candidate_correction_documents AS document
                      ON document.correction_document_id=
                         paragraph.correction_document_id
                    WHERE document.application_state='applied'
                    """
                ).fetchone()[0]
            )
            pending_correction_paragraphs = (
                observed_counts["correction_paragraphs"]
                - reviewed_correction_paragraphs
            )
            contextual_correction_paragraphs = (
                reviewed_correction_paragraphs - correction_paragraphs_referenced
            )
            effective_candidacies = int(
                connection.execute(
                    "SELECT COUNT(*) FROM boe_election_effective_candidacies"
                ).fetchone()[0]
            )
            effective_candidates = int(
                connection.execute(
                    "SELECT COUNT(*) FROM boe_election_effective_candidate_occurrences"
                ).fetchone()[0]
            )
            pending_effective_candidacies = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM boe_election_effective_candidacies AS effective
                    JOIN boe_election_candidate_documents AS document
                      ON document.document_id=effective.base_document_id
                    WHERE document.correction_state='pending'
                    """
                ).fetchone()[0]
            )
            pending_effective_candidates = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM boe_election_effective_candidate_occurrences AS effective
                    JOIN boe_election_candidate_documents AS document
                      ON document.document_id=effective.base_document_id
                    WHERE document.correction_state='pending'
                    """
                ).fetchone()[0]
            )
            missing_effective_identity = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM boe_election_effective_candidate_occurrences
                    WHERE TRIM(full_name) = '' OR TRIM(source_text_exact) = ''
                       OR effective_source_url NOT LIKE 'https://www.boe.es/%'
                       OR LENGTH(effective_source_content_sha256) <> 64
                       OR person_id IS NULL OR party_id IS NULL
                       OR source_id <> 'boe_election_candidates'
                       OR source_record_pk IS NULL
                       OR document_source_record_pk IS NULL
                       OR first_seen_snapshot_date IS NULL
                       OR last_seen_snapshot_date IS NULL
                       OR is_present <> 1
                       OR person_identity_state NOT IN (
                         'source_scoped_base_exact',
                         'source_scoped_correction_exact'
                       )
                    """
                ).fetchone()[0]
            )
            foreign_key_violations = len(
                connection.execute("PRAGMA foreign_key_check").fetchall()
            )
        except sqlite3.DatabaseError as exc:
            raise ReadinessError(f"BOE candidate database audit failed: {exc}") from exc
        finally:
            connection.close()
        if observed_counts != expected_counts:
            raise ReadinessError("BOE candidate database totals drifted")
        if (
            missing_public_identity
            or missing_effective_identity
            or foreign_key_violations
        ):
            raise ReadinessError("BOE candidate exact public evidence contract failed")
        if (
            unapplied_corrections + applied_corrections
            != expected_counts["correction_documents"]
        ):
            raise ReadinessError("BOE candidate correction state drifted")
        if policy["pending_official_corrections_explicit"] != bool(
            unapplied_corrections
        ):
            raise ReadinessError("BOE candidate pending-correction policy drifted")
        if pending_effective_candidacies or pending_effective_candidates:
            raise ReadinessError(
                "pending BOE candidate evidence entered effective state"
            )
        expected_correction_values = {
            "captured_base_documents": expected_counts["documents"],
            "captured_base_candidacies": expected_counts["candidacies"],
            "captured_base_candidates": expected_counts["candidates"],
            "reviewed_base_documents": reviewed_base_counts["documents"],
            "reviewed_base_candidacies": reviewed_base_counts["candidacies"],
            "reviewed_base_candidates": reviewed_base_counts["candidates"],
            "pending_base_documents": pending_base_counts["documents"],
            "pending_base_candidacies": pending_base_counts["candidacies"],
            "pending_base_candidates": pending_base_counts["candidates"],
            "base_candidacies": reviewed_base_counts["candidacies"],
            "base_candidates": reviewed_base_counts["candidates"],
            "effective_candidacies": effective_candidacies,
            "effective_candidates": effective_candidates,
            "correction_documents_captured": expected_counts["correction_documents"],
            "correction_documents_applied": applied_corrections,
            "correction_documents_pending_review": unapplied_corrections,
            "correction_operations": correction_operations,
            "correction_paragraphs_retained": observed_counts["correction_paragraphs"],
            "reviewed_correction_paragraphs": reviewed_correction_paragraphs,
            "pending_correction_paragraphs": pending_correction_paragraphs,
            "correction_paragraphs_referenced_by_operations": (
                correction_paragraphs_referenced
            ),
            "contextual_correction_paragraphs_retained": (
                contextual_correction_paragraphs
            ),
            "normalized_effective_candidate_lineage_rows": effective_candidates,
            "changed_or_new_source_scoped_people": 25,
            "corrected_effective_source_records": 88,
        }
        for key, observed in expected_correction_values.items():
            if (
                _require_nonnegative_int(
                    correction_totals.get(key), f"BOE correction {key}"
                )
                != observed
            ):
                raise ReadinessError(f"BOE correction total drifted: {key}")
        correction_review_metrics: dict[str, Any] = {}
        if semantic_contract:
            from scripts.prepare_boe_candidate_correction_review_queue import (
                FIELDNAMES as CORRECTION_REVIEW_FIELDNAMES,
            )
            from scripts.prepare_boe_candidate_correction_review_queue import (
                task_fingerprint as correction_review_task_fingerprint,
            )
            from scripts.prepare_boe_candidate_correction_review_queue import (
                validate_reviews as validate_correction_reviews,
            )

            correction_review_report_path = repo_path(
                str(contract.get("correction_review_report") or "")
            )
            correction_review_queue_path = repo_path(
                str(contract.get("correction_review_queue") or "")
            )
            correction_review_context_path = repo_path(
                str(contract.get("correction_review_context") or "")
            )
            correction_review_report = load_json(correction_review_report_path)
            if (
                correction_review_report.get("schema_version")
                != "boe_candidate_correction_review_queue_v1"
                or correction_review_report.get("status")
                not in {"pending_human_review", "complete"}
                or not checks_pass(correction_review_report, require_status=False)
            ):
                raise ReadinessError("BOE correction review report contract failed")
            correction_review_policy = correction_review_report.get("policy") or {}
            required_review_policy = {
                "official_real_evidence_only": True,
                "public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
                "machine_decisions_invented": False,
                "dual_independent_human_review_required": True,
                "disagreement_adjudication_required": True,
                "official_evidence_publicable": True,
                "effective_state_mutated": False,
                "remote_mutation_performed": False,
            }
            if any(
                correction_review_policy.get(key) is not expected
                for key, expected in required_review_policy.items()
            ):
                raise ReadinessError("BOE correction review policy contract failed")
            review_artifacts = correction_review_report.get("artifacts") or {}
            review_queue_artifact = review_artifacts.get("review_queue") or {}
            review_context_artifact = review_artifacts.get("candidate_context") or {}
            expected_artifacts = (
                (correction_review_queue_path, review_queue_artifact),
                (correction_review_context_path, review_context_artifact),
            )
            for artifact_path, artifact in expected_artifacts:
                if (
                    artifact.get("path")
                    != artifact_path.relative_to(REPO_ROOT).as_posix()
                    or int(artifact.get("bytes") or -1) != artifact_path.stat().st_size
                    or artifact.get("sha256") != sha256_file(artifact_path)
                ):
                    raise ReadinessError("BOE correction review artifact drifted")
            correction_review_tasks: list[dict[str, str]] = []
            with correction_review_queue_path.open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                reader = csv.DictReader(handle)
                if tuple(reader.fieldnames or ()) != CORRECTION_REVIEW_FIELDNAMES:
                    raise ReadinessError("BOE correction review queue schema drifted")
                for row in reader:
                    if (
                        row["task_fingerprint"]
                        != correction_review_task_fingerprint(row)
                        or not row["source_text_exact"]
                        or not SHA256_RE.fullmatch(row["source_content_sha256"])
                        or urlparse(row["source_url"]).scheme != "https"
                        or (urlparse(row["source_url"]).hostname or "").lower()
                        != "www.boe.es"
                    ):
                        raise ReadinessError(
                            "BOE correction review task evidence drifted"
                        )
                    correction_review_tasks.append(dict(row))
            context_candidacies = 0
            context_candidates = 0
            context_candidacy_ids: set[str] = set()
            valid_candidacies_by_document: dict[str, set[str]] = {}
            with correction_review_context_path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    try:
                        context_row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ReadinessError(
                            "BOE correction candidate context JSONL is invalid at "
                            f"line {line_number}"
                        ) from exc
                    if (
                        not isinstance(context_row, dict)
                        or context_row.get("schema_version")
                        != "boe_candidate_correction_review_context_v1"
                    ):
                        raise ReadinessError(
                            "BOE correction candidate context schema drifted"
                        )
                    candidacy = context_row.get("candidacy") or {}
                    candidacy_id = str(candidacy.get("candidacy_id") or "")
                    candidate_rows = context_row.get("candidate_occurrences") or []
                    if (
                        not candidacy_id
                        or candidacy_id in context_candidacy_ids
                        or not isinstance(candidate_rows, list)
                        or any(
                            not str(candidate.get("full_name") or "").strip()
                            or not str(candidate.get("source_text_exact") or "").strip()
                            for candidate in candidate_rows
                        )
                    ):
                        raise ReadinessError(
                            "BOE correction candidate context evidence drifted"
                        )
                    context_candidacy_ids.add(candidacy_id)
                    base_document = context_row.get("base_document") or {}
                    base_document_id = str(base_document.get("base_document_id") or "")
                    if not base_document_id:
                        raise ReadinessError(
                            "BOE correction candidate context target drifted"
                        )
                    valid_candidacies_by_document.setdefault(
                        base_document_id, set()
                    ).add(candidacy_id)
                    context_candidacies += 1
                    context_candidates += len(candidate_rows)
            try:
                correction_review_counts = validate_correction_reviews(
                    correction_review_tasks,
                    valid_candidacies_by_document=valid_candidacies_by_document,
                )
            except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
                raise ReadinessError(
                    f"BOE correction review decisions invalid: {exc}"
                ) from exc
            review_totals = correction_review_report.get("totals") or {}
            expected_review_totals = {
                "pending_correction_documents": unapplied_corrections,
                "pending_correction_paragraphs": pending_correction_paragraphs,
                "tasks": len(correction_review_tasks),
                "pending_dual_review": correction_review_counts.get(
                    "pending_dual_review", 0
                ),
                "context_candidacies": context_candidacies,
                "context_candidate_occurrences": context_candidates,
            }
            for key, expected in expected_review_totals.items():
                if int(review_totals.get(key, -1)) != expected:
                    raise ReadinessError(f"BOE correction review total drifted: {key}")
            if (
                len(correction_review_tasks) != pending_correction_paragraphs
                or context_candidacies != pending_base_counts["candidacies"]
                or context_candidates != pending_base_counts["candidates"]
            ):
                raise ReadinessError(
                    "BOE correction review coverage does not match pending state"
                )
            correction_review_metrics = {
                "correction_review_tasks": len(correction_review_tasks),
                "correction_review_context_candidacies": context_candidacies,
                "correction_review_context_candidates": context_candidates,
                **{
                    f"correction_review_{key}": value
                    for key, value in correction_review_counts.items()
                },
            }
        semantic_metrics: dict[str, Any] = {}
        if semantic_contract:
            semantic_root = repo_path(str(contract.get("semantic_root") or ""))
            semantic_manifest_path = repo_path(
                str(contract.get("semantic_manifest") or "")
            )
            semantic_validation_path = repo_path(
                str(contract.get("semantic_validation") or "")
            )
            semantic_manifest = load_json(semantic_manifest_path)
            semantic_validation = load_json(semantic_validation_path)
            if not checks_pass(semantic_manifest, require_status=False):
                raise ReadinessError("BOE candidate semantic manifest checks failed")
            if not checks_pass(semantic_validation, require_status=True):
                raise ReadinessError("BOE candidate semantic validation checks failed")
            observed_semantic = validate_semantic_files(
                semantic_root,
                semantic_manifest,
                allowed_source_ids={"boe_election_candidates"},
                allowed_hosts={"www.boe.es"},
                inspect_provenance=True,
            )
            semantic_totals = semantic_manifest.get("totals") or {}
            required_semantic_totals = {
                "rows": effective_candidates,
                "boe_rows": effective_candidates,
                "infoelectoral_rows": 0,
                "exact_public_name_rows": effective_candidates,
                "exact_source_text_rows": effective_candidates,
                "document_source_record_rows": effective_candidates,
                "correction_backed_rows": 88,
                "outcome_known_rows": 0,
            }
            for key, expected in required_semantic_totals.items():
                if int(semantic_totals.get(key, -1)) != expected:
                    raise ReadinessError(f"BOE candidate semantic total drifted: {key}")
            if int((semantic_validation.get("totals") or {}).get("rows", -1)) != (
                effective_candidates
            ):
                raise ReadinessError("BOE candidate semantic validation row drifted")
            replay = validate_replay(
                {
                    "id": "candidate_occurrences",
                    "incremental_manifest": contract.get(
                        "semantic_incremental_manifest"
                    ),
                    "incremental_validation": contract.get(
                        "semantic_incremental_validation"
                    ),
                    "replay_root": contract.get("semantic_replay_root"),
                },
                allowed_source_ids={"boe_election_candidates"},
                allowed_hosts={"www.boe.es"},
            )
            semantic_metrics = {
                "semantic_rows": observed_semantic["rows"],
                "semantic_files": observed_semantic["files"],
                "semantic_bytes": observed_semantic["bytes"],
                "semantic_boe_rows": int(semantic_totals["boe_rows"]),
                "semantic_exact_public_name_rows": int(
                    semantic_totals["exact_public_name_rows"]
                ),
                "semantic_exact_source_text_rows": int(
                    semantic_totals["exact_source_text_rows"]
                ),
                "semantic_correction_backed_rows": int(
                    semantic_totals["correction_backed_rows"]
                ),
                "semantic_outcome_known_rows": int(
                    semantic_totals["outcome_known_rows"]
                ),
                "semantic_unchanged_replay": replay,
            }
        result["metrics"] = {
            **{
                key: value
                for key, value in observed_counts.items()
                if key != "candidates"
            },
            "base_candidates": observed_counts["candidates"],
            "captured_base_documents": observed_counts["documents"],
            "captured_base_candidacies": observed_counts["candidacies"],
            "captured_base_candidates": observed_counts["candidates"],
            "reviewed_base_documents": reviewed_base_counts["documents"],
            "reviewed_base_candidacies": reviewed_base_counts["candidacies"],
            "reviewed_base_candidates": reviewed_base_counts["candidates"],
            "pending_base_documents": pending_base_counts["documents"],
            "pending_base_candidacies": pending_base_counts["candidacies"],
            "pending_base_candidates": pending_base_counts["candidates"],
            "candidates": effective_candidates,
            "effective_candidates": effective_candidates,
            "effective_candidacies": effective_candidacies,
            "correction_operations": correction_operations,
            "reviewed_correction_paragraphs": reviewed_correction_paragraphs,
            "pending_correction_paragraphs": pending_correction_paragraphs,
            "correction_paragraphs_referenced_by_operations": (
                correction_paragraphs_referenced
            ),
            "contextual_correction_paragraphs_retained": (
                contextual_correction_paragraphs
            ),
            "applied_correction_documents": applied_corrections,
            "official_public_identity_rows_retained": observed_counts["candidates"],
            "effective_public_identity_rows_retained": effective_candidates,
            "identity_fields_removed": 0,
            "captured_unapplied_correction_documents": unapplied_corrections,
            "pending_effective_candidacies": pending_effective_candidacies,
            "pending_effective_candidates": pending_effective_candidates,
            "foreign_key_violations": foreign_key_violations,
            **correction_review_metrics,
            **semantic_metrics,
            "evidence": {
                "base_ingest": evidence_reference(report_path),
                "correction_materialization": evidence_reference(
                    correction_report_path
                ),
                **(
                    {
                        "correction_review_report": evidence_reference(
                            correction_review_report_path
                        ),
                        "correction_review_queue": evidence_reference(
                            correction_review_queue_path
                        ),
                        "correction_review_context": evidence_reference(
                            correction_review_context_path
                        ),
                    }
                    if semantic_contract
                    else {}
                ),
                **(
                    {
                        "semantic_manifest": evidence_reference(semantic_manifest_path),
                        "semantic_validation": evidence_reference(
                            semantic_validation_path
                        ),
                    }
                    if semantic_contract
                    else {}
                ),
            },
        }
        return result
    if contract.get("kind") == "integrity_human_review_v1":
        from scripts.prepare_procurement_integrity_review_queue import (
            FIELDNAMES,
            task_fingerprint,
            validate_reviews,
        )

        report_path = repo_path(str(contract.get("report") or ""))
        queue_path = repo_path(str(contract.get("queue_csv") or ""))
        report = load_json(report_path)
        if report.get(
            "schema_version"
        ) != "procurement_integrity_human_review_queue_v1" or report.get(
            "status"
        ) not in {"pending_human_review", "complete"}:
            raise ReadinessError("integrity review report contract failed")
        policy = report.get("policy") or {}
        required_policy = {
            "official_real_evidence_only": True,
            "public_domain_personal_information_retained": True,
            "synthetic_or_mock_records_counted": False,
            "machine_decisions_invented": False,
            "dual_independent_human_review_required": True,
            "disagreement_adjudication_required": True,
            "review_signal_is_not_corruption_finding": True,
            "public_by_default": False,
            "remote_mutation_performed": False,
        }
        if any(
            policy.get(key) is not expected for key, expected in required_policy.items()
        ):
            raise ReadinessError("integrity review policy contract failed")
        artifact = report.get("artifact") or {}
        queue_ref = queue_path.relative_to(REPO_ROOT).as_posix()
        if (
            artifact.get("path") != queue_ref
            or int(artifact.get("bytes") or -1) != queue_path.stat().st_size
            or artifact.get("sha256") != sha256_file(queue_path)
        ):
            raise ReadinessError("integrity review queue artifact drifted")
        tasks: list[dict[str, str]] = []
        with queue_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != FIELDNAMES:
                raise ReadinessError("integrity review queue schema drifted")
            for row in reader:
                if row["task_fingerprint"] != task_fingerprint(row):
                    raise ReadinessError("integrity review task fingerprint drifted")
                evidence_count = int(row["evidence_count"])
                arrays = [
                    json.loads(row[field])
                    for field in (
                        "evidence_basis_json",
                        "evidence_row_ids_json",
                        "source_record_pks_json",
                        "source_urls_json",
                        "content_sha256s_json",
                        "amounts_eur_decimal_json",
                        "stable_contract_ids_json",
                        "lot_ids_json",
                        "supplier_identifiers_json",
                        "evidence_excerpts_json",
                    )
                ]
                if any(len(values) != evidence_count for values in arrays):
                    raise ReadinessError("integrity review evidence arrays drifted")
                if any(
                    urlparse(str(url)).scheme != "https"
                    or (urlparse(str(url)).hostname or "").lower()
                    != "contrataciondelestado.es"
                    for url in arrays[3]
                ):
                    raise ReadinessError("integrity review source URL drifted")
                if any(not SHA256_RE.fullmatch(str(value)) for value in arrays[4]):
                    raise ReadinessError("integrity review source checksum drifted")
                tasks.append(dict(row))
        try:
            review_counts = validate_reviews(tasks)
        except (RuntimeError, ValueError) as exc:
            raise ReadinessError(f"integrity human review invalid: {exc}") from exc
        totals = report.get("totals") or {}
        evidence_rows = sum(int(row["evidence_count"]) for row in tasks)
        if (
            int(totals.get("tasks") or -1) != len(tasks)
            or int(totals.get("official_evidence_rows") or -1) != evidence_rows
            or int(totals.get("pending_dual_review") or -1)
            != review_counts.get("pending_dual_review", 0)
            or int(result["current_real_rows"])
            != review_counts.get("dual_review_complete", 0)
        ):
            raise ReadinessError("integrity review totals drifted")
        result["metrics"] = {
            "review_tasks": len(tasks),
            "official_evidence_rows": evidence_rows,
            **review_counts,
        }
        return result
    raise ReadinessError(f"unsupported gap evidence contract: {contract.get('kind')!r}")


def build_report(registry_path: Path) -> dict[str, Any]:
    registry = load_json(registry_path)
    reject_disallowed_evidence(
        registry, registry_path.relative_to(REPO_ROOT).as_posix()
    )
    registry_policy = registry.get("policy")
    required_true_policy = {
        "official_real_records_only",
        "synthetic_or_mock_records_forbidden",
        "every_row_requires_source_lineage",
        "official_public_domain_personal_information_retained",
        "classification_never_suppresses_public_domain_identity",
        "secrets_workstation_traces_and_non_public_data_forbidden",
        "promotion_requires_representative_scope",
        "promotion_requires_durable_public_origin",
        "promotion_requires_clean_room_restore",
    }
    if not isinstance(registry_policy, dict):
        raise ReadinessError("real corpus registry has no policy object")
    missing_policy = sorted(
        key for key in required_true_policy if registry_policy.get(key) is not True
    )
    if missing_policy:
        raise ReadinessError(
            "real corpus registry policy is missing mandatory true gates: "
            + ", ".join(missing_policy)
        )
    supporting_evidence = registry.get("supporting_evidence") or {}
    if not isinstance(supporting_evidence, dict):
        raise ReadinessError(
            "real corpus registry supporting_evidence must be an object"
        )
    official_sample_report_path = repo_path(
        str(supporting_evidence.get("official_sample_corpus_audit") or "")
    )
    official_sample_report = load_json(official_sample_report_path)
    from etl.politicos_es.config import SOURCE_CONFIG
    from scripts.audit_official_sample_corpus import audit_official_samples

    try:
        current_official_sample_audit = audit_official_samples(
            source_config=SOURCE_CONFIG
        )
    except ValueError as exc:
        raise ReadinessError(f"official sample corpus audit failed: {exc}") from exc
    if official_sample_report != current_official_sample_audit:
        raise ReadinessError("official sample corpus audit report has drifted")
    public_source_records_report_path = repo_path(
        str(supporting_evidence.get("public_source_records_publish_audit") or "")
    )
    public_source_records_report = load_json(public_source_records_report_path)
    from scripts.publicar_hf_snapshot import (
        DEFAULT_DB,
        audit_public_source_records_for_publish,
    )

    try:
        current_public_source_records_audit = audit_public_source_records_for_publish(
            REPO_ROOT / DEFAULT_DB
        )
    except ValueError as exc:
        raise ReadinessError(
            f"public source-record publish audit failed: {exc}"
        ) from exc
    if public_source_records_report != current_public_source_records_audit:
        raise ReadinessError("public source-record publish audit report has drifted")
    corpora = registry.get("corpora")
    if not isinstance(corpora, list) or not corpora:
        raise ReadinessError("real corpus registry has no corpora")
    audited = [audit_corpus(corpus) for corpus in corpora]
    raw_gaps = registry.get("gaps") or []
    if not isinstance(raw_gaps, list):
        raise ReadinessError("real corpus registry gaps must be an array")
    gaps = [audit_gap(gap) for gap in raw_gaps]
    for gap in gaps:
        if gap.get("status") in {"complete", "promoted"}:
            raise ReadinessError(f"open gap cannot claim completion: {gap.get('id')}")
    million_lanes = sum(1 for corpus in audited if corpus["rows"] >= 1_000_000)
    promoted_lanes = sum(1 for corpus in audited if corpus["promotion_gate_passed"])
    foundation_ready = all(
        corpus["status"] == "validated_real_artifact" for corpus in audited
    )
    report = {
        "schema_version": "real-scale-readiness-v1",
        "generated_at": utc_now(),
        "status": "real_foundation_ready_scale_incomplete"
        if foundation_ready
        else "not_ready",
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_forbidden": True,
            "generated_test_records_count_toward_readiness": False,
            "loopback_network_results_count_toward_readiness": False,
            "official_public_domain_personal_information_retained": True,
            "classification_never_suppresses_public_domain_identity": True,
            "secrets_workstation_traces_and_non_public_data_forbidden": True,
            "promotion_requires_public_origin_and_clean_restore": True,
        },
        "registry": evidence_reference(registry_path),
        "supporting_evidence": {
            "official_sample_corpus_audit": {
                **official_sample_report,
                "evidence": evidence_reference(official_sample_report_path),
            },
            "public_source_records_publish_audit": {
                **public_source_records_report,
                "evidence": evidence_reference(public_source_records_report_path),
            },
        },
        "summary": {
            "registered_real_corpora": len(audited),
            "validated_real_corpora": sum(
                1 for corpus in audited if corpus["real_official_data"]
            ),
            "real_million_scale_lanes": million_lanes,
            "promoted_lanes": promoted_lanes,
            "open_gaps": len(gaps),
        },
        "foundation": {
            "ready": foundation_ready,
            "meaning": "Every registered current artifact is independently reconciled to official source provenance; societal-scale coverage remains open.",
        },
        "corpora": audited,
        "gaps": gaps,
    }
    if promoted_lanes == len(audited):
        report["status"] = "promoted_real_scale_ready"
    return report


def atomic_write_json(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", dir=output_path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, output_path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def build_failure_report(
    registry_path: Path,
    error: ReadinessError,
) -> dict[str, Any]:
    reason = str(error).replace(str(REPO_ROOT), "<repo>")
    registry_reference: dict[str, Any] = {
        "path": registry_path.relative_to(REPO_ROOT).as_posix(),
        "available": registry_path.is_file(),
    }
    if registry_path.is_file():
        registry_reference.update(evidence_reference(registry_path))
    return {
        "schema_version": "real-scale-readiness-v1",
        "generated_at": utc_now(),
        "status": "not_ready",
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_forbidden": True,
            "generated_test_records_count_toward_readiness": False,
            "loopback_network_results_count_toward_readiness": False,
            "official_public_domain_personal_information_retained": True,
            "classification_never_suppresses_public_domain_identity": True,
            "secrets_workstation_traces_and_non_public_data_forbidden": True,
            "promotion_requires_public_origin_and_clean_restore": True,
        },
        "registry": registry_reference,
        "foundation": {
            "ready": False,
            "meaning": "Current evidence validation failed; no prior readiness result remains authoritative.",
        },
        "failure": {
            "kind": "readiness_validation_failed",
            "reason": reason,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        required=True,
        help="Repository-relative real corpus registry JSON",
    )
    parser.add_argument(
        "--out", required=True, help="Repository-relative readiness report JSON"
    )
    parser.add_argument("--enforce-foundation", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = repo_path(args.registry)
    output_path = repo_path(args.out)
    try:
        report = build_report(registry_path)
        atomic_write_json(output_path, report)
    except ReadinessError as exc:
        atomic_write_json(output_path, build_failure_report(registry_path, exc))
        print(f"scale readiness failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.enforce_foundation and not report["foundation"]["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
