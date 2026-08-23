#!/usr/bin/env python3
"""Reconcile the real document inventory with durable source metadata."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import re
import sqlite3
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY_MANIFEST = Path(
    "etl/data/manifests/real-document-format-inventory.jsonl"
)
DEFAULT_FILE_MANIFEST = Path("etl/data/manifests/real-document-provenance-files.jsonl")
DEFAULT_EDGE_MANIFEST = Path("etl/data/manifests/real-document-provenance-edges.jsonl")
DEFAULT_AUXILIARY_PROVENANCE_MANIFESTS = (
    Path("etl/data/manifests/member-vote-source-url-lineage.jsonl"),
)
DEFAULT_PUBLISHED_CAPTURE_INDEXES = (
    Path("etl/data/published/proximas-elecciones-espana.json"),
    Path("etl/data/published/andalucia-2026-accountability.json"),
)
DEFAULT_ARCHIVED_DOCUMENT_LINEAGE_MANIFESTS = (
    Path(
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
        "archived-document-source-lineage.jsonl"
    ),
)
DEFAULT_WAYBACK_DOCUMENT_LINEAGE_MANIFESTS = (
    Path(
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
        "wayback-document-lineage.jsonl"
    ),
)
DEFAULT_BOE_DOCUMENT_CORPUS_LINEAGE_MANIFESTS = (
    Path("etl/data/manifests/boe-document-corpus-lineage.jsonl"),
)
DEFAULT_CAPTURED_LINK_DOCUMENT_LINEAGE_MANIFESTS = (
    Path(
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
        "captured-link-document-lineage.jsonl"
    ),
)
DEFAULT_OFFICIAL_DOCUMENT_IDENTIFIER_LINEAGE_MANIFESTS = (
    Path(
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
        "official-document-identifier-lineage.jsonl"
    ),
)
DEFAULT_OFFICIAL_PATH_DOCUMENT_LINEAGE_MANIFESTS = (
    Path(
        "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
        "official-path-document-lineage.jsonl"
    ),
)
DEFAULT_PARTY_PROGRAM_SOURCE_MANIFEST_DIR = Path("etl/data/raw/programas_partidos")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-provenance-audit.json"
)
DEFAULT_DATABASES = (
    Path("etl/data/staging/politicos-es.db"),
    Path("etl/data/staging/parlamentario-es.db"),
    Path("etl/data/staging/placsp-contracts-real-s1-20260811.db"),
)
SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm", ".xml"}
DISALLOWED_PUBLIC_HOSTS = {
    "",
    "0.0.0.0",
    "127.0.0.1",
    "example.com",
    "example.invalid",
    "example.org",
    "localhost",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EMBEDDED_METADATA_READ_LIMIT_BYTES = 16 * 1024 * 1024
PLACSP_EMBEDDED_URL_SOURCE_GROUPS = {
    "placsp_autonomico_detail",
    "placsp_sindicacion_detail",
}
PLACSP_SELF_LINK_RE = re.compile(
    r"<span[^>]+id=[\"'][^\"']*hiperenlaceId[\"'][^>]*>\s*"
    r"(https://contrataciondelestado\.es/wps/poc\?"
    r"uri=deeplink:detalle_licitacion(?:&amp;|&)idEvl=[^<\s]+)\s*</span>",
    re.IGNORECASE,
)
SENATE_INITIATIVE_SOURCE_GROUP = "text_documents/parl_initiative_docs"
CONGRESS_INTERVENTION_SOURCE_GROUP = "text_documents/congreso_intervenciones"
HTML_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
HTML_HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)
HTML_FORM_ACTION_RE = re.compile(
    r"<form\b[^>]*\baction=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
HTML_LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
HTML_ATTRIBUTE_RE = re.compile(
    r"([A-Za-z_:][A-Za-z0-9_:.-]*)\s*=\s*([\"'])(.*?)\2",
    re.DOTALL,
)
MONCLOA_RSS_CHANNEL_TITLE_RE = re.compile(
    r"<channel\b[^>]*>.*?<title\b[^>]*>\s*"
    r"(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</title>",
    re.IGNORECASE | re.DOTALL,
)
SENATE_INITIATIVE_CAPTURE_PATHS = {
    "/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html",
    "/web/actividadparlamentaria/iniciativas/enmiendas/index.html",
}
CONGRESS_CURRENT_URL_RE = re.compile(
    r"Liferay\.currentURL\s*=\s*'([^']+)'",
    re.IGNORECASE,
)
SELF_URL_LINK_RES = (
    re.compile(
        r"<link\s+rel=[\"']canonical[\"']\s+href=[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    ),
    re.compile(
        r"<link\s+href=[\"']([^\"']+)[\"']\s+rel=[\"']canonical[\"']",
        re.IGNORECASE,
    ),
    re.compile(
        r"<meta\s+property=[\"']og:url[\"']\s+content=[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    ),
)
MANUAL_SOURCE_GROUP = "manual"
MONCLOA_SOURCE_GROUP = "moncloa_referencias"
MONCLOA_RSS_SOURCE_GROUP = "moncloa_rss_referencias"
PARTY_PROGRAM_SOURCE_GROUP = "text_documents/programas_partidos"
PRIMARY_PARTY_HOSTS = {
    "coalicioncanaria.org",
    "compromis.net",
    "cup.cat",
    "elecciones.upn.org",
    "ehbildu.eus",
    "foroasturias.es",
    "izquierdaunida.org",
    "movimientosumar.es",
    "verdesequo.es",
    "www.bng.gal",
    "www.ciudadanos-cs.org",
    "www.eaj-pnv.eus",
    "www.pp.es",
    "www.socialistes.cat",
    "www.upn.org",
    "www.voxespana.es",
}
ANDALUCIA_PROGRAM_CAPTURE_HOSTS = {
    "campaign_domain": {"juanmapresidente.es"},
    "party_affiliated_domain": {"fundacionandalucia-asd.com"},
    "party_domain": {"andalucia.porunmundomasjusto.es"},
    "press_hosted_copy": {"www.eldebate.com"},
}
ANDALUCIA_PROGRAM_PATH_RE = re.compile(
    r"^elections/andalucia_2026/programas/"
    r"(?P<source_id>andalucia_2026_programa_[a-z0-9_]+)\.pdf$"
)
SENATE_VOTE_SOURCE_PATH_RE = re.compile(
    r"^/legis(?P<legislature>\d+)/votaciones/(?P<filename>ses_[^/]+\.xml)$"
)
SENATE_VOTE_XML_URL_RE = re.compile(
    r"<url_votacion_xml\b[^>]*>\s*"
    r"(https?://www\.senado\.es/legis\d+/votaciones/ses_[^<\s]+\.xml)\s*"
    r"</url_votacion_xml>",
    re.IGNORECASE,
)
SENATE_OFFICIAL_DIARY_URL_RE = re.compile(
    r"^https://www\.congreso\.es/public_oficiales/"
    r"L(?P<legislature>\d+)/SEN/DS/(?P<section>PL|CO)/"
    r"(?P<identifier>DS_(?P<kind>P|C)_(?P=legislature)_\d+)\.PDF$",
    re.IGNORECASE,
)
SENATE_DIARY_INTERNAL_IDENTIFIER_RE = re.compile(rb"DS_[PC]_\d+_\d+")
EUROPARL_MEP_SOURCE_URL = "https://www.europarl.europa.eu/meps/es/full-list/xml"
WAYBACK_CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
WAYBACK_CDX_DIGEST_RE = re.compile(r"^[A-Z2-7]{32}$")


class ProvenanceAuditError(RuntimeError):
    """Raised when an input or output violates the audit contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", default=str(DEFAULT_INVENTORY_ROOT))
    parser.add_argument("--inventory-manifest", default=str(DEFAULT_INVENTORY_MANIFEST))
    parser.add_argument("--db", action="append", dest="databases")
    parser.add_argument(
        "--provenance-manifest",
        action="append",
        dest="provenance_manifests",
    )
    parser.add_argument(
        "--published-capture-index",
        action="append",
        dest="published_capture_indexes",
    )
    parser.add_argument(
        "--party-program-source-manifest",
        action="append",
        dest="party_program_source_manifests",
    )
    parser.add_argument(
        "--archived-document-lineage-manifest",
        action="append",
        dest="archived_document_lineage_manifests",
    )
    parser.add_argument(
        "--wayback-document-lineage-manifest",
        action="append",
        dest="wayback_document_lineage_manifests",
    )
    parser.add_argument(
        "--boe-document-corpus-lineage-manifest",
        action="append",
        dest="boe_document_corpus_lineage_manifests",
    )
    parser.add_argument(
        "--captured-link-document-lineage-manifest",
        action="append",
        dest="captured_link_document_lineage_manifests",
    )
    parser.add_argument(
        "--official-document-identifier-lineage-manifest",
        action="append",
        dest="official_document_identifier_lineage_manifests",
    )
    parser.add_argument(
        "--official-path-document-lineage-manifest",
        action="append",
        dest="official_path_document_lineage_manifests",
    )
    parser.add_argument("--file-manifest-out", default=str(DEFAULT_FILE_MANIFEST))
    parser.add_argument("--edge-manifest-out", default=str(DEFAULT_EDGE_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce-integrity", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text_artifact(path: Path) -> str:
    digest = hashlib.sha256()
    opener = gzip.open if path.suffix.lower() == ".gz" else Path.open
    with opener(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path, *, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def safe_repo_path(value: str | Path, *, repo_root: Path) -> Path:
    candidate = (repo_root / value).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ProvenanceAuditError(f"path escapes repository: {value}") from exc
    return candidate


def normalize_repo_path(value: Any, *, repo_root: Path) -> str | None:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            marker = "/etl/"
            if marker not in raw:
                return None
            raw = "etl/" + raw.split(marker, 1)[1]
    normalized = PurePosixPath(raw)
    if normalized.is_absolute() or ".." in normalized.parts:
        return None
    return normalized.as_posix().removeprefix("./")


def normalize_inventory_path(
    value: Any,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> str | None:
    repo_path = normalize_repo_path(value, repo_root=repo_root)
    if repo_path is None:
        return None
    try:
        root_relative = (
            inventory_root.resolve().relative_to(repo_root.resolve()).as_posix()
        )
    except ValueError as exc:
        raise ProvenanceAuditError("inventory root must be inside repository") from exc
    prefix = root_relative.rstrip("/") + "/"
    if repo_path.startswith(prefix):
        return repo_path[len(prefix) :]
    if repo_path == root_relative:
        return None
    return repo_path


def public_url_kind(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host in DISALLOWED_PUBLIC_HOSTS:
        return "missing_or_non_public"
    return "public_https" if parsed.scheme == "https" else "public_http"


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def select_expression(columns: set[str], column: str) -> str:
    return f'"{column}"' if column in columns else "NULL"


def iter_metadata_rows(
    connection: sqlite3.Connection,
    table: str,
) -> Iterator[sqlite3.Row]:
    columns = table_columns(connection, table)
    if "raw_path" not in columns:
        return
    fetched_column = "fetched_at"
    if fetched_column not in columns and "last_attempt_at" in columns:
        fetched_column = "last_attempt_at"
    source_url_column = "source_url"
    if source_url_column not in columns and "doc_url" in columns:
        source_url_column = "doc_url"
    select = {
        "raw_path": select_expression(columns, "raw_path"),
        "content_sha256": select_expression(columns, "content_sha256"),
        "source_id": select_expression(columns, "source_id"),
        "source_url": select_expression(columns, source_url_column),
        "fetched_at": select_expression(columns, fetched_column),
        "bytes": select_expression(columns, "bytes"),
        "text_path": select_expression(columns, "text_path"),
        "text_sha256": select_expression(columns, "text_sha256"),
    }
    query = "SELECT " + ", ".join(
        f"{expression} AS {name}" for name, expression in select.items()
    )
    conditions = ['"raw_path" IS NOT NULL']
    if "text_path" in columns:
        conditions.append('"text_path" IS NOT NULL')
    query += f' FROM "{table}" WHERE ' + " OR ".join(conditions)
    yield from connection.execute(query)


def create_work_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = FILE;
        CREATE TABLE inventory (
          file_id INTEGER PRIMARY KEY,
          path TEXT NOT NULL UNIQUE,
          source_group TEXT NOT NULL,
          extension TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          item_status TEXT NOT NULL
        );
        CREATE INDEX inventory_sha_idx ON inventory(sha256);

        CREATE TABLE provenance (
          provenance_id INTEGER PRIMARY KEY,
          edge_key TEXT NOT NULL UNIQUE,
          db_ref TEXT NOT NULL,
          table_name TEXT NOT NULL,
          raw_path TEXT NOT NULL,
          normalized_path TEXT,
          content_sha256 TEXT,
          source_id TEXT,
          source_url TEXT,
          fetched_at TEXT,
          declared_bytes INTEGER,
          url_kind TEXT NOT NULL
        );
        CREATE INDEX provenance_path_idx ON provenance(normalized_path);
        CREATE INDEX provenance_sha_idx ON provenance(content_sha256);

        CREATE TABLE matches (
          file_id INTEGER NOT NULL,
          provenance_id INTEGER NOT NULL,
          match_basis TEXT NOT NULL,
          PRIMARY KEY(file_id, provenance_id)
        ) WITHOUT ROWID;
        CREATE INDEX matches_provenance_idx ON matches(provenance_id);

        CREATE TABLE text_refs (
          text_ref_id INTEGER PRIMARY KEY,
          ref_key TEXT NOT NULL UNIQUE,
          db_ref TEXT NOT NULL,
          source_id TEXT,
          source_url TEXT,
          text_path TEXT NOT NULL,
          text_sha256 TEXT
        );
        """
    )
    return connection


def load_inventory(
    work: sqlite3.Connection,
    manifest_path: Path,
) -> int:
    if not manifest_path.is_file():
        raise ProvenanceAuditError(f"inventory manifest missing: {manifest_path}")
    batch: list[tuple[str, str, str, int, str, str]] = []
    rows = 0
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceAuditError(
                    f"invalid inventory JSON at line {line_number}: {exc}"
                ) from exc
            path = str(item.get("path") or "")
            sha256 = str(item.get("sha256") or "").lower()
            if (
                not path
                or Path(path).is_absolute()
                or ".." in PurePosixPath(path).parts
            ):
                raise ProvenanceAuditError(
                    f"unsafe inventory path at line {line_number}: {path!r}"
                )
            if (
                "samples" in PurePosixPath(path).parts
                or item.get("real_data_status") != "eligible_real_capture"
            ):
                raise ProvenanceAuditError(
                    f"non-real or unclassified inventory row at line {line_number}: {path!r}"
                )
            if not SHA256_RE.fullmatch(sha256):
                raise ProvenanceAuditError(
                    f"invalid inventory SHA-256 at line {line_number}: {sha256!r}"
                )
            batch.append(
                (
                    path,
                    str(item.get("source_group") or "unknown"),
                    str(item.get("extension") or "unknown"),
                    int(item.get("bytes") or 0),
                    sha256,
                    str(item.get("status") or "unknown"),
                )
            )
            rows += 1
            if len(batch) >= 2_000:
                work.executemany(
                    """
                    INSERT INTO inventory(path, source_group, extension, bytes, sha256, item_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                batch.clear()
    if batch:
        work.executemany(
            """
            INSERT INTO inventory(path, source_group, extension, bytes, sha256, item_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
    work.commit()
    return rows


def load_official_capture_sidecars(
    work: sqlite3.Connection,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    """Load explicit official-source sidecars adjacent to eligible real captures."""
    scanned = 0
    accepted = 0
    for row in work.execute(
        "SELECT path, bytes, sha256 FROM inventory ORDER BY file_id"
    ).fetchall():
        normalized_path = str(row["path"])
        capture_path = (inventory_root / normalized_path).resolve()
        sidecar_path = Path(str(capture_path) + ".source.json")
        if not sidecar_path.is_file():
            continue
        scanned += 1
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProvenanceAuditError(
                f"invalid official capture sidecar {sidecar_path.name}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise ProvenanceAuditError(
                f"official capture sidecar is not an object: {sidecar_path.name}"
            )
        content_sha256 = str(payload.get("content_sha256") or "").lower()
        declared_bytes = payload.get("bytes")
        source_id = str(payload.get("source_id") or "").strip()
        source_url = str(payload.get("source_url") or "").strip()
        retrieved_at = str(payload.get("retrieved_at") or "").strip()
        if (
            payload.get("schema_version") != "official_source_capture_v1"
            or not source_id
            or public_url_kind(source_url) not in {"public_http", "public_https"}
            or not retrieved_at
            or not SHA256_RE.fullmatch(content_sha256)
            or not isinstance(declared_bytes, int)
            or declared_bytes <= 0
            or declared_bytes != int(row["bytes"])
            or content_sha256 != str(row["sha256"])
            or not capture_path.is_file()
            or capture_path.stat().st_size != declared_bytes
            or sha256_file(capture_path) != content_sha256
        ):
            raise ProvenanceAuditError(
                f"official capture sidecar mismatch: {sidecar_path.name}"
            )
        sidecar_ref = display_path(sidecar_path, repo_root=repo_root)
        values = (
            sidecar_ref,
            "official_source_capture_sidecar",
            normalized_path,
            content_sha256,
            source_id,
            source_url,
            retrieved_at,
        )
        work.execute(
            """
            INSERT OR IGNORE INTO provenance(
              edge_key, db_ref, table_name, raw_path, normalized_path,
              content_sha256, source_id, source_url, fetched_at,
              declared_bytes, url_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata_edge_key(values),
                sidecar_ref,
                "official_source_capture_sidecar",
                normalized_path,
                normalized_path,
                content_sha256,
                source_id,
                source_url,
                retrieved_at,
                declared_bytes,
                public_url_kind(source_url),
            ),
        )
        accepted += 1
    work.commit()
    return {
        "sidecars_scanned": scanned,
        "accepted_checksum_captures": accepted,
        "status": "ok",
    }


def metadata_edge_key(values: Iterable[Any]) -> str:
    encoded = "\x1f".join(str(value or "") for value in values).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_database_metadata(
    work: sqlite3.Connection,
    database_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    db_ref = display_path(database_path, repo_root=repo_root)
    result: dict[str, Any] = {
        "path": db_ref,
        "bytes": database_path.stat().st_size if database_path.is_file() else None,
        "status": "ok",
        "raw_metadata_rows": 0,
        "text_metadata_rows": 0,
        "tables": {},
    }
    if not database_path.is_file():
        result["status"] = "missing"
        return result
    source = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        available_tables = {
            str(row[0])
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table in (
            "raw_fetches",
            "run_fetches",
            "ingestion_runs",
            "text_documents",
            "document_fetches",
        ):
            if table not in available_tables:
                continue
            table_raw_rows = 0
            table_text_rows = 0
            for row in iter_metadata_rows(source, table):
                normalized_path = normalize_inventory_path(
                    row["raw_path"],
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                if (
                    normalized_path
                    and Path(normalized_path).suffix.lower() in SUPPORTED_SUFFIXES
                ):
                    content_sha256 = str(row["content_sha256"] or "").lower() or None
                    if content_sha256 and not SHA256_RE.fullmatch(content_sha256):
                        content_sha256 = None
                    values = (
                        db_ref,
                        table,
                        normalized_path,
                        content_sha256,
                        row["source_id"],
                        row["source_url"],
                        row["fetched_at"],
                    )
                    work.execute(
                        """
                        INSERT OR IGNORE INTO provenance(
                          edge_key, db_ref, table_name, raw_path, normalized_path,
                          content_sha256, source_id, source_url, fetched_at,
                          declared_bytes, url_kind
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            metadata_edge_key(values),
                            db_ref,
                            table,
                            str(row["raw_path"] or ""),
                            normalized_path,
                            content_sha256,
                            row["source_id"],
                            row["source_url"],
                            row["fetched_at"],
                            row["bytes"],
                            public_url_kind(row["source_url"]),
                        ),
                    )
                    table_raw_rows += 1
                text_path = normalize_repo_path(row["text_path"], repo_root=repo_root)
                if text_path:
                    text_sha256 = str(row["text_sha256"] or "").lower() or None
                    if text_sha256 and not SHA256_RE.fullmatch(text_sha256):
                        text_sha256 = None
                    values = (
                        db_ref,
                        table,
                        text_path,
                        text_sha256,
                        row["source_id"],
                        row["source_url"],
                    )
                    work.execute(
                        """
                        INSERT OR IGNORE INTO text_refs(
                          ref_key, db_ref, source_id, source_url, text_path, text_sha256
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            metadata_edge_key(values),
                            db_ref,
                            row["source_id"],
                            row["source_url"],
                            text_path,
                            text_sha256,
                        ),
                    )
                    table_text_rows += 1
            result["tables"][table] = {
                "raw_metadata_rows": table_raw_rows,
                "text_metadata_rows": table_text_rows,
            }
            result["raw_metadata_rows"] += table_raw_rows
            result["text_metadata_rows"] += table_text_rows
        work.commit()
    except sqlite3.DatabaseError as exc:
        result["status"] = "unreadable"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        source.close()
    return result


def load_vote_lineage_manifest(
    work: sqlite3.Connection,
    manifest_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise ProvenanceAuditError(
            f"auxiliary provenance manifest missing: {manifest_path}"
        )
    rows = 0
    accepted = 0
    skipped_without_capture = 0
    manifest_ref = display_path(manifest_path, repo_root=repo_root)
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceAuditError(
                    f"invalid auxiliary provenance JSON at line {line_number}: {exc}"
                ) from exc
            if item.get("capture_status") != "checksum_capture_present":
                skipped_without_capture += 1
                continue
            capture = item.get("capture")
            if not isinstance(capture, dict):
                raise ProvenanceAuditError(
                    f"missing capture object at auxiliary line {line_number}"
                )
            source_url = str(item.get("source_url") or "").strip()
            parsed = urlparse(source_url)
            source_match = SENATE_VOTE_SOURCE_PATH_RE.fullmatch(parsed.path)
            if (
                parsed.scheme not in {"http", "https"}
                or (parsed.hostname or "").lower() != "www.senado.es"
                or source_match is None
                or item.get("source_url_rewritten") is not False
            ):
                raise ProvenanceAuditError(
                    f"invalid Senate vote source contract at auxiliary line {line_number}"
                )
            normalized_path = normalize_inventory_path(
                capture.get("path"),
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            expected_path = (
                "manual/senado_votaciones_ses/"
                f"legis{source_match.group('legislature')}/"
                f"{source_match.group('filename')}"
            )
            content_sha256 = str(capture.get("sha256") or "").lower()
            declared_bytes = capture.get("bytes")
            if (
                normalized_path != expected_path
                or not SHA256_RE.fullmatch(content_sha256)
                or not isinstance(declared_bytes, int)
                or declared_bytes < 0
            ):
                raise ProvenanceAuditError(
                    f"invalid Senate capture contract at auxiliary line {line_number}"
                )
            values = (
                manifest_ref,
                "member_vote_source_url_lineage",
                normalized_path,
                content_sha256,
                "senado_votaciones",
                source_url,
                None,
            )
            work.execute(
                """
                INSERT OR IGNORE INTO provenance(
                  edge_key, db_ref, table_name, raw_path, normalized_path,
                  content_sha256, source_id, source_url, fetched_at,
                  declared_bytes, url_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata_edge_key(values),
                    manifest_ref,
                    "member_vote_source_url_lineage",
                    str(capture.get("path") or ""),
                    normalized_path,
                    content_sha256,
                    "senado_votaciones",
                    source_url,
                    None,
                    declared_bytes,
                    public_url_kind(source_url),
                ),
            )
            accepted += 1
    work.commit()
    return {
        "path": manifest_ref,
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
        "rows": rows,
        "accepted_checksum_captures": accepted,
        "skipped_without_capture": skipped_without_capture,
        "status": "ok",
    }


def load_party_program_source_manifests(
    work: sqlite3.Connection,
    manifest_paths: list[Path],
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    """Load exact local-path-to-official-URL relations from real source catalogs."""
    counts: Counter[str] = Counter()
    manifests: list[dict[str, Any]] = []
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for manifest_path in sorted(manifest_paths):
        if not manifest_path.is_file():
            raise ProvenanceAuditError(
                f"party program source manifest missing: {manifest_path}"
            )
        manifest_ref = display_path(manifest_path, repo_root=repo_root)
        manifests.append(
            {
                "path": manifest_ref,
                "bytes": manifest_path.stat().st_size,
                "sha256": sha256_file(manifest_path),
            }
        )
        with manifest_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"party_id", "source_url", "local_path"}
            if not required.issubset(reader.fieldnames or []):
                raise ProvenanceAuditError(
                    f"party program source manifest lacks required columns: {manifest_ref}"
                )
            for line_number, item in enumerate(reader, start=2):
                counts["rows"] += 1
                raw_path = str(item.get("local_path") or "").strip()
                if not raw_path:
                    counts["skipped_without_local_path"] += 1
                    continue
                counts["rows_with_local_path"] += 1
                normalized_path = normalize_inventory_path(
                    raw_path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                inventory_row = (
                    work.execute(
                        """
                        SELECT path, source_group, bytes, sha256
                        FROM inventory
                        WHERE path = ?
                        """,
                        (normalized_path,),
                    ).fetchone()
                    if normalized_path
                    else None
                )
                if (
                    inventory_row is None
                    or inventory_row["source_group"] != PARTY_PROGRAM_SOURCE_GROUP
                ):
                    counts["skipped_not_inventory_party_program"] += 1
                    continue
                path = PurePosixPath(str(inventory_row["path"]))
                if path.stem != str(inventory_row["sha256"]):
                    counts["skipped_content_address_mismatch"] += 1
                    continue
                source_url = str(item.get("source_url") or "").strip()
                if not is_allowed_self_url(PARTY_PROGRAM_SOURCE_GROUP, source_url):
                    counts["skipped_non_primary_or_non_public_url"] += 1
                    continue
                key = (str(inventory_row["path"]), source_url)
                candidates[key] = {
                    "manifest_ref": manifest_ref,
                    "line_number": line_number,
                    "raw_path": raw_path,
                    "normalized_path": str(inventory_row["path"]),
                    "bytes": int(inventory_row["bytes"]),
                    "sha256": str(inventory_row["sha256"]),
                    "source_id": f"programas_partidos:{str(item.get('party_id') or '').strip()}",
                    "source_url": source_url,
                }
    for item in candidates.values():
        values = (
            item["manifest_ref"],
            "party_program_source_manifest",
            item["normalized_path"],
            item["sha256"],
            item["source_id"],
            item["source_url"],
            None,
        )
        work.execute(
            """
            INSERT OR IGNORE INTO provenance(
              edge_key, db_ref, table_name, raw_path, normalized_path,
              content_sha256, source_id, source_url, fetched_at,
              declared_bytes, url_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata_edge_key(values),
                item["manifest_ref"],
                "party_program_source_manifest",
                item["raw_path"],
                item["normalized_path"],
                item["sha256"],
                item["source_id"],
                item["source_url"],
                None,
                item["bytes"],
                public_url_kind(item["source_url"]),
            ),
        )
    work.commit()
    counts["accepted_unique_relations"] = len(candidates)
    return {
        "status": "ok",
        "manifests": manifests,
        **dict(sorted(counts.items())),
    }


def load_archived_document_lineage_manifest(
    work: sqlite3.Connection,
    manifest_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    """Load checksum-exact public lineage recovered from archived metadata DBs."""
    if not manifest_path.is_file():
        raise ProvenanceAuditError(
            f"archived document lineage manifest missing: {manifest_path}"
        )
    manifest_ref = display_path(manifest_path, repo_root=repo_root)
    rows = 0
    accepted = 0
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceAuditError(
                    f"invalid archived lineage JSON at line {line_number}: {exc}"
                ) from exc
            capture = item.get("capture")
            metadata_sources = item.get("metadata_sources")
            if (
                item.get("schema_version") != "archived_document_source_lineage_v1"
                or item.get("capture_status") != "checksum_capture_present"
                or item.get("synthetic_or_mock_records_counted") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or not isinstance(capture, dict)
                or not isinstance(metadata_sources, list)
                or not metadata_sources
            ):
                raise ProvenanceAuditError(
                    f"invalid archived lineage contract at line {line_number}"
                )
            for metadata_source in metadata_sources:
                if not isinstance(metadata_source, dict):
                    raise ProvenanceAuditError(
                        f"invalid archived metadata source at line {line_number}"
                    )
                database_ref = normalize_repo_path(
                    metadata_source.get("database"),
                    repo_root=repo_root,
                )
                database_sha = str(metadata_source.get("database_sha256") or "").lower()
                if database_ref is None or not SHA256_RE.fullmatch(database_sha):
                    raise ProvenanceAuditError(
                        f"invalid archived database evidence at line {line_number}"
                    )
            normalized_path = normalize_inventory_path(
                capture.get("path"),
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            content_sha256 = str(capture.get("sha256") or "").lower()
            declared_bytes = capture.get("bytes")
            source_url = str(item.get("source_url") or "").strip()
            if (
                normalized_path is None
                or "samples" in PurePosixPath(normalized_path).parts
                or not SHA256_RE.fullmatch(content_sha256)
                or not isinstance(declared_bytes, int)
                or declared_bytes < 0
                or public_url_kind(source_url) not in {"public_http", "public_https"}
            ):
                raise ProvenanceAuditError(
                    f"invalid archived capture evidence at line {line_number}"
                )
            values = (
                manifest_ref,
                "archived_document_source_lineage",
                normalized_path,
                content_sha256,
                item.get("source_id"),
                source_url,
                None,
            )
            work.execute(
                """
                INSERT OR IGNORE INTO provenance(
                  edge_key, db_ref, table_name, raw_path, normalized_path,
                  content_sha256, source_id, source_url, fetched_at,
                  declared_bytes, url_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata_edge_key(values),
                    manifest_ref,
                    "archived_document_source_lineage",
                    str(capture.get("path") or ""),
                    normalized_path,
                    content_sha256,
                    item.get("source_id"),
                    source_url,
                    None,
                    declared_bytes,
                    public_url_kind(source_url),
                ),
            )
            accepted += 1
    work.commit()
    return {
        "path": manifest_ref,
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
        "rows": rows,
        "accepted_checksum_captures": accepted,
        "status": "ok",
    }


def canonical_archive_endpoint(value: str) -> tuple[str, str, str] | None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return (
        parsed.hostname.lower().removeprefix("www."),
        parsed.path,
        parsed.query,
    )


def load_wayback_document_lineage_manifest(
    work: sqlite3.Connection,
    manifest_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    """Load official-source lineage accepted by exact Wayback byte replay."""
    if not manifest_path.is_file():
        raise ProvenanceAuditError(
            f"Wayback document lineage manifest missing: {manifest_path}"
        )
    manifest_ref = display_path(manifest_path, repo_root=repo_root)
    rows = 0
    accepted = 0
    for line_number, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        rows += 1
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProvenanceAuditError(
                f"invalid Wayback lineage JSON at line {line_number}: {exc}"
            ) from exc
        capture = item.get("capture")
        archive = item.get("archive_evidence")
        if (
            item.get("schema_version") != "wayback_document_lineage_v1"
            or item.get("capture_status") != "checksum_capture_present"
            or item.get("candidate_acceptance")
            != "accepted_only_after_archive_exact_byte_match"
            or item.get("guessed_source_urls_accepted") is not False
            or item.get("synthetic_or_mock_records_counted") is not False
            or item.get("public_domain_personal_information_retained") is not True
            or item.get("remote_mutation_performed") is not False
            or not isinstance(capture, dict)
            or not isinstance(archive, dict)
        ):
            raise ProvenanceAuditError(
                f"invalid Wayback lineage contract at line {line_number}"
            )
        normalized_path = normalize_inventory_path(
            capture.get("path"),
            repo_root=repo_root,
            inventory_root=inventory_root,
        )
        source_id = str(item.get("source_id") or "")
        source_url = str(item.get("source_url") or "").strip()
        original_url = str(archive.get("original_url") or "").strip()
        archive_url = str(archive.get("archive_url") or "").strip()
        final_url = str(archive.get("final_url") or "").strip()
        timestamp = str(archive.get("timestamp") or "")
        cdx_digest = str(archive.get("cdx_digest") or "")
        content_sha256 = str(capture.get("sha256") or "").lower()
        downloaded_sha256 = str(archive.get("downloaded_sha256") or "").lower()
        declared_bytes = capture.get("bytes")
        source_endpoint = canonical_archive_endpoint(source_url)
        original_endpoint = canonical_archive_endpoint(original_url)
        source_parsed = urlparse(source_url)
        archive_parsed = urlparse(archive_url)
        final_parsed = urlparse(final_url)
        senate_match = SENATE_VOTE_SOURCE_PATH_RE.fullmatch(source_parsed.path)
        expected_senate_path = (
            "manual/senado_votaciones_ses/"
            f"legis{senate_match.group('legislature')}/"
            f"{senate_match.group('filename')}"
            if senate_match is not None
            else None
        )
        source_contract_ok = (
            source_id == "europarl_meps"
            and source_url == EUROPARL_MEP_SOURCE_URL
            and normalized_path is not None
            and normalized_path.startswith("europarl_meps/")
        ) or (
            source_id == "senado_votaciones"
            and source_parsed.scheme == "https"
            and (source_parsed.hostname or "").lower() == "www.senado.es"
            and not source_parsed.query
            and not source_parsed.fragment
            and normalized_path == expected_senate_path
        )
        expected_archive_url = (
            f"https://web.archive.org/web/{timestamp}id_/{original_url}"
        )
        if (
            normalized_path is None
            or "samples" in PurePosixPath(normalized_path).parts
            or not source_contract_ok
            or source_endpoint is None
            or original_endpoint != source_endpoint
            or not SHA256_RE.fullmatch(content_sha256)
            or downloaded_sha256 != content_sha256
            or not isinstance(declared_bytes, int)
            or declared_bytes <= 0
            or archive.get("downloaded_bytes") != declared_bytes
            or archive.get("http_status") != 200
            or archive.get("index_endpoint") != WAYBACK_CDX_ENDPOINT
            or not re.fullmatch(r"\d{14}", timestamp)
            or not WAYBACK_CDX_DIGEST_RE.fullmatch(cdx_digest)
            or archive_url != expected_archive_url
            or archive_parsed.scheme != "https"
            or (archive_parsed.hostname or "").lower() != "web.archive.org"
            or final_parsed.scheme != "https"
            or (final_parsed.hostname or "").lower() != "web.archive.org"
        ):
            raise ProvenanceAuditError(
                f"invalid Wayback checksum evidence at line {line_number}"
            )
        inventory_row = work.execute(
            "SELECT bytes, sha256 FROM inventory WHERE path = ?",
            (normalized_path,),
        ).fetchone()
        capture_path = (inventory_root / normalized_path).resolve()
        try:
            capture_path.relative_to(inventory_root.resolve())
        except ValueError as exc:
            raise ProvenanceAuditError(
                f"Wayback capture escapes inventory at line {line_number}"
            ) from exc
        if (
            inventory_row is None
            or int(inventory_row["bytes"]) != declared_bytes
            or str(inventory_row["sha256"]) != content_sha256
            or not capture_path.is_file()
            or capture_path.stat().st_size != declared_bytes
            or sha256_file(capture_path) != content_sha256
        ):
            raise ProvenanceAuditError(
                f"Wayback capture inventory mismatch at line {line_number}"
            )
        values = (
            manifest_ref,
            "wayback_document_lineage",
            normalized_path,
            content_sha256,
            source_id,
            source_url,
            archive.get("retrieved_at"),
        )
        work.execute(
            """
            INSERT OR IGNORE INTO provenance(
              edge_key, db_ref, table_name, raw_path, normalized_path,
              content_sha256, source_id, source_url, fetched_at,
              declared_bytes, url_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata_edge_key(values),
                manifest_ref,
                "wayback_document_lineage",
                str(capture.get("path") or ""),
                normalized_path,
                content_sha256,
                source_id,
                source_url,
                archive.get("retrieved_at"),
                declared_bytes,
                public_url_kind(source_url),
            ),
        )
        accepted += 1
    work.commit()
    return {
        "path": manifest_ref,
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
        "rows": rows,
        "accepted_checksum_relations": accepted,
        "status": "ok",
    }


def load_boe_document_corpus_lineage_manifest(
    work: sqlite3.Connection,
    manifest_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise ProvenanceAuditError(
            f"BOE document corpus manifest missing: {manifest_path}"
        )
    manifest_ref = display_path(manifest_path, repo_root=repo_root)
    rows = 0
    accepted = 0
    distinct_hashes: set[str] = set()
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceAuditError(
                    f"invalid BOE corpus JSON at line {line_number}: {exc}"
                ) from exc
            capture = item.get("capture")
            boe_record = item.get("boe_record")
            summary = item.get("source_summary")
            source_url = str(item.get("source_url") or "")
            parsed = urlparse(source_url)
            boe_ids = parse_qs(parsed.query).get("id") or []
            normalized_path = normalize_inventory_path(
                capture.get("path") if isinstance(capture, dict) else None,
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            content_sha256 = str(
                capture.get("sha256") if isinstance(capture, dict) else ""
            ).lower()
            declared_bytes = (
                capture.get("bytes") if isinstance(capture, dict) else None
            )
            summary_url = str(
                summary.get("source_url") if isinstance(summary, dict) else ""
            )
            summary_sha256 = str(
                summary.get("sha256") if isinstance(summary, dict) else ""
            ).lower()
            summary_path = normalize_inventory_path(
                summary.get("path") if isinstance(summary, dict) else None,
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            summary_bytes = (
                summary.get("bytes") if isinstance(summary, dict) else None
            )
            parsed_summary = urlparse(summary_url)
            boe_ref = str(
                boe_record.get("boe_ref") if isinstance(boe_record, dict) else ""
            ).upper()
            if (
                item.get("schema_version") != "boe_document_corpus_lineage_v2"
                or item.get("capture_status") != "checksum_capture_present"
                or item.get("source_id") != "boe_document_xml"
                or item.get("synthetic_or_mock_records_counted") is not False
                or item.get("official_public_domain_personal_information_retained")
                is not True
                or item.get("remote_mutation_performed") is not False
                or not isinstance(capture, dict)
                or not isinstance(boe_record, dict)
                or not isinstance(summary, dict)
                or parsed.scheme != "https"
                or (parsed.hostname or "").lower() != "www.boe.es"
                or parsed.path != "/diario_boe/xml.php"
                or len(boe_ids) != 1
                or not re.fullmatch(
                    r"BOE-[A-Z]-\d{4}-\d+", boe_ids[0], flags=re.IGNORECASE
                )
                or boe_ref != boe_ids[0].upper()
                or not normalized_path
                or not normalized_path.startswith(
                    "text_documents/boe_document_xml/"
                )
                or not SHA256_RE.fullmatch(content_sha256)
                or not isinstance(declared_bytes, int)
                or declared_bytes <= 0
                or parsed_summary.scheme != "https"
                or (parsed_summary.hostname or "").lower() != "www.boe.es"
                or not re.fullmatch(
                    r"/datosabiertos/api/boe/sumario/\d{8}",
                    parsed_summary.path,
                )
                or not SHA256_RE.fullmatch(summary_sha256)
                or not summary_path
                or not summary_path.startswith(
                    "text_documents/boe_daily_summaries/"
                )
                or not isinstance(summary_bytes, int)
                or summary_bytes <= 0
            ):
                raise ProvenanceAuditError(
                    f"invalid BOE corpus contract at line {line_number}"
                )
            values = (
                manifest_ref,
                "boe_document_corpus_lineage",
                normalized_path,
                content_sha256,
                "boe_document_xml",
                source_url,
                item.get("fetched_at"),
            )
            work.execute(
                """
                INSERT OR IGNORE INTO provenance(
                  edge_key, db_ref, table_name, raw_path, normalized_path,
                  content_sha256, source_id, source_url, fetched_at,
                  declared_bytes, url_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata_edge_key(values),
                    manifest_ref,
                    "boe_document_corpus_lineage",
                    str(capture.get("path") or ""),
                    normalized_path,
                    content_sha256,
                    "boe_document_xml",
                    source_url,
                    item.get("fetched_at"),
                    declared_bytes,
                    public_url_kind(source_url),
                ),
            )
            accepted += 1
            distinct_hashes.add(content_sha256)
            summary_values = (
                manifest_ref,
                "boe_document_corpus_summary_lineage",
                summary_path,
                summary_sha256,
                "boe_daily_summaries",
                summary_url,
                summary.get("fetched_at"),
            )
            work.execute(
                """
                INSERT OR IGNORE INTO provenance(
                  edge_key, db_ref, table_name, raw_path, normalized_path,
                  content_sha256, source_id, source_url, fetched_at,
                  declared_bytes, url_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata_edge_key(summary_values),
                    manifest_ref,
                    "boe_document_corpus_summary_lineage",
                    str(summary.get("path") or ""),
                    summary_path,
                    summary_sha256,
                    "boe_daily_summaries",
                    summary_url,
                    summary.get("fetched_at"),
                    summary_bytes,
                    public_url_kind(summary_url),
                ),
            )
    work.commit()
    return {
        "path": manifest_ref,
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
        "rows": rows,
        "accepted_checksum_captures": accepted,
        "distinct_content_objects": len(distinct_hashes),
        "status": "ok",
    }


def load_captured_link_document_lineage_manifest(
    work: sqlite3.Connection,
    manifest_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    """Load exact links whose live official bytes match preserved captures."""
    if not manifest_path.is_file():
        raise ProvenanceAuditError(
            f"captured-link document lineage manifest missing: {manifest_path}"
        )
    manifest_ref = display_path(manifest_path, repo_root=repo_root)
    rows = 0
    accepted = 0
    evidence_files: set[str] = set()
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceAuditError(
                    f"invalid captured-link lineage JSON at line {line_number}: {exc}"
                ) from exc
            capture = item.get("capture")
            evidence = item.get("embedded_link_evidence")
            verification = item.get("retrieval_verification")
            if (
                item.get("schema_version") != "captured_link_document_lineage_v1"
                or item.get("capture_status") != "checksum_capture_present"
                or item.get("synthetic_or_mock_records_counted") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or item.get("remote_mutation_performed") is not False
                or not isinstance(capture, dict)
                or not isinstance(evidence, dict)
                or not isinstance(verification, dict)
            ):
                raise ProvenanceAuditError(
                    f"invalid captured-link lineage contract at line {line_number}"
                )
            normalized_path = normalize_inventory_path(
                capture.get("path"),
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            evidence_path = normalize_inventory_path(
                evidence.get("capture_path"),
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            content_sha256 = str(capture.get("sha256") or "").lower()
            evidence_sha256 = str(evidence.get("capture_sha256") or "").lower()
            declared_bytes = capture.get("bytes")
            source_url = str(item.get("source_url") or "").strip()
            page_url = str(evidence.get("capture_page_url") or "").strip()
            raw_href = str(evidence.get("raw_href") or "")
            embedded_source_url = str(evidence.get("embedded_source_url") or "").strip()
            retrieval_url = str(evidence.get("retrieval_url") or "").strip()
            final_url = str(verification.get("final_url") or "").strip()
            downloaded_sha256 = str(verification.get("downloaded_sha256") or "").lower()
            if (
                normalized_path is None
                or evidence_path is None
                or "samples" in PurePosixPath(normalized_path).parts
                or "samples" in PurePosixPath(evidence_path).parts
                or not SHA256_RE.fullmatch(content_sha256)
                or not SHA256_RE.fullmatch(evidence_sha256)
                or not isinstance(declared_bytes, int)
                or declared_bytes <= 0
                or not is_official_parliament_document_url(source_url)
                or not is_official_parliament_document_url(final_url)
                or source_url != retrieval_url
                or verification.get("requested_url") != source_url
                or verification.get("method") != "official_http_get_sha256_match"
                or verification.get("http_status") != 200
                or verification.get("downloaded_bytes") != declared_bytes
                or downloaded_sha256 != content_sha256
            ):
                raise ProvenanceAuditError(
                    f"invalid captured-link checksum evidence at line {line_number}"
                )
            inventory_row = work.execute(
                """
                SELECT bytes, sha256 FROM inventory
                WHERE path = ?
                """,
                (normalized_path,),
            ).fetchone()
            evidence_inventory_row = work.execute(
                """
                SELECT bytes, sha256 FROM inventory
                WHERE path = ?
                """,
                (evidence_path,),
            ).fetchone()
            if (
                inventory_row is None
                or int(inventory_row["bytes"]) != declared_bytes
                or str(inventory_row["sha256"]) != content_sha256
                or evidence_inventory_row is None
                or str(evidence_inventory_row["sha256"]) != evidence_sha256
            ):
                raise ProvenanceAuditError(
                    f"captured-link inventory mismatch at line {line_number}"
                )
            evidence_capture_path = (inventory_root / evidence_path).resolve()
            try:
                evidence_capture_path.relative_to(inventory_root.resolve())
            except ValueError as exc:
                raise ProvenanceAuditError(
                    f"captured-link evidence escapes inventory at line {line_number}"
                ) from exc
            if (
                not evidence_capture_path.is_file()
                or sha256_file(evidence_capture_path) != evidence_sha256
            ):
                raise ProvenanceAuditError(
                    f"captured-link evidence checksum mismatch at line {line_number}"
                )
            payload, read_status = read_embedded_metadata_text(evidence_capture_path)
            if payload is None or read_status.endswith("_truncated"):
                raise ProvenanceAuditError(
                    f"captured-link evidence unreadable at line {line_number}"
                )
            if page_url not in extract_official_senate_capture_urls(payload):
                raise ProvenanceAuditError(
                    f"captured-link page URL absent from evidence at line {line_number}"
                )
            exact_hrefs = {
                html.unescape(value).strip() for value in HTML_HREF_RE.findall(payload)
            }
            expected_embedded_url = urljoin(page_url, raw_href)
            expected_retrieval_url, _fragment = urldefrag(expected_embedded_url)
            if (
                raw_href not in exact_hrefs
                or embedded_source_url != expected_embedded_url
                or retrieval_url != expected_retrieval_url
            ):
                raise ProvenanceAuditError(
                    f"captured-link relation absent from evidence at line {line_number}"
                )
            values = (
                manifest_ref,
                "captured_link_document_lineage",
                normalized_path,
                content_sha256,
                item.get("source_id"),
                source_url,
                verification.get("verified_at"),
            )
            work.execute(
                """
                INSERT OR IGNORE INTO provenance(
                  edge_key, db_ref, table_name, raw_path, normalized_path,
                  content_sha256, source_id, source_url, fetched_at,
                  declared_bytes, url_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata_edge_key(values),
                    manifest_ref,
                    "captured_link_document_lineage",
                    str(capture.get("path") or ""),
                    normalized_path,
                    content_sha256,
                    item.get("source_id"),
                    source_url,
                    verification.get("verified_at"),
                    declared_bytes,
                    public_url_kind(source_url),
                ),
            )
            accepted += 1
            evidence_files.add(evidence_path)
    work.commit()
    return {
        "path": manifest_ref,
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
        "rows": rows,
        "accepted_checksum_relations": accepted,
        "distinct_evidence_files": len(evidence_files),
        "status": "ok",
    }


def load_official_document_identifier_lineage_manifest(
    work: sqlite3.Connection,
    manifest_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    """Load official diary URLs proven by live byte-for-byte capture matches."""
    if not manifest_path.is_file():
        raise ProvenanceAuditError(
            f"official document identifier lineage manifest missing: {manifest_path}"
        )
    manifest_ref = display_path(manifest_path, repo_root=repo_root)
    rows = 0
    accepted = 0
    embedded_identifiers = 0
    exact_download_only = 0
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceAuditError(
                    "invalid official identifier lineage JSON at line "
                    f"{line_number}: {exc}"
                ) from exc
            capture = item.get("capture")
            evidence = item.get("identifier_evidence")
            verification = item.get("retrieval_verification")
            if (
                item.get("schema_version") != "official_document_identifier_lineage_v1"
                or item.get("capture_status") != "checksum_capture_present"
                or item.get("source_id") != "parl_initiative_docs"
                or item.get("candidate_acceptance")
                != "accepted_only_after_live_exact_byte_match"
                or item.get("guessed_source_urls_accepted") is not False
                or item.get("synthetic_or_mock_records_counted") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or item.get("remote_mutation_performed") is not False
                or not isinstance(capture, dict)
                or not isinstance(evidence, dict)
                or not isinstance(verification, dict)
            ):
                raise ProvenanceAuditError(
                    f"invalid official identifier contract at line {line_number}"
                )
            normalized_path = normalize_inventory_path(
                capture.get("path"),
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            content_sha256 = str(capture.get("sha256") or "").lower()
            declared_bytes = capture.get("bytes")
            source_url = str(item.get("source_url") or "").strip()
            final_url = str(verification.get("final_url") or "").strip()
            expected_identifier = str(evidence.get("expected_identifier") or "").upper()
            declared_internal_identifiers = evidence.get("internal_identifiers")
            evidence_status = str(evidence.get("status") or "")
            content_type = str(verification.get("content_type") or "")
            downloaded_sha256 = str(verification.get("downloaded_sha256") or "").lower()
            if (
                normalized_path is None
                or "samples" in PurePosixPath(normalized_path).parts
                or not SHA256_RE.fullmatch(content_sha256)
                or not isinstance(declared_bytes, int)
                or declared_bytes <= 0
                or not isinstance(declared_internal_identifiers, list)
                or any(
                    not isinstance(value, str)
                    for value in declared_internal_identifiers
                )
                or official_senate_diary_identifier(source_url) != expected_identifier
                or official_senate_diary_identifier(final_url) != expected_identifier
                or verification.get("requested_url") != source_url
                or verification.get("method") != "official_http_get_sha256_match"
                or verification.get("http_status") != 200
                or content_type.partition(";")[0].strip().lower() != "application/pdf"
                or verification.get("downloaded_bytes") != declared_bytes
                or downloaded_sha256 != content_sha256
            ):
                raise ProvenanceAuditError(
                    "invalid official identifier checksum evidence at line "
                    f"{line_number}"
                )
            inventory_row = work.execute(
                "SELECT bytes, sha256 FROM inventory WHERE path = ?",
                (normalized_path,),
            ).fetchone()
            capture_path = (inventory_root / normalized_path).resolve()
            try:
                capture_path.relative_to(inventory_root.resolve())
            except ValueError as exc:
                raise ProvenanceAuditError(
                    f"official identifier capture escapes inventory at line {line_number}"
                ) from exc
            if (
                inventory_row is None
                or int(inventory_row["bytes"]) != declared_bytes
                or str(inventory_row["sha256"]) != content_sha256
                or not capture_path.is_file()
                or capture_path.stat().st_size != declared_bytes
                or sha256_file(capture_path) != content_sha256
            ):
                raise ProvenanceAuditError(
                    f"official identifier inventory mismatch at line {line_number}"
                )
            with capture_path.open("rb") as capture_handle:
                if capture_handle.read(5) != b"%PDF-":
                    raise ProvenanceAuditError(
                        f"official identifier capture is not PDF at line {line_number}"
                    )
                capture_handle.seek(0)
                actual_internal_identifiers = sorted(
                    {
                        value.decode("ascii").upper()
                        for value in SENATE_DIARY_INTERNAL_IDENTIFIER_RE.findall(
                            capture_handle.read()
                        )
                    }
                )
            if actual_internal_identifiers != sorted(declared_internal_identifiers):
                raise ProvenanceAuditError(
                    f"official identifier byte evidence mismatch at line {line_number}"
                )
            if actual_internal_identifiers:
                if (
                    expected_identifier not in actual_internal_identifiers
                    or evidence_status != "embedded_identifier_and_exact_download_match"
                ):
                    raise ProvenanceAuditError(
                        f"official embedded identifier mismatch at line {line_number}"
                    )
                embedded_identifiers += 1
            else:
                if (
                    evidence_status
                    != "exact_download_match_without_embedded_identifier"
                ):
                    raise ProvenanceAuditError(
                        f"invalid exact-download-only evidence at line {line_number}"
                    )
                exact_download_only += 1
            values = (
                manifest_ref,
                "official_document_identifier_lineage",
                normalized_path,
                content_sha256,
                item.get("source_id"),
                source_url,
                verification.get("verified_at"),
            )
            work.execute(
                """
                INSERT OR IGNORE INTO provenance(
                  edge_key, db_ref, table_name, raw_path, normalized_path,
                  content_sha256, source_id, source_url, fetched_at,
                  declared_bytes, url_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata_edge_key(values),
                    manifest_ref,
                    "official_document_identifier_lineage",
                    str(capture.get("path") or ""),
                    normalized_path,
                    content_sha256,
                    item.get("source_id"),
                    source_url,
                    verification.get("verified_at"),
                    declared_bytes,
                    public_url_kind(source_url),
                ),
            )
            accepted += 1
    work.commit()
    return {
        "path": manifest_ref,
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
        "rows": rows,
        "accepted_checksum_relations": accepted,
        "relations_with_embedded_identifier": embedded_identifiers,
        "relations_with_exact_download_match_only": exact_download_only,
        "status": "ok",
    }


def load_official_path_document_lineage_manifest(
    work: sqlite3.Connection,
    manifest_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    """Load path-projected official URLs accepted only by exact live byte match."""
    if not manifest_path.is_file():
        raise ProvenanceAuditError(
            f"official path document lineage manifest missing: {manifest_path}"
        )
    manifest_ref = display_path(manifest_path, repo_root=repo_root)
    rows = 0
    accepted = 0
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceAuditError(
                    f"invalid official path lineage JSON at line {line_number}: {exc}"
                ) from exc
            capture = item.get("capture")
            relation = item.get("path_relation")
            verification = item.get("retrieval_verification")
            if (
                item.get("schema_version") != "official_path_document_lineage_v1"
                or item.get("capture_status") != "checksum_capture_present"
                or item.get("source_id") != "senado_votaciones"
                or item.get("candidate_acceptance")
                != "accepted_only_after_live_exact_byte_match"
                or item.get("guessed_source_urls_accepted") is not False
                or item.get("synthetic_or_mock_records_counted") is not False
                or item.get("public_domain_personal_information_retained") is not True
                or item.get("remote_mutation_performed") is not False
                or not isinstance(capture, dict)
                or not isinstance(relation, dict)
                or not isinstance(verification, dict)
            ):
                raise ProvenanceAuditError(
                    f"invalid official path lineage contract at line {line_number}"
                )
            normalized_path = normalize_inventory_path(
                capture.get("path"),
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            content_sha256 = str(capture.get("sha256") or "").lower()
            declared_bytes = capture.get("bytes")
            source_url = str(item.get("source_url") or "").strip()
            parsed = urlparse(source_url)
            source_match = SENATE_VOTE_SOURCE_PATH_RE.fullmatch(parsed.path)
            final_url = str(verification.get("final_url") or "").strip()
            content_type = str(verification.get("content_type") or "")
            downloaded_sha256 = str(verification.get("downloaded_sha256") or "").lower()
            expected_path = (
                "manual/senado_votaciones_ses/"
                f"legis{source_match.group('legislature')}/"
                f"{source_match.group('filename')}"
                if source_match is not None
                else None
            )
            if (
                parsed.scheme != "https"
                or (parsed.hostname or "").lower() != "www.senado.es"
                or parsed.query
                or parsed.fragment
                or source_match is None
                or normalized_path != expected_path
                or relation.get("method") != "exact_repository_path_projection"
                or relation.get("capture_path") != normalized_path
                or relation.get("projected_source_url") != source_url
                or not SHA256_RE.fullmatch(content_sha256)
                or not isinstance(declared_bytes, int)
                or declared_bytes <= 0
                or verification.get("requested_url") != source_url
                or final_url != source_url
                or verification.get("method") != "official_http_get_sha256_match"
                or verification.get("http_status") != 200
                or content_type.partition(";")[0].strip().lower()
                not in {"application/xml", "text/xml", "application/octet-stream"}
                or verification.get("downloaded_bytes") != declared_bytes
                or downloaded_sha256 != content_sha256
            ):
                raise ProvenanceAuditError(
                    f"invalid official path checksum evidence at line {line_number}"
                )
            inventory_row = work.execute(
                "SELECT bytes, sha256 FROM inventory WHERE path = ?",
                (normalized_path,),
            ).fetchone()
            capture_path = (inventory_root / normalized_path).resolve()
            try:
                capture_path.relative_to(inventory_root.resolve())
            except ValueError as exc:
                raise ProvenanceAuditError(
                    f"official path capture escapes inventory at line {line_number}"
                ) from exc
            if (
                inventory_row is None
                or int(inventory_row["bytes"]) != declared_bytes
                or str(inventory_row["sha256"]) != content_sha256
                or not capture_path.is_file()
                or capture_path.stat().st_size != declared_bytes
                or sha256_file(capture_path) != content_sha256
            ):
                raise ProvenanceAuditError(
                    f"official path inventory mismatch at line {line_number}"
                )
            with capture_path.open("rb") as capture_handle:
                if not capture_handle.read(256).lstrip().startswith(b"<?xml"):
                    raise ProvenanceAuditError(
                        f"official path capture is not XML at line {line_number}"
                    )
            values = (
                manifest_ref,
                "official_path_document_lineage",
                normalized_path,
                content_sha256,
                item.get("source_id"),
                source_url,
                verification.get("verified_at"),
            )
            work.execute(
                """
                INSERT OR IGNORE INTO provenance(
                  edge_key, db_ref, table_name, raw_path, normalized_path,
                  content_sha256, source_id, source_url, fetched_at,
                  declared_bytes, url_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata_edge_key(values),
                    manifest_ref,
                    "official_path_document_lineage",
                    str(capture.get("path") or ""),
                    normalized_path,
                    content_sha256,
                    item.get("source_id"),
                    source_url,
                    verification.get("verified_at"),
                    declared_bytes,
                    public_url_kind(source_url),
                ),
            )
            accepted += 1
    work.commit()
    return {
        "path": manifest_ref,
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
        "rows": rows,
        "accepted_checksum_relations": accepted,
        "status": "ok",
    }


def iter_json_objects(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_objects(child)


def is_official_jec_document_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == "www.juntaelectoralcentral.es"
        and parsed.path.startswith("/cs/jec/documentos/")
        and parsed.path.lower().endswith(".pdf")
    )


def andalucia_initiative_slug(value: str) -> str | None:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "www.parlamentodeandalucia.es"
        or parsed.path
        != "/webdinamica/portal-web-parlamento/actividadparlamentaria/"
        "todaslasiniciativas/portipo.do"
    ):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    numexp = query.get("numexp", [])
    if (
        len(numexp) != 1
        or re.fullmatch(r"12-\d{2}/[A-Z]+-\d{6}", numexp[0]) is None
        or query.get("legislatura") != ["12"]
    ):
        return None
    return re.sub(r"[^a-z0-9]+", "-", numexp[0].lower()).strip("-")


def andalucia_vote_document_id(value: str) -> str | None:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "www.parlamentodeandalucia.es"
        or parsed.path != "/webdinamica/portal-web-parlamento/pdf.do"
    ):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    identifiers = query.get("id", [])
    if query.get("tipodoc") != ["diario"] or len(identifiers) != 1:
        return None
    return identifiers[0] if identifiers[0].isdigit() else None


def is_official_andalucia_index_url(value: str) -> bool:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "www.parlamentodeandalucia.es"
    ):
        return False
    if parsed.path == (
        "/webdinamica/portal-web-parlamento/composicionyfuncionamiento/"
        "resultadosvotaciones.do"
    ):
        return True
    if parsed.path != (
        "/webdinamica/portal-web-parlamento/actividadparlamentaria/"
        "todaslasiniciativas/portipo.do"
    ):
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    return "numexp" not in query and query.get("legislatura") == ["12"]


def andalucia_program_capture_method(
    item: dict[str, Any],
    *,
    repo_root: Path,
    inventory_root: Path,
) -> str | None:
    normalized_path = normalize_inventory_path(
        item.get("raw_path"),
        repo_root=repo_root,
        inventory_root=inventory_root,
    )
    path_match = ANDALUCIA_PROGRAM_PATH_RE.fullmatch(normalized_path or "")
    source_id = str(item.get("source_id") or "")
    officiality = str(item.get("officiality") or "")
    url = str(item.get("url") or "")
    parsed = urlparse(url)
    allowed_hosts = ANDALUCIA_PROGRAM_CAPTURE_HOSTS.get(officiality, set())
    if (
        path_match is None
        or path_match.group("source_id") != source_id
        or item.get("status") not in {"cached", "ok"}
        or item.get("verification_status") != "verified_by_text"
        or item.get("format") != "pdf"
        or not SHA256_RE.fullmatch(str(item.get("content_sha256") or "").lower())
        or not isinstance(item.get("bytes"), int)
        or int(item["bytes"]) < 1
        or parsed.scheme != "https"
        or (parsed.hostname or "").lower() not in allowed_hosts
        or not parsed.path.lower().endswith(".pdf")
    ):
        return None
    return f"published_andalucia_program_{officiality}_capture"


def add_published_capture_edge(
    work: sqlite3.Connection,
    *,
    index_ref: str,
    inventory_root: Path,
    repo_root: Path,
    raw_path: Any,
    source_url: Any,
    source_id: str,
    method: str,
    declared_sha256: Any = None,
    declared_bytes: Any = None,
) -> str:
    normalized_path = normalize_inventory_path(
        raw_path,
        repo_root=repo_root,
        inventory_root=inventory_root,
    )
    url = str(source_url or "").strip()
    if normalized_path is None or public_url_kind(url) not in {
        "public_http",
        "public_https",
    }:
        raise ProvenanceAuditError(
            f"invalid published capture edge in {index_ref}: {raw_path!r}"
        )
    inventory = work.execute(
        "SELECT bytes, sha256 FROM inventory WHERE path = ?",
        (normalized_path,),
    ).fetchone()
    if inventory is None:
        return "not_in_inventory"
    content_sha256 = str(declared_sha256 or inventory["sha256"]).lower()
    if not SHA256_RE.fullmatch(content_sha256):
        raise ProvenanceAuditError(
            f"invalid published capture SHA-256 in {index_ref}: {normalized_path}"
        )
    if declared_bytes is None:
        edge_bytes = int(inventory["bytes"])
    elif isinstance(declared_bytes, int) and declared_bytes >= 0:
        edge_bytes = declared_bytes
    else:
        raise ProvenanceAuditError(
            f"invalid published capture byte count in {index_ref}: {normalized_path}"
        )
    values = (
        index_ref,
        method,
        normalized_path,
        content_sha256,
        source_id,
        url,
        None,
    )
    cursor = work.execute(
        """
        INSERT OR IGNORE INTO provenance(
          edge_key, db_ref, table_name, raw_path, normalized_path,
          content_sha256, source_id, source_url, fetched_at,
          declared_bytes, url_kind
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metadata_edge_key(values),
            index_ref,
            method,
            str(raw_path or ""),
            normalized_path,
            content_sha256,
            source_id,
            url,
            None,
            edge_bytes,
            public_url_kind(url),
        ),
    )
    return "accepted" if cursor.rowcount else "duplicate"


def load_published_capture_index(
    work: sqlite3.Connection,
    index_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    """Load exact public URL/path relations already emitted by real ETL runs."""
    index_ref = display_path(index_path, repo_root=repo_root)
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProvenanceAuditError(
            f"invalid published capture index {index_ref}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProvenanceAuditError(
            f"published capture index root must be an object: {index_ref}"
        )
    schema_version = str(payload.get("schema_version") or "")
    candidates: set[tuple[str, str, str, str, str | None, int | None]] = set()

    if schema_version == "election-calendar.v1":
        for item in payload.get("scraped_sources") or []:
            if not isinstance(item, dict) or not is_official_jec_document_url(
                str(item.get("url") or "")
            ):
                continue
            candidates.add(
                (
                    str(item.get("raw_path") or ""),
                    str(item.get("url") or ""),
                    str(item.get("source_id") or "official_election_calendar"),
                    "published_election_calendar_capture",
                    str(item.get("content_sha256") or "") or None,
                    item.get("bytes") if isinstance(item.get("bytes"), int) else None,
                )
            )
    elif schema_version == "andalucia_2026_accountability_snapshot_v1":
        for item in payload.get("sources") or []:
            if not isinstance(item, dict) or not is_official_jec_document_url(
                str(item.get("url") or "")
            ):
                continue
            candidates.add(
                (
                    str(item.get("raw_path") or ""),
                    str(item.get("url") or ""),
                    str(item.get("source_id") or "official_election_candidates"),
                    "published_election_candidate_capture",
                    str(item.get("content_sha256") or "") or None,
                    item.get("bytes") if isinstance(item.get("bytes"), int) else None,
                )
            )
        program_sources = payload.get("program_sources") or {}
        if not isinstance(program_sources, dict) or not isinstance(
            program_sources.get("by_party"), dict
        ):
            raise ProvenanceAuditError(
                f"invalid program_sources in published capture index: {index_ref}"
            )
        for party_items in program_sources["by_party"].values():
            if not isinstance(party_items, list):
                raise ProvenanceAuditError(
                    f"invalid program source group in published capture index: {index_ref}"
                )
            for item in party_items:
                if not isinstance(item, dict):
                    continue
                method = andalucia_program_capture_method(
                    item,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                if method is None:
                    continue
                candidates.add(
                    (
                        str(item.get("raw_path") or ""),
                        str(item.get("url") or ""),
                        str(item.get("source_id") or ""),
                        method,
                        str(item.get("content_sha256") or ""),
                        item.get("bytes"),
                    )
                )
        parliament = payload.get("parliament_activity") or {}
        if not isinstance(parliament, dict):
            raise ProvenanceAuditError(
                f"invalid parliament_activity in published capture index: {index_ref}"
            )
        raw_dir = normalize_inventory_path(
            parliament.get("raw_dir"),
            repo_root=repo_root,
            inventory_root=inventory_root,
        )
        expected_raw_dir = "elections/andalucia_2026/parlamento_andalucia"
        if raw_dir != expected_raw_dir:
            raise ProvenanceAuditError(
                f"unexpected Andalucia raw_dir in published capture index: {raw_dir!r}"
            )
        roots = (
            (
                "initiatives_url",
                "initiatives_status",
                f"{raw_dir}/legislative_initiatives_leg12.html",
                "published_andalucia_initiative_index_capture",
            ),
            (
                "voting_results_url",
                "voting_results_status",
                f"{raw_dir}/voting_results.html",
                "published_andalucia_vote_index_capture",
            ),
        )
        for url_key, status_key, raw_path, method in roots:
            source_url = str(parliament.get(url_key) or "")
            if parliament.get(status_key) in {"ok", "cached"}:
                if not is_official_andalucia_index_url(source_url):
                    raise ProvenanceAuditError(
                        f"invalid official Andalucia index URL in {index_ref}"
                    )
                candidates.add(
                    (raw_path, source_url, "parlamento_andalucia", method, None, None)
                )
        for item in parliament.get("legislative_initiatives") or []:
            if not isinstance(item, dict):
                continue
            source_url = str(item.get("source_url") or "")
            slug = andalucia_initiative_slug(source_url)
            if slug is None:
                continue
            initiative_raw_path = f"{raw_dir}/initiative_details/{slug}.html"
            candidates.add(
                (
                    initiative_raw_path,
                    source_url,
                    str(item.get("source_id") or "parlamento_andalucia"),
                    "published_andalucia_initiative_capture",
                    None,
                    None,
                )
            )
            initiative_capture = (inventory_root / initiative_raw_path).resolve()
            try:
                initiative_capture.relative_to(inventory_root.resolve())
            except ValueError as exc:
                raise ProvenanceAuditError(
                    f"Andalucia initiative capture escapes inventory root: {initiative_raw_path}"
                ) from exc
            payload, _read_status = read_embedded_metadata_text(initiative_capture)
            if payload is None:
                continue
            for raw_href in HTML_HREF_RE.findall(payload):
                vote_url = urljoin(source_url, html.unescape(raw_href).strip())
                document_id = andalucia_vote_document_id(vote_url)
                if document_id is None:
                    continue
                vote_raw_path = (
                    f"{raw_dir}/vote_pdfs/parlamento-andalucia-votacion-https-www-"
                    "parlamentodeandalucia-es-webdinamica-portal-web-parlamento-pdf-do-"
                    f"tipodoc-diario-id-{document_id}.pdf"
                )
                candidates.add(
                    (
                        vote_raw_path,
                        vote_url,
                        "parlamento_andalucia_votaciones",
                        "published_andalucia_initiative_embedded_vote_document_capture",
                        None,
                        None,
                    )
                )
        for item in iter_json_objects(parliament):
            source_url = str(item.get("source_url") or "")
            document_id = andalucia_vote_document_id(source_url)
            if document_id is None:
                continue
            raw_path = (
                f"{raw_dir}/vote_pdfs/parlamento-andalucia-votacion-https-www-"
                "parlamentodeandalucia-es-webdinamica-portal-web-parlamento-pdf-do-"
                f"tipodoc-diario-id-{document_id}.pdf"
            )
            candidates.add(
                (
                    raw_path,
                    source_url,
                    "parlamento_andalucia_votaciones",
                    "published_andalucia_vote_document_capture",
                    None,
                    None,
                )
            )
    else:
        raise ProvenanceAuditError(
            f"unsupported published capture index schema {schema_version!r}: {index_ref}"
        )

    counts: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    for (
        raw_path,
        source_url,
        source_id,
        method,
        declared_sha256,
        declared_bytes,
    ) in sorted(
        candidates,
        key=lambda item: item[:4],
    ):
        result = add_published_capture_edge(
            work,
            index_ref=index_ref,
            inventory_root=inventory_root,
            repo_root=repo_root,
            raw_path=raw_path,
            source_url=source_url,
            source_id=source_id,
            method=method,
            declared_sha256=declared_sha256,
            declared_bytes=declared_bytes,
        )
        counts[result] += 1
        if result == "accepted":
            methods[method] += 1
    work.commit()
    return {
        "path": index_ref,
        "bytes": index_path.stat().st_size,
        "sha256": sha256_file(index_path),
        "schema_version": schema_version,
        "candidate_relations": len(candidates),
        **dict(sorted(counts.items())),
        "accepted_by_method": dict(sorted(methods.items())),
        "status": "ok",
    }


def load_embedded_official_urls(
    work: sqlite3.Connection,
    *,
    inventory_root: Path,
) -> dict[str, Any]:
    """Recover exact official or primary self-links embedded in known captures."""
    scanned = 0
    linked = 0
    already_linked = 0
    missing = 0
    ambiguous = 0
    capture_read_statuses: Counter[str] = Counter()
    methods: dict[str, Counter[str]] = defaultdict(Counter)
    missing_samples: list[str] = []
    ambiguous_samples: list[str] = []
    moncloa_feed_index, moncloa_feed_index_counts = load_moncloa_feed_index_relations(
        work,
        inventory_root=inventory_root,
    )
    source_groups = {
        *PLACSP_EMBEDDED_URL_SOURCE_GROUPS,
        CONGRESS_INTERVENTION_SOURCE_GROUP,
        SENATE_INITIATIVE_SOURCE_GROUP,
        MANUAL_SOURCE_GROUP,
        MONCLOA_SOURCE_GROUP,
        MONCLOA_RSS_SOURCE_GROUP,
        PARTY_PROGRAM_SOURCE_GROUP,
    }
    placeholders = ",".join("?" for _ in source_groups)
    query = f"""
    SELECT file_id, path, source_group, extension, bytes, sha256
    FROM inventory
    WHERE source_group IN ({placeholders})
      AND (
        extension = 'html'
        OR (
          extension = 'xml'
          AND (
            source_group IN (?, ?)
            OR path LIKE 'manual/moncloa_exec/%'
            OR path LIKE 'manual/senado_votaciones_ses/%'
          )
        )
      )
    ORDER BY file_id
    """
    query_parameters = [
        *sorted(source_groups),
        MONCLOA_SOURCE_GROUP,
        MONCLOA_RSS_SOURCE_GROUP,
    ]
    for row in work.execute(query, query_parameters):
        scanned += 1
        relative_path = str(row["path"])
        source_group = str(row["source_group"])
        if source_group in PLACSP_EMBEDDED_URL_SOURCE_GROUPS:
            method = "exact_official_hiperenlaceId_self_link"
        elif source_group == CONGRESS_INTERVENTION_SOURCE_GROUP:
            method = "exact_official_congress_liferay_current_url"
        elif source_group == SENATE_INITIATIVE_SOURCE_GROUP:
            method = "exact_official_senate_embedded_identifier"
        elif source_group == PARTY_PROGRAM_SOURCE_GROUP:
            method = "exact_primary_party_canonical_url"
        elif relative_path.startswith("manual/senado_votaciones_ses/"):
            method = "exact_official_senate_vote_embedded_self_url"
        elif str(row["extension"]) == "xml":
            method = "exact_official_moncloa_embedded_index_or_feed_relation"
        elif source_group == MANUAL_SOURCE_GROUP:
            method = "exact_official_manual_embedded_identifier_or_self_link"
        else:
            method = "exact_official_canonical_or_og_url"
        methods[method]["scanned"] += 1
        has_verified_match = bool(
            work.execute(
                """
                SELECT EXISTS(
                  SELECT 1 FROM matches
                  WHERE file_id = ?
                    AND match_basis IN ('path_checksum', 'content_checksum')
                )
                """,
                (row["file_id"],),
            ).fetchone()[0]
        )
        if has_verified_match:
            already_linked += 1
            methods[method]["already_linked"] += 1
            continue
        capture_path = (inventory_root / relative_path).resolve()
        try:
            capture_path.relative_to(inventory_root.resolve())
        except ValueError as exc:
            raise ProvenanceAuditError(
                f"embedded URL capture escapes inventory root: {relative_path}"
            ) from exc
        payload, capture_read_status = read_embedded_metadata_text(capture_path)
        capture_read_statuses[capture_read_status] += 1
        if payload is None:
            missing += 1
            methods[method][capture_read_status] += 1
            if len(missing_samples) < 20:
                missing_samples.append(relative_path)
            continue
        if source_group in PLACSP_EMBEDDED_URL_SOURCE_GROUPS:
            source_urls = {
                html.unescape(value).strip()
                for value in PLACSP_SELF_LINK_RE.findall(payload)
            }
        elif source_group == CONGRESS_INTERVENTION_SOURCE_GROUP:
            source_urls = extract_official_congress_current_urls(payload)
        elif source_group == SENATE_INITIATIVE_SOURCE_GROUP:
            source_urls = extract_official_senate_capture_urls(payload)
        elif relative_path.startswith("manual/senado_votaciones_ses/"):
            source_urls = extract_official_senate_vote_self_urls(
                payload,
                relative_path=relative_path,
            )
        elif str(row["extension"]) == "xml":
            source_urls = (
                extract_official_manual_capture_urls(payload)
                if source_group == MANUAL_SOURCE_GROUP
                else set()
            )
            if not source_urls:
                channel_title = extract_moncloa_rss_channel_title(payload)
                source_urls = (
                    set(moncloa_feed_index.get(channel_title, set()))
                    if channel_title is not None
                    else set()
                )
        elif source_group == MANUAL_SOURCE_GROUP:
            source_urls = extract_official_manual_capture_urls(payload)
        else:
            source_urls = {
                html.unescape(value).strip()
                for pattern in SELF_URL_LINK_RES
                for value in pattern.findall(payload)
                if is_allowed_self_url(
                    source_group,
                    html.unescape(value).strip(),
                )
            }
        if not source_urls:
            missing += 1
            methods[method]["missing_self_link"] += 1
            if len(missing_samples) < 20:
                missing_samples.append(relative_path)
            continue
        if len(source_urls) != 1:
            ambiguous += 1
            methods[method]["ambiguous_self_link"] += 1
            if len(ambiguous_samples) < 20:
                ambiguous_samples.append(relative_path)
            continue
        source_url = next(iter(source_urls))
        if public_url_kind(source_url) not in {"public_http", "public_https"}:
            missing += 1
            if len(missing_samples) < 20:
                missing_samples.append(relative_path)
            continue
        values = (
            "embedded:inventory_file",
            "embedded_official_url",
            relative_path,
            row["sha256"],
            row["source_group"],
            source_url,
            None,
        )
        work.execute(
            """
            INSERT OR IGNORE INTO provenance(
              edge_key, db_ref, table_name, raw_path, normalized_path,
              content_sha256, source_id, source_url, fetched_at,
              declared_bytes, url_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata_edge_key(values),
                "embedded:inventory_file",
                "embedded_official_url",
                relative_path,
                relative_path,
                row["sha256"],
                row["source_group"],
                source_url,
                None,
                row["bytes"],
                public_url_kind(source_url),
            ),
        )
        linked += 1
        methods[method]["linked"] += 1
    work.commit()
    return {
        "scanned": scanned,
        "linked": linked,
        "already_checksum_linked": already_linked,
        "missing_self_link": missing,
        "ambiguous_self_link": ambiguous,
        "missing_samples": missing_samples,
        "ambiguous_samples": ambiguous_samples,
        "capture_read_statuses": dict(sorted(capture_read_statuses.items())),
        "source_groups": sorted(source_groups),
        "moncloa_feed_index": moncloa_feed_index_counts,
        "methods": {
            key: dict(sorted(value.items())) for key, value in sorted(methods.items())
        },
    }


def read_embedded_metadata_text(capture_path: Path) -> tuple[str | None, str]:
    """Read bounded HTML metadata, including gzip bytes stored under .html names."""
    try:
        with capture_path.open("rb") as raw_handle:
            magic = raw_handle.read(2)
            raw_handle.seek(0)
            if magic == b"\x1f\x8b":
                with gzip.GzipFile(fileobj=raw_handle) as decoded_handle:
                    payload = decoded_handle.read(
                        EMBEDDED_METADATA_READ_LIMIT_BYTES + 1
                    )
                kind = "gzip"
            else:
                payload = raw_handle.read(EMBEDDED_METADATA_READ_LIMIT_BYTES + 1)
                kind = "plain"
    except (EOFError, OSError):
        return None, "capture_read_error"
    truncated = len(payload) > EMBEDDED_METADATA_READ_LIMIT_BYTES
    payload = payload[:EMBEDDED_METADATA_READ_LIMIT_BYTES]
    status = f"{kind}_truncated" if truncated else kind
    return payload.decode("utf-8", errors="ignore"), status


def is_official_senate_initiative_url(value: str) -> bool:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or (parsed.hostname or "").lower() != "www.senado.es"
        or parsed.path not in SENATE_INITIATIVE_CAPTURE_PATHS
    ):
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    return all(
        len(query.get(key, [])) == 1 and query[key][0]
        for key in ("id1", "id2", "legis")
    )


def is_official_parliament_document_url(value: str) -> bool:
    """Allow exact PDF locators from the official parliamentary document hosts."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.fragment:
        return False
    host = (parsed.hostname or "").lower()
    path = parsed.path
    lower_path = path.lower()
    if not lower_path.endswith(".pdf"):
        return False
    if host == "www.senado.es":
        return (
            re.fullmatch(
                r"/legis\d+/publicaciones/pdf/senado/(?:bocg|ds)/[^/]+\.pdf",
                path,
                re.IGNORECASE,
            )
            is not None
        )
    if host == "www.congreso.es":
        return lower_path.startswith("/public_oficiales/")
    if host == "www.boe.es":
        return lower_path.startswith("/boe/")
    return False


def official_senate_diary_identifier(value: str) -> str | None:
    """Return an identifier only for the exact official Senate diary URL shape."""
    match = SENATE_OFFICIAL_DIARY_URL_RE.fullmatch(value)
    if match is None:
        return None
    section = match.group("section").upper()
    kind = match.group("kind").upper()
    if (section, kind) not in {("PL", "P"), ("CO", "C")}:
        return None
    return match.group("identifier").upper()


def extract_official_senate_capture_urls(payload: str) -> set[str]:
    """Extract exact Senado capture URLs without inventing missing identifiers."""
    identifiers = {
        html.unescape(value).strip() for value in extract_dc_identifier_values(payload)
    }
    exact_identifiers = {
        value for value in identifiers if is_official_senate_initiative_url(value)
    }
    if exact_identifiers:
        return exact_identifiers
    exact_form_actions = {
        candidate
        for value in HTML_FORM_ACTION_RE.findall(payload)
        if is_official_senate_initiative_url(
            candidate := urljoin(
                "https://www.senado.es",
                html.unescape(value).strip(),
            )
        )
    }
    if exact_form_actions:
        return exact_form_actions
    generic_identifiers = {
        value
        for value in identifiers
        if (
            urlparse(value).scheme in {"http", "https"}
            and (urlparse(value).hostname or "").lower() == "www.senado.es"
            and urlparse(value).path in SENATE_INITIATIVE_CAPTURE_PATHS
        )
    }
    if len(generic_identifiers) != 1:
        return set()
    base_url = next(iter(generic_identifiers))
    base_path = urlparse(base_url).path
    source_urls: set[str] = set()
    for value in HTML_HREF_RE.findall(payload):
        candidate = urljoin(base_url, html.unescape(value).strip())
        parsed = urlparse(candidate)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if (
            parsed.path == base_path
            and parsed.scheme in {"http", "https"}
            and (parsed.hostname or "").lower() == "www.senado.es"
            and query.get("lang") == ["es_ES"]
            and all(
                len(query.get(key, [])) == 1
                and re.fullmatch(r"\d+", query[key][0]) is not None
                for key in ("id1", "id2", "legis")
            )
        ):
            source_urls.add(candidate)
    return source_urls


def extract_dc_identifier_values(payload: str) -> set[str]:
    """Read DC.identifier regardless of safe extra attributes or attribute order."""
    values: set[str] = set()
    for tag in HTML_META_TAG_RE.findall(payload):
        attributes = {
            key.lower(): value for key, _quote, value in HTML_ATTRIBUTE_RE.findall(tag)
        }
        if attributes.get("name", "").lower() == "dc.identifier" and attributes.get(
            "content"
        ):
            values.add(attributes["content"])
    return values


def is_official_senate_home_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == "www.senado.es"
        and parsed.path == "/web/index.html"
        and not parsed.query
        and not parsed.fragment
    )


def extract_official_manual_capture_urls(payload: str) -> set[str]:
    """Extract exact official self-identifiers from preserved manual captures."""
    source_urls = {
        html.unescape(value).strip()
        for pattern in SELF_URL_LINK_RES
        for value in pattern.findall(payload)
        if is_allowed_self_url(
            MANUAL_SOURCE_GROUP,
            html.unescape(value).strip(),
        )
    }
    senate_identifiers = {
        html.unescape(value).strip() for value in extract_dc_identifier_values(payload)
    }
    source_urls.update(
        value
        for value in senate_identifiers
        if is_official_senate_home_url(value)
        or is_official_senate_initiative_url(value)
    )
    source_urls.update(extract_official_senate_capture_urls(payload))
    return source_urls


def is_official_moncloa_rss_index_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == "www.lamoncloa.gob.es"
        and parsed.path.lower() == "/paginas/varios/rss.aspx"
        and not parsed.query
        and not parsed.fragment
    )


def is_official_moncloa_feed_url(value: str) -> bool:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "www.lamoncloa.gob.es"
        or parsed.path.lower() != "/paginas/rss.aspx"
        or parsed.fragment
    ):
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    return (
        set(query) == {"tipo"}
        and len(query["tipo"]) == 1
        and re.fullmatch(r"\d+", query["tipo"][0]) is not None
    )


def normalized_embedded_title(value: str) -> str:
    return " ".join(html.unescape(value).split())


def extract_official_moncloa_feed_index(
    payload: str,
    *,
    index_url: str,
) -> dict[str, set[str]]:
    """Return exact title-to-feed relations declared by an official RSS index."""
    if not is_official_moncloa_rss_index_url(index_url):
        return {}
    relations: dict[str, set[str]] = defaultdict(set)
    for tag in HTML_LINK_TAG_RE.findall(payload):
        attributes = {
            key.lower(): html.unescape(value).strip()
            for key, _quote, value in HTML_ATTRIBUTE_RE.findall(tag)
        }
        if (
            attributes.get("rel", "").lower() != "alternate"
            or attributes.get("type", "").lower() != "application/rss+xml"
        ):
            continue
        title = normalized_embedded_title(attributes.get("title", ""))
        candidate = urljoin(index_url, attributes.get("href", ""))
        if title and is_official_moncloa_feed_url(candidate):
            relations[title].add(candidate)
    return dict(relations)


def extract_moncloa_rss_channel_title(payload: str) -> str | None:
    match = MONCLOA_RSS_CHANNEL_TITLE_RE.search(payload)
    if match is None:
        return None
    title = normalized_embedded_title(match.group(1))
    return title or None


def extract_official_senate_vote_self_urls(
    payload: str,
    *,
    relative_path: str,
) -> set[str]:
    """Recover only the exact Senate vote URL matching the captured file path."""
    path = PurePosixPath(relative_path)
    prefix = PurePosixPath("manual/senado_votaciones_ses")
    try:
        vote_path = path.relative_to(prefix)
    except ValueError:
        return set()
    if len(vote_path.parts) != 2:
        return set()
    expected_source_path = f"/{vote_path.parts[0]}/votaciones/{vote_path.parts[1]}"
    source_urls: set[str] = set()
    for value in SENATE_VOTE_XML_URL_RE.findall(payload):
        candidate = html.unescape(value).strip()
        parsed = urlparse(candidate)
        if (
            parsed.scheme in {"http", "https"}
            and (parsed.hostname or "").lower() == "www.senado.es"
            and parsed.path == expected_source_path
            and SENATE_VOTE_SOURCE_PATH_RE.fullmatch(parsed.path) is not None
            and not parsed.query
            and not parsed.fragment
        ):
            source_urls.add(candidate)
    return source_urls


def load_moncloa_feed_index_relations(
    work: sqlite3.Connection,
    *,
    inventory_root: Path,
) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Build relations from exact official index captures, never file-name guesses."""
    relations: dict[str, set[str]] = defaultdict(set)
    counts: Counter[str] = Counter()
    for row in work.execute(
        """
        SELECT path
        FROM inventory
        WHERE source_group = ?
          AND (
            extension = 'html'
            OR path LIKE 'manual/moncloa_exec/%'
          )
        ORDER BY file_id
        """,
        (MANUAL_SOURCE_GROUP,),
    ):
        relative_path = str(row["path"])
        capture_path = (inventory_root / relative_path).resolve()
        try:
            capture_path.relative_to(inventory_root.resolve())
        except ValueError as exc:
            raise ProvenanceAuditError(
                f"Moncloa index capture escapes inventory root: {relative_path}"
            ) from exc
        payload, status = read_embedded_metadata_text(capture_path)
        counts[f"capture_{status}"] += 1
        if payload is None:
            continue
        index_urls = {
            html.unescape(value).strip()
            for pattern in SELF_URL_LINK_RES
            for value in pattern.findall(payload)
            if is_official_moncloa_rss_index_url(html.unescape(value).strip())
        }
        if len(index_urls) != 1:
            continue
        counts["official_index_captures"] += 1
        index_url = next(iter(index_urls))
        for title, source_urls in extract_official_moncloa_feed_index(
            payload,
            index_url=index_url,
        ).items():
            relations[title].update(source_urls)
            counts["declared_relations"] += len(source_urls)
    counts["unique_titles"] = len(relations)
    counts["unique_source_urls"] = len(
        {source_url for values in relations.values() for source_url in values}
    )
    return dict(relations), dict(sorted(counts.items()))


def extract_official_congress_current_urls(payload: str) -> set[str]:
    """Extract exact Congreso transcript state encoded by the captured page."""
    source_urls: set[str] = set()
    for value in CONGRESS_CURRENT_URL_RE.findall(payload):
        decoded = re.sub(
            r"\\x([0-9a-fA-F]{2})",
            lambda match: chr(int(match.group(1), 16)),
            html.unescape(value),
        )
        candidate = urljoin("https://www.congreso.es", decoded)
        parsed = urlparse(candidate)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if (
            parsed.scheme == "https"
            and (parsed.hostname or "").lower() == "www.congreso.es"
            and parsed.path
            in {"/busqueda-de-intervenciones", "/es/busqueda-de-intervenciones"}
            and query.get("p_p_id") == ["intervenciones"]
            and query.get("p_p_lifecycle") == ["0"]
            and query.get("p_p_state") == ["normal"]
            and query.get("p_p_mode") == ["view"]
            and query.get("_intervenciones_mode") == ["mostrarTextoIntegro"]
            and len(query.get("_intervenciones_legislatura", [])) == 1
            and bool(query["_intervenciones_legislatura"][0])
            and len(query.get("_intervenciones_id_texto", [])) == 1
            and bool(query["_intervenciones_id_texto"][0])
        ):
            source_urls.add(candidate)
    return source_urls


def is_allowed_self_url(source_group: str, value: str) -> bool:
    if public_url_kind(value) not in {"public_http", "public_https"}:
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    path_lower = parsed.path.lower()
    if source_group == PARTY_PROGRAM_SOURCE_GROUP:
        return parsed.scheme == "https" and host in PRIMARY_PARTY_HOSTS
    if source_group in {MANUAL_SOURCE_GROUP, MONCLOA_SOURCE_GROUP}:
        if host in {"www.parlamentodegalicia.gal", "www.parlamentodegalicia.es"}:
            return path_lower == "/composicion/deputados" or path_lower.startswith(
                "/composicion/deputados/"
            )
        if host == "parlamentodenavarra.es":
            return path_lower.startswith("/es/persona/") or path_lower == (
                "/es/composicion-organos/parlamentarios-forales"
            )
        if host == "www.lamoncloa.gob.es":
            return path_lower.startswith(
                "/consejodeministros/referencias/paginas/"
            ) or is_official_moncloa_rss_index_url(value)
    return False


def build_matches(work: sqlite3.Connection) -> None:
    work.executescript(
        """
        INSERT OR IGNORE INTO matches(file_id, provenance_id, match_basis)
        SELECT
          f.file_id,
          p.provenance_id,
          CASE
            WHEN p.table_name = 'embedded_official_url'
              AND p.content_sha256 = f.sha256 THEN 'embedded_url_checksum'
            WHEN p.content_sha256 = f.sha256 THEN 'path_checksum'
            WHEN p.content_sha256 IS NULL THEN 'path_only'
            ELSE 'path_checksum_conflict'
          END
        FROM inventory AS f
        JOIN provenance AS p ON p.normalized_path = f.path;

        INSERT OR IGNORE INTO matches(file_id, provenance_id, match_basis)
        SELECT f.file_id, p.provenance_id, 'content_checksum'
        FROM inventory AS f
        JOIN provenance AS p ON p.content_sha256 = f.sha256;
        """
    )
    work.commit()


FILE_SUMMARY_QUERY = """
SELECT
  f.file_id,
  f.path,
  f.source_group,
  f.extension,
  f.bytes,
  f.sha256,
  f.item_status,
  COUNT(m.provenance_id) AS provenance_edges,
  COUNT(DISTINCT CASE WHEN p.source_id IS NOT NULL THEN p.source_id END) AS source_ids,
  SUM(CASE WHEN p.url_kind IN ('public_http', 'public_https') THEN 1 ELSE 0 END) AS public_url_edges,
  SUM(CASE WHEN p.url_kind = 'public_https' THEN 1 ELSE 0 END) AS public_https_edges,
  MAX(CASE WHEN m.match_basis = 'path_checksum' THEN 1 ELSE 0 END) AS has_path_checksum,
  MAX(CASE WHEN m.match_basis = 'content_checksum' THEN 1 ELSE 0 END) AS has_content_checksum,
  MAX(CASE WHEN m.match_basis = 'embedded_url_checksum' THEN 1 ELSE 0 END) AS has_embedded_url_checksum,
  MAX(CASE WHEN m.match_basis = 'path_only' THEN 1 ELSE 0 END) AS has_path_only,
  MAX(CASE WHEN m.match_basis = 'path_checksum_conflict' THEN 1 ELSE 0 END) AS has_conflict,
  MAX(
    CASE
      WHEN p.declared_bytes IS NOT NULL AND p.declared_bytes != f.bytes THEN 1
      ELSE 0
    END
  ) AS has_declared_bytes_conflict
FROM inventory AS f
LEFT JOIN matches AS m ON m.file_id = f.file_id
LEFT JOIN provenance AS p ON p.provenance_id = m.provenance_id
GROUP BY f.file_id
ORDER BY f.file_id
"""


def classification(row: sqlite3.Row) -> str:
    if int(row["has_declared_bytes_conflict"] or 0):
        return "declared_bytes_conflict"
    if int(row["has_path_checksum"] or 0):
        return "verified_path_checksum"
    if int(row["has_content_checksum"] or 0):
        return "verified_content_checksum"
    if int(row["has_embedded_url_checksum"] or 0):
        return "verified_embedded_url_checksum"
    if int(row["has_path_only"] or 0):
        return "path_only_checksum_unverified"
    if int(row["has_conflict"] or 0):
        return "checksum_conflict"
    return "unlinked"


def write_file_manifest(
    work: sqlite3.Connection,
    output_path: Path,
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    totals: Counter[str] = Counter()
    by_source_group: dict[str, Counter[str]] = defaultdict(Counter)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in work.execute(FILE_SUMMARY_QUERY):
            status = classification(row)
            has_conflict = bool(row["has_conflict"])
            has_declared_bytes_conflict = bool(row["has_declared_bytes_conflict"])
            item = {
                "path": row["path"],
                "source_group": row["source_group"],
                "extension": row["extension"],
                "bytes": int(row["bytes"]),
                "sha256": row["sha256"],
                "inventory_status": row["item_status"],
                "provenance_status": status,
                "provenance_edges": int(row["provenance_edges"] or 0),
                "source_ids": int(row["source_ids"] or 0),
                "public_url_edges": int(row["public_url_edges"] or 0),
                "public_https_edges": int(row["public_https_edges"] or 0),
                "checksum_conflict": has_conflict,
                "declared_bytes_conflict": has_declared_bytes_conflict,
            }
            handle.write(json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n")
            totals["files"] += 1
            totals["bytes"] += int(row["bytes"])
            totals[status] += 1
            totals["files_with_public_url"] += int(item["public_url_edges"] > 0)
            totals["files_with_public_https_url"] += int(item["public_https_edges"] > 0)
            totals["files_with_checksum_conflict"] += int(has_conflict)
            totals["files_with_declared_bytes_conflict"] += int(
                has_declared_bytes_conflict
            )
            totals["inventory_non_ok_files"] += int(row["item_status"] != "ok")
            group = by_source_group[str(row["source_group"])]
            group["files"] += 1
            group["bytes"] += int(row["bytes"])
            group[status] += 1
            group["files_with_public_url"] += int(item["public_url_edges"] > 0)
    return dict(totals), {
        key: dict(sorted(value.items()))
        for key, value in sorted(by_source_group.items())
    }


def write_edge_manifest(work: sqlite3.Connection, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    query = """
    SELECT
      f.path AS file_path,
      f.sha256 AS file_sha256,
      p.db_ref,
      p.table_name,
      p.normalized_path AS metadata_path,
      p.content_sha256 AS metadata_sha256,
      p.source_id,
      p.source_url,
      p.fetched_at,
      p.declared_bytes,
      p.url_kind,
      m.match_basis
    FROM matches AS m
    JOIN inventory AS f ON f.file_id = m.file_id
    JOIN provenance AS p ON p.provenance_id = m.provenance_id
    ORDER BY f.file_id, p.provenance_id
    """
    with output_path.open("w", encoding="utf-8") as handle:
        for row in work.execute(query):
            handle.write(
                json.dumps(dict(row), ensure_ascii=True, sort_keys=True) + "\n"
            )
            rows += 1
    return rows


def audit_text_artifacts(
    work: sqlite3.Connection,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    refs = int(work.execute("SELECT COUNT(*) FROM text_refs").fetchone()[0])
    unique_paths = int(
        work.execute("SELECT COUNT(DISTINCT text_path) FROM text_refs").fetchone()[0]
    )
    existing = 0
    missing = 0
    checksum_verified = 0
    checksum_conflicts = 0
    checksum_missing = 0
    missing_samples: list[str] = []
    conflict_samples: list[str] = []
    for row in work.execute(
        """
        SELECT text_path, GROUP_CONCAT(DISTINCT text_sha256) AS expected_hashes
        FROM text_refs
        GROUP BY text_path
        ORDER BY text_path
        """
    ):
        path = safe_repo_path(str(row["text_path"]), repo_root=repo_root)
        if not path.is_file():
            missing += 1
            if len(missing_samples) < 20:
                missing_samples.append(str(row["text_path"]))
            continue
        existing += 1
        expected = {
            value
            for value in str(row["expected_hashes"] or "").split(",")
            if SHA256_RE.fullmatch(value)
        }
        if not expected:
            checksum_missing += 1
            continue
        observed = sha256_text_artifact(path)
        if observed in expected:
            checksum_verified += 1
        else:
            checksum_conflicts += 1
            if len(conflict_samples) < 20:
                conflict_samples.append(str(row["text_path"]))
    return {
        "metadata_edges": refs,
        "unique_paths": unique_paths,
        "existing": existing,
        "missing": missing,
        "checksum_verified": checksum_verified,
        "checksum_unavailable": checksum_missing,
        "checksum_conflicts": checksum_conflicts,
        "missing_samples": missing_samples,
        "checksum_conflict_samples": conflict_samples,
    }


def artifact_reference(path: Path, *, repo_root: Path, rows: int) -> dict[str, Any]:
    return {
        "path": display_path(path, repo_root=repo_root),
        "rows": rows,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def unmatched_metadata_summary(work: sqlite3.Connection) -> dict[str, Any]:
    total = int(work.execute("SELECT COUNT(*) FROM provenance").fetchone()[0])
    matched = int(
        work.execute("SELECT COUNT(DISTINCT provenance_id) FROM matches").fetchone()[0]
    )
    samples = [
        {
            "path": row["normalized_path"],
            "source_id": row["source_id"],
            "table": row["table_name"],
        }
        for row in work.execute(
            """
            SELECT p.normalized_path, p.source_id, p.table_name
            FROM provenance AS p
            LEFT JOIN matches AS m ON m.provenance_id = p.provenance_id
            WHERE m.provenance_id IS NULL
            ORDER BY p.normalized_path
            LIMIT 20
            """
        )
    ]
    return {
        "metadata_edges": total,
        "matched_metadata_edges": matched,
        "unmatched_metadata_edges": total - matched,
        "unmatched_samples": samples,
    }


def run_audit(
    *,
    repo_root: Path,
    inventory_root: Path,
    inventory_manifest: Path,
    database_paths: list[Path],
    provenance_manifest_paths: list[Path],
    published_capture_index_paths: list[Path],
    party_program_source_manifest_paths: list[Path],
    archived_document_lineage_manifest_paths: list[Path],
    wayback_document_lineage_manifest_paths: list[Path],
    boe_document_corpus_lineage_manifest_paths: list[Path],
    captured_link_document_lineage_manifest_paths: list[Path],
    official_document_identifier_lineage_manifest_paths: list[Path],
    official_path_document_lineage_manifest_paths: list[Path],
    file_manifest_out: Path,
    edge_manifest_out: Path,
    report_out: Path,
) -> dict[str, Any]:
    if not inventory_root.is_dir():
        raise ProvenanceAuditError(f"inventory root missing: {inventory_root}")
    with tempfile.TemporaryDirectory(prefix="vota-document-provenance-") as temp_dir:
        work = create_work_database(Path(temp_dir) / "audit.sqlite")
        try:
            inventory_rows = load_inventory(work, inventory_manifest)
            official_capture_sidecars = load_official_capture_sidecars(
                work,
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            databases = [
                load_database_metadata(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in database_paths
            ]
            auxiliary_provenance_manifests = [
                load_vote_lineage_manifest(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in provenance_manifest_paths
            ]
            published_capture_indexes = [
                load_published_capture_index(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in published_capture_index_paths
            ]
            party_program_source_manifests = load_party_program_source_manifests(
                work,
                party_program_source_manifest_paths,
                repo_root=repo_root,
                inventory_root=inventory_root,
            )
            archived_document_lineage_manifests = [
                load_archived_document_lineage_manifest(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in archived_document_lineage_manifest_paths
            ]
            wayback_document_lineage_manifests = [
                load_wayback_document_lineage_manifest(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in wayback_document_lineage_manifest_paths
            ]
            boe_document_corpus_lineage_manifests = [
                load_boe_document_corpus_lineage_manifest(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in boe_document_corpus_lineage_manifest_paths
            ]
            captured_link_document_lineage_manifests = [
                load_captured_link_document_lineage_manifest(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in captured_link_document_lineage_manifest_paths
            ]
            official_document_identifier_lineage_manifests = [
                load_official_document_identifier_lineage_manifest(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in official_document_identifier_lineage_manifest_paths
            ]
            official_path_document_lineage_manifests = [
                load_official_path_document_lineage_manifest(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in official_path_document_lineage_manifest_paths
            ]
            build_matches(work)
            embedded_official_urls = load_embedded_official_urls(
                work,
                inventory_root=inventory_root,
            )
            build_matches(work)
            file_totals, by_source_group = write_file_manifest(
                work,
                file_manifest_out,
            )
            edge_rows = write_edge_manifest(work, edge_manifest_out)
            text_artifacts = audit_text_artifacts(work, repo_root=repo_root)
            metadata = unmatched_metadata_summary(work)
        finally:
            work.close()

    verified_files = (
        int(file_totals.get("verified_path_checksum", 0))
        + int(file_totals.get("verified_content_checksum", 0))
        + int(file_totals.get("verified_embedded_url_checksum", 0))
    )
    files_total = int(file_totals.get("files", 0))
    files_with_public_url = int(file_totals.get("files_with_public_url", 0))
    database_inputs_ok = all(item["status"] == "ok" for item in databases)
    integrity_passed = (
        files_total > 0
        and inventory_rows == files_total
        and database_inputs_ok
        and int(file_totals.get("inventory_non_ok_files", 0)) == 0
        and int(file_totals.get("files_with_checksum_conflict", 0)) == 0
        and int(file_totals.get("files_with_declared_bytes_conflict", 0)) == 0
        and int(text_artifacts["missing"]) == 0
        and int(text_artifacts["checksum_conflicts"]) == 0
    )
    complete_provenance = (
        files_total > 0
        and verified_files == files_total
        and files_with_public_url == files_total
    )
    report: dict[str, Any] = {
        "schema_version": "real_document_provenance_audit_v13",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": (
            "failed"
            if not integrity_passed
            else "ok"
            if complete_provenance
            else "partial"
        ),
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_counted": False,
            "public_domain_personal_information_retained": True,
            "workstation_paths_forbidden_in_outputs": True,
            "checksum_or_content_address_required_for_verified_file": True,
        },
        "inventory": artifact_reference(
            inventory_manifest,
            repo_root=repo_root,
            rows=inventory_rows,
        ),
        "official_capture_sidecars": official_capture_sidecars,
        "databases": databases,
        "auxiliary_provenance_manifests": auxiliary_provenance_manifests,
        "published_capture_indexes": published_capture_indexes,
        "party_program_source_manifests": party_program_source_manifests,
        "archived_document_lineage_manifests": (archived_document_lineage_manifests),
        "wayback_document_lineage_manifests": (wayback_document_lineage_manifests),
        "boe_document_corpus_lineage_manifests": (
            boe_document_corpus_lineage_manifests
        ),
        "captured_link_document_lineage_manifests": (
            captured_link_document_lineage_manifests
        ),
        "official_document_identifier_lineage_manifests": (
            official_document_identifier_lineage_manifests
        ),
        "official_path_document_lineage_manifests": (
            official_path_document_lineage_manifests
        ),
        "embedded_official_urls": embedded_official_urls,
        "file_manifest": artifact_reference(
            file_manifest_out,
            repo_root=repo_root,
            rows=files_total,
        ),
        "edge_manifest": artifact_reference(
            edge_manifest_out,
            repo_root=repo_root,
            rows=edge_rows,
        ),
        "totals": {
            **file_totals,
            "verified_checksum_files": verified_files,
            "verified_checksum_coverage": (
                round(verified_files / files_total, 6) if files_total else 0.0
            ),
            "public_url_coverage": (
                round(files_with_public_url / files_total, 6) if files_total else 0.0
            ),
            "provenance_edges": edge_rows,
        },
        "metadata": metadata,
        "text_artifacts": text_artifacts,
        "by_source_group": by_source_group,
        "checks": {
            "inventory_rows_reconciled": inventory_rows == files_total,
            "database_inputs_readable": database_inputs_ok,
            "inventory_files_parse_clean": int(
                file_totals.get("inventory_non_ok_files", 0)
            )
            == 0,
            "no_document_checksum_conflicts": int(
                file_totals.get("files_with_checksum_conflict", 0)
            )
            == 0,
            "no_document_declared_byte_conflicts": int(
                file_totals.get("files_with_declared_bytes_conflict", 0)
            )
            == 0,
            "all_referenced_text_artifacts_exist": int(text_artifacts["missing"]) == 0,
            "no_text_checksum_conflicts": int(text_artifacts["checksum_conflicts"])
            == 0,
            "integrity_passed": integrity_passed,
            "complete_checksum_provenance": verified_files == files_total,
            "complete_public_url_provenance": files_with_public_url == files_total,
            "promotion_ready": complete_provenance and integrity_passed,
        },
        "limitations": [
            "The audit covers only the declared inventory, SQLite inputs, auxiliary provenance manifests, and checksum-verified published capture indexes.",
            "Unlinked files remain real local bytes but do not count as fully traceable evidence until an official URL and checksum-backed metadata edge are recovered.",
            "A public HTTP(S) URL proves a public locator, not institutional completeness or long-term availability.",
            "This reconciliation does not increase the document corpus row count or prove extraction accuracy.",
        ],
        "next_action": (
            "Recover source URL, retrieval, and checksum metadata for every unlinked source group; regenerate the inventory and audit; then require promotion_ready before durable publication."
        ),
    }
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        repo_root = REPO_ROOT
        databases = [Path(value) for value in (args.databases or DEFAULT_DATABASES)]
        provenance_manifests = [
            Path(value)
            for value in (
                args.provenance_manifests or DEFAULT_AUXILIARY_PROVENANCE_MANIFESTS
            )
        ]
        published_capture_indexes = [
            Path(value)
            for value in (
                args.published_capture_indexes or DEFAULT_PUBLISHED_CAPTURE_INDEXES
            )
        ]
        party_program_source_manifests = (
            [Path(value) for value in args.party_program_source_manifests]
            if args.party_program_source_manifests
            else sorted(
                (repo_root / DEFAULT_PARTY_PROGRAM_SOURCE_MANIFEST_DIR).rglob("*.csv")
            )
        )
        archived_document_lineage_manifests = [
            Path(value)
            for value in (
                args.archived_document_lineage_manifests
                or DEFAULT_ARCHIVED_DOCUMENT_LINEAGE_MANIFESTS
            )
        ]
        wayback_document_lineage_manifests = [
            Path(value)
            for value in (
                args.wayback_document_lineage_manifests
                or DEFAULT_WAYBACK_DOCUMENT_LINEAGE_MANIFESTS
            )
        ]
        boe_document_corpus_lineage_manifests = [
            Path(value)
            for value in (
                args.boe_document_corpus_lineage_manifests
                or DEFAULT_BOE_DOCUMENT_CORPUS_LINEAGE_MANIFESTS
            )
        ]
        captured_link_document_lineage_manifests = [
            Path(value)
            for value in (
                args.captured_link_document_lineage_manifests
                or DEFAULT_CAPTURED_LINK_DOCUMENT_LINEAGE_MANIFESTS
            )
        ]
        official_document_identifier_lineage_manifests = [
            Path(value)
            for value in (
                args.official_document_identifier_lineage_manifests
                or DEFAULT_OFFICIAL_DOCUMENT_IDENTIFIER_LINEAGE_MANIFESTS
            )
        ]
        official_path_document_lineage_manifests = [
            Path(value)
            for value in (
                args.official_path_document_lineage_manifests
                or DEFAULT_OFFICIAL_PATH_DOCUMENT_LINEAGE_MANIFESTS
            )
        ]
        report = run_audit(
            repo_root=repo_root,
            inventory_root=safe_repo_path(args.inventory_root, repo_root=repo_root),
            inventory_manifest=safe_repo_path(
                args.inventory_manifest,
                repo_root=repo_root,
            ),
            database_paths=[
                safe_repo_path(path, repo_root=repo_root) for path in databases
            ],
            provenance_manifest_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in provenance_manifests
            ],
            published_capture_index_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in published_capture_indexes
            ],
            party_program_source_manifest_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in party_program_source_manifests
            ],
            archived_document_lineage_manifest_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in archived_document_lineage_manifests
            ],
            wayback_document_lineage_manifest_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in wayback_document_lineage_manifests
            ],
            boe_document_corpus_lineage_manifest_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in boe_document_corpus_lineage_manifests
            ],
            captured_link_document_lineage_manifest_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in captured_link_document_lineage_manifests
            ],
            official_document_identifier_lineage_manifest_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in official_document_identifier_lineage_manifests
            ],
            official_path_document_lineage_manifest_paths=[
                safe_repo_path(path, repo_root=repo_root)
                for path in official_path_document_lineage_manifests
            ],
            file_manifest_out=safe_repo_path(
                args.file_manifest_out,
                repo_root=repo_root,
            ),
            edge_manifest_out=safe_repo_path(
                args.edge_manifest_out,
                repo_root=repo_root,
            ),
            report_out=safe_repo_path(args.report_out, repo_root=repo_root),
        )
    except (OSError, sqlite3.DatabaseError, ProvenanceAuditError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "files": report["totals"]["files"],
                "verified_checksum_files": report["totals"]["verified_checksum_files"],
                "files_with_public_url": report["totals"]["files_with_public_url"],
                "checksum_conflicts": report["totals"]["files_with_checksum_conflict"],
                "promotion_ready": report["checks"]["promotion_ready"],
                "report": display_path(
                    safe_repo_path(args.report_out, repo_root=REPO_ROOT),
                    repo_root=REPO_ROOT,
                ),
            },
            sort_keys=True,
        )
    )
    return (
        1 if args.enforce_integrity and not report["checks"]["integrity_passed"] else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
