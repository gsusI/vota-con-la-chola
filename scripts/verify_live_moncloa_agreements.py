#!/usr/bin/env python3
"""Verify the live agreements page, JSON, and official Moncloa evidence links."""

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
            "docs/etl/sprints/AGREEMENTS-20260819/evidence/"
            "live-moncloa-agreements-verification.json"
        ),
    )
    return parser.parse_args()


def fetch(
    url: str, timeout: float, max_bytes: int | None = None
) -> tuple[bytes, int, str]:
    request = Request(
        url, headers={"User-Agent": "vota-con-la-chola-agreements-verifier/1.0"}
    )
    with urlopen(request, timeout=timeout) as response:
        data = response.read() if max_bytes is None else response.read(max_bytes)
        return data, int(response.status), response.headers.get("Content-Type", "")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    page_url = f"{base_url}/agreements/"
    artifact_url = f"{base_url}/agreements/data/moncloa-sample.json"
    errors: list[str] = []

    page_bytes, page_status, page_type = fetch(page_url, args.timeout)
    artifact_bytes, artifact_status, artifact_type = fetch(artifact_url, args.timeout)
    page_text = page_bytes.decode("utf-8", errors="replace")
    page_markers = (
        "Acuerdos y reuniones con evidencia",
        "Reunión no significa influencia",
        "Resúmenes oficiales, sin completar huecos",
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
    if artifact.get("real_data_only") is not True:
        errors.append("live real_data_only is not true")
    if artifact.get("synthetic_or_mock") is not False:
        errors.append("live synthetic_or_mock is not false")
    if artifact.get("public_domain_information_policy") != "retained_exactly":
        errors.append("live public-domain information policy mismatch")

    counts = artifact.get("counts") or {}
    records = artifact.get("records") or []
    if len(records) != 11 or counts.get("agreements") != 11:
        errors.append(f"live artifact must contain 11 agreements, found {len(records)}")
    if counts.get("attendance_claims") != 0:
        errors.append("live artifact contains unsupported attendance claims")
    if counts.get("influence_assertions") != 0:
        errors.append("live fact artifact contains influence assertions")
    if artifact.get("influence_assertions") != []:
        errors.append("live influence assertion list is not empty")

    for record in records:
        meeting = record.get("meeting") or {}
        agreement = record.get("agreement") or {}
        provenance = record.get("provenance") or {}
        if meeting.get("attendance_disclosure_state") != "not_disclosed":
            errors.append(f"attendance state mismatch: {meeting.get('meeting_id')}")
        if any(
            participant.get("attendance_claim_state") != "not_claimed"
            for participant in meeting.get("participants") or []
        ):
            errors.append(f"unsupported attendance claim: {meeting.get('meeting_id')}")
        if agreement.get("agreement_status") != "adopted":
            errors.append(f"agreement status mismatch: {agreement.get('agreement_id')}")
        if agreement.get("influence_state") != "not_asserted":
            errors.append(f"influence state mismatch: {agreement.get('agreement_id')}")
        if "acuerdo" not in str(agreement.get("summary") or "").casefold():
            errors.append(f"agreement excerpt is not explicit: {agreement.get('agreement_id')}")
        if not str(provenance.get("source_url") or "").startswith(
            "https://www.lamoncloa.gob.es/"
        ):
            errors.append(f"non-official source URL: {agreement.get('agreement_id')}")

    probe_indexes = sorted({0, len(records) // 2, max(0, len(records) - 1)})
    upstream_probes: list[dict] = []
    for index in probe_indexes:
        if not records:
            break
        source_url = records[index].get("provenance", {}).get("source_url")
        try:
            data, status, content_type = fetch(
                str(source_url), args.timeout, 256 * 1024
            )
        except Exception as exc:  # noqa: BLE001 - verifier records exact upstream failure
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
        "schema_version": "live_moncloa_agreements_verification_v1",
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
            "agreements": len(records),
        },
        "official_moncloa_probes": upstream_probes,
        "checks": {
            "page_markers": len(page_markers),
            "real_data_only": artifact.get("real_data_only") is True,
            "public_identity_retained": artifact.get(
                "public_domain_information_policy"
            )
            == "retained_exactly",
            "no_attendance_claims": counts.get("attendance_claims") == 0,
            "no_influence_assertions": counts.get("influence_assertions") == 0,
            "three_official_source_probes": len(upstream_probes) == 3,
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
