#!/usr/bin/env python3
"""Inventory a large local document corpus with bounded per-file work."""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import xml.parsers.expat
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from html.parser import HTMLParser
from itertools import zip_longest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.xlsx import (
    DEFAULT_MAX_TEXT_CHARS as DEFAULT_MAX_XLSX_TEXT_CHARS,
    XLSX_CONTENT_TYPE,
    extract_xlsx_path,
)

DEFAULT_ROOT = Path("etl/data/raw")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-format-inventory.json"
)
DEFAULT_MANIFEST = Path("etl/data/manifests/real-document-format-inventory.jsonl")
SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm", ".xml", ".xlsx"}
INVENTORY_ALGORITHM_VERSION = (
    "real_document_inventory_v7_xlsx_xml_phonetic_bounded"
)
MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "application/xml",
    ".xlsx": XLSX_CONTENT_TYPE,
}
PDF_PAGES_RE = re.compile(r"^Pages:\s*(\d+)\s*$", re.MULTILINE)
NON_REAL_DOCUMENT_MARKERS = (
    b"example.invalid",
    b"programa (synthetic)",
    b"<id>ep-0001</id>",
    b"<name>laura sanchez</name>",
)
INVENTORY_FETCH_BATCH_ROWS = 256
INVENTORY_MAX_IN_FLIGHT_PER_WORKER = 2
INVENTORY_REPORT_SAMPLE_LIMIT = 100


class InventoryRows:
    """Re-iterable disk-backed manifest rows returned by ``run_inventory``."""

    def __init__(self, path: Path, rows: int, *, owned: bool) -> None:
        self.path = path
        self._rows = rows
        self._owned = owned

    def __iter__(self) -> Iterator[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid inventory row {line_number}: {exc}"
                    ) from exc
                if not isinstance(item, dict):
                    raise ValueError(f"invalid inventory row {line_number}")
                yield item

    def __len__(self) -> int:
        return self._rows

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Iterable):
            return False
        sentinel = object()
        return all(
            left == right
            for left, right in zip_longest(self, other, fillvalue=sentinel)
        )

    def close(self) -> None:
        if self._owned:
            self.path.unlink(missing_ok=True)
            self._owned = False

    def __del__(self) -> None:
        self.close()


class _VisibleTextCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_chars = 0
        self._ignored_depth = 0
        self._title_depth = 0
        self.title_parts: list[str] = []
        self.text_sample_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "template", "svg"}:
            self._ignored_depth += 1
        if lowered == "title":
            self._title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title" and self._title_depth:
            self._title_depth -= 1
        if (
            lowered in {"script", "style", "noscript", "template", "svg"}
            and self._ignored_depth
        ):
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if self._title_depth and normalized:
            self.title_parts.append(normalized)
        if self._ignored_depth:
            return
        self.text_chars += sum(1 for char in data if not char.isspace())
        if normalized and sum(len(part) for part in self.text_sample_parts) < 4_096:
            self.text_sample_parts.append(normalized)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def text_sample(self) -> str:
        return " ".join(self.text_sample_parts)[:4_096]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory real document formats")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument(
        "--previous-manifest",
        default=str(DEFAULT_MANIFEST),
        help="Reuse unchanged checksum-verified inventory rows from this JSONL",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--pdf-timeout", type=float, default=60.0)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args(argv)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return path.name


def iter_document_paths(root: Path, limit: int = 0) -> Iterator[Path]:
    """Yield paths without retaining corpus-sized filesystem result lists.

    Callers needing deterministic order must externalize ordering. ``run_inventory``
    does this in SQLite. ``limit`` is retained for small diagnostic callers only.
    """

    yielded = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        yield path
        yielded += 1
        if limit > 0 and yielded >= limit:
            return


def _contains_non_real_marker(path: Path) -> bool:
    longest_marker = max(len(marker) for marker in NON_REAL_DOCUMENT_MARKERS)
    carry = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            folded = (carry + chunk).lower()
            if any(marker in folded for marker in NON_REAL_DOCUMENT_MARKERS):
                return True
            carry = folded[-longest_marker:]
    return False


def _iter_sample_content_fingerprints(root: Path) -> Iterator[str]:
    for path in iter_document_paths(root):
        if "samples" not in path.relative_to(root).parts:
            continue
        if _contains_non_real_marker(path):
            yield _sha256(path)


