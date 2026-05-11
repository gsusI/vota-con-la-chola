from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Callable
from urllib.parse import unquote, urlparse

from publicdata_core.util import normalize_ws


CommandRunner = Callable[[list[str]], int | None]


def command_exit_code(argv: list[str], *, timeout_seconds: int = 10) -> int | None:
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        return int(proc.returncode)
    except Exception:  # noqa: BLE001
        return None


def sanitize_runtime_path_for_public(path_value: str) -> str | None:
    token = normalize_ws(str(path_value or ""))
    if not token:
        return None
    lowered = token.lower()
    if token.startswith("/") or re.match(r"^[A-Za-z]:[\\\\/]", token):
        name = Path(token).name or "node"
        return f"<abs>/{name}"
    if lowered.startswith("file://"):
        try:
            parsed = urlparse(token)
            name = Path(unquote(parsed.path)).name or "node"
        except Exception:  # noqa: BLE001
            name = "node"
        return f"<uri>/{name}"
    return token


def ensure_playwright_nodejs_runtime(
    playwright_pkg_dir: Path,
    *,
    command_runner: CommandRunner | None = None,
    which_node: Callable[[str], str | None] | None = None,
) -> dict[str, object]:
    """Prefer system Node when bundled Playwright driver is unhealthy."""

    run_command = command_runner or command_exit_code
    find_executable = which_node or shutil.which

    env_node_raw = normalize_ws(str(os.environ.get("PLAYWRIGHT_NODEJS_PATH") or ""))
    env_node_public = sanitize_runtime_path_for_public(env_node_raw)
    meta: dict[str, object] = {
        "fallback_applied": False,
        "effective_nodejs_path": env_node_public,
        "driver_node_path": "playwright/driver/node",
        "driver_node_rc": None,
        "system_node_path": None,
        "system_cli_rc": None,
    }
    if env_node_raw:
        return meta

    driver_node = playwright_pkg_dir / "driver" / "node"
    driver_cli = playwright_pkg_dir / "driver" / "package" / "cli.js"
    system_node_raw = normalize_ws(str(find_executable("node") or ""))
    system_node_public = sanitize_runtime_path_for_public(system_node_raw)

    meta["system_node_path"] = system_node_public
    driver_rc = run_command([str(driver_node), "--version"]) if driver_node.exists() else None
    cli_rc = run_command([system_node_raw, str(driver_cli), "--version"]) if system_node_raw and driver_cli.exists() else None
    meta["driver_node_rc"] = driver_rc
    meta["system_cli_rc"] = cli_rc

    bundled_unhealthy = (not driver_node.exists()) or (driver_rc is None) or (int(driver_rc) != 0)
    if bundled_unhealthy and system_node_raw and cli_rc == 0:
        os.environ["PLAYWRIGHT_NODEJS_PATH"] = system_node_raw
        meta["fallback_applied"] = True
        meta["effective_nodejs_path"] = system_node_public
    return meta
