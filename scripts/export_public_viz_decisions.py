#!/usr/bin/env python3
"""Party decision ledger for /visualizaciones/decisiones/: what each party voted on measures with legal effect on
employment, the self-employed, healthcare and immigration, set against what evaluations say each measure did.

Subcommands:
- candidates: apply the fixed selection rule (docs/etl/sprints/DECISIONES-20261111/README.md §1-3) to the published
  vote atlas and write the worklist (one entry per measure, with its votes). Nothing is added by hand.
- validate: mechanical gate over the seed (schema, URLs, vote ids in our data, grades A-D, verdict vs grades, wording).
- export (default): merge seed + computed party votes and decisiveness + indicators from the published verticals into
  ui/site/public/visualizaciones/data/decisiones.json and a long CSV.

Party votes are never typed by hand: they are counted from per-deputy votes (vote_atlas_people_v1.json). Indicators
come from the published vertical JSONs (empleo.json, sanidad.json), which carry their own raw-payload provenance.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ATLAS = REPO_ROOT / "ui/site/public/citizen/data/vote_atlas_v1.json"
PEOPLE = REPO_ROOT / "ui/site/public/citizen/data/vote_atlas_people_v1.json"
EMPLEO = REPO_ROOT / "ui/site/public/visualizaciones/data/empleo.json"
SANIDAD = REPO_ROOT / "ui/site/public/visualizaciones/data/sanidad.json"
SEED = REPO_ROOT / "etl/data/seeds/party_decisions_v1.json"
SEED_DIR = REPO_ROOT / "etl/data/seeds/party_decisions_v1.d"
SPRINT = REPO_ROOT / "docs/etl/sprints/DECISIONES-20261111"
WORKLIST = SPRINT / "worklist.json"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/decisiones.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/decisiones.csv"
OFFICIAL_VOTE_PREFIX = "https://www.congreso.es/webpublica/opendata/votaciones/"
ATLAS_URL = "/citizen/vota/temas/"

DOMAINS = ["empleo", "autonomos", "sanidad", "inmigracion"]
DOMAIN_LABELS = {"empleo": "Empleo", "autonomos": "Autónomos", "sanidad": "Sanidad", "inmigracion": "Inmigración y servicios"}
DOMAIN_RULES = {
    "empleo": {
        "axes": {"empleo_derechos"},
        "axes_with_keywords": {"proteccion_social", "fiscalidad"},
        "keywords": r"\bempleo\b|laboral|\btrabajo\b|trabajador|desempleo|jornada|salari|despido|\bERTE|subsidio",
        "budget_sections": {"19"},
    },
    "autonomos": {
        "axes": {"autonomos_empresa"},
        "axes_with_keywords": set(),
        "keywords": r"trabajo autónomo|trabajador(?:es|as)? autónom|emprend|\bpymes?\b|empresas emergentes|morosidad",
        "budget_sections": set(),
    },
    "sanidad": {
        "axes": {"sanidad_publica"},
        "axes_with_keywords": set(),
        "keywords": r"sanidad|sanitari|\bsalud\b|medicament|farmac|hospital",
        "budget_sections": {"26"},
    },
    "inmigracion": {
        "axes": {"inmigracion"},
        "axes_with_keywords": set(),
        "keywords": r"extranjer|migra|asilo|no acompañad|nacionalidad|regularizaci|protección internacional",
        "budget_sections": {"32"},
    },
}
BINDING_KINDS = {"final", "rdl"}
POSITION_KINDS = {"mocion", "mocion_punto", "pnl", "pnl_punto"}
COUNTERFACTUAL_MARGIN = 10
ABSOLUTE_MAJORITY = 176

# XIV groups -> ballot party (deputies in mixed groups keep their own XV party when known).
XIV_GROUP_PARTY = {
    "GS": "psoe", "GP": "pp", "GVOX": "vox", "GR": "erc", "GEH Bildu": "bildu", "GV (EAJ-PNV)": "pnv",
    "GCUP-EC-GC": "up", "GCs": "cs", "GPlu": "plural", "GMx": "mixto",
}
EXTRA_PARTIES = [
    {"party_id": "up", "label": "Unidas Podemos (XIV)", "note": "Grupo de la XIV; hoy sus diputados están en Sumar y Podemos."},
    {"party_id": "cs", "label": "Ciudadanos (XIV)", "note": "Sin escaños desde 2023."},
    {"party_id": "plural", "label": "Grupo Plural (XIV, resto)", "note": "Diputados del Grupo Plural sin partido en la XV."},
    {"party_id": "mixto", "label": "Grupo Mixto (XIV, resto)", "note": "Diputados del Grupo Mixto sin partido en la XV."},
]
GOVERNING = {"psoe": "gobierna en toda la XIV y la XV", "sumar": "gobierna en la XV (antes, Unidas Podemos en la XIV)",
             "up": "gobernó en la XIV (coalición con el PSOE)", "podemos": "gobernó en la XIV dentro de Unidas Podemos; en la XV, fuera del Gobierno"}

VERDICTS = ["positivo", "negativo", "mixto", "no_evaluado"]
VERDICT_LABELS = {"positivo": "Evaluada: positiva", "negativo": "Evaluada: negativa", "mixto": "Evaluada: mixta",
                  "no_evaluado": "Sin evaluación"}
GRADES = {"A", "B", "C", "D"}
CAUSAL_RE = re.compile(r"gracias a|por culpa de|provocó|causó|creó \d|destruyó \d|empleos creados|empleos destruidos", re.I)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------------------------- votes and parties

class Votes:
    def __init__(self, atlas: dict, people: dict):
        self.atlas = atlas
        self.people = people
        self.titles = atlas["titles"]
        self.by_id = {v["id"]: v for v in atlas["votes"]}
        self.index = {row[0]: i for i, row in enumerate(people["votes"])}

    def title(self, vote: dict) -> str:
        return self.titles[vote["t"]] or ""

    def party_counts(self, vote_id: str) -> dict[str, dict[str, int]]:
        """Sí/No/Abstención/no vota per ballot party, from each deputy's own vote."""
        i = self.index[vote_id]
        leg = self.people["votes"][i][6]
        out: dict[str, Counter] = defaultdict(Counter)
        for person in self.people["people"]:
            j = i - person["first"]
            if j < 0 or j >= len(person["votes"]):
                continue
            choice = person["votes"][j]
            if choice == ".":
                continue
            if leg == "14":
                groups = person["groups_by_leg"].get("14") or []
                group = groups[0] if groups else None
                party = XIV_GROUP_PARTY.get(group or "", "mixto")
                if party in {"plural", "mixto"} and person.get("party_id"):
                    party = person["party_id"]
            else:
                party = person.get("party_id") or "mixto"
            out[party][choice] += 1
        return {p: {"S": c["S"], "N": c["N"], "A": c["A"], "no_vota": c["-"]} for p, c in out.items()}


