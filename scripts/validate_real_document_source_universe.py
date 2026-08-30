#!/usr/bin/env python3
"""Independently validate the real document source-universe report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPORT_SCHEMA = "real_document_source_universe_v1"
VALIDATION_SCHEMA = "real_document_source_universe_validation_v1"
ANDALUCIA_HOST = "www.parlamentodeandalucia.es"


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
        "path": portable_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def obstruction_projection_descriptor(
    path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
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
    projection = {
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
    body = json.dumps(
        projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "path": repo_path(path),
        "descriptor_kind": "canonical_json_projection",
        "projection_schema": projection["schema_version"],
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "open_incidents": len(open_incidents),
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


def assert_descriptor(path: Path, observed: dict[str, Any], label: str) -> None:
    if observed != descriptor(path):
        raise ValueError(f"{label} descriptor mismatch")


def independent_counts(edge_path: Path) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    file_descriptor, database_name = tempfile.mkstemp(
        prefix="real-document-source-universe-validation-", suffix=".sqlite"
    )
    os.close(file_descriptor)
    database_path = Path(database_name)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute(
            """
            CREATE TABLE urls (
              source_id TEXT NOT NULL,
              host TEXT NOT NULL,
              source_url TEXT NOT NULL,
              url_kind TEXT NOT NULL,
              PRIMARY KEY (source_id, source_url)
            ) WITHOUT ROWID
            """
        )
        edge_rows = 0
        kind_edges: dict[str, int] = defaultdict(int)
        batch: list[tuple[str, str, str, str]] = []
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
                kind_edges[url_kind] += 1
                batch.append((source_id, host, source_url, url_kind))
                if len(batch) >= 8192:
                    connection.executemany(
                        "INSERT OR IGNORE INTO urls VALUES (?, ?, ?, ?)", batch
                    )
                    batch.clear()
        if batch:
            connection.executemany(
                "INSERT OR IGNORE INTO urls VALUES (?, ?, ?, ?)", batch
            )
        connection.commit()
        totals_row = connection.execute(
            """
            SELECT
              COUNT(DISTINCT source_url),
              COUNT(DISTINCT CASE WHEN url_kind = 'public_https' THEN source_url END),
              COUNT(DISTINCT CASE WHEN url_kind = 'public_http' THEN source_url END),
              COUNT(DISTINCT source_id),
              COUNT(DISTINCT host)
            FROM urls
            """
        ).fetchone()
        hosts: dict[str, dict[str, int]] = {}
        for host, unique_urls, https_urls, http_urls in connection.execute(
            """
            SELECT
              host,
              COUNT(DISTINCT source_url),
              COUNT(DISTINCT CASE WHEN url_kind = 'public_https' THEN source_url END),
              COUNT(DISTINCT CASE WHEN url_kind = 'public_http' THEN source_url END)
            FROM urls
            GROUP BY host
            """
        ):
            eligible = connection.execute(
                """
                SELECT COUNT(DISTINCT source_url)
                FROM urls
                WHERE host = ?
                  AND url_kind = 'public_https'
                  AND (
                    source_id IN ('boe_daily_summaries', 'boe_document_xml')
                    OR host = ?
                  )
                """,
                (host, ANDALUCIA_HOST),
            ).fetchone()[0]
            hosts[str(host)] = {
                "unique_public_urls": int(unique_urls),
                "unique_https_urls": int(https_urls),
                "unique_http_urls": int(http_urls),
                "contract_eligible_https_urls": int(eligible),
            }
        totals = {
            "edge_rows": edge_rows,
            "public_https_edges": int(kind_edges["public_https"]),
            "public_http_edges": int(kind_edges["public_http"]),
            "unique_public_urls": int(totals_row[0]),
            "unique_https_urls": int(totals_row[1]),
            "unique_http_urls": int(totals_row[2]),
            "source_ids": int(totals_row[3]),
            "hosts": int(totals_row[4]),
            "contract_eligible_physically_healthy_https_urls": sum(
                row["contract_eligible_https_urls"] for row in hosts.values()
            ),
            "healthy_host_uncontracted_https_urls": sum(
                row["unique_https_urls"] - row["contract_eligible_https_urls"]
                for row in hosts.values()
                if row["contract_eligible_https_urls"]
            ),
        }
        return totals, hosts
    finally:
        connection.close()
        database_path.unlink(missing_ok=True)


def validate(args: argparse.Namespace) -> dict[str, Any]:
    report_path = Path(args.report)
    report = read_object(report_path)
    if report.get("schema_version") != REPORT_SCHEMA:
        raise ValueError("source universe schema mismatch")
    if report.get("status") not in {
        "blocked_below_numeric_target",
        "ready_for_numeric_cohort_preparation",
    }:
        raise ValueError("source universe status mismatch")
    policy = report.get("policy") or {}
    if (
        policy.get("official_real_urls_only") is not True
        or policy.get("synthetic_or_mock_records_counted") is not False
        or policy.get("official_public_domain_personal_information_retained")
        is not True
        or policy.get("network_requests_performed") != 0
        or policy.get("known_blocked_hosts_reprobed") is not False
        or policy.get("representativeness_inferred") is not False
    ):
        raise ValueError("source universe policy mismatch")
    input_paths = {
        "provenance_audit": Path(args.provenance_audit),
        "host_health": Path(args.host_health),
        "acquisition_validation": Path(args.acquisition_validation),
        "obstruction_snapshot": Path(args.obstruction_snapshot),
    }
    report_inputs = report.get("inputs") or {}
    for key, path in input_paths.items():
        if key == "obstruction_snapshot":
            continue
        assert_descriptor(path, report_inputs.get(key) or {}, key)
    obstruction = read_object(input_paths["obstruction_snapshot"])
    if report_inputs.get("obstruction_snapshot") != obstruction_projection_descriptor(
        input_paths["obstruction_snapshot"], obstruction
    ):
        raise ValueError("obstruction classification projection mismatch")
    provenance = read_object(input_paths["provenance_audit"])
    edge_descriptor = provenance.get("edge_manifest") or {}
    edge_path = Path(str(edge_descriptor.get("path") or ""))
    assert_descriptor(edge_path, report_inputs.get("edge_manifest") or {}, "edge manifest")
    if (
        int(edge_descriptor.get("rows") or 0) <= 0
        or edge_descriptor.get("sha256") != sha256_path(edge_path)
        or int(edge_descriptor.get("bytes") or 0) != edge_path.stat().st_size
    ):
        raise ValueError("provenance edge descriptor drift")
    totals, direct_hosts = independent_counts(edge_path)
    if totals["edge_rows"] != int(edge_descriptor["rows"]):
        raise ValueError("edge row count drift")
    reported_edge_counts = report.get("edge_counts") or {}
    for key in ("edge_rows", "public_https_edges", "public_http_edges"):
        if int(reported_edge_counts.get(key) or -1) != totals[key]:
            raise ValueError(f"reported {key} drift")
    summary = report.get("summary") or {}
    for key in (
        "unique_public_urls",
        "unique_https_urls",
        "unique_http_urls",
        "source_ids",
        "hosts",
        "contract_eligible_physically_healthy_https_urls",
        "healthy_host_uncontracted_https_urls",
    ):
        if int(summary.get(key) or -1) != totals[key]:
            raise ValueError(f"reported {key} drift")
    target = int(summary.get("numeric_target_urls") or 0)
    executable = totals["contract_eligible_physically_healthy_https_urls"]
    expected_gap = max(0, target - executable)
    if (
        target <= 0
        or int(summary.get("numeric_target_gap_urls", -1)) != expected_gap
        or summary.get("numeric_target_available") != (executable >= target)
        or summary.get("representative_cohort_status") != "decision_required_dec_01"
    ):
        raise ValueError("numeric target or representative decision gate drift")
    acquisition = read_object(input_paths["acquisition_validation"])
    physical_hosts = acquisition.get("hosts") or {}
    reported_hosts = {
        str(row.get("host") or ""): row for row in report.get("hosts") or []
    }
    if set(reported_hosts) != set(direct_hosts):
        raise ValueError("reported host universe drift")
    for host, expected in direct_hosts.items():
        observed = reported_hosts[host]
        for key, value in expected.items():
            if int(observed.get(key) or 0) != value:
                raise ValueError(f"host count drift: {host} {key}")
        if expected["contract_eligible_https_urls"]:
            physical = physical_hosts.get(host) or {}
            if (
                int(physical.get("rows") or 0) <= 0
                or int(physical.get("network_successes") or 0)
                != int(physical.get("rows") or 0)
                or observed.get("classification")
                != (
                    "contract_implemented_and_physically_healthy"
                    if expected["contract_eligible_https_urls"]
                    == expected["unique_https_urls"]
                    else "partially_contract_implemented_and_physically_healthy"
                )
            ):
                raise ValueError(f"host physical health drift: {host}")
    categories = report.get("category_https_urls") or {}
    if sum(int(value) for value in categories.values()) != totals["unique_https_urls"]:
        raise ValueError("HTTPS categories do not reconcile")
    return {
        "schema_version": VALIDATION_SCHEMA,
        "status": "ok",
        "generated_at": utc_now(),
        "policy": {
            "official_real_urls_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "network_requests_performed": 0,
        },
        "inputs": {
            "report": descriptor(report_path),
            "edge_manifest": descriptor(edge_path),
        },
        "checks": {
            "input_descriptors_exact": True,
            "edge_rows_replayed": totals["edge_rows"],
            "unique_https_urls_replayed": totals["unique_https_urls"],
            "host_counts_exact": True,
            "contract_eligible_urls_exact": True,
            "physical_health_bound": True,
            "numeric_target_math_exact": True,
            "representativeness_not_inferred": True,
            "real_data_policy_enforced": True,
        },
        "summary": {
            "contract_eligible_physically_healthy_https_urls": executable,
            "numeric_target_urls": target,
            "numeric_target_gap_urls": expected_gap,
            "numeric_target_available": executable >= target,
        },
        "errors": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--provenance-audit", required=True)
    parser.add_argument("--host-health", required=True)
    parser.add_argument("--acquisition-validation", required=True)
    parser.add_argument("--obstruction-snapshot", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = validate(args)
    except Exception as exc:
        payload = {
            "schema_version": VALIDATION_SCHEMA,
            "status": "failed",
            "generated_at": utc_now(),
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        write_json_atomic(Path(args.out), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1
    write_json_atomic(Path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
