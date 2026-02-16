from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from etl.politicos_es.db import finish_run, start_run
from etl.politicos_es.util import (
    normalize_key_part,
    normalize_ws,
    now_utc_iso,
    parse_date_flexible,
    sha256_bytes,
    stable_json,
)

from .config import SOURCE_CONFIG
from .connectors.base import BaseConnector
from .db import (
    upsert_parl_initiatives,
    upsert_parl_vote_event,
    upsert_source_record_for_event,
    upsert_source_records,
)


VOTE_SOURCE_TO_MANDATE_SOURCE: dict[str, str] = {
    "congreso_votaciones": "congreso_diputados",
    "senado_votaciones": "senado_senadores",
}


def _load_person_map_for_mandate_source(conn: sqlite3.Connection, mandate_source_id: str) -> dict[str, int]:
    # Best-effort mapping by active mandates in the same institution/source.
    rows = conn.execute(
        """
        SELECT DISTINCT p.person_id, p.full_name
        FROM persons p
        JOIN mandates m ON m.person_id = p.person_id
        WHERE m.source_id = ? AND m.is_active = 1
        """,
        (mandate_source_id,),
    ).fetchall()
    mapping: dict[str, int] = {}
    for r in rows:
        key = normalize_key_part(str(r["full_name"] or ""))
        if not key:
            continue
        mapping[key] = int(r["person_id"])
    return mapping


def _normalize_mandate_date(value: str | None) -> str | None:
    return parse_date_flexible(str(value).strip()) if str(value).strip() else None


def _normalize_group_key(value: str | None) -> str | None:
    return normalize_key_part(str(value or "")) or None


def _vote_date_in_mandate_window(vote_date: str | None, start_date: str | None, end_date: str | None) -> bool:
    if not vote_date:
        return False
    if start_date and vote_date < start_date:
        return False
    if end_date and vote_date > end_date:
        return False
    return True


def _candidate_match_key(
    candidate: dict[str, Any],
    *,
    vote_date_norm: str | None,
    group_norm: str | None,
) -> tuple[int, int, int, int, int, str, str]:
    in_window = _vote_date_in_mandate_window(
        vote_date_norm,
        str(candidate.get("start_date") or ""),
        str(candidate.get("end_date") or ""),
    )
    group_match = 1 if group_norm and group_norm in candidate.get("party_keys", set()) else 0
    has_dates = 1 if (candidate.get("start_date") or candidate.get("end_date")) else 0
    has_territory = 1 if str(candidate.get("person_territory_code") or "").strip() else 0
    return (
        1 if in_window else 0,
        group_match,
        has_dates,
        has_territory,
        1 if int(candidate.get("is_active") or 0) == 1 else 0,
        str(candidate.get("end_date") or "9999-12-31"),
        str(candidate.get("start_date") or "0000-01-01"),
    )


def _pick_best_person_id(
    candidates: list[dict[str, Any]],
    *,
    vote_date_norm: str | None,
    group_norm: str | None,
) -> tuple[int | None, str]:
    if not candidates:
        return None, "no_candidates"

    best_by_person: dict[int, tuple[int, int, int, int, int, str, str]] = {}
    for candidate in candidates:
        key = _candidate_match_key(
            candidate,
            vote_date_norm=vote_date_norm,
            group_norm=group_norm,
        )
        pid = int(candidate["person_id"])
        previous = best_by_person.get(pid)
        if previous is None or key > previous:
            best_by_person[pid] = key

    if not best_by_person:
        return None, "no_candidates"

    key_map: dict[tuple[int, int, int, int, int, str, str], list[int]] = {}
    for pid, key in best_by_person.items():
        key_map.setdefault(key, []).append(pid)

    best_key = max(key_map)
    winners = key_map[best_key]
    if len(winners) != 1:
        return None, "ambiguous"
    return winners[0], "matched"


def backfill_vote_member_person_ids(
    conn: sqlite3.Connection,
    *,
    vote_source_ids: tuple[str, ...] | list[str] | None = None,
    dry_run: bool = False,
    batch_size: int = 5000,
    unmatched_sample_limit: int = 0,
) -> dict[str, Any]:
    requested = list(vote_source_ids or VOTE_SOURCE_TO_MANDATE_SOURCE.keys())
    seen: list[str] = []
    for raw_id in requested:
        sid = normalize_ws(str(raw_id))
        if not sid or sid in seen:
            continue
        seen.append(sid)

    if not seen:
        return {
            "source_ids": [],
            "dry_run": bool(dry_run),
            "total_checked": 0,
            "total_matched": 0,
            "total_unmatched": 0,
            "total_ambiguous": 0,
            "total_updated": 0,
            "sources": [],
        }

    source_totals: dict[str, dict[str, int]] = {
        sid: {
            "checked": 0,
            "matched": 0,
            "unmatched": 0,
            "ambiguous": 0,
            "updated": 0,
            "orphan": 0,
            "cleared_orphan": 0,
            "skipped_no_name": 0,
            "no_mandate_map": 0,
            "no_candidates": 0,
        }
        for sid in seen
    }
    unmatched_reason_totals: dict[str, int] = {}
    unmatched_sample: list[dict[str, Any]] = []
    unmatched_samples_left = max(0, int(unmatched_sample_limit))

    source_to_mandate_index: dict[str, tuple[str, dict[str, list[dict[str, Any]]]]] = {}
    for sid in seen:
        mandate_sid = VOTE_SOURCE_TO_MANDATE_SOURCE.get(sid)
        if not mandate_sid:
            continue
        source_to_mandate_index[sid] = (mandate_sid, _load_mandate_name_index(conn, mandate_sid))

    placeholders = ",".join("?" for _ in seen)
    cur = conn.execute(
        f"""
        SELECT mv.member_vote_id, mv.source_id, mv.member_name_normalized, mv.member_name,
               mv.group_code, e.legislature, e.vote_date, mv.vote_event_id,
               mv.person_id AS current_person_id,
               CASE WHEN mv.person_id IS NOT NULL AND p.person_id IS NULL THEN 1 ELSE 0 END AS is_orphan
        FROM parl_vote_member_votes mv
        JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
        LEFT JOIN persons p ON p.person_id = mv.person_id
        WHERE mv.source_id IN ({placeholders})
          AND (mv.person_id IS NULL OR p.person_id IS NULL)
        ORDER BY mv.source_id, mv.member_vote_id
        """,
        tuple(seen),
    )

    updates: list[tuple[int | None, int, str]] = []
    total_checked = 0
    total_matched = 0
    total_unmatched = 0
    total_ambiguous = 0
    total_updated = 0

    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break

        for row in rows:
            sid = str(row["source_id"])
            source_stat = source_totals.setdefault(
                sid,
                {
                    "checked": 0,
                    "matched": 0,
                    "unmatched": 0,
                    "ambiguous": 0,
                    "updated": 0,
                    "orphan": 0,
                    "cleared_orphan": 0,
                    "skipped_no_name": 0,
                    "no_mandate_map": 0,
                    "no_candidates": 0,
                },
            )
            reason: str | None = None
            is_orphan = bool(int(row["is_orphan"] or 0))
            if is_orphan:
                source_stat["orphan"] += 1

            total_checked += 1
            source_stat["checked"] += 1

            mapping = source_to_mandate_index.get(sid)
            person_id: int | None = None
            if mapping is None:
                source_stat["no_mandate_map"] += 1
                reason = "no_mandate_map"
            else:
                _, candidates_by_name = mapping
                name_key = normalize_key_part(
                    str(row["member_name_normalized"] or row["member_name"] or "")
                )
                if not name_key:
                    source_stat["skipped_no_name"] += 1
                    reason = "skipped_no_name"
                else:
                    candidates = candidates_by_name.get(name_key, [])
                    if not candidates:
                        source_stat["no_candidates"] += 1
                        reason = "no_candidates"
                    else:
                        person_id, status = _pick_best_person_id(
                            candidates,
                            vote_date_norm=_normalize_mandate_date(str(row["vote_date"] or "")),
                            group_norm=_normalize_group_key(row["group_code"]),
                        )
                        if status != "matched" or person_id is None:
                            reason = status or "not_matched"

            if reason is not None:
                source_stat["unmatched"] += 1
                unmatched_reason_totals[reason] = unmatched_reason_totals.get(reason, 0) + 1
                if reason == "ambiguous":
                    source_stat["ambiguous"] += 1
                    total_ambiguous += 1
                if is_orphan:
                    # Keep DB consistent: if we have a dangling FK to persons, clear it even when
                    # we can't rematch right now (best-effort).
                    source_stat["cleared_orphan"] += 1
                    if dry_run:
                        source_stat["updated"] += 1
                        total_updated += 1
                    else:
                        updates.append((None, int(row["member_vote_id"]), sid))
                if (
                    unmatched_samples_left > 0
                    and len(unmatched_sample) < unmatched_samples_left
                ):
                    unmatched_sample.append(
                        {
                            "member_vote_id": int(row["member_vote_id"]),
                            "vote_event_id": str(row["vote_event_id"]),
                            "source_id": sid,
                            "reason": reason,
                            "member_name": str(row["member_name"] or ""),
                            "member_name_normalized": str(row["member_name_normalized"] or ""),
                            "group_code": str(row["group_code"] or ""),
                            "vote_date": str(row["vote_date"] or ""),
                        }
                    )
                continue

            total_matched += 1
            source_stat["matched"] += 1

            if dry_run:
                source_stat["updated"] += 1
                total_updated += 1
            else:
                updates.append((person_id, int(row["member_vote_id"]), sid))

        if not dry_run and updates:
            conn.executemany(
                """
                UPDATE parl_vote_member_votes
                SET person_id = ?
                WHERE member_vote_id = ?
                """,
                [(person_id, member_vote_id) for person_id, member_vote_id, _ in updates],
            )
            total_updated += len(updates)
            for _, _, sid in updates:
                if sid in source_totals:
                    source_totals[sid]["updated"] += 1
            updates = []

    if not dry_run and updates:
        conn.executemany(
            """
            UPDATE parl_vote_member_votes
            SET person_id = ?
            WHERE member_vote_id = ?
            """,
            [(person_id, member_vote_id) for person_id, member_vote_id, _ in updates],
        )
        total_updated += len(updates)
        for _, _, sid in updates:
            if sid in source_totals:
                source_totals[sid]["updated"] += 1

    if not dry_run:
        conn.commit()

    total_unmatched = 0
    sources_out: list[dict[str, Any]] = []
    for sid in seen:
        source_total = source_totals[sid]
        source_total["source_id"] = sid
        source_total["mandate_source_id"] = VOTE_SOURCE_TO_MANDATE_SOURCE.get(sid)
        total_unmatched += source_total["unmatched"]
        sources_out.append(source_total)

    return {
        "source_ids": [str(sid) for sid in seen],
        "dry_run": bool(dry_run),
        "total_checked": int(total_checked),
        "total_matched": int(total_matched),
        "total_unmatched": int(total_unmatched),
        "total_ambiguous": int(total_ambiguous),
        "total_updated": int(total_updated),
        "unmatched_by_reason": {reason: int(count) for reason, count in sorted(unmatched_reason_totals.items())},
        "unmatched_sample": unmatched_sample,
        "sources": sources_out,
    }


