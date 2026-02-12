from __future__ import annotations

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
from .db import upsert_parl_initiatives, upsert_parl_vote_event, upsert_source_record_for_event, upsert_source_records


def _load_person_map_for_mandate_source(conn: sqlite3.Connection, mandate_source_id: str) -> dict[str, int]:
    # Best-effort mapping by active mandates in the same institution/source.
    rows = conn.execute(
        """
        SELECT DISTINCT p.person_id, p.full_name
        FROM persons p
        JOIN mandates m ON m.person_id = p.person_id
        WHERE m.source_id = ? AND m.is_active = 1
        """
        ,
        (mandate_source_id,),
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


def _parse_congreso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parse_date_flexible(normalize_ws(str(value)))
    except Exception:  # noqa: BLE001
        return None


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
    person_map = _load_person_map_for_mandate_source(conn, "senado_senadores")
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
        conn.execute("DELETE FROM parl_vote_member_votes WHERE vote_event_id = ?", (vote_event_id,))
        member_rows: list[tuple[Any, ...]] = []
        for mv in member_votes:
            if not isinstance(mv, dict):
                continue
            member_name = mv.get("member_name")
            member_full, member_norm = _normalize_vote_member_name(member_name)
            person_id = person_map.get(member_norm or "") if member_norm else None
            seat_raw = mv.get("seat")
            seat = str(seat_raw) if seat_raw is not None else None
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
