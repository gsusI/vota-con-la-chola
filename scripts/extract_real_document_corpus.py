#!/usr/bin/env python3
"""Extract every eligible real document into a resumable text CAS."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import resource
import sqlite3
import sys
import time
import uuid
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.extraction import (
    DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
    DocumentExtraction,
    extract_document_path,
)
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    publish_generation_manifest,
)

DEFAULT_RAW_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY = Path("etl/data/manifests/real-document-format-inventory.jsonl")
DEFAULT_PROVENANCE = Path("etl/data/manifests/real-document-provenance-files.jsonl")
DEFAULT_STATE_DB = Path("etl/data/staging/real-document-text-corpus-v2.db")
DEFAULT_OUTPUT_ROOT = Path("etl/data/derived/real-document-text-corpus-v2")
DEFAULT_MANIFEST = Path("etl/data/published/real-document-text-manifest-latest.jsonl")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-text-extraction.json"
)
SHA256_HEX_LENGTH = 64
DEFAULT_MANIFEST_SHARD_MAX_ROWS = 10_000
DEFAULT_MANIFEST_SHARD_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024


class CorpusExtractionError(RuntimeError):
    """Raised when extraction cannot make an exact real-data claim."""


@dataclass(frozen=True)
class ExtractionOutcome:
    content_sha256: str
    status: str
    text_sha256: str | None
    text_cas_path: str | None
    text_chars: int
    method: str
    truncated: bool
    error: str | None


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def process_usage() -> dict[str, float | int]:
    """Return cumulative CPU and peak-memory telemetry for this real run."""
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss_multiplier = 1 if sys.platform == "darwin" else 1024
    return {
        "cpu_seconds": float(
            own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime
        ),
        "peak_rss_bytes_self": int(own.ru_maxrss * rss_multiplier),
        "peak_rss_bytes_child_max": int(children.ru_maxrss * rss_multiplier),
    }


def sha256_path(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.name


def safe_child(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise CorpusExtractionError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise CorpusExtractionError(f"path escapes root: {relative}") from exc
    return candidate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--provenance", default=str(DEFAULT_PROVENANCE))
    parser.add_argument("--state-db", default=str(DEFAULT_STATE_DB))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument(
        "--manifest-shard-max-rows",
        type=int,
        default=DEFAULT_MANIFEST_SHARD_MAX_ROWS,
    )
    parser.add_argument(
        "--manifest-shard-max-uncompressed-bytes",
        type=int,
        default=DEFAULT_MANIFEST_SHARD_MAX_UNCOMPRESSED_BYTES,
    )
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--claim-size", type=int, default=32)
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--max-input-bytes", type=int, default=128 * 1024 * 1024)
    parser.add_argument("--max-text-chars", type=int, default=16_000_000)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def open_state_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_state_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS extraction_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS document_file_instances (
          path TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          extension TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          source_group TEXT NOT NULL,
          quality_class TEXT NOT NULL,
          inventory_text_chars INTEGER,
          page_count INTEGER,
          ocr_candidate_pages_json TEXT NOT NULL,
          provenance_seen INTEGER NOT NULL DEFAULT 0,
          provenance_status TEXT,
          public_url_edges INTEGER NOT NULL DEFAULT 0,
          public_https_edges INTEGER NOT NULL DEFAULT 0,
          CHECK (bytes >= 0),
          CHECK (provenance_seen IN (0, 1))
        );

        CREATE INDEX IF NOT EXISTS idx_document_file_instances_sha256
          ON document_file_instances(content_sha256);
        CREATE INDEX IF NOT EXISTS idx_document_file_instances_source_group
          ON document_file_instances(source_group);

        CREATE TABLE IF NOT EXISTS document_text_work (
          content_sha256 TEXT PRIMARY KEY,
          representative_path TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          extension TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          source_group TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,
          max_attempts INTEGER NOT NULL,
          lease_owner TEXT,
          lease_expires_at TEXT,
          extraction_status TEXT,
          text_sha256 TEXT,
          text_cas_path TEXT,
          text_chars INTEGER,
          extraction_method TEXT,
          text_truncated INTEGER,
          last_error TEXT,
          started_at TEXT,
          completed_at TEXT,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (representative_path)
            REFERENCES document_file_instances(path),
          CHECK (state IN ('pending', 'leased', 'succeeded', 'dead')),
          CHECK (attempts >= 0),
          CHECK (max_attempts >= 1)
        );

        CREATE INDEX IF NOT EXISTS idx_document_text_work_claim
          ON document_text_work(state, lease_expires_at, content_sha256);
        """
    )
    conn.commit()


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        raise CorpusExtractionError(f"missing JSONL input: {display_path(path)}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CorpusExtractionError(
                    f"invalid JSONL at {display_path(path)}:{line_number}: {exc}"
                ) from exc
            if not isinstance(item, dict):
                raise CorpusExtractionError(
                    f"JSONL row must be an object: {display_path(path)}:{line_number}"
                )
            yield item


