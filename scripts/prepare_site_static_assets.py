#!/usr/bin/env python3
"""Mirror the built site into Workers Static Assets, leaving bulk subtrees to the R2 origin.

Static assets are served without running the Worker, so they cost no Worker requests
(Workers Free allows 100k/day) however much traffic a campaign brings. Bulk, rarely
visited subtrees and files over the 25 MiB asset limit stay in R2 and reach the Worker
only on a miss (not_found_handling = "none").
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from publicdata_core.storage import clone_or_copy  # noqa: E402

# Workers Free: 20,000 files per version and 25 MiB per file; keep headroom.
MAX_FILES = 19_000
MAX_FILE_BYTES = 25 * 1024 * 1024
# Served from R2 only: the content-addressed PLACSP release (35k files, rarely changes) plus the
# subtrees other publishers write. Everything else is a static asset.
R2_ONLY_PREFIXES = ("spending/launch/", "releases/", "datasets/", "downloads/")


def served_from_r2(rel: str, size: int) -> bool:
    return rel.startswith(R2_ONLY_PREFIXES) or size > MAX_FILE_BYTES
HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
/_next/static/*
  Cache-Control: public, max-age=31536000, immutable
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--output", default="infra/cloudflare/votaconlachola-worker/public", type=Path)
    args = parser.parse_args()
    site, dest = args.site, args.output
    if not (site / "index.html").is_file() or not (site / "_next/static").is_dir():
        raise SystemExit(f"{site} is not a built site")

    selected, oversized = [], []
    for path in sorted(p for p in site.rglob("*") if p.is_file()):
        rel = path.relative_to(site).as_posix()
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        size = path.stat().st_size
        if served_from_r2(rel, size):
            if size > MAX_FILE_BYTES:
                oversized.append(path)
            continue
        selected.append(path)
    if len(selected) > MAX_FILES:
        raise SystemExit(f"{len(selected)} static assets exceed the Workers Free budget of {MAX_FILES}")

    # Rebuild from scratch so removed pages never linger as assets shadowing R2.
    shutil.rmtree(dest, ignore_errors=True)
    for path in selected:
        out = dest / path.relative_to(site)
        out.parent.mkdir(parents=True, exist_ok=True)
        clone_or_copy(path, out)
    (dest / "_headers").write_text(HEADERS)
    print(json.dumps({
        "files": len(selected),
        "bytes": sum(p.stat().st_size for p in selected),
        "left_in_r2_oversized": [p.relative_to(site).as_posix() for p in oversized],
        "r2_only_prefixes": list(R2_ONLY_PREFIXES),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