def _load_previous_manifest(
    conn: sqlite3.Connection, path: Path | None
) -> int:
    if path is None or not path.is_file():
        return 0
    loaded = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid previous inventory row {line_number}: {exc}"
                ) from exc
            relative = str(item.get("path") or "")
            if (
                not relative
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
            ):
                raise ValueError(
                    f"invalid previous inventory contract at row {line_number}"
                )
            if item.get("inventory_algorithm_version") != INVENTORY_ALGORITHM_VERSION:
                # A prior algorithm is not reusable evidence. Treat it as a
                # cache miss so schema/version upgrades rebuild the real row.
                continue
            if (
                item.get("real_data_status") != "eligible_real_capture"
                or item.get("accountability_eligible") is not True
            ):
                raise ValueError(
                    f"invalid previous inventory contract at row {line_number}"
                )
            try:
                conn.execute(
                    """
                    INSERT INTO previous(path, sha256, bytes, row_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        relative,
                        str(item.get("sha256") or ""),
                        int(item.get("bytes") or -1),
                        json.dumps(item, ensure_ascii=True, sort_keys=True),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"duplicate previous inventory path at row {line_number}: {relative}"
                ) from exc
            loaded += 1
            if loaded % 10_000 == 0:
                conn.commit()
    conn.commit()
    return loaded


def _non_real_exclusion_reason(
    path: Path,
    root: Path,
    sample_fingerprints: set[str] | None = None,
    *,
    content_sha256: str | None = None,
) -> str | None:
    relative = path.relative_to(root)
    if "samples" in relative.parts:
        return "fixture_or_sample_path"
    digest = content_sha256 or _sha256(path)
    if digest in (sample_fingerprints or set()):
        return f"sample_content_fingerprint:{digest}"
    if path.suffix.lower() not in {".html", ".htm", ".xml"}:
        return None
    longest_marker = max(len(marker) for marker in NON_REAL_DOCUMENT_MARKERS)
    carry = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            folded = (carry + chunk).lower()
            for marker in NON_REAL_DOCUMENT_MARKERS:
                if marker in folded:
                    return f"prohibited_marker:{marker.decode('ascii')}"
            carry = folded[-longest_marker:]
    return None


def _source_group(relative_path: Path) -> str:
    parts = relative_path.parts
    if not parts:
        return "unknown"
    if parts[0] == "text_documents" and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_pdf_page_text(path: Path, reported_pages: int) -> list[int]:
    counts: list[int] = []
    current = 0
    decoder = codecs.getincrementaldecoder("utf-8")("ignore")

    def consume(chunk: str) -> None:
        nonlocal current
        for char in chunk:
            if char == "\f":
                counts.append(current)
                current = 0
            elif not char.isspace():
                current += 1

    with path.open("rb") as handle:
        for raw_chunk in iter(lambda: handle.read(1024 * 1024), b""):
            consume(decoder.decode(raw_chunk))
    consume(decoder.decode(b"", final=True))
    if current > 0 or not counts:
        counts.append(current)
    if len(counts) < reported_pages:
        counts.extend([0] * (reported_pages - len(counts)))
    return counts[:reported_pages] if reported_pages > 0 else counts


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile)))
    return int(ordered[index])


def _base_item(
    path: Path,
    root: Path,
    *,
    detected_suffix: str | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    relative_path = path.relative_to(root)
    path_suffix = path.suffix.lower()
    suffix = detected_suffix or path_suffix
    return {
        "path": str(relative_path),
        "inventory_algorithm_version": INVENTORY_ALGORITHM_VERSION,
        "source_group": _source_group(relative_path),
        "extension": suffix.lstrip("."),
        "path_extension": path_suffix.lstrip("."),
        "mime_type": MIME_BY_SUFFIX[suffix],
        "format_detection": (
            "content_magic_pdf"
            if suffix == ".pdf" and path_suffix != ".pdf"
            else "path_suffix"
        ),
        "bytes": int(path.stat().st_size),
        "sha256": content_sha256 or _sha256(path),
        "status": "ok",
        "real_data_status": "eligible_real_capture",
        "accountability_eligible": True,
        "eligibility_reason": "accountability_document",
        "page_count": None,
        "text_chars": None,
        "text_density_chars_per_page": None,
        "quality_class": "markup",
        "page_text_quality": None,
        "worksheet_count": None,
        "worksheet_rows": None,
        "nonempty_worksheet_rows": None,
        "nonempty_cells": None,
        "formula_cells": None,
        "error": None,
    }


def inspect_markup(
    path: Path, root: Path, *, content_sha256: str | None = None
) -> dict[str, Any]:
    item = _base_item(path, root, content_sha256=content_sha256)
    parser = _VisibleTextCounter()
    decoder = codecs.getincrementaldecoder("utf-8")("ignore")
    try:
        with path.open("rb") as handle:
            for raw_chunk in iter(lambda: handle.read(1024 * 1024), b""):
                parser.feed(decoder.decode(raw_chunk))
        parser.feed(decoder.decode(b"", final=True))
        parser.close()
        item["text_chars"] = parser.text_chars
        item["quality_class"] = (
            "markup_with_text" if parser.text_chars else "empty_markup"
        )
        title = parser.title.casefold()
        visible_sample = parser.text_sample.casefold()
        if title in {"access denied", "forbidden"}:
            item["real_data_status"] = "real_transport_failure_capture"
            item["accountability_eligible"] = False
            item["eligibility_reason"] = "transport_failure:access_denied"
            item["quality_class"] = "transport_failure_capture"
        elif (
            item["bytes"] <= 4_096
            and "request unsuccessful" in visible_sample
            and "incapsula incident id" in visible_sample
        ):
            item["real_data_status"] = "real_transport_failure_capture"
            item["accountability_eligible"] = False
            item["eligibility_reason"] = "transport_failure:incapsula_denial"
            item["quality_class"] = "transport_failure_capture"
        elif (
            title in {"error", "service unavailable", "bad gateway"}
            and len(parser.text_sample) < 2_000
        ):
            item["real_data_status"] = "real_transport_failure_capture"
            item["accountability_eligible"] = False
            item["eligibility_reason"] = "transport_failure:generic_error"
            item["quality_class"] = "transport_failure_capture"
    except (OSError, UnicodeError, ValueError) as exc:
        item["status"] = "error"
        item["quality_class"] = "parse_error"
        item["error"] = f"{type(exc).__name__}: {exc}"
    return item


def inspect_boe_xml(
    path: Path, root: Path, *, content_sha256: str | None = None
) -> dict[str, Any]:
    """Count valid BOE XML text with the streaming C parser, not HTML recovery."""
    item = _base_item(path, root, content_sha256=content_sha256)
    text_chars = 0
    ignored_depth = 0
    ignored_tags = {"script", "style", "noscript", "template", "svg"}

    def local_name(value: str) -> str:
        return value.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()

    def start(name: str, attributes: dict[str, str]) -> None:
        del attributes
        nonlocal ignored_depth
        if local_name(name) in ignored_tags:
            ignored_depth += 1

    def end(name: str) -> None:
        nonlocal ignored_depth
        if local_name(name) in ignored_tags and ignored_depth:
            ignored_depth -= 1

    def characters(value: str) -> None:
        nonlocal text_chars
        if not ignored_depth:
            text_chars += sum(1 for char in value if not char.isspace())

    try:
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = start
        parser.EndElementHandler = end
        parser.CharacterDataHandler = characters
        with path.open("rb") as handle:
            parser.ParseFile(handle)
        item["text_chars"] = text_chars
        item["quality_class"] = "markup_with_text" if text_chars else "empty_markup"
    except (OSError, ValueError, xml.parsers.expat.ExpatError) as exc:
        item["status"] = "error"
        item["quality_class"] = "parse_error"
        item["error"] = f"{type(exc).__name__}: {exc}"
    return item


def inspect_xlsx(
    path: Path, root: Path, *, content_sha256: str | None = None
) -> dict[str, Any]:
    """Inventory every real worksheet row/cell under explicit archive bounds."""

    item = _base_item(path, root, content_sha256=content_sha256)
    try:
        workbook = extract_xlsx_path(
            path,
            max_text_chars=DEFAULT_MAX_XLSX_TEXT_CHARS,
            retain_text=False,
            retain_rows=False,
        )
        item["text_chars"] = workbook.text_chars
        item["worksheet_count"] = workbook.worksheet_count
        item["worksheet_rows"] = workbook.worksheet_rows
        item["nonempty_worksheet_rows"] = workbook.nonempty_worksheet_rows
        item["nonempty_cells"] = workbook.nonempty_cells
        item["formula_cells"] = workbook.formula_cells
        item["quality_class"] = (
            "xlsx_public_cells_with_text"
            if workbook.nonempty_cells
            else "xlsx_empty_workbook"
        )
    except (OSError, ValueError, RuntimeError) as exc:
        item["status"] = "error"
        item["quality_class"] = "xlsx_parse_error"
        item["error"] = f"{type(exc).__name__}: {exc}"
    return item


def _run_tool(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def inspect_pdf(
    path: Path,
    root: Path,
    timeout: float,
    *,
    detected_suffix: str | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    item = _base_item(
        path,
        root,
        detected_suffix=detected_suffix,
        content_sha256=content_sha256,
    )
    pdfinfo = shutil.which("pdfinfo")
    pdftotext = shutil.which("pdftotext")
    if not pdfinfo or not pdftotext:
        item["status"] = "unsupported"
        item["quality_class"] = "tools_unavailable"
        item["error"] = "pdfinfo and pdftotext are required"
        return item

    output_fd, output_name = tempfile.mkstemp(
        prefix="vota-document-inventory-", suffix=".txt"
    )
    os.close(output_fd)
    output_path = Path(output_name)
    try:
        info = _run_tool([pdfinfo, str(path)], timeout)
        match = PDF_PAGES_RE.search(info.stdout)
        if info.returncode != 0 or match is None:
            raise RuntimeError(
                info.stderr.strip() or "pdfinfo did not return page count"
            )
        pages = int(match.group(1))
        extract = _run_tool(
            [pdftotext, "-enc", "UTF-8", str(path), str(output_path)],
            timeout,
        )
        if extract.returncode != 0:
            raise RuntimeError(extract.stderr.strip() or "pdftotext failed")
        page_text_chars = _count_pdf_page_text(output_path, pages)
        text_chars = sum(page_text_chars)
        density = round(text_chars / pages, 2) if pages else 0.0
        pages_empty = sum(value == 0 for value in page_text_chars)
        pages_sparse = sum(0 < value < 100 for value in page_text_chars)
        ocr_candidate_pages = [
            {
                "page_number": page_number,
                "reason": "empty_text" if value == 0 else "sparse_text",
                "source_text_chars": value,
            }
            for page_number, value in enumerate(page_text_chars, start=1)
            if value < 100
        ]
        item["page_count"] = pages
        item["text_chars"] = text_chars
        item["text_density_chars_per_page"] = density
        item["page_text_quality"] = {
            "segments": len(page_text_chars),
            "pages_with_text": sum(value > 0 for value in page_text_chars),
            "pages_empty": pages_empty,
            "pages_sparse_ocr_candidate": pages_sparse,
            "ocr_candidate_pages": ocr_candidate_pages,
            "min_text_chars": min(page_text_chars, default=0),
            "p50_text_chars": _percentile(page_text_chars, 0.50),
            "p95_text_chars": _percentile(page_text_chars, 0.95),
            "max_text_chars": max(page_text_chars, default=0),
        }
        if text_chars == 0:
            item["quality_class"] = "pdf_empty_text"
        elif pages_empty:
            item["quality_class"] = "pdf_mixed_empty_pages"
        elif pages_sparse:
            item["quality_class"] = "pdf_mixed_sparse_pages"
        else:
            item["quality_class"] = "pdf_digital_text"
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        item["status"] = "error"
        item["quality_class"] = "pdf_parse_error"
        item["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        output_path.unlink(missing_ok=True)
    return item


def inspect_document(
    path: Path,
    root: Path,
    pdf_timeout: float,
    *,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            prefix = handle.read(16).lstrip()
    except OSError:
        prefix = b""
    if path.suffix.lower() == ".pdf" or prefix.startswith(b"%PDF-"):
        if content_sha256 is None:
            return inspect_pdf(
                path,
                root,
                pdf_timeout,
                detected_suffix=".pdf",
            )
        return inspect_pdf(
            path,
            root,
            pdf_timeout,
            detected_suffix=".pdf",
            content_sha256=content_sha256,
        )
    if path.suffix.lower() == ".xlsx":
        return inspect_xlsx(path, root, content_sha256=content_sha256)
    relative_parts = path.relative_to(root).parts
    if (
        path.suffix.lower() == ".xml"
        and relative_parts[:2] == ("text_documents", "boe_document_xml")
    ):
        return inspect_boe_xml(path, root, content_sha256=content_sha256)
    if content_sha256 is None:
        return inspect_markup(path, root)
    return inspect_markup(path, root, content_sha256=content_sha256)


def _size_bucket(size: int) -> str:
    if size < 10_000:
        return "lt_10kb"
    if size < 100_000:
        return "10kb_to_100kb"
    if size < 1_000_000:
        return "100kb_to_1mb"
    if size < 10_000_000:
        return "1mb_to_10mb"
    return "gte_10mb"


def _open_inventory_work_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = FILE;
        CREATE TABLE previous (
          path TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          row_json TEXT NOT NULL
        );
        CREATE TABLE sample_fingerprints (
          sha256 TEXT PRIMARY KEY
        );
        CREATE TABLE queue (
          path TEXT PRIMARY KEY,
          absolute_path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          kind TEXT NOT NULL CHECK (kind IN ('inspect', 'reused')),
          is_xlsx INTEGER NOT NULL CHECK (is_xlsx IN (0, 1)),
          row_json TEXT
        );
        CREATE INDEX queue_kind_format_path
          ON queue(kind, is_xlsx, path);
        CREATE TABLE items (
          path TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          extension TEXT NOT NULL,
          source_group TEXT NOT NULL,
          status TEXT NOT NULL,
          row_json TEXT NOT NULL
        );
        CREATE INDEX items_sha256 ON items(sha256);
        CREATE TABLE exclusions (
          kind TEXT NOT NULL CHECK (kind IN ('non_real', 'accountability')),
          path TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          reason TEXT NOT NULL,
          row_json TEXT NOT NULL,
          PRIMARY KEY(kind, path)
        );
        CREATE INDEX exclusions_kind_reason
          ON exclusions(kind, reason, path);
        """
    )
    return conn


