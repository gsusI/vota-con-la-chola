#!/usr/bin/env python3
"""Publish single-file copies of archives that the site ships split into parts.

Releases such as ``spending/launch/<sha>/placsp-launch.zip.part-NNNN`` are split
because the git record (``gh-pages``) caps file sizes. The R2 origin has no such
limit, so this joins the parts, verifies every part and the whole archive
against ``spending/launch/latest.json``, and uploads one file to
``/downloads/<release>/<archive>``. The hash-pinned release itself is untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import publish_site_origin as origin  # noqa: E402

POINTERS = ("spending/launch/latest.json",)
DOWNLOADS_DIR = "downloads/"


def join_archive(site: Path, pointer_path: str) -> list[tuple[str, bytes, str]]:
    pointer = json.loads((site / pointer_path).read_text())
    release = str(pointer["release"])
    release_dir = site / Path(pointer_path).parent / release
    archives = []
    for name, parts in (pointer.get("file_parts") or {}).items():
        chunks = []
        for part in parts:
            body = (release_dir / part["path"]).read_bytes()
            if len(body) != part["bytes"] or hashlib.sha256(body).hexdigest() != part["sha256"]:
                raise SystemExit(f"Part {part['path']} does not match {pointer_path}")
            chunks.append(body)
        joined = b"".join(chunks)
        sha = hashlib.sha256(joined).hexdigest()
        expected = pointer.get("archive_sha256") if len(pointer["file_parts"]) == 1 else None
        if expected and sha != expected:
            raise SystemExit(f"{name}: joined sha256 {sha} != archive_sha256 {expected}")
        archives.append((f"{DOWNLOADS_DIR}{release}/{name}", joined, sha))
    return archives


def publish(client: Any, bucket: str, archives: list[tuple[str, bytes, str]]) -> dict[str, Any]:
    remote = origin.list_remote(client, bucket, origin.SITE_PREFIX + DOWNLOADS_DIR)
    uploaded = []
    for rel, body, sha in archives:
        key = origin.SITE_PREFIX + rel
        if remote.get(key) == hashlib.md5(body, usedforsecurity=False).hexdigest():
            continue
        origin.put_bytes(client, bucket, key, body, origin.content_type_for(rel), sha)
        uploaded.append(rel)
    return {"archives": [{"path": f"/{rel}", "bytes": len(body), "sha256": sha} for rel, body, sha in archives], "uploaded": uploaded}


def main(argv: list[str] | None = None, *, client: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--bucket", default=origin.DEFAULT_BUCKET)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    archives = [a for pointer in POINTERS if (args.site / pointer).is_file() for a in join_archive(args.site, pointer)]
    report: dict[str, Any] = {"archives": [{"path": f"/{rel}", "bytes": len(body), "sha256": sha} for rel, body, sha in archives]}
    if not args.dry_run:
        report = publish(client or origin.make_client(), args.bucket, archives)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
