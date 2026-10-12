#!/usr/bin/env python3
"""Sync a built public site into the R2 origin bucket and publish a hash manifest.

Only changed files are uploaded (R2 single-part ETag == MD5). Every upload is
verified by re-listing before stale objects are deleted. Each run writes a
public release manifest (path, size, sha256) under ``site/releases/`` so anyone
can check that what the site serves matches the published release.

Credentials come from the environment (S3-compatible API, so the same script
works against any S3 origin): R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and
R2_ACCOUNT_ID (or R2_ENDPOINT_URL).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUCKET = "vclc-site"
SITE_PREFIX = "site/"
RELEASES_DIR = "releases/"
MANIFEST_SCHEMA = "vclc.site_release.v1"
# Keep in sync with resolveContentType in infra/cloudflare/votaconlachola-worker/src/index.js.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".wasm": "application/wasm",
    ".parquet": "application/vnd.apache.parquet",
    ".gz": "application/gzip",
    ".zip": "application/zip",
    ".pdf": "application/pdf",
}


@dataclass(frozen=True)
class LocalFile:
    path: str
    size: int
    md5: str
    sha256: str
    content_type: str


def content_type_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in CONTENT_TYPES:
        return CONTENT_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def is_published(rel: Path) -> bool:
    # Dotfiles (.git, .nojekyll, .DS_Store) are workstation/host artifacts, never site content.
    return not any(part.startswith(".") for part in rel.parts)


def scan_site(site: Path, *, workers: int = 8) -> list[LocalFile]:
    paths = sorted(
        p for p in site.rglob("*") if p.is_file() and not p.is_symlink() and is_published(p.relative_to(site))
    )

    def digest(path: Path) -> LocalFile:
        md5 = hashlib.md5(usedforsecurity=False)
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                md5.update(chunk)
                sha.update(chunk)
        rel = path.relative_to(site).as_posix()
        return LocalFile(rel, path.stat().st_size, md5.hexdigest(), sha.hexdigest(), content_type_for(rel))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        files = list(pool.map(digest, paths))
    if any(f.path.startswith(RELEASES_DIR) for f in files):
        raise SystemExit(f"Site build must not contain {RELEASES_DIR}: that subtree is reserved for release manifests")
    return files


def build_manifest(files: list[LocalFile], *, release_id: str, source_commit: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "release_id": release_id,
        "source_commit": source_commit,
        "generated_at": generated_at,
        "file_count": len(files),
        "total_bytes": sum(f.size for f in files),
        "files": [{"path": f.path, "size": f.size, "sha256": f.sha256} for f in files],
    }


def make_client() -> Any:
    import boto3  # type: ignore[import-not-found]

    endpoint = os.environ.get("R2_ENDPOINT_URL")
    if not endpoint:
        account = os.environ.get("R2_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        if not account:
            raise SystemExit("Set R2_ENDPOINT_URL or R2_ACCOUNT_ID")
        endpoint = f"https://{account}.r2.cloudflarestorage.com"
    for name in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not os.environ.get(name):
            raise SystemExit(f"Missing {name}")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def list_remote(client: Any, bucket: str, prefix: str) -> dict[str, str]:
    remote: dict[str, str] = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            remote[obj["Key"]] = obj["ETag"].strip('"')
    return remote


def put_bytes(client: Any, bucket: str, key: str, body: bytes, content_type: str, sha256: str) -> None:
    md5_b64 = base64.b64encode(hashlib.md5(body, usedforsecurity=False).digest()).decode()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
        ContentMD5=md5_b64,
        Metadata={"sha256": sha256},
    )


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def sync(
    client: Any,
    *,
    site: Path,
    files: list[LocalFile],
    bucket: str,
    manifest: dict[str, Any],
    workers: int,
    delete: bool,
    max_delete_ratio: float,
) -> dict[str, Any]:
    remote = list_remote(client, bucket, SITE_PREFIX)
    wanted = {SITE_PREFIX + f.path: f for f in files}
    to_upload = [f for key, f in wanted.items() if remote.get(key) != f.md5]
    stale = sorted(
        key for key in remote if key not in wanted and not key.startswith(SITE_PREFIX + RELEASES_DIR)
    )
    if delete and remote and len(stale) > max_delete_ratio * len(remote):
        raise SystemExit(
            f"Refusing to delete {len(stale)}/{len(remote)} objects (> {max_delete_ratio:.0%}); "
            "check the site build or raise --max-delete-ratio"
        )

    def upload(f: LocalFile) -> None:
        put_bytes(client, bucket, SITE_PREFIX + f.path, (site / f.path).read_bytes(), f.content_type, f.sha256)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(upload, to_upload))

    after = list_remote(client, bucket, SITE_PREFIX)
    mismatched = sorted(key for key, f in wanted.items() if after.get(key) != f.md5)
    if mismatched:
        raise SystemExit(f"Parity check failed for {len(mismatched)} objects, e.g. {mismatched[:5]}")

    deleted = 0
    if delete:
        for batch in chunked(stale, 1000):
            client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True})
            deleted += len(batch)

    manifest_body = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    manifest_sha = hashlib.sha256(manifest_body).hexdigest()
    release_dir = f"{SITE_PREFIX}{RELEASES_DIR}{manifest['release_id']}/"
    put_bytes(client, bucket, release_dir + "manifest.json", manifest_body, CONTENT_TYPES[".json"], manifest_sha)
    latest = {
        "schema": MANIFEST_SCHEMA,
        "release_id": manifest["release_id"],
        "source_commit": manifest["source_commit"],
        "generated_at": manifest["generated_at"],
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "manifest_path": f"/{RELEASES_DIR}{manifest['release_id']}/manifest.json",
        "manifest_sha256": manifest_sha,
    }
    latest_body = json.dumps(latest, ensure_ascii=False, indent=2).encode()
    put_bytes(
        client,
        bucket,
        f"{SITE_PREFIX}{RELEASES_DIR}latest.json",
        latest_body,
        CONTENT_TYPES[".json"],
        hashlib.sha256(latest_body).hexdigest(),
    )
    return {
        "remote_before": len(remote),
        "uploaded": len(to_upload),
        "uploaded_bytes": sum(f.size for f in to_upload),
        "unchanged": len(wanted) - len(to_upload),
        "stale": len(stale),
        "deleted": deleted,
        "parity_verified": len(wanted),
        "manifest_sha256": manifest_sha,
    }


def git_head(site: Path) -> str:
    result = subprocess.run(["git", "-C", str(site), "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True, type=Path, help="Built site directory (e.g. a gh-pages checkout)")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--release-id", default="", help="Defaults to <UTC timestamp>-<source commit[:12]>")
    parser.add_argument("--source-commit", default="", help="Defaults to git HEAD of --site")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--delete", action="store_true", help="Delete objects no longer in the site build")
    parser.add_argument("--max-delete-ratio", type=float, default=0.2)
    parser.add_argument("--dry-run", action="store_true", help="Hash and report locally; no network")
    parser.add_argument("--skip-privacy-check", action="store_true", help="Only for tests")
    parser.add_argument("--report", type=Path, help="Write a JSON run report here")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, client: Any = None) -> int:
    args = parse_args(argv)
    site = args.site
    if not (site / "index.html").is_file():
        raise SystemExit(f"{site} does not look like a built site (missing index.html)")
    if not args.skip_privacy_check:
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/check_public_privacy_leaks.py"), "--path", str(site)],
            check=True,
        )

    files = scan_site(site)
    now = datetime.now(timezone.utc)
    source_commit = args.source_commit or git_head(site)
    release_id = args.release_id or f"{now.strftime('%Y%m%dT%H%M%SZ')}-{source_commit[:12]}"
    manifest = build_manifest(files, release_id=release_id, source_commit=source_commit, generated_at=now.isoformat())

    report: dict[str, Any] = {
        "release_id": release_id,
        "source_commit": source_commit,
        "bucket": args.bucket,
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "largest_file_bytes": max((f.size for f in files), default=0),
        "dry_run": args.dry_run,
    }
    if not args.dry_run:
        report |= sync(
            client or make_client(),
            site=site,
            files=files,
            bucket=args.bucket,
            manifest=manifest,
            workers=args.workers,
            delete=args.delete,
            max_delete_ratio=args.max_delete_ratio,
        )
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
