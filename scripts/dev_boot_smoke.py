#!/usr/bin/env python3
"""Boot smoke test for local Explorer startup.

This starts the Graph UI server with a fixture DB, then checks `/api/health`.
If successful it can optionally keep the server running for local development.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
from pathlib import Path
from urllib.request import urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="SQLite DB path used by the explorer (for example etl/data/staging/politicos-es.dev.db)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the explorer")
    parser.add_argument("--port", type=int, default=9010, help="Port to bind the explorer")
    parser.add_argument("--timeout", type=float, default=25.0, help="Health check timeout in seconds")
    parser.add_argument(
        "--interval",
        type=float,
        default=0.25,
        help="Retry interval for health checks",
    )
    parser.add_argument(
        "--health-path",
        default="/api/health",
        help="Health endpoint path",
    )
    parser.add_argument(
        "--keep-running",
        action="store_true",
        help="Keep explorer running after a successful smoke check",
    )
    return parser.parse_args()


def wait_for_health(url: str, timeout_seconds: float, interval_seconds: float) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: BaseException | None = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if payload.get("status") == "ok":
                    return payload
                last_error = RuntimeError(f"health payload not ok: {payload!r}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last_error = exc
        time.sleep(interval_seconds)

    raise RuntimeError(f"Explorer health check failed at {url}. Last error: {last_error}")


def main() -> int:
    args = parse_args()

    if not args.db.exists():
        raise SystemExit(f"[dev_boot_smoke] DB does not exist: {args.db}")

    url = f"http://{args.host}:{args.port}{args.health_path}"
    server_cmd = [
        sys.executable,
        str(Path(__file__).with_name("graph_ui_server.py")),
        "--db",
        str(args.db),
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    proc = subprocess.Popen(server_cmd)
    try:
        payload = wait_for_health(
            url=url,
            timeout_seconds=args.timeout,
            interval_seconds=args.interval,
        )
        print(
            f"[dev_boot_smoke] OK status={payload.get('status')} "
            f"db_exists={payload.get('db_exists')} db_path={payload.get('db_path')}"
        )

        if not args.keep_running:
            return 0

        print(f"[dev_boot_smoke] Explorer running at http://{args.host}:{args.port}/explorer")
        print("[dev_boot_smoke] Press Ctrl+C to stop")
        proc.wait()
        return 0
    except KeyboardInterrupt:
        print("[dev_boot_smoke] Interrupted, stopping explorer")
        return 130
    finally:
        if proc.poll() is None and not args.keep_running:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
