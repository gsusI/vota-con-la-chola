#!/usr/bin/env python3
"""Fail when repo-root junk files or malformed ignore patterns are present."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


NUMERIC_ARTIFACT_RE = re.compile(r"^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    detail: str
    line: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check repo root for accidental command artifacts")
    parser.add_argument(
        "--root",
        default=".",
        help="Path inside the git repo to inspect. Defaults to the current directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of text.",
    )
    return parser.parse_args()


def git_repo_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"could not determine git repo root for {path}")
    return Path(result.stdout.strip()).resolve()


def tracked_paths(repo_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("could not enumerate tracked paths")
    raw = result.stdout.decode("utf-8", errors="replace")
    return {entry for entry in raw.split("\0") if entry}


def suspicious_root_entry_detail(name: str) -> str | None:
    if name == "-":
        return "literal '-' command artifact at repo root"
    if name.startswith("python3 scripts"):
        return "misquoted command artifact path at repo root"
    if name.startswith("{"):
        return "template/interpolation artifact at repo root"
    if NUMERIC_ARTIFACT_RE.fullmatch(name):
        return "numeric command artifact at repo root"
    return None


def collect_suspicious_root_entry_findings(repo_root: Path, tracked: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for entry in sorted(repo_root.iterdir(), key=lambda item: item.name):
        rel = entry.relative_to(repo_root).as_posix()
        if rel in tracked:
            continue
        detail = suspicious_root_entry_detail(rel)
        if detail is None:
            continue
        findings.append(Finding(kind="suspicious_root_entry", path=rel, detail=detail))
    return findings


def collect_empty_root_file_findings(repo_root: Path, tracked: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for entry in sorted(repo_root.iterdir(), key=lambda item: item.name):
        if not entry.is_file():
            continue
        rel = entry.relative_to(repo_root).as_posix()
        if rel in tracked:
            continue
        if suspicious_root_entry_detail(rel) is not None:
            continue
        try:
            size = entry.stat().st_size
        except OSError:
            continue
        if size != 0:
            continue
        findings.append(Finding(kind="empty_root_file", path=rel, detail="untracked zero-byte file at repo root"))
    return findings


def collect_gitignore_findings(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.exists():
        return findings
    try:
        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return findings
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("/{"):
            findings.append(
                Finding(
                    kind="invalid_gitignore_pattern",
                    path=".gitignore",
                    line=line_no,
                    detail=stripped,
                )
            )
    return findings


def collect_findings(repo_root: Path) -> list[Finding]:
    tracked = tracked_paths(repo_root)
    findings = collect_suspicious_root_entry_findings(repo_root, tracked)
    findings.extend(collect_empty_root_file_findings(repo_root, tracked))
    findings.extend(collect_gitignore_findings(repo_root))
    findings.sort(key=lambda finding: (finding.kind, finding.path, finding.line or 0, finding.detail))
    return findings


def findings_to_json(repo_root: Path, findings: list[Finding]) -> str:
    payload = {
        "ok": not findings,
        "repo_root": str(repo_root),
        "findings": [asdict(finding) for finding in findings],
        "counts": {
            "findings_total": len(findings),
            "empty_root_file": sum(1 for finding in findings if finding.kind == "empty_root_file"),
            "suspicious_root_entry": sum(1 for finding in findings if finding.kind == "suspicious_root_entry"),
            "invalid_gitignore_pattern": sum(
                1 for finding in findings if finding.kind == "invalid_gitignore_pattern"
            ),
        },
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def render_text(repo_root: Path, findings: list[Finding]) -> str:
    if not findings:
        return f"OK repo root hygiene: no findings (repo_root={repo_root})"
    lines = [
        f"Repo root hygiene failed: {len(findings)} finding(s) (repo_root={repo_root})",
    ]
    for finding in findings:
        if finding.line is not None:
            lines.append(f"{finding.path}:{finding.line}: [{finding.kind}] {finding.detail}")
        else:
            lines.append(f"{finding.path}: [{finding.kind}] {finding.detail}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    try:
        repo_root = git_repo_root(Path(args.root).resolve())
        findings = collect_findings(repo_root)
    except RuntimeError as exc:
        if args.json:
            print(
                json.dumps(
                    {"ok": False, "repo_root": None, "findings": [], "error": str(exc)},
                    ensure_ascii=True,
                    indent=2,
                )
            )
        else:
            print(f"Repo root hygiene check error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(findings_to_json(repo_root, findings))
    else:
        print(render_text(repo_root, findings))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
