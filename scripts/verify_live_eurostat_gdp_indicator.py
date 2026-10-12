#!/usr/bin/env python3
"""Verify the live indicator page, exact artifact, and official Eurostat origin."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://votaconlachola.org")
    parser.add_argument("--expected-release", required=True)
    parser.add_argument(
        "--expected-artifact",
        type=Path,
        default=Path("ui/site/public/indicators/data/eurostat-gdp-es.json"),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path(
            "docs/etl/sprints/INDICATORS-20260820/evidence/"
            "live-eurostat-gdp-verification.json"
        ),
    )
    return parser.parse_args()


def fetch(url: str, timeout: float, max_bytes: int | None = None) -> tuple[bytes, int, str]:
    request = Request(
        url, headers={"User-Agent": "vota-con-la-chola-indicator-verifier/1.0"}
    )
    with urlopen(request, timeout=timeout) as response:
        data = response.read() if max_bytes is None else response.read(max_bytes)
        return data, int(response.status), response.headers.get("Content-Type", "")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    page_url = f"{base_url}/indicators/"
    artifact_url = f"{base_url}/indicators/data/eurostat-gdp-es.json"
    errors: list[str] = []

    page_bytes, page_status, page_type = fetch(page_url, args.timeout)
    artifact_bytes, artifact_status, artifact_type = fetch(artifact_url, args.timeout)
    expected_bytes = args.expected_artifact.read_bytes()
    page_text = page_bytes.decode("utf-8", errors="replace")
    page_markers = (
        "Lo que cambió, sin inventar por qué",
        "Un indicador no reparte mérito ni culpa",
        "Toda la geografía española del slice",
    )
    for marker in page_markers:
        if marker not in page_text:
            errors.append(f"page marker missing: {marker}")
    if page_status != 200:
        errors.append(f"page HTTP status {page_status}")
    if artifact_status != 200:
        errors.append(f"artifact HTTP status {artifact_status}")
    if artifact_bytes != expected_bytes:
        errors.append("live artifact bytes differ from the validated local artifact")

    try:
        artifact = json.loads(artifact_bytes)
    except json.JSONDecodeError as exc:
        artifact = {}
        errors.append(f"artifact is not JSON: {exc}")
    if artifact.get("release_id") != args.expected_release:
        errors.append("live release_id does not match expected release")
    policy = artifact.get("policy") or {}
    coverage = artifact.get("coverage") or {}
    full_corpus = artifact.get("full_corpus") or {}
    if policy.get("real_data_only") is not True or policy.get("synthetic_or_mock") is not False:
        errors.append("live real-only policy mismatch")
    if policy.get("official_public_domain_information_retained") is not True:
        errors.append("live public-domain retention policy mismatch")
    if policy.get("causal_claim") != "none":
        errors.append("live artifact contains unsupported causal claim")
    if coverage.get("series") != 86 or coverage.get("observations") != 2_091:
        errors.append("live bounded slice count mismatch")
    if coverage.get("source_status_codes", {}).get("p") != 113:
        errors.append("live provisional-cell count mismatch")
    if coverage.get("revision_baseline") != 2_091:
        errors.append("live baseline revision count mismatch")
    if full_corpus.get("observations") != 1_755_809:
        errors.append("live million-row corpus reference mismatch")
    if full_corpus.get("representative_scope") is not False:
        errors.append("live corpus must state non-representative scope")

    official_probes: list[dict[str, object]] = []
    source = artifact.get("source") or {}
    for label, url in (
        ("dataset", source.get("source_url")),
        ("methodology", source.get("methodology_url")),
        ("reuse_policy", source.get("license_url")),
    ):
        try:
            data, status, content_type = fetch(str(url), args.timeout, 128 * 1024)
            if status != 200 or not data:
                errors.append(f"official Eurostat {label} probe invalid: HTTP {status}")
            official_probes.append(
                {
                    "label": label,
                    "url": url,
                    "status": status,
                    "content_type": content_type,
                    "prefix_bytes": len(data),
                    "prefix_sha256": sha256_bytes(data),
                }
            )
        except Exception as exc:  # noqa: BLE001 - evidence exact external state
            errors.append(f"official Eurostat {label} probe failed: {type(exc).__name__}: {exc}")
            official_probes.append(
                {
                    "label": label,
                    "url": url,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    report = {
        "schema_version": "live_eurostat_gdp_verification_v1",
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
            "series": coverage.get("series"),
            "observations": coverage.get("observations"),
            "provisional": coverage.get("source_status_codes", {}).get("p"),
        },
        "official_eurostat_probes": official_probes,
        "checks": {
            "page_markers": len(page_markers),
            "exact_artifact_parity": artifact_bytes == expected_bytes,
            "real_data_only": policy.get("real_data_only") is True,
            "public_domain_information_retained": policy.get(
                "official_public_domain_information_retained"
            )
            is True,
            "no_causal_claim": policy.get("causal_claim") == "none",
            "bounded_slice_complete": coverage.get("observations") == 2_091,
            "million_row_corpus_referenced": full_corpus.get("observations") == 1_755_809,
            "official_source_probes": len(official_probes) == 3,
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
