#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ERROR_MARKERS = (
    '__next_error__',
    'NEXT_HTTP_ERROR_FALLBACK;404',
)


def iter_html_files(root: Path):
    if root.is_file():
        if root.suffix.lower() == ".html":
            yield root
        return
    yield from root.rglob("*.html")


def find_notfound_payloads(paths: list[Path]) -> list[Path]:
    findings: list[Path] = []
    for root in paths:
        if not root.exists():
            raise FileNotFoundError(f"path does not exist: {root}")
        for html_path in iter_html_files(root):
            text = html_path.read_text(encoding="utf-8", errors="ignore")
            if any(marker in text for marker in ERROR_MARKERS):
                findings.append(html_path)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail when a static Next export contains rendered notFound/error payload pages.",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        required=True,
        help="Export path or HTML file to scan. Repeatable.",
    )
    parser.add_argument(
        "--max-report",
        type=int,
        default=50,
        help="Maximum finding paths to print.",
    )
    args = parser.parse_args(argv)

    paths = [Path(item) for item in args.paths]
    findings = find_notfound_payloads(paths)
    if findings:
        print(f"ERROR: Next static export contains notFound/error payloads (count={len(findings)})", file=sys.stderr)
        for html_path in findings[: args.max_report]:
            print(html_path, file=sys.stderr)
        if len(findings) > args.max_report:
            print(f"... {len(findings) - args.max_report} more", file=sys.stderr)
        return 1

    print(f"OK Next notFound payload scan: no findings (files_scanned={sum(1 for root in paths for _ in iter_html_files(root))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
