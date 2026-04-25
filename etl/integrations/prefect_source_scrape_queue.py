"""Prefect flow wrapper for the source scrape queue."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.ops import source_scrape_queue as queue


def run_prefect_queue(
    *,
    db_path: Path,
    queue_path: str = "",
    snapshot_date: str = "",
    mode: str = "preferred",
    only_repeatable_now: bool = False,
    fallback_on_failure: str = "sample-if-available",
    include_logs: bool = False,
    command_timeout_seconds: int = 90,
    summary_out: str = "",
    retries: int = 1,
    retry_delay_seconds: int = 15,
) -> dict[str, Any]:
    try:
        from prefect import flow, get_run_logger, task
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError("Prefect not installed. Run: pip install -r requirements-ops.txt") from exc

    @task(name="source-scrape-item", retries=max(0, int(retries)), retry_delay_seconds=max(1, int(retry_delay_seconds)))
    def run_item_task(item: dict[str, Any]) -> dict[str, Any]:
        row = queue.execute_item(
            item=item,
            db_path=db_path,
            snapshot_date=snapshot_date,
            mode=mode,
            only_repeatable_now=only_repeatable_now,
            fallback_on_failure=fallback_on_failure,
            include_logs=include_logs,
            command_timeout_seconds=command_timeout_seconds,
            dry_run=False,
        )
        logger = get_run_logger()
        logger.info("source_id=%s status=%s chosen_mode=%s", row.get("source_id"), row.get("status"), row.get("chosen_mode"))
        if str(row.get("status") or "") == "failed":
            raise RuntimeError(json.dumps(row, ensure_ascii=True, default=str))
        return row

    @flow(name="source-scrape-queue")
    def queue_flow() -> dict[str, Any]:
        logger = get_run_logger()
        queue_payload = queue._load_queue(queue_path, db_path, snapshot_date)  # noqa: SLF001
        items = queue_payload.get("items") if isinstance(queue_payload.get("items"), list) else []
        ordered_items = queue._sort_items_by_dependencies([item for item in items if isinstance(item, dict)])  # noqa: SLF001
        futures: dict[str, Any] = {}
        fallback_items: list[dict[str, Any]] = []

        for item in ordered_items:
            source_id = str(item.get("source_id") or "").strip()
            deps = [futures[dep] for dep in queue._prerequisite_source_ids(item) if dep in futures]  # noqa: SLF001
            future = run_item_task.submit(item, wait_for=deps)
            futures[source_id or f"anon:{id(item)}"] = future
            fallback_items.append(item)

        results: list[dict[str, Any]] = []
        for item in fallback_items:
            source_id = str(item.get("source_id") or "").strip()
            future = futures[source_id or f"anon:{id(item)}"]
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover - depends on prefect runtime state objects
                logger.error("source_id=%s failed after retries: %s", source_id, exc)
                results.append(
                    {
                        "source_id": source_id,
                        "rank": int(item.get("rank") or 0),
                        "repeatability_state": str((item.get("execution") or {}).get("repeatability_state") or ""),
                        "status": "failed",
                        "failure_reason": "prefect_task_failed",
                        "prefect_error": str(exc),
                    }
                )

        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "db_path": str(db_path),
            "snapshot_date": snapshot_date,
            "mode": mode,
            "only_repeatable_now": only_repeatable_now,
            "fallback_on_failure": fallback_on_failure,
            "queue_summary": dict(queue_payload.get("summary") or {}),
            "totals": queue._totals_from_results(results),  # noqa: SLF001
            "results": results,
        }
        if str(summary_out or "").strip():
            out_path = Path(summary_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return summary

    return queue_flow()
