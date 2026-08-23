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
import subprocess
import sys
import tempfile
import xml.parsers.expat
from collections import Counter, defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path("etl/data/raw")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-format-inventory.json"
)
DEFAULT_MANIFEST = Path("etl/data/manifests/real-document-format-inventory.jsonl")
SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm", ".xml"}
MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "application/xml",
}
PDF_PAGES_RE = re.compile(r"^Pages:\s*(\d+)\s*$", re.MULTILINE)
NON_REAL_DOCUMENT_MARKERS = (
    b"example.invalid",
    b"programa (synthetic)",
    b"<id>ep-0001</id>",
    b"<name>laura sanchez</name>",
)


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


def iter_document_paths(root: Path, limit: int = 0) -> list[Path]:
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    return paths[:limit] if limit > 0 else paths


def _sample_content_fingerprints(root: Path) -> set[str]:
    fingerprints: set[str] = set()
    for path in iter_document_paths(root):
        if "samples" not in path.relative_to(root).parts:
            continue
        folded = path.read_bytes().lower()
        if any(marker in folded for marker in NON_REAL_DOCUMENT_MARKERS):
            fingerprints.add(_sha256(path))
    return fingerprints


def _load_previous_manifest(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    rows: dict[str, dict[str, Any]] = {}
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
                or item.get("real_data_status") != "eligible_real_capture"
                or item.get("accountability_eligible") is not True
            ):
                raise ValueError(
                    f"invalid previous inventory contract at row {line_number}"
                )
            rows[relative] = item
    return rows


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


