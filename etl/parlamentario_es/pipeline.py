from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from etl.politicos_es.db import finish_run, start_run
from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso, sha256_bytes, stable_json

from .config import SOURCE_CONFIG
from .connectors.base import BaseConnector
from .db import upsert_parl_vote_event, upsert_source_record_for_event


def _load_congreso_person_map(conn: sqlite3.Connection) -> dict[str, int]:
    # Best-effort mapping: Congreso vote files don't include deputy id, only name.
    # We restrict candidates to active Congreso mandates to reduce collisions.
    rows = conn.execute(
        """
        SELECT DISTINCT p.person_id, p.full_name
        FROM persons p
        JOIN mandates m ON m.person_id = p.person_id
        WHERE m.source_id = 'congreso_diputados' AND m.is_active = 1
        """
    ).fetchall()
    mapping: dict[str, int] = {}
    for r in rows:
        key = normalize_key_part(str(r["full_name"] or ""))
        if not key:
            continue
        mapping[key] = int(r["person_id"])
    return mapping


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

        person_map = _load_congreso_person_map(conn) if source_id == "congreso_votaciones" else {}

        now_iso = now_utc_iso()
        events_seen = 0
        events_loaded = 0
        member_votes_loaded = 0

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
