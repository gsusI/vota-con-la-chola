#!/usr/bin/env python3
"""Export the open-ended question pool for the voting aid: real Congreso votes that split parties.

Each item is one roll-call vote (bill taken into consideration, decree-law, motion, non-binding
motion or final vote). The question is the official title with the proposer removed (shown only
after answering, so it does not steer the answer); "agree" always means voting Sí. Party positions
use the same majority rule and ballot-party mapping as the curated statements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.export_voting_aid_snapshot import (  # noqa: E402
    DEFAULT_SEED,
    majority_choice,
    party_resolver,
    vote_position,
)

POOL_SCHEMA_VERSION = "voting_aid_pool_v1"

KIND_QUESTIONS = {
    "toma": "¿Debería el Congreso tramitar esta ley?",
    "final": "¿Debería aprobarse esta ley?",
    "rdl": "¿Debería aprobarse este decreto ley del Gobierno?",
    "pnl": "¿Debería el Congreso pedir esto al Gobierno?",
    "mocion": "¿Debería el Congreso aprobar esta moción?",
}
KIND_LABELS = {
    "toma": "Proposición de ley (toma en consideración)",
    "final": "Votación final de una ley",
    "rdl": "Convalidación de un decreto ley",
    "pnl": "Proposición no de ley",
    "mocion": "Moción",
}

# Keyword -> theme, first match wins (checked against the lower-cased title).
THEME_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Política exterior", ("israel", "palestin", "gaza", "ucrania", "rusia", "sáhara", "marruecos", "otan", "venezuela", "oriente medio", "irán", "unión europea", "unrwa", "cuba", "estados unidos", "cooperación al desarrollo", "internacional")),
    ("Defensa", ("defensa nacional", "militar", "fuerzas armadas", "ejército", "armamento")),
    ("Servicios sociales", ("dependencia", "vulnerabilidad", "ingreso mínimo", "familias", "infancia", "pobreza", "cuidados")),
    ("Modelo territorial", ("cataluña", "catalunya", "país vasco", "navarra", "galicia", "concierto económico", "convenio económico", "financiación autonómica", "financiación territorial", "financiación singular", "amnistía", "estatuto de autonomía", "comunidades autónomas", "ap-9", "formentera")),
    ("Vivienda", ("vivienda", "alquiler", "arrendamiento", "hipotec", "inmobiliari", "ocupación ilegal", "desahucio", "suelo", "urbanístic")),
    ("Empleo y pensiones", ("trabajador", "empleo", "laboral", "jornada", "salario", "pensi", "jubilación", "seguridad social", "desempleo", "autónomos")),
    ("Sanidad", ("sanitari", "salud", "sanidad", "médic", "enfermer", "farmac", "medicament", "eutanasia", "hospital", "cribado")),
    ("Educación", ("educa", "universi", "escolar", "alumnado", "profesor", "fp")),
    ("Energía y clima", ("energ", "eléctric", "nuclear", "clima", "pacto verde", "renovable", "emisiones")),
    ("Transporte", ("transporte", "ferrovi", "tren", "carretera", "tráfico", "conducción", "autopista", "aéreo", "movilidad")),
    ("Inmigración", ("extranjer", "migra", "asilo", "nacionalidad", "regularización")),
    ("Corrupción y transparencia", ("corrupción", "transparencia", "grupos de interés", "secretos oficiales", "fraude", "tribunal de cuentas")),
    ("Seguridad y justicia", ("código penal", "penal", "penitenciari", "prisión", "policía", "guardia civil", "seguridad ciudadana", "seguridad nacional", "terroris", "eta", "narcotráfico", "interior", "justicia", "judicial", "jueces", "fiscalía", "tribunal constitucional", "okupa", "delito")),
    ("Igualdad", ("mujer", "igualdad", "lgtbi", "orgullo", "violencia de género", "violencia vicaria", "discapacidad", "paritari", "terapias de conversión", "menores")),
    ("Campo y mundo rural", ("agrari", "ganader", "agricult", "pesca", "rural", "agua", "hídric", "trasvase", "lobo", "alimentari", "incendios", "dana", "la palma")),
    ("Impuestos y economía", ("impuesto", "tributari", "fiscal", "gravamen", "presupuest", "banca", "estabilidad", "deuda", "arancel", "iva", "economía", "económic", "empresa", "comercio", "inflación", "precios", "industria", "pymes", "turismo")),
    ("Instituciones", ("reglamento del congreso", "régimen electoral", "constitución", "cgpj", "consejo general del poder judicial", "rtve", "radio televisión")),
    ("Cultura", ("tauromaquia", "cultura", "cine", "deporte", "lenguas", "plurilingüismo", "memoria democrática")),
]

PROPOSER_RE = re.compile(
    r"^(?:(?P<head>Proposición de Ley|Proposición no de Ley|Moción consecuencia de interpelación urgente|Proposición)\s+)?"
    r"(?:(?P<prep>del|de los|de las|de la|de)\s+)?"
    r"(?P<rest>(?:Grupos? Parlamentari|Sr\.|Sra\.|Parlamento|Asamblea|Cortes|Junta General|Diputad).*)$",
    re.S | re.I,
)
REST_SPLIT_RE = re.compile(
    r",\s+(?=(?:Orgánica|orgánica|relativ|referid|sobre|para|de |del |por |en |a |al |que |contra|reguladora|con |acerca|ante ))"
)
# Fallback when the proposer is not followed by a comma ("... Socialista sobre programa ...").
REST_SPLIT_NOCOMMA_RE = re.compile(r"\s+(?=(?:sobre|relativa|relativo|para la|para el|por la que|de medidas)\b)")
GROUP_MENTION_RE = re.compile(r"(el|del?|de los)?\s*Grupos? Parlamentari[oa]s?\s+[^,]*", re.I)
VOTED_TERMS_RE = re.compile(r"\.?\s*Se vota(n)? en los términos.*$", re.S)
KIND_HEADS = {"pnl": "Proposición no de ley", "mocion": "Moción", "toma": "Proposición de ley", "final": "Proposición de ley"}
EXPEDIENTE_NOTE_RE = re.compile(r"\s*\(corresponde a[^)]*\)", re.I)
FINAL_PREFIX_RE = re.compile(r"^Votación de conjunto( del texto)?( de la| del)?\s+", re.I)


def classify(title: str, expediente: str, subgroup_title: str) -> str | None:
    title, expediente, sg = title or "", expediente or "", (subgroup_title or "").strip()
    if sg.startswith("Votación de conjunto") or expediente.startswith("Votación de conjunto"):
        return "final"
    if title.startswith("Toma en consideración") and not sg:
        return "toma"
    if title.startswith("Convalidación") and expediente.startswith("Real Decreto-ley"):
        return "rdl"
    if title.startswith("Proposiciones no de Ley") and not sg:
        return "pnl"
    if title.startswith("Mociones consecuencia") and not sg:
        return "mocion"
    return None


def anonymize_title(text: str, kind: str | None = None) -> tuple[str, str | None]:
    """Remove the proposing group from an official title; return (title, proposer)."""
    clean = EXPEDIENTE_NOTE_RE.sub("", " ".join(str(text or "").split())).strip()
    clean = FINAL_PREFIX_RE.sub("", clean)
    clean = VOTED_TERMS_RE.sub(".", clean).rstrip(".") + "."
    proposer = None
    m = PROPOSER_RE.match(clean)
    if m:
        rest = m.group("rest")
        split = REST_SPLIT_RE.search(rest) or REST_SPLIT_NOCOMMA_RE.search(rest)
        if split:
            proposer = rest[: split.start()].strip()
            remainder = rest[split.end():].strip()
            raw_head = (m.group("head") or "").lower()
            if raw_head.startswith("moción"):
                head = "Moción"
            elif raw_head.startswith("proposición no de ley"):
                head = "Proposición no de ley"
            elif raw_head.startswith("proposición de ley"):
                head = "Proposición de ley"
            elif raw_head:
                head = "Proposición"
            else:
                head = KIND_HEADS.get(kind or "", "Iniciativa")
            if remainder[:8].lower() == "orgánica":
                head += " orgánica"
                remainder = remainder[8:].lstrip(" ,")
            clean = f"{head} {remainder}".strip()
    # Safety net: never show which group proposed it before the user answers.
    clean = GROUP_MENTION_RE.sub(" de un grupo parlamentario", clean)
    clean = re.sub(r"\s+", " ", clean).replace(" ,", ",").strip()
    return clean[:1].upper() + clean[1:], proposer


def _key_pattern(key: str) -> re.Pattern[str]:
    # Keys are word starts (stems); short keys must match the whole word ("iva" is not "relativa").
    k = re.escape(key.strip())
    return re.compile(rf"\b{k}\b" if len(key.strip()) <= 5 else rf"\b{k}")


THEME_PATTERNS = [(theme, [_key_pattern(k) for k in keys]) for theme, keys in THEME_RULES]


def theme_for(title: str) -> str:
    low = title.lower()
    for theme, patterns in THEME_PATTERNS:
        if any(p.search(low) for p in patterns):
            return theme
    return "Otros"


def bloc_side(positions: dict[str, str]) -> str:
    a, b = positions.get("psoe"), positions.get("pp")
    if a == "agree" and b != "agree":
        return "psoe"
    if b == "agree" and a != "agree":
        return "pp"
    return "cross"


def first_text_url(links_json: str | None) -> str | None:
    try:
        links = json.loads(links_json or "[]")
    except json.JSONDecodeError:
        return None
    for url in links:
        if isinstance(url, str) and re.search(r"-1\.PDF(#.*)?$", url):
            return url.split("#", 1)[0]
    return None


def build_pool(conn: sqlite3.Connection, seed: dict[str, Any], *, legislature: str, generated_at: str) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    resolve = party_resolver(seed)
    party_ids = [p["party_id"] for p in seed["parties"]]
    curated_votes = {v["vote_event_id"] for st in seed["statements"] for v in st["votes"]}

    candidates = []
    for row in conn.execute(
        """
        SELECT vote_event_id, vote_date, title, expediente_text, subgroup_title, source_url,
               totals_yes, totals_no, totals_abstain
        FROM parl_vote_events
        WHERE source_id = 'congreso_votaciones' AND legislature = ?
        ORDER BY vote_date, vote_event_id
        """,
        (legislature,),
    ):
        kind = classify(row["title"], row["expediente_text"], row["subgroup_title"])
        if kind and row["vote_event_id"] not in curated_votes:
            candidates.append((kind, row))

    ids = [row["vote_event_id"] for _, row in candidates]
    tallies: dict[str, dict[str, Counter]] = {vid: {pid: Counter() for pid in party_ids} for vid in ids}
    for chunk_start in range(0, len(ids), 500):
        chunk = ids[chunk_start: chunk_start + 500]
        marks = ",".join("?" * len(chunk))
        for m in conn.execute(
            f"SELECT vote_event_id, member_name, group_code, vote_choice FROM parl_vote_member_votes WHERE vote_event_id IN ({marks})",
            chunk,
        ):
            pid = resolve(str(m["member_name"] or ""), str(m["group_code"] or ""))
            if pid:
                tallies[m["vote_event_id"]][pid][str(m["vote_choice"] or "")] += 1

    text_urls: dict[str, str] = {}
    for chunk_start in range(0, len(ids), 500):
        chunk = ids[chunk_start: chunk_start + 500]
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(
            f"""
            SELECT vi.vote_event_id, i.links_bocg_json
            FROM parl_vote_event_initiatives vi JOIN parl_initiatives i ON i.initiative_id = vi.initiative_id
            WHERE vi.vote_event_id IN ({marks})
            """,
            chunk,
        ):
            url = first_text_url(r["links_bocg_json"])
            if url and r["vote_event_id"] not in text_urls:
                text_urls[r["vote_event_id"]] = url

    items: list[dict[str, Any]] = []
    seen_titles: dict[str, int] = {}
    for kind, row in candidates:
        vid = row["vote_event_id"]
        positions: dict[str, str] = {}
        counts: dict[str, list[int]] = {}
        for pid in party_ids:
            c = tallies[vid][pid]
            positions[pid] = vote_position(majority_choice(c), "Sí")
            counts[pid] = [c.get("Sí", 0), c.get("No", 0), c.get("Abstención", 0)]
        agree = sum(p == "agree" for p in positions.values())
        disagree = sum(p == "disagree" for p in positions.values())
        if agree == 0 or disagree == 0:
            continue  # unanimous or no data: says nothing about differences
        title, proposer = anonymize_title(row["expediente_text"] or row["title"], kind)
        if kind == "rdl" or (not proposer and title.startswith("Proyecto de Ley")):
            proposer = "Gobierno"
        key = re.sub(r"\W+", " ", title.lower()).strip()
        item = {
            "id": "v-" + hashlib.sha1(vid.encode("utf-8")).hexdigest()[:10],
            "kind": kind,
            "kind_label": KIND_LABELS[kind],
            "question": KIND_QUESTIONS[kind],
            "title": title,
            "proposer": proposer,
            "theme": theme_for(title),
            "vote_date": row["vote_date"],
            "approved": (row["totals_yes"] or 0) > (row["totals_no"] or 0),
            "totals": [row["totals_yes"], row["totals_no"], row["totals_abstain"]],
            "source_url": row["source_url"] or (vid[4:] if vid.startswith("url:") else None),
            "text_url": text_urls.get(vid),
            "vote_event_id": vid,
            "tier": "split" if agree >= 2 and disagree >= 2 else "lone",
            "side": bloc_side(positions),
            "positions": positions,
            "counts": counts,
        }
        # One question per bill: a final vote replaces its earlier consideration vote.
        if key in seen_titles:
            prev = items[seen_titles[key]]
            if kind == "final" or prev["kind"] != "final":
                items[seen_titles[key]] = item
            continue
        seen_titles[key] = len(items)
        items.append(item)

    items.sort(key=lambda it: (it["vote_date"], it["id"]))
    tiers = Counter(it["tier"] for it in items)
    sides = Counter(it["side"] for it in items)
    return {
        "meta": {
            "schema_version": POOL_SCHEMA_VERSION,
            "generated_at": generated_at,
            "legislature": legislature,
            "institution": "Congreso de los Diputados",
            "agree_means": "Sí",
            "items_total": len(items),
            "by_tier": dict(sorted(tiers.items())),
            "by_side": dict(sorted(sides.items())),
            "by_kind": dict(sorted(Counter(it["kind"] for it in items).items())),
            "by_theme": dict(sorted(Counter(it["theme"] for it in items).items())),
            "votes_first_date": items[0]["vote_date"] if items else None,
            "votes_last_date": items[-1]["vote_date"] if items else None,
            "method": "Votaciones nominales del Congreso donde al menos un partido votó Sí y otro No. Título oficial sin el grupo proponente; «de acuerdo» = votar Sí.",
        },
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--seed", default=str(DEFAULT_SEED))
    parser.add_argument("--legislature", default="15")
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-bytes", type=int, default=2_000_000)
    args = parser.parse_args(argv)
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        pool = build_pool(
            conn,
            seed,
            legislature=args.legislature,
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
    finally:
        conn.close()
    body = json.dumps(pool, ensure_ascii=False, separators=(",", ":")) + "\n"
    size = len(body.encode("utf-8"))
    if size > args.max_bytes:
        print(f"ERROR: pool de {size} bytes supera --max-bytes {args.max_bytes}", file=sys.stderr)
        return 4
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    m = pool["meta"]
    print(f"OK voting aid pool -> {args.out} (items={m['items_total']} tiers={m['by_tier']} sides={m['by_side']} bytes={size})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
