#!/usr/bin/env python3
"""Census: Constitutional Court rulings (BOE 2012-01-01..today) that annul provisions of a state Real Decreto-ley for
breaching the limits of art. 86 CE (urgency, connection of meaning, excluded matters).

Deterministic: (1) BOE search, section TC, titles containing «Real Decreto-ley»; (2) rulings whose BOE doctrine summary
cites the limits of decree-laws; (3) fallo read from the BOE text, kept if it declares nullity; (4) ground coded by the
rules in GROUND below (the summary or the conclusion of the reasoning must tie the nullity to art. 86, not to the
distribution of competences or another principle alone); (5) the decree-law's date gives the government (party).
Writes etl/data/seeds/democracy_conduct_v1.d/events_census_tc_decreto_ley.json and the full candidate list with the
reason for each in evidence/census-tc-decreto-ley.json.

    python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/census_tc_decreto_ley.py
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(HERE))
import kit  # noqa: E402

OUT = REPO / "etl/data/seeds/democracy_conduct_v1.d/events_census_tc_decreto_ley.json"
EVIDENCE = HERE.parent / "evidence/census-tc-decreto-ley.json"
SEARCH_PARAMS = [
    ("campo[0]", "ORIS"), ("dato[0][T]", "T"), ("operador[0]", "and"), ("campo[1]", "TITULOS"), ("dato[1]", "Real Decreto-ley"),
    ("operador[1]", "and"), ("campo[2]", "DEM"), ("dato[2]", ""), ("operador[2]", "and"), ("campo[3]", "DOC"), ("dato[3]", ""),
    ("operador[3]", "and"), ("campo[4]", "NBOS"), ("dato[4]", ""), ("operador[4]", "and"), ("campo[5]", "NOF"), ("dato[5]", ""),
    ("operador[5]", "and"), ("campo[6]", "FPU"), ("dato[6][0]", "2012-01-01"), ("dato[6][1]", date.today().isoformat()),
    ("operador[6]", "and"), ("page_hits", "2000"), ("sort_field[0]", "FPU"), ("sort_order[0]", "asc"), ("accion", "Buscar"),
]
SEARCH_URL = "https://www.boe.es/buscar/boe.php?" + urllib.parse.urlencode(SEARCH_PARAMS)
# Ground coding (read from the BOE doctrine summary and, where it lists several doctrines, the reasoning's conclusion).
GROUND = {
    "156/2021": ("out", "nulidad por igualdad (art. 14) y tutela judicial (art. 24); el FJ 5 confirma el presupuesto habilitante (revisión completa)"),
    "1/2012": ("out", "nulidad por distribución de competencias en medio ambiente (Real Decreto-ley 9/2000), no por el art. 86"),
    "63/2017": ("out", "nulidad por competencias (funciones ejecutivas de la Organización Nacional de Trasplantes), no por el art. 86"),
    "182/2013": ("out", "nulidad por distribución de competencias (informe autonómico), no por el art. 86"),
    "18/2016": ("out", "FJ: «contrarios al orden constitucional de distribución de competencias»"),
    "139/2016": ("out", "nulidad por remisión en blanco al reglamento (reserva de ley), no por el art. 86"),
    "183/2016": ("out", "nulidad por competencias en sanidad y función pública"),
    "34/2017": ("out", "nulidad por competencias en urbanismo y comercio interior (Real Decreto-ley 6/2000)"),
    "136/2015": ("in", "FJ: falta la identificación de la extraordinaria y urgente necesidad (art. 86.1)"),
    "26/2016": ("in", "FJ: «vulneran el art. 86.1 CE y son, por tanto, inconstitucionales y nulos»"),
    "70/2016": ("in", "límite de los decretos-leyes: reserva de ley orgánica"),
}
MONTHS = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"], 1)}
GOVS = [  # (start, end, [(party, lineage, note)])
    ("2004-04-17", "2011-12-21", [("psoe", "same", "Gobierno Rodríguez Zapatero (PSOE)")]),
    ("2011-12-21", "2018-06-02", [("pp", "same", "Gobierno Rajoy (PP)")]),
    ("2018-06-02", "2020-01-13", [("psoe", "same", "Gobierno Sánchez I (PSOE)")]),
    ("2020-01-13", "2023-11-21", [("psoe", "same", "Gobierno Sánchez II (PSOE y Unidas Podemos)"), ("podemos", "list", "Unidas Podemos, socio de coalición del Gobierno Sánchez II")]),
    ("2023-11-21", "9999-12-31", [("psoe", "same", "Gobierno Sánchez III (PSOE y Sumar)"), ("sumar", "same", "Sumar, socio de coalición del Gobierno Sánchez III")]),
]


def es_date(text: str) -> str | None:
    m = re.search(r"(\d{1,2}) de (\w+) de (\d{4})", text)
    return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}" if m and m.group(2).lower() in MONTHS else None


def gov(d: str):
    return next(p for s, e, p in GOVS if s <= d < e)


def main() -> int:
    page = urllib.request.urlopen(urllib.request.Request(SEARCH_URL, headers={"User-Agent": kit.UA}), timeout=120).read().decode("utf-8", "replace")
    results = []
    for it in re.findall(r'<li class="resultado-busqueda">(.*?)</li>', page, re.S):
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", it))).strip()
        ident = re.search(r"BOE-A-\d{4}-\d+", it)
        results.append({"id": ident.group(0) if ident else None, "text": text})
    cands = []
    for r in results:
        summ = r["text"].split("Ir al documento")[0]
        num = re.search(r"Sentencia (\d+/\d{4}), de ([^.]+?\d{4})", summ)
        if not num:
            continue
        if re.search(r"l[ií]mites? (materiales |formales )?(de|a) (los|la) decretos?[- ]leyes?|presupuesto habilitante|extraordinaria y urgente necesidad", summ, re.I) and re.search(r"nulidad|inconstitucional", summ, re.I):
            cands.append(r | {"number": num.group(1), "ruled": es_date(num.group(2)), "summary": summ})

    def fallo(c):
        url = f"https://www.boe.es/diario_boe/txt.php?id={c['id']}"
        body, ct = kit.fetch(url)
        t = re.sub(r"\s+", " ", kit.to_text(body, ct))
        i = t.rfind("FALLO")
        return c | {"url": url, "fallo": t[i: i + 3000].split("Publíquese")[0] if i >= 0 else ""}

    with ThreadPoolExecutor(6) as ex:
        cands = list(ex.map(fallo, cands))
    existing = {}
    for path in (REPO / "etl/data/seeds/democracy_conduct_v1.d").glob("events_*.json"):
        if path == OUT:
            continue
        for ev in json.loads(path.read_text(encoding="utf-8")).get("events") or []:
            m = re.search(r"BOE-A-\d{4}-\d+", (ev.get("source") or {}).get("url") or "")
            if m and not ev.get("_exclude"):
                existing[m.group(0)] = (path.name, ev["event_id"])
    events, evidence = [], []
    for c in cands:
        nul = bool(re.search(r"\bnul[oa]s?\b|nulidad", c["fallo"], re.I))
        ground = GROUND.get(c["number"], ("in", "resumen de doctrina del BOE: nulidad por los límites del decreto ley") if nul else ("out", "el fallo no declara ninguna nulidad"))
        if not nul and c["number"] not in GROUND:
            ground = ("out", "el fallo no declara ninguna nulidad")
        rdl = re.search(r"Real Decreto-ley (\d+/(\d{4})), de (\d{1,2} de \w+)", c["fallo"]) or re.search(r"Real Decreto-ley (\d+/(\d{4})), de (\d{1,2} de \w+)", c["summary"])
        rdl_date = f"{rdl.group(2)}-{MONTHS[rdl.group(3).split(' de ')[1].lower()]:02d}-{int(rdl.group(3).split(' de ')[0]):02d}" if rdl else None
        row = {"number": c["number"], "boe": c["id"], "ruled": c["ruled"], "rdl": rdl.group(1) if rdl else None, "rdl_date": rdl_date,
               "in_census": ground[0] == "in", "reason": ground[1]}
        evidence.append(row)
        if c["id"] in existing:
            row["already_in_ledger"] = existing[c["id"]][1]
        if ground[0] != "in" or not rdl_date or c["id"] in existing:
            continue
        m = re.search(r"(declara[rn]?\b.{0,400})", c["fallo"], re.I)
        words = (m.group(1) if m else c["fallo"]).split()
        quote = " ".join(words[:15]).rstrip(",;")
        full = bool(re.search(r"nulo el Real Decreto-ley \d+/\d{4}|nulo, con el alcance [^.]*, el citado Real Decreto-ley|que el Real Decreto-ley \d+/\d{4}, de [^,]+, es inconstitucional y nulo", c["fallo"]))
        n, y = c["number"].split("/")
        events.append({
            "event_id": f"stc-{n}-{y}-decreto-ley-{rdl.group(1).replace('/', '-')}",
            "title": f"STC {c['number']}: anula {'el' if full else 'preceptos del'} Real Decreto-ley {rdl.group(1)} por los límites del decreto ley",
            "body": "Tribunal Constitucional", "finding_type": "court_annulment_full" if full else "court_annulment_partial",
            "indicator": "contrapesos", "severity": 3 if full else 2, "date": c["ruled"], "act_date": rdl_date,
            "act": f"Real Decreto-ley {rdl.group(1)}, de {rdl.group(3)}" + ("" if full else " (preceptos anulados según el fallo)"),
            "status": "firme",
            "attributions": [{"party_id": p, "role": "national_government", "attribution": "government_act", "lineage": lin, "power_only": True, "note": note}
                             for p, lin, note in gov(rdl_date)],
            "source": {"url": c["url"], "title": c["summary"][c["summary"].find("Pleno"):][:200] or c["number"], "retrieved": date.today().isoformat(),
                       "quote": quote, "quote_lang": "es", "locator": "fallo"},
            "extra_sources": [], "coverage": {"type": "census", "family": "tc_decreto_ley"},
        })
    gen_ids = {e["source"]["url"].split("id=")[-1]: e["event_id"] for e in events}
    census = {
        "family": "tc_decreto_ley",
        "scope": "Sentencias del Tribunal Constitucional publicadas en el BOE desde el 1-1-2012 que anulan preceptos de un real decreto-ley del Estado por los límites del art. 86 de la Constitución (urgencia, conexión de sentido, materias vedadas).",
        "list_source": {"url": SEARCH_URL, "title": "BOE, buscador: sección del Tribunal Constitucional, títulos con «Real Decreto-ley»", "retrieved": date.today().isoformat(),
                        "notes": f"{len(results)} documentos; {len(cands)} sentencias cuyo resumen de doctrina cita los límites del decreto ley; criterio y motivo de cada una en docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/evidence/census-tc-decreto-ley.json"},
        "rows": [{"ref": f"STC {r['number']}", "date": r["ruled"], "subject": f"Real Decreto-ley {r['rdl']}" if r["rdl"] else "", "outcome": "anula preceptos" if r["in_census"] else r["reason"][:100],
                  "in_scope": r["in_census"], "reason": r["reason"][:100], "event_id": r.get("already_in_ledger") or gen_ids.get(r["boe"])} for r in evidence],
        "n_listed": len(evidence), "n_in_scope": sum(r["in_census"] for r in evidence),
    }
    OUT.write_text(json.dumps({"part": "census_tc_decreto_ley", "generated_by": "docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/census_tc_decreto_ley.py",
                               "census": census, "events": events}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    EVIDENCE.write_text(json.dumps({"search_url": SEARCH_URL, "boe_results": len(results), "candidates": len(cands),
                                    "in_census": sum(r["in_census"] for r in evidence), "rows": evidence}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"BOE results {len(results)}, candidates {len(cands)}, in census {len(events)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