def needs_absolute(title: str) -> bool:
    t = title.lower()
    return "orgánica" in t and "conjunto" in t


def passes(yes: int, no: int, absolute: bool) -> bool:
    return yes >= ABSOLUTE_MAJORITY if absolute else yes > no


def decisiveness(counts: dict, absolute: bool) -> tuple[bool, dict]:
    yes = sum(c["S"] for c in counts.values())
    no = sum(c["N"] for c in counts.values())
    result = passes(yes, no, absolute)
    out = {}
    for party, c in counts.items():
        absent = passes(yes - c["S"], no - c["N"], absolute) != result
        flipped = passes(yes - c["S"] + c["N"], no - c["N"] + c["S"], absolute) != result
        out[party] = {"if_absent": absent, "if_opposite": flipped}
    return result, out


def stance(choice: str, yes_backs: bool) -> str:
    if choice == "A":
        return "abstained"
    if choice in ("S", "N"):
        return "backed" if (choice == "S") == yes_backs else "opposed"
    return "split" if choice == "dividido" else "absent"


def majority(c: dict) -> str:
    ranked = sorted((("S", c["S"]), ("N", c["N"]), ("A", c["A"])), key=lambda kv: -kv[1])
    if ranked[0][1] == 0:
        return "-"
    if ranked[0][1] == ranked[1][1]:
        return "dividido"
    return ranked[0][0]


# ------------------------------------------------------------------------------------------------------ candidates

def law_key(title: str) -> str:
    t = re.sub(r"^\s*votación\s+(conjunta\s+)?de\s+(las\s+)?enmiendas?\s+a\s+la\s+totalidad\s+de\s+(devolución|texto alternativo)\s+(al|a\s+la)\s+", "", title, flags=re.I)
    t = re.sub(r"^\s*(votación\s+(del\s+dictamen|de\s+conjunto)\s+(del\s+texto\s+)?(de\s+la\s+|del\s+)?)", "", t, flags=re.I)
    t = re.split(r",\s+con la incorporación", t, flags=re.I)[0]
    m = re.search(r"Real Decreto-ley (\d+/\d{4})", t)
    if m:
        return f"rdl {m.group(1)}"
    t = re.sub(r"\s+", " ", t.lower()).strip(" .")
    t = re.sub(r"^(proyecto|proposición) de ley", "ley", t)
    return t[:110]


