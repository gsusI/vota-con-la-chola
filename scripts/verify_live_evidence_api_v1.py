#!/usr/bin/env python3
"""Verify every page of a published Evidence API v1 release over HTTP."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    from scripts.export_evidence_api_v1 import (
        API_VERSION,
        COLLECTIONS,
        atomic_write,
        canonical_bytes,
        decode_cursor,
        sha256_bytes,
    )
except ModuleNotFoundError:
    from export_evidence_api_v1 import (
        API_VERSION,
        COLLECTIONS,
        atomic_write,
        canonical_bytes,
        decode_cursor,
        sha256_bytes,
    )


def fetch(
    base_url: str, href: str, *, timeout: float, max_bytes: int
) -> tuple[str, bytes]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", href.lstrip("/"))
    base_origin = urllib.parse.urlsplit(base_url)
    target_origin = urllib.parse.urlsplit(url)
    if (target_origin.scheme, target_origin.netloc) != (
        base_origin.scheme,
        base_origin.netloc,
    ):
        raise ValueError(f"cross-origin API link rejected: {url}")
    request = urllib.request.Request(
        url, headers={"User-Agent": "vclc-evidence-api-verifier/1"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(max_bytes + 1)
        status = int(response.status)
    if status != 200:
        raise ValueError(f"HTTP {status}: {url}")
    if len(body) > max_bytes:
        raise ValueError(f"response exceeds byte budget: {url}")
    return url, body


def parse_object(body: bytes, url: str) -> dict[str, Any]:
    value = json.loads(body)
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {url}")
    return value


def verify(
    *,
    base_url: str,
    expected_api_release: str,
    timeout: float,
    max_page_bytes: int,
    max_manifest_bytes: int,
) -> dict[str, Any]:
    errors: list[str] = []
    fetched_bytes = 0
    fetched_files = 0
    try:
        pointer_url, pointer_body = fetch(
            base_url,
            "/api/v1/index.json",
            timeout=timeout,
            max_bytes=max_manifest_bytes,
        )
        fetched_bytes += len(pointer_body)
        fetched_files += 1
        pointer = parse_object(pointer_body, pointer_url)
        current = pointer.get("current_release") or {}
        api_release_id = str(current.get("api_release_id") or "")
        if expected_api_release and api_release_id != expected_api_release:
            errors.append("current API release differs from expected release")
        release_url, release_body = fetch(
            base_url,
            str(current.get("href") or ""),
            timeout=timeout,
            max_bytes=max_manifest_bytes,
        )
        fetched_bytes += len(release_body)
        fetched_files += 1
        if sha256_bytes(release_body) != current.get("sha256"):
            errors.append("release index SHA-256 differs from current pointer")
        release = parse_object(release_body, release_url)
        if release.get("api_release_id") != api_release_id:
            errors.append("release index identity mismatch")
        source_artifacts = release.get("source_artifacts") or []
        collection_rows = release.get("collections") or []
        page_sizes = {int(item.get("page_size") or 0) for item in collection_rows}
        if len(page_sizes) != 1:
            errors.append("release collections use inconsistent page sizes")
        else:
            fingerprint = {
                "api_version": API_VERSION,
                "exporter_version": release.get("exporter_version"),
                "page_size": next(iter(page_sizes)),
                "upstream_scale_release_id": current.get("upstream_scale_release_id"),
                "data_snapshot_date": release.get("data_snapshot_date"),
                "source_artifacts": [
                    {"path": item.get("path"), "sha256": item.get("sha256")}
                    for item in source_artifacts
                ],
            }
            if sha256_bytes(canonical_bytes(fingerprint)) != api_release_id:
                errors.append("API release ID differs from published build fingerprint")
        collection_index = {str(item.get("id") or ""): item for item in collection_rows}
        if set(collection_index) != set(COLLECTIONS):
            errors.append("published release lacks one or more v1 collections")
        total_items = 0
        total_pages = 0
        max_observed_page_bytes = 0
        for collection in COLLECTIONS:
            entry = collection_index.get(collection) or {}
            manifest_url, manifest_body = fetch(
                base_url,
                str(entry.get("manifest") or ""),
                timeout=timeout,
                max_bytes=max_manifest_bytes,
            )
            fetched_bytes += len(manifest_body)
            fetched_files += 1
            if sha256_bytes(manifest_body) != entry.get("manifest_sha256"):
                errors.append(f"{collection} manifest SHA-256 mismatch")
            manifest = parse_object(manifest_body, manifest_url)
            pages = manifest.get("pages") or []
            seen_items = 0
            previous_key: str | None = None
            previous_cursor: str | None = None
            for offset, page_entry in enumerate(pages):
                page_url, page_body = fetch(
                    base_url,
                    str(page_entry.get("href") or ""),
                    timeout=timeout,
                    max_bytes=max_page_bytes,
                )
                fetched_bytes += len(page_body)
                fetched_files += 1
                max_observed_page_bytes = max(max_observed_page_bytes, len(page_body))
                page_hash = sha256_bytes(page_body)
                if page_hash != page_entry.get("sha256") or page_hash not in page_url:
                    errors.append(f"{collection} page {offset + 1} SHA-256 mismatch")
                page = parse_object(page_body, page_url)
                page_info = page.get("page_info") or {}
                items = page.get("items") or []
                expected_next = (
                    pages[offset + 1].get("href") if offset + 1 < len(pages) else None
                )
                if page_info.get("next") != expected_next:
                    errors.append(f"{collection} page {offset + 1} next link mismatch")
                if page_info.get("start_cursor") != previous_cursor:
                    errors.append(
                        f"{collection} page {offset + 1} start cursor mismatch"
                    )
                for item in items:
                    item_id = str(item.get("id") or "")
                    if not item_id or (
                        previous_key is not None and item_id <= previous_key
                    ):
                        errors.append(f"{collection} order/identity violation")
                    previous_key = item_id
                    item_provenance = item.get("provenance") or {}
                    if item_provenance.get("api_release_id") != api_release_id:
                        errors.append(f"{collection} record provenance mismatch")
                    if item_provenance.get("official_real_record") is not True:
                        errors.append(
                            f"{collection} contains a record not marked official real"
                        )
                if items:
                    decoded = decode_cursor(str(page_info.get("end_cursor") or ""))
                    if decoded.get("after") != items[-1].get("id"):
                        errors.append(
                            f"{collection} page {offset + 1} cursor position mismatch"
                        )
                    if (
                        decoded.get("collection") != collection
                        or decoded.get("release") != api_release_id
                    ):
                        errors.append(
                            f"{collection} page {offset + 1} cursor scope mismatch"
                        )
                previous_cursor = page_info.get("end_cursor")
                seen_items += len(items)
            if seen_items != int(manifest.get("item_count") or 0):
                errors.append(f"{collection} item count mismatch")
            total_items += seen_items
            total_pages += len(pages)
        policy = pointer.get("policy") or {}
        if policy.get("official_real_records_only") is not True:
            errors.append("live pointer does not require official real records")
        if policy.get("synthetic_or_mock_records") != "forbidden":
            errors.append("live pointer does not forbid generated records")
        if policy.get("public_domain_personal_information") != "retained":
            errors.append("live pointer does not retain official public identity")
    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        urllib.error.URLError,
    ) as exc:
        errors.append(f"verification exception: {type(exc).__name__}: {exc}")
        api_release_id = ""
        total_items = 0
        total_pages = 0
        max_observed_page_bytes = 0
        current = {}
    return {
        "schema_version": "live_evidence_api_verification_v1",
        "status": "verified_live_evidence_api" if not errors else "error",
        "passed": not errors,
        "base_url": base_url,
        "checks": {
            "api_release_id": api_release_id,
            "upstream_scale_release_id": current.get("upstream_scale_release_id"),
            "collections_total": len(COLLECTIONS),
            "pages_total": total_pages,
            "items_total": total_items,
            "fetched_files": fetched_files,
            "fetched_bytes": fetched_bytes,
            "max_observed_page_bytes": max_observed_page_bytes,
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://votaconlachola.org")
    parser.add_argument("--expected-api-release", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-page-bytes", type=int, default=2_500_000)
    parser.add_argument("--max-manifest-bytes", type=int, default=2_500_000)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify(
        base_url=args.base_url,
        expected_api_release=args.expected_api_release,
        timeout=args.timeout,
        max_page_bytes=args.max_page_bytes,
        max_manifest_bytes=args.max_manifest_bytes,
    )
    body = canonical_bytes(report, pretty=True)
    if args.json_out:
        atomic_write(args.json_out, body)
    print(body.decode("utf-8"), end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