def _insert_item(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO items(
          path, sha256, bytes, extension, source_group, status, row_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(item["path"]),
            str(item["sha256"]),
            int(item["bytes"]),
            str(item["extension"]),
            str(item["source_group"]),
            str(item["status"]),
            json.dumps(item, ensure_ascii=True, sort_keys=True),
        ),
    )


def _insert_exclusion(
    conn: sqlite3.Connection, kind: str, item: dict[str, Any]
) -> None:
    conn.execute(
        """
        INSERT INTO exclusions(kind, path, bytes, reason, row_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            kind,
            str(item["path"]),
            int(item["bytes"]),
            str(item["reason"]),
            json.dumps(item, ensure_ascii=True, sort_keys=True),
        ),
    )


def _iter_inspected_batch(
    rows: Iterable[sqlite3.Row],
    *,
    root: Path,
    pdf_timeout: float,
    workers: int,
) -> Iterator[dict[str, Any]]:
    """Inspect one bounded DB batch with an explicit bounded future window."""

    row_iter = iter(rows)
    max_pending = max(1, workers) * INVENTORY_MAX_IN_FLIGHT_PER_WORKER
    pending: dict[Future[dict[str, Any]], str] = {}
    exhausted = False
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        while pending or not exhausted:
            while not exhausted and len(pending) < max_pending:
                try:
                    row = next(row_iter)
                except StopIteration:
                    exhausted = True
                    break
                future = executor.submit(
                    inspect_document,
                    Path(str(row["absolute_path"])),
                    root,
                    pdf_timeout,
                    content_sha256=str(row["sha256"]),
                )
                pending[future] = str(row["path"])
            if not pending:
                continue
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                pending.pop(future)
                yield future.result()


def _write_inventory_manifest_atomic(
    conn: sqlite3.Connection, path: Path
) -> tuple[int, int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    rows = 0
    size = 0
    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "wb") as handle:
            cursor = conn.execute("SELECT row_json FROM items ORDER BY path")
            while batch := cursor.fetchmany(INVENTORY_FETCH_BATCH_ROWS):
                for item in batch:
                    encoded = (str(item["row_json"]) + "\n").encode("utf-8")
                    handle.write(encoded)
                    digest.update(encoded)
                    size += len(encoded)
                    rows += 1
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return rows, size, digest.hexdigest()


def _exclusion_summary(
    conn: sqlite3.Connection, kind: str
) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT COUNT(*) AS files, COALESCE(SUM(bytes), 0) AS bytes
        FROM exclusions
        WHERE kind = ?
        """,
        (kind,),
    ).fetchone()
    by_reason = {
        str(row["reason"]): int(row["files"])
        for row in conn.execute(
            """
            SELECT reason, COUNT(*) AS files
            FROM exclusions
            WHERE kind = ?
            GROUP BY reason
            ORDER BY reason
            """,
            (kind,),
        )
    }
    samples = [
        json.loads(str(row["row_json"]))
        for row in conn.execute(
            """
            SELECT row_json
            FROM exclusions
            WHERE kind = ?
            ORDER BY path
            LIMIT ?
            """,
            (kind, INVENTORY_REPORT_SAMPLE_LIMIT),
        )
    ]
    return {
        "files": int(totals["files"]),
        "bytes": int(totals["bytes"]),
        "by_reason": by_reason,
        "samples": samples,
        "samples_truncated": int(totals["files"]) > len(samples),
    }


