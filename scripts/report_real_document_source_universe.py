#!/usr/bin/env python3
"""Report the exact real official document URL universe and 100k readiness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = "real_document_source_universe_v1"
ANDALUCIA_CONTRACT_HOST = "www.parlamentodeandalucia.es"
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repository: {path}") from exc


def portable_path(path: Path) -> str:
    try:
        return repo_path(path)
    except ValueError:
        return f"<external>/{path.name}"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": repo_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def obstruction_classification_projection(payload: dict[str, Any]) -> dict[str, Any]:
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
    open_incidents.sort(
        key=lambda row: (row["incident_id"], row["endpoint_or_page"])
    )
    return {
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


def obstruction_projection_descriptor(
    path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    projection = obstruction_classification_projection(payload)
    body = json.dumps(
        projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "path": repo_path(path),
        "descriptor_kind": "canonical_json_projection",
        "projection_schema": projection["schema_version"],
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "open_incidents": len(projection["open_incidents"]),
    }


def read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    file_descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def validate_input_policies(
    *,
    provenance: dict[str, Any],
    health: dict[str, Any],
    acquisition: dict[str, Any],
    obstruction: dict[str, Any],
) -> None:
    provenance_policy = provenance.get("policy") or {}
    health_policy = health.get("policy") or {}
    acquisition_policy = acquisition.get("policy") or {}
    obstruction_policy = obstruction.get("policy") or {}
    if (
        provenance.get("schema_version") != "real_document_provenance_audit_v13"
        or provenance_policy.get("official_real_records_only") is not True
        or provenance_policy.get("synthetic_or_mock_records_counted") is not False
        or provenance_policy.get("public_domain_personal_information_retained")
        is not True
    ):
        raise ValueError("provenance audit real-data policy mismatch")
    if (
        health.get("schema_version") != "real_document_host_health_v1"
        or health_policy.get("official_real_documents_only") is not True
        or health_policy.get("synthetic_or_mock_records_counted") is not False
        or health_policy.get("official_public_domain_personal_information_retained")
        is not True
        or health_policy.get("known_blocked_hosts_reprobed") is not False
    ):
        raise ValueError("host health policy mismatch")
    if (
        acquisition.get("schema_version")
        != "real_document_fetch_scale_cohort_validation_v3"
        or acquisition.get("status") != "ok"
        or acquisition_policy.get("official_real_documents_only") is not True
        or acquisition_policy.get("synthetic_or_mock_records_counted") is not False
        or acquisition_policy.get(
            "official_public_domain_personal_information_retained"
        )
        is not True
        or int((acquisition.get("checks") or {}).get("host_failures") or 0) != 0
    ):
        raise ValueError("physical acquisition validation policy mismatch")
    if (
        obstruction_policy.get("data_origin") != "official_real_records_only"
        or obstruction_policy.get("synthetic_or_mock_records") != "forbidden"
        or obstruction_policy.get("public_domain_personal_information") != "retained"
    ):
        raise ValueError("obstruction snapshot policy mismatch")


def open_incident_hosts(obstruction: dict[str, Any]) -> dict[str, list[str]]:
    incidents: dict[str, set[str]] = defaultdict(set)
    for row in obstruction.get("incidents") or []:
        if not isinstance(row, dict) or row.get("status") != "OPEN":
            continue
        incident_id = str(row.get("incident_id") or "")
        for raw_url in URL_PATTERN.findall(str(row.get("endpoint_or_page") or "")):
            parsed = urlparse(raw_url.rstrip("),.;"))
            host = (parsed.hostname or "").lower()
            if host and incident_id:
                incidents[host].add(incident_id)
    return {host: sorted(values) for host, values in incidents.items()}


def stage_edge_universe(
    edge_path: Path, *, expected_rows: int
) -> tuple[sqlite3.Connection, Path, dict[str, int]]:
    file_descriptor, database_name = tempfile.mkstemp(
        prefix="real-document-source-universe-", suffix=".sqlite"
    )
    os.close(file_descriptor)
    database_path = Path(database_name)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute(
        """
        CREATE TABLE url_memberships (
          source_id TEXT NOT NULL,
          host TEXT NOT NULL,
          source_url TEXT NOT NULL,
          url_kind TEXT NOT NULL,
          PRIMARY KEY (source_id, source_url)
        ) WITHOUT ROWID
        """
    )
    edge_rows = 0
    public_https_edges = 0
    public_http_edges = 0
    batch: list[tuple[str, str, str, str]] = []
    try:
        with edge_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"edge row {line_number} is not an object")
                source_id = str(row.get("source_id") or "")
                source_url = str(row.get("source_url") or "")
                url_kind = str(row.get("url_kind") or "")
                parsed = urlparse(source_url)
                host = (parsed.hostname or "").lower()
                expected_kind = (
                    "public_https" if parsed.scheme == "https" else "public_http"
                )
                if (
                    not source_id
                    or not host
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.scheme not in {"http", "https"}
                    or url_kind != expected_kind
                ):
                    raise ValueError(f"invalid official URL edge at line {line_number}")
                edge_rows += 1
                public_https_edges += url_kind == "public_https"
                public_http_edges += url_kind == "public_http"
                batch.append((source_id, host, source_url, url_kind))
                if len(batch) >= 10_000:
                    connection.executemany(
                        "INSERT OR IGNORE INTO url_memberships VALUES (?, ?, ?, ?)",
                        batch,
                    )
                    batch.clear()
        if batch:
            connection.executemany(
                "INSERT OR IGNORE INTO url_memberships VALUES (?, ?, ?, ?)", batch
            )
        connection.commit()
        if edge_rows != expected_rows:
            raise ValueError(
                f"edge row count mismatch: expected={expected_rows} actual={edge_rows}"
            )
        return connection, database_path, {
            "edge_rows": edge_rows,
            "public_https_edges": public_https_edges,
            "public_http_edges": public_http_edges,
        }
    except BaseException:
        connection.close()
        database_path.unlink(missing_ok=True)
        raise


def classify_hosts(
    connection: sqlite3.Connection,
    *,
    health: dict[str, Any],
    acquisition: dict[str, Any],
    obstruction: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    probe_rows = {
        str(row.get("host") or ""): row for row in health.get("probes") or []
    }
    known_blocked = {
        str(value) for value in health.get("known_blocked_hosts_excluded_without_probe") or []
    }
    incident_hosts = open_incident_hosts(obstruction)
    physical_hosts = acquisition.get("hosts") or {}
    source_rows = connection.execute(
        """
        SELECT host, source_id, url_kind, COUNT(DISTINCT source_url)
        FROM url_memberships
        GROUP BY host, source_id, url_kind
        ORDER BY host, source_id, url_kind
        """
    ).fetchall()
    sources_by_host: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for host, source_id, url_kind, count in source_rows:
        sources_by_host[str(host)].append(
            {
                "source_id": str(source_id),
                "url_kind": str(url_kind),
                "unique_urls": int(count),
            }
        )
    host_rows = connection.execute(
        """
        SELECT
          host,
          COUNT(DISTINCT source_url),
          COUNT(DISTINCT CASE WHEN url_kind = 'public_https' THEN source_url END),
          COUNT(DISTINCT CASE WHEN url_kind = 'public_http' THEN source_url END)
        FROM url_memberships
        GROUP BY host
        ORDER BY 3 DESC, host
        """
    ).fetchall()
    result: list[dict[str, Any]] = []
    category_https_urls: dict[str, int] = defaultdict(int)
    for host, unique_urls, https_urls, http_urls in host_rows:
        host = str(host)
        eligible_https_urls = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT source_url)
                FROM url_memberships
                WHERE host = ?
                  AND url_kind = 'public_https'
                  AND (
                    source_id IN ('boe_daily_summaries', 'boe_document_xml')
                    OR host = ?
                  )
                """,
                (host, ANDALUCIA_CONTRACT_HOST),
            ).fetchone()[0]
        )
        probe = probe_rows.get(host) or {}
        physical = physical_hosts.get(host) or {}
        if eligible_https_urls:
            if (
                int(physical.get("network_successes") or 0)
                != int(physical.get("rows") or 0)
                or int(physical.get("rows") or 0) <= 0
            ):
                raise ValueError(f"eligible host lacks clean physical proof: {host}")
            category = (
                "contract_implemented_and_physically_healthy"
                if eligible_https_urls == int(https_urls)
                else "partially_contract_implemented_and_physically_healthy"
            )
        elif host in known_blocked:
            category = "known_blocked_no_new_lever"
        elif host in incident_hosts:
            category = "open_access_incident"
        elif probe.get("exclusion_reason") == "source_specific_semantic_contract_not_implemented":
            category = "reachable_semantic_contract_missing"
        elif probe.get("failure_class") == "tls_certificate_chain":
            category = "strict_tls_failed"
        else:
            category = "not_assessed_for_bulk_acquisition"
        category_https_urls[category] += int(https_urls)
        result.append(
            {
                "host": host,
                "unique_public_urls": int(unique_urls),
                "unique_https_urls": int(https_urls),
                "unique_http_urls": int(http_urls),
                "contract_eligible_https_urls": eligible_https_urls,
                "classification": category,
                "physical_success_rows": int(physical.get("network_successes") or 0),
                "probe_http_status": probe.get("http_status"),
                "probe_exclusion_reason": probe.get("exclusion_reason"),
                "open_incident_ids": incident_hosts.get(host, []),
                "sources": sources_by_host[host],
            }
        )
    return result, dict(sorted(category_https_urls.items()))


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    provenance_path = Path(args.provenance_audit)
    health_path = Path(args.host_health)
    acquisition_path = Path(args.acquisition_validation)
    obstruction_path = Path(args.obstruction_snapshot)
    provenance = read_object(provenance_path)
    health = read_object(health_path)
    acquisition = read_object(acquisition_path)
    obstruction = read_object(obstruction_path)
    validate_input_policies(
        provenance=provenance,
        health=health,
        acquisition=acquisition,
        obstruction=obstruction,
    )
    edge_descriptor = provenance.get("edge_manifest") or {}
    edge_path = Path(str(edge_descriptor.get("path") or ""))
    if (
        not edge_path.is_file()
        or repo_path(edge_path) != edge_descriptor.get("path")
        or edge_path.stat().st_size != int(edge_descriptor.get("bytes") or -1)
        or sha256_path(edge_path) != edge_descriptor.get("sha256")
    ):
        raise ValueError("provenance edge manifest descriptor mismatch")
    expected_rows = int(edge_descriptor.get("rows") or 0)
    connection, database_path, edge_counts = stage_edge_universe(
        edge_path, expected_rows=expected_rows
    )
    try:
        hosts, categories = classify_hosts(
            connection,
            health=health,
            acquisition=acquisition,
            obstruction=obstruction,
        )
        summary_row = connection.execute(
            """
            SELECT
              COUNT(DISTINCT source_url),
              COUNT(DISTINCT CASE WHEN url_kind = 'public_https' THEN source_url END),
              COUNT(DISTINCT CASE WHEN url_kind = 'public_http' THEN source_url END),
              COUNT(DISTINCT source_id),
              COUNT(DISTINCT host)
            FROM url_memberships
            """
        ).fetchone()
        executable_urls = sum(row["contract_eligible_https_urls"] for row in hosts)
        healthy_host_uncontracted_urls = sum(
            row["unique_https_urls"] - row["contract_eligible_https_urls"]
            for row in hosts
            if row["contract_eligible_https_urls"]
        )
    finally:
        connection.close()
        database_path.unlink(missing_ok=True)
    target = int(args.target_urls)
    if target <= 0:
        raise ValueError("target URLs must be positive")
    gap = max(0, target - executable_urls)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "ready_for_numeric_cohort_preparation"
            if executable_urls >= target
            else "blocked_below_numeric_target"
        ),
        "generated_at": utc_now(),
        "policy": {
            "official_real_urls_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "network_requests_performed": 0,
            "known_blocked_hosts_reprobed": False,
            "representativeness_inferred": False,
        },
        "inputs": {
            "provenance_audit": descriptor(provenance_path),
            "edge_manifest": descriptor(edge_path),
            "host_health": descriptor(health_path),
            "acquisition_validation": descriptor(acquisition_path),
            "obstruction_snapshot": obstruction_projection_descriptor(
                obstruction_path, obstruction
            ),
        },
        "edge_counts": edge_counts,
        "summary": {
            "unique_public_urls": int(summary_row[0]),
            "unique_https_urls": int(summary_row[1]),
            "unique_http_urls": int(summary_row[2]),
            "source_ids": int(summary_row[3]),
            "hosts": int(summary_row[4]),
            "contract_eligible_physically_healthy_https_urls": executable_urls,
            "healthy_host_uncontracted_https_urls": healthy_host_uncontracted_urls,
            "numeric_target_urls": target,
            "numeric_target_gap_urls": gap,
            "numeric_target_available": executable_urls >= target,
            "representative_cohort_status": "decision_required_dec_01",
        },
        "category_https_urls": categories,
        "hosts": hosts,
        "checks": {
            "provenance_edge_descriptor_exact": True,
            "all_edge_rows_accounted": (
                edge_counts["public_https_edges"] + edge_counts["public_http_edges"]
                == edge_counts["edge_rows"]
            ),
            "https_categories_reconcile": sum(categories.values())
            == int(summary_row[1]),
            "physical_health_required_for_contract_eligible_hosts": True,
            "known_blocked_hosts_not_probed": True,
            "real_data_policy_enforced": True,
        },
        "limitations": [
            "URL totals are the exact current local provenance universe, not a claim of complete official publication totals.",
            "Accessibility classifications reuse bound physical evidence; this report performs no network request.",
            "A numeric 100k URL supply would not by itself prove representative source, format, language, time, or jurisdiction coverage.",
            "HTTP-only URLs remain evidence but cannot enter the strict HTTPS acquisition cohort.",
        ],
        "next_action": {
            "minimum_additional_contract_eligible_https_urls": gap,
            "reachable_moncloa_urls_after_contract": categories.get(
                "reachable_semantic_contract_missing", 0
            ),
            "instruction": (
                "Implement and validate the Moncloa semantic contract, then expand "
                "healthy official HTTPS sources or use a genuinely new lever on an "
                "existing blocked source. Do not repeat blocker probes without a new lever."
            ),
        },
        "performance": {
            "staging": "disk_backed_sqlite",
            "edge_batch_rows": 10_000,
            "wall_seconds": round(time.perf_counter() - started_wall, 6),
            "cpu_seconds": round(time.process_time() - started_cpu, 6),
            "peak_rss_bytes": peak_rss_bytes(),
        },
        "errors": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance-audit", required=True)
    parser.add_argument("--host-health", required=True)
    parser.add_argument("--acquisition-validation", required=True)
    parser.add_argument("--obstruction-snapshot", required=True)
    parser.add_argument("--target-urls", type=int, default=100_000)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    write_json_atomic(Path(args.out), report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "executable_https_urls": report["summary"][
                    "contract_eligible_physically_healthy_https_urls"
                ],
                "target_gap_urls": report["summary"]["numeric_target_gap_urls"],
                "out": portable_path(Path(args.out)),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
