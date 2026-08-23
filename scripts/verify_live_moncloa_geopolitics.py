#!/usr/bin/env python3
"""Verify the live geopolitical page, artifact, and official Moncloa sources."""

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
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path(
            "docs/etl/sprints/GEOPOLITICS-20260819/evidence/"
            "live-moncloa-geopolitics-verification.json"
        ),
    )
    return parser.parse_args()


def fetch(
    url: str, timeout: float, max_bytes: int | None = None
) -> tuple[bytes, int, str]:
    request = Request(
        url, headers={"User-Agent": "vota-con-la-chola-geopolitics-verifier/1.0"}
    )
    with urlopen(request, timeout=timeout) as response:
        data = response.read() if max_bytes is None else response.read(max_bytes)
        return data, int(response.status), response.headers.get("Content-Type", "")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    page_url = f"{base_url}/geopolitics/"
    artifact_url = f"{base_url}/geopolitics/data/moncloa-sample.json"
    errors: list[str] = []

    page_bytes, page_status, page_type = fetch(page_url, args.timeout)
    artifact_bytes, artifact_status, artifact_type = fetch(artifact_url, args.timeout)
    page_text = page_bytes.decode("utf-8", errors="replace")
    page_markers = (
        "Geopolítica sin rellenar los huecos",
        "Autorización no significa tratado en vigor",
        "Acciones oficiales y estados desconocidos a la vista",
    )
    for marker in page_markers:
        if marker not in page_text:
            errors.append(f"page marker missing: {marker}")
    if page_status != 200:
        errors.append(f"page HTTP status {page_status}")
    if artifact_status != 200:
        errors.append(f"artifact HTTP status {artifact_status}")

    try:
        artifact = json.loads(artifact_bytes)
    except json.JSONDecodeError as exc:
        artifact = {}
        errors.append(f"artifact is not JSON: {exc}")

    if artifact.get("release_id") != args.expected_release:
        errors.append("live release_id does not match expected release")
    policy = artifact.get("policy") or {}
    if policy.get("real_data_only") is not True:
        errors.append("live real_data_only is not true")
    if policy.get("synthetic_or_mock") is not False:
        errors.append("live synthetic_or_mock is not false")
    if policy.get("official_public_domain_information_retained") is not True:
        errors.append("live public identity retention policy mismatch")
    if policy.get("inference_level") != "fact_only":
        errors.append("live inference level is not fact_only")

    coverage = artifact.get("coverage") or {}
    records = artifact.get("records") or []
    if len(records) != 2 or coverage.get("actions") != 2:
        errors.append(f"live artifact must contain 2 actions, found {len(records)}")
    if coverage.get("actors") != 11:
        errors.append("live artifact actor count mismatch")
    if coverage.get("positions") != 0:
        errors.append("live artifact contains unsupported position rows")
    if coverage.get("later_observations") != 0:
        errors.append("live artifact contains unsupported later observations")

    for record in records:
        action_id = record.get("geopolitical_action_id")
        if record.get("action_kind") != "treaty_process":
            errors.append(f"action kind mismatch: {action_id}")
        if record.get("action_status") != "authorized":
            errors.append(f"action status mismatch: {action_id}")
        if record.get("procedure_stage") != (
            "domestic_referral_and_authorization_to_consent"
        ):
            errors.append(f"procedure stage mismatch: {action_id}")
        for state_key in (
            "binding_state",
            "entry_into_force_state",
            "implementation_state",
            "outcome_state",
            "position_state",
        ):
            if record.get(state_key) != "not_assessed":
                errors.append(f"unsafe {state_key}: {action_id}")
        summary = str(record.get("summary") or "")
        if str(record.get("instrument_name") or "") not in summary:
            errors.append(f"instrument is not source-backed: {action_id}")
        evidence = record.get("evidence") or []
        if len(evidence) != 1 or evidence[0].get("exact_quote") != summary:
            errors.append(f"exact evidence mismatch: {action_id}")
        for actor in record.get("actors") or []:
            label = str(actor.get("source_label") or "")
            if label != "Gobierno de España / La Moncloa" and label not in summary:
                errors.append(f"actor is not present in official excerpt: {label}")

    upstream_probes: list[dict] = []
    for record in records:
        evidence = record.get("evidence") or []
        source_url = evidence[0].get("source_url") if evidence else None
        try:
            data, status, content_type = fetch(
                str(source_url), args.timeout, 256 * 1024
            )
        except Exception as exc:  # noqa: BLE001 - report exact upstream state
            errors.append(f"official Moncloa probe failed: {exc}")
            upstream_probes.append(
                {
                    "url": source_url,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if status != 200:
            errors.append(f"official Moncloa probe HTTP {status}")
        if not data:
            errors.append("official Moncloa probe returned empty body")
        upstream_probes.append(
            {
                "url": source_url,
                "status": status,
                "content_type": content_type,
                "prefix_bytes": len(data),
                "prefix_sha256": sha256_bytes(data),
            }
        )

    report = {
        "schema_version": "live_moncloa_geopolitics_verification_v1",
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
            "actions": len(records),
            "actors": coverage.get("actors"),
        },
        "official_moncloa_probes": upstream_probes,
        "checks": {
            "page_markers": len(page_markers),
            "real_data_only": policy.get("real_data_only") is True,
            "public_identity_retained": policy.get(
                "official_public_domain_information_retained"
            )
            is True,
            "fact_only": policy.get("inference_level") == "fact_only",
            "no_position_rows": coverage.get("positions") == 0,
            "no_later_observations": coverage.get("later_observations") == 0,
            "two_official_source_probes": len(upstream_probes) == 2,
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
