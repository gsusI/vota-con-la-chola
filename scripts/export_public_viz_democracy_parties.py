#!/usr/bin/env python3
"""Export /visualizaciones/democracia/partidos/ (democratic conduct by party).

Inputs (all committed):
- etl/data/seeds/democracy_conduct_v1.json: codebook, parties, governments, V-Party mapping and the event ledger
  (merged from etl/data/seeds/democracy_conduct_v1.d/events_*.json with `merge`).
- ui/site/public/citizen/data/vote_atlas_v1.json: Congress votes of legislatures 14-15 classified on axes; the vote
  layer uses the structural axes (justicia_independencia, instituciones_reglas, anticorrupcion) and control_gobierno.
- docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/evidence/boe-eli-norms.json.gz: Reales Decretos-leyes, Leyes and Leyes
  Orgánicas 1979-2026 from the BOE ELI listings (`fetch-boe` refreshes it; sha256 of every listing page inside).
- the V-Party extract in the same evidence folder.

Writes ui/site/public/visualizaciones/data/democracia-partidos.json and .csv. Method and decision rules:
docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/README.md.

    python3 scripts/export_public_viz_democracy_parties.py merge      # part files -> seed events
    python3 scripts/export_public_viz_democracy_parties.py fetch-boe  # refresh the BOE ELI inventory (network)
    python3 scripts/export_public_viz_democracy_parties.py            # export
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import gzip
import hashlib
import io
import itertools
import json
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = REPO_ROOT / "etl/data/seeds/democracy_conduct_v1.json"
PARTS_DIR = REPO_ROOT / "etl/data/seeds/democracy_conduct_v1.d"
ATLAS = REPO_ROOT / "ui/site/public/citizen/data/vote_atlas_v1.json"
SPRINT = REPO_ROOT / "docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111"
BOE_INVENTORY = SPRINT / "evidence/boe-eli-norms.json.gz"
SIBLING_INVENTORY = REPO_ROOT / "etl/data/seeds/democracy_safeguards_v1.d/raw/boe_eli_inventory.json.gz"
SIBLING_SEED = REPO_ROOT / "etl/data/seeds/democracy_safeguards_v1.json"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/democracia-partidos.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/democracia-partidos.csv"

STRUCTURAL_AXES = ("justicia_independencia", "instituciones_reglas", "anticorrupcion")
SCRUTINY_AXIS = "control_gobierno"
SCORED_CONFIDENCE = {"alta", "media"}
BINDING_KINDS = {"toma", "totalidad", "final", "rdl", "rdl_tramitacion", "enmienda", "enmienda_senado",
                 "voto_particular", "veto_senado", "reforma_reglamento"}
VOTE_URL = "https://www.congreso.es/webpublica/opendata/votaciones/"
LEG_GOVERNMENT = {"14": {"psoe", "podemos"}, "15": {"psoe", "sumar"}}
GROUP_PARTY = [
    ("Socialista", "psoe"), ("Popular", "pp"), ("VOX", "vox"), ("Plurinacional SUMAR", "sumar"),
    ("Unidas Podemos", "podemos"), ("Republicano", "erc"), ("Junts per Catalunya", "junts"), ("EH Bildu", "bildu"),
    ("Vasco (EAJ-PNV)", "pnv"), ("Ciudadanos", "cs"), ("Mixto", "mixto"),
]
LZ = {"reglas", "legitimidad", "violencia", "libertades", "minorias"}
ROL = {"justicia", "corrupcion", "medios", "contrapesos"}
GOV_ROLES = {"national_government", "regional_government", "local_government"}
COUNTED_LINEAGE = {"same", "list", "person"}
BOE_KINDS = {"rdl": "Real Decreto-ley", "l": "Ley", "lo": "Ley Orgánica"}


# ---------------------------------------------------------------- merge
SELECTION_FAMILIES = {
    "condenas_firmes": "Condenas firmes de cargos o del propio partido",
    "tc_otras": "Otras sentencias del Tribunal Constitucional (leyes, actos autonómicos, amparos, conflictos)",
    "otros_organos": "Otras conclusiones de órganos oficiales o internacionales",
}
CENSUS_LABELS = {
    "tc_decreto_ley": "Decretos-leyes anulados por el Tribunal Constitucional (art. 86)",
    "tc_estado_alarma": "Estados de alarma ante el Tribunal Constitucional",
    "jec_sancion": "Sanciones de la Junta Electoral Central a partidos y miembros de Gobiernos",
    "tcu_sancion": "Sanciones del Tribunal de Cuentas a partidos",
    "venecia": "Dictámenes de la Comisión de Venecia sobre España",
    "greco": "Informes de cumplimiento de GRECO sobre España",
    "rolr": "Capítulos de España del Informe sobre el Estado de Derecho",
}


def selection_family(ev: dict) -> str:
    if ev["finding_type"] in ("conviction_prison_ge1", "conviction_other", "civil_liability_party"):
        return "condenas_firmes"
    if "Constitucional" in ev.get("body", ""):
        return "tc_otras"
    return "otros_organos"


def merge() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    events = []
    system = []
    census = []
    pending = []
    for path in sorted(PARTS_DIR.glob("pending_*.json")):
        pending += [x | {"part": path.stem} for x in json.loads(path.read_text(encoding="utf-8")).get("pending") or []]
    for path in sorted(PARTS_DIR.glob("events_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        system += [f | {"part": path.stem} for f in doc.get("system_findings") or []]
        pending += [x | {"part": path.stem} for x in doc.get("pending") or []]
        if doc.get("census"):
            census.append(doc["census"] | {"part": path.stem})
        for ev in doc.get("events") or []:
            if ev.get("_exclude"):
                continue
            events.append({k: v for k, v in ev.items() if not k.startswith("_")} | {"part": path.stem})
    ids = Counter(e["event_id"] for e in events)
    dup = [k for k, n in ids.items() if n > 1]
    if dup:
        print("ERROR duplicate event_id:", dup, file=sys.stderr)
        return 1
    family_of = {}
    for c in census:
        refs = [r.get("event_id") for r in c.get("rows") or []] + list(c.get("already_in_ledger") or [])
        for eid in refs:
            if eid:
                family_of[eid] = c["family"]
    known = {e["event_id"] for e in events}
    missing = sorted(eid for eid in family_of if eid not in known)
    if missing:
        print("ERROR census rows point to unknown/excluded events:", missing, file=sys.stderr)
        return 1
    for e in events:
        if e["event_id"] in family_of:
            e["coverage"] = {"type": "census", "family": family_of[e["event_id"]]}
        else:
            e["coverage"] = {"type": "selection", "family": selection_family(e)}
    seen = Counter(x.get("pending_id") for x in pending)
    if any(n > 1 for n in seen.values()):
        print("ERROR duplicate pending_id:", [k for k, n in seen.items() if n > 1], file=sys.stderr)
        return 1
    seed["census"] = sorted(census, key=lambda c: c["family"])
    seed["pending"] = sorted(pending, key=lambda x: (x.get("party_id") or "", x.get("date") or ""))
    seed["events"] = sorted(events, key=lambda e: (e.get("date") or "", e["event_id"]))
    seed["system_findings"] = sorted(system, key=lambda f: (str(f.get("year") or ""), f.get("event_id") or ""))
    SEED.write_text(json.dumps(seed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"merged {len(events)} events into {SEED.relative_to(REPO_ROOT)}")
    return 0


# ---------------------------------------------------------------- BOE ELI
def _get(url: str) -> str:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vclc-etl/1.0 (+https://votaconlachola.org)"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(2 + 3 * attempt)
    return ""


def fetch_boe(first_year: int = 1979, last_year: int | None = None) -> int:
    last_year = last_year or date.today().year
    pages: dict[str, str] = {}
    norms: list[dict] = []
    for kind in BOE_KINDS:
        months = []
        for y in range(first_year, last_year + 1):
            url = f"https://www.boe.es/eli/es/{kind}/{y}"
            html = _get(url)
            pages[url] = hashlib.sha256(html.encode()).hexdigest()
            months += [f"https://www.boe.es{p}" for p in re.findall(rf"href = '(/eli/es/{kind}/{y}/\d\d)'", html)]
        days = []
        with cf.ThreadPoolExecutor(4) as ex:
            for url, html in zip(months, ex.map(_get, months)):
                pages[url] = hashlib.sha256(html.encode()).hexdigest()
                path = url.removeprefix("https://www.boe.es")
                days += [f"https://www.boe.es{p}" for p in re.findall(rf"href = '({re.escape(path)}/\d\d)'", html)]
            for url, html in zip(days, ex.map(_get, days)):
                pages[url] = hashlib.sha256(html.encode()).hexdigest()
                for title, eli in re.findall(r"<span class='bloque'>([^<]*)</span><span class='bloquep'><strong>Permalink ELI: </strong><a href='([^']*)'", html):
                    eli = eli.strip()
                    if "/corrigendum/" not in eli:
                        norms.append({"kind": kind, "eli": eli, "title": title.strip()[:160]})
    doc = {"source": "BOE, listados ELI /eli/es/{rdl,l,lo}/AAAA", "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "years": [first_year, last_year], "listing_pages_sha256": pages, "norms": norms}
    BOE_INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(BOE_INVENTORY, "wt", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    print(f"{len(norms)} norms, {len(pages)} pages -> {BOE_INVENTORY.relative_to(REPO_ROOT)}")
    return 0


def eli_date(eli: str) -> str | None:
    m = re.search(r"/eli/es/[a-z]+/(\d{4})/(\d{2})/(\d{2})/", eli)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def decree_layer(seed: dict, today: str) -> dict:
    if not BOE_INVENTORY.exists():
        return {"available": False}
    raw = BOE_INVENTORY.read_bytes()
    inv = json.loads(gzip.decompress(raw))
    norms = [n | {"date": eli_date(n["eli"])} for n in inv["norms"]]
    norms = [n for n in norms if n["date"]]
    years = range(inv["years"][0], int(today[:4]) + 1)
    per_year = {y: Counter() for y in years}
    for n in norms:
        y = int(n["date"][:4])
        if y in per_year:
            per_year[y][n["kind"]] += 1
    govs = json.loads(SIBLING_SEED.read_text(encoding="utf-8"))["governments"] if SIBLING_SEED.exists() else []
    # Finer split of the Sánchez period (coalition partners) from our seed.
    ours = seed["national_governments"]
    split = [g for g in govs if g["id"] != "sanchez"] + [
        {"id": g["id"], "president": "Pedro Sánchez", "party": g["label"].split("(")[-1].rstrip(")"), "start": g["start"], "end": g["end"]}
        for g in ours if g["id"].startswith("sanchez")]
    split = sorted(split, key=lambda g: g["start"])

    def gov_at(d: str) -> dict | None:
        for g in split:
            if g["start"] <= d < (g["end"] or "9999"):
                return g
        return None

    by_gov: dict[str, Counter] = defaultdict(Counter)
    for n in norms:
        g = gov_at(n["date"])
        if g:
            by_gov[g["id"]][n["kind"]] += 1
    gov_rows = []
    for g in split:
        start = max(g["start"], f"{inv['years'][0]}-01-01")
        end = g["end"] or today
        months = (date.fromisoformat(end) - date.fromisoformat(start)).days / 30.4375
        c = by_gov[g["id"]]
        primary = c["rdl"] + c["l"] + c["lo"]
        gov_rows.append({
            "id": g["id"], "president": g["president"], "party": g["party"], "start": g["start"], "end": g["end"],
            "months": round(months, 1), "rdl": c["rdl"], "laws": c["l"], "organic_laws": c["lo"],
            "rdl_per_12_months": round(c["rdl"] / months * 12, 1) if months else None,
            "rdl_share_pct": round(100 * c["rdl"] / primary, 1) if primary else None,
        })
    series = []
    for y in years:
        c = per_year[y]
        primary = c["rdl"] + c["l"] + c["lo"]
        g = gov_at(f"{y}-07-01") or gov_at(f"{y}-01-01")
        series.append({"year": y, "rdl": c["rdl"], "laws": c["l"], "organic_laws": c["lo"],
                       "rdl_share_pct": round(100 * c["rdl"] / primary, 1) if primary else None,
                       "partial_year": y == int(today[:4]), "government_mid_year": g["id"] if g else None})
    parity = None
    if SIBLING_INVENTORY.exists():
        sib = json.loads(gzip.decompress(SIBLING_INVENTORY.read_bytes()))
        sib_norms = sib.get("norms") or []
        sib_elis = {(n.get("eli") or n.get("url") or "").rstrip("/") for n in sib_norms if isinstance(n, dict)}
        our_elis = {n["eli"].rstrip("/") for n in norms}
        parity = {"sibling_file": str(SIBLING_INVENTORY.relative_to(REPO_ROOT)), "ours": len(our_elis), "sibling": len(sib_elis),
                  "only_ours": len(our_elis - sib_elis), "only_sibling": len(sib_elis - our_elis)}
    return {
        "available": True,
        "source": {"label": "BOE, listados ELI de Reales Decretos-leyes, Leyes y Leyes Orgánicas",
                   "url": "https://www.boe.es/eli/es/rdl", "retrieved": inv["retrieved_at"][:10],
                   "sha256": hashlib.sha256(raw).hexdigest(), "pages": len(inv["listing_pages_sha256"]),
                   "file": str(BOE_INVENTORY.relative_to(REPO_ROOT))},
        "series": series, "by_government": gov_rows, "parity_with_sibling": parity,
        "note": "Volumen, no abuso: un decreto ley puede ser legítimo. La señal de abuso son las anulaciones del Tribunal Constitucional del registro.",
    }


# ---------------------------------------------------------------- votes
def proposer(title: str, kind: str, subgroup: str) -> list[str]:
    text = subgroup if kind in ("enmienda",) and "Grupo" in subgroup else title
    if re.match(r"^(Proyecto de Ley|Real Decreto-ley)", title):
        return ["gobierno"]
    m = re.search(r"Grupos? Parlamentarios? (.{0,120})", text)
    if not m:
        if re.match(r"^Proposición de Ley (de la Asamblea|del Parlamento|de las Cortes|de la Junta)", title):
            return ["parlamento_autonomico"]
        return ["otro"]
    chunk = m.group(1)
    out = [pid for name, pid in GROUP_PARTY if name in chunk]
    return out or ["otro"]


def vote_layer(seed: dict) -> dict:
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    raw_sha = hashlib.sha256(ATLAS.read_bytes()).hexdigest()
    pids = [p["party_id"] for p in atlas["parties"]]
    titles = atlas["titles"]
    items = []
    for v in atlas["votes"]:
        axes = [a for a in v["axes"] if a[2] in SCORED_CONFIDENCE]
        names = [a[0] for a in axes]
        if SCRUTINY_AXIS in names:
            cat, sign = "escrutinio", next(a[1] for a in axes if a[0] == SCRUTINY_AXIS)
        elif any(a in names for a in STRUCTURAL_AXES):
            ax = next(a for a in axes if a[0] in STRUCTURAL_AXES)
            cat = "estructural_vinculante" if v["kind"] in BINDING_KINDS else "estructural_declarativa"
            sign = ax[1]
        else:
            continue
        leg = v.get("leg") or v["path"][3:5]
        title = titles[v["t"]]
        items.append({
            "id": v["id"], "leg": leg, "date": v["date"], "kind": v["kind"], "category": cat,
            "axis": next((a[0] for a in axes if a[0] in STRUCTURAL_AXES + (SCRUTINY_AXIS,)), None),
            "sign": sign, "summary_yes": v["summary_yes"], "approved": v["approved"], "title": title[:200],
            "proposer": proposer(title, v["kind"], v.get("subgroup") or ""), "parties": v["parties"],
            "url": VOTE_URL + v["path"], "t": v["t"],
        })
    # One unit of weight per initiative (title) and category, as in the atlas.
    group_n = Counter((i["leg"], i["t"], i["category"]) for i in items)
    summary: dict = {}
    for pi, pid in enumerate(pids):
        summary[pid] = {}
        for leg in ("14", "15"):
            role = "gobierno" if pid in LEG_GOVERNMENT[leg] else "fuera_del_gobierno"
            cats = {}
            for cat in ("estructural_vinculante", "estructural_declarativa", "escrutinio"):
                num = den = 0.0
                n = 0
                inits = set()
                counts = Counter()
                for i in items:
                    if i["leg"] != leg or i["category"] != cat:
                        continue
                    ch = i["parties"][pi]
                    if ch not in "SNA":
                        continue
                    s = 1 if i["sign"] == "+" else -1
                    pos = {"S": s, "N": -s, "A": 0}[ch]
                    w = 1.0 / group_n[(leg, i["t"], cat)]
                    num += w * pos
                    den += w
                    n += 1
                    inits.add(i["t"])
                    counts["mas_controles" if pos > 0 else "menos_controles" if pos < 0 else "abstencion"] += 1
                cats[cat] = {"score": round(num / den, 3) if den else None, "votes": n, "initiatives": len(inits), **counts}
            summary[pid][leg] = {"role": role, **cats}
    # Alignment with the governing PSOE across every vote of legislature 15 (context for "fuera del Gobierno").
    psoe_i = pids.index("psoe")
    align = {}
    for pi, pid in enumerate(pids):
        same = tot = 0
        for v in atlas["votes"]:
            if (v.get("leg") or v["path"][3:5]) != "15":
                continue
            a, b = v["parties"][pi], v["parties"][psoe_i]
            if a in "SNA" and b in "SNA":
                tot += 1
                same += a == b
        align[pid] = {"same_as_psoe_pct": round(100 * same / tot, 1) if tot else None, "votes": tot}
    for i in items:
        del i["t"]
    return {
        "source": {"label": "Atlas de votaciones del Congreso (legislaturas XIV y XV)", "file": "/citizen/data/vote_atlas_v1.json",
                   "sha256": raw_sha, "generated_at": atlas["meta"]["generated_at"], "qa": atlas["meta"].get("review", {}).get("agreement")},
        "parties_order": pids, "summary": summary, "items": items, "alignment_with_psoe_leg15": align,
        "coverage_note": "En la XIV solo hay posición para los grupos que equivalen a un partido (PSOE, PP, Vox, ERC, EH Bildu y PNV); Unidas Podemos era un grupo de varios partidos.",
    }


# ---------------------------------------------------------------- ledger, matrix, sensitivity
def years_in_national_government(seed: dict, today: str) -> dict[str, float]:
    out: Counter = Counter()
    start_w = seed["window"]["start"]
    for g in seed["national_governments"]:
        s = max(g["start"], start_w)
        e = g["end"] or today
        yrs = (date.fromisoformat(e) - date.fromisoformat(s)).days / 365.25
        for p in g["parties"]:
            out[p] += yrs
    return {k: round(v, 2) for k, v in out.items()}


def counted(att: dict) -> bool:
    return att["lineage"] in COUNTED_LINEAGE


def matrix(seed: dict, events: list[dict]) -> dict:
    out = {p["party_id"]: {i["id"]: {"gobierno": [], "fuera": []} for i in seed["codebook"]["indicators"]} for p in seed["parties"]}
    for ev in events:
        for a in ev["attributions"]:
            if not counted(a):
                continue
            side = "gobierno" if a["role"] in GOV_ROLES else "fuera"
            out[a["party_id"]][ev["indicator"]][side].append((ev["event_id"], ev["severity"], ev["coverage"]["type"] == "census"))
    res = {}
    for pid, inds in out.items():
        res[pid] = {}
        for ind, sides in inds.items():
            res[pid][ind] = {}
            for side, lst in sides.items():
                cen = [x for x in lst if x[2]]
                sel = [x for x in lst if not x[2]]
                res[pid][ind][side] = {
                    "n": len(cen), "max_severity": max((x[1] for x in cen), default=0),
                    "selection": len(sel), "max_severity_selection": max((x[1] for x in sel), default=0),
                    "events": [x[0] for x in lst],
                }
    return res


WEIGHTINGS = {
    "W1": "Pesos iguales; gravedad 1-2-3",
    "W2": "Gravedad al cuadrado (1-4-9)",
    "W3": "Solo indicadores de Levitsky y Ziblatt y minorías",
    "W4": "Solo pilares del Estado de Derecho",
    "W5": "W1 sin actos que solo puede hacer quien gobierna",
    "W6": "W1 por año de Gobierno nacional (solo partidos que lo han tenido)",
    "W7": "W1 más la capa de votos (votos vinculantes contra contrapesos × 3)",
}


def sensitivity(seed: dict, events: list[dict], votes: dict, gov_years: dict) -> dict:
    parties = [p["party_id"] for p in seed["parties"]]
    scores: dict[str, dict[str, float | None]] = {w: {} for w in WEIGHTINGS}
    events = [ev for ev in events if ev["coverage"]["type"] == "census"]
    for pid in parties:
        rows = [(ev, a) for ev in events for a in ev["attributions"] if a["party_id"] == pid and counted(a)]
        w1 = sum(ev["severity"] for ev, _a in rows)
        scores["W1"][pid] = w1
        scores["W2"][pid] = sum(ev["severity"] ** 2 for ev, _a in rows)
        scores["W3"][pid] = sum(ev["severity"] for ev, _a in rows if ev["indicator"] in LZ)
        scores["W4"][pid] = sum(ev["severity"] for ev, _a in rows if ev["indicator"] in ROL)
        scores["W5"][pid] = sum(ev["severity"] for ev, a in rows if not a["power_only"])
        scores["W6"][pid] = round(w1 / gov_years[pid], 3) if gov_years.get(pid) else None
        against = 0.0
        for leg in ("14", "15"):
            c = votes["summary"].get(pid, {}).get(leg, {}).get("estructural_vinculante", {})
            if c.get("votes"):
                against += c.get("menos_controles", 0) / c["votes"]
        scores["W7"][pid] = round(w1 + 3 * against, 3)
    active = [p for p in parties if scores["W1"][p] > 0]
    ranks = {}
    for w, sc in scores.items():
        vals = {p: sc[p] for p in active if sc[p] is not None}
        ordered = sorted(vals, key=lambda p: -vals[p])
        ranks[w] = {p: 1 + sum(1 for q in vals if vals[q] > vals[p]) for p in ordered}
    reversals = []
    for (wa, sa), (wb, sb) in itertools.combinations(scores.items(), 2):
        for p, q in itertools.combinations(active, 2):
            if None in (sa[p], sa[q], sb[p], sb[q]):
                continue
            da, db = sa[p] - sa[q], sb[p] - sb[q]
            if da * db < 0:
                reversals.append({"pair": [p, q], "weightings": [wa, wb], "scores": {wa: [sa[p], sa[q]], wb: [sb[p], sb[q]]}})
    publish = len(active) >= 2 and not reversals
    return {
        "rule": "Se publica un nivel compuesto solo si ningún par de partidos invierte su orden entre dos ponderaciones cualesquiera (empates permitidos).",
        "items": "Solo resoluciones de los censos completos (las de selección no son comparables entre partidos).",
        "events_used": len(events),
        "weightings": WEIGHTINGS, "parties_with_items": active, "scores": scores, "ranks": ranks,
        "reversals": reversals, "reversal_count": len(reversals), "publish_composite": publish,
        "composite": ([{"party_id": p, "W1": scores["W1"][p]} for p in sorted(active, key=lambda p: -scores["W1"][p])] if publish else None),
    }


def profiles(seed: dict, events: list[dict], votes: dict, gov_years: dict, vparty: dict) -> list[dict]:
    pending = seed.get("pending") or []
    out = []
    for p in seed["parties"]:
        pid = p["party_id"]
        mine = [ev for ev in events if any(a["party_id"] == pid for a in ev["attributions"])]
        cnt = [ev for ev in mine if any(a["party_id"] == pid and counted(a) for a in ev["attributions"])]
        cen = [ev for ev in cnt if ev["coverage"]["type"] == "census"]
        roles = Counter(a["role"] for ev in cnt for a in ev["attributions"] if a["party_id"] == pid)
        out.append({
            "party_id": pid, "label": p["label"], "note": p.get("note"),
            "national_government_years_in_window": gov_years.get(pid, 0),
            "events_counted": len(cnt), "events_predecessor": len(mine) - len(cnt),
            "events_census": len(cen), "events_selection": len(cnt) - len(cen),
            "severity_sum": sum(ev["severity"] for ev in cnt), "severity_sum_census": sum(ev["severity"] for ev in cen),
            "pending": sum(1 for x in pending if x.get("party_id") == pid),
            "by_role": dict(roles), "by_indicator": dict(Counter(ev["indicator"] for ev in cnt)),
            "no_signal": not cnt,
            "vparty": vparty.get(pid),
            "votes": votes["summary"].get(pid), "alignment_with_psoe_leg15": votes["alignment_with_psoe_leg15"].get(pid),
        })
    return out


def vparty_layer(seed: dict) -> tuple[dict, list[dict]]:
    cfg = seed["vparty"]
    rows = list(csv.DictReader((REPO_ROOT / cfg["extract"]).open(encoding="utf-8")))
    latest = {}
    for r in rows:
        if r["historical_date"] == cfg["election"]:
            latest[r["v2pashname"]] = r

    def pack(r: dict) -> dict:
        f = lambda k: round(float(r[k]), 3) if r.get(k) not in (None, "", "NA", "nan") else None  # noqa: E731
        return {"name": r["v2pashname"], "election": r["historical_date"], "antiplural": f("v2xpa_antiplural"),
                "antiplural_low": f("v2xpa_antiplural_codelow"), "antiplural_high": f("v2xpa_antiplural_codehigh"),
                "pluralism": f("v2paplur"), "demonization": f("v2paopresp"), "minority_rights": f("v2paminor"),
                "violence": f("v2paviol"), "vote_pct": f("v2pavote")}

    by_party = {pid: pack(latest[name]) for pid, name in cfg["map"].items() if name in latest}
    for pid, names in (cfg.get("map_partial") or {}).items():
        by_party[pid] = {"partial": [pack(latest[n]) for n in names if n in latest],
                         "note": "Sin puntuación propia: se muestran los partidos que hoy integra (IU y Comuns, en 2019 dentro de Unidas Podemos)."}
    series = []
    for r in rows:
        if r["v2pashname"] in set(cfg["map"].values()) and r.get("v2xpa_antiplural") not in ("", "NA", None):
            series.append({"name": r["v2pashname"], "election": r["historical_date"], "antiplural": round(float(r["v2xpa_antiplural"]), 3)})
    meta = {k: cfg[k] for k in ("release", "url", "mirror_url", "mirror_note", "sha256", "retrieved", "election", "measures", "does_not_measure")}
    return by_party, [meta | {"series": series}]


def census_summary(seed: dict, events: list[dict], decrees: dict) -> dict:
    by_id = {e["event_id"]: e for e in events}
    fams = []
    for c in seed.get("census") or []:
        evs = [by_id[e] for e in {r.get("event_id") for r in c.get("rows") or []} | set(c.get("already_in_ledger") or []) if e in by_id]
        per_party = Counter(a["party_id"] for e in evs for a in e["attributions"] if counted(a))
        fam = {"family": c["family"], "label": CENSUS_LABELS.get(c["family"], c["family"]), "type": "census",
               "scope": c.get("scope"), "list_source": c.get("list_source"), "n_listed": c.get("n_listed"),
               "n_in_scope": c.get("n_in_scope"), "n_events": len(evs), "by_party": dict(per_party), "rows": c.get("rows") or []}
        if c["family"] == "tc_decreto_ley" and decrees.get("available"):
            ann = Counter()
            for e in evs:
                g = next((g for g in decrees["by_government"] if g["start"] <= e["act_date"] < (g["end"] or "9999")), None)
                if g:
                    ann[g["id"]] += 1
            fam["by_government"] = [{"id": g["id"], "president": g["president"], "party": g["party"], "rdl": g["rdl"], "annulled_rulings": ann.get(g["id"], 0)}
                                    for g in decrees["by_government"] if g["start"] >= "2004"]
            fam["lag_note"] = "Las sentencias llegan años después del decreto: los decretos-leyes recientes pueden estar aún pendientes de recurso."
        fams.append(fam)
    sel = Counter(e["coverage"]["family"] for e in events if e["coverage"]["type"] == "selection")
    for fid, label in SELECTION_FAMILIES.items():
        fams.append({"family": fid, "label": label, "type": "selection", "n_events": sel.get(fid, 0),
                     "scope": "Selección, no censo: casos encontrados en la búsqueda, sin lista oficial completa; no se cuentan ni se comparan entre partidos."})
    return {"families": fams}


# ---------------------------------------------------------------- main
def export() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    today = seed.get("snapshot_date") or date.today().isoformat()
    events = seed["events"]
    gov_years = years_in_national_government(seed, today)
    votes = vote_layer(seed)
    vp_party, vp_meta = vparty_layer(seed)
    sens = sensitivity(seed, events, votes, gov_years)
    decrees = decree_layer(seed, today)
    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "snapshot_date": today,
            "window": seed["window"], "method": seed["method"],
            "seed_sha256": hashlib.sha256(SEED.read_bytes()).hexdigest(),
            "events": len(events), "events_attributed": sum(1 for e in events if any(counted(a) for a in e["attributions"])),
        },
        "codebook": seed["codebook"], "parties": profiles(seed, events, votes, gov_years, vp_party),
        "national_governments": seed["national_governments"], "national_governments_source": seed["national_governments_source"],
        "events": events, "system_findings": seed.get("system_findings") or [],
        "matrix": matrix(seed, events), "votes": votes, "decrees": decrees,
        "census": census_summary(seed, events, decrees), "pending": seed.get("pending") or [],
        "vparty": vp_meta[0], "sensitivity": sens,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["event_id", "coverage", "coverage_family", "date", "act_date", "party_id", "role", "attribution", "lineage", "power_only", "indicator",
                "severity", "finding_type", "body", "title", "act", "status", "source_url", "source_retrieved", "quote"])
    for ev in events:
        for a in ev["attributions"]:
            s = ev["source"]
            w.writerow([ev["event_id"], "censo" if ev["coverage"]["type"] == "census" else "selección, no censo", ev["coverage"]["family"], ev["date"], ev.get("act_date", ""), a["party_id"], a["role"], a["attribution"], a["lineage"],
                        a["power_only"], ev["indicator"], ev["severity"], ev["finding_type"], ev["body"], ev["title"], ev["act"],
                        ev.get("status", ""), s["url"], s["retrieved"], s["quote"]])
    OUT_CSV.write_text(buf.getvalue(), encoding="utf-8")
    kb = OUT_JSON.stat().st_size / 1024
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)} ({kb:.0f} KB), {len(events)} events, "
          f"{len(votes['items'])} votes, composite published: {sens['publish_composite']} ({sens['reversal_count']} reversals)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", nargs="?", default="export", choices=["export", "merge", "fetch-boe"])
    args = ap.parse_args(argv)
    if args.command == "merge":
        return merge()
    if args.command == "fetch-boe":
        return fetch_boe()
    return export()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
