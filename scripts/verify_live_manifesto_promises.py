#!/usr/bin/env python3
"""Verify the published promises page, JSON contract, and official source bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from ingest_manifesto_promises import BNG_BYTES, BNG_PAGES, BNG_SHA256, BNG_SOURCE_URL


def fetch(url: str, timeout: float) -> tuple[bytes, int, str]:
    request = Request(
        url, headers={"User-Agent": "vota-con-la-chola-promises-verifier/1.0"}
    )
    with urlopen(request, timeout=timeout) as response:
        return (
            response.read(),
            int(response.status),
            response.headers.get("Content-Type", ""),
        )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://votaconlachola.org")
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path(
            "docs/etl/sprints/PROMISES-20260819/evidence/"
            "live-promises-bng-2023-verification.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    page_url = f"{base_url}/promises/"
    artifact_url = f"{base_url}/promises/data/bng-2023.json"
    errors: list[str] = []

    page_bytes, page_status, page_type = fetch(page_url, args.timeout)
    artifact_bytes, artifact_status, artifact_type = fetch(artifact_url, args.timeout)
    source_bytes, source_status, source_type = fetch(BNG_SOURCE_URL, args.timeout)

    page_text = page_bytes.decode("utf-8", errors="replace")
    for marker in (
        "Promesas con evidencia",
        "Lo dicho no es lo cumplido",
        "Veinte compromisos, veinte anclas",
    ):
        if marker not in page_text:
            errors.append(f"page marker missing: {marker}")
    try:
        artifact = json.loads(artifact_bytes)
    except json.JSONDecodeError as exc:
        artifact = {}
        errors.append(f"artifact is not JSON: {exc}")

    if page_status != 200:
        errors.append(f"page HTTP status {page_status}")
    if artifact_status != 200:
        errors.append(f"artifact HTTP status {artifact_status}")
    if source_status != 200:
        errors.append(f"official source HTTP status {source_status}")
    if artifact.get("release_id") != args.expected_release:
        errors.append("live release_id does not match expected release")
    if artifact.get("real_data_only") is not True:
        errors.append("live real_data_only is not true")
    if artifact.get("synthetic_or_mock") is not False:
        errors.append("live synthetic_or_mock is not false")
    if artifact.get("public_domain_information_policy") != "retained_exactly":
        errors.append("live public-domain information policy mismatch")
    if artifact.get("source", {}).get("content_sha256") != BNG_SHA256:
        errors.append("live artifact official source hash mismatch")
    if artifact.get("source", {}).get("source_url") != BNG_SOURCE_URL:
        errors.append("live artifact official source URL mismatch")
    if artifact.get("source", {}).get("page_count") != BNG_PAGES:
        errors.append("live artifact official source page count mismatch")
    items = artifact.get("items", [])
    if not isinstance(items, list) or len(items) != 20:
        errors.append("live artifact must contain 20 items")
        items = []
    for item in items:
        evidence = item.get("evidence", {})
        quote = evidence.get("exact_quote", "")
        if item.get("review", {}).get("status") != "rule_confirmed":
            errors.append(f"unconfirmed live item: {item.get('claim_id')}")
        if sha256_bytes(str(quote).encode("utf-8")) != evidence.get("quote_sha256"):
            errors.append(f"quote hash mismatch: {item.get('claim_id')}")
        if evidence.get("document_sha256") != BNG_SHA256:
            errors.append(f"document hash mismatch: {item.get('claim_id')}")

    official_source_sha256 = sha256_bytes(source_bytes)
    if len(source_bytes) != BNG_BYTES:
        errors.append(f"official source byte mismatch: {len(source_bytes)}")
    if official_source_sha256 != BNG_SHA256:
        errors.append(f"official source SHA-256 mismatch: {official_source_sha256}")
    if not source_bytes.startswith(b"%PDF-"):
        errors.append("official source response is not PDF")

    report = {
        "schema_version": "live_manifesto_promises_verification_v1",
        "status": "ok" if not errors else "error",
        "verified_at": datetime.now(UTC).isoformat(),
        "expected_release": args.expected_release,
        "live_release": artifact.get("release_id"),
        "page": {
            "url": page_url,
            "http_status": page_status,
            "content_type": page_type,
            "bytes": len(page_bytes),
            "sha256": sha256_bytes(page_bytes),
        },
        "artifact": {
            "url": artifact_url,
            "http_status": artifact_status,
            "content_type": artifact_type,
            "bytes": len(artifact_bytes),
            "sha256": sha256_bytes(artifact_bytes),
            "items": len(items),
        },
        "official_source": {
            "url": BNG_SOURCE_URL,
            "http_status": source_status,
            "content_type": source_type,
            "bytes": len(source_bytes),
            "sha256": official_source_sha256,
        },
        "checks": {
            "page_markers": 3,
            "public_items": len(items),
            "quote_hashes": len(items),
            "official_source_exact": official_source_sha256 == BNG_SHA256,
            "real_data_only": artifact.get("real_data_only") is True,
            "public_domain_information_retained": artifact.get(
                "public_domain_information_policy"
            )
            == "retained_exactly",
        },
        "errors": errors,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
