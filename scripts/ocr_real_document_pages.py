#!/usr/bin/env python3
"""Run resumable additive OCR for every real sparse or empty PDF page."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import resource
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_ROOT = Path("etl/data/raw")
DEFAULT_NATIVE_MANIFEST = Path(
    "etl/data/published/real-document-text-manifest-latest.jsonl"
)
DEFAULT_STATE_DB = Path("etl/data/staging/real-document-page-ocr-v2.db")
DEFAULT_OUTPUT_ROOT = Path("etl/data/derived/real-document-page-ocr-v2")
DEFAULT_MANIFEST = Path(
    "etl/data/published/real-document-page-ocr-manifest-latest.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr.json"
)
SHA256_HEX_LENGTH = 64


class CorpusOcrError(RuntimeError):
    """Raised when full page OCR cannot make an exact real-data claim."""


@dataclass(frozen=True)
class OcrOutcome:
    document_sha256: str
    page_number: int
    status: str
    ocr_text_sha256: str | None
    ocr_text_cas_path: str | None
    ocr_text_chars: int
    improved_over_native: bool
    elapsed_seconds: float
    error: str | None


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def process_usage() -> dict[str, float | int]:
    """Return cumulative parent/child CPU and peak-memory telemetry."""
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


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.name


def safe_child(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise CorpusOcrError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise CorpusOcrError(f"path escapes root: {relative}") from exc
    return candidate


def sha256_path(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--native-manifest", default=str(DEFAULT_NATIVE_MANIFEST))
    parser.add_argument("--state-db", default=str(DEFAULT_STATE_DB))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--claim-size", type=int, default=16)
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--language", default="spa+cat+glg+eus+eng")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        raise CorpusOcrError(f"missing native manifest: {display_path(path)}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CorpusOcrError(
                    f"invalid JSONL at {display_path(path)}:{line_number}: {exc}"
                ) from exc
            if not isinstance(item, dict):
                raise CorpusOcrError(
                    f"JSONL row must be an object: {display_path(path)}:{line_number}"
                )
            yield item


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
        CREATE TABLE IF NOT EXISTS ocr_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ocr_documents (
          document_sha256 TEXT PRIMARY KEY,
          representative_path TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          source_group TEXT NOT NULL,
          page_count INTEGER NOT NULL,
          CHECK (bytes >= 0),
          CHECK (page_count >= 1)
        );

        CREATE TABLE IF NOT EXISTS ocr_page_work (
          document_sha256 TEXT NOT NULL,
          page_number INTEGER NOT NULL,
          reason TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,
          max_attempts INTEGER NOT NULL,
          lease_owner TEXT,
          lease_expires_at TEXT,
          ocr_status TEXT,
          ocr_text_sha256 TEXT,
          ocr_text_cas_path TEXT,
          ocr_text_chars INTEGER,
          improved_over_native INTEGER,
          elapsed_seconds REAL,
          last_error TEXT,
          started_at TEXT,
          completed_at TEXT,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (document_sha256, page_number),
          FOREIGN KEY (document_sha256)
            REFERENCES ocr_documents(document_sha256),
          CHECK (page_number >= 1),
          CHECK (native_text_chars >= 0),
          CHECK (state IN ('pending', 'leased', 'succeeded', 'dead')),
          CHECK (attempts >= 0),
          CHECK (max_attempts >= 1)
        );

        CREATE INDEX IF NOT EXISTS idx_ocr_page_work_claim
          ON ocr_page_work(state, lease_expires_at, document_sha256, page_number);
        """
    )
    conn.commit()


def _metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row["key"]): str(row["value"])
        for row in conn.execute("SELECT key, value FROM ocr_metadata")
    }