def auto_name(cand: dict) -> str:
    """Readable default name before a measure is documented (the documented `name` replaces it)."""
    title = cand["title"]
    section = budget_section(title)
    if section:
        m = re.match(r"\s*Sección \d{2} \(([^)]*)\)", title)
        return f"Presupuestos 2023, sección {section}" + (f" ({m.group(1)})" if m else "")
    t = re.sub(r"^\s*votación\s+(conjunta\s+de\s+las\s+enmiendas\s+a\s+la\s+totalidad\s+de\s+devolución\s+al|del\s+dictamen\s+(del|de\s+la)|de\s+conjunto\s+(del\s+texto\s+)?(del|de\s+la))\s+", "", title, flags=re.I)
    t = re.sub(r"^(Real Decreto-ley \d+/\d{4}), de \d{1,2} de \w+,?", r"\1:", t)
    t = re.sub(r"^(Proyecto|Proposición) de Ley", "Ley", t).strip(" .")
    if len(t) > 110:
        t = t[:110].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return t


def budget_section(title: str) -> str | None:
    m = re.match(r"\s*Sección (\d{2})\b", title)
    return m.group(1) if m else None


def match_domains(vote: dict, title: str) -> list[str]:
    axes = {a[0] for a in vote.get("axes") or []}
    text = f"{title} {vote.get('summary_yes') or ''}"
    section = budget_section(title)
    out = []
    for domain, rule in DOMAIN_RULES.items():
        if section is not None:
            if section in rule["budget_sections"]:
                out.append(domain)
            continue
        if axes & rule["axes"]:
            out.append(domain)
        elif axes & rule["axes_with_keywords"] and re.search(rule["keywords"], text, re.I):
            out.append(domain)
        elif re.search(rule["keywords"], title, re.I):
            out.append(domain)
    return out


def margin(vote: dict) -> int:
    yes, no, _ = vote["totals"]
    return abs(yes - no)


def build_candidates(votes: Votes) -> list[dict]:
    groups: dict[str, dict] = {}
    for v in votes.atlas["votes"]:
        kind = v["kind"]
        title = votes.title(v)
        if kind not in BINDING_KINDS and kind != "totalidad":
            continue
        domains = match_domains(v, title)
        if not domains:
            continue
        section = budget_section(title)
        if kind == "totalidad":
            # A government bill killed by an approved enmienda a la totalidad, by a narrow margin.
            if not v["approved"] or margin(v) > COUNTERFACTUAL_MARGIN:
                continue
            unit = "contrafactual"
        elif section is not None:
            unit = "presupuesto"
        elif not v["approved"]:
            if margin(v) > COUNTERFACTUAL_MARGIN:
                continue
            unit = "contrafactual"
        else:
            unit = "ley" if kind == "final" else "decreto_ley"
        key = f"pge2023 sección {section}" if section else law_key(title)
        g = groups.setdefault(key, {"key": key, "unit": unit, "domains": set(), "votes": []})
        g["domains"].update(domains)
        g["votes"].append(v)
        if unit == "contrafactual":
            g["unit"] = unit
    out = []
    for key, g in groups.items():
        vs = sorted(g["votes"], key=lambda v: v["date"])
        conj = [v for v in vs if "conjunto" in votes.title(v).lower()]
        main = conj[-1] if conj else vs[-1]
        title = votes.title(main)
        out.append({
            "candidate_key": key,
            "unit": g["unit"],
            "domains": [d for d in DOMAINS if d in g["domains"]],
            "main_vote_id": main["id"],
            "vote_ids": [v["id"] for v in vs],
            "date": main["date"],
            "legislature": main.get("leg", "15"),
            "kind": main["kind"],
            "title": title,
            "summary_yes": main.get("summary_yes"),
            "totals": main["totals"],
            "approved_in_our_data": main["approved"],
            "official_vote_url": OFFICIAL_VOTE_PREFIX + main["path"],
        })
    out.sort(key=lambda c: (c["date"], c["candidate_key"]))
    return out


