#!/usr/bin/env python3
"""Backfill canonical BOE source_records for sanction norms (boe_ref:<BOE-ID>)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from etl.politicos_es.db import upsert_source_record
from etl.politicos_es.http import http_get_bytes, payload_looks_like_html
from etl.politicos_es.util import normalize_ws, sha256_bytes
from etl.parlamentario_es.db import open_db


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _canonical_source_record_id(boe_id: str) -> str:
    return f"boe_ref:{boe_id}"


def _safe_text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    if node is None or node.text is None:
        return ""
    return _norm(node.text)


def _build_xml_url(boe_id: str) -> str:
    return f"https://www.boe.es/diario_boe/xml.php?id={quote(boe_id)}"


def _parse_boe_xml_metadata(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8", errors="replace")
    root = ET.fromstring(text)
    return {
        "boe_ref": _safe_text(root, "./metadatos/identificador"),
        "title": _safe_text(root, "./metadatos/titulo"),
        "fecha_publicacion": _safe_text(root, "./metadatos/fecha_publicacion"),
        "url_pdf": _safe_text(root, "./metadatos/url_pdf"),
        "url_eli": _safe_text(root, "./metadatos/url_eli"),
    }


def _is_seed_payload(raw_payload: str, *, seed_schema_version: str) -> bool:
    return f'"seed_schema_version": "{seed_schema_version}"' in str(raw_payload or "")


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    return row is not None


def _iter_target_boe_ids(conn: sqlite3.Connection, *, boe_ids: list[str], limit: int) -> list[str]:
    if boe_ids:
        out = sorted({_norm(v).upper() for v in boe_ids if _norm(v)})
    else:
        rows = conn.execute(
            """
            SELECT DISTINCT UPPER(TRIM(COALESCE(n.boe_id, ''))) AS boe_id
            FROM sanction_norm_catalog c
            JOIN legal_norms n ON n.norm_id = c.norm_id
            WHERE TRIM(COALESCE(n.boe_id, '')) <> ''
            ORDER BY boe_id
            """
        ).fetchall()
        out = [str(r["boe_id"]) for r in rows if _norm(r["boe_id"])]
    if int(limit) > 0:
        out = out[: int(limit)]
    return out


def backfill(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    timeout: int,
    boe_ids: list[str],
    limit: int,
    seed_schema_version: str,
    strict_network: bool,
) -> dict[str, Any]:
    source_id_norm = _norm(source_id)
    if not source_id_norm:
        raise ValueError("source_id is required")
    if not _source_exists(conn, source_id_norm):
        raise RuntimeError(f"source_id not found in sources: {source_id_norm}")

    targets = _iter_target_boe_ids(conn, boe_ids=boe_ids, limit=int(limit))
    now_iso = now_utc_iso()

    counts: dict[str, int] = {
        "targets_total": len(targets),
        "records_inserted": 0,
        "records_updated": 0,
        "records_existing_non_seed": 0,
        "records_existing_seed_refreshed": 0,
        "records_fetch_failed": 0,
        "records_html_blocked": 0,
    }
    failures: list[dict[str, Any]] = []

    for boe_id in targets:
        source_record_id = _canonical_source_record_id(boe_id)
        existing = conn.execute(
            """
            SELECT source_record_pk, raw_payload
            FROM source_records
            WHERE source_id = ? AND source_record_id = ?
            """,
            (source_id_norm, source_record_id),
        ).fetchone()

        if existing is not None and not _is_seed_payload(
            str(existing["raw_payload"] or ""), seed_schema_version=seed_schema_version
        ):
            counts["records_existing_non_seed"] += 1
            continue

        xml_url = _build_xml_url(boe_id)
        try:
            payload, content_type = http_get_bytes(xml_url, int(timeout))
            if payload_looks_like_html(payload):
                counts["records_html_blocked"] += 1
                raise RuntimeError("unexpected_html_payload")
            metadata = _parse_boe_xml_metadata(payload)
        except Exception as exc:  # noqa: BLE001
            counts["records_fetch_failed"] += 1
            failures.append(
                {
                    "boe_id": boe_id,
                    "source_record_id": source_record_id,
                    "source_url": xml_url,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            if strict_network:
                conn.rollback()
                raise
            continue

        raw_payload = json.dumps(
            {
                "record_kind": "boe_document_xml",
                "source_feed": "boe_diario_xml_id",
                "source_url": xml_url,
                "source_record_id": source_record_id,
                "boe_ref": boe_id,
                "title": _norm(metadata.get("title")),
                "fecha_publicacion": _norm(metadata.get("fecha_publicacion")),
                "url_pdf": _norm(metadata.get("url_pdf")),
                "url_eli": _norm(metadata.get("url_eli")),
                "content_type": _norm(content_type),
                "xml_sha256": sha256_bytes(payload),
                "xml_bytes": len(payload),
                "fetched_at": now_iso,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        content_sha = sha256_bytes(raw_payload.encode("utf-8"))

        existed_before = existing is not None
        upsert_source_record(
            conn,
            source_id_norm,
            source_record_id,
            now_iso[:10],
            raw_payload,
            content_sha,
            now_iso,
        )
        if existed_before:
            counts["records_updated"] += 1
            if _is_seed_payload(str(existing["raw_payload"] or ""), seed_schema_version=seed_schema_version):
                counts["records_existing_seed_refreshed"] += 1
        else:
            counts["records_inserted"] += 1

    conn.commit()
    return {
        "generated_at": now_iso,
        "source_id": source_id_norm,
        "seed_schema_version": seed_schema_version,
        "timeout": int(timeout),
        "strict_network": bool(strict_network),
        "counts": counts,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Backfill BOE canonical source_records for sanction norms")
    ap.add_argument("--db", required=True)
    ap.add_argument("--source-id", default="boe_api_legal")
    ap.add_argument("--seed-schema-version", default="sanction_norms_seed_v1")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--boe-id", action="append", default=[])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--strict-network", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = backfill(
            conn,
            source_id=str(args.source_id),
            timeout=int(args.timeout),
            boe_ids=[str(v) for v in list(args.boe_id)],
            limit=int(args.limit),
            seed_schema_version=_norm(args.seed_schema_version) or "sanction_norms_seed_v1",
            strict_network=bool(args.strict_network),
        )
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
