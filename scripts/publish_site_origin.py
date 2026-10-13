#!/usr/bin/env python3
"""Sync a built public site into the R2 origin bucket and publish a hash manifest.

Only changed files are uploaded (R2 single-part ETag == MD5). Every upload is
verified by re-listing before stale objects are deleted. Each run writes a
public release manifest (path, size, sha256) under ``site/releases/`` so anyone
can check that what the site serves matches the published release.

Credentials come from the environment, falling back to the repo ``.env``
(S3-compatible API, so the same script works against any S3 origin):
R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_ACCOUNT_ID (or R2_ENDPOINT_URL).
The account id falls back to CLOUDFLARE_ACCOUNT_ID, then to ``account_id`` in
the domain Worker's wrangler.toml.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUCKET = "vclc-site"
ENV_FILE = REPO_ROOT / ".env"
WRANGLER_TOML = REPO_ROOT / "infra/cloudflare/votaconlachola-worker/wrangler.toml"
ENV_KEYS = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ACCOUNT_ID", "R2_ENDPOINT_URL", "CLOUDFLARE_ACCOUNT_ID")
SITE_PREFIX = "site/"
RELEASES_DIR = "releases/"
# Subtrees written by other publishers (release manifests, dataset mirror, joined archives); never synced or deleted here.
RESERVED_DIRS = (RELEASES_DIR, "datasets/", "downloads/")
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


def scan_site(site: Path, *, workers: int = 8, hashes: bool = True) -> list[LocalFile]:
    paths = sorted(
        p for p in site.rglob("*") if p.is_file() and not p.is_symlink() and is_published(p.relative_to(site))
    )

    def digest(path: Path) -> LocalFile:
        if not hashes:  # prune only needs paths and sizes
            rel = path.relative_to(site).as_posix()
            return LocalFile(rel, path.stat().st_size, "", "", content_type_for(rel))
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
    clashes = sorted({d for f in files for d in RESERVED_DIRS if f.path.startswith(d)})
    if clashes:
        raise SystemExit(f"Site build must not contain {clashes}: reserved for release manifests and dataset mirrors")
    return files


def build_manifest(
    files: list[LocalFile], *, release_id: str, source_commit: str, generated_at: str, source_dirty: bool = False
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "release_id": release_id,
        "source_commit": source_commit,
        "source_dirty": source_dirty,
        "generated_at": generated_at,
        "file_count": len(files),
        "total_bytes": sum(f.size for f in files),
        "files": [{"path": f.path, "size": f.size, "sha256": f.sha256} for f in files],
    }


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def wrangler_account_id(path: Path) -> str:
    if not path.is_file():
        return ""
    match = re.search(r'^account_id\s*=\s*"([0-9a-f]+)"', path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else ""


def resolve_r2_settings(
    environ: dict[str, str] | None = None, *, env_file: Path = ENV_FILE, wrangler_toml: Path = WRANGLER_TOML
) -> dict[str, str]:
    """Environment wins over .env; the account id finally falls back to the Worker's wrangler.toml."""
    environ = os.environ if environ is None else environ
    dotenv = read_dotenv(env_file)
    settings = {key: (environ.get(key) or dotenv.get(key) or "").strip() for key in ENV_KEYS}
    if not settings["R2_ENDPOINT_URL"]:
        account = settings["R2_ACCOUNT_ID"] or settings["CLOUDFLARE_ACCOUNT_ID"] or wrangler_account_id(wrangler_toml)
        if not account:
            raise SystemExit(f"Set R2_ENDPOINT_URL or R2_ACCOUNT_ID (env or {env_file.name})")
        settings["R2_ENDPOINT_URL"] = f"https://{account}.r2.cloudflarestorage.com"
    for name in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not settings[name]:
            raise SystemExit(f"Missing {name} (set it in the environment or {env_file.name})")
    return settings