def position_counts(votes: Votes) -> dict:
    """Non-binding motions per domain axis (confidence alta/media): how many each party backed or opposed."""
    parties = [p["party_id"] for p in votes.atlas["parties"]]
    out = {}
    for domain, rule in DOMAIN_RULES.items():
        per = {p: Counter() for p in parties}
        n = 0
        for v in votes.atlas["votes"]:
            if v["kind"] not in POSITION_KINDS:
                continue
            if not any(a[0] in rule["axes"] and a[2] in ("alta", "media") for a in v.get("axes") or []):
                continue
            n += 1
            for p, ch in zip(parties, v.get("parties") or ""):
                per[p][{"S": "si", "N": "no", "A": "abst"}.get(ch, "otro")] += 1
        out[domain] = {"votes": n, "axes": sorted(rule["axes"]), "parties": {p: dict(c) for p, c in per.items()}}
    return out


# ----------------------------------------------------------------------------------------------------------- seed

def load_seed() -> dict:
    seed = load(SEED) if SEED.exists() else {"schema_version": "party_decisions_v1", "measures": []}
    measures = list(seed.get("measures") or [])
    if SEED_DIR.exists():
        for part in sorted(SEED_DIR.glob("*.json")):
            data = load(part)
            items = data.get("measures") if isinstance(data, dict) and "measures" in data else [data]
            for m in items:
                m.setdefault("_part", part.name)
                measures.append(m)
    seed["measures"] = measures
    return seed


REQUIRED = ["measure_id", "candidate_key", "name", "what_changes", "stated_goal", "boe_url", "verdict", "verdict_reason",
            "ex_ante", "ex_post", "evidence_against", "retrieved"]
SOURCE_KEYS = ["source", "url", "finding"]


def validate(seed: dict, votes: Votes, worklist: list[dict]) -> list[str]:
    errors = []
    by_key = {c["candidate_key"]: c for c in worklist}
    seen = set()
    for m in seed["measures"]:
        mid = m.get("measure_id", "?")
        where = f"{mid} ({m.get('_part', 'seed')})"
        for k in REQUIRED:
            if k not in m or m[k] in (None, ""):
                if k not in ("ex_ante", "ex_post", "evidence_against"):
                    errors.append(f"{where}: missing {k}")
        if mid in seen:
            errors.append(f"{where}: duplicate measure_id")
        seen.add(mid)
        cand = by_key.get(m.get("candidate_key"))
        if cand is None:
            errors.append(f"{where}: candidate_key not in worklist (selection rule): {m.get('candidate_key')}")
        for vid in m.get("vote_ids") or ([cand["main_vote_id"]] if cand else []):
            if vid not in votes.by_id:
                errors.append(f"{where}: vote {vid} not in our data")
        if not str(m.get("boe_url", "")).startswith("https://"):
            errors.append(f"{where}: boe_url must be an https URL")
        if m.get("verdict") not in VERDICTS:
            errors.append(f"{where}: verdict {m.get('verdict')} not in {VERDICTS}")
        grades = []
        for bucket in ("ex_ante", "ex_post", "evidence_against"):
            for s in m.get(bucket) or []:
                for k in SOURCE_KEYS:
                    if not s.get(k):
                        errors.append(f"{where}: {bucket} source missing {k}")
                if not str(s.get("url", "")).startswith("http"):
                    errors.append(f"{where}: {bucket} url not http(s): {s.get('url')}")
                if bucket != "ex_ante":
                    g = s.get("grade")
                    if g not in GRADES:
                        errors.append(f"{where}: {bucket} grade {g} not in A-D")
                    grades.append(g)
        strong = [g for g in grades if g in ("A", "B")]
        if m.get("verdict") in ("positivo", "negativo", "mixto") and not strong:
            errors.append(f"{where}: verdict {m['verdict']} needs at least one A/B ex-post source")
        if cand and cand["unit"] == "contrafactual" and not m.get("later_route"):
            # A measure that never applied has no ex-post of its own: only evidence on similar measures abroad (B).
            if any(s.get("grade") == "A" for s in (m.get("ex_post") or []) + (m.get("evidence_against") or [])):
                errors.append(f"{where}: counterfactual cannot have grade A evidence without later_route")
            if m.get("verdict") != "no_evaluado":
                errors.append(f"{where}: counterfactual without later_route must stay no_evaluado")
        for field in ("what_changes", "stated_goal", "verdict_reason", "indicator_note"):
            if CAUSAL_RE.search(str(m.get(field) or "")):
                errors.append(f"{where}: causal wording in {field}")
        for ind in m.get("indicators") or []:
            if not ind.get("url") and not ind.get("series"):
                errors.append(f"{where}: indicator without series or url")
    return errors


