#!/usr/bin/env python3
"""Stream-sanitize workstation paths in JSON or gzip JSON."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path


LOCAL_JSON_STRING_RE = re.compile(
    r'"(?:[^"\\]|\\.)*(?:file:///|/Users/|/home/)(?:[^"\\]|\\.)*"'
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitize a JSON or gzip JSON artifact")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--in-place", action="store_true")
    return parser.parse_args(argv)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize_gzip_json(source: Path, destination: Path) -> dict[str, object]:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    local_strings_redacted = 0
    lines = 0
    try:
        with gzip.open(source, "rt", encoding="utf-8", errors="strict") as input_handle:
            with partial.open("xb") as raw_output:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=raw_output,
                    compresslevel=9,
                    mtime=0,
                ) as zipped_output:
                    for line in input_handle:
                        lines += 1
                        line, local_count = LOCAL_JSON_STRING_RE.subn(
                            json.dumps("<redacted-local-reference>"), line
                        )
                        local_strings_redacted += local_count
                        zipped_output.write(line.encode("utf-8"))
                raw_output.flush()
                os.fsync(raw_output.fileno())
        os.replace(partial, destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return {
        "schema_version": "public_gzip_json_sanitization_v2",
        "input_file": source.name,
        "output_file": destination.name,
        "lines": lines,
        "local_strings_redacted": local_strings_redacted,
        "official_public_emails_retained": True,
        "output_bytes": int(destination.stat().st_size),
        "output_sha256": _sha256_file(destination),
    }


def sanitize_plain_json(source: Path, destination: Path) -> dict[str, object]:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    local_strings_redacted = 0
    lines = 0
    try:
        with source.open("rt", encoding="utf-8", errors="strict") as input_handle:
            with partial.open("xb") as output_handle:
                for line in input_handle:
                    lines += 1
                    line, local_count = LOCAL_JSON_STRING_RE.subn(
                        json.dumps("<redacted-local-reference>"), line
                    )
                    local_strings_redacted += local_count
                    output_handle.write(line.encode("utf-8"))
                output_handle.flush()
                os.fsync(output_handle.fileno())
        os.replace(partial, destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return {
        "schema_version": "public_json_sanitization_v2",
        "input_file": source.name,
        "output_file": destination.name,
        "lines": lines,
        "local_strings_redacted": local_strings_redacted,
        "official_public_emails_retained": True,
        "output_bytes": int(destination.stat().st_size),
        "output_sha256": _sha256_file(destination),
    }


def sanitize_json_artifact(source: Path, destination: Path) -> dict[str, object]:
    if Path(source).suffix.lower() == ".gz":
        return sanitize_gzip_json(source, destination)
    return sanitize_plain_json(source, destination)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = Path(args.input)
    if not source.is_file():
        print(f"ERROR: input not found: {source.name}", file=sys.stderr)
        return 2
    if args.in_place and str(args.out).strip():
        print("ERROR: choose --in-place or --out, not both", file=sys.stderr)
        return 2
    if args.in_place:
        destination = source
    elif str(args.out).strip():
        destination = Path(args.out)
    else:
        print("ERROR: --out or --in-place is required", file=sys.stderr)
        return 2
    try:
        report = sanitize_json_artifact(source, destination)
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