def make_client() -> Any:
    import boto3  # type: ignore[import-not-found]

    from botocore.config import Config  # type: ignore[import-not-found]

    settings = resolve_r2_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings["R2_ENDPOINT_URL"],
        aws_access_key_id=settings["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=settings["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        # One pooled connection per upload thread (botocore defaults to 10).
        config=Config(max_pool_connections=64, retries={"max_attempts": 5, "mode": "adaptive"}),
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
    r2_scope: Any = None,
    prune_only: bool = False,
) -> dict[str, Any]:
    remote = list_remote(client, bucket, SITE_PREFIX)
    # The manifest covers the whole build; R2 only stores what it serves (see --r2-only).
    wanted = {SITE_PREFIX + f.path: f for f in files if r2_scope is None or r2_scope(f)}
    if prune_only:
        stale = sorted(
            key for key in remote if key not in wanted and not any(key.startswith(SITE_PREFIX + d) for d in RESERVED_DIRS)
        )
        # Leftovers outside the R2-served prefixes are shadowed by static assets: always safe to drop.
        # Inside them, a big deletion means a broken build: keep the ratio guard there.
        from prepare_site_static_assets import R2_ONLY_PREFIXES

        served = [k for k in remote if k[len(SITE_PREFIX):].startswith(R2_ONLY_PREFIXES)]
        stale_served = [k for k in stale if k[len(SITE_PREFIX):].startswith(R2_ONLY_PREFIXES)]
        if served and len(stale_served) > max_delete_ratio * len(served):
            raise SystemExit(f"Refusing to delete {len(stale_served)}/{len(served)} R2-served objects (> {max_delete_ratio:.0%})")
        for batch in chunked(stale, 1000):
            client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True})
        return {"remote_before": len(remote), "deleted": len(stale)}
    to_upload = [f for key, f in wanted.items() if remote.get(key) != f.md5]
    stale = sorted(
        key for key in remote if key not in wanted and not any(key.startswith(SITE_PREFIX + d) for d in RESERVED_DIRS)
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
        missing = sum(1 for key in mismatched if key not in after)
        raise SystemExit(
            f"Parity check failed for {len(mismatched)} objects ({missing} missing, "
            f"{len(mismatched) - missing} with different content), e.g. {mismatched[:5]}. "
            "If another publish ran concurrently, the bucket changed during this sync: nothing was deleted; "
            "re-run `just site-origin-publish` once it finishes (it uploads only diffs)."
        )

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


# Sources that end up in the static build: uncommitted changes there make the release not reproducible from its commit.
SITE_SOURCE_PATHS = ("ui/site",)


def git_head(site: Path) -> str:
    """Commit the build came from: the site's own repo if it is one, else this repo's HEAD (``ui/site/out``)."""
    for repo in (site, REPO_ROOT):
        result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel", "HEAD"], capture_output=True, text=True)
        if result.returncode == 0:
            top, head = result.stdout.split()
            if Path(top).resolve() == Path(repo).resolve() or repo == REPO_ROOT:
                return head
    return "unknown"


BUILD_STAMP = ".vclc-build.json"


def read_build_stamp(site: Path) -> dict[str, Any]:
    """``just site-publish`` writes the commit the build came from into the (unpublished) dotfile ``.vclc-build.json``."""
    try:
        return json.loads((site / BUILD_STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def git_dirty(paths: Iterable[str] = SITE_SOURCE_PATHS) -> bool:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--untracked-files=no", "--", *paths],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True, type=Path, help="Built site directory (ui/site/out)")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--release-id", default="", help="Defaults to <UTC timestamp>-<source commit[:12]>")
    parser.add_argument("--source-commit", default="", help="Defaults to git HEAD of --site, else of this repo")
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument(
        "--r2-only",
        action="store_true",
        help="Store only what R2 serves (prepare_site_static_assets.served_from_r2); the rest ships as Worker static assets",
    )
    parser.add_argument("--delete", action="store_true", help="Delete objects no longer in the site build")
    parser.add_argument("--max-delete-ratio", type=float, default=0.2)
    parser.add_argument(
        "--prune-only",
        action="store_true",
        help="Only delete objects R2 no longer needs (run after the Worker deploy); no upload, no manifest",
    )
    parser.add_argument("--dry-run", action="store_true", help="Hash and report locally; no network")
    parser.add_argument("--skip-privacy-check", action="store_true", help="Only for tests")
    parser.add_argument("--report", type=Path, help="Write a JSON run report here")
    return parser.parse_args(argv)


def r2_scope() -> Any:
    from prepare_site_static_assets import served_from_r2

    return lambda f: served_from_r2(f.path, f.size)


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

    files = scan_site(site, hashes=not args.prune_only)
    now = datetime.now(timezone.utc)
    stamp = read_build_stamp(site)
    source_commit = args.source_commit or stamp.get("source_commit") or git_head(site)
    source_dirty = False if args.source_commit else bool(stamp["source_dirty"]) if "source_dirty" in stamp else git_dirty()
    if not args.source_commit and not stamp:
        print(f"WARN: {site}/{BUILD_STAMP} missing (build not made by `just site-publish`); using current HEAD", file=sys.stderr)
    release_id = args.release_id or f"{now.strftime('%Y%m%dT%H%M%SZ')}-{source_commit[:12]}"
    manifest = build_manifest(
        files, release_id=release_id, source_commit=source_commit, generated_at=now.isoformat(), source_dirty=source_dirty
    )

    report: dict[str, Any] = {
        "release_id": release_id,
        "source_commit": source_commit,
        "source_dirty": source_dirty,
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
            r2_scope=r2_scope() if args.r2_only else None,
            prune_only=args.prune_only,
        )
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