# ---------------------------------------------------------------------------------------------------- indicators

def series_from(data: dict, path: str) -> list[dict]:
    node = data
    for part in path.split("."):
        node = node[part]
    return node


INDICATOR_SERIES = {
    "empleo": [
        {"id": "temporalidad", "label": "Asalariados con contrato temporal (% de asalariados)", "file": "empleo",
         "es": "temporary.epa_temporal_share", "peers": "temporary.eurostat", "peer_codes": ["EU27", "DEU", "FRA", "ITA", "PRT"],
         "source": "INE, EPA (España); Eurostat lfsa_etpga (pares)", "page": "/visualizaciones/empleo/"},
        {"id": "tasa_empleo", "label": "Tasa de empleo 20-64 años (%)", "file": "empleo",
         "es": "employment_rate.current.ESP", "peers": "employment_rate.current", "peer_codes": ["EU27", "DEU", "FRA", "ITA", "PRT"],
         "source": "Eurostat lfsi_emp_a", "page": "/visualizaciones/empleo/"},
    ],
    "sanidad": [
        {"id": "espera_quirurgica", "label": "Espera media para cirugía (días)", "file": "sanidad",
         "es": "waiting.surgery.mean_days", "peers": None, "peer_codes": [],
         "source": "Ministerio de Sanidad, SISLE-SNS", "page": "/visualizaciones/sanidad/"},
        {"id": "gasto_publico_pps", "label": "Gasto sanitario público por habitante (PPS)", "file": "sanidad",
         "es": "spending.eurostat_pps_public.ES", "peers": "spending.eurostat_pps_public", "peer_codes": ["EU27_2020", "DE", "FR", "IT", "PT"],
         "source": "Eurostat hlth_sha11_hf", "page": "/visualizaciones/sanidad/"},
    ],
}


def to_year_points(rows: list[dict], since: int) -> list[dict]:
    out = []
    for r in rows:
        year = r.get("year")
        if year is None and r.get("date"):
            # Semi-annual waiting-list cuts: keep the December cut as the year's value.
            if not r["date"].endswith("12-31"):
                continue
            year = int(r["date"][:4])
        if year is not None and year >= since and r.get("value") is not None:
            out.append({"year": int(year), "value": r["value"]})
    return out


def indicators(empleo: dict, sanidad: dict, since: int = 2015) -> dict:
    files = {"empleo": empleo, "sanidad": sanidad}
    out = {}
    for domain, specs in INDICATOR_SERIES.items():
        rows = []
        for spec in specs:
            data = files[spec["file"]]
            try:
                es = to_year_points(series_from(data, spec["es"]), since)
            except (KeyError, TypeError):
                es = []
            peers = {}
            if spec["peers"]:
                node = series_from(data, spec["peers"])
                for code in spec["peer_codes"]:
                    if code in node:
                        peers[code] = to_year_points(node[code], since)
            rows.append({k: spec[k] for k in ("id", "label", "source", "page")} | {"es": es, "peers": peers})
        out[domain] = rows
    return out


def value_at(points: list[dict], year: int) -> float | None:
    for p in points:
        if p["year"] == year:
            return p["value"]
    return None


def before_after(series: list[dict], date: str) -> dict | None:
    """Last full year before the vote and the latest year: what the indicator did afterwards (moved with, not because)."""
    year = int(date[:4])
    before = year - 1
    pts = [p for p in series if p["year"] >= before]
    if not pts or value_at(series, before) is None:
        return None
    last = series[-1]
    if last["year"] <= before:
        return None
    return {"before_year": before, "before": value_at(series, before), "after_year": last["year"], "after": last["value"],
            "change": round(last["value"] - value_at(series, before), 2)}


# ---------------------------------------------------------------------------------------------------------- build

