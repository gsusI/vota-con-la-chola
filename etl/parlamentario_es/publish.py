from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from .quality import (
    compute_initiative_quality_kpis,
    compute_vote_quality_kpis,
    evaluate_initiative_quality_gate,
    evaluate_vote_quality_gate,
)
from .pipeline import backfill_vote_member_person_ids


def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _parse_json_maybe(text: str | None) -> Any | None:
    if not text:
        return None
    try:
        return json.loads(str(text))
    except Exception:  # noqa: BLE001
        return None


def _event_source_hash(row: sqlite3.Row) -> str:
    source_hash = str(row["event_source_hash"] or "").strip()
    if source_hash:
        return source_hash
    return _sha256_text(str(row["event_raw_payload"] or ""))


def _initiative_source_hash(row: sqlite3.Row) -> str:
    source_hash = str(row["initiative_source_hash"] or "").strip()
    if source_hash:
        return source_hash
    return _sha256_text(str(row["initiative_raw_payload"] or ""))


def _chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


def build_votaciones_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    source_ids: Iterable[str] = ("congreso_votaciones", "senado_votaciones"),
    include_initiative_quality: bool = False,
    initiative_source_ids: Iterable[str] = ("congreso_iniciativas", "senado_iniciativas"),
    only_linked_events: bool = False,
    max_events: int | None = None,
    max_member_votes_per_event: int | None = None,
    backfill_member_ids: bool = False,
    backfill_batch_size: int = 5000,
    include_unmatched_people: bool = False,
    unmatched_sample_limit: int = 0,
) -> dict[str, Any]:
    source_ids = tuple(str(x).strip() for x in source_ids if str(x).strip())
    initiative_source_ids = tuple(
        str(x).strip() for x in initiative_source_ids if str(x).strip()
    )
    if not source_ids:
        raise ValueError("source_ids vacio")
    if bool(include_initiative_quality) and not initiative_source_ids:
        raise ValueError("initiative_source_ids vacio")
    unmatched_sample_limit_i = int(unmatched_sample_limit)
    if unmatched_sample_limit_i < 0:
        raise ValueError("unmatched-sample-limit debe ser >= 0")
    if int(backfill_batch_size) <= 0:
        raise ValueError("backfill-batch-size debe ser > 0")

    backfill_report: dict[str, Any] | None = None
    if bool(backfill_member_ids):
        backfill_report = backfill_vote_member_person_ids(
            conn,
            vote_source_ids=source_ids,
            dry_run=False,
            batch_size=int(backfill_batch_size),
            unmatched_sample_limit=0,
        )

    where = ["e.source_id IN (" + ",".join("?" for _ in source_ids) + ")"]
    params: list[Any] = [*source_ids]
    if only_linked_events:
        where.append(
            "EXISTS (SELECT 1 FROM parl_vote_event_initiatives l WHERE l.vote_event_id = e.vote_event_id)"
        )

    sql = f"""
        SELECT
          e.vote_event_id,
          e.legislature,
          e.session_number,
          e.vote_number,
          e.vote_date,
          e.title,
          e.expediente_text,
          e.subgroup_title,
          e.subgroup_text,
          e.assentimiento,
          e.totals_present,
          e.totals_yes,
          e.totals_no,
          e.totals_abstain,
          e.totals_no_vote,
          e.source_id,
          e.source_url,
          e.source_record_pk,
          e.source_snapshot_date,
          e.raw_payload AS event_raw_payload,
          sr.source_record_id AS event_source_record_id,
          sr.content_sha256 AS event_source_hash
        FROM parl_vote_events e
        LEFT JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
        WHERE {" AND ".join(where)}
        ORDER BY
          e.source_id,
          e.vote_date,
          e.session_number,
          e.vote_number,
          e.vote_event_id
    """
    if isinstance(max_events, int) and max_events > 0:
        sql += "\nLIMIT ?"
        params.append(int(max_events))

    event_rows = conn.execute(sql, params).fetchall()

    items: list[dict[str, Any]] = []
    index: dict[str, int] = {}
    event_ids: list[str] = []
    events_by_source: dict[str, int] = {}

    for r in event_rows:
        vote_event_id = str(r["vote_event_id"])
        source_id = str(r["source_id"])
        event_ids.append(vote_event_id)
        events_by_source[source_id] = events_by_source.get(source_id, 0) + 1

        items.append(
            {
                "event": {
                    "vote_event_id": vote_event_id,
                    "source_id": source_id,
                    "legislature": r["legislature"],
                    "session_number": r["session_number"],
                    "vote_number": r["vote_number"],
                    "vote_date": r["vote_date"],
                    "title": r["title"],
                    "expediente_text": r["expediente_text"],
                    "subgroup_title": r["subgroup_title"],
                    "subgroup_text": r["subgroup_text"],
                    "assentimiento": r["assentimiento"],
                    "totals_present": r["totals_present"],
                    "totals_yes": r["totals_yes"],
                    "totals_no": r["totals_no"],
                    "totals_abstain": r["totals_abstain"],
                    "totals_no_vote": r["totals_no_vote"],
                },
                "source": {
                    "source_id": source_id,
                    "source_record_id": r["event_source_record_id"],
                    "source_snapshot_date": r["source_snapshot_date"],
                    "source_url": r["source_url"],
                    "source_hash": _event_source_hash(r),
                    "source_record_pk": r["source_record_pk"],
                },
                "initiatives": [],
                "member_votes": [],
            }
        )
        index[vote_event_id] = len(items) - 1

    if event_ids:
        for chunk in _chunked(event_ids, 400):
            qmarks = ",".join("?" for _ in chunk)
            link_rows = conn.execute(
                f"""
                SELECT
                  l.vote_event_id,
                  l.link_method,
                  l.confidence,
                  l.evidence_json,
                  i.initiative_id,
                  i.legislature,
                  i.expediente,
                  i.supertype,
                  i.grouping,
                  i.type,
                  i.title,
                  i.source_id AS initiative_source_id,
                  i.source_url AS initiative_source_url,
                  i.source_record_pk AS initiative_source_record_pk,
                  i.source_snapshot_date AS initiative_source_snapshot_date,
                  i.raw_payload AS initiative_raw_payload,
                  sr.source_record_id AS initiative_source_record_id,
                  sr.content_sha256 AS initiative_source_hash
                FROM parl_vote_event_initiatives l
                JOIN parl_initiatives i ON i.initiative_id = l.initiative_id
                LEFT JOIN source_records sr ON sr.source_record_pk = i.source_record_pk
                WHERE l.vote_event_id IN ({qmarks})
                ORDER BY l.vote_event_id, i.initiative_id, l.link_method
                """,
                chunk,
            ).fetchall()

            for r in link_rows:
                vote_event_id = str(r["vote_event_id"])
                if vote_event_id not in index:
                    continue
                evidence = _parse_json_maybe(r["evidence_json"])
                items[index[vote_event_id]]["initiatives"].append(
                    {
                        "initiative": {
                            "initiative_id": str(r["initiative_id"]),
                            "source_id": str(r["initiative_source_id"]),
                            "legislature": r["legislature"],
                            "expediente": r["expediente"],
                            "supertype": r["supertype"],
                            "grouping": r["grouping"],
                            "type": r["type"],
                            "title": r["title"],
                        },
                        "link": {
                            "method": r["link_method"],
                            "confidence": r["confidence"],
                            "evidence": evidence if evidence is not None else r["evidence_json"],
                        },
                        "source": {
                            "source_id": str(r["initiative_source_id"]),
                            "source_record_id": r["initiative_source_record_id"],
                            "source_snapshot_date": r["initiative_source_snapshot_date"],
                            "source_url": r["initiative_source_url"],
                            "source_hash": _initiative_source_hash(r),
                            "source_record_pk": r["initiative_source_record_pk"],
                        },
                    }
                )

        member_vote_counts: dict[str, int] = {}
        for chunk in _chunked(event_ids, 400):
            qmarks = ",".join("?" for _ in chunk)
            vote_rows = conn.execute(
                f"""
                SELECT
                  mv.vote_event_id,
                  mv.seat,
                  mv.member_name,
                  mv.member_name_normalized,
                  mv.person_id,
                  p.full_name AS person_full_name,
                  mv.group_code,
                  mv.vote_choice,
                  mv.source_id,
                  mv.source_url,
                  mv.source_snapshot_date,
                  mv.raw_payload
                FROM parl_vote_member_votes mv
                LEFT JOIN persons p ON p.person_id = mv.person_id
                WHERE mv.vote_event_id IN ({qmarks})
                ORDER BY mv.vote_event_id, mv.seat, mv.member_name, mv.member_vote_id
                """,
                chunk,
            ).fetchall()

            for r in vote_rows:
                vote_event_id = str(r["vote_event_id"])
                if vote_event_id not in index:
                    continue

                current = member_vote_counts.get(vote_event_id, 0)
                if isinstance(max_member_votes_per_event, int) and max_member_votes_per_event > 0:
                    if current >= max_member_votes_per_event:
                        continue
                member_vote_counts[vote_event_id] = current + 1

                raw_payload = str(r["raw_payload"] or "")
                items[index[vote_event_id]]["member_votes"].append(
                    {
                        "seat": r["seat"],
                        "member_name": r["member_name"],
                        "member_name_normalized": r["member_name_normalized"],
                        "person_id": r["person_id"],
                        "person_full_name": r["person_full_name"],
                        "group_code": r["group_code"],
                        "vote_choice": r["vote_choice"],
                        "source": {
                            "source_id": r["source_id"],
                            "source_url": r["source_url"],
                            "source_snapshot_date": r["source_snapshot_date"],
                            "source_hash": _sha256_text(raw_payload),
                            "source_record_pk": None,
                            "source_record_id": None,
                        },
                    }
                )

    events_with_topic = 0
    events_with_totals = 0
    member_votes_total = 0
    member_votes_with_person_id = 0
    member_votes_by_source: dict[str, int] = {}

    for item in items:
        if item["initiatives"]:
            events_with_topic += 1
        ev = item["event"]
        if (
            ev["totals_present"] is not None
            or ev["totals_yes"] is not None
            or ev["totals_no"] is not None
            or ev["totals_abstain"] is not None
            or ev["totals_no_vote"] is not None
        ):
            events_with_totals += 1

        votes = item["member_votes"]
        member_votes_total += len(votes)
        for mv in votes:
            if mv.get("person_id") is not None:
                member_votes_with_person_id += 1
            src_id = str(mv.get("source", {}).get("source_id") or "")
            if not src_id:
                continue
            member_votes_by_source[src_id] = member_votes_by_source.get(src_id, 0) + 1

    kpis = compute_vote_quality_kpis(conn, source_ids=source_ids)
    events_with_initiative_link = int(kpis.get("events_with_initiative_link") or 0)

    totales: dict[str, Any] = {
        "eventos": len(items),
        "eventos_con_tema": events_with_topic,
        "eventos_con_vinculo_iniciativa": events_with_initiative_link,
        "eventos_con_totales": events_with_totals,
        "votos_nominales": member_votes_total,
        "votos_nominales_con_person_id": member_votes_with_person_id,
        "eventos_por_source_id": dict(sorted(events_by_source.items())),
        "votos_por_source_id": dict(sorted(member_votes_by_source.items())),
    }
    gate = evaluate_vote_quality_gate(kpis)
    unmatched_people = None
    if bool(include_unmatched_people):
        unmatched_people = backfill_vote_member_person_ids(
            conn,
            vote_source_ids=source_ids,
            dry_run=True,
            unmatched_sample_limit=unmatched_sample_limit_i,
        )

    initiatives_quality: dict[str, Any] | None = None
    if bool(include_initiative_quality):
        initiative_kpis = compute_initiative_quality_kpis(
            conn,
            source_ids=initiative_source_ids,
        )
        initiatives_quality = {
            "provider": "etl.parlamentario_es.quality",
            "scope": {"source_ids": list(initiative_source_ids)},
            "kpis": initiative_kpis,
            "gate": evaluate_initiative_quality_gate(initiative_kpis),
        }

    quality: dict[str, Any] = {
        "provider": "etl.parlamentario_es.quality",
        "scope": {"source_ids": list(source_ids)},
        "kpis": kpis,
        "gate": gate,
        "member_id_backfill": backfill_report,
    }
    if initiatives_quality is not None:
        quality["initiatives"] = initiatives_quality
    if unmatched_people is not None:
        quality["unmatched_people"] = unmatched_people

    snapshot: dict[str, Any] = {
        "fecha_referencia": snapshot_date,
        # Deterministic timestamp for a given snapshot date.
        "generado_en": f"{snapshot_date}T00:00:00+00:00",
        "filtros": {
            "source_ids": list(source_ids),
            "only_linked_events": bool(only_linked_events),
            "max_events": max_events,
            "max_member_votes_per_event": max_member_votes_per_event,
        },
        "totales": totales,
        "quality": quality,
        "items": items,
    }
    return snapshot


def write_json_if_changed(path: Path, obj: Any) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if old == text:
            return False
    path.write_text(text, encoding="utf-8")
    return True