def seed_state(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    native_manifest: Path,
    max_attempts: int,
) -> dict[str, int]:
    manifest_sha256 = sha256_path(native_manifest)
    metadata = _metadata(conn)
    if metadata:
        if metadata.get("native_manifest_sha256") != manifest_sha256:
            raise CorpusOcrError(
                "state DB belongs to a different native manifest; use a new "
                "--state-db so prior OCR evidence remains immutable"
            )
        return {
            "documents": int(metadata["documents"]),
            "candidate_pages": int(metadata["candidate_pages"]),
        }

    now_iso = utc_now()
    manifest_rows = 0
    candidate_rows = 0
    for item in iter_jsonl(native_manifest):
        manifest_rows += 1
        path = str(item.get("path") or "")
        document_sha256 = str(item.get("content_sha256") or "").lower()
        page_count = item.get("page_count")
        candidates = item.get("ocr_candidate_pages")
        if (
            item.get("schema_version") != "real_document_text_manifest_row_v1"
            or item.get("synthetic_or_mock") is not False
            or item.get("official_public_domain_personal_information_retained")
            is not True
            or item.get("work_state") != "succeeded"
            or len(document_sha256) != SHA256_HEX_LENGTH
            or not isinstance(candidates, list)
        ):
            raise CorpusOcrError(f"unsafe native manifest row: {path}")
        if not candidates:
            continue
        if item.get("mime_type") != "application/pdf" or not isinstance(
            page_count, int
        ):
            raise CorpusOcrError(f"OCR candidate is not a PDF page set: {path}")
        result = conn.execute(
            """
            INSERT OR IGNORE INTO ocr_documents (
              document_sha256, representative_path, bytes, source_group,
              page_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_sha256,
                path,
                int(item.get("bytes") or 0),
                str(item.get("source_group") or "unknown"),
                page_count,
            ),
        )
        if result.rowcount == 0:
            existing = conn.execute(
                """
                SELECT bytes, page_count FROM ocr_documents
                WHERE document_sha256 = ?
                """,
                (document_sha256,),
            ).fetchone()
            if (
                existing is None
                or int(existing["bytes"]) != int(item.get("bytes") or 0)
                or int(existing["page_count"]) != page_count
            ):
                raise CorpusOcrError(f"duplicate document drift: {path}")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise CorpusOcrError(f"invalid OCR candidate: {path}")
            page_number = int(candidate.get("page_number") or 0)
            native_chars = int(candidate.get("source_text_chars") or 0)
            reason = str(candidate.get("reason") or "")
            if (
                page_number < 1
                or page_number > page_count
                or native_chars < 0
                or reason not in {"empty_text", "sparse_text"}
            ):
                raise CorpusOcrError(f"invalid OCR page contract: {path}:{page_number}")
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO ocr_page_work (
                  document_sha256, page_number, reason, native_text_chars,
                  max_attempts, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    document_sha256,
                    page_number,
                    reason,
                    native_chars,
                    max_attempts,
                    now_iso,
                ),
            )
            if cursor.rowcount == 0:
                existing = conn.execute(
                    """
                    SELECT reason, native_text_chars FROM ocr_page_work
                    WHERE document_sha256 = ? AND page_number = ?
                    """,
                    (document_sha256, page_number),
                ).fetchone()
                if (
                    existing is None
                    or str(existing["reason"]) != reason
                    or int(existing["native_text_chars"]) != native_chars
                ):
                    raise CorpusOcrError(
                        f"duplicate OCR page drift: {path}:{page_number}"
                    )
            else:
                candidate_rows += 1
        if manifest_rows % 5_000 == 0:
            conn.commit()
    conn.commit()

    documents = conn.execute("SELECT COUNT(*) FROM ocr_documents").fetchone()[0]
    pages = conn.execute("SELECT COUNT(*) FROM ocr_page_work").fetchone()[0]
    for row in conn.execute(
        "SELECT document_sha256, representative_path, bytes FROM ocr_documents"
    ):
        raw_path = safe_child(raw_root, str(row["representative_path"]))
        if (
            not raw_path.is_file()
            or raw_path.stat().st_size != int(row["bytes"])
            or sha256_path(raw_path) != str(row["document_sha256"])
        ):
            raise CorpusOcrError(f"OCR source file drift: {row['representative_path']}")
    conn.executemany(
        "INSERT INTO ocr_metadata (key, value) VALUES (?, ?)",
        [
            ("schema_version", "real_document_page_ocr_state_v1"),
            ("native_manifest_sha256", manifest_sha256),
            ("native_manifest_rows", str(manifest_rows)),
            ("documents", str(documents)),
            ("candidate_pages", str(pages)),
            ("seeded_at", utc_now()),
            ("synthetic_or_mock_records", "0"),
            ("official_public_domain_personal_information_retained", "true"),
        ],
    )
    conn.commit()
    if int(pages) != candidate_rows:
        raise CorpusOcrError("candidate page seed totals do not reconcile")
    return {"documents": int(documents), "candidate_pages": int(pages)}


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
        UPDATE ocr_page_work
        SET state = 'pending', lease_owner = NULL, lease_expires_at = NULL,
            updated_at = ?
        WHERE state = 'leased' AND lease_expires_at <= ?
        """,
        (now_iso, now_iso),
    )
    rows = conn.execute(
        """
        SELECT w.document_sha256, w.page_number, w.reason,
               w.native_text_chars, w.attempts, w.max_attempts,
               d.representative_path, d.bytes, d.source_group, d.page_count
        FROM ocr_page_work w
        JOIN ocr_documents d USING (document_sha256)
        WHERE w.state = 'pending' AND w.attempts < w.max_attempts
        ORDER BY w.document_sha256, w.page_number
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    if rows:
        conn.executemany(
            """
            UPDATE ocr_page_work
            SET state = 'leased', attempts = attempts + 1, lease_owner = ?,
                lease_expires_at = ?, started_at = COALESCE(started_at, ?),
                updated_at = ?
            WHERE document_sha256 = ? AND page_number = ? AND state = 'pending'
            """,
            [
                (
                    owner,
                    expires,
                    now_iso,
                    now_iso,
                    str(row["document_sha256"]),
                    int(row["page_number"]),
                )
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


def ocr_one(
    row: Mapping[str, Any],
    *,
    raw_root: Path,
    output_root: Path,
    pdftoppm: str,
    tesseract: str,
    dpi: int,
    language: str,
    psm: int,
    timeout: float,
) -> OcrOutcome:
    started = time.monotonic()
    document_sha256 = str(row["document_sha256"])
    page_number = int(row["page_number"])
    try:
        pdf_path = safe_child(raw_root, str(row["representative_path"]))
        with tempfile.TemporaryDirectory(prefix="vota-real-page-ocr-") as temp_dir:
            image_prefix = Path(temp_dir) / "page"
            image_path = image_prefix.with_suffix(".png")
            render = subprocess.run(
                [
                    pdftoppm,
                    "-f",
                    str(page_number),
                    "-l",
                    str(page_number),
                    "-r",
                    str(dpi),
                    "-png",
                    "-singlefile",
                    str(pdf_path),
                    str(image_prefix),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if render.returncode != 0 or not image_path.is_file():
                raise RuntimeError(render.stderr.strip() or "pdftoppm failed")
            ocr = subprocess.run(
                [
                    tesseract,
                    str(image_path),
                    "stdout",
                    "-l",
                    language,
                    "--psm",
                    str(psm),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if ocr.returncode != 0:
                raise RuntimeError(ocr.stderr.strip() or "tesseract failed")
            normalized = " ".join(ocr.stdout.split())
        native_chars = int(row["native_text_chars"])
        if not normalized:
            return OcrOutcome(
                document_sha256,
                page_number,
                "ocr_no_text",
                None,
                None,
                0,
                False,
                round(time.monotonic() - started, 4),
                None,
            )
        text_sha256, text_cas_path = store_text_cas(normalized, output_root)
        return OcrOutcome(
            document_sha256,
            page_number,
            "ocr_text_extracted",
            text_sha256,
            text_cas_path,
            len(normalized),
            len(normalized) >= native_chars + 50,
            round(time.monotonic() - started, 4),
            None,
        )
    except Exception as exc:  # noqa: BLE001
        return OcrOutcome(
            document_sha256,
            page_number,
            "failed",
            None,
            None,
            0,
            False,
            round(time.monotonic() - started, 4),
            f"{type(exc).__name__}: {exc}"[:2_000],
        )


def persist_outcomes(
    conn: sqlite3.Connection,
    *,
    owner: str,
    outcomes: list[OcrOutcome],
) -> dict[str, int]:
    totals = {"succeeded": 0, "retried": 0, "dead": 0}
    now_iso = utc_now()
    conn.execute("BEGIN IMMEDIATE")
    for outcome in outcomes:
        identity = (outcome.document_sha256, outcome.page_number)
        if outcome.status != "failed":
            cursor = conn.execute(
                """
                UPDATE ocr_page_work
                SET state = 'succeeded', lease_owner = NULL,
                    lease_expires_at = NULL, ocr_status = ?,
                    ocr_text_sha256 = ?, ocr_text_cas_path = ?,
                    ocr_text_chars = ?, improved_over_native = ?,
                    elapsed_seconds = ?, last_error = NULL, completed_at = ?,
                    updated_at = ?
                WHERE document_sha256 = ? AND page_number = ?
                  AND state = 'leased' AND lease_owner = ?
                """,
                (
                    outcome.status,
                    outcome.ocr_text_sha256,
                    outcome.ocr_text_cas_path,
                    outcome.ocr_text_chars,
                    1 if outcome.improved_over_native else 0,
                    outcome.elapsed_seconds,
                    now_iso,
                    now_iso,
                    *identity,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise CorpusOcrError(f"lost OCR lease: {identity[0]}:{identity[1]}")
            totals["succeeded"] += 1
            continue
        row = conn.execute(
            """
            SELECT attempts, max_attempts FROM ocr_page_work
            WHERE document_sha256 = ? AND page_number = ?
              AND state = 'leased' AND lease_owner = ?
            """,
            (*identity, owner),
        ).fetchone()
        if row is None:
            raise CorpusOcrError(f"lost failed OCR lease: {identity[0]}:{identity[1]}")
        dead = int(row["attempts"]) >= int(row["max_attempts"])
        conn.execute(
            """
            UPDATE ocr_page_work
            SET state = ?, lease_owner = NULL, lease_expires_at = NULL,
                ocr_status = 'failed', elapsed_seconds = ?, last_error = ?,
                updated_at = ?
            WHERE document_sha256 = ? AND page_number = ? AND lease_owner = ?
            """,
            (
                "dead" if dead else "pending",
                outcome.elapsed_seconds,
                outcome.error,
                now_iso,
                *identity,
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
    pdftoppm: str,
    tesseract: str,
    dpi: int,
    language: str,
    psm: int,
    timeout: float,
) -> dict[str, int]:
    owner = f"real-document-ocr-{uuid.uuid4().hex}"
    totals = {"claimed": 0, "succeeded": 0, "retried": 0, "dead": 0}
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
        outcomes: list[OcrOutcome] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = [
                executor.submit(
                    ocr_one,
                    row,
                    raw_root=raw_root,
                    output_root=output_root,
                    pdftoppm=pdftoppm,
                    tesseract=tesseract,
                    dpi=dpi,
                    language=language,
                    psm=psm,
                    timeout=timeout,
                )
                for row in claimed
            ]
            for future in as_completed(futures):
                outcomes.append(future.result())
        persisted = persist_outcomes(conn, owner=owner, outcomes=outcomes)
        for key, value in persisted.items():
            totals[key] += value
    return totals


def tool_version(command: str, version_arg: str = "--version") -> str:
    completed = subprocess.run(
        [command, version_arg],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    text = completed.stdout or completed.stderr
    return text.splitlines()[0].strip() if text else "unknown"


def write_manifest(conn: sqlite3.Connection, out_path: Path) -> dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{out_path.name}.", suffix=".tmp", dir=out_path.parent
    )
    os.close(file_descriptor)
    temp_path = Path(temp_name)
    rows = 0
    digest = hashlib.sha256()
    try:
        with temp_path.open("wb") as handle:
            cursor = conn.execute(
                """
                SELECT
                  d.document_sha256, d.representative_path, d.bytes,
                  d.source_group, d.page_count, w.page_number, w.reason,
                  w.native_text_chars, w.state, w.attempts, w.ocr_status,
                  w.ocr_text_sha256, w.ocr_text_cas_path, w.ocr_text_chars,
                  w.improved_over_native, w.last_error
                FROM ocr_page_work w
                JOIN ocr_documents d USING (document_sha256)
                ORDER BY d.document_sha256, w.page_number
                """
            )
            for row in cursor:
                payload = {
                    "schema_version": "real_document_page_ocr_manifest_row_v1",
                    "document_sha256": row["document_sha256"],
                    "representative_path": row["representative_path"],
                    "document_bytes": int(row["bytes"]),
                    "source_group": row["source_group"],
                    "document_page_count": int(row["page_count"]),
                    "page_number": int(row["page_number"]),
                    "routing_reason": row["reason"],
                    "native_text_chars": int(row["native_text_chars"]),
                    "work_state": row["state"],
                    "attempts": int(row["attempts"]),
                    "ocr_status": row["ocr_status"],
                    "ocr_text_sha256": row["ocr_text_sha256"],
                    "ocr_text_cas_path": row["ocr_text_cas_path"],
                    "ocr_text_chars": row["ocr_text_chars"],
                    "improved_over_native": (
                        bool(row["improved_over_native"])
                        if row["improved_over_native"] is not None
                        else None
                    ),
                    "last_error": row["last_error"],
                    "additive_to_native_text": True,
                    "synthetic_or_mock": False,
                    "official_public_domain_personal_information_retained": True,
                }
                encoded = (
                    json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n"
                ).encode("utf-8")
                handle.write(encoded)
                digest.update(encoded)
                rows += 1
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, out_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return {
        "path": display_path(out_path),
        "rows": rows,
        "bytes": out_path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def build_report(
    conn: sqlite3.Connection,
    *,
    native_manifest: Path,
    state_db: Path,
    output_root: Path,
    manifest: dict[str, Any],
    run_totals: dict[str, int],
    dpi: int,
    language: str,
    psm: int,
    pdftoppm: str,
    tesseract: str,
    performance: dict[str, Any],
) -> dict[str, Any]:
    metadata = _metadata(conn)
    state_counts = {
        str(row["state"]): int(row["total"])
        for row in conn.execute(
            "SELECT state, COUNT(*) AS total FROM ocr_page_work GROUP BY state"
        )
    }
    status_counts = {
        str(row["ocr_status"] or "not_processed"): int(row["total"])
        for row in conn.execute(
            "SELECT ocr_status, COUNT(*) AS total FROM ocr_page_work GROUP BY ocr_status"
        )
    }
    totals_row = conn.execute(
        """
        SELECT
          COUNT(*) AS candidate_pages,
          SUM(CASE WHEN reason = 'empty_text' THEN 1 ELSE 0 END)
            AS empty_text_pages,
          SUM(CASE WHEN reason = 'sparse_text' THEN 1 ELSE 0 END)
            AS sparse_text_pages,
          SUM(native_text_chars) AS native_text_chars,
          SUM(COALESCE(ocr_text_chars, 0)) AS ocr_text_chars,
          SUM(CASE WHEN improved_over_native = 1 THEN 1 ELSE 0 END)
            AS improved_pages,
          SUM(COALESCE(elapsed_seconds, 0)) AS elapsed_seconds
        FROM ocr_page_work
        """
    ).fetchone()
    documents = conn.execute("SELECT COUNT(*) FROM ocr_documents").fetchone()[0]
    cas_files = 0
    cas_bytes = 0
    if output_root.is_dir():
        for path in output_root.rglob("*.txt.gz"):
            if path.is_file():
                cas_files += 1
                cas_bytes += path.stat().st_size
    complete = (
        state_counts.get("succeeded", 0) == int(totals_row["candidate_pages"])
        and state_counts.get("dead", 0) == 0
        and state_counts.get("pending", 0) == 0
        and state_counts.get("leased", 0) == 0
    )
    checks = {
        "native_manifest_bound_by_sha256": (
            metadata.get("native_manifest_sha256") == sha256_path(native_manifest)
        ),
        "all_candidate_pages_manifested": (
            int(totals_row["candidate_pages"]) == int(manifest["rows"])
        ),
        "all_candidate_pages_terminal_success": complete,
        "no_dead_work": state_counts.get("dead", 0) == 0,
        "ocr_is_additive_and_native_text_is_unchanged": True,
        "no_synthetic_or_mock_records": True,
        "official_public_domain_personal_information_retained": True,
    }
    succeeded_this_run = int(run_totals.get("succeeded", 0))
    elapsed_seconds = float(performance["elapsed_seconds"])
    performance = {
        **performance,
        "pages_per_second": round(succeeded_this_run / elapsed_seconds, 6),
    }
    return {
        "schema_version": "real_document_page_ocr_v1",
        "generated_at": utc_now(),
        "status": "ok" if all(checks.values()) else "partial",
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "ocr_text_is_not_sanitized_or_identity_stripped": True,
            "ocr_is_additive_to_native_text": True,
            "raw_document_bytes_are_not_copied_into_work_rows": True,
        },
        "inputs": {
            "native_manifest": {
                "path": display_path(native_manifest),
                "bytes": native_manifest.stat().st_size,
                "sha256": metadata.get("native_manifest_sha256"),
                "rows": int(metadata.get("native_manifest_rows", 0)),
            }
        },
        "configuration": {
            "dpi": dpi,
            "language": language,
            "page_segmentation_mode": psm,
            "tool_versions": {
                "pdftoppm": tool_version(pdftoppm, "-v"),
                "tesseract": tool_version(tesseract),
            },
        },
        "state": {
            "database": display_path(state_db),
            "state_counts": state_counts,
            "ocr_status_counts": status_counts,
        },
        "manifest": manifest,
        "run": run_totals,
        "performance": performance,
        "totals": {
            "documents": int(documents),
            "candidate_pages": int(totals_row["candidate_pages"]),
            "empty_text_pages": int(totals_row["empty_text_pages"] or 0),
            "sparse_text_pages": int(totals_row["sparse_text_pages"] or 0),
            "native_text_chars_on_candidate_pages": int(
                totals_row["native_text_chars"] or 0
            ),
            "ocr_text_chars": int(totals_row["ocr_text_chars"] or 0),
            "pages_improved_over_native_by_50_chars": int(
                totals_row["improved_pages"] or 0
            ),
            "elapsed_worker_seconds": round(
                float(totals_row["elapsed_seconds"] or 0), 4
            ),
            "ocr_text_cas_files": cas_files,
            "ocr_text_cas_bytes": cas_bytes,
        },
        "checks": checks,
        "limitations": [
            "More OCR characters do not prove semantic accuracy.",
            "Native text remains the primary extraction; OCR is page-level additive evidence.",
            "Volatile per-page elapsed time stays in the state database and aggregate report; it is excluded from the deterministic semantic manifest.",
            "Human review must measure OCR accuracy by source, language, scan quality, and document type before analytical promotion.",
        ],
        "next_action": (
            "Independently validate every page row and OCR text CAS object, then "
            "human-review a stratified real-page sample before analytical promotion."
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
    positive = (
        int(args.workers),
        int(args.claim_size),
        int(args.max_attempts),
        int(args.lease_seconds),
        int(args.dpi),
        int(args.psm),
    )
    if (
        any(value < 1 for value in positive)
        or int(args.max_items) < 0
        or float(args.timeout) <= 0
    ):
        print("ERROR: worker, lease, OCR, and attempt values are invalid")
        return 2
    raw_root = Path(args.raw_root)
    native_manifest = Path(args.native_manifest)
    state_db = Path(args.state_db)
    output_root = Path(args.output_root)
    manifest_out = Path(args.manifest_out)
    report_out = Path(args.report_out)
    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    if (
        not raw_root.is_dir()
        or not native_manifest.is_file()
        or not pdftoppm
        or not tesseract
    ):
        print("ERROR: raw root, native manifest, pdftoppm, and tesseract are required")
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
                native_manifest=native_manifest,
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
                pdftoppm=pdftoppm,
                tesseract=tesseract,
                dpi=int(args.dpi),
                language=str(args.language),
                psm=int(args.psm),
                timeout=float(args.timeout),
            )
            manifest = write_manifest(conn, manifest_out)
            usage_after = process_usage()
            performance = {
                "measurement_scope": "seed_ocr_and_manifest",
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "cpu_seconds": round(
                    float(usage_after["cpu_seconds"])
                    - float(usage_before["cpu_seconds"]),
                    6,
                ),
                "peak_rss_bytes_self": usage_after["peak_rss_bytes_self"],
                "peak_rss_bytes_child_max": usage_after[
                    "peak_rss_bytes_child_max"
                ],
                "workers": int(args.workers),
                "claim_size": int(args.claim_size),
                "state_db_preexisting": state_db_preexisting,
                "output_root_preexisting": output_root_preexisting,
                "cold_state_and_output": not state_db_preexisting
                and not output_root_preexisting,
            }
            report = build_report(
                conn,
                native_manifest=native_manifest,
                state_db=state_db,
                output_root=output_root,
                manifest=manifest,
                run_totals=run_totals,
                dpi=int(args.dpi),
                language=str(args.language),
                psm=int(args.psm),
                pdftoppm=pdftoppm,
                tesseract=tesseract,
                performance=performance,
            )
        report["seed"] = seeded
        write_json_atomic(report_out, report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        if args.enforce and report["status"] != "ok":
            return 1
        return 0
    except (
        CorpusOcrError,
        OSError,
        sqlite3.Error,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
