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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
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
        "keywords": r"trabajo autónomo|trabajador(?:es|as)? autónom|cuenta propia|emprend|\bpymes?\b|empresas emergentes|morosidad",
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

PUBLISHABLE = {"pass", "corrected"}
VERDICTS = ["positivo", "negativo", "mixto", "no_evaluado"]
VERDICT_LABELS = {"positivo": "Evaluada: positiva", "negativo": "Evaluada: negativa", "mixto": "Evaluada: mixta",
                  "no_evaluado": "Sin evaluación"}
GRADES = {"A", "B", "C", "D"}
CAUSAL_RE = re.compile(r"gracias a|por culpa de|provocó|causó|creó \d|destruyó \d|empleos creados|empleos destruidos", re.I)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))



def load_backfill_votes() -> list[dict]:
    """XIV binding votes from 2019-12 to 2022-10 (committed seed), contested only (same filter as the atlas), with
    their classification (axes + summary) merged in when it exists."""
    path = SEED_DIR / "votes" / "xiv_2019_2022.json"
    if not path.exists():
        return []
    classes_path = SEED_DIR / "votes" / "xiv_2019_2022_classes.json"
    classes = load(classes_path).get("votes", {}) if classes_path.exists() else {}
    out = []
    for v in load(path)["votes"]:
        majorities = {p: majority(c) for p, c in v["party_counts"].items()}
        if not ("S" in majorities.values() and "N" in majorities.values()):
            continue
        c = classes.get(v["id"], {})
        out.append(v | {"axes": c.get("axes") or [], "summary_yes": c.get("summary_yes"), "classified": bool(c)})
    return out

# ----------------------------------------------------------------------------------------------- votes and parties

class Votes:
    def __init__(self, atlas: dict, people: dict):
        self.atlas = atlas
        self.people = people
        self.titles = atlas["titles"]
        self.by_id = {v["id"]: v for v in atlas["votes"]}
        self.index = {row[0]: i for i, row in enumerate(people["votes"])}
        self.backfill = load_backfill_votes()
        for v in self.backfill:
            self.by_id[v["id"]] = v

    def all_votes(self) -> list[dict]:
        """Backfilled XIV binding votes (before the atlas window) followed by the atlas votes."""
        return self.backfill + self.atlas["votes"]

    def title(self, vote: dict) -> str:
        return (self.titles[vote["t"]] if "t" in vote else vote.get("title")) or ""

    def party_counts(self, vote_id: str) -> dict[str, dict[str, int]]:
        """Sí/No/Abstención/no vota per ballot party, from each deputy's own vote."""
        if "party_counts" in self.by_id.get(vote_id, {}):
            return self.by_id[vote_id]["party_counts"]
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



# ------------------------------------------------------------------------------- backfill: XIV before the atlas window

BACKFILL_DB = REPO_ROOT / "etl/data/staging/decisiones-xiv.db"
BACKFILL_DIR = SEED_DIR / "votes"
BACKFILL_VOTES = BACKFILL_DIR / "xiv_2019_2022.json"
BACKFILL_CLASSES = BACKFILL_DIR / "xiv_2019_2022_classes.json"
BACKFILL_FROM, BACKFILL_UNTIL = "2019-12-03", "2022-10-03"
BACKFILL_KINDS = {"final", "rdl", "totalidad"}  # legal effect, plus totalidad for narrow-failure counterfactuals
CHOICE = {"Sí": "S", "No": "N", "Abstención": "A", "No vota": "-"}


