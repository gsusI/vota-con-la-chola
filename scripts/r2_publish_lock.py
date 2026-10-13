#!/usr/bin/env python3
"""Cross-machine lock for publishing votaconlachola.org (CI and local sessions share R2).

The checkout lock (scripts/with_site_lock.sh) only serialises sessions on one machine;
a CI publish and a local publish could still interleave their R2 syncs and Worker
deploys. This lock is one object created with a conditional PUT (If-None-Match: *),
so exactly one publisher holds it; it expires so a crashed publisher cannot wedge
the site. Costs two R2 writes per publish.

Usage: r2_publish_lock.py acquire --owner ID [--wait-seconds N] | release --owner ID
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import publish_site_origin as origin  # noqa: E402

LOCK_KEY = "locks/site-publish.json"
TTL = timedelta(hours=2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status(exc: Exception) -> int:
    return int(getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode") or 0)


def read_lock(client: Any, bucket: str) -> dict[str, Any] | None:
    try:
        return json.loads(client.get_object(Bucket=bucket, Key=LOCK_KEY)["Body"].read())
    except Exception as exc:  # noqa: BLE001
        if _status(exc) == 404 or "NoSuchKey" in str(exc):
            return None
        raise


def try_acquire(client: Any, bucket: str, owner: str, now: datetime) -> dict[str, Any] | None:
    """Return None when acquired, else the current holder."""
    body = json.dumps({"owner": owner, "acquired_at": now.isoformat(), "expires_at": (now + TTL).isoformat()})
    try:
        client.put_object(Bucket=bucket, Key=LOCK_KEY, Body=body.encode(), IfNoneMatch="*",
                          ContentType="application/json")
        return None
    except Exception as exc:  # noqa: BLE001
        if _status(exc) not in (409, 412):
            raise
    holder = read_lock(client, bucket) or {}
    if holder and datetime.fromisoformat(holder["expires_at"]) < now:
        print(f"r2 publish lock: removing expired lock of {holder.get('owner')}", file=sys.stderr)
        client.delete_object(Bucket=bucket, Key=LOCK_KEY)
        return try_acquire(client, bucket, owner, now)
    return holder or {"owner": "unknown"}


def acquire(client: Any, bucket: str, owner: str, wait_seconds: float, poll: float = 20) -> None:
    deadline = time.monotonic() + wait_seconds
    while True:
        holder = try_acquire(client, bucket, owner, _now())
        if holder is None:
            print(f"r2 publish lock: acquired by {owner}", file=sys.stderr)
            return
        if holder.get("owner") == owner:
            return
        if time.monotonic() >= deadline:
            raise SystemExit(f"r2 publish lock held by {holder.get('owner')} until {holder.get('expires_at')}")
        print(f"r2 publish lock: waiting for {holder.get('owner')}", file=sys.stderr)
        time.sleep(poll)


def release(client: Any, bucket: str, owner: str) -> None:
    holder = read_lock(client, bucket)
    if holder and holder.get("owner") == owner:
        client.delete_object(Bucket=bucket, Key=LOCK_KEY)
        print(f"r2 publish lock: released by {owner}", file=sys.stderr)


def main(argv: list[str] | None = None, *, client: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("acquire", "release"))
    parser.add_argument("--owner", required=True)
    parser.add_argument("--bucket", default=origin.DEFAULT_BUCKET)
    parser.add_argument("--wait-seconds", type=float, default=1800)
    args = parser.parse_args(argv)
    client = client or origin.make_client()
    if args.action == "acquire":
        acquire(client, args.bucket, args.owner, args.wait_seconds)
    else:
        release(client, args.bucket, args.owner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
