#!/usr/bin/env python3
"""Verify the live spending page, public JSON, and official PLACSP links."""

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
            "docs/etl/sprints/SPENDING-20260819/evidence/"
            "live-placsp-spending-verification.json"
        ),
    )
    return parser.parse_args()


def fetch(
    url: str, timeout: float, max_bytes: int | None = None
) -> tuple[bytes, int, str]:
    request = Request(
        url, headers={"User-Agent": "vota-con-la-chola-spending-verifier/1.0"}
    )
    with urlopen(request, timeout=timeout) as response:
        data = response.read() if max_bytes is None else response.read(max_bytes)
        return data, int(response.status), response.headers.get("Content-Type", "")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    page_url = f"{base_url}/spending/"
    artifact_url = f"{base_url}/spending/data/placsp-sample.json"
    errors: list[str] = []

    page_bytes, page_status, page_type = fetch(page_url, args.timeout)
    artifact_bytes, artifact_status, artifact_type = fetch(artifact_url, args.timeout)
    page_text = page_bytes.decode("utf-8", errors="replace")
    for marker in (
        "Dinero público con evidencia",
        "Adjudicado no significa pagado",
        "Veinte adjudicaciones reales, identidad pública intacta",
    ):
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
    if artifact.get("methodology", {}).get("award_is_payment") is not False:
        errors.append("live artifact does not separate award from payment")

    items = artifact.get("items") or []
    if len(items) != 20:
        errors.append(f"live artifact must contain 20 items, found {len(items)}")
    identity_counts = {
        "legal_entity": 0,
        "potential_natural_person": 0,
        "unclassified": 0,
    }
    probe_by_category: dict[str, dict] = {}
    for item in items:
        if item.get("spending_kind") != "procurement_award":
            errors.append(f"non-award live item: {item.get('spending_item_id')}")
        if item.get("dates", {}).get("paid_on") is not None:
            errors.append(f"live award implies payment: {item.get('spending_item_id')}")
        actors = item.get("actors") or []
        if len(actors) != 2:
            errors.append(
                f"live item missing actor pair: {item.get('spending_item_id')}"
            )
            continue
        supplier = actors[1]
        category = supplier.get("source_category")
        if category in identity_counts:
            identity_counts[category] += 1
            probe_by_category.setdefault(category, item)
        if not supplier.get("source_label"):
            errors.append(
                f"live supplier label missing: {item.get('spending_item_id')}"
            )
        evidence = item.get("evidence") or []
        if not evidence or evidence[0].get("evidence_state") != "captured_bytes":
            errors.append(
                f"live primary evidence missing: {item.get('spending_item_id')}"
            )
        if len(str(item.get("provenance", {}).get("source_record_sha256") or "")) != 64:
            errors.append(f"live source hash missing: {item.get('spending_item_id')}")

    expected_identity_counts = {
        "legal_entity": 10,
        "potential_natural_person": 5,
        "unclassified": 5,
    }
    if identity_counts != expected_identity_counts:
        errors.append(f"live identity strata mismatch: {identity_counts}")

    upstream_probes: list[dict] = []
    for category in expected_identity_counts:
        item = probe_by_category.get(category)
        if item is None:
            continue
        source_url = item.get("provenance", {}).get("source_url")
        if not str(source_url or "").startswith("https://contrataciondelestado.es/"):
            errors.append(f"non-official evidence URL for {category}")
            continue
        try:
            data, status, content_type = fetch(
                str(source_url), args.timeout, 256 * 1024
            )
        except Exception as exc:  # noqa: BLE001 - verifier records exact upstream failure
            errors.append(f"official PLACSP probe failed for {category}: {exc}")
            upstream_probes.append(
                {
                    "category": category,
                    "url": source_url,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if status != 200:
            errors.append(f"official PLACSP probe HTTP {status} for {category}")
        if not data:
            errors.append(f"official PLACSP probe empty for {category}")
        upstream_probes.append(
            {
                "category": category,
                "url": source_url,
                "status": status,
                "content_type": content_type,
                "prefix_bytes": len(data),
                "prefix_sha256": sha256_bytes(data),
            }
        )

    report = {
        "schema_version": "live_placsp_spending_verification_v1",
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
        "identity_counts": identity_counts,
        "official_placsp_probes": upstream_probes,
        "checks": {
            "page_markers": 3,
            "real_data_only": artifact.get("real_data_only") is True,
            "award_not_payment": artifact.get("methodology", {}).get("award_is_payment")
            is False,
            "public_identity_retained": artifact.get("public_domain_information_policy")
            == "retained_exactly",
            "three_identity_strata_probed": len(upstream_probes) == 3,
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