def fold_name(name: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(sorted(re.sub(r"[^a-z ]+", " ", t).split()))


def build_backfill(db: Path, people: dict) -> dict:
    """Binding XIV votes from the staging DB (loaded with scripts/ingestar_parlamentario_es.py), counted per party."""
    import hashlib
    import sqlite3
    from scripts.vote_atlas import load_congreso_events
    by_name = {fold_name(p["name"]): p.get("party_id") for p in people["people"] if p.get("party_id")}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    events = [e for e in load_congreso_events(conn, "14", BACKFILL_FROM)
              if e["vote_date"] <= BACKFILL_UNTIL and e["kind"] in BACKFILL_KINDS]
    out = []
    for e in events:
        raw = conn.execute("SELECT raw_payload FROM parl_vote_events WHERE vote_event_id = ?", (e["vote_event_id"],)).fetchone()[0]
        counts: dict[str, Counter] = defaultdict(Counter)
        for name, group, choice in conn.execute(
                "SELECT member_name, group_code, vote_choice FROM parl_vote_member_votes WHERE vote_event_id = ?",
                (e["vote_event_id"],)):
            party = XIV_GROUP_PARTY.get(group or "", "mixto")
            if party in {"plural", "mixto"}:
                party = by_name.get(fold_name(name)) or party
            counts[party][CHOICE.get(choice, "-")] += 1
        yes, no = e["yes"] or 0, e["no"] or 0
        path = (e["source_url"] or "").replace(OFFICIAL_VOTE_PREFIX, "")
        out.append({
            "id": "b-" + hashlib.sha1(e["vote_event_id"].encode()).hexdigest()[:10],
            "path": path, "leg": "14", "date": e["vote_date"], "kind": e["kind"],
            "title": (e["expediente_text"] or e["title"] or "").strip(), "heading": e["title"],
            "subgroup": e["subgroup_title"] or "", "totals": [yes, no, e["abstain"] or 0],
            "approved": yes > no,
            "party_counts": {p: {"S": c["S"], "N": c["N"], "A": c["A"], "no_vota": c["-"]} for p, c in sorted(counts.items())},
            "raw_sha256": hashlib.sha256((raw or "").encode("utf-8")).hexdigest(),
        })
    return {"schema_version": "party_decisions_votes_v1", "source": "Congreso de los Diputados, datos abiertos de votaciones",
            "loaded_with": "scripts/ingestar_parlamentario_es.py ingest --source congreso_votaciones --congreso-legs 14 "
                           f"--since-date {BACKFILL_FROM} --until-date {BACKFILL_UNTIL} --strict-network",
            "window": [BACKFILL_FROM, BACKFILL_UNTIL], "kinds": sorted(BACKFILL_KINDS), "votes": out}

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
        return f"Presupuestos {budget_year(cand['date'])}, sección {section}" + (f" ({m.group(1)})" if m else "")
    t = re.sub(r"^\s*votación\s+(conjunta\s+de\s+las\s+enmiendas\s+a\s+la\s+totalidad\s+de\s+devolución\s+al|del\s+dictamen\s+(del|de\s+la)|de\s+conjunto\s+(del\s+texto\s+)?(del|de\s+la))\s+", "", title, flags=re.I)
    t = re.sub(r"^(Real Decreto-ley \d+/\d{4}), de \d{1,2} de \w+,?", r"\1:", t)
    t = re.sub(r"^(Proyecto|Proposición) de Ley", "Ley", t).strip(" .")
    if len(t) > 110:
        t = t[:110].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return t


def budget_year(date: str) -> int:
    """State budgets are voted in the autumn before the year they cover."""
    year = int(date[:4])
    return year + 1 if int(date[5:7]) >= 9 else year


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
    for v in votes.all_votes():
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
        key = f"pge{budget_year(v['date'])} sección {section}" if section else law_key(title)
        g = groups.setdefault(key, {"key": key, "domains": set(), "votes": [], "units": {}})
        g["domains"].update(domains)
        g["votes"].append(v)
        g["units"][v["id"]] = unit
    out = []
    for key, g in groups.items():
        vs = sorted(g["votes"], key=lambda v: v["date"])
        conj = [v for v in vs if "conjunto" in votes.title(v).lower()]
        main = conj[-1] if conj else vs[-1]
        title = votes.title(main)
        out.append({
            "candidate_key": key,
            "unit": g["units"][main["id"]],  # the unit of the vote that decided it, not of the group's first vote
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
        if m.get("method_version", 1) >= 2:
            errors += validate_v2(m, where, took_effect=not (cand and cand["unit"] == "contrafactual"))
    return errors


def validate_government() -> list[str]:
    """Government-only decisions: same evidence rules (v2), id must come from the fixed BOE rule."""
    errors = []
    ids = {d["decision_id"] for d in load(GOV_WORKLIST)["decisions"]} if GOV_WORKLIST.exists() else set()
    for d in load_government_seed():
        where = f"government/{d.get('decision_id', '?')}"
        if d.get("decision_id") not in ids:
            errors.append(f"{where}: decision_id not produced by GOV_RULES")
        for k in ("name", "what_changes", "stated_goal", "verdict", "verdict_reason", "retrieved"):
            if not d.get(k):
                errors.append(f"{where}: missing {k}")
        if d.get("verdict") not in VERDICTS:
            errors.append(f"{where}: verdict {d.get('verdict')} not in {VERDICTS}")
        grades = []
        for bucket in ("ex_ante", "ex_post", "evidence_against"):
            for src in d.get(bucket) or []:
                for k in SOURCE_KEYS:
                    if not src.get(k):
                        errors.append(f"{where}: {bucket} source missing {k}")
                if bucket != "ex_ante":
                    if src.get("grade") not in GRADES:
                        errors.append(f"{where}: {bucket} grade {src.get('grade')} not in A-D")
                    grades.append(src.get("grade"))
        if d.get("verdict") in ("positivo", "negativo", "mixto") and not any(g in ("A", "B") for g in grades):
            errors.append(f"{where}: verdict {d['verdict']} needs at least one A/B ex-post source")
        for field in ("what_changes", "stated_goal", "verdict_reason"):
            if CAUSAL_RE.search(str(d.get(field) or "")):
                errors.append(f"{where}: causal wording in {field}")
        errors += validate_v2(d, where)
    return errors


def validate_v2(m: dict, where: str, took_effect: bool = True) -> list[str]:
    """Rules added after the first pilot failed (README «What is next»):
    1. a monitoring statistic is not an evaluation: every ex-post / against item states whether the source itself
       attributes the change to the measure (`attributes_to_measure`) or is about another country
       (`about_other_country`); grade A/B needs one of the two;
    2. one series per before/after: an indicator has one `series` name and one source, or `same_series: true` with a
       `series_note` when two documents report the same series;
    3. entry into force from the text: `in_force` lists every date with the provision that sets it (from
       `boe-vigor`), so deferred disposiciones finales are not missed."""
    errors = []
    for bucket in ("ex_post", "evidence_against"):
        for i, src in enumerate(m.get(bucket) or []):
            if "attributes_to_measure" not in src and not src.get("about_other_country"):
                errors.append(f"{where}: {bucket}[{i}] must say attributes_to_measure (true/false) or about_other_country")
            if src.get("grade") in ("A", "B") and not (src.get("attributes_to_measure") or src.get("about_other_country")):
                errors.append(f"{where}: {bucket}[{i}] graded {src.get('grade')} but the source does not attribute the "
                              "change to the measure: move it to indicators")
            if src.get("about_other_country") and src.get("grade") == "A":
                errors.append(f"{where}: {bucket}[{i}] about another country cannot be grade A")
    for i, ind in enumerate(m.get("indicators") or []):
        if not ind.get("series"):
            errors.append(f"{where}: indicators[{i}] needs a single named `series`")
        urls = {u for u in ((ind.get("before") or {}).get("url"), (ind.get("after") or {}).get("url"), ind.get("url")) if u}
        if len(urls) > 1 and not (ind.get("same_series") and ind.get("series_note")):
            errors.append(f"{where}: indicators[{i}] before/after from different documents: set same_series + series_note "
                          "only if it is the same series and scope, otherwise drop it")
    if took_effect and not m.get("not_yet_in_force"):  # e.g. passed by Congress, still in the Senate
        if not m.get("in_force"):
            errors.append(f"{where}: in_force missing (dates and provisions from boe-vigor)")
        for i, f in enumerate(m.get("in_force") or []):
            if not (f.get("date") and f.get("provision") and f.get("what")):
                errors.append(f"{where}: in_force[{i}] needs what, date and provision")
            if f.get("date") and not re.match(r"^\d{4}-\d{2}-\d{2}$", f["date"]):
                errors.append(f"{where}: in_force[{i}] date must be YYYY-MM-DD")
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



# ------------------------------------------------------------------------------- decisions without a Congress vote

# Governments by date (Consejo de Ministros). Parties in each; used only to attribute government-only decisions.
GOVERNMENTS = [
    {"from": "2018-06-07", "to": "2020-01-12", "label": "Gobierno Sánchez I (PSOE)", "parties": ["psoe"]},
    {"from": "2020-01-13", "to": "2023-11-20", "label": "Gobierno Sánchez II (PSOE y Unidas Podemos)", "parties": ["psoe", "up"]},
    {"from": "2023-11-21", "to": "9999-12-31", "label": "Gobierno Sánchez III (PSOE y Sumar)", "parties": ["psoe", "sumar"]},
]
# Fixed rule: every royal decree found by the BOE query whose title matches, from the first year on.
GOV_RULES = [
    {"id": "smi", "label": "Salario mínimo interprofesional (real decreto anual)", "domain": "empleo",
     "query": "salario mínimo interprofesional", "from_year": 2019,
     "title_re": r"^Real Decreto (\d+/\d{4}), de .*salario mínimo interprofesional para (\d{4})\.?$",
     "positions_re": r"salario mínimo|\bSMI\b"},
]
GOV_DIR = SEED_DIR / "government"
GOV_WORKLIST = SPRINT / "worklist-government.json"


def government_at(date: str) -> dict:
    return next(g for g in GOVERNMENTS if g["from"] <= date <= g["to"])


def build_government_candidates() -> list[dict]:
    out = []
    for rule in GOV_RULES:
        for r in boe_search(rule["query"], limit=40):
            m = re.match(rule["title_re"], r["title"] or "")
            if not m or int(m.group(2)) < rule["from_year"]:
                continue
            date = f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}"
            gov = government_at(date)
            out.append({"decision_id": f"{rule['id']}-{m.group(2)}", "rule": rule["id"], "domain": rule["domain"],
                        "instrument": f"Real Decreto {m.group(1)}", "year": int(m.group(2)), "date": date,
                        "title": r["title"], "boe_id": r["boe_id"], "boe_url": r["url"],
                        "government": gov["label"], "governing_parties": gov["parties"]})
    return sorted(out, key=lambda c: c["date"])


def load_government_seed() -> list[dict]:
    return [load(p) for p in sorted(GOV_DIR.glob("*.json"))] if GOV_DIR.exists() else []


def government_positions(votes: "Votes", pattern: str) -> list[dict]:
    """Congress motions and PNL on the same subject: positions only, no legal effect."""
    parties = [p["party_id"] for p in votes.atlas["parties"]]
    out = []
    for v in votes.atlas["votes"]:
        if v["kind"] not in POSITION_KINDS:
            continue
        text = f"{votes.title(v)} {v.get('summary_yes') or ''}"
        if not re.search(pattern, text, re.I):
            continue
        out.append({"vote_id": v["id"], "date": v["date"], "kind": v["kind"], "summary_yes": v.get("summary_yes"),
                    "approved": v["approved"], "official_vote_url": OFFICIAL_VOTE_PREFIX + v["path"],
                    "parties": {p: ch for p, ch in zip(parties, v.get("parties") or "") if ch in "SNA"}})
    return out


def build_government(votes: "Votes") -> dict:
    worklist = load(GOV_WORKLIST)["decisions"] if GOV_WORKLIST.exists() else []
    seed = {d["decision_id"]: d for d in load_government_seed() if (d.get("review") or {}).get("status") in PUBLISHABLE}
    rows = []
    for c in worklist:
        d = seed.get(c["decision_id"])
        row = dict(c) | {"requires_power": True, "documented": d is not None, "verdict": (d or {}).get("verdict", "pendiente")}
        if d:
            for k in ("name", "what_changes", "stated_goal", "stated_goal_url", "ex_ante", "ex_post", "evidence_against",
                      "verdict_reason", "indicators", "notes", "retrieved", "review", "legal_status", "in_force"):
                if k in d:
                    row[k] = d[k]
        rows.append(row)
    blocks = []
    for rule in GOV_RULES:
        blocks.append({"rule": rule["id"], "label": rule["label"], "domain": rule["domain"],
                       "decisions": [r for r in rows if r["rule"] == rule["id"]],
                       "positions": government_positions(votes, rule["positions_re"])})
    return {"note": "Decisiones que toma el Gobierno sin votación del Congreso: solo puede tomarlas quien gobierna. Se "
                    "atribuyen a los partidos del Gobierno de cada fecha y no se comparan con la oposición; las mociones "
                    "del Congreso sobre el mismo asunto se muestran como posición, sin efecto legal.",
            "governments": GOVERNMENTS, "blocks": blocks}

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
    # Evidence is published only for measures that passed the independent review (or were corrected as it said).
    documented = {m["candidate_key"]: m for m in seed["measures"] if (m.get("review") or {}).get("status") in PUBLISHABLE}
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
        if m and m.get("lapsed"):
            # Passed by Congress but lapsed before publication (e.g. in the Senate): it never took effect.
            row["took_effect"] = False
            row["lapsed"] = True
        if m:
            for k in ("name", "what_changes", "stated_goal", "boe_url", "boe_id", "legal_status", "ex_ante", "ex_post",
                      "evidence_against", "verdict", "verdict_reason", "indicators", "indicator_note", "later_route", "in_force",
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
                   "last": votes.atlas["meta"]["votes_last_date"],
                   "data_from": min((v["date"] for v in votes.backfill), default="2022-10-04"),
                   "gap": ("Los votos empiezan en el primer Pleno de la XIV con votaciones nominales publicadas "
                           f"({min((v['date'] for v in votes.backfill), default='2022-10-04')}); las legislaturas anteriores "
                           "no están en estos datos.") if votes.backfill else
                          ("Las votaciones de la XIV anteriores al 4 de octubre de 2022 no están en nuestros datos.")},
        "domains": [{"id": d, "label": DOMAIN_LABELS[d], "axes": sorted(DOMAIN_RULES[d]["axes"]),
                     "measures": sum(1 for m in measures if d in m["domains"])} for d in DOMAINS],
        "parties": [{**p, "governing": GOVERNING.get(p["party_id"])} for p in parties],
        "party_labels": labels,
        "verdict_labels": VERDICT_LABELS,
        "measures": measures,
        "party_summary": summary,
        "positions": position_counts(votes),
        "government": build_government(votes),
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


def cache_find(pattern: str, limit: int = 20) -> list[str]:
    """Cached documents whose text matches a regex: URL and number of matching lines."""
    rx, out = re.compile(pattern, re.I), []
    for meta_path in sorted(CACHE.glob("*.json")):
        meta = load(meta_path)
        if "text_path" not in meta:
            continue
        hits = sum(1 for line in (REPO_ROOT / meta["text_path"]).read_text(encoding="utf-8", errors="replace").splitlines() if rx.search(line))
        if hits:
            out.append(f"{hits:5d}  {meta['url']}")
    return sorted(out, reverse=True)[:limit]


def boe_pdf_url(boe_id: str) -> str | None:
    xml = http_text(f"https://www.boe.es/diario_boe/xml.php?id={boe_id}")
    m = re.search(r"<url_pdf>([^<]+)</url_pdf>", xml)
    return m.group(1) if m else None


VIGOR_RE = r"entrar[áa] en vigor|surtir[áa] efectos|con efectos (desde|a partir)|será de aplicación (a partir|desde)|producir[áa] efectos"


def boe_vigor(boe_id: str) -> list[str]:
    """Every entry-into-force clause of a BOE text, with page: catches deferred dates in disposiciones finales."""
    url = boe_pdf_url(boe_id)
    return grep_cached(url, VIGOR_RE, context=2, limit=30) if url else ["no PDF url in BOE metadata"]


def boe_article(boe_id: str, heading: str, chars: int = 4000) -> str:
    """One whole provision of a BOE text (e.g. «Disposición final octava», «Artículo 3»), up to the next heading."""
    url = boe_pdf_url(boe_id)
    meta = fetch_cached(url) if url else {}
    if "text_path" not in meta:
        return "no cached text"
    pages = (REPO_ROOT / meta["text_path"]).read_text(encoding="utf-8", errors="replace").split("\f")
    text = ""
    for n, page in enumerate(pages, start=1):
        text += f"\n[p. {n}]\n" + page
    flat = re.sub(r"[ \t]+", " ", text)
    head = re.compile(r"^\s*" + re.escape(heading[:1].upper() + heading[1:]) + r"\b", re.M)  # headings are capitalised
    starts = [m.start() for m in head.finditer(flat)]
    if not starts:
        return f"heading not found: {heading}"
    start = starts[-1]  # the provision itself, not a mention in the preamble or index
    nxt = re.compile(r"^\s*(Artículo \d+|Disposición (adicional|transitoria|derogatoria|final)\b)", re.I | re.M)
    m = nxt.search(flat, start + len(heading) + 1)
    page_marks = re.findall(r"\[p\. (\d+)\]", flat[:start])
    page = page_marks[-1] if page_marks else "?"
    return f"[from p. {page}] " + flat[start:(m.start() if m else start + chars)][:chars].strip()


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


# ----------------------------------------------------------------------------------------- shared fetch cache (kit)

CACHE = REPO_ROOT / "etl/data/cache/decisiones"
# Hosts with a broken TLS chain from this environment (AGENTS.md: unverified TLS surgically per host, never globally).
INSECURE_TLS_HOSTS = {"www.airef.es", "airef.es"}
KIT_UA = "vota-con-la-chola-research/1.0 (+https://votaconlachola.org; public-data research)"


def cache_paths(url: str) -> tuple[Path, Path, Path]:
    import hashlib
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return CACHE / f"{key}.bin", CACHE / f"{key}.txt", CACHE / f"{key}.json"


def fetch_cached(url: str, timeout: int = 60) -> dict:
    """Download once (shared by every agent), keep bytes + sha256, and a text version (pdftotext -layout for PDFs,
    tags stripped for HTML). Returns the metadata; the text is in meta['text_path'] with pages split by form feeds."""
    import hashlib
    import subprocess
    import urllib.request
    raw, txt, meta_path = cache_paths(url)
    if meta_path.exists():
        return load(meta_path)
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = {"url": url, "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
    try:
        import urllib.parse
        safe_url = urllib.parse.quote(url, safe=":/?&=%#+,;@~!$'()*")
        req = urllib.request.Request(safe_url, headers={"User-Agent": KIT_UA, "Accept": "*/*"})
        ctx = None
        if urllib.parse.urlparse(url).hostname in INSECURE_TLS_HOSTS:
            import ssl
            ctx = ssl._create_unverified_context()  # noqa: S323 - host listed in INSECURE_TLS_HOSTS
            meta["tls_unverified"] = True
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read()
            meta |= {"status": resp.status, "content_type": resp.headers.get("Content-Type", "")}
    except Exception as exc:  # noqa: BLE001 - record the failure so nobody retries blindly
        meta |= {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return meta
    raw.write_bytes(body)
    meta["sha256"] = hashlib.sha256(body).hexdigest()
    meta["bytes"] = len(body)
    if body[:5] == b"%PDF-":
        subprocess.run(["pdftotext", "-layout", str(raw), str(txt)], check=False, capture_output=True)
    else:
        html = body.decode("utf-8", errors="replace")
        html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", html)
        text = re.sub(r"<[^>]+>", " ", text)
        import html as htmllib
        txt.write_text(re.sub(r"[ \t]+", " ", htmllib.unescape(text)), encoding="utf-8")
    if txt.exists():
        content = txt.read_text(encoding="utf-8", errors="replace")
        meta["text_path"] = str(txt.relative_to(REPO_ROOT))
        meta["pages"] = content.count("\f") + 1
        meta["chars"] = len(content)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def grep_cached(url: str, pattern: str, context: int = 1, limit: int = 40, width: int = 400) -> list[str]:
    """Lines matching a regex in a cached document, prefixed with [p. N] (PDF page) and line number."""
    meta = fetch_cached(url)
    if "text_path" not in meta:
        return [f"no text: {meta.get('error') or meta.get('content_type')}"]
    content = (REPO_ROOT / meta["text_path"]).read_text(encoding="utf-8", errors="replace")
    out, rx = [], re.compile(pattern, re.I)
    for page_no, page in enumerate(content.split("\f"), start=1):
        lines = page.splitlines()
        for i, line in enumerate(lines):
            if rx.search(line):
                lo, hi = max(0, i - context), min(len(lines), i + context + 1)
                snippet = " / ".join(re.sub(r"\s+", " ", l).strip() for l in lines[lo:hi] if l.strip())
                out.append(f"[p. {page_no}] {snippet[:width]}")
                if len(out) >= limit:
                    return out
    return out

# ----------------------------------------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", nargs="?", default="export", choices=["candidates", "backfill", "classify-worklist", "government", "validate", "export", "boe-search", "boe-text", "boe-vigor", "boe-article", "cache-find", "enrich", "fetch", "grep"])
    ap.add_argument("args", nargs="*", help="boe-search: title words; boe-text: BOE id; enrich: output path")
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    args = ap.parse_args(argv)
    if args.command == "boe-search":
        for r in boe_search(" ".join(args.args)):
            print(json.dumps(r, ensure_ascii=False))
        return 0
    if args.command == "fetch":
        for url in args.args:
            meta = fetch_cached(url)
            print(json.dumps({k: meta.get(k) for k in ("url", "status", "error", "sha256", "pages", "chars", "text_path")}, ensure_ascii=False))
        return 0
    if args.command == "cache-find":
        for line in cache_find(args.args[0]):
            print(line)
        return 0
    if args.command == "grep":
        width = int(args.args[2]) if len(args.args) > 2 else 400
        for line in grep_cached(args.args[0], args.args[1], width=width):
            print(line)
        return 0
    if args.command == "boe-article":
        print(boe_article(args.args[0], " ".join(args.args[1:])))
        return 0
    if args.command == "boe-vigor":
        for line in boe_vigor(args.args[0]):
            print(line)
        return 0
    if args.command == "boe-text":
        print(boe_preamble(args.args[0], 6000))
        return 0
    votes = Votes(load(ATLAS), load(PEOPLE))
    worklist = build_candidates(votes)
    if args.command == "backfill":
        data = build_backfill(BACKFILL_DB, load(PEOPLE))
        BACKFILL_DIR.mkdir(parents=True, exist_ok=True)
        BACKFILL_VOTES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"backfill: {len(data['votes'])} binding XIV votes -> {BACKFILL_VOTES.relative_to(REPO_ROOT)} "
              f"({dict(Counter(v['kind'] for v in data['votes']))})")
        return 0
    if args.command == "classify-worklist":
        rows = []
        for v in votes.backfill:  # contested binding XIV votes before the atlas window
            if v.get("classified"):
                continue
            row = {"id": v["id"], "date": v["date"], "kind": v["kind"], "title": v["title"], "subgroup": v.get("subgroup", "")}
            hit = boe_find_rdl(v["title"]) if v["kind"] == "rdl" else None
            if hit:
                try:
                    row["preamble"] = boe_preamble(hit["boe_id"], 1200)
                    row["boe_id"] = hit["boe_id"]
                except Exception:  # noqa: BLE001
                    pass
            rows.append(row)
        out = SPRINT / "classify-xiv-worklist.json"
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"classify-worklist: {len(rows)} votes ({sum(1 for r in rows if r.get('preamble'))} with BOE preamble) -> {out.relative_to(REPO_ROOT)}")
        return 0
    if args.command == "government":
        rows = build_government_candidates()
        GOV_WORKLIST.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).date().isoformat(),
                                            "rule": "GOV_RULES in scripts/export_public_viz_decisions.py",
                                            "decisions": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"government: {len(rows)} decisions -> {GOV_WORKLIST.relative_to(REPO_ROOT)}")
        return 0
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
    errors = validate(seed, votes, worklist) + validate_government()
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
