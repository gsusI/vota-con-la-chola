#!/usr/bin/env python3
"""Verify the live comparison route, exact release artifact, and official sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_EXPECTED_ARTIFACT = Path(
    "ui/site/public/comparisons/data/comparisons.json"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/COMPARISON-ENGINE-20260820/evidence/"
    "live-promise-action-comparisons-verification.json"
)
PUBLIC_IDENTITY_POLICY = (
    "retain_official_public_identity_exclude_only_secrets_private_session_state_"
    "and_workstation_traces"
)
EXPECTED_COUNTS = {
    "action_pairs_total": 4,
    "bounded_action_search_assessments_total": 1,
    "comparisons_total": 5,
    "evidence_total": 18,
    "strong_pairs_total": 0,
    "unique_claims_total": 4,
}
EXPECTED_STATUS_COUNTS = {
    "ambiguous_mapping": 3,
    "insufficient_evidence": 1,
    "not_comparable": 1,
}
ALLOWED_STATUSES = {
    "aligned",
    "conflicted",
    "insufficient_evidence",
    "ambiguous_mapping",
    "changed_framing",
    "not_comparable",
}
FORBIDDEN_V1_STATUSES = {"aligned", "conflicted", "changed_framing"}
EXPECTED_ACTION_IDENTITIES = Counter(
    {
        "MARÍA CARMEN DA SILVA MÉNDEZ": 3,
        "Néstor Rego Candamil": 1,
    }
)
PAGE_MARKERS = (
    "Lo dicho frente a lo observado",
    "Comparar no es sentenciar",
    "Evaluaciones revisadas",
    "Pares con acción",
    "Búsquedas acotadas",
    "Ranking oculto",
    "causalidad ni corrupción",
)
OFFICIAL_SOURCE_DOMAIN_SUFFIXES = (
    "bng.gal",
    "congreso.es",
    "senado.es",
)
PROBE_HOST_PRIORITY = (
    "www.bng.gal",
    "www.senado.es",
    "www.congreso.es",
)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "file:///",
    "Authorization: Bearer",
    "cookie_jar",
    "private_key",
)
FAKE_MARKERS = (
    "example.invalid",
    "example.test",
    "fixture data",
    "generated person",
    "mock person",
    "placeholder person",
    "synthetic sample",
)

FetchResult = tuple[bytes, int, str, str]
Fetcher = Callable[[str, float, int, bool], FetchResult]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_http(
    url: str,
    timeout: float,
    max_bytes: int,
    prefix_only: bool = False,
) -> FetchResult:
    request = Request(
        url,
        headers={
            "User-Agent": "vota-con-la-chola-comparison-verifier/1.0",
            "Accept": "application/json,text/html,application/pdf,application/xml,*/*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read(max_bytes if prefix_only else max_bytes + 1)
        if not prefix_only and len(body) > max_bytes:
            raise ValueError(f"response exceeds {max_bytes} byte budget: {url}")
        return (
            body,
            int(response.status),
            response.headers.get("Content-Type", ""),
            response.geturl(),
        )


def official_source_host(url: object) -> str | None:
    try:
        parsed = urlparse(str(url or ""))
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host:
        return None
    if any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in OFFICIAL_SOURCE_DOMAIN_SUFFIXES
    ):
        return host
    return None


def same_official_source_domain(first_host: str, second_host: str | None) -> bool:
    if not second_host:
        return False
    return any(
        (first_host == suffix or first_host.endswith(f".{suffix}"))
        and (second_host == suffix or second_host.endswith(f".{suffix}"))
        for suffix in OFFICIAL_SOURCE_DOMAIN_SUFFIXES
    )


def same_origin(first: str, second: str) -> bool:
    left = urlparse(first)
    right = urlparse(second)
    return (left.scheme.casefold(), left.netloc.casefold()) == (
        right.scheme.casefold(),
        right.netloc.casefold(),
    )


def select_probe_urls(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    urls_by_host: dict[str, set[str]] = {}
    for item in items:
        for evidence in item.get("evidence") or []:
            if not isinstance(evidence, dict):
                continue
            if evidence.get("evidence_role") != "primary":
                continue
            if evidence.get("evidence_side") not in {"claim", "action"}:
                continue
            source_url = str(evidence.get("source_url") or "").strip()
            host = official_source_host(source_url)
            if host:
                urls_by_host.setdefault(host, set()).add(source_url)
    return [
        (host, sorted(urls_by_host[host])[0])
        for host in PROBE_HOST_PRIORITY
        if host in urls_by_host
    ]


def add_check(
    checks: dict[str, bool],
    errors: list[str],
    key: str,
    condition: object,
    message: str,
) -> None:
    passed = bool(condition)
    checks[key] = passed
    if not passed:
        errors.append(message)


def parse_artifact(data: bytes, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} artifact is invalid JSON: {type(exc).__name__}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} artifact top-level value is not an object")
        return {}
    return value


def validate_artifact_contract(
    artifact: dict[str, Any],
    *,
    expected_release: str,
    expected_semantic_sha256: str,
    label: str,
) -> tuple[dict[str, bool], list[str], list[tuple[str, str]]]:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    items_value = artifact.get("items")
    items = (
        items_value
        if isinstance(items_value, list)
        and all(isinstance(item, dict) for item in items_value)
        else []
    )
    if not items and items_value != []:
        errors.append(f"{label} items is not a list of objects")

    add_check(
        checks,
        errors,
        "release_id",
        artifact.get("release_id") == expected_release,
        f"{label} release_id differs from the pinned release",
    )
    add_check(
        checks,
        errors,
        "semantic_sha256",
        artifact.get("semantic_sha256") == expected_semantic_sha256,
        f"{label} semantic SHA-256 differs from the pinned semantic release",
    )
    add_check(
        checks,
        errors,
        "schema_version",
        artifact.get("schema_version") == "promise_action_comparison_v1",
        f"{label} comparison schema version mismatch",
    )
    add_check(
        checks,
        errors,
        "real_data_only",
        artifact.get("real_data_only") is True
        and artifact.get("synthetic_or_mock") is False,
        f"{label} does not enforce real data only",
    )
    add_check(
        checks,
        errors,
        "public_identity_policy",
        artifact.get("public_domain_information_policy") == PUBLIC_IDENTITY_POLICY,
        f"{label} official public identity retention policy mismatch",
    )

    hash_contract = artifact.get("hash_contract") or {}
    input_releases = artifact.get("input_releases") or {}
    reviewed_mappings = input_releases.get("reviewed_mappings") or {}
    recorded_hashes = [
        artifact.get("semantic_sha256"),
        hash_contract.get("semantic_sha256"),
        hash_contract.get("reviewed_mappings_canonical_sha256"),
        reviewed_mappings.get("canonical_sha256"),
    ]
    for input_release in input_releases.values():
        if isinstance(input_release, dict):
            recorded_hashes.extend(
                value
                for key, value in input_release.items()
                if key in {"sha256", "selected_scope_sha256"}
            )
    add_check(
        checks,
        errors,
        "hash_contract",
        hash_contract.get("semantic_sha256") == expected_semantic_sha256
        and hash_contract.get("reviewed_mappings_canonical_sha256")
        == reviewed_mappings.get("canonical_sha256")
        and all(HEX_SHA256.fullmatch(str(value or "")) for value in recorded_hashes),
        f"{label} semantic/source hash contract mismatch",
    )

    counts = artifact.get("counts") or {}
    actual_status_counts = Counter(
        str(item.get("comparison_status")) for item in items
    )
    actual_nonzero_status_counts = dict(sorted(actual_status_counts.items()))
    action_items = [item for item in items if isinstance(item.get("action"), dict)]
    bounded_items = [item for item in items if item.get("action") is None]
    actual_counts = {
        "action_pairs_total": len(action_items),
        "bounded_action_search_assessments_total": len(bounded_items),
        "comparisons_total": len(items),
        "evidence_total": sum(len(item.get("evidence") or []) for item in items),
        "strong_pairs_total": sum(
            actual_status_counts.get(status, 0) for status in {"aligned", "conflicted"}
        ),
        "unique_claims_total": len(
            {
                str((item.get("claim") or {}).get("claim_id"))
                for item in items
            }
        ),
    }
    add_check(
        checks,
        errors,
        "exact_counts",
        counts == EXPECTED_COUNTS and actual_counts == EXPECTED_COUNTS,
        f"{label} comparison/evidence count contract mismatch",
    )
    add_check(
        checks,
        errors,
        "exact_status_counts",
        artifact.get("status_counts") == EXPECTED_STATUS_COUNTS
        and actual_nonzero_status_counts == EXPECTED_STATUS_COUNTS
        and set(actual_status_counts).issubset(ALLOWED_STATUSES),
        f"{label} comparison status distribution mismatch",
    )
    add_check(
        checks,
        errors,
        "no_strong_or_changed_framing",
        not (set(actual_status_counts) & FORBIDDEN_V1_STATUSES)
        and all(item.get("directional_countable") is False for item in items),
        f"{label} contains a forbidden v1 directional or changed-framing verdict",
    )

    comparison_ids = [str(item.get("comparison_id") or "") for item in items]
    mapping_review_ids = [str(item.get("mapping_review_id") or "") for item in items]
    add_check(
        checks,
        errors,
        "stable_unique_ids",
        len(set(comparison_ids)) == len(items)
        and len(set(mapping_review_ids)) == len(items)
        and all(value.startswith("vclc:promise-action-comparison:") for value in comparison_ids)
        and all(value.startswith("vclc:comparison-mapping-review:") for value in mapping_review_ids),
        f"{label} comparison/review identity contract mismatch",
    )

    action_identity_counts = Counter(
        str((item.get("action") or {}).get("member_name") or "")
        for item in action_items
    )
    claim_labels = {
        str((item.get("claim") or {}).get("actor_label") or "") for item in items
    }
    identity_evidence_ok = all(
        any(
            edge.get("evidence_side") == "actor_link"
            and edge.get("evidence_role") == "identity"
            and str((item.get("action") or {}).get("member_name") or "")
            in str(edge.get("exact_quote") or "")
            for edge in item.get("evidence") or []
        )
        for item in action_items
    )
    capacity_ok = all(
        (item.get("actor_capacity") or {}).get("assertion_capacity")
        == "party_manifesto_publisher"
        and (
            (item.get("actor_capacity") or {}).get("action_capacity")
            == "individual_legislator_roll_call"
            if item.get("action") is not None
            else (item.get("actor_capacity") or {}).get("action_capacity") is None
        )
        for item in items
    )
    add_check(
        checks,
        errors,
        "official_public_identities_exact",
        claim_labels == {"BNG"}
        and action_identity_counts == EXPECTED_ACTION_IDENTITIES
        and identity_evidence_ok
        and capacity_ok,
        f"{label} official public identity/capacity contract mismatch",
    )

    evidence_ok = True
    for item in items:
        evidence_rows = item.get("evidence") or []
        if not isinstance(evidence_rows, list):
            evidence_ok = False
            continue
        for edge in evidence_rows:
            if not isinstance(edge, dict):
                evidence_ok = False
                continue
            evidence_ok = evidence_ok and bool(str(edge.get("exact_quote") or "").strip())
            evidence_ok = evidence_ok and bool(
                HEX_SHA256.fullmatch(str(edge.get("content_sha256") or ""))
            )
            if edge.get("evidence_side") != "mapping_review":
                evidence_ok = evidence_ok and official_source_host(
                    edge.get("source_url")
                ) is not None
    add_check(
        checks,
        errors,
        "official_evidence_complete",
        evidence_ok,
        f"{label} contains incomplete or non-official evidence",
    )

    uncertainty_ok = all(
        bool((item.get("mapping_review") or {}).get("mapping_state"))
        and (item.get("frame") or {}).get("same_exact_frame_confirmed") is False
        and (item.get("confidence") or {}).get("aggregate_rule")
        == "minimum_required_component"
        and (item.get("confidence") or {}).get("aggregate_value") == 0.0
        and (item.get("coverage") or {}).get("exhaustive") is False
        and (item.get("counterevidence") or {}).get("exhaustive") is False
        and (item.get("freshness") or {}).get("ranking_eligible") is False
        for item in items
    )
    coverage = artifact.get("coverage") or {}
    freshness = artifact.get("freshness") or {}
    methodology = artifact.get("methodology") or {}
    scale_contract = artifact.get("scale_contract") or {}
    caveat_text = "\n".join(str(value) for value in artifact.get("caveats") or [])
    add_check(
        checks,
        errors,
        "truth_contract",
        uncertainty_ok
        and methodology.get("topic_overlap_is_proof") is False
        and coverage.get("ranking_state") == "hidden"
        and coverage.get("all_possible_actions_searched") is False
        and coverage.get("counterevidence_search_complete") is False
        and freshness.get("tier") == "stale"
        and freshness.get("ranking_eligible") is False
        and scale_contract.get("million_row_physical_run_proven") is False
        and "No hay comparaciones aligned o conflicted" in caveat_text
        and "Insufficient evidence no significa incumplimiento" in caveat_text
        and "no como posición colectiva completa del partido" in caveat_text,
        f"{label} uncertainty/non-causal truth contract mismatch",
    )

    bounded = bounded_items[0] if len(bounded_items) == 1 else {}
    bounded_search = bounded.get("action_search") or {}
    bounded_scope = bounded_search.get("scope") or {}
    add_check(
        checks,
        errors,
        "bounded_search_not_fabricated_action",
        len(bounded_items) == 1
        and bounded.get("comparison_status") == "insufficient_evidence"
        and bounded_search.get("state") == "no_reviewed_action_found"
        and bounded_scope.get("candidate_events_scanned") == 97
        and bounded_scope.get("candidate_vote_rows_scanned") == 97
        and bounded_scope.get("matching_event_ids") == []
        and bounded_scope.get("expected_matching_events") == 0,
        f"{label} bounded-search assessment contract mismatch",
    )

    folded = json.dumps(artifact, ensure_ascii=False, sort_keys=True).casefold()
    add_check(
        checks,
        errors,
        "no_fake_or_private_markers",
        not any(marker.casefold() in folded for marker in FAKE_MARKERS)
        and not any(marker.casefold() in folded for marker in PRIVATE_MARKERS),
        f"{label} contains fake-data or workstation/private markers",
    )

    probe_targets = select_probe_urls(items)
    add_check(
        checks,
        errors,
        "deterministic_probe_set",
        [host for host, _url in probe_targets] == list(PROBE_HOST_PRIORITY),
        f"{label} cannot derive the three deterministic official-source probes",
    )
    return checks, errors, probe_targets


def empty_fetch_record(url: str) -> dict[str, Any]:
    return {
        "url": url,
        "final_url": url,
        "http_status": "not_fetched",
        "content_type": "",
        "bytes": 0,
        "sha256": sha256_bytes(b""),
    }


def verify(
    *,
    base_url: str,
    expected_release: str,
    expected_semantic_sha256: str,
    expected_artifact_sha256: str,
    expected_artifact: Path,
    timeout: float,
    max_page_bytes: int,
    max_artifact_bytes: int,
    max_probe_bytes: int,
    fetcher: Fetcher = fetch_http,
) -> dict[str, Any]:
    base_url = base_url.rstrip("/")
    page_url = f"{base_url}/comparisons/"
    artifact_url = f"{base_url}/comparisons/data/comparisons.json"
    errors: list[str] = []
    checks: dict[str, bool] = {}
    page_record = empty_fetch_record(page_url)
    live_record = empty_fetch_record(artifact_url)
    official_probes: list[dict[str, Any]] = []

    try:
        expected_bytes = expected_artifact.read_bytes()
    except OSError as exc:
        expected_bytes = b""
        errors.append(
            "validated local comparison artifact unavailable: "
            f"{type(exc).__name__}: {expected_artifact.name}"
        )
    expected_sha256 = sha256_bytes(expected_bytes)
    add_check(
        checks,
        errors,
        "local_artifact_size_bounded",
        0 < len(expected_bytes) <= max_artifact_bytes,
        "validated local comparison artifact is missing, empty, or over budget",
    )
    add_check(
        checks,
        errors,
        "local_artifact_sha256_pinned",
        bool(HEX_SHA256.fullmatch(expected_artifact_sha256))
        and expected_sha256 == expected_artifact_sha256,
        "validated local comparison artifact SHA-256 differs from the pinned hash",
    )
    add_check(
        checks,
        errors,
        "expected_semantic_sha256_well_formed",
        bool(HEX_SHA256.fullmatch(expected_semantic_sha256)),
        "pinned semantic SHA-256 is malformed",
    )

    expected_artifact_value = parse_artifact(expected_bytes, "local", errors)
    try:
        local_contract, local_contract_errors, local_probe_targets = (
            validate_artifact_contract(
                expected_artifact_value,
                expected_release=expected_release,
                expected_semantic_sha256=expected_semantic_sha256,
                label="local",
            )
            if expected_artifact_value
            else ({}, [], [])
        )
    except Exception as exc:  # noqa: BLE001 - malformed baseline must yield a report
        local_contract = {"contract_shape_valid": False}
        local_contract_errors = [
            f"local artifact contract exception: {type(exc).__name__}: {exc}"
        ]
        local_probe_targets = []
    errors.extend(local_contract_errors)
    checks.update(
        {f"local_{key}": value for key, value in local_contract.items()}
    )

    # Never probe live state from an invalid or unpinned local baseline.
    local_ready = bool(expected_artifact_value) and all(checks.values()) and not errors
    if local_ready:
        try:
            page_bytes, page_status, page_type, page_final_url = fetcher(
                page_url, timeout, max_page_bytes, False
            )
            page_record = {
                "url": page_url,
                "final_url": page_final_url,
                "http_status": page_status,
                "content_type": page_type,
                "bytes": len(page_bytes),
                "sha256": sha256_bytes(page_bytes),
            }
        except Exception as exc:  # noqa: BLE001 - preserve exact live failure
            page_bytes = b""
            page_status = "error"
            page_type = ""
            page_final_url = page_url
            errors.append(
                f"live comparison page fetch failed: {type(exc).__name__}: {exc}"
            )

        try:
            live_bytes, live_status, live_type, live_final_url = fetcher(
                artifact_url, timeout, max_artifact_bytes, False
            )
            live_record = {
                "url": artifact_url,
                "final_url": live_final_url,
                "http_status": live_status,
                "content_type": live_type,
                "bytes": len(live_bytes),
                "sha256": sha256_bytes(live_bytes),
            }
        except Exception as exc:  # noqa: BLE001 - preserve exact live failure
            live_bytes = b""
            live_status = "error"
            live_type = ""
            live_final_url = artifact_url
            errors.append(
                f"live comparison artifact fetch failed: {type(exc).__name__}: {exc}"
            )

        page_text = page_bytes.decode("utf-8", errors="replace")
        found_markers = [marker for marker in PAGE_MARKERS if marker in page_text]
        add_check(
            checks,
            errors,
            "live_page_http_and_origin",
            page_status == 200
            and same_origin(page_url, page_final_url)
            and "html" in page_type.casefold(),
            "live comparison page HTTP/origin/content-type contract failed",
        )
        add_check(
            checks,
            errors,
            "live_page_markers",
            len(found_markers) == len(PAGE_MARKERS),
            "live comparison page is missing one or more truth-contract markers",
        )
        add_check(
            checks,
            errors,
            "live_artifact_http_and_origin",
            live_status == 200
            and same_origin(artifact_url, live_final_url)
            and "json" in live_type.casefold(),
            "live comparison artifact HTTP/origin/content-type contract failed",
        )
        add_check(
            checks,
            errors,
            "exact_local_live_artifact_bytes",
            bool(expected_bytes) and live_bytes == expected_bytes,
            "live comparison artifact bytes differ from the validated local artifact",
        )
        add_check(
            checks,
            errors,
            "live_artifact_sha256_pinned",
            sha256_bytes(live_bytes) == expected_artifact_sha256,
            "live comparison artifact SHA-256 differs from the pinned hash",
        )

        live_artifact_value = parse_artifact(live_bytes, "live", errors)
        try:
            live_contract, live_contract_errors, live_probe_targets = (
                validate_artifact_contract(
                    live_artifact_value,
                    expected_release=expected_release,
                    expected_semantic_sha256=expected_semantic_sha256,
                    label="live",
                )
                if live_artifact_value
                else ({}, [], [])
            )
        except Exception as exc:  # noqa: BLE001 - malformed live data must report
            live_contract = {"contract_shape_valid": False}
            live_contract_errors = [
                f"live artifact contract exception: {type(exc).__name__}: {exc}"
            ]
            live_probe_targets = []
        errors.extend(live_contract_errors)
        checks.update(
            {f"live_{key}": value for key, value in live_contract.items()}
        )
        add_check(
            checks,
            errors,
            "local_live_probe_selection_parity",
            live_probe_targets == local_probe_targets,
            "live official-source probe selection differs from local release",
        )

        for requested_host, source_url in live_probe_targets:
            try:
                data, status, content_type, final_url = fetcher(
                    source_url, timeout, max_probe_bytes, True
                )
                final_host = official_source_host(final_url)
                syntax_ok = bool(data)
                if requested_host == "www.bng.gal":
                    syntax_ok = data.startswith(b"%PDF-")
                elif requested_host == "www.senado.es":
                    syntax_ok = data.lstrip().startswith(b"<")
                elif requested_host == "www.congreso.es":
                    syntax_ok = data.lstrip().startswith((b"{", b"["))
                probe = {
                    "requested_url": source_url,
                    "requested_host": requested_host,
                    "final_url": final_url,
                    "final_host": final_host,
                    "http_status": status,
                    "content_type": content_type,
                    "prefix_bytes": len(data),
                    "prefix_sha256": sha256_bytes(data),
                    "syntax_ok": syntax_ok,
                }
                if (
                    status != 200
                    or not same_official_source_domain(requested_host, final_host)
                    or not syntax_ok
                ):
                    errors.append(
                        f"official source probe contract failed for {requested_host}"
                    )
            except Exception as exc:  # noqa: BLE001 - preserve exact upstream state
                probe = {
                    "requested_url": source_url,
                    "requested_host": requested_host,
                    "http_status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                errors.append(
                    f"official source probe {requested_host} failed: "
                    f"{type(exc).__name__}: {exc}"
                )
            official_probes.append(probe)
        add_check(
            checks,
            errors,
            "three_deterministic_official_sources_available",
            len(official_probes) == 3
            and [probe.get("requested_host") for probe in official_probes]
            == list(PROBE_HOST_PRIORITY)
            and all(
                probe.get("http_status") == 200
                and same_official_source_domain(
                    str(probe.get("requested_host") or ""),
                    str(probe.get("final_host") or "") or None,
                )
                and probe.get("syntax_ok") is True
                for probe in official_probes
            ),
            "three deterministic official-source probes did not pass",
        )

    return {
        "schema_version": "live_promise_action_comparison_verification_v1",
        "status": "verified_live_comparison_release" if not errors else "error",
        "passed": not errors and all(checks.values()),
        "verified_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "expected": {
            "release_id": expected_release,
            "semantic_sha256": expected_semantic_sha256,
            "artifact_filename": expected_artifact.name,
            "artifact_bytes": len(expected_bytes),
            "artifact_sha256": expected_sha256,
        },
        "page": page_record,
        "artifact": live_record,
        "official_source_probes": official_probes,
        "checks": dict(sorted(checks.items())),
        "failed_checks": sorted(key for key, value in checks.items() if not value),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://votaconlachola.org")
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--expected-semantic-sha256", required=True)
    parser.add_argument("--expected-artifact-sha256", required=True)
    parser.add_argument(
        "--expected-artifact", type=Path, default=DEFAULT_EXPECTED_ARTIFACT
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-page-bytes", type=int, default=2_500_000)
    parser.add_argument("--max-artifact-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--max-probe-bytes", type=int, default=256 * 1024)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify(
        base_url=args.base_url,
        expected_release=args.expected_release,
        expected_semantic_sha256=args.expected_semantic_sha256,
        expected_artifact_sha256=args.expected_artifact_sha256,
        expected_artifact=args.expected_artifact,
        timeout=args.timeout,
        max_page_bytes=args.max_page_bytes,
        max_artifact_bytes=args.max_artifact_bytes,
        max_probe_bytes=args.max_probe_bytes,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
