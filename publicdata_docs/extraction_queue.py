"""Build deterministic queues for local text extraction work."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

def _norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_csv_set(raw: str) -> set[str]:
    out: set[str] = set()
    for token in str(raw or "").split(","):
        t = _norm(token).lower()
        if t:
            out.add(t)
    return out


def _infer_doc_format(content_type: str, raw_path: str) -> str:
    ct = _norm(content_type).lower()
    suffix = Path(_norm(raw_path)).suffix.lower()
    if "pdf" in ct or suffix == ".pdf":
        return "pdf"
    if "html" in ct or suffix in {".html", ".htm"}:
        return "html"
    if "xml" in ct or suffix == ".xml":
        return "xml"
    return "other"


def _make_queue_key(*, dedupe_by: str, content_sha256: str, raw_path: str, source_record_pk: int) -> str:
    if dedupe_by == "content_sha256" and content_sha256:
        return f"sha256:{content_sha256.lower()}"
    if dedupe_by in {"content_sha256", "raw_path"} and raw_path:
        return f"path:{raw_path}"
    return f"source_record_pk:{int(source_record_pk)}"


def build_queue_rows(
    conn: sqlite3.Connection,
    *,
    source_ids: set[str],
    allowed_formats: set[str],
    only_missing_excerpt: bool,
    dedupe_by: str,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if source_ids:
        marks = ",".join("?" for _ in source_ids)
        where.append(f"LOWER(source_id) IN ({marks})")
        params.extend(sorted(source_ids))
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    rows = conn.execute(
        f"""
        SELECT
          source_id,
          source_record_pk,
          source_url,
          COALESCE(content_type, '') AS content_type,
          COALESCE(content_sha256, '') AS content_sha256,
          COALESCE(bytes, 0) AS bytes,
          COALESCE(raw_path, '') AS raw_path,
          COALESCE(fetched_at, '') AS fetched_at,
          CASE
            WHEN text_excerpt IS NULL OR TRIM(text_excerpt) = '' THEN 1
            ELSE 0
          END AS missing_excerpt
        FROM text_documents
        {where_sql}
        ORDER BY source_id ASC, source_record_pk ASC
        """,
        params,
    ).fetchall()

    scanned = 0
    skipped_format = 0
    skipped_has_excerpt = 0
    queue_map: dict[str, dict[str, Any]] = {}
    all_refs_missing_excerpt = 0
    all_refs_missing_raw_file = 0

    for r in rows:
        scanned += 1
        source_id = _norm(str(r["source_id"] or ""))
        source_url = _norm(str(r["source_url"] or ""))
        raw_path = _norm(str(r["raw_path"] or ""))
        content_type = _norm(str(r["content_type"] or ""))
        content_sha256 = _norm(str(r["content_sha256"] or ""))
        doc_format = _infer_doc_format(content_type, raw_path)
        if allowed_formats and doc_format not in allowed_formats:
            skipped_format += 1
            continue

        missing_excerpt = int(r["missing_excerpt"] or 0) == 1
        if only_missing_excerpt and not missing_excerpt:
            skipped_has_excerpt += 1
            continue

        try:
            source_record_pk = int(r["source_record_pk"])
        except Exception:
            continue

        try:
            byte_size = int(r["bytes"] or 0)
        except Exception:
            byte_size = 0

        has_raw_file = bool(raw_path) and Path(raw_path).is_file()
        if missing_excerpt:
            all_refs_missing_excerpt += 1
            if not has_raw_file:
                all_refs_missing_raw_file += 1

        queue_key = _make_queue_key(
            dedupe_by=dedupe_by,
            content_sha256=content_sha256,
            raw_path=raw_path,
            source_record_pk=source_record_pk,
        )

        bucket = queue_map.get(queue_key)
        if bucket is None:
            bucket = {
                "queue_key": queue_key,
                "doc_format": doc_format,
                "content_sha256": content_sha256,
                "representative_source_id": source_id,
                "representative_source_record_pk": source_record_pk,
                "representative_source_url": source_url,
                "bytes": byte_size,
                "raw_path": raw_path,
                "fetched_at": _norm(str(r["fetched_at"] or "")),
                "has_raw_file": 1 if has_raw_file else 0,
                "refs_total": 0,
                "refs_missing_excerpt": 0,
                "refs_missing_raw_file": 0,
                "_source_ids": set(),
                "_source_record_pks": [],
            }
            queue_map[queue_key] = bucket

        bucket["refs_total"] += 1
        if missing_excerpt:
            bucket["refs_missing_excerpt"] += 1
            if not has_raw_file:
                bucket["refs_missing_raw_file"] += 1

        bucket["_source_ids"].add(source_id)
        bucket["_source_record_pks"].append(source_record_pk)

        # Keep largest payload as representative for extraction planning.
        if byte_size > int(bucket["bytes"]):
            bucket["bytes"] = byte_size
            bucket["raw_path"] = raw_path
            bucket["representative_source_id"] = source_id
            bucket["representative_source_record_pk"] = source_record_pk
            bucket["representative_source_url"] = source_url
            bucket["fetched_at"] = _norm(str(r["fetched_at"] or ""))

        if has_raw_file:
            bucket["has_raw_file"] = 1
            if not bucket["raw_path"]:
                bucket["raw_path"] = raw_path

    queue_rows: list[dict[str, Any]] = []
    for row in queue_map.values():
        refs_missing = int(row["refs_missing_excerpt"])
        has_raw = int(row["has_raw_file"]) == 1
        if refs_missing <= 0:
            queue_status = "already_extracted"
        elif not has_raw:
            queue_status = "missing_raw_file"
        else:
            queue_status = "pending"

        source_ids_csv = ",".join(sorted({str(v) for v in row.pop("_source_ids")}))
        pks = sorted({int(v) for v in row.pop("_source_record_pks")})

        out = dict(row)
        out["queue_status"] = queue_status
        out["source_ids"] = source_ids_csv
        out["source_record_pks_json"] = json.dumps(pks, ensure_ascii=False)
        queue_rows.append(out)

    queue_rows.sort(
        key=lambda r: (
            0 if str(r["queue_status"]) == "pending" else 1,
            -int(r["refs_missing_excerpt"]),
            -int(r["bytes"]),
            str(r["queue_key"]),
        )
    )

    total_before_limit = len(queue_rows)
    if int(limit or 0) > 0:
        queue_rows = queue_rows[: int(limit)]

    summary = {
        "rows_scanned": scanned,
        "queue_items_total": total_before_limit,
        "queue_items_written": len(queue_rows),
        "queue_items_pending": sum(1 for r in queue_rows if str(r["queue_status"]) == "pending"),
        "refs_total_written": sum(int(r["refs_total"]) for r in queue_rows),
        "refs_missing_excerpt_written": sum(int(r["refs_missing_excerpt"]) for r in queue_rows),
        "refs_missing_raw_file_written": sum(int(r["refs_missing_raw_file"]) for r in queue_rows),
        "refs_missing_excerpt_all": all_refs_missing_excerpt,
        "refs_missing_raw_file_all": all_refs_missing_raw_file,
        "skipped_by_format": skipped_format,
        "skipped_has_excerpt": skipped_has_excerpt,
        "dedupe_by": dedupe_by,
        "formats": sorted(allowed_formats),
        "source_ids": sorted(source_ids),
        "only_missing_excerpt": bool(only_missing_excerpt),
        "limit": int(limit or 0),
    }

    return queue_rows, summary
