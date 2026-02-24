#!/usr/bin/env python3
"""Fail when public artifacts contain local-path or email leaks."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_SCAN_PATHS = (Path("docs/gh-pages"), Path("etl/data/published"))
SKIP_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".gz",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".pdf",
}
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("local_file_url", re.compile(r"file:///Users/[^\r\n\"']+")),
    ("local_user_path", re.compile(r"/Users/[^/\s]+/")),
    ("gdrive_email_segment", re.compile(r"GoogleDrive-[^/\s]+@[^\s/]+")),
    ("email", EMAIL_RE),
)


@dataclass
class Finding:
    path: Path
    line: int
    kind: str
    snippet: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check public artifacts for private path/email leaks")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Path to scan (repeatable). Defaults to docs/gh-pages and etl/data/published.",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=200,
        help="Maximum findings to print before truncating output.",
    )
    return parser.parse_args()


def iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for root in paths:
        if root.is_file():
            yield root
            continue
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if file_path.is_file():
                yield file_path


def read_text_file(path: Path) -> str | None:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def build_snippet(text: str, start: int, end: int, radius: int = 64) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].replace("\n", " ").replace("\r", " ").strip()
    if len(snippet) > 160:
        snippet = snippet[:157] + "..."
    return snippet


def collect_findings(paths: list[Path]) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    files_scanned = 0
    for file_path in iter_files(paths):
        text = read_text_file(file_path)
        if text is None:
            continue
        files_scanned += 1
        for kind, pattern in LEAK_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(
                    Finding(
                        path=file_path,
                        line=line,
                        kind=kind,
                        snippet=build_snippet(text, match.start(), match.end()),
                    )
                )
    return findings, files_scanned


def main() -> int:
    args = parse_args()
    targets = [Path(p) for p in args.path] if args.path else list(DEFAULT_SCAN_PATHS)
    findings, files_scanned = collect_findings(targets)
    if not findings:
        print(f"OK privacy leak scan: no findings (files_scanned={files_scanned})")
        return 0

    findings.sort(key=lambda f: (str(f.path), f.line, f.kind))
    max_findings = max(1, int(args.max_findings))
    shown = findings[:max_findings]
    print(
        "Privacy leak scan failed: "
        f"{len(findings)} finding(s) across {len({str(f.path) for f in findings})} file(s)."
    )
    for finding in shown:
        print(f"{finding.path}:{finding.line}: [{finding.kind}] {finding.snippet}")
    if len(findings) > len(shown):
        print(f"... truncated {len(findings) - len(shown)} additional finding(s)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
