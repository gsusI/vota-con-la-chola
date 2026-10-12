#!/usr/bin/env python3
"""Mirror the latest Hugging Face dataset snapshot into the site origin (R2).

The explorer reads ``/datasets/latest.json`` and the snapshot Parquet files from
votaconlachola.org, so Hugging Face stays a public replica instead of a runtime
dependency. Every file is checked against the snapshot's ``checksums.sha256``
before upload; ``latest.json`` is written last so readers never see a partial
snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import publish_site_origin as origin  # noqa: E402

DEFAULT_REPO = "JesusIC/vota-con-la-chola-data"
DATASETS_PREFIX = f"{origin.SITE_PREFIX}datasets/"
USER_AGENT = "vota-con-la-chola-dataset-mirror/1"

Fetch = Callable[[str], bytes]


def http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def resolve_url(repo: str, rel: str) -> str:
    return f"https://huggingface.co/datasets/{repo}/resolve/main/{urllib.parse.quote(rel)}"


def tree_url(repo: str, rel: str) -> str:
    return f"https://huggingface.co/api/datasets/{repo}/tree/main/{urllib.parse.quote(rel)}?recursive=true"


def parse_checksums(text: str) -> dict[str, str]:
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            sums[parts[1].lstrip("*").lstrip("./")] = parts[0].lower()
    return sums


def collect_snapshot(repo: str, fetch: Fetch) -> tuple[bytes, str, dict[str, bytes]]:
    latest_body = fetch(resolve_url(repo, "latest.json"))
    snapshot_dir = str(json.loads(latest_body).get("snapshot_dir") or "").strip("/")
    if not snapshot_dir.startswith("snapshots/"):
        raise SystemExit(f"Unexpected snapshot_dir in latest.json: {snapshot_dir!r}")

    entries = json.loads(fetch(tree_url(repo, snapshot_dir)))
    paths = sorted(e["path"] for e in entries if e.get("type") == "file")
    if not paths:
        raise SystemExit(f"No files under {snapshot_dir}")
    checksums_path = f"{snapshot_dir}/checksums.sha256"
    if checksums_path not in paths:
        raise SystemExit(f"{checksums_path} missing: refusing to mirror an unverifiable snapshot")

    with ThreadPoolExecutor(max_workers=8) as pool:
        bodies = dict(zip(paths, pool.map(lambda p: fetch(resolve_url(repo, p)), paths)))

    sums = parse_checksums(bodies[checksums_path].decode())
    verified = 0
    for path, body in bodies.items():
        rel = path[len(snapshot_dir) + 1 :]
        expected = sums.get(rel)
        if expected is None:
            continue
        if hashlib.sha256(body).hexdigest() != expected:
            raise SystemExit(f"sha256 mismatch for {path}")
        verified += 1
    parquet = [p for p in paths if p.endswith(".parquet")]
    unverified_parquet = [p for p in parquet if p[len(snapshot_dir) + 1 :] not in sums]
    if unverified_parquet:
        raise SystemExit(f"{len(unverified_parquet)} Parquet files lack checksums, e.g. {unverified_parquet[:3]}")
    print(f"verified {verified}/{len(paths)} files against checksums.sha256", file=sys.stderr)
    return latest_body, snapshot_dir, bodies


def mirror(client: Any, bucket: str, latest_body: bytes, snapshot_dir: str, bodies: dict[str, bytes], workers: int) -> dict[str, Any]:
    remote = origin.list_remote(client, bucket, f"{DATASETS_PREFIX}{snapshot_dir}/")

    def key_for(path: str) -> str:
        return f"{DATASETS_PREFIX}{path}"

    changed = [p for p, body in bodies.items() if remote.get(key_for(p)) != hashlib.md5(body, usedforsecurity=False).hexdigest()]

    def upload(path: str) -> None:
        body = bodies[path]
        origin.put_bytes(client, bucket, key_for(path), body, origin.content_type_for(path), hashlib.sha256(body).hexdigest())

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(upload, changed))

    after = origin.list_remote(client, bucket, f"{DATASETS_PREFIX}{snapshot_dir}/")
    missing = [p for p, body in bodies.items() if after.get(key_for(p)) != hashlib.md5(body, usedforsecurity=False).hexdigest()]
    if missing:
        raise SystemExit(f"Parity check failed for {len(missing)} dataset objects, e.g. {missing[:3]}")

    origin.put_bytes(
        client, bucket, f"{DATASETS_PREFIX}latest.json", latest_body, origin.CONTENT_TYPES[".json"], hashlib.sha256(latest_body).hexdigest()
    )
    return {
        "snapshot_dir": snapshot_dir,
        "files": len(bodies),
        "bytes": sum(len(b) for b in bodies.values()),
        "uploaded": len(changed),
        "parity_verified": len(bodies),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset-repo", default=os.environ.get("HF_DATASET_REPO_ID") or DEFAULT_REPO)
    parser.add_argument("--bucket", default=origin.DEFAULT_BUCKET)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true", help="Download and verify only; no upload")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, client: Any = None, fetch: Fetch = http_get) -> int:
    args = parse_args(argv)
    if "/" not in args.dataset_repo:
        # Same convention as publicar_hf_snapshot.py: bare names live under HF_USERNAME.
        user = os.environ.get("HF_USERNAME", "").strip()
        args.dataset_repo = f"{user}/{args.dataset_repo}" if user else DEFAULT_REPO
    latest_body, snapshot_dir, bodies = collect_snapshot(args.dataset_repo, fetch)
    report: dict[str, Any] = {
        "dataset_repo": args.dataset_repo,
        "snapshot_dir": snapshot_dir,
        "files": len(bodies),
        "bytes": sum(len(b) for b in bodies.values()),
        "dry_run": args.dry_run,
    }
    if not args.dry_run:
        report |= mirror(client or origin.make_client(), args.bucket, latest_body, snapshot_dir, bodies, args.workers)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