def _aggregate(
    items: InventoryRows,
    root: Path,
    *,
    distinct_content_objects: int,
    non_real_exclusions: dict[str, Any],
    accountability_exclusions: dict[str, Any],
    sample_content_fingerprints_excluded: bool,
) -> dict[str, Any]:
    """Aggregate one manifest pass without materializing corpus-sized rows."""

    by_extension: dict[str, Counter[str]] = defaultdict(Counter)
    by_source_group: dict[str, Counter[str]] = defaultdict(Counter)
    size_buckets: Counter[str] = Counter()
    quality_classes: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    files_total = len(items)
    files_ok = 0
    total_bytes = 0
    pdf_files = 0
    pdf_files_ok = 0
    pdf_pages = 0
    pdf_pages_with_text = 0
    pdf_pages_empty = 0
    pdf_pages_sparse = 0
    pdf_text_chars = 0
    xlsx_files = 0
    xlsx_files_ok = 0
    xlsx_worksheets = 0
    xlsx_worksheet_rows = 0
    xlsx_nonempty_rows = 0
    xlsx_nonempty_cells = 0
    xlsx_formula_cells = 0
    xlsx_native_text_chars = 0
    xlsx_text_respects_shared_ceiling = True
    markup_text_chars = 0
    repo_relative_paths = True
    fixture_paths_excluded = True
    eligible_rows_marked_real = True
    for item in items:
        extension = str(item["extension"])
        source_group = str(item["source_group"])
        size = int(item["bytes"])
        status = str(item["status"])
        total_bytes += size
        files_ok += int(status == "ok")
        by_extension[extension]["files"] += 1
        by_extension[extension]["bytes"] += size
        by_extension[extension][status] += 1
        by_source_group[source_group]["files"] += 1
        by_source_group[source_group]["bytes"] += size
        by_source_group[source_group][status] += 1
        size_buckets[_size_bucket(size)] += 1
        quality_classes[str(item["quality_class"])] += 1
        if status != "ok" and len(failures) < 100:
            failures.append(
                {
                    "path": item["path"],
                    "status": status,
                    "error": item["error"],
                }
            )
        relative_path = Path(str(item["path"]))
        repo_relative_paths = repo_relative_paths and not relative_path.is_absolute()
        fixture_paths_excluded = (
            fixture_paths_excluded and "samples" not in relative_path.parts
        )
        eligible_rows_marked_real = eligible_rows_marked_real and (
            item.get("real_data_status") == "eligible_real_capture"
            and item.get("accountability_eligible") is True
        )
        if extension == "pdf":
            pdf_files += 1
            if status == "ok":
                pdf_files_ok += 1
                page_quality = dict(item.get("page_text_quality") or {})
                pdf_pages += int(item.get("page_count") or 0)
                pdf_pages_with_text += int(page_quality.get("pages_with_text") or 0)
                pdf_pages_empty += int(page_quality.get("pages_empty") or 0)
                pdf_pages_sparse += int(
                    page_quality.get("pages_sparse_ocr_candidate") or 0
                )
                pdf_text_chars += int(item.get("text_chars") or 0)
        elif extension == "xlsx":
            xlsx_files += 1
            if status == "ok":
                xlsx_files_ok += 1
                xlsx_worksheets += int(item.get("worksheet_count") or 0)
                xlsx_worksheet_rows += int(item.get("worksheet_rows") or 0)
                xlsx_nonempty_rows += int(
                    item.get("nonempty_worksheet_rows") or 0
                )
                xlsx_nonempty_cells += int(item.get("nonempty_cells") or 0)
                xlsx_formula_cells += int(item.get("formula_cells") or 0)
                xlsx_native_text_chars += int(item.get("text_chars") or 0)
                xlsx_text_respects_shared_ceiling = (
                    xlsx_text_respects_shared_ceiling
                    and int(item.get("text_chars") or 0)
                    <= DEFAULT_MAX_XLSX_TEXT_CHARS
                )
        elif status == "ok":
            markup_text_chars += int(item.get("text_chars") or 0)
    return {
        "schema_version": "real_document_format_inventory_v7_xlsx_contract_bound",
        "inventory_algorithm_version": INVENTORY_ALGORITHM_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "root": _display_path(root),
        "status": "ok" if files_ok == files_total else "partial",
        "capacity_class": (
            "s1_100k" if files_total >= 100_000 else "below_s1_100k"
        ),
        "target_files_s1": 100_000,
        "xlsx_contract": {
            "max_text_chars": DEFAULT_MAX_XLSX_TEXT_CHARS,
            "empty_workbooks_are_eligible_native_no_text": True,
            "blank_worksheets_preserve_workbook_sheet_count": True,
        },
        "file_instances_progress_to_s1_pct": round(files_total * 100 / 100_000, 4),
        "distinct_content_progress_to_s1_pct": round(
            distinct_content_objects * 100 / 100_000,
            4,
        ),
        "totals": {
            "files": files_total,
            "distinct_content_objects": distinct_content_objects,
            "duplicate_file_instances": files_total - distinct_content_objects,
            "bytes": total_bytes,
            "ok": files_ok,
            "failed_or_unsupported": files_total - files_ok,
            "pdf_files": pdf_files,
            "pdf_files_ok": pdf_files_ok,
            "pdf_pages": pdf_pages,
            "pdf_pages_with_text": pdf_pages_with_text,
            "pdf_pages_empty": pdf_pages_empty,
            "pdf_pages_sparse_ocr_candidate": pdf_pages_sparse,
            "pdf_text_chars": pdf_text_chars,
            "xlsx_files": xlsx_files,
            "xlsx_files_ok": xlsx_files_ok,
            "xlsx_worksheets": xlsx_worksheets,
            "xlsx_worksheet_rows": xlsx_worksheet_rows,
            "xlsx_nonempty_worksheet_rows": xlsx_nonempty_rows,
            "xlsx_nonempty_cells": xlsx_nonempty_cells,
            "xlsx_formula_cells": xlsx_formula_cells,
            "xlsx_native_text_chars": xlsx_native_text_chars,
            "markup_text_chars": markup_text_chars,
            "excluded_non_real_files": non_real_exclusions["files"],
            "excluded_non_real_bytes": non_real_exclusions["bytes"],
            "excluded_non_accountability_capture_files": accountability_exclusions[
                "files"
            ],
            "excluded_non_accountability_capture_bytes": accountability_exclusions[
                "bytes"
            ],
            "raw_document_files_discovered": (
                files_total
                + int(non_real_exclusions["files"])
                + int(accountability_exclusions["files"])
            ),
        },
        "by_extension": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_extension.items())
        },
        "by_source_group": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_source_group.items())
        },
        "size_buckets": dict(sorted(size_buckets.items())),
        "quality_classes": dict(sorted(quality_classes.items())),
        "failure_samples": failures,
        "non_real_exclusions": {
            "by_reason": non_real_exclusions["by_reason"],
            "samples": non_real_exclusions["samples"],
            "samples_truncated": non_real_exclusions["samples_truncated"],
        },
        "accountability_exclusions": {
            "policy": (
                "Retain real transport-failure bytes as obstruction evidence; do not "
                "count them as successfully processed accountability documents."
            ),
            "by_reason": accountability_exclusions["by_reason"],
            "files": accountability_exclusions["samples"],
            "files_truncated": accountability_exclusions["samples_truncated"],
        },
        "checks": {
            "all_files_accounted": files_total
            == sum(value["files"] for value in by_extension.values()),
            "repo_relative_manifest_paths": repo_relative_paths,
            "s1_100k_reached": files_total >= 100_000,
            "fixture_or_sample_paths_excluded": fixture_paths_excluded,
            "sample_content_fingerprints_excluded": (
                sample_content_fingerprints_excluded
            ),
            "eligible_rows_marked_real": eligible_rows_marked_real,
            "transport_failures_excluded_from_accountability_scale": True,
            "xlsx_text_respects_shared_extraction_ceiling": (
                xlsx_text_respects_shared_ceiling
            ),
        },
        "limitations": [
            (
                "This proves inventory of more than 100000 captured official document instances; it does not by itself prove representative source and format coverage or million-document operation."
                if files_total >= 100_000
                else "This inventories the existing local real corpus; it does not prove a 100000-document run."
            ),
            "Sparse or empty PDF text marks an OCR candidate only; OCR was not run.",
            "Markup text counts are parser-based inventory metrics, not semantic extraction quality judgments.",
            "Transport-failure captures remain on disk for obstruction accountability but are excluded from successful-document scale metrics.",
            "XLSX coverage proves raw OOXML scalar-value extraction for the observed real cohort only; DOC, ODT, legacy XLS, and presentation formats remain unsupported.",
            "The real XLSX cohort contains zero observed formula cells. Formula handling is implemented but not empirically validated by this cohort.",
            "XLSX scalar values and typed phonetic annotations are preserved with exact sheet/row/cell coordinates; visual formatting, comments, charts, and embedded media are not claimed as extracted text.",
            "Additional languages require representative source inventory and review.",
        ],
    }