def _metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row["key"]): str(row["value"])
        for row in conn.execute("SELECT key, value FROM extraction_metadata")
    }


def _insert_metadata(conn: sqlite3.Connection, values: Mapping[str, object]) -> None:
    conn.executemany(
        "INSERT INTO extraction_metadata (key, value) VALUES (?, ?)",
        [(str(key), str(value)) for key, value in values.items()],
    )


def seed_state(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    inventory_path: Path,
    provenance_path: Path,
    max_attempts: int,
) -> dict[str, int]:
    inventory_sha256 = sha256_path(inventory_path)
    provenance_sha256 = sha256_path(provenance_path)
    metadata = _metadata(conn)
    if metadata:
        if (
            metadata.get("inventory_sha256") != inventory_sha256
            or metadata.get("provenance_sha256") != provenance_sha256
            or metadata.get("extraction_algorithm_version")
            != DOCUMENT_EXTRACTION_ALGORITHM_VERSION
        ):
            raise CorpusExtractionError(
                "state DB belongs to different inputs/extractor version; "
                "use a new --state-db so prior evidence remains immutable"
            )
        return {
            "file_instances": int(metadata["file_instances"]),
            "distinct_content_objects": int(metadata["distinct_content_objects"]),
        }

    existing_rows = conn.execute(
        "SELECT COUNT(*) FROM document_file_instances"
    ).fetchone()[0]
    if int(existing_rows):
        raise CorpusExtractionError("state DB has rows without input metadata")

    inventory_rows = 0
    for item in iter_jsonl(inventory_path):
        path = str(item.get("path") or "")
        sha256 = str(item.get("sha256") or "").lower()
        declared_bytes = item.get("bytes")
        if (
            item.get("accountability_eligible") is not True
            or item.get("status") != "ok"
            or len(sha256) != SHA256_HEX_LENGTH
            or not isinstance(declared_bytes, int)
            or declared_bytes < 0
        ):
            raise CorpusExtractionError(f"ineligible inventory row: {path}")
        raw_path = safe_child(raw_root, path)
        if not raw_path.is_file() or raw_path.stat().st_size != declared_bytes:
            raise CorpusExtractionError(
                f"inventory file missing or size drifted: {path}"
            )
        page_quality = item.get("page_text_quality") or {}
        ocr_pages = (
            page_quality.get("ocr_candidate_pages")
            if isinstance(page_quality, dict)
            else []
        )
        conn.execute(
            """
            INSERT INTO document_file_instances (
              path, content_sha256, bytes, extension, mime_type, source_group,
              quality_class, inventory_text_chars, page_count,
              ocr_candidate_pages_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path,
                sha256,
                declared_bytes,
                str(item.get("extension") or ""),
                str(item.get("mime_type") or ""),
                str(item.get("source_group") or "unknown"),
                str(item.get("quality_class") or "unknown"),
                item.get("text_chars"),
                item.get("page_count"),
                json.dumps(ocr_pages or [], ensure_ascii=True, sort_keys=True),
            ),
        )
        inventory_rows += 1
        if inventory_rows % 5_000 == 0:
            conn.commit()
    conn.commit()

    provenance_rows = 0
    for item in iter_jsonl(provenance_path):
        path = str(item.get("path") or "")
        if (
            item.get("inventory_status") != "ok"
            or item.get("checksum_conflict") is not False
            or item.get("declared_bytes_conflict") is not False
        ):
            raise CorpusExtractionError(f"unsafe provenance row: {path}")
        cursor = conn.execute(
            """
            UPDATE document_file_instances
            SET provenance_seen = 1,
                provenance_status = ?,
                public_url_edges = ?,
                public_https_edges = ?
            WHERE path = ?
              AND content_sha256 = ?
              AND bytes = ?
              AND provenance_seen = 0
            """,
            (
                str(item.get("provenance_status") or "unlinked"),
                int(item.get("public_url_edges") or 0),
                int(item.get("public_https_edges") or 0),
                path,
                str(item.get("sha256") or "").lower(),
                int(item.get("bytes") or 0),
            ),
        )
        if cursor.rowcount != 1:
            raise CorpusExtractionError(f"provenance row does not reconcile: {path}")
        provenance_rows += 1
        if provenance_rows % 5_000 == 0:
            conn.commit()
    conn.commit()

    missing_provenance = conn.execute(
        "SELECT COUNT(*) FROM document_file_instances WHERE provenance_seen = 0"
    ).fetchone()[0]
    if provenance_rows != inventory_rows or int(missing_provenance):
        raise CorpusExtractionError(
            "inventory/provenance path sets do not reconcile: "
            f"inventory={inventory_rows} provenance={provenance_rows} "
            f"missing={missing_provenance}"
        )

    inserted_work = 0
    cursor = conn.execute(
        """
        SELECT path, content_sha256, bytes, extension, mime_type, source_group
        FROM document_file_instances
        ORDER BY path
        """
    )
    now_iso = utc_now()
    for row in cursor:
        result = conn.execute(
            """
            INSERT OR IGNORE INTO document_text_work (
              content_sha256, representative_path, bytes, extension, mime_type,
              source_group, max_attempts, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["content_sha256"],
                row["path"],
                row["bytes"],
                row["extension"],
                row["mime_type"],
                row["source_group"],
                max_attempts,
                now_iso,
            ),
        )
        inserted_work += max(0, int(result.rowcount))
        if inserted_work and inserted_work % 5_000 == 0:
            conn.commit()
    conn.commit()

    distinct_contents = conn.execute(
        "SELECT COUNT(*) FROM document_text_work"
    ).fetchone()[0]
    _insert_metadata(
        conn,
        {
            "schema_version": "real_document_text_extraction_state_v1",
            "inventory_sha256": inventory_sha256,
            "provenance_sha256": provenance_sha256,
            "extraction_algorithm_version": DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
            "file_instances": inventory_rows,
            "distinct_content_objects": int(distinct_contents),
            "seeded_at": utc_now(),
            "synthetic_or_mock_records": 0,
            "official_public_domain_personal_information_retained": "true",
        },
    )
    conn.commit()
    return {
        "file_instances": inventory_rows,
        "distinct_content_objects": int(distinct_contents),
    }


