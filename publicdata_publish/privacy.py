from __future__ import annotations

import argparse
from dataclasses import dataclass
import mmap
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable


DEFAULT_SCAN_PATHS = (
    Path("etl/data/published"),
    Path("ui/gh-pages-next/public"),
    Path("ui/gh-pages-next/out"),
)
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
LOCAL_USERS_PREFIX = "/" + "Users" + "/"
LOCAL_FILE_USERS_PREFIX = "file://" + LOCAL_USERS_PREFIX
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("local_file_url", re.compile(re.escape(LOCAL_FILE_USERS_PREFIX) + r"[^\r\n\"']+")),
    ("local_user_path", re.compile(re.escape(LOCAL_USERS_PREFIX) + r"[^/\s]+/")),
    ("gdrive_email_segment", re.compile(r"GoogleDrive-[^/\s]+@[^\s/]+")),
    ("email", EMAIL_RE),
    ("internal_db_path", re.compile(r'"db_path"\s*:\s*"[^"\r\n]+"')),
)
LEAK_PREFILTERS: dict[str, tuple[str, ...]] = {
    "local_file_url": (LOCAL_FILE_USERS_PREFIX,),
    "local_user_path": (LOCAL_USERS_PREFIX,),
    "gdrive_email_segment": ("GoogleDrive-", "@"),
    "email": ("@",),
    "internal_db_path": ('"db_path"',),
}
LEAK_SENTINELS = tuple(sorted({token for tokens in LEAK_PREFILTERS.values() for token in tokens}))
LEAK_SENTINEL_BYTES = tuple(token.encode("utf-8") for token in LEAK_SENTINELS)
LEAK_SENTINEL_BYTES_RE = re.compile(b"|".join(re.escape(token) for token in LEAK_SENTINEL_BYTES))
LARGE_FILE_PREFILTER_BYTES = 1024 * 1024


@dataclass
class Finding:
    path: Path
    line: int
    kind: str
    snippet: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check public artifacts for private path/email leaks")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Path to scan (repeatable). Defaults to static app public/out and etl/data/published.",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=200,
        help="Maximum findings to print before truncating output.",
    )
    return parser.parse_args(argv)


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


def file_is_scannable(path: Path) -> bool:
    return path.suffix.lower() not in SKIP_SUFFIXES


def build_snippet(text: str, start: int, end: int, radius: int = 64) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].replace("\n", " ").replace("\r", " ").strip()
    if len(snippet) > 160:
        snippet = snippet[:157] + "..."
    return snippet


def may_contain_leak_candidate(text: str) -> bool:
    return any(token in text for token in LEAK_SENTINELS)


def should_scan_pattern(text: str, kind: str) -> bool:
    return all(token in text for token in LEAK_PREFILTERS.get(kind, ()))


def collect_rg_candidate_paths(paths: list[Path]) -> set[str] | None:
    if shutil.which("rg") is None:
        return None
    scan_roots = [str(path) for path in paths if path.exists()]
    if not scan_roots:
        return set()
    cmd = ["rg", "--files-with-matches", "--fixed-strings", "--no-messages"]
    for token in LEAK_SENTINELS:
        cmd.extend(["-e", token])
    cmd.extend(["--", *scan_roots])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return None
    if result.returncode not in (0, 1):
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def large_file_may_contain_leak_candidate(path: Path) -> bool:
    try:
        if path.stat().st_size <= LARGE_FILE_PREFILTER_BYTES:
            return True
        with path.open("rb") as handle:
            with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as payload:
                return LEAK_SENTINEL_BYTES_RE.search(payload) is not None
    except (OSError, ValueError):
        return False


def collect_findings(paths: list[Path]) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    files_scanned = 0
    rg_candidate_paths = collect_rg_candidate_paths(paths)
    for file_path in iter_files(paths):
        if not file_is_scannable(file_path):
            continue
        files_scanned += 1
        if rg_candidate_paths is not None:
            if str(file_path) not in rg_candidate_paths:
                continue
        elif not large_file_may_contain_leak_candidate(file_path):
            continue
        text = read_text_file(file_path)
        if text is None:
            continue
        if not may_contain_leak_candidate(text):
            continue
        for kind, pattern in LEAK_PATTERNS:
            if not should_scan_pattern(text, kind):
                continue
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