def backfill_senado_vote_details(
    conn: sqlite3.Connection,
    *,
    timeout: int,
    snapshot_date: str | None,
    limit: int | None = None,
    include_existing: bool = False,
    only_reingest_when_member_votes: bool = False,
    legislature_filter: tuple[str, ...] | list[str] | None = None,
    vote_event_ids: tuple[str, ...] | list[str] | None = None,
    vote_event_min: str | None = None,
    senado_detail_dir: str | None = None,
    senado_detail_host: str | None = None,
    senado_detail_cookie: str | None = None,
    senado_skip_details: bool = False,
    dry_run: bool = False,
    detail_workers: int = 1,
) -> dict[str, Any]:
    if limit is not None and limit <= 0:
        raise ValueError("max-events debe ser > 0")

    selected_legislatures: list[str] = []
    seen_legislatures: set[str] = set()
    for value in legislature_filter or ():
        txt = normalize_ws(str(value))
        if not txt or txt in seen_legislatures:
            continue
        seen_legislatures.add(txt)
        selected_legislatures.append(txt)

    selected_event_ids: list[str] = []
    seen_event_ids: set[str] = set()
    for value in vote_event_ids or ():
        txt = normalize_ws(str(value))
        if not txt or txt in seen_event_ids:
            continue
        seen_event_ids.add(txt)
        selected_event_ids.append(txt)

    query = """
    SELECT e.vote_event_id, e.legislature, sr.raw_payload
    FROM parl_vote_events e
    LEFT JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
    WHERE e.source_id = 'senado_votaciones'
    """
    if not bool(include_existing):
        query += """
          AND NOT EXISTS (
            SELECT 1 FROM parl_vote_member_votes mv
            WHERE mv.vote_event_id = e.vote_event_id
          )
        """
    params: list[Any] = []
    if vote_event_min is not None:
        query += " AND e.vote_event_id > ?"
        params.append(vote_event_min)
    if selected_legislatures:
        placeholders = ",".join("?" for _ in selected_legislatures)
        query += f" AND e.legislature IN ({placeholders})"
        params.extend(selected_legislatures)
    if selected_event_ids:
        placeholders = ",".join("?" for _ in selected_event_ids)
        query += f" AND e.vote_event_id IN ({placeholders})"
        params.extend(selected_event_ids)

    rows = conn.execute((query + " ORDER BY e.vote_event_id"), tuple(params)).fetchall()
    if limit is not None:
        rows = rows[:int(limit)]
    last_vote_event_id = rows[-1]["vote_event_id"] if rows else None

    if senado_skip_details:
        # Preserve existing payload as-is if detail enrichment is disabled.
        records = [{"payload": _parse_raw_payload(r["raw_payload"]), "legislature": r["legislature"]} for r in rows]
        records_with_votes = [r for r in records if isinstance(r.get("payload"), dict) and r["payload"].get("member_votes")]
        return {
            "source_id": "senado_votaciones",
            "dry_run": bool(dry_run),
            "events_considered": len(rows),
            "events_with_payload": len(records),
            "events_without_payload": sum(1 for r in records if not isinstance(r.get("payload"), dict)),
            "events_with_member_votes": len(records_with_votes),
            "events_without_member_votes": len(records) - len(records_with_votes),
            "events_reingested": 0 if dry_run else 0,
            "member_votes_loaded": 0,
            "errors_summary": {},
            "last_vote_event_id": last_vote_event_id,
            "detail_failures": [],
            "would_reingest": 0,
        }

    # Need to enrich records with session detail to recover member votes.
    from .connectors.senado_votaciones import (
        _enrich_senado_record_with_details,
        _load_session_vote_info,
        _session_vote_file_url_candidates,
        _to_int,
    )

    detail_host = normalize_ws(str(senado_detail_host or "https://www.senado.es")) or "https://www.senado.es"
    detail_dir = Path(str(senado_detail_dir)) if senado_detail_dir else None
    detail_failures: list[str] = []
    detail_blocked = False
    session_cache: dict[str, dict[str, Any]] = {}
    rows_to_enrich: list[tuple[Any, dict[str, Any]]] = []
    first_session_urls: dict[str, tuple[int | None, int | None]] = {}

    worker_count = max(1, int(detail_workers or 1))

    for row in rows:
        payload = _parse_raw_payload(row["raw_payload"])
        if not isinstance(payload, dict):
            continue
        rows_to_enrich.append((row, payload))
        leg = normalize_ws(str(payload.get("legislature") or row["legislature"] or "")) or None
        session_id = _to_int(payload.get("session_id"))
        vote_id = _to_int(payload.get("vote_id"))
        vote_file_url = normalize_ws(str(payload.get("vote_file_url") or ""))
        candidate_urls = _session_vote_file_url_candidates(
            detail_host,
            leg,
            session_id,
            vote_id,
            vote_file_url,
        )
        if candidate_urls:
            first_session_urls.setdefault(candidate_urls[0], (session_id, vote_id))

    def _prefetch_session(args: tuple[str, tuple[int | None, int | None]]) -> tuple[str, dict[str, Any]]:
        session_url, ids = args
        session_id, vote_id = ids
        info = _load_session_vote_info(
            session_url,
            timeout=timeout,
            detail_dir=detail_dir,
            session_id=session_id,
            vote_id=vote_id,
            detail_cookie=senado_detail_cookie,
        )
        return session_url, info

    def _enrich_row(row: Any) -> tuple[dict[str, Any] | None, list[str]]:
        row_data, payload = row
        rec = {
            "detail_url": row_data["vote_event_id"],
            "legislature": payload.get("legislature") or row_data["legislature"],
            "payload": payload,
        }
        failures: list[str] = []
        try:
            _enrich_senado_record_with_details(
                rec,
                timeout=timeout,
                session_cache=session_cache,
                detail_dir=detail_dir,
                detail_host=detail_host,
                detail_cookie=senado_detail_cookie,
                detail_failures=failures,
            )
        except Exception as exc:  # noqa: BLE001
            payload_detail = rec.get("payload")
            if isinstance(payload_detail, dict):
                payload_detail["detail_error"] = f"unexpected-enrich-error: {type(exc).__name__}: {exc}"
            failures.append(f"unexpected-enrich-error: {type(exc).__name__}: {exc}")
        return rec, failures

    if first_session_urls:
        prefetch_items = list(first_session_urls.items())
        blocked_error: str | None = None
        probe_budget = min(3, len(prefetch_items))
        probe_403_count = 0
        start_idx = 0
        # Probe a small sample first: treat repeated hard 403 as blocked host.
        for session_url, _ids in prefetch_items[:probe_budget]:
            session_url, info = _prefetch_session((session_url, _ids))
            session_cache[session_url] = info
            err = normalize_ws(str(info.get("error") or ""))
            if err:
                detail_failures.append(f"detail-prefetch {session_url}: {err}")
                if "HTTPError: HTTP Error 403: Forbidden" in err:
                    probe_403_count += 1
                    if blocked_error is None:
                        blocked_error = err
        start_idx = probe_budget

        if blocked_error is not None and probe_403_count >= probe_budget and probe_budget > 0:
            detail_blocked = True
            blocked_error_text = blocked_error
            for session_url, _ids in prefetch_items[start_idx:]:
                session_cache[session_url] = {
                    "ok": False,
                    "votes": [],
                    "error": blocked_error_text,
                    "source": None,
                }
                detail_failures.append(f"detail-prefetch {session_url}: {blocked_error_text}")
        elif worker_count <= 1:
            for item in prefetch_items[start_idx:]:
                session_url, info = _prefetch_session(item)
                session_cache[session_url] = info
                err = normalize_ws(str(info.get("error") or ""))
                if err:
                    detail_failures.append(f"detail-prefetch {session_url}: {err}")
        else:
            remaining = prefetch_items[start_idx:]
            if remaining:
                with ThreadPoolExecutor(max_workers=worker_count) as prefetch_executor:
                    for session_url, info in prefetch_executor.map(_prefetch_session, remaining):
                        session_cache[session_url] = info
                        err = normalize_ws(str(info.get("error") or ""))
                        if err:
                            detail_failures.append(f"detail-prefetch {session_url}: {err}")

    records: list[dict[str, Any]] = []

    if worker_count <= 1:
        for row in rows_to_enrich:
            rec, row_failures = _enrich_row(row)
            if rec is None:
                continue
            records.append(rec)
            detail_failures.extend(row_failures)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for rec, row_failures in executor.map(_enrich_row, rows_to_enrich):
                if rec is None:
                    continue
                records.append(rec)
                detail_failures.extend(row_failures)

    # Re-ingest records when enrichment produced useful fields, even if there is no roll-call.
    # Many Senado votes are "Por asentimiento" (no member list), but the session XML still provides
    # a vote date and sometimes totals; we want those columns updated in `parl_vote_events`.
    records_with_votes = [r for r in records if isinstance(r.get("payload"), dict) and r["payload"].get("member_votes")]
    records_to_reingest: list[dict[str, Any]] = []
    if bool(only_reingest_when_member_votes):
        records_to_reingest = list(records_with_votes)
    else:
        for r in records:
            payload = r.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("member_votes"):
                records_to_reingest.append(r)
                continue
            if payload.get("vote_date"):
                records_to_reingest.append(r)
                continue
            if (
                payload.get("totals_present") is not None
                or payload.get("totals_yes") is not None
                or payload.get("totals_no") is not None
                or payload.get("totals_abstain") is not None
                or payload.get("totals_no_vote") is not None
            ):
                records_to_reingest.append(r)

    events_by_error: dict[str, int] = {}
    for rec in records_with_votes:
        payload = rec.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        err = normalize_ws(str(payload.get("detail_error") or ""))
        if err:
            events_by_error[err] = events_by_error.get(err, 0) + 1

    if dry_run:
        return {
            "source_id": "senado_votaciones",
            "dry_run": True,
            "events_considered": len(rows),
            "detail_blocked": bool(detail_blocked),
            "events_with_payload": len(records),
            "events_without_payload": len(rows) - len(records),
            "events_with_member_votes": len(records_with_votes),
            "events_without_member_votes": len(records) - len(records_with_votes),
            "events_reingested": 0,
            "member_votes_loaded": 0,
            "errors_summary": {k: int(v) for k, v in sorted(events_by_error.items())},
            "last_vote_event_id": last_vote_event_id,
            "detail_failures": sorted(set(detail_failures)),
            "would_reingest": len(records_to_reingest),
        }

    if not records_to_reingest:
        return {
            "source_id": "senado_votaciones",
            "dry_run": False,
            "events_considered": len(rows),
            "detail_blocked": bool(detail_blocked),
            "events_with_payload": len(records),
            "events_without_payload": len(rows) - len(records),
            "events_with_member_votes": 0,
            "events_without_member_votes": len(records),
            "events_reingested": 0,
            "member_votes_loaded": 0,
            "errors_summary": {k: int(v) for k, v in sorted(events_by_error.items())},
            "last_vote_event_id": last_vote_event_id,
            "detail_failures": sorted(set(detail_failures)),
            "would_reingest": 0,
        }

    now_iso = now_utc_iso()
    _, events_reingested, member_votes_loaded = _ingest_senado_votaciones(
        conn,
        extracted_records=records_to_reingest,
        source_id="senado_votaciones",
        snapshot_date=snapshot_date,
        now_iso=now_iso,
    )
    conn.commit()

    return {
        "source_id": "senado_votaciones",
        "dry_run": False,
        "events_considered": len(rows),
        "detail_blocked": bool(detail_blocked),
        "events_with_payload": len(records),
        "events_without_payload": len(rows) - len(records),
        "events_with_member_votes": len(records_with_votes),
        "events_without_member_votes": len(records) - len(records_with_votes),
        "events_reingested": int(events_reingested),
        "member_votes_loaded": int(member_votes_loaded),
        "errors_summary": {k: int(v) for k, v in sorted(events_by_error.items())},
        "last_vote_event_id": last_vote_event_id,
        "detail_failures": sorted(set(detail_failures)),
    }