def health_state_share(sanidad: dict) -> dict:
    """What share of public health spending the State (not the communities) manages, and the dispersion between them."""
    regions = (sanidad.get("spending") or {}).get("regions_per_person") or {}
    rows = [r for r in regions.get("rows") or [] if r.get("value") is not None or r.get("spend") is not None]
    vals = sorted((r.get("value") or r.get("spend"), r.get("name")) for r in rows)
    out = {"regions_year": regions.get("year"), "regions_total": regions.get("total"), "provisional": regions.get("provisional")}
    if vals:
        out |= {"min": {"name": vals[0][1], "value": vals[0][0]}, "max": {"name": vals[-1][1], "value": vals[-1][0]},
                "ratio_max_min": round(vals[-1][0] / vals[0][0], 2) if vals[0][0] else None, "n": len(vals)}
    sectors = (sanidad.get("money") or {}).get("sector_shares") or {}
    if sectors:
        out["sector_shares"] = sectors
    return out


def build(votes: Votes, seed: dict, worklist: list[dict], empleo: dict, sanidad: dict) -> dict:
    by_key = {c["candidate_key"]: c for c in worklist}
    parties = list(votes.atlas["parties"]) + EXTRA_PARTIES
    labels = {p["party_id"]: p["label"] for p in parties}
    inds = indicators(empleo, sanidad)
    documented = {m["candidate_key"]: m for m in seed["measures"] if m.get("review", {}).get("status") != "rejected"}
    measures = []
    for cand in worklist:
        m = documented.get(cand["candidate_key"])
        counts = votes.party_counts(cand["main_vote_id"])
        absolute = needs_absolute(cand["title"])
        result, dec = decisiveness(counts, absolute)
        yes_backs = cand["kind"] != "totalidad"  # Sí on an enmienda a la totalidad kills the bill
        party_rows = {}
        for p, c in counts.items():
            choice = majority(c)
            party_rows[p] = {"choice": choice, "stance": stance(choice, yes_backs), **c,
                             "decisive_if_absent": dec[p]["if_absent"], "decisive_if_opposite": dec[p]["if_opposite"]}
        yes = sum(c["S"] for c in counts.values())
        no = sum(c["N"] for c in counts.values())
        abst = sum(c["A"] for c in counts.values())
        row = {
            "name": auto_name(cand),
            "measure_id": (m or {}).get("measure_id") or re.sub(r"[^a-z0-9]+", "-", cand["candidate_key"])[:60].strip("-"),
            "candidate_key": cand["candidate_key"],
            "unit": cand["unit"],
            "domains": cand["domains"],
            "date": cand["date"],
            "legislature": cand["legislature"],
            "kind": cand["kind"],
            "title": cand["title"],
            "vote_id": cand["main_vote_id"],
            "official_vote_url": cand["official_vote_url"],
            "totals": {"si": yes, "no": no, "abst": abst},
            "totals_published": cand["totals"],
            "absolute_majority_required": absolute,
            "passed_in_vote": result,
            "yes_backs_measure": yes_backs,
            "took_effect": result if yes_backs else not result,
            "parties": party_rows,
            "documented": m is not None,
        }
        if m:
            for k in ("name", "what_changes", "stated_goal", "boe_url", "boe_id", "legal_status", "ex_ante", "ex_post",
                      "evidence_against", "verdict", "verdict_reason", "indicators", "indicator_note", "later_route",
                      "notes", "retrieved", "review"):
                if k in m:
                    row[k] = m[k]
        else:
            row["verdict"] = "pendiente"
        # Indicator before/after from the published verticals (domain series), moved-with only.
        moved = []
        for d in (cand["domains"] if row["took_effect"] else []):  # a measure that never applied moved nothing
            for spec in inds.get(d, [])[:1]:  # the domain's headline indicator (the one in the figure)
                ba = before_after(spec["es"], cand["date"])
                if ba:
                    moved.append({"domain": d, "indicator": spec["id"], "label": spec["label"], **ba})
        row["indicator_moves"] = moved
        measures.append(row)

    summary = party_summary(measures, parties)
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "schema_version": "decisiones_v1",
        "method": "docs/etl/sprints/DECISIONES-20261111/README.md",
        "window": {"first": min(c["date"] for c in worklist) if worklist else None,
                   "last": votes.atlas["meta"]["votes_last_date"], "data_from": "2022-10-04",
                   "gap": "Las votaciones de la XIV anteriores al 4 de octubre de 2022 (entre ellas la reforma laboral, "
                          "RDL 32/2021, y la reforma de cotización de autónomos, RDL 13/2022) no están en nuestros datos."},
        "domains": [{"id": d, "label": DOMAIN_LABELS[d], "axes": sorted(DOMAIN_RULES[d]["axes"]),
                     "measures": sum(1 for m in measures if d in m["domains"])} for d in DOMAINS],
        "parties": [{**p, "governing": GOVERNING.get(p["party_id"])} for p in parties],
        "party_labels": labels,
        "verdict_labels": VERDICT_LABELS,
        "measures": measures,
        "party_summary": summary,
        "positions": position_counts(votes),
        "indicators": inds,
        "health_state": health_state_share(sanidad) | {"by_sector": (seed.get("context") or {}).get("health_spending_by_sector")},
        "counts": {"measures": len(measures), "documented": sum(1 for m in measures if m["documented"]),
                   "by_verdict": dict(Counter(m.get("verdict") for m in measures))},
    }


