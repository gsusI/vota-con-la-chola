#!/usr/bin/env python3
"""Count housing norms published per year in section I of the BOE (2000-2025).

Source: BOE open-data API, daily summary ("sumario"):
  https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD  (Accept: application/json)
  Docs: https://www.boe.es/datosabiertos/documentos/APIsumarioBOE.pdf
A day without BOE returns HTTP 404 (normal: most Sundays and some holidays).

Raw responses are cached under etl/data/raw/housing/boe_sumarios/YYYY/YYYYMMDD.json
(404 days leave an empty marker YYYYMMDD.404 so reruns and --offline skip them).
Some days return a persistent HTTP 500 ("Server error - Code: 101") for the JSON rendering while
the XML rendering of the same endpoint works (e.g. 2000-08-05); for those days the XML response is
cached as YYYYMMDD.xml and parsed instead.

Output: etl/data/manual/housing/boe_housing_norms_es.json

Usage:
  python3 scripts/boe_housing_norms.py                 # download missing days + build
  python3 scripts/boe_housing_norms.py --offline       # build from cache only
  python3 scripts/boe_housing_norms.py --start 2019-01-01 --end 2019-12-31 --sample 15
stdlib only.
"""
import argparse, datetime as dt, hashlib, json, os, random, re, sys, threading, time, unicodedata
import urllib.error, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_REL = "etl/data/raw/housing/boe_sumarios"
OUT_REL = "etl/data/manual/housing/boe_housing_norms_es.json"
API = "https://www.boe.es/datosabiertos/api/boe/sumario/{}"
UA = "Mozilla/5.0 (compatible; vota-con-la-chola-etl/1.0; +https://votaconlachola.org)"
HOST = "www.boe.es"

# Housing regex, applied to the accent-folded, lower-cased title.
HOUSING_RE_TEXT = (r"\b(vivienda|viviendas|alquiler|arrendamientos? urbanos?|desahucios?|"
                   r"suelo y rehabilitacion|rehabilitacion edificatoria|parque publico de vivienda)\b")
HOUSING_RE = re.compile(HOUSING_RE_TEXT)

# Exclusion rules (each one tested on the 2000-2025 section-I titles; see run notes).
# 1) Issuing-body names: "Ministerio/Ministra/Ministro de Vivienda", "Secretaría de Estado de
#    Vivienda", "Consejería de ... Vivienda" etc. are removed from the title before matching, so a
#    title that mentions housing only as the name of a department (e.g. structure decrees of the
#    Ministerio de Vivienda, or an order "a propuesta de la Ministra de Vivienda") does not match.
DEPT_NAME_RE = re.compile(
    r"\b(ministerio|ministra|ministro|ministros|secretaria de estado|secretaria general|"
    r"direccion general|consejeria|conselleria|departamento|vicepresidencia)\s+de\s+"
    r"(vivienda|[a-z ,]{0,60}?\by vivienda)(\s+y\s+agenda urbana)?\b")
# 2) Non-normative items in section I: constitutional-court appeals/questions/conflicts and court
#    rulings ("Recurso de inconstitucionalidad ... contra la Ley de vivienda") are not norms.
NON_NORM_TITLE_RE = re.compile(r"^(recurso|cuestion|conflicto|sentencia|auto|impugnacion)\b")
NON_NORM_DEPT_RE = re.compile(r"\b(tribunal|consejo general del poder judicial)\b")
# 3) Corrections of errors ("Corrección de errores/erratas ...") re-publish an existing norm; they
#    are not counted as new norms.
CORRECTION_RE = re.compile(r"^correccion de (errores|erratas|error)\b|"
                           r"\bpor (la|el) que se corrigen? (los )?(errores|erratas)\b")
