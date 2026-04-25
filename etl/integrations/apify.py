"""Small Apify REST client for actor runs and dataset fetches."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib import error, parse, request


API_BASE = "https://api.apify.com/v2"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}


class ApifyError(RuntimeError):
    """Raised when Apify rejects a request."""



def _request_json(*, method: str, path: str, token: str, payload: Any = None, query: dict[str, Any] | None = None) -> dict[str, Any]:
    query_string = ""
    if query:
        query_string = "?" + parse.urlencode({key: value for key, value in query.items() if value not in (None, "")})
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{API_BASE}{path}{query_string}",
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:  # pragma: no cover - exercised by live API
        detail = exc.read().decode("utf-8", errors="replace")
        raise ApifyError(f"Apify HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:  # pragma: no cover - exercised by live API
        raise ApifyError(f"Apify connection error: {exc.reason}") from exc



def _request_dataset_items(*, path: str, token: str, limit: int = 0) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"clean": 1}
    if int(limit or 0) > 0:
        query["limit"] = int(limit)
    query_string = "?" + parse.urlencode(query)
    req = request.Request(
        f"{API_BASE}{path}{query_string}",
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with request.urlopen(req, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:  # pragma: no cover - exercised by live API
        detail = exc.read().decode("utf-8", errors="replace")
        raise ApifyError(f"Apify HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:  # pragma: no cover - exercised by live API
        raise ApifyError(f"Apify connection error: {exc.reason}") from exc
    if not isinstance(payload, list):
        raise ApifyError("Expected dataset items response to be a JSON list")
    return [item for item in payload if isinstance(item, dict)]



def start_actor_run(
    *,
    actor_id: str,
    run_input: dict[str, Any] | None = None,
    memory_mbytes: int = 0,
    timeout_seconds: int = 0,
    build: str = "",
    token: str | None = None,
) -> dict[str, Any]:
    resolved_token = str(token or os.environ.get("APIFY_TOKEN") or "").strip()
    if not resolved_token:
        raise ApifyError("Missing Apify token. Set APIFY_TOKEN or pass --token.")
    query = {
        "memory": int(memory_mbytes) if int(memory_mbytes or 0) > 0 else None,
        "timeout": int(timeout_seconds) if int(timeout_seconds or 0) > 0 else None,
        "build": str(build or "").strip() or None,
    }
    response = _request_json(
        method="POST",
        path=f"/acts/{parse.quote(actor_id, safe='~')}/runs",
        token=resolved_token,
        payload=run_input or {},
        query=query,
    )
    data = response.get("data") if isinstance(response.get("data"), dict) else response
    if not isinstance(data, dict):
        raise ApifyError("Unexpected run response from Apify")
    return data



def get_actor_run(*, actor_id: str, run_id: str, token: str | None = None) -> dict[str, Any]:
    resolved_token = str(token or os.environ.get("APIFY_TOKEN") or "").strip()
    if not resolved_token:
        raise ApifyError("Missing Apify token. Set APIFY_TOKEN or pass --token.")
    response = _request_json(
        method="GET",
        path=f"/acts/{parse.quote(actor_id, safe='~')}/runs/{parse.quote(run_id)}",
        token=resolved_token,
    )
    data = response.get("data") if isinstance(response.get("data"), dict) else response
    if not isinstance(data, dict):
        raise ApifyError("Unexpected run status response from Apify")
    return data



def wait_for_actor_run(
    *,
    actor_id: str,
    run_id: str,
    poll_interval_seconds: int = 10,
    token: str | None = None,
) -> dict[str, Any]:
    resolved_token = str(token or os.environ.get("APIFY_TOKEN") or "").strip()
    while True:
        run = get_actor_run(actor_id=actor_id, run_id=run_id, token=resolved_token)
        status = str(run.get("status") or "").upper()
        if status in TERMINAL_STATUSES:
            return run
        time.sleep(max(1, int(poll_interval_seconds or 10)))



def fetch_dataset_items(*, dataset_id: str, limit: int = 0, token: str | None = None) -> list[dict[str, Any]]:
    resolved_token = str(token or os.environ.get("APIFY_TOKEN") or "").strip()
    if not resolved_token:
        raise ApifyError("Missing Apify token. Set APIFY_TOKEN or pass --token.")
    return _request_dataset_items(
        path=f"/datasets/{parse.quote(dataset_id)}/items",
        token=resolved_token,
        limit=limit,
    )



def load_json_input(raw: str) -> dict[str, Any]:
    token = str(raw or "").strip()
    if not token:
        return {}
    candidate = Path(token)
    if candidate.exists():
        parsed = json.loads(candidate.read_text(encoding="utf-8"))
    else:
        parsed = json.loads(token)
    if not isinstance(parsed, dict):
        raise ApifyError("Expected actor input to be a JSON object")
    return parsed
