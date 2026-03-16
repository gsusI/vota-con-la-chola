#!/usr/bin/env python3
"""Apply initiative-measure review outputs from JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json
from scripts.measure_scale_layer import purge_seeded_measure_scale_layer, seed_measure_scale_layer


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
ALLOWED_STATUS = {"resolved", "ignored", "pending"}
ALLOWED_MEASURE_STATUS = {"proposed", "approved", "rejected", "derogated", "pending", "unknown"}
ALLOWED_SUPPORT_SIDE = {"yes", "no", "mixed", "unknown"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply initiative-measure review outputs")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--in-dir", required=True, help="Directory containing JSON result files")
    p.add_argument("--source-id", default="", help="Optional task source_id scope")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON summary output")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _list_json_files(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".json")


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _measure_point_id(task_id: str, rank: int, measure_title: str) -> str:
    token = f"{_norm(task_id)}|{int(rank)}|{_norm(measure_title).lower()}"
    return sha256_bytes(token.encode("utf-8"))[:32]


def _repo_relative_path(value: Any) -> str:
    text = _norm(value)
    if not text:
        return ""
    path = Path(text).expanduser()
    try:
        resolved = path.resolve(strict=False)
    except Exception:
        resolved = path
    try:
        return str(resolved.relative_to(REPO_ROOT.resolve()))
    except Exception:
        return text


def _sanitize_evidence_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    clean_rows: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        clean_item = dict(item)
        for key in ("doc_file", "doc_path", "file", "path"):
            if key in clean_item:
                clean_item[key] = _repo_relative_path(clean_item.get(key))
        clean_rows.append(clean_item)
    return clean_rows


def apply_review_results(
    conn: Any,
    *,
    result_files: list[Path],
    source_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    files_seen = 0
    tasks_updated = 0
    measures_inserted = 0
    skipped_invalid_json = 0
    skipped_missing_task = 0
    skipped_blank_status = 0
    skipped_invalid_status = 0
    skipped_source_mismatch = 0
    skipped_invalid_measure = 0
    scale_layer_cleanup: dict[str, Any] = {
        "measure_point_ids_seen": 0,
        "candidates_deleted": 0,
        "clusters_deleted": 0,
    }
    scale_layer_sync: dict[str, Any] = {
        "schema_ready": False,
        "missing_tables": [],
        "measure_points_seen": 0,
        "candidate_rows_written": 0,
        "cluster_rows_written": 0,
        "link_rows_written": 0,
        "versions_resolved": 0,
        "fragments_matched": 0,
        "missing_versions": 0,
        "missing_fragments": 0,
        "dry_run": bool(dry_run),
    }

    task_updates: list[tuple[Any, ...]] = []
    delete_task_ids: list[str] = []
    measure_rows: list[tuple[Any, ...]] = []

    for path in result_files:
        files_seen += 1
        payload = _load_json(path)
        if payload is None:
            skipped_invalid_json += 1
            continue

        task_id = _norm(payload.get("task_id"))
        review_status = _norm(payload.get("review_status")).lower()
        if not task_id:
            skipped_missing_task += 1
            continue
        if not review_status:
            skipped_blank_status += 1
            continue
        if review_status not in ALLOWED_STATUS:
            skipped_invalid_status += 1
            continue

        current = conn.execute(
            """
            SELECT initiative_id, source_id, raw_payload_json
            FROM parl_initiative_measure_review_tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        if current is None:
            skipped_missing_task += 1
            continue
        if source_id and _norm(current["source_id"]) != _norm(source_id):
            skipped_source_mismatch += 1
            continue

        measures = payload.get("measures")
        if not isinstance(measures, list):
            measures = []
        if review_status == "resolved" and not measures:
            skipped_invalid_measure += 1
            continue

        initiative_id = _norm(current["initiative_id"])
        clean_measure_rows: list[tuple[Any, ...]] = []
        rank = 0
        invalid_task = False

        for item in measures:
            if not isinstance(item, dict):
                invalid_task = True
                break
            measure_title = _norm(item.get("measure_title"))
            citizen_summary = _norm(item.get("citizen_summary"))
            if not measure_title or not citizen_summary:
                invalid_task = True
                break
            measure_status = _norm(item.get("measure_status")).lower() or "unknown"
            if measure_status not in ALLOWED_MEASURE_STATUS:
                invalid_task = True
                break
            support_side = _norm(item.get("support_side")).lower() or "unknown"
            if support_side not in ALLOWED_SUPPORT_SIDE:
                invalid_task = True
                break

            vote_ids = item.get("primary_vote_event_ids")
            if not isinstance(vote_ids, list):
                vote_ids = []
            vote_ids_clean = [_norm(v) for v in vote_ids if _norm(v)]

            search_terms = item.get("search_terms")
            if not isinstance(search_terms, list):
                search_terms = []
            search_terms_clean = [_norm(v) for v in search_terms if _norm(v)]

            evidence = _sanitize_evidence_rows(item.get("evidence"))

            rank += 1
            clean_measure_rows.append(
                (
                    _measure_point_id(task_id, rank, measure_title),
                    task_id,
                    initiative_id,
                    _norm(current["source_id"]),
                    rank,
                    measure_title,
                    citizen_summary,
                    _norm(item.get("affected_groups")) or None,
                    _norm(item.get("policy_area")) or None,
                    _norm(item.get("measure_kind")) or None,
                    measure_status,
                    stable_json(search_terms_clean),
                    stable_json(vote_ids_clean),
                    support_side,
                    _norm(item.get("support_explanation")) or None,
                    stable_json(evidence),
                    _norm(item.get("note")) or None,
                    now_iso,
                    now_iso,
                )
            )
        if invalid_task:
            skipped_invalid_measure += 1
            continue

        existing_payload_raw = _norm(current["raw_payload_json"]) or "{}"
        try:
            existing_payload = json.loads(existing_payload_raw)
        except Exception:
            existing_payload = {}
        if not isinstance(existing_payload, dict):
            existing_payload = {}
        history = existing_payload.get("review_history")
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "review_status": review_status,
                "reviewed_at": now_iso,
                "reviewer": _norm(payload.get("reviewer")),
                "review_note": _norm(payload.get("review_note")),
                "result_file": _repo_relative_path(path),
                "measures_count": len(clean_measure_rows),
            }
        )
        existing_payload["review_status"] = review_status
        existing_payload["reviewed_at"] = now_iso
        if _norm(payload.get("reviewer")):
            existing_payload["reviewer"] = _norm(payload.get("reviewer"))
        if _norm(payload.get("review_note")):
            existing_payload["review_note"] = _norm(payload.get("review_note"))
        existing_payload["review_history"] = history[-50:]

        task_updates.append(
            (
                review_status,
                _norm(payload.get("review_note")) or None,
                stable_json(existing_payload),
                now_iso,
                task_id,
            )
        )
        delete_task_ids.append(task_id)
        measure_rows.extend(clean_measure_rows)

    if not dry_run and task_updates:
        existing_measure_point_ids: list[str] = []
        if delete_task_ids:
            marks = ",".join("?" for _ in delete_task_ids)
            existing_rows = conn.execute(
                f"""
                SELECT measure_point_id
                FROM parl_initiative_measure_points
                WHERE task_id IN ({marks})
                """,
                delete_task_ids,
            ).fetchall()
            existing_measure_point_ids = [
                _norm(row["measure_point_id"]) for row in existing_rows if _norm(row["measure_point_id"])
            ]
        with conn:
            scale_layer_cleanup = purge_seeded_measure_scale_layer(
                conn,
                measure_point_ids=existing_measure_point_ids,
                dry_run=False,
            )
            conn.executemany(
                """
                UPDATE parl_initiative_measure_review_tasks
                SET status = ?, note = ?, raw_payload_json = ?, updated_at = ?
                WHERE task_id = ?
                """,
                task_updates,
            )
            for task_id in delete_task_ids:
                conn.execute(
                    "DELETE FROM parl_initiative_measure_points WHERE task_id = ?",
                    (task_id,),
                )
            if measure_rows:
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_measure_points (
                      measure_point_id, task_id, initiative_id, source_id, measure_rank,
                      measure_title, citizen_summary, affected_groups, policy_area, measure_kind,
                      measure_status, search_terms_json, primary_vote_event_ids_json, support_side,
                      support_explanation, evidence_json, note, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    measure_rows,
                )
                scale_layer_sync = seed_measure_scale_layer(
                    conn,
                    measure_point_ids=[row[0] for row in measure_rows],
                    dry_run=False,
                )

    tasks_updated = len(task_updates)
    measures_inserted = len(measure_rows)
    return {
        "source_id": _norm(source_id),
        "dry_run": bool(dry_run),
        "files_seen": int(files_seen),
        "tasks_updated": int(tasks_updated),
        "measures_inserted": int(measures_inserted),
        "skipped_invalid_json": int(skipped_invalid_json),
        "skipped_missing_task": int(skipped_missing_task),
        "skipped_blank_status": int(skipped_blank_status),
        "skipped_invalid_status": int(skipped_invalid_status),
        "skipped_source_mismatch": int(skipped_source_mismatch),
        "skipped_invalid_measure": int(skipped_invalid_measure),
        "scale_layer_cleanup": scale_layer_cleanup,
        "scale_layer_sync": scale_layer_sync,
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    in_dir = Path(args.in_dir)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2
    if not in_dir.exists() or not in_dir.is_dir():
        print(f"ERROR: input directory not found: {in_dir}", file=sys.stderr)
        return 2

    files = _list_json_files(in_dir)
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        result = apply_review_results(
            conn,
            result_files=files,
            source_id=str(args.source_id or ""),
            dry_run=bool(args.dry_run),
        )

    out_path = _norm(args.out)
    if out_path:
        Path(out_path).write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
