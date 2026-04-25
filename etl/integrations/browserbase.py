"""Small Browserbase REST client used for managed anti-bot browser sessions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request


API_BASE = "https://api.browserbase.com/v1"
DEFAULT_REGION = "us-west-2"


class BrowserbaseError(RuntimeError):
    """Raised when Browserbase rejects a request."""



def _request_json(*, method: str, path: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{API_BASE}{path}",
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-BB-API-Key": api_key,
        },
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:  # pragma: no cover - exercised by live API
        detail = exc.read().decode("utf-8", errors="replace")
        raise BrowserbaseError(f"Browserbase HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:  # pragma: no cover - exercised by live API
        raise BrowserbaseError(f"Browserbase connection error: {exc.reason}") from exc



def create_session(
    *,
    project_id: str = "",
    region: str = DEFAULT_REGION,
    timeout_seconds: int = 900,
    keep_alive: bool = False,
    use_default_proxy: bool = False,
    proxies: list[dict[str, Any]] | None = None,
    context_id: str = "",
    user_metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    resolved_api_key = str(api_key or os.environ.get("BROWSERBASE_API_KEY") or "").strip()
    if not resolved_api_key:
        raise BrowserbaseError("Missing Browserbase API key. Set BROWSERBASE_API_KEY or pass --api-key.")

    payload: dict[str, Any] = {}
    if str(project_id or "").strip():
        payload["projectId"] = str(project_id).strip()
    if str(context_id or "").strip():
        payload["contextId"] = str(context_id).strip()
    if user_metadata:
        payload["userMetadata"] = user_metadata

    browser_settings: dict[str, Any] = {
        "region": str(region or DEFAULT_REGION),
        "timeout": max(60, min(int(timeout_seconds or 900), 21600)),
        "keepAlive": bool(keep_alive),
    }
    if proxies:
        browser_settings["proxies"] = proxies
    elif use_default_proxy:
        browser_settings["proxies"] = True
    payload["browserSettings"] = browser_settings
    return _request_json(method="POST", path="/sessions", api_key=resolved_api_key, payload=payload)



def load_json_arg(raw: str) -> dict[str, Any]:
    token = str(raw or "").strip()
    if not token:
        return {}
    candidate = Path(token)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    parsed = json.loads(token)
    if not isinstance(parsed, dict):
        raise BrowserbaseError("Expected JSON object for metadata/proxy payload")
    return parsed
