#!/usr/bin/env python3
"""Exporta un snapshot estático de accountability parlamentario para GH Pages.

El objetivo es que la nueva página de Next.js no dependa de la API en runtime y
pueda ejecutarse 100% con JSON público.

Métricas incluidas:
- Disciplina partidaria por partido, legislatura y tema.
- Disciplina por persona (usando membresía corregida por fecha).
- Asistencia/ausencias por persona y partido con separación comité/pleno.
- Similitud entre bloques (coseno y Jaccard sobre vectores roll-call).
- Resultado por votación y partidos de impacto (pivotalidad simplificada).
- Detección de coaliciones por tema (alineamiento alto en tema y bajo global).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/gh-pages/parliamentary-accountability/data/accountability.json")


@dataclass(frozen=True)
class PartyAgg:
    party_id: int
    party_name: str
    party_acronym: str | None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Exporta un snapshot de accountability parlamentaria para GH Pages"
    )
    p.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta a la base SQLite",
    )
    p.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Ruta de salida JSON (ej. docs/gh-pages/parliamentary-accountability/data/accountability.json)",
    )
    p.add_argument(
        "--min-shared-events",
        type=int,
        default=12,
        help="Mínimo de votaciones compartidas para calcular similitud de dos partidos",
    )
    p.add_argument(
        "--min-events-per-party",
        type=int,
        default=12,
        help="Mínimo de votaciones direccionales para incluir partido en similitud",
    )
    p.add_argument(
        "--min-events-topic-pairs",
        type=int,
        default=8,
        help="Mínimo de votaciones compartidas para comparar similitud por tema",
    )
    p.add_argument(
        "--max-rows-events",
        type=int,
        default=700,
        help="Máximo de eventos expuestos con detalle (el resto se deja en resumen)",
    )
    return p.parse_args()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_text(value: Any) -> str:
    return safe_text(value).lower()


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def normalize_vote_choice(raw: Any) -> str:
    v = strip_accents(normalize_text(raw)).upper()
    if not v:
        return "other"
    if v in {"SI", "SÍ", "YES", "A", "A FAVOR", "A FAVOR DE", "AFAVOR", "FAVOR", "FAV", "APOYA", "YES"}:
        return "yes"
    if v in {"NO", "DENEGADO", "EN CONTRA", "ENCONTRAR"}:
        return "no"
    if "ABST" in v or "ABSTENCION" in v:
        return "abstain"
    if "NO VOT" in v or "AUSENT" in v or "NO VOTA" in v:
        return "no_vote"
    return "other"


PARTY_ID_CODE_RE = re.compile(r"^(?:\d{1,3}:\d{3,}|\d{4,})$")

PARTY_NAME_KEYS = (
    "partido_nombre",
    "partido_name",
    "partidoName",
    "partidoNom",
    "partido_nom",
    "partidoNombr",
    "grupo",
    "grupo_nombre",
    "grupoNombre",
    "grupo_name",
    "grupoName",
    "group_name",
    "group",
)


def looks_like_party_code(value: Any) -> bool:
    return bool(PARTY_ID_CODE_RE.fullmatch(safe_text(value)))


def normalize_party_name_key(value: Any) -> str:
    return "".join(ch for ch in strip_accents(safe_text(value)).lower() if ch.isalnum() or ch in {"_", "-", ":"})


def extract_party_name_from_raw_payload(raw_payload: Any) -> str:
    payload_text = safe_text(raw_payload)
    if not payload_text:
        return ""

    try:
        payload = json.loads(payload_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""

    if isinstance(payload, dict):
        for key in PARTY_NAME_KEYS:
            if key in payload:
                name = safe_text(payload.get(key))
                if name and not looks_like_party_code(name):
                    return name

        for key, value in payload.items():
            key_text = normalize_party_name_key(key)
            if ("partido" in key_text or "grupo" in key_text) and ("nombre" in key_text or "name" in key_text):
                name = safe_text(value)
                if name and not looks_like_party_code(name):
                    return name

    return ""


def build_party_name_by_vote_group_code(conn: sqlite3.Connection) -> dict[int, str]:
    rows = conn.execute(
        """
        SELECT
          m.party_id,
          mv.group_code
        FROM mandates m
        JOIN parl_vote_member_votes mv
          ON mv.person_id = m.person_id
        JOIN parl_vote_events ev
          ON ev.vote_event_id = mv.vote_event_id
        WHERE m.party_id IS NOT NULL
          AND mv.group_code IS NOT NULL
          AND TRIM(mv.group_code) <> ''
          AND (
            m.start_date IS NULL OR TRIM(m.start_date) = '' OR substr(ev.vote_date, 1, 10) >= m.start_date
          )
          AND (
            m.end_date IS NULL OR TRIM(m.end_date) = '' OR substr(ev.vote_date, 1, 10) <= m.end_date
          )
        """
    ).fetchall()

    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        party_id = to_int_or_none(row["party_id"])
        if not party_id:
            continue
        group_name = safe_text(row["group_code"])
        if not group_name or looks_like_party_code(group_name):
            continue
        counts[party_id][group_name] += 1

    out: dict[int, str] = {}
    for party_id, names in counts.items():
        if not names:
            continue
        out[party_id] = sorted(names.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
    return out


def pick_party_name(current: str, candidate: str) -> str:
    current_name = safe_text(current)
    candidate_name = safe_text(candidate)

    if not candidate_name:
        return current_name

    if looks_like_party_code(current_name) and not looks_like_party_code(candidate_name):
        return candidate_name

    if current_name:
        return current_name

    return candidate_name


def source_bucket(source_id: str) -> str:
    v = normalize_text(source_id)
    if "congreso" in v:
        return "congreso"
    if "senado" in v:
        return "senado"
    return "other"


def vote_event_outcome(event: dict[str, Any]) -> tuple[str, int, dict[str, float]]:
    yes = int(event.get("totals_yes") or 0)
    no = int(event.get("totals_no") or 0)
    abstain = int(event.get("totals_abstain") or 0)
    no_vote = int(event.get("totals_no_vote") or 0)
    present = int(event.get("totals_present") or 0)

    total_signal = yes + no
    if total_signal <= 0:
        return "no_signal", 0, {
            "yes": yes,
            "no": no,
            "abstain": abstain,
            "no_vote": no_vote,
            "present": present,
            "margin": 0,
            "total_signal": total_signal,
        }

    if yes > no:
        outcome = "passed"
    elif no > yes:
        outcome = "failed"
    else:
        outcome = "tied"

    return outcome, yes - no, {
        "yes": yes,
        "no": no,
        "abstain": abstain,
        "no_vote": no_vote,
        "present": present,
        "margin": yes - no,
        "total_signal": total_signal,
    }


def parse_event_date(raw: Any) -> int | None:
    text = safe_text(raw)
    if not text:
        return None

    # Expected formats: YYYY-MM-DD (may come with time suffix)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        year, month, day = map(int, m.groups())
        if year < 1800:
            return None
        return year * 10000 + month * 100 + day

    # Fallback: YYYYMMDD
    m = re.match(r"^(\d{8})$", text.replace("-", ""))
    if m:
        yy = int(text[:4])
        if yy < 1800:
            return None
        return int(text[:4]) * 10000 + int(text[4:6]) * 100 + int(text[6:8])

    return None


def normalize_topic(event: dict[str, Any]) -> str:
    for key in ("supertype", "grouping", "initiative_type", "initiative_title", "title"):
        value = safe_text(event.get(key))
        if value:
            value = " ".join(value.split())
            return value[:72]
    return "Sin tema"


def normalize_context(event: dict[str, Any]) -> str:
    txt = " ".join(
        [safe_text(event.get("subgroup_title")), safe_text(event.get("subgroup_text")), safe_text(event.get("title"))]
    ).lower()
    txt = strip_accents(txt)
    if any(token in txt for token in ("comision", "comisiones", "subcomision", "subcomisiones", "comité", "comite")):
        return "committee"
    if any(token in txt for token in ("pleno", "plenary", "plenaria", "plenario")):
        return "plenary"
    return "other"


def compact_text(value: Any, limit: int = 240) -> str:
    text = " ".join(safe_text(value).split())
    if not text:
        return ""
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rstrip()
    last_space = trimmed.rfind(" ")
    if last_space > 24:
        trimmed = trimmed[:last_space]
    return f"{trimmed}..."


def derive_vote_subject(event: dict[str, Any]) -> str:
    for key in ("initiative_title", "title", "expediente_text", "subgroup_title", "subgroup_text"):
        value = compact_text(event.get(key), 240)
        if value:
            return value
    return ""


def float_pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator * 100 / denominator, 2)


def to_int_or_none(raw: Any) -> int | None:
    text = safe_text(raw)
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def build_mandate_index(conn: sqlite3.Connection) -> tuple[
    dict[tuple[int, str], list[dict[str, Any]]], dict[int, PartyAgg], dict[str, int]
]:
    party_name_overrides = build_party_name_by_vote_group_code(conn)

    rows = conn.execute(
        """
        SELECT
          m.person_id,
          m.party_id,
          p.name AS party_name,
          p.acronym AS party_acronym,
          m.role_title,
          m.source_id,
          m.start_date,
          m.end_date,
          m.mandate_id,
          sr.raw_payload
        FROM mandates m
        LEFT JOIN parties p ON p.party_id = m.party_id
        LEFT JOIN source_records sr ON sr.source_record_pk = m.source_record_pk
        WHERE m.party_id IS NOT NULL
          AND m.person_id IS NOT NULL
          AND m.person_id > 0
        """
    ).fetchall()

    index: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    parties: dict[int, PartyAgg] = {}
    person_party_stats: dict[str, int] = defaultdict(int)

    for row in rows:
        person_id = to_int_or_none(row["person_id"])
        if not person_id:
            continue

        party_id = to_int_or_none(row["party_id"])
        if not party_id:
            continue

        bucket = source_bucket(safe_text(row["source_id"]))
        key = (person_id, bucket)
        source_party_name = extract_party_name_from_raw_payload(row["raw_payload"])
        resolved_party_name = pick_party_name(safe_text(row["party_name"]), source_party_name)
        resolved_party_name = pick_party_name(
            resolved_party_name,
            party_name_overrides.get(party_id, ""),
        )
        existing = parties.get(party_id)
        if existing:
            resolved_party_name = pick_party_name(existing.party_name, resolved_party_name)

        resolved_party_acronym = safe_text(row["party_acronym"]) or None
        if existing and existing.party_acronym:
            resolved_party_acronym = existing.party_acronym

        parties[party_id] = PartyAgg(
            party_id=party_id,
            party_name=resolved_party_name,
            party_acronym=resolved_party_acronym,
        )
        rec = {
            "person_id": person_id,
            "party_id": party_id,
            "party_name": resolved_party_name,
            "party_acronym": resolved_party_acronym,
            "role_title": safe_text(row["role_title"]),
            "source_id": safe_text(row["source_id"]),
            "start_ord": parse_event_date(row["start_date"]),
            "end_ord": parse_event_date(row["end_date"]),
            "mandate_id": to_int_or_none(row["mandate_id"]) or 0,
        }
        index[key].append(rec)
        person_party_stats[f"{person_id}:{party_id}"] += 1

    # Ordena por mandato más reciente (start_desc) para resolver por orden lineal rápido.
    for key, items in index.items():
        items.sort(
            key=lambda it: (
                it["start_ord"] if it["start_ord"] is not None else -1,
                it["mandate_id"],
            ),
            reverse=True,
        )

    return index, parties, person_party_stats


def resolve_party_for_vote(
    mandate_index: dict[tuple[int, str], list[dict[str, Any]]],
    cache: dict[tuple[int, str, int | None], dict[str, Any] | None],
    person_id: int | None,
    source_id: str,
    vote_date_ord: int | None,
) -> dict[str, Any] | None:
    if not person_id:
        return None

    bucket = source_bucket(source_id)
    key = (person_id, bucket, vote_date_ord)
    if key in cache:
        return cache[key]

    candidates = mandate_index.get((person_id, bucket), [])
    if not candidates:
        cache[key] = None
        return None

    if vote_date_ord is None:
        # fallback determinístico: si la fecha está rota usamos el mandato más reciente.
        fallback = candidates[0]
        cache[key] = fallback
        return fallback

    for rec in candidates:
        start_ord = rec["start_ord"]
        end_ord = rec["end_ord"]
        if start_ord is not None and vote_date_ord < start_ord:
            continue
        if end_ord is not None and vote_date_ord > end_ord:
            continue
        cache[key] = rec
        return rec

    # Si no cuadra por fecha, usamos el mandato activo más cercano hacia atrás (si lo hay)
    for rec in candidates:
        start_ord = rec["start_ord"]
        if start_ord is None or start_ord <= vote_date_ord:
            cache[key] = rec
            return rec

    cache[key] = candidates[-1]
    return candidates[-1]


def build_event_map(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        WITH first_documents AS (
          SELECT
            d.initiative_id,
            MIN(d.doc_url) AS initiative_doc_url
          FROM parl_initiative_documents d
          GROUP BY d.initiative_id
        ),
        ranked_initiatives AS (
          SELECT
            vei.vote_event_id,
            vei.initiative_id,
            COALESCE(vei.confidence, -1) AS initiative_link_confidence,
            vei.link_method AS initiative_link_method,
            i.supertype,
            i.grouping,
            i.type AS initiative_type,
            i.title AS initiative_title,
            i.expediente AS initiative_expediente,
            i.source_url AS initiative_source_url,
            d.initiative_doc_url,
            ROW_NUMBER() OVER (
              PARTITION BY vei.vote_event_id
              ORDER BY COALESCE(vei.confidence, -1) DESC, vei.initiative_id
            ) AS rn
          FROM parl_vote_event_initiatives vei
          JOIN parl_initiatives i ON i.initiative_id = vei.initiative_id
          LEFT JOIN first_documents d ON d.initiative_id = i.initiative_id
        )
        SELECT
          e.vote_event_id,
          e.source_id,
          e.source_url AS vote_source_url,
          e.legislature,
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
          r.supertype,
          r.grouping,
          r.initiative_type,
          r.initiative_title,
          r.initiative_id,
          r.initiative_expediente,
          r.initiative_source_url,
          r.initiative_doc_url,
          r.initiative_link_method,
          r.initiative_link_confidence
        FROM parl_vote_events e
        LEFT JOIN ranked_initiatives r
          ON r.vote_event_id = e.vote_event_id
         AND r.rn = 1
        ORDER BY e.vote_date DESC, e.vote_event_id ASC
        """
    ).fetchall()

    events: dict[str, dict[str, Any]] = {}
    for row in rows:
        event_id = safe_text(row["vote_event_id"])
        if not event_id:
            continue

        event_data = {
            "vote_event_id": event_id,
            "source_id": safe_text(row["source_id"]),
            "source_bucket": source_bucket(safe_text(row["source_id"])),
            "source_url": safe_text(row["vote_source_url"]),
            "legislature": safe_text(row["legislature"]),
            "vote_date": safe_text(row["vote_date"]),
            "vote_date_ord": parse_event_date(row["vote_date"]),
            "title": safe_text(row["title"]),
            "expediente_text": safe_text(row["expediente_text"]),
            "subgroup_title": safe_text(row["subgroup_title"]),
            "subgroup_text": safe_text(row["subgroup_text"]),
            "assentimiento": safe_text(row["assentimiento"]),
            "totals_present": int(row["totals_present"] or 0),
            "totals_yes": int(row["totals_yes"] or 0),
            "totals_no": int(row["totals_no"] or 0),
            "totals_abstain": int(row["totals_abstain"] or 0),
            "totals_no_vote": int(row["totals_no_vote"] or 0),
            "initiative_id": safe_text(row["initiative_id"]),
            "supertype": safe_text(row["supertype"]),
            "grouping": safe_text(row["grouping"]),
            "initiative_type": safe_text(row["initiative_type"]),
            "initiative_title": safe_text(row["initiative_title"]),
            "initiative_expediente": safe_text(row["initiative_expediente"]),
            "initiative_source_url": safe_text(row["initiative_source_url"]),
            "initiative_doc_url": safe_text(row["initiative_doc_url"]),
            "initiative_link_method": safe_text(row["initiative_link_method"]),
            "initiative_link_confidence": (
                float(row["initiative_link_confidence"])
                if row["initiative_link_confidence"] is not None
                else None
            ),
        }
        event_data["topic"] = normalize_topic(event_data)
        event_data["context"] = normalize_context(event_data)
        event_data["vote_subject"] = derive_vote_subject(event_data)
        outcome, margin, outcome_meta = vote_event_outcome(event_data)
        event_data["outcome"] = outcome
        event_data["margin"] = margin
        event_data.update(outcome_meta)
        has_vote_subject = bool(event_data["vote_subject"])
        has_initiative_link = bool(event_data["initiative_id"])
        has_source_url = bool(
            event_data["source_url"] or event_data["initiative_source_url"] or event_data["initiative_doc_url"]
        )
        missing: list[str] = []
        if not has_vote_subject:
            missing.append("missing_vote_subject")
        if not has_initiative_link:
            missing.append("missing_initiative_link")
        if not has_source_url:
            missing.append("missing_official_source_url")
        event_data["quality"] = {
            "has_vote_subject": has_vote_subject,
            "has_initiative_link": has_initiative_link,
            "has_source_url": has_source_url,
            "is_interpretable": has_vote_subject and has_initiative_link and has_source_url,
            "missing": missing,
        }
        events[event_id] = event_data

    return events