# 4) Parliamentary validation acts ("Resolución ... por la que se ordena la publicación del
#    Acuerdo de convalidación/derogación del Real Decreto-ley ...") re-reference an already counted
#    decree-law (e.g. the Congress repeal of RDL 21/2018 in January 2019).
CONVALIDATION_RE = re.compile(r"\bconvalidacion\b|\bacuerdo de derogacion\b")
# 5) "alquiler"/"arrendamiento" of non-housing assets (vehicles, ships, aircraft, equipment,
#    financial leasing, rural leases are already outside the regex).
NON_HOUSING_RENT_RE = re.compile(
    r"\b(alquiler|arrendamiento)s? (de )?(vehiculos?|automoviles|buques?|embarcaciones|aeronaves?|"
    r"maquinaria|equipos?|bicicletas|motocicletas|coches?|turismos?|(los )?contadores|"
    r"(los )?(equipos|aparatos) de medida)\b|\balquiler con conductor\b")
#    (energy tariff orders "tarifas de gas natural ... y alquiler de contadores" are the main case).
# 6) Statistical operations: "Censos de Población y Viviendas" / "censos de edificios, locales,
#    viviendas y población" (INE census instructions) are not
#    housing policy; the census phrase is removed before matching.
CENSUS_RE = re.compile(r"\bcensos? de [a-z ,]{0,60}?viviendas?( y (de )?(la )?poblacion)?\b")
# 7) Historical republications: the BOE republished in 2011-2012 old regional laws (e.g. Basque
#    Ley 7/1988 or Ley 17/1994, Murcia Ley 4/2008). A norm whose own number-year ("Ley 17/1994")
#    is two or more years before the BOE date is a late republication, not new output that year.
NORM_YEAR_RE = re.compile(r"^[^,]{0,80}?\b\d+/((?:19|20)\d{2})\b")

AUTONOMIC_DEPT_RE = re.compile(
    r"^(comunidad|comunitat|region|principado|illes|islas|generalitat|ciudad autonoma|ciudad de|"
    r"pais vasco|cataluna|galicia|andalucia|aragon|canarias|cantabria|castilla|extremadura|"
    r"la rioja|navarra|comunidad foral|madrid|murcia|asturias|valencia)\b")

RANKS = ["ley", "real_decreto_ley", "real_decreto", "orden", "otra"]
_lock = threading.Lock()
_blocked = []


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", s).strip()


def day_paths(d):
    ymd = d.strftime("%Y%m%d")
    base = os.path.join(REPO, RAW_REL, d.strftime("%Y"))
    return os.path.join(base, ymd + ".json"), os.path.join(base, ymd + ".404")


def cached_file(d):
    jp, _ = day_paths(d)
    for p in (jp, jp[:-5] + ".xml"):
        if os.path.exists(p):
            return p
    return None


def fetch_day(d, timeout=60, attempts=6):
    """Returns 'cached'|'ok'|'ok_xml'|'404'|'error:<msg>'|'blocked:<msg>'."""
    jp, np_ = day_paths(d)
    if cached_file(d) or os.path.exists(np_):
        return "cached"
    st = _fetch(d, jp, np_, "application/json", timeout, attempts)
    if st.startswith("error:HTTP 5"):
        st2 = _fetch(d, jp[:-5] + ".xml", np_, "application/xml", timeout, 3)
        return "ok_xml" if st2 == "ok" else st + " (xml fallback: " + st2 + ")"
    return st


def _fetch(d, jp, np_, accept, timeout, attempts):
    if _blocked:
        return "blocked:aborted"
    url = API.format(d.strftime("%Y%m%d"))
    last = ""
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type", "")
            head = data[:200].lstrip().lower()
            if head.startswith(b"<!doctype html") or head.startswith(b"<html") or "text/html" in ctype:
                with _lock:
                    _blocked.append(f"{HOST}: HTML instead of JSON for {url} (possible WAF challenge)")
                return "blocked:html"
            if accept == "application/json":  # validate before caching
                json.loads(data)
            else:
                root = ET.fromstring(data)
                if root.findtext("status/code") != "200":
                    raise ValueError("xml status " + str(root.findtext("status/code")))
            os.makedirs(os.path.dirname(jp), exist_ok=True)
            tmp = jp + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, jp)
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                os.makedirs(os.path.dirname(np_), exist_ok=True)
                open(np_, "wb").close()
                return "404"
            if e.code == 403 or e.headers.get("cf-mitigated"):
                with _lock:
                    _blocked.append(f"{HOST}: HTTP {e.code} for {url}")
                return f"blocked:HTTP {e.code}"
            last = f"HTTP {e.code}"
            if e.code != 429 and e.code < 500:
                break
        except Exception as e:  # timeouts, resets, bad JSON
            last = f"{type(e).__name__}: {e}"
        time.sleep(min(60, 2 ** i + random.random()))
    return "error:" + last


