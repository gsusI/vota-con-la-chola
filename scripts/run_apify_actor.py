#!/usr/bin/env python3
"""Run an Apify actor and optionally wait for completion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.integrations.apify import (  # noqa: E402
    ApifyError,
    fetch_dataset_items,
    load_json_input,
    start_actor_run,
    wait_for_actor_run,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Apify actor")
    parser.add_argument("--token", default="")
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--input-json", default="", help="JSON object or file path")
    parser.add_argument("--memory-mbytes", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--build", default="")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-interval-seconds", type=int, default=10)
    parser.add_argument("--fetch-dataset-items", action="store_true")
    parser.add_argument("--dataset-limit", type=int, default=0)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_input = load_json_input(args.input_json)
        run = start_actor_run(
            actor_id=str(args.actor_id),
            run_input=run_input,
            memory_mbytes=int(args.memory_mbytes or 0),
            timeout_seconds=int(args.timeout_seconds or 0),
            build=str(args.build or ""),
            token=str(args.token or "").strip() or None,
        )
        if bool(args.wait):
            run = wait_for_actor_run(
                actor_id=str(args.actor_id),
                run_id=str(run.get("id") or ""),
                poll_interval_seconds=int(args.poll_interval_seconds or 10),
                token=str(args.token or "").strip() or None,
            )
        output = {"run": run}
        if bool(args.fetch_dataset_items):
            dataset_id = str(run.get("defaultDatasetId") or "")
            if not dataset_id:
                raise ApifyError("Run has no defaultDatasetId to fetch")
            output["dataset_items"] = fetch_dataset_items(
                dataset_id=dataset_id,
                limit=int(args.dataset_limit or 0),
                token=str(args.token or "").strip() or None,
            )
    except ApifyError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2

    if str(args.out or "").strip():
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
