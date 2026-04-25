#!/usr/bin/env python3
"""Create a managed Browserbase session for anti-bot/manual capture work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.integrations.browserbase import BrowserbaseError, create_session  # noqa: E402


def _load_json_value(raw: str):
    token = str(raw or "").strip()
    if not token:
        return None
    candidate = Path(token)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(token)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Browserbase session")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--keep-alive", action="store_true")
    parser.add_argument("--use-default-proxy", action="store_true")
    parser.add_argument("--proxies-json", default="", help="JSON array or file path for proxy config")
    parser.add_argument("--context-id", default="")
    parser.add_argument("--metadata-json", default="", help="JSON object or file path")
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        proxies_value = _load_json_value(args.proxies_json)
        if proxies_value is not None and not isinstance(proxies_value, list):
            raise BrowserbaseError("--proxies-json must resolve to a JSON list")
        metadata_value = _load_json_value(args.metadata_json)
        if metadata_value is not None and not isinstance(metadata_value, dict):
            raise BrowserbaseError("--metadata-json must resolve to a JSON object")
        session = create_session(
            api_key=str(args.api_key or "").strip() or None,
            project_id=str(args.project_id or "").strip(),
            region=str(args.region or "us-west-2"),
            timeout_seconds=int(args.timeout_seconds or 900),
            keep_alive=bool(args.keep_alive),
            use_default_proxy=bool(args.use_default_proxy),
            proxies=proxies_value,
            context_id=str(args.context_id or "").strip(),
            user_metadata=metadata_value,
        )
    except BrowserbaseError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2

    if str(args.out or "").strip():
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(session, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