def party_summary(measures: list[dict], parties: list[dict]) -> dict:
    out = {}
    for p in parties:
        pid = p["party_id"]
        per_domain = {}
        for d in DOMAINS:
            cells = {"backed": defaultdict(list), "opposed": defaultdict(list), "abstained": defaultdict(list),
                     "decisive": []}
            for m in measures:
                if d not in m["domains"] or pid not in m["parties"]:
                    continue
                r = m["parties"][pid]
                verdict = m.get("verdict", "pendiente")
                bucket = r["stance"] if r["stance"] in ("backed", "opposed", "abstained") else None
                if bucket:
                    cells[bucket][verdict].append(m["measure_id"])
                if r["decisive_if_absent"]:
                    cells["decisive"].append(m["measure_id"])
            if any(cells[b] for b in ("backed", "opposed", "abstained")):
                per_domain[d] = {b: dict(v) if isinstance(v, defaultdict) else v for b, v in cells.items()}
        if per_domain:
            out[pid] = per_domain
    return out


def write_csv(data: dict, path: Path) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    labels = data["party_labels"]
    w.writerow(["measure_id", "date", "legislature", "unit", "domains", "name", "verdict", "party", "vote", "si", "no",
                "abst", "decisive_if_absent", "decisive_if_opposite", "boe_url", "official_vote_url"])
    for m in data["measures"]:
        for pid, r in m["parties"].items():
            w.writerow([m["measure_id"], m["date"], m["legislature"], m["unit"], "|".join(m["domains"]),
                        m.get("name") or m["title"][:120], m.get("verdict"), labels.get(pid, pid), r["choice"], r["S"], r["N"],
                        r["A"], int(r["decisive_if_absent"]), int(r["decisive_if_opposite"]), m.get("boe_url", ""),
                        m["official_vote_url"]])
    path.write_text(buf.getvalue(), encoding="utf-8")



# ------------------------------------------------------------------------------------------------ BOE helpers (kit)

BOE_API = "https://www.boe.es/datosabiertos/api"
MONTHS_ES = {m: i + 1 for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                             "septiembre", "octubre", "noviembre", "diciembre"])}


def http_json(url: str) -> dict:
    import urllib.request
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_text(url: str) -> str:
    import urllib.request
    with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def boe_search(words: str, limit: int = 8) -> list[dict]:
    """Consolidated legislation whose title contains every word (the API does not match phrases or numbers)."""
    import urllib.parse
    q = " and ".join(f"titulo:{w}" for w in words.split())
    query = json.dumps({"query": {"query_string": {"query": q}}, "sort": [{"fecha_publicacion": "desc"}]})
    url = f"{BOE_API}/legislacion-consolidada?" + urllib.parse.urlencode({"query": query, "limit": limit})
    rows = http_json(url).get("data") or []
    return [{"boe_id": r.get("identificador"), "title": r.get("titulo"), "date": r.get("fecha_disposicion"),
             "url": f"https://www.boe.es/buscar/act.php?id={r.get('identificador')}"} for r in rows]


def boe_find_rdl(title: str) -> dict | None:
    """BOE item of a decree-law from its title («Real Decreto-ley N/YYYY, de D de mes»), via the daily summaries."""
    from datetime import date, timedelta
    m = re.search(r"Real Decreto-ley (\d+)/(\d{4}), de (\d{1,2}) de (\w+)", title)
    if not m:
        return None
    number = f"{m.group(1)}/{m.group(2)}"
    day = date(int(m.group(2)), MONTHS_ES[m.group(4).lower()], int(m.group(3)))
    for offset in range(0, 5):
        d = day + timedelta(days=offset)
        try:
            summary = http_json(f"{BOE_API}/boe/sumario/{d:%Y%m%d}")
        except Exception:  # noqa: BLE001 - no BOE that day
            continue
        found = []

        def walk(o):
            if isinstance(o, dict):
                t = o.get("titulo") or ""
                if o.get("identificador") and t.startswith(f"Real Decreto-ley {number},"):
                    found.append({"boe_id": o["identificador"], "title": t, "published": f"{d:%Y-%m-%d}"})
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(summary)
        if found:
            f = found[0]
            return f | {"url": f"https://www.boe.es/buscar/act.php?id={f['boe_id']}",
                        "url_original": f"https://www.boe.es/diario_boe/txt.php?id={f['boe_id']}"}
    return None


