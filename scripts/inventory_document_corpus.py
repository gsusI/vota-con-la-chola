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
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

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


class _VisibleTextCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_chars = 0

    def handle_data(self, data: str) -> None:
        self.text_chars += sum(1 for char in data if not char.isspace())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory real document formats")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
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


def _base_item(path: Path, root: Path) -> dict[str, Any]:
    relative_path = path.relative_to(root)
    suffix = path.suffix.lower()
    return {
        "path": str(relative_path),
        "source_group": _source_group(relative_path),
        "extension": suffix.lstrip("."),
        "mime_type": MIME_BY_SUFFIX[suffix],
        "bytes": int(path.stat().st_size),
        "sha256": _sha256(path),
        "status": "ok",
        "page_count": None,
        "text_chars": None,
        "text_density_chars_per_page": None,
        "quality_class": "markup",
        "page_text_quality": None,
        "error": None,
    }


def inspect_markup(path: Path, root: Path) -> dict[str, Any]:
    item = _base_item(path, root)
    parser = _VisibleTextCounter()
    decoder = codecs.getincrementaldecoder("utf-8")("ignore")
    try:
        with path.open("rb") as handle:
            for raw_chunk in iter(lambda: handle.read(1024 * 1024), b""):
                parser.feed(decoder.decode(raw_chunk))
        parser.feed(decoder.decode(b"", final=True))
        parser.close()
        item["text_chars"] = parser.text_chars
        item["quality_class"] = "markup_with_text" if parser.text_chars else "empty_markup"
    except (OSError, UnicodeError, ValueError) as exc:
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


def inspect_pdf(path: Path, root: Path, timeout: float) -> dict[str, Any]:
    item = _base_item(path, root)
    pdfinfo = shutil.which("pdfinfo")
    pdftotext = shutil.which("pdftotext")
    if not pdfinfo or not pdftotext:
        item["status"] = "unsupported"
        item["quality_class"] = "tools_unavailable"
        item["error"] = "pdfinfo and pdftotext are required"
        return item

    output_fd, output_name = tempfile.mkstemp(prefix="vota-document-inventory-", suffix=".txt")
    os.close(output_fd)
    output_path = Path(output_name)
    try:
        info = _run_tool([pdfinfo, str(path)], timeout)
        match = PDF_PAGES_RE.search(info.stdout)
        if info.returncode != 0 or match is None:
            raise RuntimeError(info.stderr.strip() or "pdfinfo did not return page count")
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


def inspect_document(path: Path, root: Path, pdf_timeout: float) -> dict[str, Any]:
    if path.suffix.lower() == ".pdf":
        return inspect_pdf(path, root, pdf_timeout)
    return inspect_markup(path, root)


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


def _aggregate(items: Iterable[dict[str, Any]], root: Path) -> dict[str, Any]:
    item_list = list(items)
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
        "schema_version": "real_document_format_inventory_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "root": _display_path(root),
        "status": "ok" if files_ok == files_total else "partial",
        "capacity_class": "below_s1_100k",
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
                int(dict(item.get("page_text_quality") or {}).get("pages_with_text") or 0)
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
        "checks": {
            "all_files_accounted": files_total
            == sum(value["files"] for value in by_extension.values()),
            "repo_relative_manifest_paths": all(
                not Path(str(item["path"])).is_absolute() for item in item_list
            ),
            "s1_100k_reached": files_total >= 100_000,
        },
        "limitations": [
            "This inventories the existing local real corpus; it does not prove a 100k-document run.",
            "Sparse or empty PDF text marks an OCR candidate only; OCR was not run.",
            "Markup text counts are parser-based inventory metrics, not semantic extraction quality judgments.",
            "Office documents and additional languages require new representative source inventory.",
        ],
    }


def run_inventory(
    *,
    root: Path,
    workers: int,
    pdf_timeout: float,
    limit: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if workers < 1:
        raise ValueError("workers must be >= 1")
    paths = iter_document_paths(root, limit)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        items = list(
            executor.map(
                lambda path: inspect_document(path, root, pdf_timeout),
                paths,
            )
        )
    return items, _aggregate(items, root)


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
