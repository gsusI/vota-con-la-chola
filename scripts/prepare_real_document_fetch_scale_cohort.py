#!/usr/bin/env python3
"""Prepare deterministic bounded cohorts of real official documents."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


PIPELINE_ID = "real_document_fetch_scale_cohort_v2"
DEFAULT_BOE_DOCUMENT_ROWS = 800
DEFAULT_BOE_SUMMARY_ROWS = 114
EXPECTED_HOST_ROWS = {
    "www.boe.es": 914,
    "www.parlamentodeandalucia.es": 86,
}
KNOWN_BLOCKED_HOSTS = {
    "contrataciondelestado.es",
    "parlamentodenavarra.es",
    "www.congreso.es",
    "www.senado.es",
}
FORBIDDEN_HTML_MARKERS = [
    "cf-mitigated",
    "<title>just a moment...</title>",
    "attention required! | cloudflare",
    "access denied",
]
MAX_PARTITION_ROWS = 250_000
MAX_PARTITION_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repository: {path}") from exc


def source_descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": repo_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def read_only_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
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


def validate_host_health(path: Path) -> dict[str, Any]:
    report = read_json(path)
    if report.get("schema_version") != "real_document_host_health_v1":
        raise ValueError("host health schema mismatch")
    policy = report.get("policy") or {}
    if policy.get("official_real_documents_only") is not True:
        raise ValueError("host health real-document policy mismatch")
    if policy.get("synthetic_or_mock_records_counted") is not False:
        raise ValueError("host health synthetic-data policy mismatch")
    probes = {
        str(row.get("host") or ""): row for row in report.get("probes") or []
    }
    parliament = probes.get("www.parlamentodeandalucia.es") or {}
    if (
        parliament.get("eligible") is not True
        or int(parliament.get("http_status") or 0) != 200
        or parliament.get("validation_mode") != "official_html_semantic_contract"
    ):
        raise ValueError("Parlamento de Andalucia host is not probe-eligible")
    excluded = set(report.get("known_blocked_hosts_excluded_without_probe") or [])
    if not KNOWN_BLOCKED_HOSTS.issubset(excluded):
        raise ValueError("known blocked host exclusion set is incomplete")
    return report


def boe_validation_contract(
    *, source_id: str, expected_bytes: int
) -> dict[str, Any]:
    allowed_types = ["application/xml", "text/xml"]
    if source_id == "boe_daily_summaries":
        allowed_types.extend(["application/json", "text/json"])
    return {
        "require_https": True,
        "expected_host": "www.boe.es",
        "minimum_bytes": max(1, min(expected_bytes, 1024)),
        "allowed_content_types": allowed_types,
    }


def decile_quota(total: int) -> tuple[int, int]:
    if total < 0:
        raise ValueError("row quota cannot be negative")
    return divmod(total, 10)


def select_boe_rows(
    conn: sqlite3.Connection,
    *,
    document_rows: int,
    summary_rows: int,
) -> list[dict[str, Any]]:
    document_base, document_extra = decile_quota(document_rows)
    summary_base, summary_extra = decile_quota(summary_rows)
    rows = conn.execute(
        """
        WITH ranked AS (
          SELECT
            w.pipeline_id AS source_pipeline_id,
            w.item_key AS source_url,
            w.payload_json,
            f.source_id,
            f.content_type,
            f.content_sha256,
            f.bytes,
            f.raw_path,
            NTILE(10) OVER (
              PARTITION BY w.pipeline_id
              ORDER BY f.bytes, w.item_key
            ) AS size_decile
          FROM pipeline_work_items w
          JOIN document_fetches f ON f.doc_url = w.item_key
          WHERE w.pipeline_id IN ('boe_document_fetch', 'boe_summary_fetch')
            AND w.state = 'succeeded'
            AND f.fetched_ok = 1
            AND f.last_http_status = 200
            AND f.doc_url LIKE 'https://www.boe.es/%'
            AND f.content_sha256 IS NOT NULL
            AND f.bytes > 0
            AND f.raw_path IS NOT NULL
        ), numbered AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY source_pipeline_id, size_decile
            ORDER BY source_url
          ) AS row_in_decile
          FROM ranked
        )
        SELECT *
        FROM numbered
        WHERE (
          source_pipeline_id = 'boe_document_fetch'
          AND row_in_decile <= ? + CASE WHEN size_decile <= ? THEN 1 ELSE 0 END
        ) OR (
          source_pipeline_id = 'boe_summary_fetch'
          AND row_in_decile <= ? + CASE WHEN size_decile <= ? THEN 1 ELSE 0 END
        )
        ORDER BY source_pipeline_id, size_decile, source_url
        """,
        (document_base, document_extra, summary_base, summary_extra),
    ).fetchall()
    selected: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, dict):
            raise ValueError(f"queue payload is not an object: {row['source_url']}")
        source_pipeline_id = str(row["source_pipeline_id"])
        expected_source_id = (
            "boe_document_xml"
            if source_pipeline_id == "boe_document_fetch"
            else "boe_daily_summaries"
        )
        source_url = str(row["source_url"])
        if str(row["source_id"]) != expected_source_id:
            raise ValueError(f"BOE source mismatch: {source_url}")
        if str(payload.get("document_source_id") or "") != expected_source_id:
            raise ValueError(f"BOE payload source mismatch: {source_url}")
        if payload.get("synthetic_or_mock_records_counted") is not False:
            raise ValueError(f"BOE real-data policy mismatch: {source_url}")
        if payload.get("official_public_domain_personal_information_retained") is not True:
            raise ValueError(f"BOE public-information policy mismatch: {source_url}")
        raw_path = Path(str(row["raw_path"]))
        expected_bytes = int(row["bytes"])
        expected_sha256 = str(row["content_sha256"])
        if not raw_path.is_file() or raw_path.stat().st_size != expected_bytes:
            raise ValueError(f"BOE captured raw size mismatch: {source_url}")
        if sha256_path(raw_path) != expected_sha256:
            raise ValueError(f"BOE captured raw hash mismatch: {source_url}")
        payload = {
            **payload,
            "validation_contract": boe_validation_contract(
                source_id=expected_source_id,
                expected_bytes=expected_bytes,
            ),
        }
        selected.append(
            {
                "source_pipeline_id": source_pipeline_id,
                "source_id": expected_source_id,
                "source_url": source_url,
                "source_host": "www.boe.es",
                "document_kind": (
                    "boe_document_xml"
                    if source_pipeline_id == "boe_document_fetch"
                    else "boe_daily_summary"
                ),
                "validation_mode": (
                    "boe_document_identifier"
                    if source_pipeline_id == "boe_document_fetch"
                    else "boe_summary_structure"
                ),
                "size_decile": int(row["size_decile"]),
                "expected_bytes": expected_bytes,
                "expected_content_sha256": expected_sha256,
                "captured_raw_path": repo_path(raw_path),
                "partition_key": f"{source_pipeline_id}:size_decile_{row['size_decile']}",
                "payload": payload,
            }
        )
    counts = {
        "boe_document_fetch": sum(
            row["source_pipeline_id"] == "boe_document_fetch" for row in selected
        ),
        "boe_summary_fetch": sum(
            row["source_pipeline_id"] == "boe_summary_fetch" for row in selected
        ),
    }
    expected = {
        "boe_document_fetch": document_rows,
        "boe_summary_fetch": summary_rows,
    }
    if counts != expected:
        raise ValueError(f"BOE row allocation mismatch: expected={expected} actual={counts}")
    return selected


def safe_capture_path(raw_root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe provenance capture path: {value}")
    path = (raw_root / relative).resolve()
    try:
        path.relative_to(raw_root.resolve())
    except ValueError as exc:
        raise ValueError(f"provenance capture escapes raw root: {value}") from exc
    return path


def parliament_validation_contract(
    *, source_url: str, document_kind: str
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "require_https": True,
        "expected_host": "www.parlamentodeandalucia.es",
        "minimum_bytes": 8192,
        "forbidden_ascii_casefolded": FORBIDDEN_HTML_MARKERS,
    }
    if document_kind == "pdf":
        return {
            **base,
            "required_ascii_casefolded": ["%pdf-"],
        }
    references = parse_qs(urlparse(source_url).query).get("numexp") or []
    if len(references) == 1 and str(references[0]).strip():
        required = ["<!doctype html", str(references[0]).lower()]
    elif "resultadosvotaciones.do" in urlparse(source_url).path:
        required = ["<!doctype html", "<title>sentido del voto", "votaciones"]
    elif "todaslasiniciativas/portipo.do" in urlparse(source_url).path:
        required = ["<!doctype html", "iniciativas", "legislatura"]
    else:
        raise ValueError(f"Parlamento HTML URL lacks a semantic contract: {source_url}")
    return {
        **base,
        "allowed_content_types": ["text/html"],
        "required_ascii_casefolded": required,
    }


def select_parliament_rows(edges_path: Path, raw_root: Path) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    with edges_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            edge = json.loads(line)
            if not isinstance(edge, dict):
                raise ValueError(f"edge line {line_number} is not an object")
            source_url = str(edge.get("source_url") or "")
            parsed = urlparse(source_url)
            if (
                edge.get("url_kind") != "public_https"
                or parsed.scheme != "https"
                or (parsed.hostname or "").lower() != "www.parlamentodeandalucia.es"
            ):
                continue
            projection = {
                key: edge.get(key)
                for key in (
                    "declared_bytes",
                    "file_path",
                    "file_sha256",
                    "match_basis",
                    "source_id",
                    "source_url",
                )
            }
            previous = by_url.get(source_url)
            if previous is not None:
                previous_projection = {
                    key: previous.get(key) for key in projection
                }
                if previous_projection != projection:
                    raise ValueError(f"ambiguous provenance for URL: {source_url}")
                previous["db_refs"] = sorted(
                    {*previous["db_refs"], str(edge.get("db_ref") or "")}
                )
                previous["table_names"] = sorted(
                    {*previous["table_names"], str(edge.get("table_name") or "")}
                )
            else:
                by_url[source_url] = {
                    **projection,
                    "db_refs": [str(edge.get("db_ref") or "")],
                    "table_names": [str(edge.get("table_name") or "")],
                }
    base_rows: list[dict[str, Any]] = []
    for source_url, edge in sorted(by_url.items()):
        if edge.get("match_basis") != "path_checksum":
            raise ValueError(f"weak provenance basis: {source_url}")
        file_path = str(edge.get("file_path") or "")
        captured = safe_capture_path(raw_root, file_path)
        expected_bytes = int(edge.get("declared_bytes") or 0)
        expected_sha256 = str(edge.get("file_sha256") or "")
        if expected_bytes <= 0 or len(expected_sha256) != 64:
            raise ValueError(f"invalid provenance size/hash: {source_url}")
        if not captured.is_file() or captured.stat().st_size != expected_bytes:
            raise ValueError(f"captured Parliament file size mismatch: {source_url}")
        if sha256_path(captured) != expected_sha256:
            raise ValueError(f"captured Parliament file hash mismatch: {source_url}")
        document_kind = "pdf" if captured.suffix.lower() == ".pdf" else "html"
        validation_mode = (
            "parliament_pdf_signature"
            if document_kind == "pdf"
            else "parliament_html_semantic"
        )
        validation_contract = parliament_validation_contract(
            source_url=source_url,
            document_kind=document_kind,
        )
        payload = {
            "doc_url": source_url,
            "document_source_id": "parl_initiative_docs",
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock_records_counted": False,
            "provenance": {
                "source_id": str(edge.get("source_id") or ""),
                "table_names": list(edge.get("table_names") or []),
                "db_refs": list(edge.get("db_refs") or []),
                "captured_raw_path": repo_path(captured),
                "captured_content_sha256": expected_sha256,
                "captured_bytes": expected_bytes,
            },
            "validation_contract": validation_contract,
        }
        base_rows.append(
            {
                "source_pipeline_id": "provenance_edges:parlamento_andalucia",
                "source_id": "parl_initiative_docs",
                "provenance_source_id": str(edge.get("source_id") or ""),
                "source_url": source_url,
                "source_host": "www.parlamentodeandalucia.es",
                "document_kind": f"parliament_{document_kind}",
                "validation_mode": validation_mode,
                "expected_bytes": expected_bytes,
                "expected_content_sha256": expected_sha256,
                "captured_raw_path": repo_path(captured),
                "partition_key": f"parlamento_andalucia:{document_kind}",
                "payload": payload,
            }
        )
    for document_kind in ("parliament_html", "parliament_pdf"):
        members = sorted(
            (row for row in base_rows if row["document_kind"] == document_kind),
            key=lambda row: (int(row["expected_bytes"]), str(row["source_url"])),
        )
        total = len(members)
        for index, row in enumerate(members):
            row["size_decile"] = min(10, (index * 10 // total) + 1)
    return sorted(base_rows, key=lambda row: str(row["source_url"]))


def validate_rows(
    rows: list[dict[str, Any]],
    *,
    expected_rows: int,
    expected_host_rows: dict[str, int],
    expected_mode_rows: dict[str, int],
) -> list[dict[str, Any]]:
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows:,} rows, got {len(rows):,}")
    urls = [str(row["source_url"]) for row in rows]
    if len(set(urls)) != len(urls):
        raise ValueError("cohort URLs are not unique")
    host_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    for row in rows:
        host = str(row["source_host"])
        host_counts[host] = host_counts.get(host, 0) + 1
        mode = str(row["validation_mode"])
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        if host in KNOWN_BLOCKED_HOSTS:
            raise ValueError(f"known blocked host selected: {host}")
        payload = row["payload"]
        if payload.get("synthetic_or_mock_records_counted") is not False:
            raise ValueError(f"real-data policy mismatch: {row['source_url']}")
        if payload.get("official_public_domain_personal_information_retained") is not True:
            raise ValueError(f"public-information policy mismatch: {row['source_url']}")
    if host_counts != expected_host_rows:
        raise ValueError(f"host allocation mismatch: {host_counts}")
    if mode_counts != expected_mode_rows:
        raise ValueError(f"validation-mode allocation mismatch: {mode_counts}")
    rows.sort(
        key=lambda row: (
            str(row["source_pipeline_id"]),
            int(row["size_decile"]),
            str(row["source_url"]),
        )
    )
    host_ranks: dict[str, int] = {}
    for row in rows:
        host = str(row["source_host"])
        host_rank = host_ranks.get(host, 0)
        row["queue_priority"] = -host_rank
        host_ranks[host] = host_rank + 1
    return rows


def semantic_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "source_pipeline_id",
        "source_id",
        "source_url",
        "source_host",
        "document_kind",
        "validation_mode",
        "size_decile",
        "expected_bytes",
        "expected_content_sha256",
    )
    return [{field: row.get(field) for field in fields} for row in rows]


def semantic_sha256(rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        semantic_projection(rows),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def partitioned_semantic_sha256(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(
                semantic_projection([row])[0],
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def partition_slug(source_pipeline_id: str, size_decile: int) -> str:
    safe_pipeline = "".join(
        character if character.isalnum() else "-"
        for character in source_pipeline_id.lower()
    ).strip("-")
    return f"{safe_pipeline}-size-decile-{size_decile:02d}.jsonl.gz"


def write_partitioned_rows(
    *, partition_dir: Path, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    if partition_dir.exists():
        raise ValueError(f"manifest partition directory already exists: {partition_dir}")
    partition_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{partition_dir.name}.", dir=partition_dir.parent)
    )
    descriptors: list[dict[str, Any]] = []
    try:
        for (source_pipeline_id, size_decile), member_rows in groupby(
            rows,
            key=lambda row: (
                str(row["source_pipeline_id"]),
                int(row["size_decile"]),
            ),
        ):
            members = list(member_rows)
            if len(members) > MAX_PARTITION_ROWS:
                raise ValueError(
                    "manifest partition exceeds row bound: "
                    f"{source_pipeline_id} decile {size_decile}"
                )
            filename = partition_slug(source_pipeline_id, size_decile)
            temporary_path = temporary / filename
            uncompressed_bytes = 0
            with temporary_path.open("wb") as raw_handle:
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=raw_handle, mtime=0
                ) as compressed:
                    for row in members:
                        line = (
                            json.dumps(
                                row,
                                ensure_ascii=True,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                        compressed.write(line)
                        uncompressed_bytes += len(line)
                        if uncompressed_bytes > MAX_PARTITION_UNCOMPRESSED_BYTES:
                            raise ValueError(
                                "manifest partition exceeds expanded-byte bound: "
                                f"{source_pipeline_id} decile {size_decile}"
                            )
                raw_handle.flush()
                os.fsync(raw_handle.fileno())
            descriptors.append(
                {
                    "path": repo_path(partition_dir / filename),
                    "compression": "gzip",
                    "rows": len(members),
                    "bytes": temporary_path.stat().st_size,
                    "uncompressed_bytes": uncompressed_bytes,
                    "sha256": sha256_path(temporary_path),
                    "source_pipeline_id": source_pipeline_id,
                    "size_decile": size_decile,
                    "first_source_url": str(members[0]["source_url"]),
                    "last_source_url": str(members[-1]["source_url"]),
                }
            )
        os.replace(temporary, partition_dir)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "layout": "partitioned_jsonl_gzip_v1",
        "semantic_identity_contract": (
            "sha256_concatenated_canonical_projection_jsonl_v1"
        ),
        "rows": len(rows),
        "partitions": descriptors,
    }


def build_queue_db(
    *, schema_path: Path, out_db: Path, rows: list[dict[str, Any]], prepared_at: str
) -> None:
    out_db.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{out_db.name}.", suffix=".tmp", dir=out_db.parent
    )
    os.close(descriptor)
    try:
        conn = sqlite3.connect(temporary)
        try:
            conn.executescript(schema_path.read_text(encoding="utf-8"))
            conn.executemany(
                """
                INSERT INTO pipeline_work_items (
                  pipeline_id, item_key, partition_key, priority, state,
                  payload_json, available_at, attempts, max_attempts,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, 0, 2, ?, ?)
                """,
                (
                    (
                        PIPELINE_ID,
                        row["source_url"],
                        row["partition_key"],
                        int(row["queue_priority"]),
                        json.dumps(
                            row["payload"],
                            ensure_ascii=True,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        prepared_at,
                        prepared_at,
                        prepared_at,
                    )
                    for row in rows
                ),
            )
            conn.commit()
            if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise ValueError("prepared database integrity failed")
        finally:
            conn.close()
        os.replace(temporary, out_db)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--schema", default="etl/load/sqlite_schema.sql")
    parser.add_argument(
        "--provenance-edges",
        default="etl/data/manifests/real-document-provenance-edges.jsonl",
    )
    parser.add_argument("--raw-root", default="etl/data/raw")
    parser.add_argument("--host-health", required=True)
    parser.add_argument("--out-db", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument(
        "--manifest-layout",
        choices=("embedded_v2", "partitioned_v3"),
        default="embedded_v2",
    )
    parser.add_argument("--manifest-partition-dir", default="")
    parser.add_argument(
        "--boe-document-rows", type=int, default=DEFAULT_BOE_DOCUMENT_ROWS
    )
    parser.add_argument(
        "--boe-summary-rows", type=int, default=DEFAULT_BOE_SUMMARY_ROWS
    )
    parser.add_argument("--prepared-at", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_db = Path(args.source_db)
    schema_path = Path(args.schema)
    edges_path = Path(args.provenance_edges)
    raw_root = Path(args.raw_root)
    host_health_path = Path(args.host_health)
    out_db = Path(args.out_db)
    manifest_out = Path(args.manifest_out)
    partition_dir = (
        Path(
            args.manifest_partition_dir
            or manifest_out.with_suffix("").as_posix() + "-rows"
        )
        if args.manifest_layout == "partitioned_v3"
        else None
    )
    prepared_at = str(args.prepared_at or "").strip() or utc_now()
    created_out_db = False
    created_partition_dir = False
    try:
        datetime.fromisoformat(prepared_at.replace("Z", "+00:00"))
        for required in (source_db, schema_path, edges_path, host_health_path):
            if not required.is_file():
                raise ValueError(f"required input missing: {required}")
        if not raw_root.is_dir():
            raise ValueError(f"raw root missing: {raw_root}")
        for output in (out_db, manifest_out, partition_dir):
            if output is not None and output.exists():
                raise ValueError(f"output already exists: {output}")
        host_health = validate_host_health(host_health_path)
        with read_only_db(source_db) as conn:
            boe_rows = select_boe_rows(
                conn,
                document_rows=args.boe_document_rows,
                summary_rows=args.boe_summary_rows,
            )
        parliament_rows = select_parliament_rows(edges_path, raw_root)
        expected_mode_rows = {
            "boe_document_identifier": args.boe_document_rows,
            "boe_summary_structure": args.boe_summary_rows,
            "parliament_html_semantic": sum(
                row["validation_mode"] == "parliament_html_semantic"
                for row in parliament_rows
            ),
            "parliament_pdf_signature": sum(
                row["validation_mode"] == "parliament_pdf_signature"
                for row in parliament_rows
            ),
        }
        expected_host_rows = {
            "www.boe.es": args.boe_document_rows + args.boe_summary_rows,
            "www.parlamentodeandalucia.es": len(parliament_rows),
        }
        expected_rows = sum(expected_host_rows.values())
        rows = validate_rows(
            boe_rows + parliament_rows,
            expected_rows=expected_rows,
            expected_host_rows=expected_host_rows,
            expected_mode_rows=expected_mode_rows,
        )
        if args.manifest_layout == "partitioned_v3":
            cohort_sha256 = partitioned_semantic_sha256(rows)
        else:
            cohort_sha256 = semantic_sha256(rows)
        build_queue_db(
            schema_path=schema_path,
            out_db=out_db,
            rows=rows,
            prepared_at=prepared_at,
        )
        created_out_db = True
        host_counts: dict[str, int] = {}
        kind_counts: dict[str, int] = {}
        mode_counts: dict[str, int] = {}
        for row in rows:
            for counts, key in (
                (host_counts, str(row["source_host"])),
                (kind_counts, str(row["document_kind"])),
                (mode_counts, str(row["validation_mode"])),
            ):
                counts[key] = counts.get(key, 0) + 1
        manifest: dict[str, Any] = {
            "schema_version": (
                "real_document_fetch_scale_cohort_v3"
                if args.manifest_layout == "partitioned_v3"
                else "real_document_fetch_scale_cohort_v2"
            ),
            "prepared_at": prepared_at,
            "status": "ready",
            "cohort_id": f"real_document_fetch_scale_cohort_{cohort_sha256[:24]}",
            "cohort_semantic_sha256": cohort_sha256,
            "pipeline_id": PIPELINE_ID,
            "policy": {
                "official_real_documents_only": True,
                "synthetic_or_mock_records_counted": False,
                "official_public_domain_personal_information_retained": True,
                "known_blocked_rows_selected": 0,
                "known_blocked_hosts_excluded": sorted(KNOWN_BLOCKED_HOSTS),
                "dynamic_official_html_requires_semantic_contract": True,
                "official_content_revisions_preserved_and_measured": True,
            },
            "selection": {
                "method": "deterministic_official_host_kind_and_captured_size_decile",
                "rows": len(rows),
                "expected_prior_bytes": sum(int(row["expected_bytes"]) for row in rows),
                "hosts": dict(sorted(host_counts.items())),
                "document_kinds": dict(sorted(kind_counts.items())),
                "validation_modes": dict(sorted(mode_counts.items())),
                "size_deciles": 10,
            },
            "host_health": {
                "status": host_health.get("status"),
                "probe_requests": int(
                    (host_health.get("method") or {}).get("probe_requests") or 0
                ),
                "eligible_hosts": sorted(EXPECTED_HOST_ROWS),
            },
            "inputs": {
                "producer": source_descriptor(Path(__file__)),
                "source_db": source_descriptor(source_db),
                "schema": source_descriptor(schema_path),
                "provenance_edges": source_descriptor(edges_path),
                "host_health": source_descriptor(host_health_path),
            },
            "output_db": repo_path(out_db),
        }
        if args.manifest_layout == "partitioned_v3":
            if partition_dir is None:
                raise ValueError("partition directory is required for v3")
            manifest["row_manifest"] = write_partitioned_rows(
                partition_dir=partition_dir,
                rows=rows,
            )
            created_partition_dir = True
        else:
            manifest["rows"] = rows
        write_json_atomic(manifest_out, manifest)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        if created_out_db:
            out_db.unlink(missing_ok=True)
        if created_partition_dir and partition_dir is not None:
            shutil.rmtree(partition_dir, ignore_errors=True)
        print(f"ERROR real document fetch scale cohort preparation: {exc}")
        return 2
    print(
        "OK real document fetch scale cohort -> "
        f"{out_db} (rows={len(rows)} prior_bytes={manifest['selection']['expected_prior_bytes']} "
        f"sha256={cohort_sha256})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