def iter_items(node, dept=None):
    """Yield (department_name, item_dict) for every item under a section node."""
    if isinstance(node, list):
        for x in node:
            yield from iter_items(x, dept)
    elif isinstance(node, dict):
        if "identificador" in node and "titulo" in node:
            yield dept, node
            return
        if "departamento" in node:
            for dep in node["departamento"] if isinstance(node["departamento"], list) else [node["departamento"]]:
                yield from iter_items({k: v for k, v in dep.items() if k not in ("codigo", "nombre")},
                                      dep.get("nombre"))
            return
        for k, v in node.items():
            if k in ("epigrafe", "item"):
                yield from iter_items(v, dept)


def section_one_items(doc):
    diarios = doc["data"]["sumario"]["diario"]
    for diario in diarios if isinstance(diarios, list) else [diarios]:
        secs = diario.get("seccion") or []
        for sec in secs if isinstance(secs, list) else [secs]:
            if str(sec.get("codigo")) == "1" or fold(sec.get("nombre", "")).startswith("i. disposiciones generales"):
                yield from iter_items(sec)


def section_one_items_xml(raw):
    root = ET.fromstring(raw)
    for sec in root.iter("seccion"):
        if sec.get("codigo") == "1" or fold(sec.get("nombre", "")).startswith("i. disposiciones generales"):
            for dep in sec.iter("departamento"):
                for it in dep.iter("item"):
                    yield dep.get("nombre"), {"identificador": it.findtext("identificador"),
                                              "titulo": it.findtext("titulo")}


def rank_of(ft):
    if re.match(r"^ley( organica)?\b", ft):
        return "ley", "ley_organica" if ft.startswith("ley organica") else "ley"
    if re.match(r"^real decreto[- ]ley\b", ft):
        return "real_decreto_ley", "real_decreto_ley"
    if re.match(r"^decreto[- ]ley\b", ft):
        return "real_decreto_ley", "decreto_ley_autonomico"
    if re.match(r"^real decreto legislativo\b", ft):
        return "otra", "real_decreto_legislativo"
    if re.match(r"^decreto legislativo\b", ft):
        return "otra", "decreto_legislativo"
    if re.match(r"^real decreto\b", ft):
        return "real_decreto", "real_decreto"
    if re.match(r"^orden\b", ft):
        return "orden", "orden"
    m = re.match(r"^(\w+)", ft)
    return "otra", (m.group(1) if m else "otra")


def classify(title, dept, year=None):
    """Returns (status, reason) where status in match|exclude|nomatch."""
    ft, fd = fold(title), fold(dept)
    if not HOUSING_RE.search(ft):
        return "nomatch", ""
    stripped = DEPT_NAME_RE.sub(" ", ft)
    if not HOUSING_RE.search(stripped):
        return "exclude", "department_name_only"
    if NON_NORM_TITLE_RE.match(ft) or NON_NORM_DEPT_RE.search(fd):
        return "exclude", "court_or_appeal"
    if CORRECTION_RE.search(ft):
        return "exclude", "correction"
    if CONVALIDATION_RE.search(ft):
        return "exclude", "convalidation"
    if not HOUSING_RE.search(NON_HOUSING_RENT_RE.sub(" ", stripped)):
        return "exclude", "non_housing_rent"
    if not HOUSING_RE.search(CENSUS_RE.sub(" ", stripped)):
        return "exclude", "census"
    m = NORM_YEAR_RE.match(ft)
    if year and m and int(m.group(1)) <= year - 2:
        return "exclude", "late_republication"
    return "match", ""


