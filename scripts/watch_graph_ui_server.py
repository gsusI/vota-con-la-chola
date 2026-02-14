#!/usr/bin/env python3
"""Watch Graph UI server files and restart automatically on changes."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


def _resolve_watch_files() -> list[Path]:
    base = Path(__file__).resolve().parent
    repo_root = base.parent
    return [
        repo_root / "scripts" / "graph_ui_server.py",
        repo_root / "ui" / "graph" / "explorers.html",
        repo_root / "ui" / "graph" / "explorer.html",
        repo_root / "ui" / "graph" / "explorer-sports.html",
        repo_root / "ui" / "graph" / "explorer-sources.html",
        repo_root / "docs" / "etl" / "e2e-scrape-load-tracker.md",
    ]


def _snapshot(files: Iterable[Path]) -> dict[Path, float]:
    data: dict[Path, float] = {}
    for path in files:
        try:
            data[path] = path.stat().st_mtime
        except FileNotFoundError:
            data[path] = 0.0
    return data


def _changed(previous: dict[Path, float], current: dict[Path, float]) -> bool:
    if previous.keys() != current.keys():
        return True
    for key in current:
        if current[key] != previous[key]:
            return True
    return False


def _start_server(db_path: str, host: str, port: str, extra_watch_env: dict[str, str]) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.update(extra_watch_env)
    env["DB_PATH"] = db_path
    return subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "graph_ui_server.py"),
            "--db",
            db_path,
            "--host",
            host,
            "--port",
            port,
        ],
        env=env,
    )


def _stop_server(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)


def main() -> int:
    db_path = os.environ.get("DB_PATH", "etl/data/staging/politicos-es.db")
    host = os.environ.get("EXPLORER_HOST", "127.0.0.1")
    port = os.environ.get("EXPLORER_PORT", "9010")
    interval = float(os.environ.get("EXPLORER_WATCH_INTERVAL", "1.0"))
    files = _resolve_watch_files()

    print(f"Graph UI watch activo en : {host}:{port}")
    print("Observando:")
    for path in files:
        print(f" - {path}")
    print("Pulsa Ctrl+C para parar.")

    previous = _snapshot(files)
    process = _start_server(db_path, host, port, {})

    try:
        while True:
            time.sleep(interval)
            current = _snapshot(files)
            if process.poll() is not None:
                process = None

            if _changed(previous, current) or process is None:
                if process is not None:
                    print("Cambio detectado. Reiniciando servidor...")
                    _stop_server(process)
                else:
                    print("Servidor finalizado. Reiniciando...")

                process = _start_server(db_path, host, port, {})
                previous = current
    except KeyboardInterrupt:
        print("Parando servidor watch...")
        _stop_server(process)
        return 0
    except Exception as exc:
        print(f"Error en watcher: {exc}")
        _stop_server(process)
        return 1

    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    sys.exit(main())
