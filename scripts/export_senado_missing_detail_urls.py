#!/usr/bin/env python3
"""Export missing Senado detail XML URLs from SQLite.

Goal: make the manual "download ses_*.xml then backfill" loop trivial.

By default this exports *session-level* URLs (`ses_<session>.xml`) because one file
can cover multiple vote events. The backfill code can consume these files via
`--senado-detail-dir` even if the event originally points to a vote-specific URL.

Examples:
  # Sessions (recommended): fewer downloads, still enriches many events
  python3 scripts/export_senado_missing_detail_urls.py \\
    --db etl/data/staging/politicos-es.db --mode session > /tmp/senado_missing_sessions.txt

  # Vote URLs (1:1 per missing event)
  python3 scripts/export_senado_missing_detail_urls.py \\
    --db etl/data/staging/politicos-es.db --mode vote > /tmp/senado_missing_votes.txt

  # Filter by legislature
  python3 scripts/export_senado_missing_detail_urls.py \\
    --db etl/data/staging/politicos-es.db --mode session --legislature 14 > /tmp/senado_leg14_sessions.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_HOST = "https://www.senado.es"
UA = "Mozilla/5.0 (compatible; etl-script/1.0)"

_SENADO_SES_RE = re.compile(r"/legis(?P<leg>\\d+)/votaciones/ses_(?P<ses>\\d+)(?:_(?P<vot>\\d+))?\\.xml\\b")


def _looks_xml(payload: bytes) -> bool:
    if not payload:
        return False
    text = payload.lstrip()[:1024].lower()
    if not text:
        return False
    if text.startswith(b"<!doctype html") or text.startswith(b"<html"):
        return False
    return text.startswith(b"<?xm") or text.startswith(b"<")


def _url_is_xml(url: str, timeout: int) -> bool:
    head = Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/xml,text/xml,*/*"},
        method="HEAD",
    )
    try:
        with urlopen(head, timeout=timeout) as resp:
            ct = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" in ct:
                return False
            return 200 <= getattr(resp, "status", 200) < 400
    except HTTPError as e:
        if e.code in {301, 302, 303, 307, 308}:
            loc = e.headers.get("Location")
            if not loc:
                return False
            return _url_is_xml(loc, timeout=timeout)
        # Any non-success response is treated as non-XML.
        return False
    except (URLError, OSError, TimeoutError, ValueError):  # noqa: BLE001
        return False
    return False


def _parse_csv(value: str | None) -> tuple[str, ...]:
    txt = str(value or "").strip()
    if not txt:
        return tuple()
    out: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,\s;]+", txt):
        token = part.strip()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return tuple(out)


def _clean_url(url: str, *, force_https: bool) -> str:
    u = str(url or "").strip()
    if u.startswith("url:"):
        u = u[4:]
    if not u:
        return ""
    if force_https and u.startswith("http://www.senado.es/"):
        return "https://www.senado.es/" + u[len("http://www.senado.es/") :]
    return u


def _session_url(host: str, leg: str, session_id: int) -> str:
    base = host.rstrip("/")
    return f"{base}/legis{leg}/votaciones/ses_{int(session_id)}.xml"


def _vote_url(host: str, leg: str, session_id: int | None, vote_id: int | None) -> str | None:
    if session_id is None or vote_id is None:
        return None
    base = host.rstrip("/")
    return f"{base}/legis{leg}/votaciones/ses_{int(session_id)}_{int(vote_id)}.xml"


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return int(value)
        txt = str(value).strip()
        if not txt:
            return None
        return int(txt) if txt.isdigit() else None
    except Exception:  # noqa: BLE001
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export missing Senado ses_*.xml URLs from SQLite (no network).")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta al SQLite (default etl/data/staging/politicos-es.db)")
    p.add_argument(
        "--legislature",
        default="",
        help="Filtro de legislaturas (CSV, ej: 15,14). Si vacio, incluye todas.",
    )
    p.add_argument(
        "--mode",
        choices=("session", "vote"),
        default="session",
        help="session: ses_<sesion>.xml (recomendado). vote: ses_<sesion>_<voto>.xml (1:1 por evento).",
    )
    p.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Base host para construir URLs (default https://www.senado.es).",
    )
    p.add_argument(
        "--no-force-https",
        action="store_true",
        help="No normalizar http://www.senado.es a https://www.senado.es.",
    )
    p.add_argument(
        "--validate",
        action="store_true",
        help="Valida que la URL devuelve XML; cuando falla, omite esa URL y usa fallback.",
    )
    p.add_argument(
        "--validate-timeout",
        type=int,
        default=10,
        help="Timeout de validación por URL (segundos).",
    )
    args = p.parse_args(list(argv or sys.argv[1:]))

    leg_filter = set(_parse_csv(str(args.legislature)))
    host = str(args.host or DEFAULT_HOST).strip() or DEFAULT_HOST
    force_https = not bool(args.no_force_https)

    conn = sqlite3.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT e.vote_event_id, e.legislature, sr.raw_payload
            FROM parl_vote_events e
            LEFT JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
            WHERE e.source_id = 'senado_votaciones'
              AND NOT EXISTS (
                SELECT 1 FROM parl_vote_member_votes mv
                WHERE mv.vote_event_id = e.vote_event_id
              )
            ORDER BY e.vote_event_id
            """
        ).fetchall()
    finally:
        conn.close()

    urls: set[str] = set()
    url_ok_cache: dict[str, bool] = {}

    for r in rows:
        leg = str(r["legislature"] or "").strip()
        if leg_filter and leg not in leg_filter:
            continue

        payload: dict[str, object] = {}
        raw_payload = r["raw_payload"]
        if raw_payload:
            try:
                parsed = json.loads(str(raw_payload))
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:  # noqa: BLE001
                payload = {}

        # Prefer payload (more stable), but fall back to parsing the URL if needed.
        session_id = _to_int(payload.get("session_id"))
        vote_id = _to_int(payload.get("vote_id"))
        vote_file_url = _clean_url(str(payload.get("vote_file_url") or ""), force_https=force_https)
        candidate_urls: list[str] = []
        raw_candidates = payload.get("session_vote_file_urls")
        if isinstance(raw_candidates, list):
            for value in raw_candidates:
                candidate = _clean_url(str(value), force_https=force_https)
                if candidate:
                    candidate_urls.append(candidate)
        if vote_file_url:
            candidate_urls.append(vote_file_url)

        def _add_url(candidate: str) -> bool:
            if not candidate:
                return False

            ok = url_ok_cache.get(candidate)
            if ok is None:
                if args.validate and not _url_is_xml(candidate, timeout=args.validate_timeout):
                    url_ok_cache[candidate] = False
                    return False
                url_ok_cache[candidate] = True
            elif not ok:
                return False

            if candidate in urls:
                return False
            urls.add(candidate)
            return True

        if args.mode == "vote":
            if vote_file_url.startswith("http") and _add_url(vote_file_url):
                continue
            if leg and (session_id is not None) and (vote_id is not None):
                built = _vote_url(host, leg, session_id, vote_id)
                if built:
                    _add_url(_clean_url(built, force_https=force_https))
                continue
        else:
            if leg and session_id is not None:
                session_url = _clean_url(_session_url(host, leg, session_id), force_https=force_https)
                if _add_url(session_url):
                    continue
                for candidate in candidate_urls:
                    if candidate and _add_url(candidate):
                        break
                continue

        # Last-resort fallback: parse session/vote from the vote_event_id url:... if present.
        vote_event_id = _clean_url(str(r["vote_event_id"] or ""), force_https=force_https)
        m = _SENADO_SES_RE.search(vote_event_id)
        if not m:
            continue
        leg = leg or str(m.group("leg") or "").strip()
        ses = _to_int(m.group("ses"))
        vot = _to_int(m.group("vot"))
        if args.mode == "session":
            if leg and ses is not None:
                _add_url(_clean_url(_session_url(host, leg, ses), force_https=force_https))
        else:
            if leg and ses is not None and vot is not None:
                built = _vote_url(host, leg, ses, vot)
                if built:
                    _add_url(_clean_url(built, force_https=force_https))

    for u in sorted(urls):
        if not u:
            continue
        print(u)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