def run_inventory(
    *,
    root: Path,
    workers: int,
    pdf_timeout: float,
    limit: int = 0,
    previous_manifest_path: Path | None = None,
    manifest_out: Path | None = None,
) -> tuple[InventoryRows, dict[str, Any]]:
    if workers < 1:
        raise ValueError("workers must be >= 1")
    root = root.absolute()
    owned_manifest = manifest_out is None
    if manifest_out is None:
        descriptor, name = tempfile.mkstemp(
            prefix="vota-real-document-inventory-", suffix=".jsonl"
        )
        os.close(descriptor)
        manifest_out = Path(name)
    try:
        with tempfile.TemporaryDirectory(
            prefix="vota-document-inventory-work-"
        ) as work_dir:
            conn = _open_inventory_work_db(Path(work_dir) / "inventory.sqlite")
            try:
                for fingerprint in _iter_sample_content_fingerprints(root):
                    conn.execute(
                        "INSERT OR IGNORE INTO sample_fingerprints(sha256) VALUES (?)",
                        (fingerprint,),
                    )
                conn.commit()
                _load_previous_manifest(conn, previous_manifest_path)

                eligible_files = 0
                reused_files = 0
                excluded_non_real_files = 0
                for discovered, path in enumerate(iter_document_paths(root), start=1):
                    stat = path.stat()
                    content_sha256 = _sha256(path)
                    sample_match = (
                        conn.execute(
                            "SELECT 1 FROM sample_fingerprints WHERE sha256 = ?",
                            (content_sha256,),
                        ).fetchone()
                        is not None
                    )
                    exclusion_reason = _non_real_exclusion_reason(
                        path,
                        root,
                        {content_sha256} if sample_match else None,
                        content_sha256=content_sha256,
                    )
                    relative = str(path.relative_to(root))
                    if exclusion_reason:
                        _insert_exclusion(
                            conn,
                            "non_real",
                            {
                                "path": relative,
                                "bytes": stat.st_size,
                                "sha256": content_sha256,
                                "reason": exclusion_reason,
                            },
                        )
                        excluded_non_real_files += 1
                    else:
                        previous = conn.execute(
                            """
                            SELECT row_json
                            FROM previous
                            WHERE path = ? AND sha256 = ? AND bytes = ?
                            """,
                            (relative, content_sha256, stat.st_size),
                        ).fetchone()
                        kind = "reused" if previous is not None else "inspect"
                        conn.execute(
                            """
                            INSERT INTO queue(
                              path, absolute_path, sha256, bytes, kind, is_xlsx,
                              row_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                relative,
                                str(path.absolute()),
                                content_sha256,
                                stat.st_size,
                                kind,
                                int(path.suffix.casefold() == ".xlsx"),
                                (
                                    str(previous["row_json"])
                                    if previous is not None
                                    else None
                                ),
                            ),
                        )
                        eligible_files += 1
                        reused_files += int(previous is not None)
                    if discovered % 10_000 == 0:
                        conn.commit()
                        print(
                            json.dumps(
                                {
                                    "stage": "inventory_hash_and_classify",
                                    "files_discovered": discovered,
                                    "eligible_files": eligible_files,
                                    "unchanged_files_reused": reused_files,
                                    "excluded_non_real_files": (
                                        excluded_non_real_files
                                    ),
                                },
                                sort_keys=True,
                            ),
                            file=sys.stderr,
                            flush=True,
                        )
                conn.commit()

                if limit > 0:
                    threshold = conn.execute(
                        """
                        SELECT path
                        FROM queue
                        ORDER BY path
                        LIMIT 1 OFFSET ?
                        """,
                        (limit - 1,),
                    ).fetchone()
                    if threshold is not None:
                        conn.execute(
                            "DELETE FROM queue WHERE path > ?",
                            (str(threshold["path"]),),
                        )
                        conn.commit()

                queue_totals = conn.execute(
                    """
                    SELECT COUNT(*) AS files,
                           SUM(kind = 'reused') AS reused,
                           SUM(kind = 'inspect') AS inspect
                    FROM queue
                    """
                ).fetchone()
                reused_files = int(queue_totals["reused"] or 0)
                inspected_target = int(queue_totals["inspect"] or 0)

                last_path = ""
                while True:
                    batch = conn.execute(
                        """
                        SELECT path, row_json
                        FROM queue
                        WHERE kind = 'reused' AND path > ?
                        ORDER BY path
                        LIMIT ?
                        """,
                        (last_path, INVENTORY_FETCH_BATCH_ROWS),
                    ).fetchall()
                    if not batch:
                        break
                    for row in batch:
                        _insert_item(conn, json.loads(str(row["row_json"])))
                    last_path = str(batch[-1]["path"])
                    conn.commit()

                inspected_files = 0
                for is_xlsx, cohort_workers in (
                    (0, workers),
                    (1, min(workers, 2)),
                ):
                    cohort_total = int(
                        conn.execute(
                            """
                            SELECT COUNT(*) FROM queue
                            WHERE kind = 'inspect' AND is_xlsx = ?
                            """,
                            (is_xlsx,),
                        ).fetchone()[0]
                    )
                    cohort_inspected = 0
                    next_progress = 10_000
                    last_path = ""
                    while True:
                        batch = conn.execute(
                            """
                            SELECT path, absolute_path, sha256
                            FROM queue
                            WHERE kind = 'inspect'
                              AND is_xlsx = ?
                              AND path > ?
                            ORDER BY path
                            LIMIT ?
                            """,
                            (is_xlsx, last_path, INVENTORY_FETCH_BATCH_ROWS),
                        ).fetchall()
                        if not batch:
                            break
                        for item in _iter_inspected_batch(
                            batch,
                            root=root,
                            pdf_timeout=pdf_timeout,
                            workers=cohort_workers,
                        ):
                            inspected_files += 1
                            cohort_inspected += 1
                            if item.get("accountability_eligible") is True:
                                _insert_item(conn, item)
                            else:
                                _insert_exclusion(
                                    conn,
                                    "accountability",
                                    {
                                        "path": item["path"],
                                        "source_group": item["source_group"],
                                        "bytes": item["bytes"],
                                        "sha256": item["sha256"],
                                        "real_data_status": item[
                                            "real_data_status"
                                        ],
                                        "accountability_eligible": False,
                                        "reason": item["eligibility_reason"],
                                    },
                                )
                        last_path = str(batch[-1]["path"])
                        conn.commit()
                        if cohort_inspected >= next_progress:
                            print(
                                json.dumps(
                                    {
                                        "stage": "inventory_inspect",
                                        "files_inspected_in_cohort": (
                                            cohort_inspected
                                        ),
                                        "cohort_files": cohort_total,
                                        "xlsx_cohort": bool(is_xlsx),
                                    },
                                    sort_keys=True,
                                ),
                                file=sys.stderr,
                                flush=True,
                            )
                            next_progress = (
                                (cohort_inspected // 10_000) + 1
                            ) * 10_000

                if inspected_files != inspected_target:
                    raise ValueError(
                        "bounded inventory scheduler did not consume every queued file"
                    )
                distinct_content_objects = int(
                    conn.execute(
                        "SELECT COUNT(DISTINCT sha256) FROM items"
                    ).fetchone()[0]
                )
                sample_content_fingerprints_excluded = (
                    int(
                        conn.execute(
                            """
                            SELECT COUNT(*)
                            FROM items AS item
                            JOIN sample_fingerprints AS sample
                              ON sample.sha256 = item.sha256
                            """
                        ).fetchone()[0]
                    )
                    == 0
                )
                non_real_exclusions = _exclusion_summary(conn, "non_real")
                accountability_exclusions = _exclusion_summary(
                    conn, "accountability"
                )
                manifest_rows, manifest_bytes, manifest_sha256 = (
                    _write_inventory_manifest_atomic(conn, manifest_out)
                )
                items = InventoryRows(
                    manifest_out, manifest_rows, owned=owned_manifest
                )
                report = _aggregate(
                    items,
                    root,
                    distinct_content_objects=distinct_content_objects,
                    non_real_exclusions=non_real_exclusions,
                    accountability_exclusions=accountability_exclusions,
                    sample_content_fingerprints_excluded=(
                        sample_content_fingerprints_excluded
                    ),
                )
                report["incremental_reuse"] = {
                    "previous_manifest": (
                        _display_path(previous_manifest_path)
                        if previous_manifest_path is not None
                        and previous_manifest_path.is_file()
                        else None
                    ),
                    "unchanged_file_instances_reused": reused_files,
                    "file_instances_reinspected": inspected_files,
                }
                report["bounded_execution"] = {
                    "ordering": "sqlite_path_order",
                    "inventory_rows_materialized_in_memory": False,
                    "filesystem_paths_materialized_in_memory": False,
                    "fetch_batch_rows": INVENTORY_FETCH_BATCH_ROWS,
                    "max_in_flight_per_worker": (
                        INVENTORY_MAX_IN_FLIGHT_PER_WORKER
                    ),
                    "xlsx_workers_max": min(workers, 2),
                }
                report["manifest"] = {
                    "ref": _display_path(manifest_out),
                    "storage_class": "local_generated_ignored",
                    "rows": manifest_rows,
                    "bytes": manifest_bytes,
                    "sha256": manifest_sha256,
                }
                return items, report
            finally:
                conn.close()
    except Exception:
        if owned_manifest:
            manifest_out.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR: document root not found: {root}")
        return 2
    try:
        items, report = run_inventory(
            root=root,
            workers=args.workers,
            pdf_timeout=args.pdf_timeout,
            limit=max(0, args.limit),
            previous_manifest_path=(
                Path(args.previous_manifest) if args.previous_manifest else None
            ),
            manifest_out=Path(args.manifest_out),
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    report_out = Path(args.report_out)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{report_out.name}.", dir=report_out.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, report_out)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print(
        json.dumps(
            {
                "status": report["status"],
                "files": report["totals"]["files"],
                "pdf_files": report["totals"]["pdf_files"],
                "report": _display_path(report_out),
                "manifest": report["manifest"]["ref"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