def iter_vote_rows(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT
          mv.vote_event_id,
          mv.person_id,
          mv.vote_choice,
          mv.group_code,
          e.vote_date,
          e.legislature,
          e.source_id
        FROM parl_vote_member_votes mv
        JOIN parl_vote_events e ON e.vote_event_id = mv.vote_event_id
        """
    )


def event_party_counts(
    conn: sqlite3.Connection,
    events: dict[str, dict[str, Any]],
    mandate_index: dict[tuple[int, str], list[dict[str, Any]]],
    args: argparse.Namespace,
) -> tuple[dict[str, dict[int, dict[str, int]]], dict[tuple[str, int], int], int]:
    counts_by_event: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"yes": 0, "no": 0, "abstain": 0, "no_vote": 0, "other": 0}))
    party_direction_map: dict[tuple[str, int], int] = {}

    resolver_cache: dict[tuple[int, str, int | None], dict[str, Any] | None] = {}
    total_rows = 0

    for row in iter_vote_rows(conn):
        total_rows += 1
        event_id = safe_text(row["vote_event_id"])
        if not event_id or event_id not in events:
            continue

        vote_dir = normalize_vote_choice(row["vote_choice"])
        person_id = to_int_or_none(row["person_id"])
        source_id = safe_text(row["source_id"])
        date_ord = parse_event_date(row["vote_date"])

        # Direccion partidaria temporal para formar el vector partido-evento.
        party_row = resolve_party_for_vote(mandate_index, resolver_cache, person_id, source_id, date_ord)
        if not party_row:
            continue

        party_id = int(party_row["party_id"])
        counts_by_event[event_id][party_id][vote_dir] += 1

    # Precalcular conteo total de directivas por partido para limitar pares extremos.
    for event_id, party_counts in counts_by_event.items():
        for party_id, counter in party_counts.items():
            directional = (counter["yes"] + counter["no"])
            party_direction_map[(event_id, party_id)] = directional

    return counts_by_event, party_direction_map, total_rows


def compute_event_outcome_payload(
    events: dict[str, dict[str, Any]],
    party_counts: dict[str, dict[int, dict[str, int]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary = {"passed": 0, "failed": 0, "tied": 0, "no_signal": 0}
    pivotal_rows: list[dict[str, Any]] = []

    for event_id, event in events.items():
        outcome = event["outcome"]
        summary[outcome] = summary.get(outcome, 0) + 1
        margin = event["margin"]
        totals = {
            "yes": event.get("totals_yes", 0),
            "no": event.get("totals_no", 0),
            "abstain": event.get("totals_abstain", 0),
            "no_vote": event.get("totals_no_vote", 0),
            "present": event.get("totals_present", 0),
            "margin": margin,
            "total_signal": event.get("total_signal", 0),
        }

        pivotals: list[dict[str, Any]] = []
        for party_id, c in party_counts.get(event_id, {}).items():
            party_diff = (c["yes"] - c["no"])
            party_total = c["yes"] + c["no"] + c["abstain"] + c["no_vote"] + c["other"]
            if party_total <= 0:
                continue

            # Cálculo mínimo de pivotalidad: si quitar el sesgo partidista cambia el signo del margen.
            is_pivotal = False
            if totals["yes"] + totals["no"] > 0:
                if outcome == "passed" and (margin - party_diff) <= 0:
                    is_pivotal = True
                elif outcome == "failed" and (margin - party_diff) >= 0:
                    is_pivotal = True

            if is_pivotal:
                pivotals.append({
                    "party_id": party_id,
                    "swing_if_removed": abs(margin - party_diff),
                    "party_diff": party_diff,
                    "yes": c["yes"],
                    "no": c["no"],
                    "abstain": c["abstain"],
                    "no_vote": c["no_vote"],
                })

        pivotals.sort(key=lambda row: (abs(row["party_diff"]), row["swing_if_removed"]))

        payload = {
            "vote_event_id": event_id,
            "source_bucket": event["source_bucket"],
            "source_id": event["source_id"],
            "source_url": event.get("source_url", ""),
            "vote_date": event["vote_date"],
            "legislature": event["legislature"],
            "title": event["title"],
            "vote_subject": event.get("vote_subject", ""),
            "topic": event["topic"],
            "context": event["context"],
            "initiative_id": event.get("initiative_id", ""),
            "initiative_title": event.get("initiative_title", ""),
            "initiative_expediente": event.get("initiative_expediente", ""),
            "initiative_type": event.get("initiative_type", ""),
            "initiative_source_url": event.get("initiative_source_url", ""),
            "initiative_doc_url": event.get("initiative_doc_url", ""),
            "initiative_link_method": event.get("initiative_link_method", ""),
            "initiative_link_confidence": event.get("initiative_link_confidence"),
            "quality": event.get("quality", {}),
            "outcome": outcome,
            "totals": totals,
            "pivotal_parties": pivotals[:6],
        }
        pivotal_rows.append(payload)

    # Ordena para UI enfocada en votaciones de alta sensibilidad.
    pivotal_rows.sort(
        key=lambda row: (
            0 if row["outcome"] == "tied" else 1,
            abs(row["totals"]["yes"] - row["totals"]["no"]),
        )
    )
    return pivotal_rows, summary


def party_vectors_for_similarity(
    events: dict[str, dict[str, Any]],
    party_counts: dict[str, dict[int, dict[str, int]]],
    min_events_per_party: int,
) -> tuple[
    dict[tuple[str, str], dict[int, dict[str, int]]],
    dict[tuple[str, str, str], dict[int, dict[str, int]]],
    dict[int, str],
]:
    scope_vectors: dict[tuple[str, str], dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    topic_vectors: dict[tuple[str, str, str], dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))

    # First pass: build raw party->event sign vectors.
    party_event_support_counts: dict[tuple[str, str], dict[int, int]] = defaultdict(dict)

    for event_id, party_map in party_counts.items():
        event = events[event_id]
        scope = (event["source_bucket"], event.get("legislature") or "all")
        topic = event.get("topic") or "Sin tema"

        for party_id, counts in party_map.items():
            if counts["yes"] + counts["no"] == 0:
                continue

            if counts["yes"] > counts["no"]:
                direction = 1
            elif counts["no"] > counts["yes"]:
                direction = -1
            else:
                continue

            scope_vectors[scope][party_id][event_id] = direction
            topic_vectors[(scope[0], scope[1], topic)][party_id][event_id] = direction
            party_event_support_counts[scope, party_id] = {
                "count": len(scope_vectors[scope][party_id]),
            }

    # Descarta partidos con pocas observaciones antes de comparar.
    filtered_scope_vectors: dict[tuple[str, str], dict[int, dict[str, int]]] = {}
    for scope, parties in scope_vectors.items():
        kept = {
            party_id: events_for_party
            for party_id, events_for_party in parties.items()
            if len(events_for_party) >= min_events_per_party
        }
        filtered_scope_vectors[scope] = kept

    filtered_topic_vectors: dict[tuple[str, str, str], dict[int, dict[str, int]]] = {}
    for scope_topic, parties in topic_vectors.items():
        kept = {
            party_id: events_for_party
            for party_id, events_for_party in parties.items()
            if len(events_for_party) >= min_events_per_party
        }
        filtered_topic_vectors[scope_topic] = kept

    return filtered_scope_vectors, filtered_topic_vectors


def compute_pair_similarity(vectors: dict[int, dict[str, int]]) -> dict[tuple[int, int], dict[str, Any]]:
    party_ids = list(vectors.keys())
    out: dict[tuple[int, int], dict[str, Any]] = {}

    for i in range(len(party_ids)):
        p1 = party_ids[i]
        v1 = vectors[p1]
        set1 = set(v1.keys())
        yes1 = {k for k, val in v1.items() if val > 0}
        no1 = {k for k, val in v1.items() if val < 0}

        for j in range(i + 1, len(party_ids)):
            p2 = party_ids[j]
            v2 = vectors[p2]
            shared = set1 & set(v2.keys())
            if not shared:
                continue

            # coseno simplificado en vectores {-1, +1}; equivalente a media de signos.
            same = 0
            for e in shared:
                v1v = v1[e]
                v2v = v2[e]
                same += 1 if v1v == v2v else -1

            cosine = round(same / len(shared), 4)

            yes2 = {k for k, val in v2.items() if val > 0}
            no2 = {k for k, val in v2.items() if val < 0}
            agree = len(yes1 & yes2) + len(no1 & no2)
            union = len(yes1 | yes2) + len(no1 | no2)
            jaccard = round(agree / union, 4) if union else 0.0

            out[(p1, p2)] = {
                "shared_events": len(shared),
                "cosine": cosine,
                "jaccard": jaccard,
            }

    return out


def top_pairs_for_scope(
    vectors_by_scope: dict[tuple[str, str], dict[int, dict[str, int]]],
    parties: dict[int, PartyAgg],
    min_shared_events: int,
    top_n: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for (source_bucket, legislature), party_vectors in vectors_by_scope.items():
        pair_stats = compute_pair_similarity(party_vectors)
        for (p1, p2), stats in pair_stats.items():
            if stats["shared_events"] < min_shared_events:
                continue

            p1_meta = parties.get(p1)
            p2_meta = parties.get(p2)
            out.append(
                {
                    "scope": f"{source_bucket}:{legislature or 'all'}",
                    "party_1_id": p1,
                    "party_1_name": p1_meta.party_name if p1_meta else f"Partido {p1}",
                    "party_1_acronym": p1_meta.party_acronym if p1_meta else None,
                    "party_2_id": p2,
                    "party_2_name": p2_meta.party_name if p2_meta else f"Partido {p2}",
                    "party_2_acronym": p2_meta.party_acronym if p2_meta else None,
                    "shared_events": stats["shared_events"],
                    "cosine": stats["cosine"],
                    "jaccard": stats["jaccard"],
                }
            )

    out.sort(key=lambda row: (-(row["cosine"]), -row["shared_events"], row["scope"], row["party_1_name"]))
    return out[:top_n]


def issue_coalitions(
    vectors_by_scope: dict[tuple[str, str], dict[int, dict[str, int]]],
    topic_vectors: dict[tuple[str, str, str], dict[int, dict[str, int]]],
    parties: dict[int, PartyAgg],
    min_shared_events: int,
    min_topic_events: int,
    top_n: int,
) -> list[dict[str, Any]]:
    global_pairs_by_scope: dict[tuple[str, str], dict[tuple[int, int], dict[str, Any]]] = {}
    for scope, vectors in vectors_by_scope.items():
        global_pairs_by_scope[scope] = compute_pair_similarity(vectors)

    out: list[dict[str, Any]] = []
    for (source_bucket, legislature, topic), vectors in topic_vectors.items():
        scope = (source_bucket, legislature)
        topic_stats = compute_pair_similarity(vectors)
        global_stats = global_pairs_by_scope.get(scope, {})

        for (p1, p2), tstat in topic_stats.items():
            shared = tstat["shared_events"]
            if shared < min_topic_events:
                continue

            gstat = global_stats.get((p1, p2))
            g = gstat["cosine"] if gstat else 0.0
            if tstat["cosine"] >= 0.75 and g <= 0.40:
                p1_meta = parties.get(p1)
                p2_meta = parties.get(p2)
                out.append(
                    {
                        "scope": f"{source_bucket}:{legislature or 'all'}",
                        "topic": topic,
                        "party_1_id": p1,
                        "party_1_name": p1_meta.party_name if p1_meta else f"Partido {p1}",
                        "party_1_acronym": p1_meta.party_acronym if p1_meta else None,
                        "party_2_id": p2,
                        "party_2_name": p2_meta.party_name if p2_meta else f"Partido {p2}",
                        "party_2_acronym": p2_meta.party_acronym if p2_meta else None,
                        "topic_shared_events": shared,
                        "topic_cosine": tstat["cosine"],
                        "topic_jaccard": tstat["jaccard"],
                        "global_cosine": g,
                        "global_jaccard": gstat["jaccard"] if gstat else 0.0,
                        "topic_minus_global": round(tstat["cosine"] - g, 4),
                    }
                )

    out.sort(key=lambda row: (-row["topic_minus_global"], -row["topic_shared_events"], row["topic"]))
    return out[:top_n]


def person_name_map(conn: sqlite3.Connection, person_ids: set[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    if not person_ids:
        return names

    ids = sorted(person_ids)
    chunks = [ids[i : i + 500] for i in range(0, len(ids), 500)]
    for chunk in chunks:
        placeholders = ",".join(["?"] * len(chunk))
        rows = conn.execute(
            f"SELECT person_id, full_name FROM persons WHERE person_id IN ({placeholders})",
            chunk,
        ).fetchall()
        for row in rows:
            names[row["person_id"]] = safe_text(row["full_name"]) or f"Persona {row['person_id']}"
    return names


def compute_disciplines(
    conn: sqlite3.Connection,
    args: argparse.Namespace,
    events: dict[str, dict[str, Any]],
    party_counts: dict[str, dict[int, dict[str, int]]],
    mandate_index: dict[tuple[int, str], list[dict[str, Any]]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[int, dict[str, Any]],
]:
    resolver_cache: dict[tuple[int, str, int | None], dict[str, Any] | None] = {}

    person_raw = defaultdict(lambda: {
        "total_votes": 0,
        "directional_votes": 0,
        "aligned": 0,
        "rebels": 0,
        "yes": 0,
        "no": 0,
        "abstain": 0,
        "no_vote": 0,
        "other": 0,
        "party_id": None,
        "party_name": None,
        "party_acronym": None,
        "scope_votes": defaultdict(int),
        "topic_votes": defaultdict(int),
    })

    # party_id -> stats
    party_raw = defaultdict(lambda: {
        "party_id": None,
        "total_votes": 0,
        "directional_votes": 0,
        "aligned": 0,
        "rebels": 0,
        "yes": 0,
        "no": 0,
        "abstain": 0,
        "no_vote": 0,
        "other": 0,
        "scope_map": defaultdict(int),
        "topic_map": defaultdict(int),
    })

    party_scope_raw = defaultdict(lambda: {
        "total_votes": 0,
        "directional_votes": 0,
        "aligned": 0,
        "rebels": 0,
    })

    party_topic_raw = defaultdict(lambda: {
        "total_votes": 0,
        "directional_votes": 0,
        "aligned": 0,
        "rebels": 0,
    })

    attendance_party_context = defaultdict(lambda: {
        "yes": 0,
        "no": 0,
        "abstain": 0,
        "no_vote": 0,
        "other": 0,
        "context_votes": 0,
    })

    attendance_member_context = defaultdict(lambda: {
        "yes": 0,
        "no": 0,
        "abstain": 0,
        "no_vote": 0,
        "other": 0,
        "context_votes": 0,
    })

    vote_rows_total = 0

    event_party_position: dict[tuple[str, int], str] = {}
    for event_id, parties in party_counts.items():
        for party_id, counts in parties.items():
            if counts["yes"] + counts["no"] == 0:
                continue
            if counts["yes"] > counts["no"]:
                event_party_position[(event_id, party_id)] = "yes"
            elif counts["no"] > counts["yes"]:
                event_party_position[(event_id, party_id)] = "no"
            else:
                event_party_position[(event_id, party_id)] = "tie"

    for row in iter_vote_rows(conn):
        vote_rows_total += 1
        event_id = safe_text(row["vote_event_id"])
        if not event_id or event_id not in events:
            continue

        vote_dir = normalize_vote_choice(row["vote_choice"])
        person_id = to_int_or_none(row["person_id"])
        source_id = safe_text(row["source_id"])
        date_ord = parse_event_date(row["vote_date"])
        legislature = safe_text(row["legislature"])

        event = events[event_id]
        context = event["context"]
        topic = event["topic"]

        party_row = resolve_party_for_vote(mandate_index, resolver_cache, person_id, source_id, date_ord)
        party_id = int(party_row["party_id"]) if party_row else None

        if person_id:
            pstat = person_raw[person_id]
            pstat["total_votes"] += 1
            pstat[vote_dir] += 1
            pstat["scope_votes"][f"{source_bucket(source_id)}:{legislature or 'all'}"] += 1
            pstat["topic_votes"][topic] += 1

            if party_row:
                pstat["party_id"] = party_id
                pstat["party_name"] = party_row["party_name"]
                pstat["party_acronym"] = party_row["party_acronym"]

            if vote_dir in {"yes", "no"}:
                pstat["directional_votes"] += 1

                pdir = event_party_position.get((event_id, party_id)) if party_id is not None else None
                if pdir in {"yes", "no"}:
                    if vote_dir == pdir:
                        pstat["aligned"] += 1
                    else:
                        pstat["rebels"] += 1

            attendance_member_context[(person_id, context)][vote_dir] += 1
            attendance_member_context[(person_id, context)]["context_votes"] += 1

        if not party_id:
            continue

        sstat = party_raw[party_id]
        sstat["party_id"] = party_id
        sstat[vote_dir] += 1
        sstat["total_votes"] += 1
        sstat["scope_map"][f"{source_bucket(source_id)}:{legislature or 'all'}"] += 1
        sstat["topic_map"][topic] += 1

        if vote_dir in {"yes", "no"}:
            sstat["directional_votes"] += 1

            pdir = event_party_position.get((event_id, party_id))
            if pdir in {"yes", "no"}:
                if vote_dir == pdir:
                    sstat["aligned"] += 1
                else:
                    sstat["rebels"] += 1

        party_scope_key = (party_id, source_bucket(source_id), legislature or "all")
        scope_stats = party_scope_raw[party_scope_key]
        scope_stats["total_votes"] += 1
        scope_stats["directional_votes"] += 1 if vote_dir in {"yes", "no"} else 0
        pdir = event_party_position.get((event_id, party_id))
        if vote_dir in {"yes", "no"} and pdir in {"yes", "no"}:
            if vote_dir == pdir:
                scope_stats["aligned"] += 1
            else:
                scope_stats["rebels"] += 1

        topic_key = (party_id, topic)
        topic_stats = party_topic_raw[topic_key]
        topic_stats["total_votes"] += 1
        topic_stats["directional_votes"] += 1 if vote_dir in {"yes", "no"} else 0
        pdir = event_party_position.get((event_id, party_id))
        if vote_dir in {"yes", "no"} and pdir in {"yes", "no"}:
            if vote_dir == pdir:
                topic_stats["aligned"] += 1
            else:
                topic_stats["rebels"] += 1

        attendance_party_context[(party_id, context)][vote_dir] += 1
        attendance_party_context[(party_id, context)]["context_votes"] += 1

    # Nombres para personas (para evitar N+1 en la renderización).
    persons = person_name_map(conn, set(person_raw.keys()))

    member_rows = []
    for person_id, stats in person_raw.items():
        directional = stats["directional_votes"]
        members_total = stats["total_votes"]
        if directional == 0 and members_total == 0:
            continue

        aligned = stats["aligned"]
        rebels = stats["rebels"]
        member_rows.append(
            {
                "person_id": person_id,
                "full_name": persons.get(person_id, f"Persona {person_id}"),
                "party_id": stats["party_id"],
                "party_name": stats["party_name"],
                "party_acronym": stats["party_acronym"],
                "total_votes": members_total,
                "directional_votes": directional,
                "yes": stats["yes"],
                "no": stats["no"],
                "abstain": stats["abstain"],
                "no_vote": stats["no_vote"],
                "other": stats["other"],
                "aligned": aligned,
                "rebels": rebels,
                "discipline_rate_pct": float_pct(aligned, directional),
                "rebellion_rate_pct": float_pct(rebels, directional),
                "absence_rate_pct": float_pct(stats["no_vote"], members_total),
                "abstention_rate_pct": float_pct(stats["abstain"], members_total),
                "top_scopes": [
                    {
                        "scope": scope,
                        "votes": qty,
                    }
                    for scope, qty in sorted(stats["scope_votes"].items(), key=lambda item: item[1], reverse=True)[:6]
                ],
                "top_topics": [
                    {
                        "topic": topic_name,
                        "votes": qty,
                    }
                    for topic_name, qty in sorted(stats["topic_votes"].items(), key=lambda item: item[1], reverse=True)[:6]
                ],
            }
        )

    member_rows.sort(key=lambda row: (-row["rebellion_rate_pct"], -row["directional_votes"], row["full_name"]))

    party_rows = []
    for party_id, stats in party_raw.items():
        directional = stats["directional_votes"]
        total_votes = stats["total_votes"]
        if directional == 0 and total_votes == 0:
            continue

        party_rows.append(
            {
                "party_id": party_id,
                "total_votes": total_votes,
                "directional_votes": directional,
                "yes": stats["yes"],
                "no": stats["no"],
                "abstain": stats["abstain"],
                "no_vote": stats["no_vote"],
                "other": stats["other"],
                "aligned": stats["aligned"],
                "rebels": stats["rebels"],
                "discipline_rate_pct": float_pct(stats["aligned"], directional),
                "rebellion_rate_pct": float_pct(stats["rebels"], directional),
            }
        )

    party_rows.sort(key=lambda row: (-row["rebellion_rate_pct"], -row["directional_votes"], row["party_id"]))

    party_scope_rows = []
    for (party_id, source, legislature), stats in party_scope_raw.items():
        directional = stats["directional_votes"]
        if directional == 0:
            continue
        party_scope_rows.append(
            {
                "party_id": party_id,
                "scope": f"{source}:{legislature}",
                "directional_votes": directional,
                "aligned": stats["aligned"],
                "rebels": stats["rebels"],
                "discipline_rate_pct": float_pct(stats["aligned"], directional),
                "rebellion_rate_pct": float_pct(stats["rebels"], directional),
            }
        )
    party_scope_rows.sort(key=lambda row: (-row["rebellion_rate_pct"], row["scope"], row["party_id"]))

    party_topic_rows = []
    for (party_id, topic), stats in party_topic_raw.items():
        directional = stats["directional_votes"]
        if directional == 0:
            continue
        party_topic_rows.append(
            {
                "party_id": party_id,
                "topic": topic,
                "directional_votes": directional,
                "aligned": stats["aligned"],
                "rebels": stats["rebels"],
                "discipline_rate_pct": float_pct(stats["aligned"], directional),
                "rebellion_rate_pct": float_pct(stats["rebels"], directional),
            }
        )
    party_topic_rows.sort(key=lambda row: (-row["rebellion_rate_pct"], row["topic"], row["party_id"]))

    member_context_rows = []
    for (person_id, context), stats in attendance_member_context.items():
        total = stats["context_votes"]
        if total == 0:
            continue
        member_context_rows.append(
            {
                "person_id": person_id,
                "context": context,
                "total_votes": total,
                "yes": stats["yes"],
                "no": stats["no"],
                "abstain": stats["abstain"],
                "no_vote": stats["no_vote"],
                "absence_rate_pct": float_pct(stats["no_vote"], total),
                "abstention_rate_pct": float_pct(stats["abstain"], total),
            }
        )
    member_context_rows.sort(key=lambda row: (-row["absence_rate_pct"], -row["total_votes"]))

    party_context_rows = []
    for (party_id, context), stats in attendance_party_context.items():
        total = stats["context_votes"]
        if total == 0:
            continue
        party_context_rows.append(
            {
                "party_id": party_id,
                "context": context,
                "total_votes": total,
                "yes": stats["yes"],
                "no": stats["no"],
                "abstain": stats["abstain"],
                "no_vote": stats["no_vote"],
                "presence_rate_pct": float_pct(stats["yes"] + stats["no"] + stats["abstain"], total),
                "absence_rate_pct": float_pct(stats["no_vote"], total),
            }
        )
    party_context_rows.sort(key=lambda row: (row["party_id"], row["context"]))

    return (
        member_rows,
        party_rows,
        party_scope_rows,
        party_topic_rows,
        member_context_rows[:400],
        party_raw,
        party_context_rows,
    )


def assemble_output(
    args: argparse.Namespace,
    events: dict[str, dict[str, Any]],
    member_rows: list[dict[str, Any]],
    party_rows: list[dict[str, Any]],
    party_scope_rows: list[dict[str, Any]],
    party_topic_rows: list[dict[str, Any]],
    member_context_rows: list[dict[str, Any]],
    party_context_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
    outcome_summary: dict[str, int],
    coalition_rows: list[dict[str, Any]],
    issue_rows: list[dict[str, Any]],
    parties: dict[int, PartyAgg],
) -> dict[str, Any]:
    total_events = len(events)
    with_data_rows = [
        row
        for row in outcome_rows
        if row["outcome"] in {"passed", "failed", "tied", "no_signal"}
    ]

    latest_events = events.values()
    latest_preview = sorted(
        latest_events,
        key=lambda ev: (safe_text(ev["vote_date"]) or "", ev["vote_event_id"]),
        reverse=True,
    )[: min(args.max_rows_events, total_events)]

    event_preview = []
    for row in latest_preview:
        event_preview.append(
            {
                "vote_event_id": row["vote_event_id"],
                "source_bucket": row["source_bucket"],
                "vote_date": row["vote_date"],
                "legislature": row["legislature"],
                "outcome": row["outcome"],
                "vote_subject": row.get("vote_subject", ""),
                "topic": row["topic"],
                "context": row["context"],
                "margin": row["margin"],
                "initiative_id": row.get("initiative_id", ""),
                "source_url": row.get("source_url", ""),
                "quality": row.get("quality", {}),
                "yes": row["totals_yes"],
                "no": row["totals_no"],
                "abstain": row["totals_abstain"],
                "no_vote": row["totals_no_vote"],
            }
        )

    party_payload = []
    for pid, agg in parties.items():
        party_payload.append(
            {
                "party_id": pid,
                "name": agg.party_name,
                "acronym": agg.party_acronym,
            }
        )
    party_payload.sort(key=lambda row: row["name"])

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total_events": total_events,
            "max_rows_events": args.max_rows_events,
            "min_shared_events": args.min_shared_events,
            "min_events_per_party": args.min_events_per_party,
            "min_events_topic_pairs": args.min_events_topic_pairs,
        },
        "parties": party_payload,
        "events_preview": event_preview,
        "discipline": {
            "members": member_rows[:300],
            "members_count": len(member_rows),
            "parties": party_rows[:240],
            "parties_count": len(party_rows),
            "parties_by_legislature": party_scope_rows[:300],
            "parties_by_topic": party_topic_rows[:300],
            "attendance_by_member_context": member_context_rows,
            "attendance_by_party_context": party_context_rows,
        },
        "coalitions": {
            "pairs": coalition_rows,
            "issue_coalitions": issue_rows,
        },
        "outcomes": {
            "summary": outcome_summary,
            "samples": with_data_rows[:600],
            "critical_by_margin": [row for row in outcome_rows if row["outcome"] != "no_signal"][:200],
        },
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: no existe la DB -> {db_path}")
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        events = build_event_map(conn)
        mandate_index, parties, _ = build_mandate_index(conn)

        party_direction_counts, _, _ = event_party_counts(
            conn,
            events,
            mandate_index,
            args,
        )

        outcome_rows, outcome_summary = compute_event_outcome_payload(events, party_direction_counts)
        member_rows, party_rows, party_scope_rows, party_topic_rows, member_context_rows, _party_raw, party_context_rows = compute_disciplines(
            conn,
            args,
            events,
            party_direction_counts,
            mandate_index,
        )

        vectors_scope, vectors_topic = party_vectors_for_similarity(
            events,
            party_direction_counts,
            args.min_events_per_party,
        )

        coalition_rows = top_pairs_for_scope(
            vectors_scope,
            parties,
            args.min_shared_events,
            top_n=240,
        )
        issue_rows = issue_coalitions(
            vectors_scope,
            vectors_topic,
            parties,
            args.min_shared_events,
            args.min_events_topic_pairs,
            top_n=240,
        )

        payload = assemble_output(
            args,
            events,
            member_rows,
            party_rows,
            party_scope_rows,
            party_topic_rows,
            member_context_rows,
            party_context_rows,
            outcome_rows,
            outcome_summary,
            coalition_rows,
            issue_rows,
            parties,
        )

        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print(
            f"OK accountability snapshot -> {out_path} (events={payload['meta']['total_events']} "
            f"members={payload['discipline']['members_count']} parties={len(payload['parties'])} "
            f"pair_similarity={len(payload['coalitions']['pairs'])} issue_coalitions={len(payload['coalitions']['issue_coalitions'])})"
        )
        return 0
    except sqlite3.Error as exc:
        print(f"ERROR SQL: {exc}")
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
