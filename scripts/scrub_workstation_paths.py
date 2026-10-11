#!/usr/bin/env python3
"""Rewrite workstation-identifying paths in repo text files.

- Absolute paths to a checkout of this repo (any parent, with or without
  ``file://``) become repo-relative.
- Any other home-directory prefix becomes ``~/``.
- Google Drive account segments are redacted.

Use ``--check`` in CI/pre-commit to fail without writing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_DIR_NAME = "vota-con-la-chola"
HOME_PREFIXES = ("/" + "Users" + "/", "/" + "home" + "/")
_HOME_ALT = "|".join(re.escape(p.rstrip("/")) for p in HOME_PREFIXES)

# Segments may contain spaces ("My Drive") but never quotes, backticks or newlines.
_SEGMENT = r"[^/\n\"'`]+"
# Not preceded by a path/URL character, so ".../PRODSTS/Users/Login" in official URLs is left alone.
_START = r"(?<![\w.~/-])"
REPO_ROOT_RE = re.compile(
    rf"{_START}(?:file://)?(?:{_HOME_ALT})/{_SEGMENT}(?:/{_SEGMENT})*?/{re.escape(REPO_DIR_NAME)}(?P<tail>/|(?=[\"'`\s)\],;]|$))"
)
HOME_USER_RE = re.compile(rf"{_START}(?:file://)?(?:{_HOME_ALT})/[^/\s\"'`]+/")
GDRIVE_ACCOUNT_RE = re.compile(r"GoogleDrive-[^/\s\"'`]+@[^/\s\"'`]+")
SKIP_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".parquet", ".zip", ".gz", ".png", ".jpg", ".jpeg", ".webp", ".pdf", ".xlsx"}


def scrub_text(text: str) -> str:
    text = REPO_ROOT_RE.sub(lambda m: "" if m.group("tail") == "/" else ".", text)
    text = HOME_USER_RE.sub("~/", text)
    return GDRIVE_ACCOUNT_RE.sub("GoogleDrive-<redacted-account>", text)


def iter_files(paths: list[Path]):
    for root in paths:
        if root.is_file():
            yield root
        elif root.is_dir():
            yield from (p for p in sorted(root.rglob("*")) if p.is_file())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--check", action="store_true", help="Report files that would change; do not write")
    args = parser.parse_args(argv)

    changed: list[Path] = []
    for path in iter_files(args.paths):
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            original = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scrubbed = scrub_text(original)
        if scrubbed == original:
            continue
        changed.append(path)
        if not args.check:
            path.write_bytes(scrubbed.encode("utf-8"))

    verb = "would change" if args.check else "scrubbed"
    for path in changed:
        print(f"{verb}: {path}")
    print(f"{len(changed)} file(s) {verb}")
    return 1 if (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
