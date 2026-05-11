from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any


REPEATABLE_NOW_STATES = {"network_verified", "sample_replay_only", "blocked_with_sample"}
MANUAL_STATES = {"manual_capture_required", "blocked_upstream"}


def render_command(command: str, *, db_path: Path, snapshot_date: str) -> str:
    rendered = str(command or "").replace("<db>", str(db_path))
    if snapshot_date:
        rendered = rendered.replace("<snapshot-date>", snapshot_date)
    return rendered


def normalize_command(command: str, *, db_path: Path, snapshot_date: str) -> list[str]:
    rendered = render_command(command, db_path=db_path, snapshot_date=snapshot_date)
    tokens = shlex.split(rendered)
    if not tokens:
        return []
    tokens = _set_cli_arg(tokens, "--db", str(db_path))
    if snapshot_date and "ingest" in tokens:
        tokens = _set_cli_arg(tokens, "--snapshot-date", snapshot_date)
    return tokens


def prerequisite_source_ids(item: dict[str, Any]) -> list[str]:
    execution = item.get("execution") if isinstance(item.get("execution"), dict) else {}
    raw = execution.get("prerequisite_source_ids")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in raw:
        token = str(value or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def pre_commands(item: dict[str, Any]) -> list[str]:
    execution = item.get("execution") if isinstance(item.get("execution"), dict) else {}
    raw = execution.get("pre_commands")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for value in raw:
        token = str(value or "").strip()
        if token:
            out.append(token)
    return out


def sort_items_by_dependencies(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    for item in items:
        source_id = str(item.get("source_id") or "").strip()
        if source_id and source_id not in by_source:
            by_source[source_id] = item

    ordered: list[dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item: dict[str, Any]) -> None:
        source_id = str(item.get("source_id") or "").strip()
        visit_key = source_id or f"anon:{id(item)}"
        if visit_key in visited or visit_key in visiting:
            return
        visiting.add(visit_key)
        for dep_source_id in prerequisite_source_ids(item):
            dep_item = by_source.get(dep_source_id)
            if dep_item is not None:
                visit(dep_item)
        visiting.remove(visit_key)
        visited.add(visit_key)
        ordered.append(item)

    for item in items:
        if isinstance(item, dict):
            visit(item)
    return ordered


def _set_cli_arg(tokens: list[str], flag: str, value: str) -> list[str]:
    if not value:
        return tokens
    out = list(tokens)
    if flag in out:
        idx = out.index(flag)
        if idx + 1 < len(out):
            out[idx + 1] = value
        else:
            out.append(value)
        return out
    out.extend([flag, value])
    return out
