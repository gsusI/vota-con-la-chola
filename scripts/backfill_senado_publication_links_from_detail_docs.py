#!/usr/bin/env python3
"""Backfill Senado initiative publication links from downloaded detail XML.

Uses already-downloaded `tipoFich=3` XML docs to extract Senado publication PDFs
(`.../publicaciones/pdf/senado/bocg/...` and `.../publicaciones/pdf/senado/ds/...`)
and append them into `parl_initiatives.links_bocg_json` / `links_ds_json`.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urljoin

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.util import normalize_ws, now_utc_iso, stable_json


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
SENADO_BASE = "https://www.senado.es"
_SENADO_PUBLICATION_RE = re.compile(
    r"(?:(?:https?://www\.senado\.es)?/(?:legis\d+/publicaciones/pdf/senado/(?:bocg|ds)/[^\s<\]\"')]+\.PDF))",
    re.I,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill Senado publication links from downloaded detail XML")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--source-id", default="senado_iniciativas")
    p.add_argument("--doc-source-id", default="parl_initiative_docs")
    p.add_argument(
        "--only-initiatives-with-missing-docs",
        action="store_true",
        help="Only initiatives that still have at least one missing downloaded doc",
    )
    p.add_argument("--limit", type=int, default=0, help="0 = no limit")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _canonical_url(url: str) -> str:
    token = normalize_ws(str(url or ""))
    if not token:
        return ""
    return token.split("#", 1)[0]


def _extract_senado_publication_urls(raw_bytes: bytes) -> tuple[list[str], list[str]]:
    text = raw_bytes.decode("latin-1", errors="replace")
    out: list[str] = []
    seen: set[str] = set()
    for m in _SENADO_PUBLICATION_RE.findall(text):
        token = normalize_ws(str(m or ""))
        if not token:
            continue
        while token and token[-1] in "]).,;>\"'":
            token = token[:-1].rstrip()
        if not token:
            continue
        full = urljoin(SENADO_BASE, token)
        canon = _canonical_url(full)
        if not canon or canon in seen:
            continue
        seen.add(canon)
        out.append(canon)

    bocg = [u for u in out if "/senado/bocg/" in u.lower()]
    ds = [u for u in out if "/senado/ds/" in u.lower()]
    return bocg, ds


def _parse_json_urls(raw_json: str | None) -> list[str]:
    token = normalize_ws(str(raw_json or ""))
    if not token:
        return []
    try:
        obj = json.loads(token)
    except Exception:
        return []
    if not isinstance(obj, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in obj:
        if not isinstance(item, str):
            continue
        canon = _canonical_url(item)
        if not canon or canon in seen:
            continue
        seen.add(canon)
        out.append(canon)
    return out


def _merge_urls(existing: list[str], extra: list[str]) -> tuple[list[str], int]:
    out = list(existing)
    seen = set(existing)
    added = 0
    for u in extra:
        canon = _canonical_url(u)
        if not canon or canon in seen:
            continue
        seen.add(canon)
        out.append(canon)
        added += 1
    return out, added


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    source_id = normalize_ws(str(args.source_id or "")) or "senado_iniciativas"
    doc_source_id = normalize_ws(str(args.doc_source_id or "")) or "parl_initiative_docs"
    limit = int(args.limit or 0)
    where_missing = ""
    if bool(args.only_initiatives_with_missing_docs):
        where_missing = """
          AND EXISTS (
            SELECT 1
            FROM parl_initiative_documents dm
            LEFT JOIN text_documents tdm
              ON tdm.source_record_pk = dm.source_record_pk
             AND tdm.source_id = :doc_source_id
            WHERE dm.initiative_id = i.initiative_id
              AND tdm.source_record_pk IS NULL
          )
        """
    limit_sql = "LIMIT :limit" if limit > 0 else ""

    sql = f"""
    WITH detail_docs AS (
      SELECT
        pid.initiative_id,
        MAX(td.text_document_id) AS text_document_id
      FROM parl_initiative_documents pid
      JOIN parl_initiatives i ON i.initiative_id = pid.initiative_id
      JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
      WHERE i.source_id = :source_id
        AND td.source_id = :doc_source_id
        AND td.source_url LIKE '%tipoFich=3%'
      GROUP BY pid.initiative_id
    )
    SELECT
      i.initiative_id,
      i.links_bocg_json,
      i.links_ds_json,
      td.raw_path
    FROM detail_docs dd
    JOIN parl_initiatives i ON i.initiative_id = dd.initiative_id
    JOIN text_documents td ON td.text_document_id = dd.text_document_id
    WHERE i.source_id = :source_id
      {where_missing}
    ORDER BY i.initiative_id ASC
    {limit_sql}
    """

    seen = 0
    updated = 0
    bocg_links_added = 0
    ds_links_added = 0
    parse_failures: list[str] = []
    updates: list[tuple[str, str, str, str]] = []
    sample_updates: list[dict[str, object]] = []
    now_iso = now_utc_iso()

    with open_db(db_path) as conn:
        params: dict[str, object] = {"source_id": source_id, "doc_source_id": doc_source_id}
        if limit > 0:
            params["limit"] = limit
        rows = conn.execute(sql, params).fetchall()
        seen = len(rows)

        for r in rows:
            initiative_id = normalize_ws(str(r["initiative_id"] or ""))
            if not initiative_id:
                continue
            raw_path = normalize_ws(str(r["raw_path"] or ""))
            if not raw_path:
                parse_failures.append(f"{initiative_id}: missing raw_path")
                continue
            p = Path(raw_path)
            if not p.exists():
                parse_failures.append(f"{initiative_id}: raw_path missing on disk ({raw_path})")
                continue

            try:
                extra_bocg, extra_ds = _extract_senado_publication_urls(p.read_bytes())
            except OSError as exc:
                parse_failures.append(f"{initiative_id}: read raw_path -> {type(exc).__name__}: {exc}")
                continue
            if not extra_bocg and not extra_ds:
                continue

            existing_bocg = _parse_json_urls(str(r["links_bocg_json"] or ""))
            existing_ds = _parse_json_urls(str(r["links_ds_json"] or ""))
            merged_bocg, added_bocg = _merge_urls(existing_bocg, extra_bocg)
            merged_ds, added_ds = _merge_urls(existing_ds, extra_ds)
            if added_bocg <= 0 and added_ds <= 0:
                continue

            bocg_links_added += int(added_bocg)
            ds_links_added += int(added_ds)
            updated += 1
            new_bocg_json = stable_json(merged_bocg) if merged_bocg else "[]"
            new_ds_json = stable_json(merged_ds) if merged_ds else "[]"
            updates.append((new_bocg_json, new_ds_json, now_iso, initiative_id))
            if len(sample_updates) < 20:
                sample_updates.append(
                    {
                        "initiative_id": initiative_id,
                        "added_bocg": int(added_bocg),
                        "added_ds": int(added_ds),
                    }
                )

        if updates and not bool(args.dry_run):
            with conn:
                conn.executemany(
                    """
                    UPDATE parl_initiatives
                    SET
                      links_bocg_json = ?,
                      links_ds_json = ?,
                      updated_at = ?
                    WHERE initiative_id = ?
                    """,
                    updates,
                )

    result = {
        "db": str(db_path),
        "source_id": source_id,
        "doc_source_id": doc_source_id,
        "dry_run": bool(args.dry_run),
        "only_initiatives_with_missing_docs": bool(args.only_initiatives_with_missing_docs),
        "limit": int(limit),
        "initiatives_seen": int(seen),
        "initiatives_updated": int(updated),
        "bocg_links_added": int(bocg_links_added),
        "ds_links_added": int(ds_links_added),
        "parse_failures": parse_failures[:30],
        "sample_updates": sample_updates,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
