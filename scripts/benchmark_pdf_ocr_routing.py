#!/usr/bin/env python3
"""Benchmark page-level OCR routing on deterministic real PDF candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path("etl/data/raw")
DEFAULT_MANIFEST = Path("etl/data/manifests/real-document-format-inventory.jsonl")
DEFAULT_OUT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "pdf-ocr-routing-benchmark.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark routed OCR candidate pages")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--language", default="spa")
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args(argv)


def _tool_version(command: str, version_arg: str = "--version") -> str:
    completed = subprocess.run(
        [command, version_arg],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    text = completed.stdout or completed.stderr
    return text.splitlines()[0].strip() if text else "unknown"


def load_candidates(manifest_path: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            relative_path = Path(str(row.get("path") or ""))
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError("manifest contains unsafe document path")
            page_quality = dict(row.get("page_text_quality") or {})
            for page in list(page_quality.get("ocr_candidate_pages") or []):
                candidates.append(
                    {
                        "path": str(relative_path),
                        "document_sha256": str(row.get("sha256") or ""),
                        "page_number": int(page["page_number"]),
                        "reason": str(page["reason"]),
                        "source_text_chars": int(page["source_text_chars"]),
                    }
                )
    return sorted(
        candidates,
        key=lambda row: (
            0 if row["reason"] == "empty_text" else 1,
            row["path"],
            row["page_number"],
        ),
    )


def select_diverse_candidates(
    candidates: list[dict[str, Any]], max_pages: int
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[str(candidate["path"])].append(candidate)
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for reason in ("empty_text", "sparse_text"):
        for path in sorted(grouped):
            match = next(
                (row for row in grouped[path] if row["reason"] == reason),
                None,
            )
            if match is None:
                continue
            selected.append(match)
            seen.add((str(match["path"]), int(match["page_number"])))
            if len(selected) >= max_pages:
                return selected
    for candidate in candidates:
        identity = (str(candidate["path"]), int(candidate["page_number"]))
        if identity in seen:
            continue
        selected.append(candidate)
        if len(selected) >= max_pages:
            break
    return selected


def ocr_page(
    candidate: dict[str, Any],
    *,
    root: Path,
    pdftoppm: str,
    tesseract: str,
    dpi: int,
    language: str,
    timeout: float,
) -> dict[str, Any]:
    started = time.monotonic()
    page_number = int(candidate["page_number"])
    pdf_path = root / str(candidate["path"])
    result = dict(candidate)
    result.update(
        {
            "status": "error",
            "ocr_text_chars": 0,
            "ocr_text_sha256": None,
            "improved_over_embedded_text": False,
            "elapsed_seconds": None,
            "error": None,
        }
    )
    if not pdf_path.is_file():
        result["error"] = "FileNotFoundError: PDF is missing"
        return result
    with tempfile.TemporaryDirectory(prefix="vota-ocr-routing-") as temp_dir:
        image_prefix = Path(temp_dir) / "page"
        image_path = image_prefix.with_suffix(".png")
        try:
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
                [tesseract, str(image_path), "stdout", "-l", language, "--psm", "6"],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if ocr.returncode != 0:
                raise RuntimeError(ocr.stderr.strip() or "tesseract failed")
            normalized = " ".join(ocr.stdout.split())
            ocr_chars = len(normalized)
            source_chars = int(candidate["source_text_chars"])
            result.update(
                {
                    "status": "ok",
                    "ocr_text_chars": ocr_chars,
                    "ocr_text_sha256": hashlib.sha256(
                        normalized.encode("utf-8")
                    ).hexdigest(),
                    "improved_over_embedded_text": ocr_chars >= source_chars + 50,
                }
            )
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            result["elapsed_seconds"] = round(time.monotonic() - started, 4)
    return result


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile)))
    return round(float(ordered[index]), 4)


def build_report(
    *,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    results: list[dict[str, Any]],
    manifest_path: Path,
    dpi: int,
    language: str,
    tool_versions: dict[str, str],
) -> dict[str, Any]:
    successes = [row for row in results if row["status"] == "ok"]
    elapsed = [float(row["elapsed_seconds"] or 0) for row in results]
    return {
        "schema_version": "pdf_ocr_routing_benchmark_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok" if len(successes) == len(results) else "partial",
        "manifest_ref": str(manifest_path),
        "routing": {
            "candidate_pages_total": len(candidates),
            "candidate_pdf_files_total": len({row["path"] for row in candidates}),
            "empty_text_pages_total": sum(
                row["reason"] == "empty_text" for row in candidates
            ),
            "sparse_text_pages_total": sum(
                row["reason"] == "sparse_text" for row in candidates
            ),
            "sample_pages": len(selected),
            "sample_pdf_files": len({row["path"] for row in selected}),
            "selection": "one empty page per document, then one sparse page per document, then deterministic remainder",
        },
        "ocr": {
            "dpi": dpi,
            "language": language,
            "succeeded": len(successes),
            "failed": len(results) - len(successes),
            "improved_over_embedded_text": sum(
                bool(row["improved_over_embedded_text"]) for row in successes
            ),
            "source_text_chars": sum(
                int(row["source_text_chars"]) for row in successes
            ),
            "ocr_text_chars": sum(int(row["ocr_text_chars"]) for row in successes),
            "elapsed_seconds_total": round(sum(elapsed), 4),
            "elapsed_seconds_p50": _percentile(elapsed, 0.50),
            "elapsed_seconds_p95": _percentile(elapsed, 0.95),
        },
        "tool_versions": tool_versions,
        "results": results,
        "limitations": [
            "This is a deterministic routed sample, not full OCR of every candidate page.",
            "More OCR characters do not prove better semantic accuracy; human quality sampling remains required.",
            "No OCR text is promoted or published by this benchmark; only hashes and metrics are retained.",
            "The current local corpus does not prove scanned-PDF diversity or 100k-document throughput.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_pages < 1 or args.workers < 1 or args.dpi < 72 or args.timeout <= 0:
        print("ERROR: max-pages/workers/dpi/timeout are out of range")
        return 2
    root = Path(args.root)
    manifest_path = Path(args.manifest)
    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    if not root.is_dir() or not manifest_path.is_file() or not pdftoppm or not tesseract:
        print("ERROR: root, manifest, pdftoppm, and tesseract are required")
        return 2
    try:
        candidates = load_candidates(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    selected = select_diverse_candidates(candidates, args.max_pages)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(
            executor.map(
                lambda candidate: ocr_page(
                    candidate,
                    root=root,
                    pdftoppm=pdftoppm,
                    tesseract=tesseract,
                    dpi=args.dpi,
                    language=args.language,
                    timeout=args.timeout,
                ),
                selected,
            )
        )
    report = build_report(
        candidates=candidates,
        selected=selected,
        results=results,
        manifest_path=manifest_path,
        dpi=args.dpi,
        language=args.language,
        tool_versions={
            "pdftoppm": _tool_version(pdftoppm, "-v"),
            "tesseract": _tool_version(tesseract),
        },
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidates": len(candidates),
                "sampled": len(selected),
                "succeeded": report["ocr"]["succeeded"],
                "out": str(out_path),
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