def boe_preamble(boe_id: str, chars: int = 2500) -> str:
    """First part of the preamble (exposición de motivos), plain text, from the BOE XML of the original text."""
    xml = http_text(f"https://www.boe.es/diario_boe/xml.php?id={boe_id}")
    body = xml.split("<texto>", 1)[-1]
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:chars]


def enrich_worklist(worklist: list[dict], only: set[str] | None = None) -> list[dict]:
    out = []
    for c in worklist:
        if only and c["candidate_key"] not in only:
            continue
        row = dict(c)
        hit = boe_find_rdl(c["title"]) if c["kind"] == "rdl" else None
        if hit:
            row["boe"] = hit
            try:
                row["boe"]["preamble_excerpt"] = boe_preamble(hit["boe_id"])
            except Exception as exc:  # noqa: BLE001
                row["boe"]["preamble_error"] = str(exc)[:120]
        out.append(row)
    return out

# ----------------------------------------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", nargs="?", default="export", choices=["candidates", "validate", "export", "boe-search", "boe-text", "enrich"])
    ap.add_argument("args", nargs="*", help="boe-search: title words; boe-text: BOE id; enrich: output path")
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    args = ap.parse_args(argv)
    if args.command == "boe-search":
        for r in boe_search(" ".join(args.args)):
            print(json.dumps(r, ensure_ascii=False))
        return 0
    if args.command == "boe-text":
        print(boe_preamble(args.args[0], 6000))
        return 0
    votes = Votes(load(ATLAS), load(PEOPLE))
    worklist = build_candidates(votes)
    if args.command == "enrich":
        done = {m.get("candidate_key") for m in load_seed()["measures"]}
        rows = enrich_worklist([c for c in worklist if c["candidate_key"] not in done])
        out = Path(args.args[0]) if args.args else SPRINT / "worklist-scale.json"
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"enrich: {len(rows)} measures, {sum(1 for r in rows if r.get('boe'))} with BOE id -> {out}")
        return 0
    if args.command == "candidates":
        enriched = []
        for c in worklist:
            counts = votes.party_counts(c["main_vote_id"])
            result, dec = decisiveness(counts, needs_absolute(c["title"]))
            yes_backs = c["kind"] != "totalidad"
            enriched.append(c | {"party_votes": {p: majority(v) for p, v in counts.items()},
                                 "party_stance": {p: stance(majority(v), yes_backs) for p, v in counts.items()},
                                 "decisive_if_absent": sorted(p for p, d in dec.items() if d["if_absent"]),
                                 "passed_recount": result})
        WORKLIST.parent.mkdir(parents=True, exist_ok=True)
        WORKLIST.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).date().isoformat(),
                                        "rule": "docs/etl/sprints/DECISIONES-20261111/README.md §1-3",
                                        "counts": dict(Counter(d for c in worklist for d in c["domains"])),
                                        "measures": enriched}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"candidates: {len(worklist)} measures -> {WORKLIST.relative_to(REPO_ROOT)}")
        for d, n in Counter(d for c in worklist for d in c["domains"]).items():
            print(f"  {d}: {n}")
        return 0
    seed = load_seed()
    errors = validate(seed, votes, worklist)
    if args.command == "validate":
        for e in errors:
            print("ERROR", e)
        print(f"validate: {len(seed['measures'])} measures, {len(errors)} errors")
        return 1 if errors else 0
    if errors:
        for e in errors:
            print("ERROR", e, file=sys.stderr)
        raise SystemExit(f"export_public_viz_decisions: {len(errors)} validation errors")
    data = build(votes, seed, worklist, load(EMPLEO), load(SANIDAD))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_csv(data, args.out_csv)
    print(f"export_public_viz_decisions: {data['counts']} -> {args.out_json.relative_to(REPO_ROOT)} "
          f"({args.out_json.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
