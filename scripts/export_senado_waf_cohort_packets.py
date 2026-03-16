#!/usr/bin/env python3
"""Export reproducible Senado actionable packets grouped by WAF cohort.

This script materializes a bounded retry queue from initiative-document rows
that are still missing downloads. It is designed for operational slices where
network access remains blocked and we need deterministic, high-signal packets.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import defaultdict
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


def _load_initiatives_with_any_downloaded_doc(
    conn: sqlite3.Connection,
    *,
    initiative_source_id: str,
) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT i.initiative_id
        FROM parl_initiatives i
        JOIN parl_initiative_documents d ON d.initiative_id = i.initiative_id
        WHERE i.source_id = ?
          AND d.source_record_pk IS NOT NULL
        """,
        (initiative_source_id,),
    ).fetchall()
    return {str(r["initiative_id"] or "") for r in rows if str(r["initiative_id"] or "")}


def _fetch_missing_rows(
    conn: sqlite3.Connection,
    *,
    initiative_source_id: str,
    doc_source_id: str,
    only_linked_to_votes: bool,
) -> list[dict[str, Any]]:
    vote_join = ""
    vote_where = ""
    if only_linked_to_votes and _table_exists(conn, "parl_vote_event_initiatives"):
        vote_join = "JOIN (SELECT DISTINCT initiative_id FROM parl_vote_event_initiatives) vi ON vi.initiative_id = i.initiative_id"
    elif only_linked_to_votes:
        vote_where = "AND 1=0"

    rows = conn.execute(
        f"""
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
        """,
        (doc_source_id, doc_source_id, initiative_source_id),
    ).fetchall()

    redundant_inits = _load_redundant_senado_initiatives(conn)
    out: list[dict[str, Any]] = []
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
        out.append(
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
    return out


def _cohort_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_cohort: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cohort[str(row["cohort"])].append(row)

    stats: list[dict[str, Any]] = []
    for cohort, group in by_cohort.items():
        missing_urls = len(group)
        blocked_403 = sum(1 for r in group if int(r["last_http_status"]) == 403)
        blocked_500 = sum(1 for r in group if int(r["last_http_status"]) == 500)
        stats.append(
            {
                "cohort": cohort,
                "legislature": str(group[0]["legislature"]),
                "tipo_expediente": str(group[0]["tipo_expediente"]),
                "missing_urls": int(missing_urls),
                "blocked_403_urls": int(blocked_403),
                "blocked_403_rate": round((blocked_403 / missing_urls), 6) if missing_urls > 0 else 0.0,
                "blocked_500_urls": int(blocked_500),
                "status_buckets": _status_buckets(group),
            }
        )
    stats.sort(key=lambda x: (-int(x["blocked_403_urls"]), -int(x["missing_urls"]), str(x["cohort"])))
    return stats


def _select_packet_rows(
    rows: list[dict[str, Any]],
    *,
    cohort_top_n: int,
    max_urls_per_cohort: int,
    max_total_rows: int,
    include_zero_doc_priority: bool,
    max_zero_doc_rows: int,
    initiatives_with_any_downloaded_doc: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_cohort: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_initiative: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cohort[str(row["cohort"])].append(row)
        by_initiative[str(row["initiative_id"])].append(row)

    cohort_stats = _cohort_stats(rows)
    selected_cohorts = cohort_stats[: max(0, int(cohort_top_n))]
    selected_cohort_keys = {str(c["cohort"]) for c in selected_cohorts}

    packet_rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    total_cap = max(0, int(max_total_rows))
    if total_cap == 0:
        total_cap = 1_000_000_000

    for idx, cohort_info in enumerate(selected_cohorts, start=1):
        cohort = str(cohort_info["cohort"])
        group = by_cohort.get(cohort, [])
        for row in group[: max(0, int(max_urls_per_cohort))]:
            doc_url = str(row["doc_url"])
            if doc_url in seen_urls:
                continue
            if len(packet_rows) >= total_cap:
                break
            seen_urls.add(doc_url)
            packet_rows.append(
                {
                    "packet_kind": "cohort",
                    "packet_rank": int(idx),
                    "packet_id": f"cohort_{idx:02d}_{cohort}",
                    "cohort": cohort,
                    "legislature": str(row["legislature"]),
                    "tipo_expediente": str(row["tipo_expediente"]),
                    "initiative_id": str(row["initiative_id"]),
                    "doc_kind": str(row["doc_kind"]),
                    "doc_url": doc_url,
                    "last_http_status": int(row["last_http_status"]),
                    "attempts": int(row["attempts"]),
                    "last_attempt_at": str(row["last_attempt_at"]),
                    "method_hint": str(row["method_hint"]),
                    "is_zero_doc_initiative": int(
                        str(row["initiative_id"]) not in initiatives_with_any_downloaded_doc
                    ),
                    "cohort_missing_urls": int(cohort_info["missing_urls"]),
                    "cohort_blocked_403_rate": float(cohort_info["blocked_403_rate"]),
                }
            )
        if len(packet_rows) >= total_cap:
            break

    zero_doc_priority: list[dict[str, Any]] = []
    if include_zero_doc_priority:
        for initiative_id, group in by_initiative.items():
            if initiative_id in initiatives_with_any_downloaded_doc:
                continue
            total = len(group)
            blocked_403 = sum(1 for r in group if int(r["last_http_status"]) == 403)
            top = sorted(
                group,
                key=lambda r: (
                    -int(r["last_http_status"] == 403),
                    -int(r["attempts"]),
                    str(r["doc_url"]),
                ),
            )[0]
            zero_doc_priority.append(
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
                    "doc_kind": str(top["doc_kind"]),
                }
            )
        zero_doc_priority.sort(
            key=lambda x: (
                -int(x["blocked_403_urls"]),
                -float(x["blocked_403_rate"]),
                -int(x["missing_urls"]),
                str(x["initiative_id"]),
            )
        )

        for idx, item in enumerate(zero_doc_priority[: max(0, int(max_zero_doc_rows))], start=1):
            if len(packet_rows) >= total_cap:
                break
            doc_url = str(item["top_doc_url"])
            if doc_url in seen_urls:
                continue
            seen_urls.add(doc_url)
            packet_rows.append(
                {
                    "packet_kind": "zero_doc",
                    "packet_rank": int(idx),
                    "packet_id": f"zero_doc_{idx:02d}_{item['initiative_id']}",
                    "cohort": str(item["cohort"]),
                    "legislature": str(item["legislature"]),
                    "tipo_expediente": str(item["tipo_expediente"]),
                    "initiative_id": str(item["initiative_id"]),
                    "doc_kind": str(item["doc_kind"]),
                    "doc_url": doc_url,
                    "last_http_status": int(item["top_last_http_status"]),
                    "attempts": int(item["top_attempts"]),
                    "last_attempt_at": str(item["top_last_attempt_at"]),
                    "method_hint": str(item["top_method_hint"]),
                    "is_zero_doc_initiative": 1,
                    "cohort_missing_urls": int(item["missing_urls"]),
                    "cohort_blocked_403_rate": float(item["blocked_403_rate"]),
                }
            )

    # Keep output deterministic.
    packet_rows.sort(
        key=lambda r: (
            str(r["packet_kind"]),
            int(r["packet_rank"]),
            str(r["cohort"]),
            str(r["initiative_id"]),
            str(r["doc_url"]),
        )
    )
    return selected_cohorts, zero_doc_priority, packet_rows


def build_packet_report(
    conn: sqlite3.Connection,
    *,
    initiative_source_id: str,
    doc_source_id: str,
    only_linked_to_votes: bool,
    cohort_top_n: int,
    max_urls_per_cohort: int,
    max_total_rows: int,
    include_zero_doc_priority: bool,
    max_zero_doc_rows: int,
    strict_min_packet_rows: int,
    strict_min_cohorts: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    required_tables = ("parl_initiatives", "parl_initiative_documents", "document_fetches")
    for table in required_tables:
        if not _table_exists(conn, table):
            return (
                {
                    "status": "failed",
                    "error": f"required table missing: {table}",
                    "checks": {
                        "has_missing_urls": False,
                        "selected_cohorts_min_met": False,
                        "packet_rows_min_met": False,
                    },
                },
                [],
            )

    rows = _fetch_missing_rows(
        conn,
        initiative_source_id=initiative_source_id,
        doc_source_id=doc_source_id,
        only_linked_to_votes=only_linked_to_votes,
    )
    initiatives_with_any_downloaded_doc = _load_initiatives_with_any_downloaded_doc(
        conn,
        initiative_source_id=initiative_source_id,
    )

    selected_cohorts, zero_doc_priority, packet_rows = _select_packet_rows(
        rows,
        cohort_top_n=cohort_top_n,
        max_urls_per_cohort=max_urls_per_cohort,
        max_total_rows=max_total_rows,
        include_zero_doc_priority=include_zero_doc_priority,
        max_zero_doc_rows=max_zero_doc_rows,
        initiatives_with_any_downloaded_doc=initiatives_with_any_downloaded_doc,
    )

    missing_urls = len(rows)
    blocked_403_urls = sum(1 for r in rows if int(r["last_http_status"]) == 403)
    missing_initiatives = len({str(r["initiative_id"]) for r in rows})
    packet_unique_initiatives = len({str(r["initiative_id"]) for r in packet_rows})
    checks = {
        "has_missing_urls": bool(missing_urls > 0),
        "selected_cohorts_min_met": bool(len(selected_cohorts) >= max(0, int(strict_min_cohorts))),
        "packet_rows_min_met": bool(len(packet_rows) >= max(0, int(strict_min_packet_rows))),
    }
    status = "ok" if all(bool(v) for v in checks.values()) else "degraded"
    strict_fail_reasons: list[str] = []
    if not checks["has_missing_urls"]:
        strict_fail_reasons.append("no_missing_urls")
    if not checks["selected_cohorts_min_met"]:
        strict_fail_reasons.append("selected_cohorts_below_min")
    if not checks["packet_rows_min_met"]:
        strict_fail_reasons.append("packet_rows_below_min")

    report = {
        "generated_at": now_utc_iso(),
        "status": status,
        "initiative_source_id": initiative_source_id,
        "doc_source_id": doc_source_id,
        "filters": {
            "only_linked_to_votes": bool(only_linked_to_votes),
            "exclude_redundant_senado_global": True,
        },
        "limits": {
            "cohort_top_n": int(max(0, cohort_top_n)),
            "max_urls_per_cohort": int(max(0, max_urls_per_cohort)),
            "max_total_rows": int(max(0, max_total_rows)),
            "include_zero_doc_priority": bool(include_zero_doc_priority),
            "max_zero_doc_rows": int(max(0, max_zero_doc_rows)),
            "strict_min_packet_rows": int(max(0, strict_min_packet_rows)),
            "strict_min_cohorts": int(max(0, strict_min_cohorts)),
        },
        "totals": {
            "missing_urls": int(missing_urls),
            "missing_initiatives": int(missing_initiatives),
            "blocked_403_urls": int(blocked_403_urls),
            "blocked_403_rate": round((blocked_403_urls / missing_urls), 6) if missing_urls > 0 else 0.0,
            "selected_cohorts_total": int(len(selected_cohorts)),
            "zero_doc_priority_total": int(len(zero_doc_priority)),
            "packet_rows_total": int(len(packet_rows)),
            "packet_unique_initiatives_total": int(packet_unique_initiatives),
        },
        "status_buckets_missing_urls": _status_buckets(rows),
        "selected_cohorts": selected_cohorts,
        "zero_doc_priority": zero_doc_priority[: max(0, int(max_zero_doc_rows))],
        "checks": checks,
        "strict_fail_reasons": strict_fail_reasons,
    }
    return report, packet_rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "packet_kind",
        "packet_rank",
        "packet_id",
        "cohort",
        "legislature",
        "tipo_expediente",
        "initiative_id",
        "doc_kind",
        "doc_url",
        "last_http_status",
        "attempts",
        "last_attempt_at",
        "method_hint",
        "is_zero_doc_initiative",
        "cohort_missing_urls",
        "cohort_blocked_403_rate",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export bounded Senado WAF cohort packets")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--initiative-source-id", default="senado_iniciativas")
    p.add_argument("--doc-source-id", default="parl_initiative_docs")
    p.add_argument(
        "--only-linked-to-votes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Restrict queue to initiatives linked to vote events (default true).",
    )
    p.add_argument("--cohort-top-n", type=int, default=4, help="Top cohorts by 403/missing to include")
    p.add_argument("--max-urls-per-cohort", type=int, default=25, help="Cap rows per selected cohort")
    p.add_argument("--max-total-rows", type=int, default=120, help="Global cap across packets (0 = no cap)")
    p.add_argument(
        "--include-zero-doc-priority",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Append one top URL per initiative with zero downloaded docs (default true).",
    )
    p.add_argument("--max-zero-doc-rows", type=int, default=25, help="Cap zero-doc packet rows")
    p.add_argument(
        "--strict-min-packet-rows",
        type=int,
        default=1,
        help="Strict check: minimum packet rows required",
    )
    p.add_argument(
        "--strict-min-cohorts",
        type=int,
        default=1,
        help="Strict check: minimum selected cohorts required",
    )
    p.add_argument("--out", required=True, help="JSON summary output path")
    p.add_argument("--csv-out", required=True, help="CSV packet output path")
    p.add_argument("--strict", action="store_true", help="Exit code 4 when status != ok")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(str(args.db))
    out_path = Path(str(args.out))
    csv_out_path = Path(str(args.csv_out))

    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    try:
        with _open_db(db_path) as conn:
            report, packet_rows = build_packet_report(
                conn,
                initiative_source_id=str(args.initiative_source_id or "senado_iniciativas"),
                doc_source_id=str(args.doc_source_id or "parl_initiative_docs"),
                only_linked_to_votes=bool(args.only_linked_to_votes),
                cohort_top_n=max(0, int(args.cohort_top_n or 0)),
                max_urls_per_cohort=max(0, int(args.max_urls_per_cohort or 0)),
                max_total_rows=max(0, int(args.max_total_rows or 0)),
                include_zero_doc_priority=bool(args.include_zero_doc_priority),
                max_zero_doc_rows=max(0, int(args.max_zero_doc_rows or 0)),
                strict_min_packet_rows=max(0, int(args.strict_min_packet_rows or 0)),
                strict_min_cohorts=max(0, int(args.strict_min_cohorts or 0)),
            )
    except sqlite3.Error as exc:
        print(json.dumps({"error": f"sqlite error: {exc}"}, ensure_ascii=False))
        return 3

    report["db"] = _display_path(db_path)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")
    _write_csv(csv_out_path, packet_rows)

    if bool(args.strict) and str(report.get("status") or "") != "ok":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
