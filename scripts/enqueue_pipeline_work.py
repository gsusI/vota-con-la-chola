#!/usr/bin/env python3
"""Stream database references into the durable high-volume work queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.util import now_utc_iso  # noqa: E402
from publicdata_ops import (  # noqa: E402
    enqueue_work_items,
    ensure_work_queue_schema,
    work_queue_stats,
)
from publicdata_sqlite import open_db, table_exists  # noqa: E402

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_PIPELINES = {
    "document-fetch": "document_fetch",
    "placsp-document-fetch": "placsp_document_fetch",
    "source-record-transform": "source_record_transform",
    "text-extract": "text_extraction",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream source/document references into pipeline_work_items"
    )
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--kind", choices=tuple(DEFAULT_PIPELINES), required=True)
    parser.add_argument("--pipeline-id", default="")
    parser.add_argument("--source-ids", default="", help="Comma-separated source filter")
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="0 means unbounded streaming")
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument(
        "--skip-link-materialization",
        action="store_true",
        help="For document-fetch, do not materialize initiative JSON links first",
    )
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def _source_ids(raw: str) -> list[str]:
    return sorted({token.strip() for token in str(raw or "").split(",") if token.strip()})


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        return resolved.name


def _iter_cursor(cursor: sqlite3.Cursor, *, fetch_size: int) -> Iterator[sqlite3.Row]:
    while True:
        rows = cursor.fetchmany(max(1, int(fetch_size)))
        if not rows:
            return
        yield from rows


def _where_source_ids(column: str, source_ids: list[str]) -> tuple[str, list[object]]:
    if not source_ids:
        return "", []
    marks = ",".join("?" for _ in source_ids)
    return f" AND {column} IN ({marks})", list(source_ids)


def _urls_from_json(raw: object) -> tuple[list[str], bool]:
    text = str(raw or "").strip()
    if not text:
        return [], True
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return [], False
    urls: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, str):
            candidate = node.strip()
            if candidate.startswith(("http://", "https://")):
                urls.append(candidate)
        elif isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, dict):
            for key in ("url", "href", "source_url", "doc_url"):
                if key in node:
                    visit(node[key])

    visit(value)
    return sorted(set(urls)), True


def materialize_initiative_document_links(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    fetch_size: int,
) -> dict[str, int]:
    if not table_exists(conn, "parl_initiatives") or not table_exists(
        conn, "parl_initiative_documents"
    ):
        return {
            "initiatives_scanned": 0,
            "link_values_seen": 0,
            "rows_candidate": 0,
            "rows_inserted": 0,
            "invalid_json_values": 0,
        }
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(parl_initiatives)").fetchall()
    }
    if not {"links_bocg_json", "links_ds_json"}.issubset(columns):
        return {
            "initiatives_scanned": 0,
            "link_values_seen": 0,
            "rows_candidate": 0,
            "rows_inserted": 0,
            "invalid_json_values": 0,
        }
    source_where, params = _where_source_ids("source_id", source_ids)
    cursor = conn.execute(
        f"""
        SELECT initiative_id, links_bocg_json, links_ds_json
        FROM parl_initiatives
        WHERE 1 = 1 {source_where}
        ORDER BY initiative_id ASC
        """,
        params,
    )
    now_iso = now_utc_iso()
    totals = {
        "initiatives_scanned": 0,
        "link_values_seen": 0,
        "rows_candidate": 0,
        "rows_inserted": 0,
        "invalid_json_values": 0,
    }
    pending: list[tuple[object, ...]] = []
    before_changes = conn.total_changes

    def flush() -> None:
        if not pending:
            return
        conn.executemany(
            """
            INSERT INTO parl_initiative_documents (
              initiative_id, doc_kind, doc_url, source_record_pk,
              created_at, updated_at
            ) VALUES (?, ?, ?, NULL, ?, ?)
            ON CONFLICT(initiative_id, doc_kind, doc_url) DO NOTHING
            """,
            pending,
        )
        pending.clear()

    for row in _iter_cursor(cursor, fetch_size=fetch_size):
        totals["initiatives_scanned"] += 1
        for doc_kind, column in (
            ("bocg", "links_bocg_json"),
            ("ds", "links_ds_json"),
        ):
            urls, valid = _urls_from_json(row[column])
            totals["link_values_seen"] += 1 if str(row[column] or "").strip() else 0
            totals["invalid_json_values"] += 0 if valid else 1
            for url in urls:
                totals["rows_candidate"] += 1
                pending.append(
                    (str(row["initiative_id"]), doc_kind, url, now_iso, now_iso)
                )
                if len(pending) >= max(1, int(fetch_size)):
                    flush()
    flush()
    conn.commit()
    totals["rows_inserted"] = conn.total_changes - before_changes
    return totals


def iter_source_record_work(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    limit: int,
    fetch_size: int,
    max_attempts: int,
) -> Iterable[dict[str, object]]:
    source_where, params = _where_source_ids("source_id", source_ids)
    limit_sql = " LIMIT ?" if limit > 0 else ""
    if limit > 0:
        params.append(int(limit))
    cursor = conn.execute(
        f"""
        SELECT source_record_pk, source_id, source_record_id, source_snapshot_date
        FROM source_records
        WHERE 1 = 1 {source_where}
        ORDER BY source_record_pk ASC
        {limit_sql}
        """,
        params,
    )
    for row in _iter_cursor(cursor, fetch_size=fetch_size):
        source_id = str(row["source_id"])
        yield {
            "item_key": f"{source_id}:{row['source_record_id']}",
            "partition_key": source_id,
            "payload": {
                "source_record_pk": int(row["source_record_pk"]),
                "source_id": source_id,
                "source_record_id": str(row["source_record_id"]),
                "source_snapshot_date": row["source_snapshot_date"],
            },
            "max_attempts": max_attempts,
        }


def iter_text_extraction_work(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    only_missing: bool,
    limit: int,
    fetch_size: int,
    max_attempts: int,
) -> Iterable[dict[str, object]]:
    source_where, params = _where_source_ids("source_id", source_ids)
    missing_where = (
        " AND (text_excerpt IS NULL OR TRIM(text_excerpt) = '')" if only_missing else ""
    )
    limit_sql = " LIMIT ?" if limit > 0 else ""
    if limit > 0:
        params.append(int(limit))
    cursor = conn.execute(
        f"""
        SELECT
          text_document_id,
          source_id,
          source_record_pk,
          source_url,
          content_type,
          content_sha256,
          bytes,
          raw_path
        FROM text_documents
        WHERE raw_path IS NOT NULL
          AND TRIM(raw_path) != ''
          {source_where}
          {missing_where}
        ORDER BY text_document_id ASC
        {limit_sql}
        """,
        params,
    )
    for row in _iter_cursor(cursor, fetch_size=fetch_size):
        source_id = str(row["source_id"])
        content_sha256 = str(row["content_sha256"] or "").strip()
        source_record_pk = int(row["source_record_pk"] or 0)
        item_key = (
            f"sha256:{content_sha256.lower()}"
            if content_sha256
            else f"text_document_id:{int(row['text_document_id'])}"
        )
        yield {
            "item_key": item_key,
            "partition_key": source_id,
            "payload": {
                "text_document_id": int(row["text_document_id"]),
                "source_record_pk": source_record_pk,
                "source_id": source_id,
                "source_url": str(row["source_url"] or ""),
                "content_type": str(row["content_type"] or ""),
                "content_sha256": content_sha256,
                "bytes": int(row["bytes"] or 0),
                "raw_path": str(row["raw_path"]),
            },
            "max_attempts": max_attempts,
        }


def iter_document_fetch_work(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    only_missing: bool,
    limit: int,
    fetch_size: int,
    max_attempts: int,
) -> Iterable[dict[str, object]]:
    source_where, params = _where_source_ids("i.source_id", source_ids)
    missing_where = (
        " AND d.source_record_pk IS NULL AND COALESCE(f.fetched_ok, 0) = 0"
        if only_missing
        else ""
    )
    limit_sql = " LIMIT ?" if limit > 0 else ""
    if limit > 0:
        params.append(int(limit))
    cursor = conn.execute(
        f"""
        SELECT
          d.initiative_id,
          d.doc_kind,
          d.doc_url,
          d.source_record_pk,
          i.source_id,
          i.legislature,
          COALESCE(f.attempts, 0) AS prior_attempts,
          COALESCE(f.last_http_status, 0) AS last_http_status
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        LEFT JOIN document_fetches f ON f.doc_url = d.doc_url
        WHERE TRIM(d.doc_url) != ''
          {source_where}
          {missing_where}
        ORDER BY d.initiative_id ASC, d.doc_url ASC
        {limit_sql}
        """,
        params,
    )
    for row in _iter_cursor(cursor, fetch_size=fetch_size):
        source_id = str(row["source_id"])
        doc_url = str(row["doc_url"])
        legislature = str(row["legislature"] or "").strip()
        try:
            legislature_priority = max(0, int(legislature))
        except ValueError:
            legislature_priority = 0
        yield {
            "item_key": doc_url,
            "partition_key": (
                f"{source_id}:leg{legislature}" if legislature else source_id
            ),
            "priority": (
                (1_000 if int(row["prior_attempts"] or 0) == 0 else 0)
                + legislature_priority * 10
                + (1 if doc_url.startswith("https://") else 0)
            ),
            "payload": {
                "initiative_id": str(row["initiative_id"]),
                "doc_kind": str(row["doc_kind"]),
                "doc_url": doc_url,
                "source_id": source_id,
                "legislature": legislature,
                "source_record_pk": int(row["source_record_pk"] or 0),
                "prior_attempts": int(row["prior_attempts"] or 0),
                "last_http_status": int(row["last_http_status"] or 0),
            },
            "max_attempts": max_attempts,
        }


def iter_placsp_document_fetch_work(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    only_missing: bool,
    limit: int,
    fetch_size: int,
    max_attempts: int,
) -> Iterable[dict[str, object]]:
    source_where, params = _where_source_ids("d.source_id", source_ids)
    missing_where = (
        " AND d.document_source_record_pk IS NULL "
        "AND COALESCE(f.fetched_ok, 0) = 0"
        if only_missing
        else ""
    )
    limit_sql = " LIMIT ?" if limit > 0 else ""
    if limit > 0:
        params.append(int(limit))
    cursor = conn.execute(
        f"""
        SELECT
          MIN(d.contract_document_id) AS contract_document_id,
          d.source_url AS doc_url,
          MIN(d.document_kind) AS document_kind,
          COUNT(*) AS manifest_sightings,
          COALESCE(MAX(f.attempts), 0) AS prior_attempts,
          COALESCE(MAX(f.last_http_status), 0) AS last_http_status
        FROM money_contract_documents AS d
        LEFT JOIN document_fetches AS f ON f.doc_url = d.source_url
        WHERE TRIM(d.source_url) != ''
          {source_where}
          {missing_where}
        GROUP BY d.source_url
        ORDER BY MIN(d.contract_document_id)
        {limit_sql}
        """,
        params,
    )
    for row in _iter_cursor(cursor, fetch_size=fetch_size):
        doc_url = str(row["doc_url"])
        yield {
            "item_key": doc_url,
            "partition_key": f"placsp:{hashlib.sha256(doc_url.encode()).hexdigest()[:2]}",
            "priority": 1_000 if int(row["prior_attempts"] or 0) == 0 else 0,
            "payload": {
                "contract_document_id": int(row["contract_document_id"]),
                "doc_kind": str(row["document_kind"] or ""),
                "doc_url": doc_url,
                "document_source_id": "placsp_contract_docs",
                "manifest_sightings": int(row["manifest_sightings"]),
                "prior_attempts": int(row["prior_attempts"] or 0),
                "last_http_status": int(row["last_http_status"] or 0),
            },
            "max_attempts": max_attempts,
        }


def iter_work_items(
    conn: sqlite3.Connection,
    *,
    kind: str,
    source_ids: list[str],
    only_missing: bool,
    limit: int,
    fetch_size: int,
    max_attempts: int,
) -> Iterable[dict[str, object]]:
    required_table = {
        "document-fetch": "parl_initiative_documents",
        "placsp-document-fetch": "money_contract_documents",
        "source-record-transform": "source_records",
        "text-extract": "text_documents",
    }[kind]
    if not table_exists(conn, required_table):
        raise RuntimeError(f"required table missing for {kind}: {required_table}")
    if kind == "source-record-transform":
        return iter_source_record_work(
            conn,
            source_ids=source_ids,
            limit=limit,
            fetch_size=fetch_size,
            max_attempts=max_attempts,
        )
    if kind == "text-extract":
        return iter_text_extraction_work(
            conn,
            source_ids=source_ids,
            only_missing=only_missing,
            limit=limit,
            fetch_size=fetch_size,
            max_attempts=max_attempts,
        )
    if kind == "placsp-document-fetch":
        return iter_placsp_document_fetch_work(
            conn,
            source_ids=source_ids,
            only_missing=only_missing,
            limit=limit,
            fetch_size=fetch_size,
            max_attempts=max_attempts,
        )
    return iter_document_fetch_work(
        conn,
        source_ids=source_ids,
        only_missing=only_missing,
        limit=limit,
        fetch_size=fetch_size,
        max_attempts=max_attempts,
    )


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"ERROR: DB not found: {_display_path(db_path)}", file=sys.stderr)
        return 2
    if int(args.batch_size) < 1 or int(args.max_attempts) < 1 or int(args.limit) < 0:
        print("ERROR: batch-size/max-attempts must be >= 1 and limit >= 0", file=sys.stderr)
        return 2

    pipeline_id = str(args.pipeline_id or DEFAULT_PIPELINES[str(args.kind)]).strip()
    writer = open_db(db_path)
    try:
        ensure_work_queue_schema(writer)
        link_materialization = None
        if str(args.kind) == "document-fetch" and not bool(
            args.skip_link_materialization
        ):
            link_materialization = materialize_initiative_document_links(
                writer,
                source_ids=_source_ids(str(args.source_ids)),
                fetch_size=int(args.batch_size),
            )
        reader = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        reader.row_factory = sqlite3.Row
        try:
            items = iter_work_items(
                reader,
                kind=str(args.kind),
                source_ids=_source_ids(str(args.source_ids)),
                only_missing=bool(args.only_missing),
                limit=int(args.limit),
                fetch_size=int(args.batch_size),
                max_attempts=int(args.max_attempts),
            )
            enqueue_result = enqueue_work_items(
                writer,
                pipeline_id=pipeline_id,
                items=items,
                batch_size=int(args.batch_size),
            )
        finally:
            reader.close()
        report = {
            "schema_version": "scale_work_queue_enqueue_v1",
            "status": "ok",
            "db": _display_path(db_path),
            "kind": str(args.kind),
            "pipeline_id": pipeline_id,
            "source_ids": _source_ids(str(args.source_ids)),
            "only_missing": bool(args.only_missing),
            "limit": int(args.limit),
            "batch_size": int(args.batch_size),
            "enqueue": enqueue_result,
            "link_materialization": link_materialization,
            "queue": work_queue_stats(writer, pipeline_id=pipeline_id),
        }
    finally:
        writer.close()

    if str(args.report_out or "").strip():
        write_report(Path(args.report_out), report)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
