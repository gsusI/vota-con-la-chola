#!/usr/bin/env python3
"""Exporta un snapshot estático de conexiones elecciones-comportamiento.

Incluye:
- Comparación pre/post de cohesión por partido para Congreso y Senado.
- Cambios de cohesión por tema en ventanas pre/post.
- Representación territorial (circunscripción) por elección usando mandatos como proxy.

Se construye de forma estática para consumo en GH Pages.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/gh-pages/elections-behavior/data/elections-behavior.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta snapshot de conexiones elecciones-comportamiento")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Ruta SQLite")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Ruta JSON de salida")
    parser.add_argument("--window-days", type=int, default=365, help="Días pre/post en torno a cada elección")
    parser.add_argument("--min-directional-votes", type=int, default=24, help="Mínimo votos direccionales para incluir fila")
    parser.add_argument("--min-topic-votes", type=int, default=12, help="Mínimo votos direccionales por tema")
    parser.add_argument("--max-party-shifts", type=int, default=400, help="Máximo de filas de cambios por partido")
    parser.add_argument("--max-topic-shifts", type=int, default=240, help="Máximo de filas de cambios por tema")
    parser.add_argument("--max-district-rows", type=int, default=1200, help="Máximo filas de representación territorial")
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def safe_int(value: Any) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def parse_vote_date(raw: Any) -> int | None:
    text = safe_text(raw)
    if not text:
        return None

    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        y, mo, d = map(int, m.groups())
        if 1700 <= y <= 2600:
            return y * 10000 + mo * 100 + d

    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", text)
    if m:
        y, mo, d = map(int, m.groups())
        if 1700 <= y <= 2600:
            return y * 10000 + mo * 100 + d

    m = re.match(r"^(\d{4})(\d{2})$", text)
    if m:
        y, mo = map(int, m.groups())
        if 1700 <= y <= 2600:
            return y * 10000 + mo * 100 + 1

    return None


def parse_election_date(raw: Any) -> date | None:
    text = safe_text(raw)
    if not text:
        return None

    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        y, mo, d = map(int, m.groups())
        if 1700 <= y <= 2600:
            try:
                return date(y, mo, d)
            except ValueError:
                return None

    m = re.match(r"^(\d{6})$", text)
    if m:
        y = int(text[:4])
        mo = int(text[4:])
        if 1700 <= y <= 2600:
            return date(y, mo, 1)

    return None


def date_ord(value: date | None) -> int:
    if value is None:
        return 0
    return value.year * 10000 + value.month * 100 + value.day


def to_iso(value: int) -> str:
    t = str(value)
    return f"{t[:4]}-{t[4:6]}-{t[6:]}"


def source_bucket(source_id: str) -> str:
    raw = safe_text(source_id).lower()
    if "congreso" in raw:
        return "congreso"
    if "senado" in raw:
        return "senado"
    return "other"


def normalize_vote_choice(raw: Any) -> str:
    value = safe_text(raw).upper().replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    if value in {"SÍ", "SI", "YES", "A FAVOR", "FAVOR", "A", "AFAVOR"}:
        return "yes"
    if value.startswith("NO"):
        return "no"
    if "ABST" in value:
        return "abstain"
    if "NO VOTA" in value or "NO VOT" in value:
        return "no_vote"
    return "other"


def pct(a: int, b: int) -> float:
    if not b:
        return 0.0
    return round(a * 100 / b, 2)


def load_party_meta(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    rows = conn.execute("SELECT party_id, COALESCE(name,''), COALESCE(acronym,'') FROM parties").fetchall()
    return {safe_int(r[0]): (safe_text(r[1]), safe_text(r[2])) for r in rows}


def load_territory_meta(conn: sqlite3.Connection) -> dict[int, str]:
    rows = conn.execute("SELECT territory_id, COALESCE(name,''), COALESCE(code,'') FROM territories").fetchall()
    out = {}
    for r in rows:
        tid = safe_int(r[0])
        label = safe_text(r[1]) or safe_text(r[2])
        if tid > 0 and label:
            out[tid] = label
    return out


def institution_buckets(conn: sqlite3.Connection) -> dict[int, str]:
    rows = conn.execute("SELECT institution_id, COALESCE(name,'') FROM institutions").fetchall()
    out: dict[int, str] = {}
    for r in rows:
        iid = safe_int(r[0])
        name = safe_text(r[1]).lower()
        if "congreso" in name:
            out[iid] = "congreso"
        elif "senado" in name:
            out[iid] = "senado"
    return out


def load_events(conn: sqlite3.Connection) -> tuple[dict[str, dict[str, Any]], dict[str, list[tuple[int, str]]]]:
    rows = conn.execute(
        """
        SELECT
          vote_event_id,
          source_id,
          vote_date,
          title,
          expediente_text,
          subgroup_title,
          subgroup_text
        FROM parl_vote_events
        """
    ).fetchall()

    events: dict[str, dict[str, Any]] = {}
    by_bucket: dict[str, list[tuple[int, str]]] = {"congreso": [], "senado": []}

    for r in rows:
        event_id = safe_text(r[0])
        bucket = source_bucket(safe_text(r[1]))
        if bucket == "other":
            continue

        d = parse_vote_date(r[2])
        if not d:
            continue

        row = {
            "vote_event_id": event_id,
            "source_bucket": bucket,
            "source_id": safe_text(r[1]),
            "vote_date": safe_text(r[2]),
            "vote_date_ord": d,
            "title": safe_text(r[3]),
            "expediente_text": safe_text(r[4]),
            "subgroup_title": safe_text(r[5]),
            "subgroup_text": safe_text(r[6]),
        }
        topic = row["title"] or row["subgroup_title"] or row["subgroup_text"] or row["expediente_text"]
        row["topic"] = topic[:72] if topic else "Sin tema"

        events[event_id] = row
        by_bucket[bucket].append((d, event_id))

    by_bucket["congreso"].sort()
    by_bucket["senado"].sort()
    return events, by_bucket


def build_mandate_index(
    conn: sqlite3.Connection,
    institution_map: dict[int, str],
) -> tuple[dict[tuple[int, str], list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    rows = conn.execute(
        """
        SELECT
          person_id,
          party_id,
          territory_id,
          m.start_date,
          m.end_date,
          m.institution_id,
          COALESCE(m.source_id, '') AS source_id
        FROM mandates m
        WHERE m.party_id IS NOT NULL
          AND m.person_id IS NOT NULL
        """
    ).fetchall()

    index: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    by_bucket: dict[str, list[dict[str, Any]]] = {"congreso": [], "senado": []}

    for r in rows:
        person_id = safe_int(r[0])
        party_id = safe_int(r[1])
        if not person_id or not party_id:
            continue

        bucket = source_bucket(safe_text(r[6]))
        if bucket == "other":
            bucket = institution_map.get(safe_int(r[5]), "other")
        if bucket == "other":
            continue

        territory_id = safe_int(r[2])
        start_ord = parse_vote_date(r[3])
        end_ord = parse_vote_date(r[4])

        payload = {
            "person_id": person_id,
            "party_id": party_id,
            "territory_id": territory_id,
            "start_ord": start_ord,
            "end_ord": end_ord,
        }
        index[(person_id, bucket)].append(payload)
        by_bucket[bucket].append(
            {
                "person_id": person_id,
                "party_id": party_id,
                "territory_id": territory_id,
                "start_ord": start_ord,
                "end_ord": end_ord,
            }
        )

    for key, items in index.items():
        items.sort(key=lambda it: it["start_ord"] if it["start_ord"] is not None else 0, reverse=True)

    for bucket in by_bucket:
        by_bucket[bucket].sort(key=lambda it: (it["person_id"], it["start_ord"] or 0), reverse=True)

    return index, by_bucket


def resolve_mandate_for_vote(
    mandate_index: dict[tuple[int, str], list[dict[str, Any]]],
    cache: dict[tuple[int, str, int | None], dict[str, Any] | None],
    person_id: int | None,
    bucket: str,
    vote_date_ord: int,
) -> dict[str, Any] | None:
    if not person_id or bucket == "other":
        return None

    key = (person_id, bucket, vote_date_ord)
    if key in cache:
        return cache[key]

    candidates = mandate_index.get((person_id, bucket), [])
    if not candidates:
        cache[key] = None
        return None

    for row in candidates:
        start_ord = row.get("start_ord")
        end_ord = row.get("end_ord")
        if start_ord is not None and vote_date_ord < start_ord:
            continue
        if end_ord is not None and vote_date_ord > end_ord:
            continue
        cache[key] = row
        return row

    cache[key] = candidates[0]
    return candidates[0]


def build_vote_aggregates(
    conn: sqlite3.Connection,
    events: dict[str, dict[str, Any]],
    mandate_index: dict[tuple[int, str], list[dict[str, Any]]],
) -> tuple[
    dict[str, dict[int, dict[str, int]]],
    dict[tuple[str, int, int], dict[str, int]],
    dict[tuple[str, int], str],
]:
    event_party_counts: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    event_party_territory_counts: dict[tuple[str, int, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    resolve_cache: dict[tuple[int, str, int | None], dict[str, Any] | None] = {}

    rows = conn.execute(
        """
        SELECT mv.vote_event_id, mv.person_id, mv.vote_choice, e.source_id
        FROM parl_vote_member_votes mv
        JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
        """
    ).fetchall()

    for r in rows:
        event_id = safe_text(r[0])
        event = events.get(event_id)
        if not event:
            continue

        person_id = safe_int(r[1])
        vote_dir = normalize_vote_choice(r[2])
        bucket = event["source_bucket"]
        mandate = resolve_mandate_for_vote(mandate_index, resolve_cache, person_id, bucket, event["vote_date_ord"])
        if not mandate:
            continue

        party_id = safe_int(mandate["party_id"])
        if not party_id:
            continue

        territory_id = safe_int(mandate.get("territory_id"))
        event_party_counts[event_id][party_id][vote_dir] += 1
        if territory_id > 0:
            event_party_territory_counts[(event_id, party_id, territory_id)][vote_dir] += 1

    event_party_position: dict[tuple[str, int], str] = {}
    for eid, by_party in event_party_counts.items():
        for party_id, counts in by_party.items():
            yes = safe_int(counts.get("yes"))
            no = safe_int(counts.get("no"))
            if yes + no <= 0:
                continue
            if yes > no:
                event_party_position[(eid, party_id)] = "yes"
            elif no > yes:
                event_party_position[(eid, party_id)] = "no"
            else:
                event_party_position[(eid, party_id)] = "tie"

    return event_party_counts, event_party_territory_counts, event_party_position


def aggregate_window(
    events_seq: list[tuple[int, str]],
    events: dict[str, dict[str, Any]],
    event_party_counts: dict[str, dict[int, dict[str, int]]],
    event_party_territory_counts: dict[tuple[str, int, int], dict[str, int]],
    event_party_position: dict[tuple[str, int], str],
    start_ord: int,
    end_ord: int,
) -> tuple[
    dict[int, dict[str, int]],
    dict[tuple[int, str], dict[str, int]],
    dict[tuple[int, int], dict[str, int]],
    int,
]:
    party_stats: dict[int, dict[str, int]] = defaultdict(lambda: {
        "votes_total": 0,
        "directional_votes": 0,
        "yes": 0,
        "no": 0,
        "abstain": 0,
        "no_vote": 0,
        "other": 0,
        "aligned": 0,
        "rebels": 0,
    })

    topic_stats: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: {
        "votes_total": 0,
        "directional_votes": 0,
        "yes": 0,
        "no": 0,
        "abstain": 0,
        "no_vote": 0,
        "other": 0,
        "aligned": 0,
        "rebels": 0,
    })

    territory_stats: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: {
        "votes_total": 0,
        "directional_votes": 0,
        "yes": 0,
        "no": 0,
        "abstain": 0,
        "no_vote": 0,
        "other": 0,
        "aligned": 0,
        "rebels": 0,
    })

    event_count = 0

    for event_ord, event_id in events_seq:
        if event_ord < start_ord or event_ord > end_ord:
            continue

        event_count += 1
        topic = events[event_id]["topic"]

        for party_id, counts in event_party_counts.get(event_id, {}).items():
            yes = safe_int(counts.get("yes"))
            no = safe_int(counts.get("no"))
            abstain = safe_int(counts.get("abstain"))
            no_vote = safe_int(counts.get("no_vote"))
            other = safe_int(counts.get("other"))
            directional = yes + no

            s = party_stats[party_id]
            s["votes_total"] += yes + no + abstain + no_vote + other
            s["directional_votes"] += directional
            s["yes"] += yes
            s["no"] += no
            s["abstain"] += abstain
            s["no_vote"] += no_vote
            s["other"] += other

            pos = event_party_position.get((event_id, party_id))
            if directional > 0 and pos in {"yes", "no"}:
                s["aligned"] += yes if pos == "yes" else no
                s["rebels"] += no if pos == "yes" else yes

            key_t = (party_id, topic)
            t = topic_stats[key_t]
            t["votes_total"] += yes + no + abstain + no_vote + other
            t["directional_votes"] += directional
            t["yes"] += yes
            t["no"] += no
            t["abstain"] += abstain
            t["no_vote"] += no_vote
            t["other"] += other
            if directional > 0 and pos in {"yes", "no"}:
                t["aligned"] += yes if pos == "yes" else no
                t["rebels"] += no if pos == "yes" else yes

        for (eid, party_id, territory_id), counts in event_party_territory_counts.items():
            if eid != event_id:
                continue

            yes = safe_int(counts.get("yes"))
            no = safe_int(counts.get("no"))
            abstain = safe_int(counts.get("abstain"))
            no_vote = safe_int(counts.get("no_vote"))
            other = safe_int(counts.get("other"))
            directional = yes + no

            t = territory_stats[(party_id, territory_id)]
            t["votes_total"] += yes + no + abstain + no_vote + other
            t["directional_votes"] += directional
            t["yes"] += yes
            t["no"] += no
            t["abstain"] += abstain
            t["no_vote"] += no_vote
            t["other"] += other

            pos = event_party_position.get((event_id, party_id))
            if directional > 0 and pos in {"yes", "no"}:
                t["aligned"] += yes if pos == "yes" else no
                t["rebels"] += no if pos == "yes" else yes

    return party_stats, topic_stats, territory_stats, event_count


def load_election_result_coverage(conn: sqlite3.Connection, election_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not election_ids:
        return {}

    placeholders = ",".join("?" for _ in election_ids)
    rows = conn.execute(
        f"""
        SELECT
          pr.proceso_id,
          pr.tipo_dato,
          pr.url,
          td.text_document_id
        FROM infoelectoral_proceso_resultados pr
        LEFT JOIN text_documents td ON td.source_record_pk = pr.source_record_pk
        WHERE pr.proceso_id IN ({placeholders})
        """,
        election_ids,
    ).fetchall()

    out: dict[str, dict[str, Any]] = {eid: {"result_rows": 0, "types": set(), "urls": [], "text_documents": 0} for eid in election_ids}
    for r in rows:
        eid = safe_text(r[0])
        if eid not in out:
            continue
        rec = out[eid]
        rec["result_rows"] += 1
        if safe_text(r[1]):
            rec["types"].add(safe_text(r[1]))
        if safe_text(r[2]) and len(rec["urls"]) < 3:
            rec["urls"].append(safe_text(r[2]))
        if safe_int(r[3]) > 0:
            rec["text_documents"] += 1

    output = {}
    for eid, rec in out.items():
        output[eid] = {
            "result_rows": rec["result_rows"],
            "types": sorted(rec["types"]),
            "urls": rec["urls"],
            "text_documents": rec["text_documents"],
            "has_official_result_rows": rec["result_rows"] > 0,
        }
    return output


def build_district_snapshot(
    mandates_rows: list[dict[str, Any]],
    election_date_ord: int,
) -> tuple[dict[tuple[int, int], int], int]:
    seats: dict[tuple[int, int], int] = defaultdict(int)
    seen_person: set[int] = set()
    seen_rows: int = 0

    for row in mandates_rows:
        person_id = safe_int(row["person_id"])
        if person_id in seen_person:
            continue

        start_ord = row.get("start_ord")
        end_ord = row.get("end_ord")
        if start_ord is not None and election_date_ord < start_ord:
            continue
        if end_ord is not None and election_date_ord > end_ord:
            continue

        seen_person.add(person_id)
        party_id = safe_int(row["party_id"])
        territory_id = safe_int(row["territory_id"])
        if party_id <= 0 or territory_id <= 0:
            continue

        seats[(party_id, territory_id)] += 1
        seen_rows += 1

    return seats, seen_rows


def make_party_label(party_id: int, party_meta: dict[int, tuple[str, str]]) -> str:
    if party_id <= 0:
        return f"Partido {party_id}"
    name, acronym = party_meta.get(party_id, ("", ""))
    if acronym:
        return acronym
    if name:
        return name
    return f"Partido {party_id}"


def run(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: DB no existe: {db_path}")
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        party_meta = load_party_meta(conn)
        territory_meta = load_territory_meta(conn)
        institution_map = institution_buckets(conn)

        events, events_by_bucket = load_events(conn)
        mandate_index, mandates_by_bucket = build_mandate_index(conn, institution_map)
        event_party_counts, event_party_territory_counts, event_party_position = build_vote_aggregates(
            conn,
            events,
            mandate_index,
        )

        elections = conn.execute(
            """
            SELECT convocatoria_id, tipo_convocatoria, fecha, cod, descripcion
            FROM infoelectoral_convocatorias
            WHERE tipo_convocatoria IN ('2', '3')
            ORDER BY fecha ASC
            """
        ).fetchall()

        election_rows: list[dict[str, Any]] = []
        valid_elections: list[str] = []

        for row in elections:
            e_date = parse_election_date(row[2])
            if not e_date:
                continue
            bucket = "congreso" if safe_text(row[1]) == "2" else "senado"
            election_id = safe_text(row[0])
            payload = {
                "election_id": election_id,
                "bucket": bucket,
                "type": safe_text(row[1]),
                "fecha": safe_text(row[2]),
                "cod": safe_text(row[3]),
                "label": safe_text(row[4]),
                "election_date": e_date.isoformat(),
                "election_date_ord": date_ord(e_date),
            }
            election_rows.append(payload)
            valid_elections.append(election_id)

        election_coverage = load_election_result_coverage(conn, valid_elections)

        # merge coverage into election list
        for e in election_rows:
            cov = election_coverage.get(e["election_id"], {})
            e.update(
                {
                    "has_result_payload": bool(cov.get("has_official_result_rows")),
                    "result_rows": int(cov.get("result_rows", 0)),
                    "result_types": cov.get("types", []),
                    "result_urls": cov.get("urls", []),
                    "result_text_documents": int(cov.get("text_documents", 0)),
                }
            )

        party_shifts: list[dict[str, Any]] = []
        topic_shifts: list[dict[str, Any]] = []
        district_rows: list[dict[str, Any]] = []

        by_bucket = {"congreso": [], "senado": []}
        for e in election_rows:
            by_bucket[e["bucket"]].append(e)

        for bucket in ("congreso", "senado"):
            for i, election in enumerate(by_bucket[bucket]):
                e_date = parse_election_date(election["fecha"])
                if not e_date:
                    continue

                pre_from = date_ord(e_date - timedelta(days=args.window_days))
                pre_to = date_ord(e_date - timedelta(days=1))
                post_from = date_ord(e_date)
                post_to = date_ord(e_date + timedelta(days=args.window_days))

                election["pre_window_from"] = to_iso(pre_from)
                election["pre_window_to"] = to_iso(pre_to)
                election["post_window_from"] = to_iso(post_from)
                election["post_window_to"] = to_iso(post_to)

                pre_party, pre_topic, pre_territory, pre_events = aggregate_window(
                    events_by_bucket[bucket],
                    events,
                    event_party_counts,
                    event_party_territory_counts,
                    event_party_position,
                    pre_from,
                    pre_to,
                )
                post_party, post_topic, post_territory, post_events = aggregate_window(
                    events_by_bucket[bucket],
                    events,
                    event_party_counts,
                    event_party_territory_counts,
                    event_party_position,
                    post_from,
                    post_to,
                )

                election["pre_events"] = pre_events
                election["post_events"] = post_events

                party_ids = sorted(set(pre_party) | set(post_party))
                for party_id in party_ids:
                    ps = pre_party.get(party_id, {})
                    po = post_party.get(party_id, {})
                    pre_dir = safe_int(ps.get("directional_votes"))
                    post_dir = safe_int(po.get("directional_votes"))
                    if pre_dir < args.min_directional_votes and post_dir < args.min_directional_votes:
                        continue

                    pre_c = pct(ps.get("aligned", 0), pre_dir)
                    post_c = pct(po.get("aligned", 0), post_dir)
                    party_shifts.append(
                        {
                            "bucket": bucket,
                            "election_id": election["election_id"],
                            "election_date": election["election_date"],
                            "label": election["label"],
                            "party_id": party_id,
                            "party_label": make_party_label(party_id, party_meta),
                            "pre_directional_votes": pre_dir,
                            "pre_aligned": safe_int(ps.get("aligned")),
                            "pre_cohesion_pct": pre_c,
                            "post_directional_votes": post_dir,
                            "post_aligned": safe_int(po.get("aligned")),
                            "post_cohesion_pct": post_c,
                            "delta_cohesion_pct": round(post_c - pre_c, 2),
                            "pre_events": pre_events,
                            "post_events": post_events,
                            "pre_vs_prev_election_delta_pct": None,
                        }
                    )

                seats, seats_total = build_district_snapshot(mandates_by_bucket[bucket], election["election_date_ord"])
                for (party_id, territory_id), seat_count in seats.items():
                    if len(district_rows) >= args.max_district_rows:
                        break

                    behavior = post_territory.get((party_id, territory_id), {})
                    behavior_dir = safe_int(behavior.get("directional_votes"))
                    behavior_aligned = safe_int(behavior.get("aligned"))
                    district_rows.append(
                        {
                            "bucket": bucket,
                            "election_id": election["election_id"],
                            "election_date": election["election_date"],
                            "label": election["label"],
                            "party_id": party_id,
                            "party_label": make_party_label(party_id, party_meta),
                            "territory_id": territory_id,
                            "territory_label": territory_meta.get(territory_id, f"Territorio {territory_id}"),
                            "seats": seat_count,
                            "seat_share_pct": pct(seat_count, seats_total),
                            "behavior_directional_votes": behavior_dir,
                            "behavior_aligned": behavior_aligned,
                            "behavior_cohesion_pct": pct(behavior_aligned, behavior_dir),
                        }
                    )

                for (party_id, topic), ts in post_topic.items():
                    ps = pre_topic.get((party_id, topic), {})
                    pre_dir = safe_int(ps.get("directional_votes"))
                    post_dir = safe_int(ts.get("directional_votes"))
                    if pre_dir < args.min_topic_votes or post_dir < args.min_topic_votes:
                        continue
                    pre_c = pct(ps.get("aligned", 0), pre_dir)
                    post_c = pct(ts.get("aligned", 0), post_dir)
                    topic_shifts.append(
                        {
                            "bucket": bucket,
                            "election_id": election["election_id"],
                            "election_date": election["election_date"],
                            "label": election["label"],
                            "party_id": party_id,
                            "party_label": make_party_label(party_id, party_meta),
                            "topic": topic,
                            "pre_directional_votes": pre_dir,
                            "pre_aligned": safe_int(ps.get("aligned", 0)),
                            "pre_cohesion_pct": pre_c,
                            "post_directional_votes": post_dir,
                            "post_aligned": safe_int(ts.get("aligned", 0)),
                            "post_cohesion_pct": post_c,
                            "delta_cohesion_pct": round(post_c - pre_c, 2),
                        }
                    )

        # Compute trend across legislatures (using previous election per party in same chamber)
        last_by_party_bucket: dict[tuple[str, int], tuple[str, float]] = {}
        for bucket in ("congreso", "senado"):
            ordered = sorted(
                [r for r in party_shifts if r["bucket"] == bucket],
                key=lambda r: r["election_date"],
            )
            for row in ordered:
                key = (bucket, row["party_id"])
                previous = last_by_party_bucket.get(key)
                if previous is not None:
                    prev_eid, prev_value = previous
                    row["pre_vs_prev_election"] = prev_eid
                    row["pre_vs_prev_election_delta_pct"] = round(row["pre_cohesion_pct"] - prev_value, 2)
                last_by_party_bucket[key] = (row["election_id"], row["pre_cohesion_pct"])

        # Sort and cap outputs
        party_shifts = sorted(
            party_shifts,
            key=lambda r: (r["bucket"], abs(r["delta_cohesion_pct"]), r["election_date"]),
            reverse=True,
        )[: args.max_party_shifts]
        topic_shifts = sorted(
            topic_shifts,
            key=lambda r: (r["bucket"], abs(r["delta_cohesion_pct"]), r["election_date"]),
            reverse=True,
        )[: args.max_topic_shifts]
        district_rows = sorted(
            district_rows,
            key=lambda r: (r["bucket"], r["election_date"], -r["seats"], r["party_label"], r["territory_label"]),
            reverse=True,
        )

        party_index = {
            str(party_id): {
                "name": safe_text(name),
                "acronym": safe_text(acronym),
            }
            for party_id, (name, acronym) in party_meta.items()
        }

        payload = {
            "meta": {
                "generated_at": now_utc_iso(),
                "source_db": str(db_path),
                "window_days": args.window_days,
                "min_directional_votes": args.min_directional_votes,
                "min_topic_votes": args.min_topic_votes,
            },
            "institutions": [
                {"bucket": "congreso", "label": "Congreso"},
                {"bucket": "senado", "label": "Senado"},
            ],
            "elections": election_rows,
            "party_index": party_index,
            "party_shifts": party_shifts,
            "topic_shifts": topic_shifts,
            "district_representation": district_rows,
        }

        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"OK elections-behavior snapshot -> {out_path} (elections={len(election_rows)} "
            f"party_shifts={len(party_shifts)} topic_shifts={len(topic_shifts)} districts={len(district_rows)})"
        )
        return 0
    except sqlite3.Error as exc:
        print(f"ERROR SQL: {exc}")
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