def scope_of(dept):
    return "autonomica" if AUTONOMIC_DEPT_RE.match(fold(dept)) else "estatal"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2000-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sample", type=int, default=0, help="print N random matches / non-matches with 'vivienda'")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    d0, d1 = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    days = [d0 + dt.timedelta(n) for n in range((d1 - d0).days + 1)]
    gaps = []

    if not a.offline:
        t0, done, stats = time.time(), 0, {}
        with ThreadPoolExecutor(max_workers=min(4, a.workers)) as ex:
            for d, st in zip(days, ex.map(fetch_day, days)):
                done += 1
                k = st.split(":")[0]
                stats[k] = stats.get(k, 0) + 1
                if k in ("error", "blocked") and st != "blocked:aborted":
                    gaps.append(f"{d.isoformat()}: {st}")
                if done % 250 == 0:
                    print(f"[fetch] {done}/{len(days)} {d} {stats} {time.time() - t0:.0f}s", flush=True)
        print(f"[fetch] done {stats} in {time.time() - t0:.0f}s", flush=True)
        if _blocked:
            print("[fetch] BLOCKED:", _blocked[:3], flush=True)

    norms, excluded, viv_nomatch = [], {}, []
    for d in days:
        _, np_ = day_paths(d)
        jp = cached_file(d)
        if not jp:
            if not os.path.exists(np_) and not any(g.startswith(d.isoformat()) for g in gaps):
                gaps.append(f"{d.isoformat()}: not cached")
            continue
        raw = open(jp, "rb").read()
        sha = hashlib.sha256(raw).hexdigest()
        try:
            items = list(section_one_items_xml(raw) if jp.endswith(".xml") else section_one_items(json.loads(raw)))
        except Exception as e:
            gaps.append(f"{d.isoformat()}: unparseable cached sumario ({type(e).__name__})")
            continue
        seen = set()
        for dept, it in items:
            bid, title = it.get("identificador"), (it.get("titulo") or "").strip()
            if bid in seen:
                continue
            seen.add(bid)
            st, why = classify(title, dept or "", d.year)
            if st == "nomatch":
                continue
            if st == "exclude":
                excluded.setdefault(why, []).append((d.isoformat(), bid, dept, title))
                continue
            rank, rank_detail = rank_of(fold(title))
            norms.append({
                "boe_id": bid, "date": d.isoformat(), "title": title, "department": dept or "",
                "scope": scope_of(dept or ""), "rank": rank, "rank_detail": rank_detail,
                "url": f"https://www.boe.es/buscar/doc.php?id={bid}",
                "sumario_file": os.path.relpath(jp, REPO).replace(os.sep, "/"), "sumario_sha256": sha,
            })
        if a.sample:
            for dept, it in items:
                ft = fold(it.get("titulo"))
                if "vivienda" in ft and classify(it.get("titulo"), dept or "")[0] == "nomatch":
                    viv_nomatch.append((d.isoformat(), it.get("identificador"), dept, it.get("titulo")))

    years = []
    for y in range(d0.year, d1.year + 1):
        ys = [n for n in norms if n["date"].startswith(str(y))]
        years.append({"year": y, "total": len(ys),
                      "estatal": sum(n["scope"] == "estatal" for n in ys),
                      "autonomica": sum(n["scope"] == "autonomica" for n in ys),
                      "by_rank": {r: sum(n["rank"] == r for n in ys) for r in RANKS}})
        print(f"{y}: total={len(ys):4d} est={years[-1]['estatal']:3d} aut={years[-1]['autonomica']:3d} {years[-1]['by_rank']}")
    print("excluded:", {k: len(v) for k, v in excluded.items()})

    if a.sample:
        rnd = random.Random(42)
        print("\n--- sample matches ---")
        for n in rnd.sample(norms, min(a.sample, len(norms))):
            print(f"{n['boe_id']} [{n['scope']}/{n['rank']}] {n['department'][:30]} | {n['title'][:170]}")
        for why, rows in excluded.items():
            print(f"\n--- sample excluded: {why} ({len(rows)}) ---")
            for r in rnd.sample(rows, min(6, len(rows))):
                print(f"{r[1]} {str(r[2])[:30]} | {r[3][:170]}")
        print(f"\n--- section-I titles with 'vivienda' not matched: {len(viv_nomatch)} ---")
        for r in rnd.sample(viv_nomatch, min(10, len(viv_nomatch))):
            print(f"{r[1]} {str(r[2])[:30]} | {r[3][:170]}")

    if a.no_write:
        return
    out = {
        "generated_by": "scripts/boe_housing_norms.py",
        "retrieved_at": dt.datetime.now(dt.timezone.utc).date().isoformat(),
        "source": "https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD",
        "period": [a.start, a.end],
        "method": (
            "Recuento de disposiciones publicadas en la sección I (Disposiciones generales) del sumario "
            "diario del BOE cuyo título contiene términos de vivienda (expresión regular sin distinguir "
            "mayúsculas ni tildes). Se excluyen menciones que solo nombran al órgano emisor (Ministerio/"
            "Consejería de Vivienda), recursos y sentencias, correcciones de errores, convalidaciones "
            "parlamentarias, alquileres de bienes no residenciales los Censos de Población y Viviendas y las republicaciones tardías de leyes autonómicas antiguas. Ámbito: 'autonomica' si el "
            "departamento es una comunidad o ciudad autónoma (leyes autonómicas republicadas en el BOE), "
            "'estatal' en otro caso. Rango por el inicio del título; 'real_decreto_ley' incluye decretos-ley "
            "autonómicos y 'otra' incluye reales decretos legislativos, resoluciones, acuerdos, convenios, "
            "etc. Límites: es un recuento de títulos, no de contenido; normas de vivienda cuyo título no "
            "usa estos términos (p. ej. leyes de presupuestos u ómnibus con medidas de vivienda, normas de "
            "suelo o urbanismo) no se cuentan; las CCAA publican antes en su propio diario oficial y no todas "
            "sus normas llegan al BOE; un mayor número de normas no implica más o mejor política."),
        "regex": HOUSING_RE_TEXT,
        "exclusions": [
            "Nombre de órgano emisor eliminado antes de buscar: " + DEPT_NAME_RE.pattern,
            "Recursos, cuestiones, conflictos y sentencias (título): " + NON_NORM_TITLE_RE.pattern
            + " ; departamentos judiciales: " + NON_NORM_DEPT_RE.pattern,
            "Correcciones de errores (no son normas nuevas): " + CORRECTION_RE.pattern,
            "Convalidaciones o derogaciones parlamentarias de reales decretos-ley ya contados: " + CONVALIDATION_RE.pattern,
            "Alquiler/arrendamiento de bienes no residenciales: " + NON_HOUSING_RENT_RE.pattern,
            "Censos de Población y Viviendas (operación estadística, no política de vivienda): " + CENSUS_RE.pattern,
            "Republicaciones tardías (año del número de la norma <= año de publicación en el BOE - 2; p. ej. leyes "
            "vascas de 1983-1994 republicadas en 2012): " + NORM_YEAR_RE.pattern,
        ],
        "excluded_counts": {k: len(v) for k, v in sorted(excluded.items())},
        "years": years,
        "norms": norms,
        "gaps": gaps,
        "blocked_hosts": sorted(set(_blocked)),
    }
    op = os.path.join(REPO, OUT_REL)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {OUT_REL}: {len(norms)} norms, {len(gaps)} gaps")


if __name__ == "__main__":
    sys.exit(main())