def _aggregate(
    items: Iterable[dict[str, Any]],
    root: Path,
    non_real_exclusions: list[dict[str, Any]] | None = None,
    accountability_exclusions: list[dict[str, Any]] | None = None,
    sample_content_fingerprints: set[str] | None = None,
) -> dict[str, Any]:
    item_list = list(items)
    excluded_non_real = non_real_exclusions or []
    excluded_captures = accountability_exclusions or []
    sample_fingerprints = sample_content_fingerprints or set()
    by_extension: dict[str, Counter[str]] = defaultdict(Counter)
    by_source_group: dict[str, Counter[str]] = defaultdict(Counter)
    size_buckets: Counter[str] = Counter()
    quality_classes: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    for item in item_list:
        extension = str(item["extension"])
        source_group = str(item["source_group"])
        size = int(item["bytes"])
        status = str(item["status"])
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
    files_total = len(item_list)
    files_ok = sum(1 for item in item_list if item["status"] == "ok")
    distinct_content_objects = len({str(item["sha256"]) for item in item_list})
    pdf_items = [item for item in item_list if item["extension"] == "pdf"]
    pdf_ok = [item for item in pdf_items if item["status"] == "ok"]
    return {
        "schema_version": "real_document_format_inventory_v4",
        "generated_at": datetime.now(UTC).isoformat(),
        "root": _display_path(root),
        "status": "ok" if files_ok == files_total else "partial",
        "capacity_class": (
            "s1_100k" if files_total >= 100_000 else "below_s1_100k"
        ),
        "target_files_s1": 100_000,
        "file_instances_progress_to_s1_pct": round(files_total * 100 / 100_000, 4),
        "distinct_content_progress_to_s1_pct": round(
            distinct_content_objects * 100 / 100_000,
            4,
        ),
        "totals": {
            "files": files_total,
            "distinct_content_objects": distinct_content_objects,
            "duplicate_file_instances": files_total - distinct_content_objects,
            "bytes": sum(int(item["bytes"]) for item in item_list),
            "ok": files_ok,
            "failed_or_unsupported": files_total - files_ok,
            "pdf_files": len(pdf_items),
            "pdf_files_ok": len(pdf_ok),
            "pdf_pages": sum(int(item["page_count"] or 0) for item in pdf_ok),
            "pdf_pages_with_text": sum(
                int(
                    dict(item.get("page_text_quality") or {}).get("pages_with_text")
                    or 0
                )
                for item in pdf_ok
            ),
            "pdf_pages_empty": sum(
                int(dict(item.get("page_text_quality") or {}).get("pages_empty") or 0)
                for item in pdf_ok
            ),
            "pdf_pages_sparse_ocr_candidate": sum(
                int(
                    dict(item.get("page_text_quality") or {}).get(
                        "pages_sparse_ocr_candidate"
                    )
                    or 0
                )
                for item in pdf_ok
            ),
            "pdf_text_chars": sum(int(item["text_chars"] or 0) for item in pdf_ok),
            "markup_text_chars": sum(
                int(item["text_chars"] or 0)
                for item in item_list
                if item["extension"] != "pdf" and item["status"] == "ok"
            ),
            "excluded_non_real_files": len(excluded_non_real),
            "excluded_non_real_bytes": sum(
                int(item["bytes"]) for item in excluded_non_real
            ),
            "excluded_non_accountability_capture_files": len(excluded_captures),
            "excluded_non_accountability_capture_bytes": sum(
                int(item["bytes"]) for item in excluded_captures
            ),
            "raw_document_files_discovered": (
                files_total + len(excluded_non_real) + len(excluded_captures)
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
            "by_reason": dict(
                sorted(
                    Counter(str(item["reason"]) for item in excluded_non_real).items()
                )
            ),
            "samples": excluded_non_real[:100],
        },
        "accountability_exclusions": {
            "policy": (
                "Retain real transport-failure bytes as obstruction evidence; do not "
                "count them as successfully processed accountability documents."
            ),
            "by_reason": dict(
                sorted(
                    Counter(str(item["reason"]) for item in excluded_captures).items()
                )
            ),
            "files": excluded_captures,
        },
        "checks": {
            "all_files_accounted": files_total
            == sum(value["files"] for value in by_extension.values()),
            "repo_relative_manifest_paths": all(
                not Path(str(item["path"])).is_absolute() for item in item_list
            ),
            "s1_100k_reached": files_total >= 100_000,
            "fixture_or_sample_paths_excluded": all(
                "samples" not in Path(str(item["path"])).parts for item in item_list
            ),
            "sample_content_fingerprints_excluded": all(
                str(item.get("sha256") or "") not in sample_fingerprints
                for item in item_list
            ),
            "eligible_rows_marked_real": all(
                item.get("real_data_status") == "eligible_real_capture"
                and item.get("accountability_eligible") is True
                for item in item_list
            ),
            "transport_failures_excluded_from_accountability_scale": all(
                item.get("real_data_status") == "real_transport_failure_capture"
                and item.get("accountability_eligible") is False
                for item in excluded_captures
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
            "Office documents and additional languages require new representative source inventory.",
        ],
    }


def run_inventory(
    *,
    root: Path,
    workers: int,
    pdf_timeout: float,
    limit: int = 0,
    previous_manifest_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if workers < 1:
        raise ValueError("workers must be >= 1")
    sample_fingerprints = _sample_content_fingerprints(root)
    previous_rows = _load_previous_manifest(previous_manifest_path)
    non_real_exclusions: list[dict[str, Any]] = []
    paths: list[tuple[Path, str]] = []
    reused_items: list[dict[str, Any]] = []
    for discovered, path in enumerate(iter_document_paths(root), start=1):
        content_sha256 = _sha256(path)
        exclusion_reason = _non_real_exclusion_reason(
            path,
            root,
            sample_fingerprints,
            content_sha256=content_sha256,
        )
        if exclusion_reason:
            non_real_exclusions.append(
                {
                    "path": str(path.relative_to(root)),
                    "bytes": path.stat().st_size,
                    "sha256": content_sha256,
                    "reason": exclusion_reason,
                }
            )
            continue
        relative = str(path.relative_to(root))
        previous = previous_rows.get(relative)
        if (
            previous is not None
            and previous.get("sha256") == content_sha256
            and int(previous.get("bytes") or -1) == path.stat().st_size
        ):
            reused_items.append(previous)
        else:
            paths.append((path, content_sha256))
        if discovered % 10_000 == 0:
            print(
                json.dumps(
                    {
                        "stage": "inventory_hash_and_classify",
                        "files_discovered": discovered,
                        "eligible_files": len(paths) + len(reused_items),
                        "unchanged_files_reused": len(reused_items),
                        "excluded_non_real_files": len(non_real_exclusions),
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )
    if limit > 0:
        combined = sorted(
            [(str(item["path"]), "reused", item) for item in reused_items]
            + [
                (str(path.relative_to(root)), "inspect", (path, digest))
                for path, digest in paths
            ]
        )[:limit]
        reused_items = [item for _, kind, item in combined if kind == "reused"]
        paths = [item for _, kind, item in combined if kind == "inspect"]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        inspected_items = []
        for inspected, item in enumerate(
            executor.map(
                lambda item: inspect_document(
                    item[0],
                    root,
                    pdf_timeout,
                    content_sha256=item[1],
                ),
                paths,
            ),
            start=1,
        ):
            inspected_items.append(item)
            if inspected % 10_000 == 0:
                print(
                    json.dumps(
                        {
                            "stage": "inventory_inspect",
                            "files_inspected": inspected,
                            "files_total": len(paths),
                        },
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                    flush=True,
                )
    items = reused_items + [
        item for item in inspected_items if item.get("accountability_eligible") is True
    ]
    items.sort(key=lambda item: str(item["path"]))
    accountability_exclusions = [
        {
            "path": item["path"],
            "source_group": item["source_group"],
            "bytes": item["bytes"],
            "sha256": item["sha256"],
            "real_data_status": item["real_data_status"],
            "accountability_eligible": False,
            "reason": item["eligibility_reason"],
        }
        for item in inspected_items
        if item.get("accountability_eligible") is False
    ]
    report = _aggregate(
        items,
        root,
        non_real_exclusions,
        accountability_exclusions,
        sample_fingerprints,
    )
    report["incremental_reuse"] = {
        "previous_manifest": (
            _display_path(previous_manifest_path)
            if previous_manifest_path is not None and previous_manifest_path.is_file()
            else None
        ),
        "unchanged_file_instances_reused": len(reused_items),
        "file_instances_reinspected": len(inspected_items),
    }
    return items, report


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
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    manifest_out = Path(args.manifest_out)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    with manifest_out.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n")
    report["manifest"] = {
        "ref": _display_path(manifest_out),
        "storage_class": "local_generated_ignored",
        "rows": len(items),
        "bytes": int(manifest_out.stat().st_size),
        "sha256": _sha256(manifest_out),
    }
    report_out = Path(args.report_out)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "files": report["totals"]["files"],
                "pdf_files": report["totals"]["pdf_files"],
                "report": _display_path(report_out),
                "manifest": _display_path(manifest_out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