def _parse_raw_payload(raw_payload: Any) -> dict[str, Any] | None:
    if not raw_payload:
        return None
    if isinstance(raw_payload, dict):
        return raw_payload
    try:
        parsed = json.loads(str(raw_payload))
    except Exception:  # noqa: BLE001
        return None
    return parsed if isinstance(parsed, dict) else None


def _load_mandate_name_index(
    conn: sqlite3.Connection,
    mandate_source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT m.person_id, p.full_name, p.given_name, p.family_name,
               p.territory_code AS person_territory_code,
               m.is_active,
               m.start_date, m.end_date,
               par.name AS party_name,
               par.acronym AS party_acronym,
               pa.canonical_alias AS party_alias
        FROM mandates m
        JOIN persons p ON p.person_id = m.person_id
        LEFT JOIN parties par ON par.party_id = m.party_id
        LEFT JOIN party_aliases pa ON pa.party_id = m.party_id
        WHERE m.source_id = ?
        """,
        (mandate_source_id,),
    ).fetchall()

    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    candidate_by_term: dict[tuple[int, str, str], dict[str, Any]] = {}
    for r in rows:
        person_id = int(r["person_id"])
        start_date = _normalize_mandate_date(str(r["start_date"] or ""))
        end_date = _normalize_mandate_date(str(r["end_date"] or ""))
        term_key = (person_id, start_date or "", end_date or "")
        person = candidate_by_term.get(term_key)
        if person is None:
            names: set[str] = {
                normalize_key_part(str(r["full_name"] or "")),
                normalize_key_part(str(r["given_name"] or "")),
                normalize_key_part(str(r["family_name"] or "")),
            }
            given = normalize_ws(str(r["given_name"] or "")).strip()
            family = normalize_ws(str(r["family_name"] or "")).strip()
            if given and family:
                names.add(normalize_key_part(f"{given} {family}"))
                names.add(normalize_key_part(f"{family} {given}"))

            person = {
                "person_id": person_id,
                "is_active": 1 if int(r["is_active"] or 0) == 1 else 0,
                "start_date": start_date,
                "end_date": end_date,
                "person_territory_code": normalize_ws(str(r["person_territory_code"] or "")).strip(),
                "party_keys": set[str](),
            }
            candidate_by_term[term_key] = person
            for name in names:
                if not name:
                    continue
                index[name].append(person)

        for value in (
            str(r["party_name"] or ""),
            str(r["party_acronym"] or ""),
            str(r["party_alias"] or ""),
        ):
            key = normalize_key_part(str(value).strip())
            if key:
                person["party_keys"].add(key)
    return index


def _normalize_vote_member_name(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    text = normalize_ws(str(raw))
    if not text:
        return None, None
    if "," in text:
        family, given = [normalize_ws(p) for p in text.split(",", 1)]
        full = normalize_ws(f"{given} {family}")
    else:
        full = text
    return full, normalize_key_part(full)


def _congreso_leg_num(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"(\d+)", str(value))
    return m.group(1) if m else None


def _urls_to_json_list(text: str | None) -> str | None:
    if not text:
        return None
    urls = re.findall(r"https?://\\S+", str(text))
    urls = [u.strip() for u in urls if u.strip()]
    if not urls:
        return None
    return stable_json(urls)


def _urls_to_json_values(values: list[str | None]) -> str | None:
    urls: list[str] = []
    for value in values:
        txt = normalize_ws(str(value or ""))
        if not txt or not txt.startswith("http"):
            continue
        urls.append(txt)
    if not urls:
        return None
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return stable_json(deduped)


def _parse_congreso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parse_date_flexible(normalize_ws(str(value)))
    except Exception:  # noqa: BLE001
        return None


def _split_trailing_parenthetical(text: str) -> tuple[str, str | None]:
    """Split 'Name (Group)' while supporting nested parentheses in the group.

    Examples:
    - 'Foo, Bar (GP)' -> ('Foo, Bar', 'GP')
    - 'Foo, Bar (GV (EAJ-PNV))' -> ('Foo, Bar', 'GV (EAJ-PNV)')
    """
    s = normalize_ws(text)
    if not s.endswith(")"):
        return s, None
    depth = 0
    for i in range(len(s) - 1, -1, -1):
        ch = s[i]
        if ch == ")":
            depth += 1
            continue
        if ch == "(":
            depth -= 1
            if depth == 0:
                name = s[:i].rstrip()
                grp = s[i + 1 : -1].strip()
                if name and grp:
                    return name, grp
                break
    return s, None


def _normalize_orador(raw: str | None) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (full_name, name_key, group_raw, group_key)."""
    if not raw:
        return None, None, None, None
    text = normalize_ws(str(raw))
    if not text:
        return None, None, None, None
    base, grp = _split_trailing_parenthetical(text)
    full, name_key = _normalize_vote_member_name(base)
    grp_key = normalize_key_part(grp) if grp else None
    return full, name_key, grp, grp_key


def _ingest_congreso_iniciativas(
    conn: sqlite3.Connection,
    *,
    extracted_records: list[dict[str, Any]],
    source_id: str,
    snapshot_date: str | None,
    now_iso: str,
) -> tuple[int, int]:
    # Each extracted record is one initiative row from an export list.
    seen = 0
    loaded = 0

    upsert_rows: list[dict[str, Any]] = []
    sr_rows: list[dict[str, Any]] = []
    for rec in extracted_records:
        seen += 1
        item = rec.get("payload") or {}
        if not isinstance(item, dict):
            continue

        category = normalize_ws(str(rec.get("category") or "")) or None
        raw_payload = stable_json(item)

        initiative_id: str | None = None
        leg: str | None = None
        expediente: str | None = None
        title: str | None = None
        type_text: str | None = None

        # Shape A: general initiatives exports (have stable expediente).
        leg = _congreso_leg_num(item.get("LEGISLATURA"))
        expediente = normalize_ws(str(item.get("NUMEXPEDIENTE") or "")) or None
        if leg and expediente:
            initiative_id = f"congreso:leg{leg}:exp:{expediente}"
            title = normalize_ws(str(item.get("OBJETO") or "")) or None
            type_text = normalize_ws(str(item.get("TIPO") or "")) or None

        # Shape B: approved laws export (no expediente/legislature).
        if initiative_id is None and (item.get("TITULO_LEY") or item.get("NUMERO_LEY")):
            title = normalize_ws(str(item.get("TITULO_LEY") or "")) or None
            type_text = normalize_ws(str(item.get("TIPO") or "")) or None
            num = normalize_ws(str(item.get("NUMERO_LEY") or "")) or None
            year = None
            m = re.search(r"\\bLey\\s+(\\d{1,4})/(\\d{4})\\b", title or "")
            if m:
                num = num or m.group(1)
                year = m.group(2)
            if year is None:
                iso = _parse_congreso_date(item.get("FECHA_LEY"))
                if iso:
                    year = iso[:4]
            if num and year:
                expediente = f"ley:{num}/{year}"
                initiative_id = f"congreso:ley:{num}:{year}"
            else:
                initiative_id = f"congreso:ley:{sha256_bytes(raw_payload.encode('utf-8'))[:24]}"

        # Shape C: unknown export row; ingest anyway but keep an explicit hash-derived id.
        if initiative_id is None:
            type_text = normalize_ws(str(item.get("TIPO") or "")) or None
            title = (
                normalize_ws(str(item.get("OBJETO") or item.get("TITULO") or item.get("TITULO_LEY") or "")) or None
            )
            initiative_id = f"congreso:init:{sha256_bytes(raw_payload.encode('utf-8'))[:24]}"

        sr_rows.append({"source_record_id": initiative_id, "raw_payload": raw_payload})

        upsert_rows.append(
            {
                "initiative_id": initiative_id,
                "legislature": leg,
                "expediente": expediente,
                "supertype": normalize_ws(str(item.get("SUPERTIPO") or "")) or None,
                # Keep the OpenData export group visible even if the row lacks a domain-specific grouping.
                "grouping": normalize_ws(str(item.get("AGRUPACION") or "")) or category,
                "type": type_text,
                "title": title,
                "presented_date": _parse_congreso_date(item.get("FECHAPRESENTACION")),
                "qualified_date": _parse_congreso_date(item.get("FECHACALIFICACION")),
                "author_text": normalize_ws(str(item.get("AUTOR") or "")) or None,
                "procedure_type": normalize_ws(str(item.get("TIPOTRAMITACION") or "")) or None,
                "result_text": normalize_ws(str(item.get("RESULTADOTRAMITACION") or "")) or None,
                "current_status": normalize_ws(str(item.get("SITUACIONACTUAL") or "")) or None,
                "competent_committee": normalize_ws(str(item.get("COMISIONCOMPETENTE") or "")) or None,
                "deadlines_text": normalize_ws(str(item.get("PLAZOS") or "")) or None,
                "rapporteurs_text": normalize_ws(str(item.get("PONENTES") or "")) or None,
                "processing_text": normalize_ws(str(item.get("TRAMITACIONSEGUIDA") or "")) or None,
                "related_initiatives_text": normalize_ws(str(item.get("INICIATIVASRELACIONADAS") or "")) or None,
                "links_bocg_json": _urls_to_json_list(item.get("ENLACESBOCG") or item.get("PDF")),
                "links_ds_json": _urls_to_json_list(item.get("ENLACESDS")),
                "source_id": source_id,
                "source_url": str(rec.get("list_url") or "") or None,
                "source_record_pk": None,  # filled below
                "source_snapshot_date": snapshot_date,
                "raw_payload": raw_payload,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    pk_map = upsert_source_records(conn, source_id=source_id, rows=sr_rows, snapshot_date=snapshot_date, now_iso=now_iso)
    for row in upsert_rows:
        row["source_record_pk"] = pk_map.get(row["initiative_id"])

    upsert_parl_initiatives(conn, source_id=source_id, rows=upsert_rows)
    loaded = len(upsert_rows)
    return seen, loaded


def _resolve_congreso_topic_set(
    conn: sqlite3.Connection,
    *,
    legislature: str,
) -> tuple[int, int | None, int | None, int | None] | None:
    """Return (topic_set_id, institution_id, admin_level_id, territory_id) for Congreso/leg."""
    row = conn.execute(
        """
        SELECT ts.topic_set_id, ts.institution_id, ts.admin_level_id, ts.territory_id
        FROM topic_sets ts
        JOIN institutions i ON i.institution_id = ts.institution_id
        WHERE i.name = 'Congreso de los Diputados'
          AND ts.legislature = ?
        ORDER BY ts.is_active DESC, ts.topic_set_id DESC
        LIMIT 1
        """,
        (legislature,),
    ).fetchone()
    if not row:
        return None
    return (
        int(row["topic_set_id"]),
        int(row["institution_id"]) if row["institution_id"] is not None else None,
        int(row["admin_level_id"]) if row["admin_level_id"] is not None else None,
        int(row["territory_id"]) if row["territory_id"] is not None else None,
    )


def _topic_id_map_for_set(conn: sqlite3.Connection, *, topic_set_id: int) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT t.canonical_key, t.topic_id
        FROM topic_set_topics st
        JOIN topics t ON t.topic_id = st.topic_id
        WHERE st.topic_set_id = ?
        """,
        (int(topic_set_id),),
    ).fetchall()
    out: dict[str, int] = {}
    for r in rows:
        key = normalize_ws(str(r["canonical_key"] or ""))
        if not key:
            continue
        out[key] = int(r["topic_id"])
    return out


def _ingest_congreso_intervenciones(
    conn: sqlite3.Connection,
    *,
    extracted_records: list[dict[str, Any]],
    source_id: str,
    snapshot_date: str | None,
    now_iso: str,
) -> tuple[int, int, dict[str, Any]]:
    """Materialize 'says' evidence rows from Congreso interventions OpenData.

    Contract: we only attach interventions to topics that are already present in an existing Congreso topic_set
    (typically built via backfill-topic-analytics). This keeps Explorer navigation stable and avoids flooding
    topic_set_topics beyond UI limits.
    """
    seen = 0
    inserted = 0

    skip: dict[str, int] = {
        "bad_payload": 0,
        "no_leg": 0,
        "no_expediente": 0,
        "no_topic_set": 0,
        "topic_not_in_set": 0,
        "no_orador": 0,
        "no_person_match": 0,
    }

    # Discover legislatures in payloads (usually only Leg.15).
    legs: list[str] = []
    seen_legs: set[str] = set()
    for rec in extracted_records:
        payload = rec.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        leg = _congreso_leg_num(payload.get("LEGISLATURA"))
        if not leg or leg in seen_legs:
            continue
        seen_legs.add(leg)
        legs.append(leg)

    leg_to_set: dict[str, tuple[int, int | None, int | None, int | None]] = {}
    leg_to_topic_id: dict[str, dict[str, int]] = {}
    for leg in legs:
        resolved = _resolve_congreso_topic_set(conn, legislature=str(leg))
        if not resolved:
            continue
        topic_set_id, inst_id, admin_id, terr_id = resolved
        leg_to_set[str(leg)] = (topic_set_id, inst_id, admin_id, terr_id)
        leg_to_topic_id[str(leg)] = _topic_id_map_for_set(conn, topic_set_id=topic_set_id)

    mandate_index = _load_mandate_name_index(conn, "congreso_diputados")

    evidence_type = "declared:intervention"
    sr_payload_by_id: dict[str, str] = {}
    ev_by_id: dict[str, dict[str, Any]] = {}

    for rec in extracted_records:
        seen += 1
        payload = rec.get("payload") or {}
        if not isinstance(payload, dict):
            skip["bad_payload"] += 1
            continue

        leg = _congreso_leg_num(payload.get("LEGISLATURA"))
        if not leg:
            skip["no_leg"] += 1
            continue

        ts_info = leg_to_set.get(str(leg))
        if not ts_info:
            skip["no_topic_set"] += 1
            continue
        topic_set_id, institution_id, admin_level_id, territory_id = ts_info

        expediente = normalize_ws(str(payload.get("NUMEXPEDIENTE") or "")) or None
        if not expediente:
            skip["no_expediente"] += 1
            continue

        initiative_id = f"congreso:leg{leg}:exp:{expediente}"
        topic_id = leg_to_topic_id.get(str(leg), {}).get(initiative_id)
        if not topic_id:
            skip["topic_not_in_set"] += 1
            continue

        session_date = _parse_congreso_date(payload.get("SESION"))

        orador_full, orador_key, orador_group, orador_group_key = _normalize_orador(payload.get("ORADOR"))
        if not orador_key:
            skip["no_orador"] += 1
            continue
        candidates = mandate_index.get(orador_key, [])
        person_id, _reason = _pick_best_person_id(
            candidates,
            vote_date_norm=session_date,
            group_norm=orador_group_key,
        )
        if person_id is None:
            skip["no_person_match"] += 1
            continue

        enlace_diferido = normalize_ws(str(payload.get("ENLACEDIFERIDO") or "")) or None
        interv_id = enlace_diferido.rsplit("/", 1)[-1] if enlace_diferido else None
        if not interv_id:
            interv_id = sha256_bytes(stable_json(payload).encode("utf-8"))[:24]

        source_record_id = f"congreso:interv:{interv_id}:leg{leg}:exp:{expediente}"
        sr_payload_by_id[source_record_id] = stable_json(payload)

        source_url = (
            normalize_ws(str(payload.get("ENLACETEXTOINTEGRO") or "")) or None
        ) or (normalize_ws(str(payload.get("ENLACEPDF") or "")) or None) or enlace_diferido

        start = normalize_ws(str(payload.get("INICIOINTERVENCION") or "")) or None
        end = normalize_ws(str(payload.get("FININTERVENCION") or "")) or None
        organo = normalize_ws(str(payload.get("ORGANO") or "")) or None
        fase = normalize_ws(str(payload.get("FASE") or "")) or None
        tipo = normalize_ws(str(payload.get("TIPOINTERVENCION") or "")) or None

        excerpt_bits: list[str] = []
        if orador_full:
            excerpt_bits.append(orador_full)
        elif payload.get("ORADOR"):
            excerpt_bits.append(normalize_ws(str(payload.get("ORADOR"))))
        if orador_group:
            excerpt_bits.append(f"({orador_group})")
        if organo:
            excerpt_bits.append(organo)
        if tipo:
            excerpt_bits.append(tipo)
        if fase:
            excerpt_bits.append(f"fase:{fase}")
        if start or end:
            excerpt_bits.append(f"{start or ''}-{end or ''}".strip("-"))
        excerpt = " | ".join([b for b in excerpt_bits if b])

        ev_raw_payload = stable_json(
            {
                "intervencion_id": interv_id,
                "initiative_id": initiative_id,
                "numexpediente": expediente,
                "session_date": session_date,
                "start": start,
                "end": end,
                "orador_raw": normalize_ws(str(payload.get("ORADOR") or "")) or None,
                "orador_name": orador_full,
                "orador_group": orador_group,
                "organo": organo,
                "fase": fase,
                "tipo": tipo,
                "enlace_pdf": normalize_ws(str(payload.get("ENLACEPDF") or "")) or None,
                "enlace_texto_integro": normalize_ws(str(payload.get("ENLACETEXTOINTEGRO") or "")) or None,
                "enlace_diferido": enlace_diferido,
                "enlace_video": normalize_ws(str(payload.get("ENLACEDESCARGADIRECTA") or "")) or None,
            }
        )

        title = normalize_ws(str(payload.get("OBJETOINICIATIVA") or "")) or None
        ev_by_id[source_record_id] = {
            "topic_id": int(topic_id),
            "topic_set_id": int(topic_set_id),
            "person_id": int(person_id),
            "institution_id": int(institution_id) if institution_id is not None else None,
            "admin_level_id": int(admin_level_id) if admin_level_id is not None else None,
            "territory_id": int(territory_id) if territory_id is not None else None,
            "evidence_type": evidence_type,
            "evidence_date": session_date,
            "title": title,
            "excerpt": excerpt,
            # No stance classification yet; keep a neutral signal so the UI counts it as "says".
            "stance": "unclear",
            "polarity": 0,
            "weight": 0.5,
            "confidence": 0.2,
            "topic_method": "initiative:expediente",
            "stance_method": "intervention_metadata",
            "initiative_id": initiative_id,
            "source_url": source_url,
            "source_record_id": source_record_id,
            "raw_payload": ev_raw_payload,
        }

    evidence_rows = list(ev_by_id.values())
    if not evidence_rows:
        return seen, 0, {"skipped": skip, "evidence_type": evidence_type, "topic_sets": sorted(set(leg_to_set.keys()))}

    # Idempotence: rebuild evidence for this source + each touched topic_set.
    touched_set_ids = sorted({int(r["topic_set_id"]) for r in evidence_rows})

    with conn:
        for set_id in touched_set_ids:
            conn.execute(
                """
                DELETE FROM topic_evidence
                WHERE source_id = ?
                  AND topic_set_id = ?
                  AND evidence_type = ?
                """,
                (source_id, int(set_id), evidence_type),
            )

        sr_rows = [{"source_record_id": sid, "raw_payload": raw} for sid, raw in sr_payload_by_id.items()]
        pk_map = upsert_source_records(conn, source_id=source_id, rows=sr_rows, snapshot_date=snapshot_date, now_iso=now_iso)

        # If we already fetched Diario excerpts for some interventions, surface them in topic_evidence.excerpt.
        # This keeps /explorer-temas auditable without extra joins or N+1 calls.
        text_excerpt_by_pk: dict[int, str] = {}
        sr_pks = sorted({int(pk) for pk in pk_map.values() if pk is not None})
        if sr_pks:
            chunk = 400
            for i in range(0, len(sr_pks), chunk):
                batch = sr_pks[i : i + chunk]
                qmarks = ",".join("?" for _ in batch)
                fetched = conn.execute(
                    f"""
                    SELECT source_record_pk, text_excerpt
                    FROM text_documents
                    WHERE source_id = ?
                      AND source_record_pk IN ({qmarks})
                      AND text_excerpt IS NOT NULL
                      AND TRIM(text_excerpt) <> ''
                    """,
                    (source_id, *batch),
                ).fetchall()
                for row in fetched:
                    try:
                        pk = int(row["source_record_pk"])
                    except Exception:  # noqa: BLE001
                        continue
                    ex = normalize_ws(str(row["text_excerpt"] or ""))
                    if not ex:
                        continue
                    text_excerpt_by_pk[pk] = ex

        params: list[tuple[Any, ...]] = []
        for r in evidence_rows:
            sr_pk = pk_map.get(str(r["source_record_id"]))
            if sr_pk is None:
                continue
            excerpt = text_excerpt_by_pk.get(int(sr_pk)) or r.get("excerpt")
            params.append(
                (
                    int(r["topic_id"]),
                    int(r["topic_set_id"]),
                    int(r["person_id"]),
                    None,  # mandate_id
                    r["institution_id"],
                    r["admin_level_id"],
                    r["territory_id"],
                    evidence_type,
                    r.get("evidence_date"),
                    r.get("title"),
                    excerpt[:800] if isinstance(excerpt, str) else excerpt,
                    r.get("stance"),
                    r.get("polarity"),
                    r.get("weight"),
                    r.get("confidence"),
                    r.get("topic_method"),
                    r.get("stance_method"),
                    None,  # vote_event_id
                    r.get("initiative_id"),
                    source_id,
                    r.get("source_url"),
                    int(sr_pk),
                    snapshot_date,
                    r.get("raw_payload") or "{}",
                    now_iso,
                    now_iso,
                )
            )

        conn.executemany(
            """
            INSERT INTO topic_evidence (
              topic_id, topic_set_id,
              person_id, mandate_id,
              institution_id, admin_level_id, territory_id,
              evidence_type, evidence_date, title, excerpt,
              stance, polarity, weight, confidence,
              topic_method, stance_method,
              vote_event_id, initiative_id,
              source_id, source_url, source_record_pk, source_snapshot_date,
              raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params,
        )
        inserted = len(params)

    return seen, inserted, {"skipped": skip, "topic_sets_touched": touched_set_ids, "evidence_type": evidence_type}


def _ingest_senado_iniciativas(
    conn: sqlite3.Connection,
    *,
    extracted_records: list[dict[str, Any]],
    source_id: str,
    snapshot_date: str | None,
    now_iso: str,
) -> tuple[int, int]:
    seen = 0
    loaded = 0

    upsert_rows: list[dict[str, Any]] = []
    sr_rows: list[dict[str, Any]] = []

    for rec in extracted_records:
        seen += 1
        payload = rec.get("payload") or {}
        if not isinstance(payload, dict):
            continue

        raw_payload = stable_json(payload)
        leg = normalize_ws(str(payload.get("legislature") or rec.get("legislature") or "")) or None
        tipo_ex = normalize_ws(str(payload.get("tipo_expediente") or "")) or None
        num_ex = normalize_ws(str(payload.get("numero_expediente") or "")) or None
        expediente = normalize_ws(str(payload.get("expediente") or "")) or None
        if not expediente and tipo_ex and num_ex:
            expediente = f"{tipo_ex}/{num_ex}"

        if leg and expediente:
            initiative_id = f"senado:leg{leg}:exp:{expediente}"
        else:
            initiative_id = f"senado:init:{sha256_bytes(raw_payload.encode('utf-8'))[:24]}"

        sr_rows.append({"source_record_id": initiative_id, "raw_payload": raw_payload})

        title = normalize_ws(str(payload.get("iniciativa_title") or "")) or None
        votes = payload.get("vote_refs") or []
        vote_count = len(votes) if isinstance(votes, list) else 0
        grouping = "Votaciones por iniciativa (Senado)"
        processing_note = f"vote_refs={vote_count}" if vote_count else None

        upsert_rows.append(
            {
                "initiative_id": initiative_id,
                "legislature": leg,
                "expediente": expediente,
                "supertype": None,
                "grouping": grouping,
                "type": tipo_ex,
                "title": title,
                "presented_date": None,
                "qualified_date": None,
                "author_text": None,
                "procedure_type": None,
                "result_text": None,
                "current_status": None,
                "competent_committee": None,
                "deadlines_text": None,
                "rapporteurs_text": None,
                "processing_text": processing_note,
                "related_initiatives_text": None,
                "links_bocg_json": _urls_to_json_values(
                    [
                        payload.get("detail_file_url"),
                        payload.get("enmiendas_file_url"),
                    ]
                ),
                "links_ds_json": _urls_to_json_values(
                    [
                        payload.get("iniciativa_url"),
                        payload.get("enmiendas_url"),
                        payload.get("votaciones_file_url"),
                    ]
                ),
                "source_id": source_id,
                "source_url": str(rec.get("detail_url") or payload.get("source_tipo9_url") or "") or None,
                "source_record_pk": None,
                "source_snapshot_date": snapshot_date,
                "raw_payload": raw_payload,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    pk_map = upsert_source_records(conn, source_id=source_id, rows=sr_rows, snapshot_date=snapshot_date, now_iso=now_iso)
    for row in upsert_rows:
        row["source_record_pk"] = pk_map.get(row["initiative_id"])

    upsert_parl_initiatives(conn, source_id=source_id, rows=upsert_rows)
    loaded = len(upsert_rows)
    return seen, loaded


def _build_senado_vote_event_id(rec: dict[str, Any]) -> str:
    payload = rec.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    vote_file_url = normalize_ws(str(payload.get("vote_file_url") or ""))
    vote_url = normalize_ws(str(payload.get("vote_url") or ""))
    if vote_file_url.startswith("http"):
        return f"url:{vote_file_url}"
    if vote_url.startswith("http"):
        return f"url:{vote_url}"
    fingerprint = stable_json(
        {
            "leg": rec.get("legislature"),
            "tipo": payload.get("tipo_expediente"),
            "num": payload.get("numero_expediente"),
            "session_id": payload.get("session_id"),
            "vote_id": payload.get("vote_id"),
            "title": payload.get("vote_title"),
        }
    )
    return f"senado:vote:{sha256_bytes(fingerprint.encode('utf-8'))[:24]}"


def _ingest_senado_votaciones(
    conn: sqlite3.Connection,
    *,
    extracted_records: list[dict[str, Any]],
    source_id: str,
    snapshot_date: str | None,
    now_iso: str,
) -> tuple[int, int, int]:
    seen = 0
    loaded = 0
    member_votes_loaded = 0
    person_index = _load_mandate_name_index(conn, "senado_senadores")
    for rec in extracted_records:
        seen += 1
        payload = rec.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        vote_event_id = _build_senado_vote_event_id(rec)
        event_payload_json = stable_json(payload)
        source_record_pk = upsert_source_record_for_event(
            conn,
            source_id=source_id,
            source_record_id=vote_event_id,
            snapshot_date=snapshot_date,
            raw_payload=event_payload_json,
            now_iso=now_iso,
        )

        tipo_ex = normalize_ws(str(payload.get("tipo_expediente") or "")) or None
        num_ex = normalize_ws(str(payload.get("numero_expediente") or "")) or None
        expediente = None
        if tipo_ex and num_ex:
            expediente = f"{tipo_ex}/{num_ex}"

        iniciativa_title = normalize_ws(str(payload.get("iniciativa_title") or "")) or None
        expediente_text = iniciativa_title
        if expediente and iniciativa_title and expediente not in iniciativa_title:
            expediente_text = f"{iniciativa_title} ({expediente})"
        elif expediente and not expediente_text:
            expediente_text = expediente

        upsert_parl_vote_event(
            conn,
            vote_event_id=vote_event_id,
            row={
                "legislature": rec.get("legislature"),
                "session_number": payload.get("session_id"),
                "vote_number": payload.get("vote_id"),
                "vote_date": payload.get("vote_date"),
                "title": payload.get("vote_title"),
                "expediente_text": expediente_text,
                "subgroup_title": None,
                "subgroup_text": None,
                "assentimiento": None,
                "totals_present": payload.get("totals_present"),
                "totals_yes": payload.get("totals_yes"),
                "totals_no": payload.get("totals_no"),
                "totals_abstain": payload.get("totals_abstain"),
                "totals_no_vote": payload.get("totals_no_vote"),
            },
            source_id=source_id,
            source_url=normalize_ws(
                str(
                    payload.get("detail_source")
                    or payload.get("session_vote_file_url")
                    or payload.get("source_tipo12_url")
                    or ""
                )
            )
            or str(rec.get("detail_url") or ""),
            source_record_pk=source_record_pk,
            snapshot_date=snapshot_date,
            raw_payload=event_payload_json,
            now_iso=now_iso,
        )
        loaded += 1

        member_votes = payload.get("member_votes") or []
        member_rows: list[tuple[Any, ...]] = []
        vote_date_norm = _normalize_mandate_date(str(payload.get("vote_date") or ""))
        for mv in member_votes:
            if not isinstance(mv, dict):
                continue
            member_name = mv.get("member_name")
            member_full, member_norm = _normalize_vote_member_name(member_name)
            seat_raw = mv.get("seat")
            seat = str(seat_raw) if seat_raw is not None else None
            person_id = None
            if member_norm:
                candidates = person_index.get(member_norm, [])
                if candidates:
                    person_id, status = _pick_best_person_id(
                        candidates,
                        vote_date_norm=vote_date_norm,
                        group_norm=_normalize_group_key(str(mv.get("group") or "")),
                    )
                    if status != "matched" or person_id is None:
                        person_id = None
            if not seat:
                seat = f"name:{member_norm or sha256_bytes((member_full or member_name or '').encode('utf-8'))[:16]}"
            member_rows.append(
                (
                    vote_event_id,
                    seat,
                    member_full,
                    member_norm,
                    person_id,
                    mv.get("group"),
                    mv.get("vote_choice") or "",
                    source_id,
                    str(
                        payload.get("detail_source")
                        or payload.get("session_vote_file_url")
                        or payload.get("source_tipo12_url")
                        or rec.get("detail_url")
                        or ""
                    ),
                    snapshot_date,
                    stable_json(mv),
                    now_iso,
                    now_iso,
                )
            )

        # We intentionally avoid deleting existing member votes here:
        # - Refresh/backfills want to preserve previously resolved `person_id` values.
        # - In partial/failed detail runs (404/no-match/etc.), deleting would wipe previously ingested data.
        # The UPSERT below updates names/choices while keeping old person_id when the new one is NULL.
        if member_rows:
            conn.executemany(
                """
                INSERT INTO parl_vote_member_votes (
                  vote_event_id,
                  seat, member_name, member_name_normalized, person_id,
                  group_code, vote_choice,
                  source_id, source_url, source_snapshot_date,
                  raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(vote_event_id, seat) DO UPDATE SET
                  member_name=excluded.member_name,
                  member_name_normalized=excluded.member_name_normalized,
                  person_id=COALESCE(excluded.person_id, parl_vote_member_votes.person_id),
                  group_code=excluded.group_code,
                  vote_choice=excluded.vote_choice,
                  source_url=COALESCE(excluded.source_url, parl_vote_member_votes.source_url),
                  source_snapshot_date=COALESCE(excluded.source_snapshot_date, parl_vote_member_votes.source_snapshot_date),
                  raw_payload=excluded.raw_payload,
                  updated_at=excluded.updated_at
                """,
                member_rows,
            )
        member_votes_loaded += len(member_rows)

    return seen, loaded, member_votes_loaded


def ingest_one_source(
    conn: sqlite3.Connection,
    connector: BaseConnector,
    raw_dir: Path,
    timeout: int,
    from_file: Path | None,
    url_override: str | None,
    snapshot_date: str | None,
    strict_network: bool,
    options: dict[str, Any] | None = None,
) -> tuple[int, int, str]:
    options = dict(options or {})
    source_id = connector.source_id
    resolved_url = f"file://{from_file.resolve()}" if from_file else connector.resolve_url(url_override, timeout)

    run_id = start_run(conn, source_id, resolved_url)
    try:
        extracted = connector.extract(
            raw_dir=raw_dir,
            timeout=timeout,
            from_file=from_file,
            url_override=url_override,
            strict_network=strict_network,
            options=options,
        )

        # Keep per-run fetch metadata (used by ops dashboards).
        conn.execute(
            """
            INSERT INTO run_fetches (
              run_id, source_id, source_url, fetched_at, raw_path, content_sha256, content_type, bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
              source_id=excluded.source_id,
              source_url=excluded.source_url,
              fetched_at=excluded.fetched_at,
              raw_path=excluded.raw_path,
              content_sha256=excluded.content_sha256,
              content_type=excluded.content_type,
              bytes=excluded.bytes
            """,
            (
                run_id,
                source_id,
                extracted.source_url,
                extracted.fetched_at,
                str(extracted.raw_path),
                extracted.content_sha256,
                extracted.content_type,
                extracted.bytes,
            ),
        )

        conn.execute(
            """
            INSERT INTO raw_fetches (
              run_id, source_id, source_url, fetched_at, raw_path, content_sha256, content_type, bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, content_sha256) DO NOTHING
            """,
            (
                run_id,
                source_id,
                extracted.source_url,
                extracted.fetched_at,
                str(extracted.raw_path),
                extracted.content_sha256,
                extracted.content_type,
                extracted.bytes,
            ),
        )

        person_map: dict[str, int] = {}
        if source_id == "congreso_votaciones":
            person_map = _load_person_map_for_mandate_source(conn, "congreso_diputados")

        now_iso = now_utc_iso()
        events_seen = 0
        events_loaded = 0
        member_votes_loaded = 0

        if source_id == "congreso_iniciativas":
            rec_seen, rec_loaded = _ingest_congreso_iniciativas(
                conn,
                extracted_records=extracted.records,
                source_id=source_id,
                snapshot_date=snapshot_date,
                now_iso=now_iso,
            )
            if strict_network and rec_seen > 0 and rec_loaded == 0:
                raise RuntimeError(
                    "strict-network abortado: records_seen > 0 y records_loaded == 0 "
                    f"({source_id}: seen={rec_seen}, loaded={rec_loaded})"
                )

            min_loaded = SOURCE_CONFIG.get(source_id, {}).get("min_records_loaded_strict")
            if (
                strict_network
                and extracted.note.startswith("network")
                and isinstance(min_loaded, int)
                and rec_loaded < min_loaded
            ):
                raise RuntimeError(
                    f"strict-network abortado: records_loaded < min_records_loaded_strict "
                    f"({source_id}: loaded={rec_loaded}, min={min_loaded})"
                )

            conn.commit()
            message = json.dumps(
                {
                    "note": extracted.note,
                    "initiatives_loaded": rec_loaded,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
            finish_run(
                conn,
                run_id=run_id,
                status="ok",
                message=message,
                records_seen=rec_seen,
                records_loaded=rec_loaded,
                fetched_at=extracted.fetched_at,
                raw_path=extracted.raw_path,
            )
            return rec_seen, rec_loaded, message

        if source_id == "congreso_intervenciones":
            rec_seen, rec_loaded, info = _ingest_congreso_intervenciones(
                conn,
                extracted_records=extracted.records,
                source_id=source_id,
                snapshot_date=snapshot_date,
                now_iso=now_iso,
            )
            if strict_network and rec_seen > 0 and rec_loaded == 0:
                raise RuntimeError(
                    "strict-network abortado: records_seen > 0 y records_loaded == 0 "
                    f"({source_id}: seen={rec_seen}, loaded={rec_loaded})"
                )

            min_loaded = SOURCE_CONFIG.get(source_id, {}).get("min_records_loaded_strict")
            if (
                strict_network
                and extracted.note.startswith("network")
                and isinstance(min_loaded, int)
                and rec_loaded < min_loaded
            ):
                raise RuntimeError(
                    f"strict-network abortado: records_loaded < min_records_loaded_strict "
                    f"({source_id}: loaded={rec_loaded}, min={min_loaded})"
                )

            conn.commit()
            message = json.dumps(
                {
                    "note": extracted.note,
                    "evidence_inserted": rec_loaded,
                    "info": info,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
            finish_run(
                conn,
                run_id=run_id,
                status="ok",
                message=message,
                records_seen=rec_seen,
                records_loaded=rec_loaded,
                fetched_at=extracted.fetched_at,
                raw_path=extracted.raw_path,
            )
            return rec_seen, rec_loaded, message

        if source_id == "senado_iniciativas":
            rec_seen, rec_loaded = _ingest_senado_iniciativas(
                conn,
                extracted_records=extracted.records,
                source_id=source_id,
                snapshot_date=snapshot_date,
                now_iso=now_iso,
            )
            if strict_network and rec_seen > 0 and rec_loaded == 0:
                raise RuntimeError(
                    "strict-network abortado: records_seen > 0 y records_loaded == 0 "
                    f"({source_id}: seen={rec_seen}, loaded={rec_loaded})"
                )

            min_loaded = SOURCE_CONFIG.get(source_id, {}).get("min_records_loaded_strict")
            if (
                strict_network
                and extracted.note.startswith("network")
                and isinstance(min_loaded, int)
                and rec_loaded < min_loaded
            ):
                raise RuntimeError(
                    f"strict-network abortado: records_loaded < min_records_loaded_strict "
                    f"({source_id}: loaded={rec_loaded}, min={min_loaded})"
                )

            conn.commit()
            message = json.dumps(
                {
                    "note": extracted.note,
                    "initiatives_loaded": rec_loaded,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
            finish_run(
                conn,
                run_id=run_id,
                status="ok",
                message=message,
                records_seen=rec_seen,
                records_loaded=rec_loaded,
                fetched_at=extracted.fetched_at,
                raw_path=extracted.raw_path,
            )
            return rec_seen, rec_loaded, message

        if source_id == "senado_votaciones":
            rec_seen, rec_loaded, mv_loaded = _ingest_senado_votaciones(
                conn,
                extracted_records=extracted.records,
                source_id=source_id,
                snapshot_date=snapshot_date,
                now_iso=now_iso,
            )
            if strict_network and rec_seen > 0 and rec_loaded == 0:
                raise RuntimeError(
                    "strict-network abortado: records_seen > 0 y records_loaded == 0 "
                    f"({source_id}: seen={rec_seen}, loaded={rec_loaded})"
                )

            min_loaded = SOURCE_CONFIG.get(source_id, {}).get("min_records_loaded_strict")
            if (
                strict_network
                and extracted.note.startswith("network")
                and isinstance(min_loaded, int)
                and rec_loaded < min_loaded
            ):
                raise RuntimeError(
                    f"strict-network abortado: records_loaded < min_records_loaded_strict "
                    f"({source_id}: loaded={rec_loaded}, min={min_loaded})"
                )

            conn.commit()
            message = json.dumps(
                {
                    "note": extracted.note,
                    "events_loaded": rec_loaded,
                    "member_votes_loaded": mv_loaded,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
            finish_run(
                conn,
                run_id=run_id,
                status="ok",
                message=message,
                records_seen=rec_seen,
                records_loaded=rec_loaded,
                fetched_at=extracted.fetched_at,
                raw_path=extracted.raw_path,
            )
            return rec_seen, rec_loaded, message

        for rec in extracted.records:
            events_seen += 1
            payload = rec.get("payload") or {}
            info = payload.get("informacion") or {}
            totals = payload.get("totales") or {}
            votos = payload.get("votaciones") or []

            detail_url = rec.get("detail_url")
            if detail_url and str(detail_url).startswith("http"):
                vote_event_id = f"url:{detail_url}"
            else:
                fingerprint = stable_json(
                    {
                        "leg": rec.get("legislature"),
                        "ses": info.get("sesion"),
                        "num": info.get("numeroVotacion"),
                        "fecha": info.get("fecha"),
                        "titulo": info.get("titulo"),
                    }
                )
                vote_event_id = f"congreso:vote:{sha256_bytes(fingerprint.encode('utf-8'))[:24]}"

            event_payload_json = stable_json(payload)
            source_record_pk = upsert_source_record_for_event(
                conn,
                source_id=source_id,
                source_record_id=vote_event_id,
                snapshot_date=snapshot_date,
                raw_payload=event_payload_json,
                now_iso=now_iso,
            )

            upsert_parl_vote_event(
                conn,
                vote_event_id=vote_event_id,
                row={
                    "legislature": rec.get("legislature"),
                    "session_number": info.get("sesion"),
                    "vote_number": info.get("numeroVotacion"),
                    "vote_date": rec.get("vote_date"),
                    "title": info.get("titulo"),
                    "expediente_text": info.get("textoExpediente"),
                    "subgroup_title": info.get("tituloSubGrupo"),
                    "subgroup_text": info.get("textoSubGrupo"),
                    "assentimiento": totals.get("asentimiento"),
                    "totals_present": totals.get("presentes"),
                    "totals_yes": totals.get("afavor"),
                    "totals_no": totals.get("enContra"),
                    "totals_abstain": totals.get("abstenciones"),
                    "totals_no_vote": totals.get("noVotan"),
                },
                source_id=source_id,
                source_url=str(detail_url) if detail_url else None,
                source_record_pk=source_record_pk,
                snapshot_date=snapshot_date,
                raw_payload=event_payload_json,
                now_iso=now_iso,
            )
            events_loaded += 1

            # Batch upsert member votes for speed.
            conn.execute("DELETE FROM parl_vote_member_votes WHERE vote_event_id = ?", (vote_event_id,))
            member_rows: list[tuple[Any, ...]] = []
            for v in votos:
                seat_raw = v.get("asiento")
                member_name = v.get("diputado")
                member_full, member_norm = _normalize_vote_member_name(member_name)
                person_id = person_map.get(member_norm or "") if member_norm else None
                seat = str(seat_raw) if seat_raw is not None else None
                # Some vote files use asiento=-1 for multiple members; make the key unique per member.
                if not seat or seat == "-1":
                    seat = f"name:{member_norm or sha256_bytes((member_full or member_name or '').encode('utf-8'))[:16]}"
                member_rows.append(
                    (
                        vote_event_id,
                        seat,
                        member_full,
                        member_norm,
                        person_id,
                        v.get("grupo"),
                        v.get("voto") or "",
                        source_id,
                        str(detail_url) if detail_url else None,
                        snapshot_date,
                        stable_json(v),
                        now_iso,
                        now_iso,
                    )
                )

            conn.executemany(
                """
                INSERT INTO parl_vote_member_votes (
                  vote_event_id,
                  seat, member_name, member_name_normalized, person_id,
                  group_code, vote_choice,
                  source_id, source_url, source_snapshot_date,
                  raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(vote_event_id, seat) DO UPDATE SET
                  member_name=excluded.member_name,
                  member_name_normalized=excluded.member_name_normalized,
                  person_id=COALESCE(excluded.person_id, parl_vote_member_votes.person_id),
                  group_code=excluded.group_code,
                  vote_choice=excluded.vote_choice,
                  source_url=COALESCE(excluded.source_url, parl_vote_member_votes.source_url),
                  source_snapshot_date=COALESCE(excluded.source_snapshot_date, parl_vote_member_votes.source_snapshot_date),
                  raw_payload=excluded.raw_payload,
                  updated_at=excluded.updated_at
                """,
                member_rows,
            )
            member_votes_loaded += len(member_rows)

        if strict_network and events_seen > 0 and events_loaded == 0:
            raise RuntimeError(
                "strict-network abortado: records_seen > 0 y records_loaded == 0 "
                f"({source_id}: seen={events_seen}, loaded={events_loaded})"
            )

        min_loaded = SOURCE_CONFIG.get(source_id, {}).get("min_records_loaded_strict")
        if strict_network and extracted.note.startswith("network") and isinstance(min_loaded, int) and events_loaded < min_loaded:
            raise RuntimeError(
                f"strict-network abortado: records_loaded < min_records_loaded_strict "
                f"({source_id}: loaded={events_loaded}, min={min_loaded})"
            )

        conn.commit()

        message = json.dumps(
            {
                "note": extracted.note,
                "events_loaded": events_loaded,
                "member_votes_loaded": member_votes_loaded,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        finish_run(
            conn,
            run_id=run_id,
            status="ok",
            message=message,
            records_seen=events_seen,
            records_loaded=events_loaded,
            fetched_at=extracted.fetched_at,
            raw_path=extracted.raw_path,
        )
        return events_seen, events_loaded, message
    except Exception as exc:  # noqa: BLE001
        finish_run(
            conn,
            run_id=run_id,
            status="error",
            message=f"{type(exc).__name__}: {exc}",
            records_seen=0,
            records_loaded=0,
        )
        raise
