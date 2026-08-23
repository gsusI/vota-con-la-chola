#!/usr/bin/env python3
"""Fail-closed validation for the public Evidence API v1 export."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts.export_evidence_api_v1 import (
        API_VERSION,
        COLLECTIONS,
        DEFAULT_EVIDENCE,
        DEFAULT_OUT,
        DEFAULT_SCHEMA,
        DEFAULT_SOURCE_HEALTH,
        MAX_PAGE_SIZE,
        REPO_ROOT,
        atomic_write,
        canonical_bytes,
        decode_cursor,
        read_json,
        sha256_bytes,
        sha256_file,
    )
except ModuleNotFoundError:
    from export_evidence_api_v1 import (
        API_VERSION,
        COLLECTIONS,
        DEFAULT_EVIDENCE,
        DEFAULT_OUT,
        DEFAULT_SCHEMA,
        DEFAULT_SOURCE_HEALTH,
        MAX_PAGE_SIZE,
        REPO_ROOT,
        atomic_write,
        canonical_bytes,
        decode_cursor,
        read_json,
        sha256_bytes,
        sha256_file,
    )


HEX_64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_PUBLIC_PATHS = ("/Users/", "file:///", "/home/")
ALLOWED_ANSWER_STATES = {
    "known",
    "partial",
    "unanswerable",
    "blocked",
    "unknown",
    "no_signal",
}


def resolve_api_path(out_root: Path, href: str) -> Path:
    prefix = "/api/v1/"
    if not href.startswith(prefix):
        raise ValueError(f"href is outside API v1: {href}")
    return out_root / href.removeprefix(prefix)


def scan_strings(value: Any) -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            findings.extend(scan_strings(child))
    elif isinstance(value, list):
        for child in value:
            findings.extend(scan_strings(child))
    elif isinstance(value, str):
        findings.extend(marker for marker in FORBIDDEN_PUBLIC_PATHS if marker in value)
    return findings


def validate(
    *,
    out_root: Path,
    evidence_path: Path,
    source_health_path: Path,
    schema_path: Path,
    max_page_bytes: int,
    max_manifest_bytes: int,
) -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    pointer_path = out_root / "index.json"
    if not pointer_path.is_file():
        return {
            "schema_version": "evidence_api_validation_v1",
            "status": "error",
            "checks": {},
            "errors": ["missing current pointer"],
        }
    pointer = read_json(pointer_path)
    current = pointer.get("current_release") or {}
    api_release_id = str(current.get("api_release_id") or "")
    if pointer.get("schema_version") != "evidence_api_current_pointer_v1":
        errors.append("current pointer schema_version mismatch")
    if pointer.get("api_version") != API_VERSION:
        errors.append("current pointer api_version mismatch")
    if not HEX_64.fullmatch(api_release_id):
        errors.append("current API release ID is not SHA-256")
    policy = pointer.get("policy") or {}
    expected_policy = {
        "read_only": True,
        "official_real_records_only": True,
        "synthetic_or_mock_records": "forbidden",
        "public_domain_personal_information": "retained",
        "unknown_states_explicit": True,
    }
    if policy != expected_policy:
        errors.append("current pointer policy mismatch")

    try:
        release_path = resolve_api_path(out_root, str(current.get("href") or ""))
    except ValueError as exc:
        errors.append(str(exc))
        release_path = out_root / "missing-release.json"
    if not release_path.is_file():
        errors.append("current release index is missing")
        release = {}
    else:
        release = read_json(release_path)
        if sha256_file(release_path) != current.get("sha256"):
            errors.append("current release index hash mismatch")
    if release.get("schema_version") != "evidence_api_release_index_v1":
        errors.append("release index schema_version mismatch")
    if release.get("api_release_id") != api_release_id:
        errors.append("release index API release ID mismatch")
    if (release.get("upstream_scale_release") or {}).get("release_id") != current.get(
        "upstream_scale_release_id"
    ):
        errors.append("upstream scale release mismatch")
    if release.get("policy") != expected_policy:
        errors.append("release policy mismatch")
    compatibility = release.get("compatibility") or {}
    if int(compatibility.get("deprecation_window_days") or 0) < 180:
        errors.append("deprecation window must be at least 180 days")
    if int(compatibility.get("minimum_parallel_public_releases") or 0) < 2:
        errors.append(
            "at least two parallel public releases are required for deprecation"
        )

    schema_copy = out_root / "schema.json"
    if not schema_copy.is_file() or sha256_file(schema_copy) != sha256_file(
        schema_path
    ):
        errors.append("public schema copy differs from canonical schema")
    else:
        schema = read_json(schema_copy)
        required_defs = {
            "currentPointer",
            "releaseIndex",
            "collectionManifest",
            "collectionPage",
            "provenance",
        }
        if not required_defs.issubset(set((schema.get("$defs") or {}).keys())):
            errors.append("public schema is missing required definitions")

    artifact_by_path = {
        str(item.get("path") or ""): item
        for item in release.get("source_artifacts") or []
    }
    for relative, artifact in artifact_by_path.items():
        path = REPO_ROOT / relative
        if not path.is_file():
            errors.append(f"source artifact missing: {relative}")
        elif sha256_file(path) != artifact.get("sha256"):
            errors.append(f"source artifact hash mismatch: {relative}")

    evidence = read_json(evidence_path)
    source_health = read_json(source_health_path)
    expected_counts = {
        "entities": len(evidence.get("actor_answers") or [])
        + len(evidence.get("issue_answers") or []),
        "source-health": len(source_health.get("sources") or []),
        "question-results": sum(
            len(evidence.get(name) or [])
            for name in (
                "actor_answers",
                "issue_answers",
                "actor_issue_refs",
                "gap_answers",
                "blocker_answers",
                "qa_answers",
            )
        ),
    }
    source_entity_labels = {
        str(item.get("answer_id") or ""): str(item.get("actor_label") or "")
        for item in evidence.get("actor_answers") or []
    }
    source_entity_labels.update(
        {
            str(item.get("answer_id") or ""): str(item.get("issue_label") or "")
            for item in evidence.get("issue_answers") or []
        }
    )
    collection_rows = release.get("collections") or []
    collection_index = {str(item.get("id") or ""): item for item in collection_rows}
    if set(collection_index) != set(COLLECTIONS):
        errors.append("release collections must be exactly the four v1 collections")
    release_page_sizes = {int(item.get("page_size") or 0) for item in collection_rows}
    if len(release_page_sizes) != 1:
        errors.append("all collections must use the same page size")
    else:
        build_fingerprint = {
            "api_version": API_VERSION,
            "exporter_version": release.get("exporter_version"),
            "page_size": next(iter(release_page_sizes)),
            "upstream_scale_release_id": current.get("upstream_scale_release_id"),
            "data_snapshot_date": release.get("data_snapshot_date"),
            "source_artifacts": [
                {"path": item.get("path"), "sha256": item.get("sha256")}
                for item in release.get("source_artifacts") or []
            ],
        }
        if sha256_bytes(canonical_bytes(build_fingerprint)) != api_release_id:
            errors.append("API release ID does not match its build fingerprint")
    evidence_ids: set[str] = set()
    question_evidence_refs: set[str] = set()
    entity_labels: dict[str, str] = {}
    total_items = 0
    total_pages = 0
    max_observed_page_bytes = 0

    for collection in COLLECTIONS:
        entry = collection_index.get(collection) or {}
        try:
            manifest_path = resolve_api_path(out_root, str(entry.get("manifest") or ""))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not manifest_path.is_file():
            errors.append(f"missing {collection} manifest")
            continue
        if manifest_path.stat().st_size > max_manifest_bytes:
            errors.append(f"{collection} manifest exceeds byte budget")
        if sha256_file(manifest_path) != entry.get("manifest_sha256"):
            errors.append(f"{collection} manifest hash mismatch")
        manifest = read_json(manifest_path)
        if manifest.get("schema_version") != "evidence_api_collection_manifest_v1":
            errors.append(f"{collection} manifest schema mismatch")
        if (
            manifest.get("collection") != collection
            or manifest.get("api_release_id") != api_release_id
        ):
            errors.append(f"{collection} manifest identity mismatch")
        page_size = int(manifest.get("page_size") or 0)
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            errors.append(f"{collection} invalid page size")
        pages = manifest.get("pages") or []
        if len(pages) != int(manifest.get("page_count") or 0):
            errors.append(f"{collection} page count mismatch")
        if int(manifest.get("item_count") or 0) != int(entry.get("item_count") or 0):
            errors.append(f"{collection} item count differs between indexes")
        expected_count = expected_counts.get(collection)
        if (
            expected_count is not None
            and int(manifest.get("item_count") or 0) != expected_count
        ):
            errors.append(f"{collection} count differs from real source export")
        seen_count = 0
        previous_key: str | None = None
        previous_end_cursor: str | None = None
        actual_page_files: set[Path] = set()
        for page_offset, page_entry in enumerate(pages):
            page_number = page_offset + 1
            try:
                page_path = resolve_api_path(
                    out_root, str(page_entry.get("href") or "")
                )
            except ValueError as exc:
                errors.append(str(exc))
                continue
            actual_page_files.add(page_path)
            if not page_path.is_file():
                errors.append(f"missing {collection} page {page_number}")
                continue
            page_bytes = page_path.read_bytes()
            max_observed_page_bytes = max(max_observed_page_bytes, len(page_bytes))
            if len(page_bytes) > max_page_bytes:
                errors.append(f"{collection} page {page_number} exceeds byte budget")
            page_hash = sha256_bytes(page_bytes)
            if page_hash != page_entry.get("sha256") or page_hash not in page_path.name:
                errors.append(f"{collection} page {page_number} hash mismatch")
            page = json.loads(page_bytes)
            page_info = page.get("page_info") or {}
            items = page.get("items") or []
            if page.get("schema_version") != "evidence_api_collection_page_v1":
                errors.append(f"{collection} page {page_number} schema mismatch")
            if (
                page.get("collection") != collection
                or page.get("api_release_id") != api_release_id
            ):
                errors.append(f"{collection} page {page_number} identity mismatch")
            if int(page_info.get("page_number") or 0) != page_number:
                errors.append(f"{collection} page number mismatch")
            if int(page_info.get("returned") or -1) != len(items):
                errors.append(f"{collection} returned count mismatch")
            if len(items) > page_size:
                errors.append(f"{collection} page exceeds page size")
            expected_has_next = page_number < len(pages)
            expected_next = (
                pages[page_offset + 1].get("href") if expected_has_next else None
            )
            if (
                page_info.get("has_next") is not expected_has_next
                or page_info.get("next") != expected_next
            ):
                errors.append(f"{collection} page {page_number} next link mismatch")
            if page_info.get("start_cursor") != previous_end_cursor:
                errors.append(f"{collection} page {page_number} start cursor mismatch")
            for item in items:
                item_id = str(item.get("id") or "")
                if not item_id or (
                    previous_key is not None and item_id <= previous_key
                ):
                    errors.append(f"{collection} item order/identity violation")
                previous_key = item_id
                record_provenance = item.get("provenance") or {}
                if record_provenance.get("api_release_id") != api_release_id:
                    errors.append(f"{collection} record API provenance mismatch")
                if record_provenance.get("upstream_scale_release_id") != current.get(
                    "upstream_scale_release_id"
                ):
                    errors.append(f"{collection} record upstream provenance mismatch")
                if record_provenance.get("official_real_record") is not True:
                    errors.append(f"{collection} record is not marked official real")
                if not HEX_64.fullmatch(
                    str(record_provenance.get("source_artifact_sha256") or "")
                ):
                    errors.append(f"{collection} record source hash invalid")
                if collection == "entities":
                    entity_labels[item_id] = str(item.get("label") or "")
                elif collection == "evidence-chains":
                    evidence_ids.add(item_id)
                    evidence_block = item.get("evidence") or {}
                    source_url = str(evidence_block.get("source_url") or "")
                    source_url_state = str(evidence_block.get("source_url_state") or "")
                    if source_url and not source_url.startswith(
                        ("https://", "http://")
                    ):
                        errors.append(
                            f"evidence chain {item_id} has an invalid public source URL"
                        )
                    if (
                        not source_url
                        and source_url_state != "not_available_in_current_export"
                    ):
                        errors.append(
                            f"evidence chain {item_id} hides its missing source URL state"
                        )
                    if not str(evidence_block.get("source_locator") or ""):
                        errors.append(f"evidence chain {item_id} has no source locator")
                elif collection == "question-results":
                    question_evidence_refs.update(
                        str(ref) for ref in item.get("evidence_chain_ids") or []
                    )
                    state = str(item.get("answer_status") or "unknown")
                    if state not in ALLOWED_ANSWER_STATES:
                        errors.append(
                            f"question result has unsupported answer state: {state}"
                        )
                findings = scan_strings(item)
                if findings:
                    errors.append(
                        f"{collection} record leaks workstation path marker: {item_id}"
                    )
            end_cursor = page_info.get("end_cursor")
            if items:
                try:
                    decoded = decode_cursor(str(end_cursor or ""))
                    if decoded != {
                        "after": items[-1]["id"],
                        "collection": collection,
                        "release": api_release_id,
                        "version": 1,
                    }:
                        errors.append(
                            f"{collection} page {page_number} end cursor mismatch"
                        )
                except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                    errors.append(f"{collection} page {page_number} cursor is invalid")
            if page_info.get("next_cursor") != (
                end_cursor if expected_has_next else None
            ):
                errors.append(f"{collection} page {page_number} next cursor mismatch")
            previous_end_cursor = end_cursor
            seen_count += len(items)
        page_dir = manifest_path.parent / "pages"
        disk_page_files = set(page_dir.glob("*.json")) if page_dir.is_dir() else set()
        if actual_page_files != disk_page_files:
            errors.append(f"{collection} page inventory mismatch")
        if seen_count != int(manifest.get("item_count") or 0):
            errors.append(f"{collection} paginated item total mismatch")
        total_items += seen_count
        total_pages += len(pages)

    expected_evidence_total = len(
        {
            (
                str(sample.get("entry_id") or ""),
                str(sample.get("source_locator") or ""),
                str(sample.get("source_url") or ""),
            )
            for collection in ("actor_answers", "issue_answers")
            for answer in evidence.get(collection) or []
            for sample in answer.get("evidence_samples") or []
        }
    )
    if len(evidence_ids) != expected_evidence_total:
        errors.append("evidence-chain count differs from unique real evidence samples")
    if not question_evidence_refs.issubset(evidence_ids):
        errors.append("question results reference missing evidence chains")
    if entity_labels != source_entity_labels:
        errors.append("official public entity labels were altered or omitted")

    checks.update(
        {
            "api_release_id": api_release_id,
            "upstream_scale_release_id": current.get("upstream_scale_release_id"),
            "collections_total": len(collection_index),
            "items_total": total_items,
            "pages_total": total_pages,
            "entities_total": len(entity_labels),
            "evidence_chains_total": len(evidence_ids),
            "question_evidence_refs_total": len(question_evidence_refs),
            "source_health_total": expected_counts["source-health"],
            "max_observed_page_bytes": max_observed_page_bytes,
            "public_identity_labels_retained": entity_labels == source_entity_labels,
            "official_real_records_only": policy.get("official_real_records_only")
            is True,
        }
    )
    return {
        "schema_version": "evidence_api_validation_v1",
        "status": "ok" if not errors else "error",
        "checks": checks,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--evidence-api", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--source-health", type=Path, default=DEFAULT_SOURCE_HEALTH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--max-page-bytes", type=int, default=2_500_000)
    parser.add_argument("--max-manifest-bytes", type=int, default=2_500_000)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate(
        out_root=args.out_root,
        evidence_path=args.evidence_api,
        source_health_path=args.source_health,
        schema_path=args.schema,
        max_page_bytes=args.max_page_bytes,
        max_manifest_bytes=args.max_manifest_bytes,
    )
    body = canonical_bytes(report, pretty=True)
    if args.json_out:
        atomic_write(args.json_out, body)
    print(body.decode("utf-8"), end="")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
