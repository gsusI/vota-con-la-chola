#!/usr/bin/env python3
"""Verify the live actor graph page, exact artifact, and official sources."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


EXPECTED_NODES = 133_595
EXPECTED_RELATIONSHIPS = 237_973
EXPECTED_SOURCE_SCOPED_DECISIONS = 133_595
EXPECTED_SOURCE_SCOPES = 30
EXPECTED_SOURCE_MAPPINGS = 55
EXPECTED_CONFLICTING_SOURCE_IDS = 3
EXPECTED_NAMESPACED_SOURCE_ROWS = 7
EXPECTED_SAMPLE_NODES = 32
EXPECTED_SAMPLE_RELATIONSHIPS = 34

# Every host currently represented by the bounded actor-graph sample is an
# official institution, public procurement/election publisher, or political
# party publisher. Subdomains are accepted; lookalike suffixes are not.
OFFICIAL_SOURCE_DOMAIN_SUFFIXES = (
    "asambleamadrid.es",
    "asambleaex.es",
    "bng.gal",
    "boe.es",
    "ceuta.es",
    "congreso.es",
    "contrataciondelestado.es",
    "interior.gob.es",
    "lamoncloa.gob.es",
)

# Prefer origins already used by dedicated live verifiers. Remaining official
# hosts are selected in lexical order, making selection deterministic.
PROBE_HOST_PRIORITY = (
    "www.boe.es",
    "www.lamoncloa.gob.es",
    "descargas.interior.gob.es",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://votaconlachola.org")
    parser.add_argument("--expected-release", required=True)
    parser.add_argument(
        "--expected-artifact",
        type=Path,
        default=Path("ui/site/public/actor-graph/data/graph.json"),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path(
            "docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/"
            "live-actor-graph-verification.json"
        ),
    )
    return parser.parse_args()


def fetch(
    url: str, timeout: float, max_bytes: int | None = None
) -> tuple[bytes, int, str, str]:
    request = Request(
        url,
        headers={"User-Agent": "vota-con-la-chola-actor-graph-verifier/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        data = response.read() if max_bytes is None else response.read(max_bytes)
        return (
            data,
            int(response.status),
            response.headers.get("Content-Type", ""),
            response.geturl(),
        )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def select_probe_urls(rows: list[dict[str, object]]) -> list[tuple[str, str]]:
    urls_by_host: dict[str, set[str]] = {}
    for row in rows:
        url = str(row.get("source_url") or "").strip()
        host = official_source_host(url)
        if host:
            urls_by_host.setdefault(host, set()).add(url)

    ordered_hosts = [host for host in PROBE_HOST_PRIORITY if host in urls_by_host]
    ordered_hosts.extend(
        sorted(host for host in urls_by_host if host not in ordered_hosts)
    )
    return [
        (host, sorted(urls_by_host[host])[0])
        for host in ordered_hosts[:3]
    ]


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    page_url = f"{base_url}/actor-graph/"
    artifact_url = f"{base_url}/actor-graph/data/graph.json"
    errors: list[str] = []

    try:
        expected_bytes = args.expected_artifact.read_bytes()
    except OSError as exc:
        expected_bytes = b""
        errors.append(
            "validated local actor graph unavailable: "
            f"{type(exc).__name__} ({args.expected_artifact.name})"
        )

    try:
        page_bytes, page_status, page_type, page_final_url = fetch(
            page_url, args.timeout
        )
    except Exception as exc:  # noqa: BLE001 - preserve exact live failure
        page_bytes = b""
        page_status = "error"
        page_type = ""
        page_final_url = page_url
        errors.append(f"live actor graph page fetch failed: {type(exc).__name__}: {exc}")

    try:
        artifact_bytes, artifact_status, artifact_type, artifact_final_url = fetch(
            artifact_url, args.timeout
        )
    except Exception as exc:  # noqa: BLE001 - preserve exact live failure
        artifact_bytes = b""
        artifact_status = "error"
        artifact_type = ""
        artifact_final_url = artifact_url
        errors.append(
            f"live actor graph artifact fetch failed: {type(exc).__name__}: {exc}"
        )

    if page_status != 200:
        errors.append(f"actor graph page HTTP status {page_status}")
    if artifact_status != 200:
        errors.append(f"actor graph artifact HTTP status {artifact_status}")
    exact_artifact_parity = bool(expected_bytes) and artifact_bytes == expected_bytes
    if not exact_artifact_parity:
        errors.append("live artifact bytes differ from the validated local artifact")

    page_text = page_bytes.decode("utf-8", errors="replace")
    page_markers = (
        "Quién aparece conectado con qué",
        "Mismo nombre no significa misma persona",
        "Una ruta del grafo no prueba corrupción",
    )
    found_page_markers = [marker for marker in page_markers if marker in page_text]
    for marker in page_markers:
        if marker not in page_text:
            errors.append(f"actor graph page marker missing: {marker}")

    try:
        artifact = json.loads(artifact_bytes)
        if not isinstance(artifact, dict):
            raise ValueError("top-level JSON value is not an object")
    except (UnicodeError, ValueError) as exc:
        artifact = {}
        errors.append(f"live actor graph artifact is invalid JSON: {exc}")

    def object_field(container: dict, key: str) -> dict:
        value = container.get(key)
        if isinstance(value, dict):
            return value
        errors.append(f"live actor graph field {key} is not an object")
        return {}

    def row_list_field(container: dict, key: str) -> list[dict[str, object]]:
        value = container.get(key)
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            errors.append(f"live actor graph field {key} is not a list of objects")
            return []
        return value

    meta = object_field(artifact, "meta")
    policy = object_field(artifact, "policy")
    coverage = object_field(artifact, "coverage")
    database_counts = object_field(coverage, "database_counts")
    resolution_outcomes = object_field(coverage, "resolution_outcomes")
    source_mapping = object_field(coverage, "source_mapping")
    sample_contract = object_field(artifact, "sample_contract")
    sample_nodes = row_list_field(artifact, "sample_nodes")
    sample_relationships = row_list_field(artifact, "sample_relationships")

    if meta.get("release_id") != args.expected_release:
        errors.append("live actor graph release_id does not match expected release")
    if meta.get("schema_version") != "actor_graph_public_v1":
        errors.append("live actor graph schema_version mismatch")
    if meta.get("contract_version") != "actor_graph_v1":
        errors.append("live actor graph contract_version mismatch")
    if meta.get("real_data_only") is not True:
        errors.append("live actor graph real_data_only is not true")
    if meta.get("synthetic_or_mock") is not False:
        errors.append("live actor graph synthetic_or_mock is not false")
    if meta.get("official_public_domain_information_retained") is not True:
        errors.append("live official public-domain information retention mismatch")
    if policy.get("public_identity_redaction") != (
        "forbidden_for_official_public_fields"
    ):
        errors.append("live official public identity retention policy mismatch")
    if policy.get("default_identity_scope") != "source_scoped":
        errors.append("live default identity scope is not source_scoped")
    if policy.get("name_only_cross_source_merge") != "forbidden":
        errors.append("live name-only cross-source merge policy is not forbidden")
    if policy.get("causal_inference_from_graph_path") != "forbidden":
        errors.append("live causal inference from graph path is not forbidden")

    expected_counts = {
        "actor_graph_nodes": EXPECTED_NODES,
        "actor_graph_node_versions": EXPECTED_NODES,
        "actor_graph_relationships": EXPECTED_RELATIONSHIPS,
        "actor_graph_relationship_versions": EXPECTED_RELATIONSHIPS,
        "actor_graph_relationship_evidence": EXPECTED_RELATIONSHIPS,
        "actor_resolution_decisions": EXPECTED_SOURCE_SCOPED_DECISIONS,
        "actor_resolution_evidence": EXPECTED_SOURCE_SCOPED_DECISIONS,
    }
    for key, expected in expected_counts.items():
        actual = database_counts.get(key)
        if actual != expected:
            errors.append(f"live {key} count mismatch: expected {expected}, found {actual}")
    if resolution_outcomes.get("source_scoped") != EXPECTED_SOURCE_SCOPED_DECISIONS:
        errors.append("live source-scoped resolution outcome count mismatch")
    if coverage.get("source_scopes") != EXPECTED_SOURCE_SCOPES:
        errors.append("live source scope count mismatch")
    if coverage.get("cross_source_resolved_actors") != 0:
        errors.append("live graph publishes cross-source resolved actors")
    if policy.get("cross_source_merges_published") != 0:
        errors.append("live graph publishes cross-source merges")
    if policy.get("operational_append_only_history") != "not_yet_proven":
        errors.append("live graph overstates operational append-only history")
    if database_counts.get("actor_graph_source_mappings") != EXPECTED_SOURCE_MAPPINGS:
        errors.append("live actor graph source-mapping row count mismatch")
    if source_mapping.get("mapping_rows") != EXPECTED_SOURCE_MAPPINGS:
        errors.append("live actor graph source-mapping summary mismatch")
    if source_mapping.get("conflicting_upstream_source_ids") != (
        EXPECTED_CONFLICTING_SOURCE_IDS
    ):
        errors.append("live actor graph source-conflict count mismatch")
    if source_mapping.get("namespaced_mapping_rows") != (
        EXPECTED_NAMESPACED_SOURCE_ROWS
    ):
        errors.append("live actor graph namespaced-source row count mismatch")

    if sample_contract.get("bounded") is not True:
        errors.append("live actor graph sample is not marked bounded")
    if sample_contract.get("all_rows_materialized_in_sqlite") is not True:
        errors.append("live actor graph omits full materialization contract")
    if sample_contract.get("full_graph_not_embedded_in_browser") is not True:
        errors.append("live actor graph does not enforce bounded browser payload")
    if len(sample_nodes) != EXPECTED_SAMPLE_NODES:
        errors.append(
            "live actor sample count mismatch: "
            f"expected {EXPECTED_SAMPLE_NODES}, found {len(sample_nodes)}"
        )
    if len(sample_relationships) != EXPECTED_SAMPLE_RELATIONSHIPS:
        errors.append(
            "live relationship sample count mismatch: "
            f"expected {EXPECTED_SAMPLE_RELATIONSHIPS}, "
            f"found {len(sample_relationships)}"
        )

    valid_node_labels = 0
    valid_relationship_labels = 0
    valid_official_source_urls = 0
    sample_rows: list[dict[str, object]] = []
    for index, node in enumerate(sample_nodes):
        sample_rows.append(node)
        label = str(node.get("canonical_label") or "").strip()
        if label:
            valid_node_labels += 1
        else:
            errors.append(f"sample node {index} has no canonical label")
        if node.get("identity_scope") != "source_scoped":
            errors.append(f"sample node {index} is not source_scoped")
        if not str(node.get("actor_id") or "").strip():
            errors.append(f"sample node {index} has no actor_id")
        if official_source_host(node.get("source_url")):
            valid_official_source_urls += 1
        else:
            errors.append(f"sample node {index} has a non-official source URL")

    for index, relationship in enumerate(sample_relationships):
        sample_rows.append(relationship)
        subject_label = str(relationship.get("subject_label") or "").strip()
        target_label = str(
            relationship.get("object_label")
            or relationship.get("context_kind")
            or ""
        ).strip()
        role_label = str(relationship.get("role_label") or "").strip()
        if subject_label and target_label and role_label:
            valid_relationship_labels += 1
        else:
            errors.append(f"sample relationship {index} has an empty display label")
        if relationship.get("resolution_state") != "source_scoped":
            errors.append(f"sample relationship {index} is not source_scoped")
        if not str(relationship.get("relationship_id") or "").strip():
            errors.append(f"sample relationship {index} has no relationship_id")
        if official_source_host(relationship.get("source_url")):
            valid_official_source_urls += 1
        else:
            errors.append(
                f"sample relationship {index} has a non-official source URL"
            )

    probe_targets = select_probe_urls(sample_rows)
    probe_hosts = [host for host, _url in probe_targets]
    if len(probe_targets) != 3 or len(set(probe_hosts)) != 3:
        errors.append("could not select three official sources on distinct hosts")

    official_source_probes: list[dict[str, object]] = []
    for host, source_url in probe_targets:
        try:
            data, status, content_type, final_url = fetch(
                source_url, args.timeout, 256 * 1024
            )
            outcome = {
                "requested_url": source_url,
                "requested_host": host,
                "final_url": final_url,
                "final_host": (urlparse(final_url).hostname or "").casefold(),
                "http_status": status,
                "content_type": content_type,
                "prefix_bytes": len(data),
                "prefix_sha256": sha256_bytes(data),
            }
            if status != 200:
                errors.append(f"official source probe {host} returned HTTP {status}")
            if not data:
                errors.append(f"official source probe {host} returned an empty body")
        except Exception as exc:  # noqa: BLE001 - preserve exact upstream state
            outcome = {
                "requested_url": source_url,
                "requested_host": host,
                "http_status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
            errors.append(
                f"official source probe {host} failed: {type(exc).__name__}: {exc}"
            )
        official_source_probes.append(outcome)

    report = {
        "schema_version": "live_actor_graph_verification_v1",
        "status": "ok" if not errors else "error",
        "verified_at": datetime.now(UTC).isoformat(),
        "expected_release": args.expected_release,
        "live_release": meta.get("release_id"),
        "page": {
            "url": page_url,
            "final_url": page_final_url,
            "http_status": page_status,
            "content_type": page_type,
            "bytes": len(page_bytes),
            "sha256": sha256_bytes(page_bytes),
        },
        "expected_artifact": {
            "filename": args.expected_artifact.name,
            "bytes": len(expected_bytes),
            "sha256": sha256_bytes(expected_bytes),
        },
        "artifact": {
            "url": artifact_url,
            "final_url": artifact_final_url,
            "http_status": artifact_status,
            "content_type": artifact_type,
            "bytes": len(artifact_bytes),
            "sha256": sha256_bytes(artifact_bytes),
            "nodes": database_counts.get("actor_graph_nodes"),
            "relationships": database_counts.get("actor_graph_relationships"),
            "source_scoped_decisions": database_counts.get(
                "actor_resolution_decisions"
            ),
            "source_scopes": coverage.get("source_scopes"),
            "source_mappings": source_mapping.get("mapping_rows"),
            "conflicting_source_ids": source_mapping.get(
                "conflicting_upstream_source_ids"
            ),
            "namespaced_source_rows": source_mapping.get(
                "namespaced_mapping_rows"
            ),
            "cross_source_merges": policy.get("cross_source_merges_published"),
            "sample_nodes": len(sample_nodes),
            "sample_relationships": len(sample_relationships),
        },
        "official_source_probes": official_source_probes,
        "checks": {
            "page_markers_found": len(found_page_markers),
            "exact_artifact_parity": exact_artifact_parity,
            "real_data_only": meta.get("real_data_only") is True,
            "synthetic_or_mock_false": meta.get("synthetic_or_mock") is False,
            "official_public_domain_information_retained": meta.get(
                "official_public_domain_information_retained"
            )
            is True,
            "source_scoped_default": policy.get("default_identity_scope")
            == "source_scoped",
            "name_only_cross_source_merge_forbidden": policy.get(
                "name_only_cross_source_merge"
            )
            == "forbidden",
            "causal_path_inference_forbidden": policy.get(
                "causal_inference_from_graph_path"
            )
            == "forbidden",
            "exact_node_count": database_counts.get("actor_graph_nodes")
            == EXPECTED_NODES,
            "exact_relationship_count": database_counts.get(
                "actor_graph_relationships"
            )
            == EXPECTED_RELATIONSHIPS,
            "exact_source_scoped_decisions": database_counts.get(
                "actor_resolution_decisions"
            )
            == EXPECTED_SOURCE_SCOPED_DECISIONS,
            "exact_source_scopes": coverage.get("source_scopes")
            == EXPECTED_SOURCE_SCOPES,
            "exact_source_mapping_contract": source_mapping.get("mapping_rows")
            == EXPECTED_SOURCE_MAPPINGS
            and database_counts.get("actor_graph_source_mappings")
            == EXPECTED_SOURCE_MAPPINGS
            and source_mapping.get("conflicting_upstream_source_ids")
            == EXPECTED_CONFLICTING_SOURCE_IDS
            and source_mapping.get("namespaced_mapping_rows")
            == EXPECTED_NAMESPACED_SOURCE_ROWS,
            "append_only_history_not_overstated": policy.get(
                "operational_append_only_history"
            )
            == "not_yet_proven",
            "zero_cross_source_merges": coverage.get(
                "cross_source_resolved_actors"
            )
            == 0
            and policy.get("cross_source_merges_published") == 0,
            "sample_node_labels": valid_node_labels == EXPECTED_SAMPLE_NODES,
            "sample_relationship_labels": valid_relationship_labels
            == EXPECTED_SAMPLE_RELATIONSHIPS,
            "sample_official_source_urls": valid_official_source_urls
            == EXPECTED_SAMPLE_NODES + EXPECTED_SAMPLE_RELATIONSHIPS,
            "three_distinct_official_source_probes": len(probe_targets) == 3
            and len(set(probe_hosts)) == 3,
            "three_available_nonempty_official_sources": len(
                official_source_probes
            )
            == 3
            and all(
                probe.get("http_status") == 200
                and int(probe.get("prefix_bytes") or 0) > 0
                for probe in official_source_probes
            ),
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
