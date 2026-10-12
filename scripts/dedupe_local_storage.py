#!/usr/bin/env python3
"""Reclaim disk by turning byte-identical local data files into copy-on-write clones.

Lossless: every path keeps an independent file with the same bytes; duplicates
just share disk blocks (APFS clonefile / Linux reflink). Nothing is deleted.
Dry-run by default; pass --apply to rewrite duplicates.

Note: `du` counts each clone separately; check reclaimed space with `df`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.storage import try_clone  # noqa: E402

DEFAULT_ROOTS = ("etl/data", "ui/site")
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__"}


def _blake2b(path: Path) -> str:
    digest = hashlib.blake2b(digest_size=32)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicate_groups(roots: list[Path], *, min_bytes: int) -> list[list[Path]]:
    """Group regular files by identical content (size, then full hash).

    Files that are already hardlinks of each other (same inode) count once.
    """
    by_size: dict[int, dict[tuple[int, int], Path]] = defaultdict(dict)
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            for name in filenames:
                path = Path(dirpath) / name
                try:
                    st = path.lstat()
                except OSError:
                    continue
                if not path.is_file() or path.is_symlink() or st.st_size < min_bytes:
                    continue
                by_size[st.st_size].setdefault((st.st_dev, st.st_ino), path)
    groups: list[list[Path]] = []
    for size in sorted(by_size, reverse=True):
        candidates = list(by_size[size].values())
        if len(candidates) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in candidates:
            try:
                by_hash[_blake2b(path)].append(path)
            except OSError:
                continue
        groups.extend(sorted(g) for g in by_hash.values() if len(g) > 1)
    return groups


def replace_with_clone(original: Path, duplicate: Path) -> bool:
    """Atomically replace ``duplicate`` with a clone of ``original``.

    Re-verifies bytes after cloning and keeps the duplicate's mode/mtime.
    """
    st = duplicate.stat()
    staged = duplicate.with_name(f".{duplicate.name}.{uuid.uuid4().hex}.clone")
    if not try_clone(original, staged):
        return False
    try:
        if staged.stat().st_size != st.st_size or _blake2b(staged) != _blake2b(duplicate):
            raise RuntimeError(f"clone verification failed for {duplicate}")
        os.chmod(staged, st.st_mode & 0o7777)
        os.utime(staged, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.replace(staged, duplicate)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", default=list(DEFAULT_ROOTS))
    parser.add_argument("--min-bytes", type=int, default=64 * 1024)
    parser.add_argument("--apply", action="store_true", help="rewrite duplicates as clones")
    parser.add_argument("--top", type=int, default=10, help="largest groups to list")
    args = parser.parse_args(argv)

    roots = [Path(r) for r in args.roots if Path(r).exists()]
    groups = find_duplicate_groups(roots, min_bytes=args.min_bytes)
    reclaimable = sum(g[0].stat().st_size * (len(g) - 1) for g in groups)

    cloned = failed = reclaimed = 0
    if args.apply:
        for group in groups:
            original, size = group[0], group[0].stat().st_size
            for duplicate in group[1:]:
                if replace_with_clone(original, duplicate):
                    cloned += 1
                    reclaimed += size
                else:
                    failed += 1

    top = sorted(groups, key=lambda g: g[0].stat().st_size * (len(g) - 1), reverse=True)
    print(
        json.dumps(
            {
                "roots": [r.as_posix() for r in roots],
                "duplicate_groups": len(groups),
                "duplicate_files": sum(len(g) - 1 for g in groups),
                "reclaimable_bytes": reclaimable,
                "applied": bool(args.apply),
                "cloned_files": cloned,
                "clone_unsupported_files": failed,
                "reclaimed_bytes": reclaimed,
                "top_groups": [
                    {"bytes_each": g[0].stat().st_size, "copies": len(g), "paths": [p.as_posix() for p in g[:3]]}
                    for g in top[: args.top]
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
