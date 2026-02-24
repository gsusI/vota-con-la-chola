#!/usr/bin/env python3
"""Export initiative document URLs that are missing downloads.

Purpose:
- Provide a deterministic URL list for manual/headful capture when upstream blocks reproducible HTTP.

Typical use:
- Export Senado missing URLs (often 403) to feed a headful/manual tool.

Output formats:
- default: plain newline-separated URLs
- optional: CSV with metadata
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export missing initiative document URLs")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument(
        "--initiative-source-ids",
        default="congreso_iniciativas,senado_iniciativas",
        help="CSV of parl_initiatives.source_id values",
    )
    p.add_argument("--only-missing", action="store_true", help="Only URLs with d.source_record_pk IS NULL")
    p.add_argument(
        "--only-status",
        default="",
        help="Filter by document_fetches.last_http_status (e.g. 403). Empty disables.",
    )
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--out", required=True, help="Output path")
    p.add_argument(
        "--format",
        choices=("txt", "csv"),
        default="txt",
        help="txt=newline urls; csv=urls with metadata",
    )
    p.add_argument(
        "--exclude-redundant-senado-global",
        action="store_true",
        help=(
            "Exclude Senado global_enmiendas_vetos URLs when the initiative already has "
            "downloaded alternative BOCG docs (INI-3, tipoFich=3 or publication PDFs)."
        ),
    )
    p.add_argument(
        "--only-actionable-missing",
        action="store_true",
        help=(
            "Shortcut for --only-missing + --exclude-redundant-senado-global. "
            "Use this to export only the actionable queue."
        ),
    )
    p.add_argument(
        "--strict-empty",
        action="store_true",
        help="Exit with code 4 when exported queue is non-empty.",
    )
    return p.parse_args(argv)


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def parse_source_ids(csv_value: str) -> list[str]:
    vals = [x.strip() for x in str(csv_value or "").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for v in vals:
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _load_redundant_senado_initiatives(conn: sqlite3.Connection) -> set[str]:
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT pid.initiative_id
            FROM parl_initiative_documents pid
            JOIN parl_initiatives i ON i.initiative_id = pid.initiative_id
            JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
            WHERE i.source_id = 'senado_iniciativas'
              AND pid.doc_kind = 'bocg'
              AND td.source_id = 'parl_initiative_docs'
              AND (
                pid.doc_url LIKE '%/xml/INI-3-%'
                OR pid.doc_url LIKE '%/publicaciones/pdf/senado/bocg/%'
                OR pid.doc_url LIKE '%tipoFich=3%'
              )
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"SQLite error while computing redundant Senado set: {exc}") from exc

    return {str(r["initiative_id"] or "") for r in rows if str(r["initiative_id"] or "")}


def _filter_redundant_senado_global_rows(
    rows: list[sqlite3.Row],
    *,
    redundant_initiatives: set[str],
) -> tuple[list[sqlite3.Row], int]:
    filtered_rows: list[sqlite3.Row] = []
    filtered_out = 0
    for r in rows:
        initiative_source_id = str(r["initiative_source_id"] or "")
        initiative_id = str(r["initiative_id"] or "")
        doc_kind = str(r["doc_kind"] or "")
        doc_url = str(r["doc_url"] or "")
        is_redundant_global = (
            initiative_source_id == "senado_iniciativas"
            and initiative_id in redundant_initiatives
            and doc_kind == "bocg"
            and "global_enmiendas_vetos_" in doc_url
        )
        if is_redundant_global:
            filtered_out += 1
            continue
        filtered_rows.append(r)
    return filtered_rows, filtered_out


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    source_ids = parse_source_ids(args.initiative_source_ids)
    if not source_ids:
        print("ERROR: initiative-source-ids empty", file=sys.stderr)
        return 2

    status_filter = str(args.only_status or "").strip()
    status_int = None
    if status_filter:
        try:
            status_int = int(status_filter)
        except ValueError:
            print("ERROR: only-status must be int", file=sys.stderr)
            return 2

    placeholders = ",".join("?" for _ in source_ids)
    where = [f"i.source_id IN ({placeholders})"]
    params: list[object] = [*source_ids]

    only_missing = bool(args.only_missing or args.only_actionable_missing)
    exclude_redundant = bool(args.exclude_redundant_senado_global or args.only_actionable_missing)

    if only_missing:
        where.append("d.source_record_pk IS NULL")

    if status_int is not None:
        where.append("df.last_http_status = ?")
        params.append(int(status_int))

    limit_sql = ""
    if int(args.limit or 0) > 0:
        limit_sql = "LIMIT ?"
        params.append(int(args.limit))

    sql = f"""
    SELECT
      i.source_id AS initiative_source_id,
      d.initiative_id,
      d.doc_kind,
      d.doc_url,
      d.source_record_pk,
      df.attempts,
      df.fetched_ok,
      df.last_http_status,
      df.last_attempt_at
    FROM parl_initiative_documents d
    JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
    LEFT JOIN document_fetches df ON df.doc_url = d.doc_url
    WHERE {' AND '.join(where)}
    ORDER BY
      COALESCE(df.last_http_status, 0) DESC,
      COALESCE(df.attempts, 0) DESC,
      d.initiative_id ASC,
      d.doc_kind ASC,
      d.doc_url ASC
    {limit_sql}
    """

    filtered_out_redundant = 0
    with open_db(db_path) as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            print(f"ERROR: SQLite error: {exc}", file=sys.stderr)
            return 3

        if exclude_redundant and rows:
            try:
                redundant_initiatives = _load_redundant_senado_initiatives(conn)
                rows, filtered_out_redundant = _filter_redundant_senado_global_rows(
                    rows,
                    redundant_initiatives=redundant_initiatives,
                )
            except RuntimeError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 3

    exported_count = 0
    if args.format == "txt":
        urls: list[str] = []
        seen: set[str] = set()
        for r in rows:
            u = str(r["doc_url"] or "").strip()
            if not u or u in seen:
                continue
            seen.add(u)
            urls.append(u)
        out_path.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
        exported_count = len(urls)
        msg = f"OK wrote {out_path} (urls={exported_count})"
        if filtered_out_redundant:
            msg += f" [excluded_redundant_senado_global={filtered_out_redundant}]"
    else:
        with out_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "initiative_source_id",
                    "initiative_id",
                    "doc_kind",
                    "doc_url",
                    "source_record_pk",
                    "attempts",
                    "fetched_ok",
                    "last_http_status",
                    "last_attempt_at",
                ]
            )
            for r in rows:
                w.writerow(
                    [
                        str(r["initiative_source_id"] or ""),
                        str(r["initiative_id"] or ""),
                        str(r["doc_kind"] or ""),
                        str(r["doc_url"] or ""),
                        str(r["source_record_pk"] or ""),
                        str(r["attempts"] or ""),
                        str(r["fetched_ok"] or ""),
                        str(r["last_http_status"] or ""),
                        str(r["last_attempt_at"] or ""),
                    ]
                )
        exported_count = len(rows)
        msg = f"OK wrote {out_path} (rows={exported_count})"
        if filtered_out_redundant:
            msg += f" [excluded_redundant_senado_global={filtered_out_redundant}]"

    if bool(args.strict_empty) and exported_count > 0:
        print(
            f"ERROR: strict-empty failed: exported_count={exported_count} out={out_path}",
            file=sys.stderr,
        )
        return 4

    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