def claim_work(
    conn: sqlite3.Connection,
    *,
    owner: str,
    limit: int,
    lease_seconds: int,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    now_iso = now.isoformat().replace("+00:00", "Z")
    expires = (
        (now + timedelta(seconds=lease_seconds)).isoformat().replace("+00:00", "Z")
    )
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        """
        UPDATE document_text_work
        SET state = 'pending', lease_owner = NULL, lease_expires_at = NULL,
            updated_at = ?
        WHERE state = 'leased' AND lease_expires_at <= ?
        """,
        (now_iso, now_iso),
    )
    rows = conn.execute(
        """
        SELECT content_sha256, representative_path, bytes, extension,
               mime_type, source_group, attempts, max_attempts
        FROM document_text_work
        WHERE state = 'pending' AND attempts < max_attempts
        ORDER BY content_sha256
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    if rows:
        conn.executemany(
            """
            UPDATE document_text_work
            SET state = 'leased', attempts = attempts + 1, lease_owner = ?,
                lease_expires_at = ?, started_at = COALESCE(started_at, ?),
                updated_at = ?
            WHERE content_sha256 = ? AND state = 'pending'
            """,
            [
                (owner, expires, now_iso, now_iso, str(row["content_sha256"]))
                for row in rows
            ],
        )
    conn.commit()
    return [dict(row) for row in rows]


def store_text_cas(text: str, output_root: Path) -> tuple[str, str]:
    encoded = text.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    relative = Path(digest[:2]) / digest[2:4] / f"{digest}.txt.gz"
    final_path = safe_child(output_root, relative.as_posix())
    if final_path.is_file():
        return digest, relative.as_posix()
    partial_root = output_root / ".partial"
    partial_root.mkdir(parents=True, exist_ok=True)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = partial_root / f"{uuid.uuid4().hex}.part"
    try:
        with partial_path.open("xb") as raw_handle:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw_handle, mtime=0
            ) as zipped:
                zipped.write(encoded)
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        if final_path.exists():
            partial_path.unlink(missing_ok=True)
        else:
            os.replace(partial_path, final_path)
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise
    return digest, relative.as_posix()


def extract_one(
    row: Mapping[str, Any],
    *,
    raw_root: Path,
    output_root: Path,
    max_input_bytes: int,
    max_text_chars: int,
) -> ExtractionOutcome:
    sha256 = str(row["content_sha256"])
    relative_path = str(row["representative_path"])
    try:
        raw_path = safe_child(raw_root, relative_path)
        if not raw_path.is_file():
            raise CorpusExtractionError("representative file missing")
        if raw_path.stat().st_size != int(row["bytes"]):
            raise CorpusExtractionError("representative file size drifted")
        if sha256_path(raw_path) != sha256:
            raise CorpusExtractionError("representative file checksum drifted")
        extraction: DocumentExtraction = extract_document_path(
            raw_path,
            content_type=str(row.get("mime_type") or ""),
            max_input_bytes=max_input_bytes,
            max_text_chars=max_text_chars,
        )
        if not extraction.text:
            return ExtractionOutcome(
                sha256,
                "native_no_text",
                None,
                None,
                0,
                extraction.method,
                extraction.truncated,
                None,
            )
        text_sha256, text_cas_path = store_text_cas(extraction.text, output_root)
        return ExtractionOutcome(
            sha256,
            "native_text_extracted",
            text_sha256,
            text_cas_path,
            extraction.text_chars,
            extraction.method,
            extraction.truncated,
            None,
        )
    except Exception as exc:  # noqa: BLE001
        return ExtractionOutcome(
            sha256,
            "failed",
            None,
            None,
            0,
            "",
            False,
            f"{type(exc).__name__}: {exc}"[:2_000],
        )


def persist_outcomes(
    conn: sqlite3.Connection,
    *,
    owner: str,
    outcomes: list[ExtractionOutcome],
) -> dict[str, int]:
    totals = {"succeeded": 0, "retried": 0, "dead": 0}
    now_iso = utc_now()
    conn.execute("BEGIN IMMEDIATE")
    for outcome in outcomes:
        if outcome.status != "failed":
            cursor = conn.execute(
                """
                UPDATE document_text_work
                SET state = 'succeeded', lease_owner = NULL,
                    lease_expires_at = NULL, extraction_status = ?,
                    text_sha256 = ?, text_cas_path = ?, text_chars = ?,
                    extraction_method = ?, text_truncated = ?, last_error = NULL,
                    completed_at = ?, updated_at = ?
                WHERE content_sha256 = ? AND state = 'leased'
                  AND lease_owner = ?
                """,
                (
                    outcome.status,
                    outcome.text_sha256,
                    outcome.text_cas_path,
                    outcome.text_chars,
                    outcome.method,
                    1 if outcome.truncated else 0,
                    now_iso,
                    now_iso,
                    outcome.content_sha256,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise CorpusExtractionError(
                    f"lost extraction lease: {outcome.content_sha256}"
                )
            totals["succeeded"] += 1
            continue
        row = conn.execute(
            "SELECT attempts, max_attempts FROM document_text_work "
            "WHERE content_sha256 = ? AND state = 'leased' AND lease_owner = ?",
            (outcome.content_sha256, owner),
        ).fetchone()
        if row is None:
            raise CorpusExtractionError(
                f"lost failed extraction lease: {outcome.content_sha256}"
            )
        dead = int(row["attempts"]) >= int(row["max_attempts"])
        conn.execute(
            """
            UPDATE document_text_work
            SET state = ?, lease_owner = NULL, lease_expires_at = NULL,
                extraction_status = 'failed', last_error = ?, updated_at = ?
            WHERE content_sha256 = ? AND lease_owner = ?
            """,
            (
                "dead" if dead else "pending",
                outcome.error,
                now_iso,
                outcome.content_sha256,
                owner,
            ),
        )
        totals["dead" if dead else "retried"] += 1
    conn.commit()
    return totals


def run_worker(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    output_root: Path,
    workers: int,
    claim_size: int,
    max_items: int,
    lease_seconds: int,
    max_input_bytes: int,
    max_text_chars: int,
) -> dict[str, int]:
    owner = f"real-document-text-{uuid.uuid4().hex}"
    totals = {
        "claimed": 0,
        "succeeded": 0,
        "retried": 0,
        "dead": 0,
        "raw_bytes_succeeded": 0,
    }
    while max_items <= 0 or totals["claimed"] < max_items:
        remaining = (
            claim_size
            if max_items <= 0
            else min(claim_size, max_items - totals["claimed"])
        )
        if remaining <= 0:
            break
        claimed = claim_work(
            conn, owner=owner, limit=remaining, lease_seconds=lease_seconds
        )
        if not claimed:
            break
        totals["claimed"] += len(claimed)
        outcomes: list[ExtractionOutcome] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = [
                executor.submit(
                    extract_one,
                    row,
                    raw_root=raw_root,
                    output_root=output_root,
                    max_input_bytes=max_input_bytes,
                    max_text_chars=max_text_chars,
                )
                for row in claimed
            ]
            for future in as_completed(futures):
                outcomes.append(future.result())
        persisted = persist_outcomes(conn, owner=owner, outcomes=outcomes)
        for key, value in persisted.items():
            totals[key] += value
        succeeded_hashes = {
            outcome.content_sha256 for outcome in outcomes if outcome.status != "failed"
        }
        totals["raw_bytes_succeeded"] += sum(
            int(row["bytes"])
            for row in claimed
            if str(row["content_sha256"]) in succeeded_hashes
        )
    return totals


def iter_manifest_rows(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    cursor = conn.execute(
        """
        SELECT
          f.path, f.content_sha256, f.bytes, f.extension, f.mime_type,
          f.source_group, f.quality_class, f.inventory_text_chars,
          f.page_count, f.ocr_candidate_pages_json,
          f.provenance_status, f.public_url_edges,
          f.public_https_edges, w.state, w.attempts,
          w.extraction_status, w.text_sha256, w.text_cas_path,
          w.text_chars, w.extraction_method, w.text_truncated,
          w.last_error
        FROM document_file_instances f
        JOIN document_text_work w
          ON w.content_sha256 = f.content_sha256
        ORDER BY f.path
        """
    )
    for row in cursor:
        yield {
            "schema_version": "real_document_text_manifest_row_v1",
            "path": row["path"],
            "source_group": row["source_group"],
            "extension": row["extension"],
            "mime_type": row["mime_type"],
            "bytes": int(row["bytes"]),
            "content_sha256": row["content_sha256"],
            "quality_class": row["quality_class"],
            "inventory_text_chars": row["inventory_text_chars"],
            "page_count": row["page_count"],
            "ocr_candidate_pages": json.loads(row["ocr_candidate_pages_json"]),
            "provenance_status": row["provenance_status"],
            "public_url_edges": int(row["public_url_edges"]),
            "public_https_edges": int(row["public_https_edges"]),
            "work_state": row["state"],
            "attempts": int(row["attempts"]),
            "native_extraction_status": row["extraction_status"],
            "native_text_sha256": row["text_sha256"],
            "native_text_cas_path": row["text_cas_path"],
            "native_text_chars": row["text_chars"],
            "native_extraction_method": row["extraction_method"],
            "native_extraction_algorithm_version": (
                DOCUMENT_EXTRACTION_ALGORITHM_VERSION
            ),
            "native_text_truncated": (
                bool(row["text_truncated"])
                if row["text_truncated"] is not None
                else None
            ),
            "last_error": row["last_error"],
            "synthetic_or_mock": False,
            "official_public_domain_personal_information_retained": True,
        }


def terminal_state(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN state = 'succeeded' THEN 1 ELSE 0 END) AS succeeded
        FROM document_text_work
        """
    ).fetchone()
    return int(row["total"] or 0) > 0 and int(row["total"] or 0) == int(
        row["succeeded"] or 0
    )


