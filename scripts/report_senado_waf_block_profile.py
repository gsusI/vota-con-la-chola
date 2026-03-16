#!/usr/bin/env python3
"""Build a reproducible WAF block profile for Senado initiative-doc tails.

The report focuses on missing initiative-doc URLs for `senado_iniciativas`,
with actionable defaults aligned to the current operational queue:
- linked to vote events only
- redundant global_enmiendas rows excluded when an equivalent BOCG/INI-3 doc
  is already downloaded for the initiative
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
_GLOBAL_ENMIENDAS_TOKEN = "global_enmiendas_vetos_"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _display_path(path: Path) -> str:
    if not path.is_absolute():
        return str(path)
    return f"<abs>/{path.name or 'db.sqlite'}"


def _status_buckets(rows: list[dict[str, Any]], *, key: str = "last_http_status") -> list[dict[str, int]]:
    buckets: dict[int, int] = {}
    for r in rows:
        status = int(r.get(key) or 0)
        buckets[status] = int(buckets.get(status, 0)) + 1
    out = [{"status": int(k), "count": int(v)} for k, v in buckets.items()]
    out.sort(key=lambda x: (-int(x["count"]), -int(x["status"])))
    return out


def _method_hint(last_error: str) -> str:
    token = str(last_error or "").lower()
    if "playwright" in token:
        return "playwright"
    if "http error" in token or "httperror" in token:
        return "http"
    if token:
        return "other"
    return "unknown"


def _parse_leg_tipo_from_url(url: str) -> tuple[str, str]:
    token = str(url or "").strip()
    if not token:
        return "unknown", "unknown"
    try:
        parsed = urlparse(token)
    except Exception:  # noqa: BLE001
        return "unknown", "unknown"
    q = parse_qs(parsed.query or "", keep_blank_values=False)
    leg = (q.get("legis") or [""])[0].strip()
    tipo = ((q.get("tipoEx") or [""])[0] or (q.get("id1") or [""])[0]).strip()
    if leg and tipo:
        return leg, tipo

    path = parsed.path or ""
    m = re.search(r"/legis(?P<leg>\d+)/expedientes/(?P<tipo>\d+)/", path, flags=re.I)
    if m:
        return str(m.group("leg") or "").strip() or "unknown", str(m.group("tipo") or "").strip() or "unknown"
    return leg or "unknown", tipo or "unknown"


def _open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(table),),
    ).fetchone()
    return row is not None


def _load_redundant_senado_initiatives(conn: sqlite3.Connection) -> set[str]:
    if not _table_exists(conn, "text_documents"):
        return set()
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
    return {str(r["initiative_id"] or "") for r in rows if str(r["initiative_id"] or "")}


def build_waf_block_profile(
    conn: sqlite3.Connection,
    *,
    initiative_source_id: str,
    doc_source_id: str,
    only_linked_to_votes: bool,
    sample_limit: int,
) -> dict[str, Any]:
    if not _table_exists(conn, "parl_initiative_documents") or not _table_exists(conn, "parl_initiatives"):
        return {
            "status": "failed",
            "error": "required initiative tables are missing",
            "checks": {
                "has_missing_urls": False,
                "has_403_signal": False,
                "has_cohorts": False,
                "has_zero_doc_priority": False,
            },
        }

    vote_join = ""
    vote_where = ""
    if only_linked_to_votes and _table_exists(conn, "parl_vote_event_initiatives"):
        vote_join = "JOIN (SELECT DISTINCT initiative_id FROM parl_vote_event_initiatives) vi ON vi.initiative_id = i.initiative_id"
    elif only_linked_to_votes:
        vote_where = "AND 1=0"

    sql = f"""
        SELECT
          i.initiative_id,
          d.doc_kind,
          d.doc_url,
          COALESCE(df.last_http_status, 0) AS last_http_status,
          COALESCE(df.attempts, 0) AS attempts,
          COALESCE(df.last_error, '') AS last_error,
          COALESCE(df.last_attempt_at, '') AS last_attempt_at
        FROM parl_initiatives i
        JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
        {vote_join}
        LEFT JOIN document_fetches df ON df.doc_url = d.doc_url AND COALESCE(df.source_id, ?) = ?
        WHERE i.source_id = ?
          AND d.source_record_pk IS NULL
          {vote_where}
        ORDER BY
          COALESCE(df.last_http_status, 0) DESC,
          COALESCE(df.attempts, 0) DESC,
          i.initiative_id ASC,
          d.doc_url ASC
    """
    rows = conn.execute(
        sql,
        (
            doc_source_id,
            doc_source_id,
            initiative_source_id,
        ),
    ).fetchall()

    redundant_inits = _load_redundant_senado_initiatives(conn)
    filtered_rows: list[dict[str, Any]] = []
    for r in rows:
        initiative_id = str(r["initiative_id"] or "")
        doc_kind = str(r["doc_kind"] or "")
        doc_url = str(r["doc_url"] or "")
        if (
            initiative_source_id == "senado_iniciativas"
            and initiative_id in redundant_inits
            and doc_kind == "bocg"
            and _GLOBAL_ENMIENDAS_TOKEN in doc_url
        ):
            continue
        leg, tipo = _parse_leg_tipo_from_url(doc_url)
        filtered_rows.append(
            {
                "initiative_id": initiative_id,
                "doc_kind": doc_kind,
                "doc_url": doc_url,
                "last_http_status": int(r["last_http_status"] or 0),
                "attempts": int(r["attempts"] or 0),
                "last_error": str(r["last_error"] or ""),
                "last_attempt_at": str(r["last_attempt_at"] or ""),
                "method_hint": _method_hint(str(r["last_error"] or "")),
                "legislature": leg,
                "tipo_expediente": tipo,
                "cohort": f"leg{leg}:tipo{tipo}",
            }
        )

    downloaded_inits_rows = conn.execute(
        """
        SELECT DISTINCT i.initiative_id
        FROM parl_initiatives i
        JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
        WHERE i.source_id = ?
          AND d.source_record_pk IS NOT NULL
        """,
        (initiative_source_id,),
    ).fetchall()
    downloaded_inits = {str(r["initiative_id"] or "") for r in downloaded_inits_rows if str(r["initiative_id"] or "")}

    by_cohort: dict[str, list[dict[str, Any]]] = {}
    by_initiative: dict[str, list[dict[str, Any]]] = {}
    for row in filtered_rows:
        by_cohort.setdefault(str(row["cohort"]), []).append(row)
        by_initiative.setdefault(str(row["initiative_id"]), []).append(row)

    cohort_rows: list[dict[str, Any]] = []
    for cohort in sorted(by_cohort.keys()):
        group = by_cohort[cohort]
        total = len(group)
        blocked_403 = sum(1 for r in group if int(r["last_http_status"]) == 403)
        blocked_500 = sum(1 for r in group if int(r["last_http_status"]) == 500)
        methods: dict[str, int] = {}
        for r in group:
            methods[str(r["method_hint"])] = int(methods.get(str(r["method_hint"]), 0)) + 1
        method_buckets = [{"method": k, "count": methods[k]} for k in sorted(methods.keys())]
        method_buckets.sort(key=lambda x: (-int(x["count"]), str(x["method"])))
        sample_urls = [str(r["doc_url"]) for r in group[: max(0, int(sample_limit))]]
        cohort_rows.append(
            {
                "cohort": cohort,
                "legislature": str(group[0]["legislature"]),
                "tipo_expediente": str(group[0]["tipo_expediente"]),
                "missing_urls": int(total),
                "blocked_403_urls": int(blocked_403),
                "blocked_403_rate": round((blocked_403 / total), 6) if total > 0 else 0.0,
                "blocked_500_urls": int(blocked_500),
                "status_buckets": _status_buckets(group),
                "method_buckets": method_buckets,
                "sample_urls": sample_urls,
            }
        )
    cohort_rows.sort(
        key=lambda x: (
            -int(x["blocked_403_urls"]),
            -int(x["missing_urls"]),
            str(x["cohort"]),
        )
    )

    zero_doc_rows: list[dict[str, Any]] = []
    for initiative_id, group in by_initiative.items():
        if initiative_id in downloaded_inits:
            continue
        total = len(group)
        blocked_403 = sum(1 for r in group if int(r["last_http_status"]) == 403)
        sorted_group = sorted(
            group,
            key=lambda r: (
                -int(r["last_http_status"] == 403),
                -int(r["attempts"]),
                str(r["doc_url"]),
            ),
        )
        top = sorted_group[0]
        zero_doc_rows.append(
            {
                "initiative_id": initiative_id,
                "cohort": str(top["cohort"]),
                "legislature": str(top["legislature"]),
                "tipo_expediente": str(top["tipo_expediente"]),
                "missing_urls": int(total),
                "blocked_403_urls": int(blocked_403),
                "blocked_403_rate": round((blocked_403 / total), 6) if total > 0 else 0.0,
                "top_doc_url": str(top["doc_url"]),
                "top_last_http_status": int(top["last_http_status"]),
                "top_attempts": int(top["attempts"]),
                "top_last_attempt_at": str(top["last_attempt_at"]),
                "top_method_hint": str(top["method_hint"]),
            }
        )
    zero_doc_rows.sort(
        key=lambda x: (
            -int(x["blocked_403_urls"]),
            -float(x["blocked_403_rate"]),
            -int(x["missing_urls"]),
            str(x["initiative_id"]),
        )
    )

    missing_urls = len(filtered_rows)
    missing_initiatives = len(by_initiative)
    blocked_403_urls = sum(1 for r in filtered_rows if int(r["last_http_status"]) == 403)
    blocked_500_urls = sum(1 for r in filtered_rows if int(r["last_http_status"]) == 500)
    unknown_status_urls = sum(1 for r in filtered_rows if int(r["last_http_status"]) == 0)
    checks = {
        "has_missing_urls": bool(missing_urls > 0),
        "has_403_signal": bool(blocked_403_urls > 0),
        "has_cohorts": bool(len(cohort_rows) > 0),
        "has_zero_doc_priority": bool(len(zero_doc_rows) > 0),
    }
    status = "ok" if all(bool(v) for v in checks.values()) else "degraded"
    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "initiative_source_id": initiative_source_id,
        "doc_source_id": doc_source_id,
        "filters": {
            "only_linked_to_votes": bool(only_linked_to_votes),
            "exclude_redundant_senado_global": True,
        },
        "totals": {
            "missing_urls": int(missing_urls),
            "missing_initiatives": int(missing_initiatives),
            "blocked_403_urls": int(blocked_403_urls),
            "blocked_403_rate": round((blocked_403_urls / missing_urls), 6) if missing_urls > 0 else 0.0,
            "blocked_500_urls": int(blocked_500_urls),
            "unknown_status_urls": int(unknown_status_urls),
            "zero_doc_initiatives": int(len(zero_doc_rows)),
        },
        "status_buckets_missing_urls": _status_buckets(filtered_rows),
        "cohorts": cohort_rows,
        "zero_doc_priority": zero_doc_rows[: max(0, int(sample_limit))],
        "checks": checks,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Senado WAF block profile from initiative-doc fetch traces")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--initiative-source-id", default="senado_iniciativas", help="parl_initiatives.source_id to profile")
    p.add_argument("--doc-source-id", default="parl_initiative_docs", help="document_fetches/text_documents source_id")
    p.add_argument(
        "--only-linked-to-votes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Filter to initiatives linked to vote events (default true).",
    )
    p.add_argument("--sample-limit", type=int, default=25, help="Max rows in samples/priority arrays")
    p.add_argument("--strict", action="store_true", help="Exit with code 4 when status != ok")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(str(args.db))
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    try:
        with _open_db(db_path) as conn:
            report = build_waf_block_profile(
                conn,
                initiative_source_id=str(args.initiative_source_id or "senado_iniciativas"),
                doc_source_id=str(args.doc_source_id or "parl_initiative_docs"),
                only_linked_to_votes=bool(args.only_linked_to_votes),
                sample_limit=max(0, int(args.sample_limit or 0)),
            )
    except sqlite3.Error as exc:
        print(json.dumps({"error": f"sqlite error: {exc}"}, ensure_ascii=False))
        return 3

    report["db"] = _display_path(db_path)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_value = str(args.out or "").strip()
    if out_value:
        out_path = Path(out_value)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and str(report.get("status") or "") != "ok":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