def write_manifest(
    conn: sqlite3.Connection,
    out_path: Path,
    *,
    max_rows: int,
    max_uncompressed_bytes: int,
) -> dict[str, Any]:
    manifest = publish_generation_manifest(
        manifest_path=out_path,
        rows=iter_manifest_rows(conn),
        dataset="native_text",
        row_schema_version="real_document_text_manifest_row_v1",
        state_connection=conn,
        max_rows=max_rows,
        max_uncompressed_bytes=max_uncompressed_bytes,
        policy={
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "native_text_is_not_sanitized_or_identity_stripped": True,
            "automatic_deletion_forbidden": True,
        },
    )
    manifest["path"] = display_path(out_path)
    return manifest


def build_report(
    conn: sqlite3.Connection,
    *,
    inventory_path: Path,
    provenance_path: Path,
    state_db: Path,
    output_root: Path,
    manifest: dict[str, Any],
    run_totals: dict[str, int],
    performance: dict[str, Any],
) -> dict[str, Any]:
    metadata = _metadata(conn)
    state_counts = {
        str(row["state"]): int(row["total"])
        for row in conn.execute(
            "SELECT state, COUNT(*) AS total FROM document_text_work GROUP BY state"
        )
    }
    extraction_counts = {
        str(row["extraction_status"] or "not_processed"): int(row["total"])
        for row in conn.execute(
            "SELECT extraction_status, COUNT(*) AS total "
            "FROM document_text_work GROUP BY extraction_status"
        )
    }
    totals_row = conn.execute(
        """
        SELECT
          COUNT(*) AS distinct_content_objects,
          COALESCE(SUM(bytes), 0) AS raw_content_bytes,
          COALESCE(SUM(text_chars), 0) AS native_text_chars,
          SUM(CASE WHEN text_truncated = 1 THEN 1 ELSE 0 END) AS truncated_objects,
          SUM(CASE WHEN extraction_status = 'native_no_text' THEN 1 ELSE 0 END)
            AS no_text_objects
        FROM document_text_work
        """
    ).fetchone()
    instance_row = conn.execute(
        """
        SELECT
          COUNT(*) AS file_instances,
          SUM(CASE WHEN public_url_edges > 0 THEN 1 ELSE 0 END)
            AS public_url_instances,
          SUM(CASE WHEN public_url_edges = 0 THEN 1 ELSE 0 END)
            AS provenance_gap_instances,
          SUM(json_array_length(ocr_candidate_pages_json))
            AS ocr_candidate_pages
        FROM document_file_instances
        """
    ).fetchone()
    current_cas_paths = {
        str(row["text_cas_path"])
        for row in conn.execute(
            """
            SELECT DISTINCT text_cas_path FROM document_text_work
            WHERE text_cas_path IS NOT NULL
            """
        )
    }
    cas_files = len(current_cas_paths)
    cas_bytes = sum(
        safe_child(output_root, relative).stat().st_size
        for relative in current_cas_paths
    )
    retained_cas_files = 0
    retained_cas_bytes = 0
    if output_root.is_dir():
        for path in output_root.rglob("*.txt.gz"):
            if path.is_file():
                retained_cas_files += 1
                retained_cas_bytes += path.stat().st_size
    complete = (
        state_counts.get("succeeded", 0) == int(totals_row["distinct_content_objects"])
        and state_counts.get("dead", 0) == 0
        and state_counts.get("pending", 0) == 0
        and state_counts.get("leased", 0) == 0
    )
    checks = {
        "inventory_and_provenance_inputs_bound_by_sha256": (
            metadata.get("inventory_sha256") == sha256_path(inventory_path)
            and metadata.get("provenance_sha256") == sha256_path(provenance_path)
        ),
        "extraction_algorithm_version_bound": metadata.get(
            "extraction_algorithm_version"
        )
        == DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
        "all_file_instances_manifested": (
            int(instance_row["file_instances"]) == int(manifest["rows"])
        ),
        "all_distinct_content_objects_terminal_success": complete,
        "no_dead_work": state_counts.get("dead", 0) == 0,
        "no_native_text_truncation": int(totals_row["truncated_objects"] or 0) == 0,
        "no_synthetic_or_mock_records": True,
        "official_public_domain_personal_information_retained": True,
    }
    succeeded_this_run = int(run_totals.get("succeeded", 0))
    elapsed_seconds = float(performance["elapsed_seconds"])
    corpus_bytes = int(totals_row["raw_content_bytes"] or 0)
    measured_bytes = int(run_totals.get("raw_bytes_succeeded", 0))
    performance = {
        **performance,
        "items_per_second": round(succeeded_this_run / elapsed_seconds, 6),
        "raw_bytes_per_second": round(measured_bytes / elapsed_seconds, 6),
    }
    return {
        "schema_version": "real_document_text_extraction_v1",
        "generated_at": utc_now(),
        "status": "ok" if all(checks.values()) else "partial",
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "native_text_is_not_sanitized_or_identity_stripped": True,
            "raw_document_bytes_are_not_copied_into_work_rows": True,
            "content_deduplicated_processing": True,
            "pdf_plain_text_angle_brackets_retained": True,
        },
        "extraction_algorithm_version": DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
        "inputs": {
            "inventory": {
                "path": display_path(inventory_path),
                "bytes": inventory_path.stat().st_size,
                "sha256": metadata.get("inventory_sha256"),
            },
            "provenance": {
                "path": display_path(provenance_path),
                "bytes": provenance_path.stat().st_size,
                "sha256": metadata.get("provenance_sha256"),
            },
        },
        "state": {
            "database": display_path(state_db),
            "state_counts": state_counts,
            "extraction_counts": extraction_counts,
        },
        "manifest": manifest,
        "run": run_totals,
        "performance": performance,
        "totals": {
            "file_instances": int(instance_row["file_instances"]),
            "distinct_content_objects": int(totals_row["distinct_content_objects"]),
            "duplicate_file_instances": int(instance_row["file_instances"])
            - int(totals_row["distinct_content_objects"]),
            "raw_content_bytes": corpus_bytes,
            "public_url_instances": int(instance_row["public_url_instances"] or 0),
            "provenance_gap_instances": int(
                instance_row["provenance_gap_instances"] or 0
            ),
            "native_text_chars": int(totals_row["native_text_chars"]),
            "native_no_text_objects": int(totals_row["no_text_objects"] or 0),
            "native_truncated_objects": int(totals_row["truncated_objects"] or 0),
            "ocr_candidate_pages": int(instance_row["ocr_candidate_pages"] or 0),
            "text_cas_files": cas_files,
            "text_cas_bytes": cas_bytes,
            "text_cas_files_observed_across_retained_generations": (
                retained_cas_files
            ),
            "text_cas_bytes_observed_across_retained_generations": (
                retained_cas_bytes
            ),
        },
        "checks": checks,
        "next_action": (
            "Independently validate every manifest row and text CAS object, then OCR "
            "every distinct empty or sparse PDF page without replacing native text."
        ),
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    positive_values = (
        int(args.workers),
        int(args.claim_size),
        int(args.max_attempts),
        int(args.lease_seconds),
        int(args.max_input_bytes),
        int(args.max_text_chars),
        int(args.manifest_shard_max_rows),
        int(args.manifest_shard_max_uncompressed_bytes),
    )
    if any(value < 1 for value in positive_values) or int(args.max_items) < 0:
        print("ERROR: worker, lease, size, and attempt values are invalid")
        return 2

    raw_root = Path(args.raw_root)
    inventory_path = Path(args.inventory)
    provenance_path = Path(args.provenance)
    state_db = Path(args.state_db)
    output_root = Path(args.output_root)
    manifest_out = Path(args.manifest_out)
    report_out = Path(args.report_out)
    if not raw_root.is_dir():
        print(f"ERROR: raw root missing: {display_path(raw_root)}")
        return 2

    try:
        output_root_preexisting = output_root.exists()
        state_db_preexisting = state_db.exists()
        started = time.monotonic()
        usage_before = process_usage()
        output_root.mkdir(parents=True, exist_ok=True)
        with open_state_db(state_db) as conn:
            apply_state_schema(conn)
            seeded = seed_state(
                conn,
                raw_root=raw_root,
                inventory_path=inventory_path,
                provenance_path=provenance_path,
                max_attempts=int(args.max_attempts),
            )
            run_totals = run_worker(
                conn,
                raw_root=raw_root,
                output_root=output_root,
                workers=int(args.workers),
                claim_size=int(args.claim_size),
                max_items=int(args.max_items),
                lease_seconds=int(args.lease_seconds),
                max_input_bytes=int(args.max_input_bytes),
                max_text_chars=int(args.max_text_chars),
            )
            if terminal_state(conn):
                manifest = write_manifest(
                    conn,
                    manifest_out,
                    max_rows=int(args.manifest_shard_max_rows),
                    max_uncompressed_bytes=int(
                        args.manifest_shard_max_uncompressed_bytes
                    ),
                )
            else:
                manifest = {
                    "path": display_path(manifest_out),
                    "rows": -1,
                    "bytes": 0,
                    "sha256": None,
                    "publication": {
                        "activated": False,
                        "reason": "nonterminal_work_state",
                        "live_index_preserved": manifest_out.is_file(),
                        "automatic_deletion_performed": False,
                    },
                }
            usage_after = process_usage()
            performance = {
                "measurement_scope": "seed_extract_and_manifest",
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "cpu_seconds": round(
                    float(usage_after["cpu_seconds"])
                    - float(usage_before["cpu_seconds"]),
                    6,
                ),
                "peak_rss_bytes_self": usage_after["peak_rss_bytes_self"],
                "peak_rss_bytes_child_max": usage_after["peak_rss_bytes_child_max"],
                "workers": int(args.workers),
                "claim_size": int(args.claim_size),
                "state_db_preexisting": state_db_preexisting,
                "output_root_preexisting": output_root_preexisting,
                "cold_state_and_output": not state_db_preexisting
                and not output_root_preexisting,
            }
            report = build_report(
                conn,
                inventory_path=inventory_path,
                provenance_path=provenance_path,
                state_db=state_db,
                output_root=output_root,
                manifest=manifest,
                run_totals=run_totals,
                performance=performance,
            )
        report["seed"] = seeded
        write_json_atomic(report_out, report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        if args.enforce and report["status"] != "ok":
            return 1
        return 0
    except (
        CorpusExtractionError,
        GenerationManifestError,
        OSError,
        sqlite3.Error,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
