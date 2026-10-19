#!/usr/bin/env python3
"""Growth of tax-law complexity in Spain, computed from BOE open data.

Stdlib only. Run: python3 scripts/boe_tax_complexity.py  (from any cwd)
Every HTTP response is cached under etl/data/raw/public_finance/boe/; reruns read the cache.
Output: etl/data/manual/public_finance/tax_complexity_es.json (loaded by scripts/ingest_public_finance_es.py).
"""
import json, os, re, sys, time, threading, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(REPO, "etl", "data", "raw", "public_finance", "boe")
OUT = os.path.join(REPO, "etl", "data", "manual", "public_finance", "tax_complexity_es.json")
API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
UA = "Mozilla/5.0 (compatible; vota-con-la-chola-etl/1.0; +https://votaconlachola.org)"
_lock = threading.Lock()
_last = [0.0]


def fetch(url, name, accept="application/xml"):
    path = os.path.join(RAW, name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    for attempt in range(4):
        with _lock:  # polite pacing: >=0.25 s between request starts
            wait = 0.25 - (time.time() - _last[0])
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
            data = urllib.request.urlopen(req, timeout=120).read()
            break
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                data = b"HTTPERROR %d" % e.code
                break
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    with open(path, "wb") as f:
        f.write(data)
    return data


def xml_or_none(data):
    if data.startswith(b"HTTPERROR"):
        return None
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        return None


def cons(bid, part):
    return xml_or_none(fetch(f"{API}/id/{bid}/{part}", f"cons_{bid}_{part}.xml"))


def orig(bid):
    return xml_or_none(fetch(f"https://www.boe.es/diario_boe/xml.php?id={bid}", f"orig_{bid}.xml"))


def ymd(s):
    s = (s or "").strip()
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if re.fullmatch(r"\d{8}", s) else None


def text_of(e):
    return " ".join("".join(e.itertext()).split())


WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]")


def count_words(s):
    # word = whitespace-separated token containing at least one letter or digit
    return sum(1 for t in s.split() if WORD_RE.search(t))


# ---------------------------------------------------------------- A. amendments
LAWS_A = [
    ("Ley 58/2003 General Tributaria", "BOE-A-2003-23186", ["58/2003", "General Tributaria"]),
    ("Ley 35/2006 IRPF", "BOE-A-2006-20764", ["35/2006", "Renta de las Personas Físicas"]),
    ("Ley 27/2014 Impuesto sobre Sociedades", "BOE-A-2014-12328", ["27/2014", "Impuesto sobre Sociedades"]),
    ("Ley 37/1992 IVA", "BOE-A-1992-28740", ["37/1992", "Valor Añadido"]),
    ("Ley 38/1992 Impuestos Especiales", "BOE-A-1992-28741", ["38/1992", "Impuestos Especiales"]),
    ("RDLeg 2/2004 Haciendas Locales", "BOE-A-2004-4214", ["2/2004", "Haciendas Locales"]),
    ("Ley 19/1991 Impuesto sobre el Patrimonio", "BOE-A-1991-14392", ["19/1991", "Patrimonio"]),
    ("Ley 29/1987 Sucesiones y Donaciones", "BOE-A-1987-28141", ["29/1987", "Sucesiones y Donaciones"]),
    ("RDLeg 1/1993 ITPAJD", "BOE-A-1993-25359", ["1/1993", "Transmisiones Patrimoniales"]),
    ("RD 439/2007 Reglamento IRPF", "BOE-A-2007-6820", ["439/2007", "Reglamento del Impuesto sobre la Renta"]),
]
# relation codes (BOE "relacion@codigo") counted as a legislative modification of the law
MOD_LABEL_RE = re.compile(r"^SE (MODIFICA|AÑADE|DEROGA|SUPRIME|DA NUEVA REDACCI|SUSTITUYE|DEJA SIN EFECTO|SUSPENDE|PRORROGA|AMPLÍA|REDUCE|ELEVA)", re.I)


def meta_cons(bid):
    r = cons(bid, "metadatos")
    if r is None:
        return None
    m = r.find(".//metadatos")
    if m is None:
        return None
    return {"title": m.findtext("titulo"), "fecha_disposicion": ymd(m.findtext("fecha_disposicion")),
            "fecha_publicacion": ymd(m.findtext("fecha_publicacion")), "rango": m.findtext("rango"),
            "estatus_derogacion": m.findtext("estatus_derogacion"), "src": "legislacion-consolidada/metadatos"}


def meta_any(bid):
    m = meta_cons(bid)
    if m:
        return m
    r = orig(bid)
    if r is None or r.find("metadatos") is None:
        return None
    m = r.find("metadatos")
    return {"title": m.findtext("titulo"), "fecha_disposicion": ymd(m.findtext("fecha_disposicion")),
            "fecha_publicacion": ymd(m.findtext("fecha_publicacion")), "rango": m.findtext("rango"),
            "src": "diario_boe/xml.php"}


def title_short(t):
    t = (t or "").strip()
    m = re.match(r"^(.*?\d+/\d{4}, de \d+ de \w+)", t)
    return m.group(1) if m else t[:120]


def amendments(gaps):
    out, all_labels = [], Counter()
    plans = []
    for name, bid, must in LAWS_A:
        md = meta_cons(bid)
        ok = bool(md) and all(x.lower() in (md["title"] or "").lower() for x in must)
        if not ok:
            gaps.append(f"A: id check failed for {name} ({bid}): title={md and md['title']!r}")
            continue
        an = cons(bid, "analisis")
        posts = an.findall(".//referencias/posteriores/posterior")
        labels_all = Counter()
        mod = defaultdict(set)
        for p in posts:
            rel = p.find("relacion")
            code, label = rel.get("codigo"), (rel.text or "").strip()
            labels_all[f"{code} {label}"] += 1
            nid = p.findtext("id_norma")
            if MOD_LABEL_RE.match(label):
                if nid and nid.startswith("BOE-"):
                    mod[nid].add(label)
                else:
                    gaps.append(f"A: {name}: modifying reference without BOE id: {nid!r} {label}")
        all_labels.update(labels_all)
        plans.append((name, bid, md, labels_all, mod))
    ids = sorted({n for *_, mod in plans for n in mod})
    with ThreadPoolExecutor(4) as ex:
        metas = dict(zip(ids, ex.map(meta_any, ids)))
    for name, bid, md, labels_all, mod in plans:
        norms, by_year = [], Counter()
        for nid in sorted(mod):
            m = metas.get(nid) or {}
            date = m.get("fecha_publicacion")
            year = int(date[:4]) if date else int(nid.split("-")[2])  # BOE id year = publication year
            if not date:
                gaps.append(f"A: no metadata for modifying norm {nid} (year taken from BOE id)")
            by_year[year] += 1
            norms.append({"boe_id": nid, "date": date, "title_short": title_short(m.get("title")),
                          "relations": sorted(mod[nid])})
        norms.sort(key=lambda x: (x["date"] or "", x["boe_id"]))
        y0, y1 = int(md["fecha_publicacion"][:4]), max(list(by_year) + [int(md["fecha_publicacion"][:4])])
        cum, run = {}, 0
        for y in range(y0, y1 + 1):
            run += by_year.get(y, 0)
            cum[str(y)] = run
        counted = sorted({l for s in mod.values() for l in s})
        out.append({
            "law": name, "boe_id": bid, "title_official": md["title"],
            "url": f"https://www.boe.es/buscar/act.php?id={bid}",
            "api_analisis": f"{API}/id/{bid}/analisis",
            "enacted": md["fecha_disposicion"], "published": md["fecha_publicacion"],
            "relation_labels_counted": counted,
            "relation_labels_all": dict(labels_all.most_common()),
            "by_year": {str(y): by_year[y] for y in sorted(by_year)},
            "cumulative": cum, "total": len(mod), "modifying_norms": norms,
        })
    return out, all_labels


# ---------------------------------------------------------------- B/C. length & structure
HEAD_CLASSES = {"titulo_num", "titulo", "capitulo_num", "capitulo", "articulo", "libro", "libro_num", "seccion"}
FIRMA_RE = re.compile(r"^firma")


def words_original(bid):
    r = orig(bid)
    m, t = r.find("metadatos"), r.find("texto")
    paras = [e for e in t if e.tag in ("p", "table", "blockquote", "div")]
    total = disp = 0
    started = False
    arts = 0
    # walk top-level children in order; preamble = everything before first structural heading
    for e in paras:
        cls = e.get("class") or ""
        w = count_words(text_of(e))
        total += w
        if not started and e.tag == "p" and cls in HEAD_CLASSES:
            started = True
        if started and not FIRMA_RE.match(cls):
            disp += w
        if e.tag == "p" and cls == "articulo" and re.match(r"^(Artículo|Art\.)\s", text_of(e)):
            arts += 1
    return {"title": m.findtext("titulo"), "published": ymd(m.findtext("fecha_publicacion")),
            "words": total, "words_excl_preamble": disp if started else None, "articles": arts,
            "source": f"https://www.boe.es/diario_boe/xml.php?id={bid}"}


def consolidated(bid):
    r = cons(bid, "texto")
    md = meta_cons(bid)
    upd = r.find(".//texto")
    total = disp = 0
    struct = Counter()
    emptied = Counter()
    text_norms = set()
    for b in r.iter("bloque"):
        tipo, tit = b.get("tipo"), (b.get("titulo") or "").strip()
        vs = b.findall("version")
        for v in vs:
            if v.get("id_norma") and v.get("id_norma") != bid:
                text_norms.add(v.get("id_norma"))
        if tipo == "nota_inicial" or not vs:
            continue
        v = vs[-1]  # current version = last version of the block
        w = 0
        for e in v:
            if e.tag == "blockquote":  # BOE editorial notes (nota_pie: "Se modifica por ...")
                continue
            if e.tag == "p" and (e.get("class") or "").startswith("nota_pie"):
                continue
            w += count_words(text_of(e))
        total += w
        if tipo not in ("preambulo", "firma"):
            disp += w
        if tipo == "precepto":
            kind = None
            for k, rx in [("articulos", r"^Art[íi]culo"), ("disp_adicionales", r"^Disposici[óo]n adicional"),
                          ("disp_transitorias", r"^Disposici[óo]n transitoria"),
                          ("disp_derogatorias", r"^Disposici[óo]n derogatoria"),
                          ("disp_finales", r"^Disposici[óo]n final"), ("anexos", r"^Anexo")]:
                if re.match(rx, tit, re.I):
                    kind = k
                    break
            kind = kind or "otros_bloques_precepto"
            struct[kind] += 1
            parts = [text_of(e) for e in v if e.tag != "blockquote" and not (e.get("class") or "").startswith("nota_pie")]
            rest = " ".join(parts[1:]).strip()  # parts[0] = block heading
            if re.fullmatch(r"\(?\s*(Derogad|Suprimid|Sin contenido|Anulad|Sin efecto)[a-z]*\s*\)?\.?", rest, re.I):
                emptied[kind] += 1
    return {"title": md["title"], "version_date": None, "words": total, "words_excl_preamble": disp,
            "structure": dict(struct), "emptied_blocks": dict(emptied),
            "distinct_norms_in_text_versions": len(text_norms),
            "source": f"{API}/id/{bid}/texto"}


LENGTH = [
    ("irpf", "Ley 44/1978 IRPF", "BOE-A-1978-23326", ["44/1978"]),
    ("irpf", "Ley 18/1991 IRPF", "BOE-A-1991-14391", ["18/1991"]),
    ("irpf", "Ley 40/1998 IRPF", "BOE-A-1998-28472", ["40/1998"]),
    ("irpf", "RDLeg 3/2004 TR Ley IRPF", "BOE-A-2004-4347", ["3/2004"]),
    ("irpf", "Ley 35/2006 IRPF", "BOE-A-2006-20764", ["35/2006"]),
    ("is", "Ley 61/1978 Impuesto sobre Sociedades", "BOE-A-1978-31230", ["61/1978"]),
    ("is", "Ley 43/1995 Impuesto sobre Sociedades", "BOE-A-1995-27752", ["43/1995"]),
    ("is", "RDLeg 4/2004 TR Ley IS", "BOE-A-2004-4456", ["4/2004"]),
    ("is", "Ley 27/2014 Impuesto sobre Sociedades", "BOE-A-2014-12328", ["27/2014"]),
]
CONSOLIDATED_NOW = {"BOE-A-2006-20764", "BOE-A-2014-12328"}
STRUCT_LAWS = [("irpf", "Ley 35/2006 IRPF", "BOE-A-2006-20764"), ("is", "Ley 27/2014 IS", "BOE-A-2014-12328"),
               ("iva", "Ley 37/1992 IVA", "BOE-A-1992-28740"), ("lgt", "Ley 58/2003 LGT", "BOE-A-2003-23186")]


def last_update(bid):
    r = cons(bid, "metadatos")
    s = r.findtext(".//fecha_actualizacion") or ""
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else None


def length_and_structure(gaps):
    rows, struct = [], []
    for tax, name, bid, must in LENGTH:
        o = words_original(bid)
        if not all(x in (o["title"] or "") for x in must):
            gaps.append(f"B: id check failed {name} {bid}: {o['title']!r}")
            continue
        rows.append({"tax": tax, "law": name, "boe_id": bid, "title_official": o["title"],
                     "year": int(o["published"][:4]), "version": "original", "published": o["published"],
                     "words": o["words"], "words_excl_preamble": o["words_excl_preamble"],
                     "articles": o["articles"], "source": o["source"]})
        if bid in CONSOLIDATED_NOW:
            c = consolidated(bid)
            d = last_update(bid)
            rows.append({"tax": tax, "law": name, "boe_id": bid, "title_official": c["title"],
                         "year": int(d[:4]), "version": f"consolidated-{d}",
                         "words": c["words"], "words_excl_preamble": c["words_excl_preamble"],
                         "articles": c["structure"].get("articulos"), "source": c["source"]})
    for tax, name, bid in STRUCT_LAWS:
        c = consolidated(bid)
        d = last_update(bid)
        struct.append({"tax": tax, "law": name, "boe_id": bid, "version": f"consolidated-{d}",
                       "counts": c["structure"], "of_which_emptied_derogated_or_no_content": c["emptied_blocks"],
                       "words": c["words"], "words_excl_preamble": c["words_excl_preamble"],
                       "distinct_norms_in_text_versions": c["distinct_norms_in_text_versions"],
                       "source": c["source"], "url": f"https://www.boe.es/buscar/act.php?id={bid}"})
    return rows, struct


# ---------------------------------------------------------------- D. tax norms by year
TAX_MATERIA_RE = re.compile(r"^(Impuestos?\b|Arbitrio|Contribuci[óo]n Territorial|Contribuciones especiales|Gravamen|"
                            r"Sistema tributario|Tasas fiscales|Cesi[óo]n de Tributos|Incentivos fiscales|Desgravaci[óo]n fiscal|"
                            r"Reg[íi]menes tributarios|R[ée]gimen Tributario|R[ée]gimen Fiscal|Transparencia fiscal|"
                            r"Devoluci[óo]n de ingresos tributarios|Gesti[óo]n fiscal|Inspecci[óo]n fiscal|Informaci[óo]n tributaria)")


def tax_norms_by_year(gaps):
    j = json.loads(fetch("https://www.boe.es/datosabiertos/api/datos-auxiliares/materias", "materias.json", "application/json"))
    mats = {k: v for k, v in j["data"].items() if TAX_MATERIA_RE.match(v)}
    seen = {}
    for code in sorted(mats, key=int):
        q = {"query": {"query_string": {"query": f"materia@codigo:{code}"},
                       "range": {"fecha_publicacion": {"gte": "19600101", "lte": "20251231"}}}}
        url = f"{API}?query={urllib.parse.quote(json.dumps(q))}&limit=10000"
        d = json.loads(fetch(url, f"search10k_materia_{code}.json", "application/json"))
        data = d.get("data") or []
        if len(data) >= 10000:
            gaps.append(f"D: materia {code} returned exactly {len(data)} rows (possible truncation)")
        for x in data:
            seen[x["identificador"]] = x
    by_all, by_state = Counter(), Counter()
    for x in seen.values():
        y = (x.get("fecha_publicacion") or "")[:4]
        if not y.isdigit() or not (1960 <= int(y) <= 2025):
            continue
        by_all[y] += 1
        amb = x.get("ambito") or {}
        if (amb.get("codigo") if isinstance(amb, dict) else None) == "1":
            by_state[y] += 1
    years = [str(y) for y in range(1960, 2026)]
    return {"materias_used": mats, "query": "materia@codigo:<code> with range fecha_publicacion 19600101..20251231, limit=10000 (limit=-1 is silently capped at 50), union of distinct identificador",
            "scope_caveat": "Counts norms present in the BOE consolidated-legislation database (mostly in force or recently consolidated); "
                            "repealed historical norms are largely absent, so earlier years are undercounted (survivorship). Not a count of all tax norms ever published.",
            "estatal": {y: by_state.get(y, 0) for y in years},
            "all_ambitos": {y: by_all.get(y, 0) for y in years},
            "distinct_norms": len(seen)}


def main():
    os.makedirs(RAW, exist_ok=True)
    gaps = []
    am, labels = amendments(gaps)
    print("A done:", [(a["law"][:22], a["total"]) for a in am])
    ll, st = length_and_structure(gaps)
    print("B/C done:", [(r["law"][:20], r["version"], r["words"], r["words_excl_preamble"]) for r in ll])
    try:
        tn = tax_norms_by_year(gaps)
        print("D done: distinct", tn["distinct_norms"])
    except Exception as e:
        tn = None
        gaps.append(f"D: failed: {e!r}")
    gaps.append("A: id fix: Ley 29/1987 Sucesiones y Donaciones is BOE-A-1987-28141 (the given BOE-A-1987-27215 returns 404 in legislacion-consolidada); found via search numero_oficial:29/1987.")
    gaps.append("A: not counted as modifications (see relation_labels_all per law): SE ACTUALIZA (budget-law updates of amounts), SE INTERPRETA, SE DICTA DE CONFORMIDAD, SE DESARROLLA, SE DECLARA (court rulings), error corrections.")
    gaps.append("C: 'articulos' counts every article block present in the consolidated text, including emptied ones (see of_which_emptied...); 'bis/ter' articles count as separate blocks.")
    gaps.append("B: Ley 35/2006 and Ley 27/2014 originals include final provisions amending other laws (counted in their word totals, as published).")
    gaps.append("B: 1932 Contribución General sobre la Renta (Ley de 20-12-1932, Gaceta de Madrid): Gazeta items are PDF-only; "
                "diario_boe/xml.php has no XML text for Gazeta ids (probe BOE-A-1932-1/500/5000/10000 -> 'Documento con referencia desconocida'). Not computed.")
    gaps.append("B: original-text predecessor ids found by following 'referencias anteriores' (DEROGA) in diario_boe/xml.php: "
                "35/2006->BOE-A-2004-4347->BOE-A-1998-28472->BOE-A-1991-14391->BOE-A-1978-23326; 27/2014->BOE-A-2004-4456->BOE-A-1995-27752->BOE-A-1978-31230; titles verified by script.")
    res = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": (
            "All figures computed by scripts/boe_tax_complexity.py (stdlib) from BOE open data; raw responses cached in etl/data/raw/public_finance/boe/. "
            "A) /legislacion-consolidada/id/{id}/analisis -> referencias/posteriores; a later norm is counted once if any of its relations "
            f"has a label matching {MOD_LABEL_RE.pattern!r} (modify/add/partial repeal/suppress/new wording/replace/leave without effect/suspend/extend); excluded: error corrections, "
            "court rulings (SE DECLARA), development/implementation (SE DESARROLLA, SE DICTA DE CONFORMIDAD), appeals, citations. "
            "Year = BOE publication date of the modifying norm (metadatos; xml.php fallback). Count = distinct modifying norms, not individual changes. "
            "B) words = whitespace tokens containing a letter or digit, after stripping XML tags. Original = <texto> of diario_boe/xml.php "
            "(BOE metadata/analysis excluded); words_excl_preamble starts at the first structural heading (título/capítulo/artículo) and drops signature lines. "
            "Consolidated = last <version> of each <bloque> of /texto, excluding the nota_inicial block and BOE editorial notes (blockquote/nota_pie). "
            "1978 laws have no preamble, so words_excl_preamble is the comparable series. "
            "C) block counts by block title in consolidated /texto (tipo=precepto); emptied = current text only says derogado/suprimido/sin contenido."),
        "amendments": am,
        "relation_labels_seen_all_laws": dict(labels.most_common()),
        "law_length": ll,
        "structure": st,
        "tax_norms_by_year": tn,
        "gaps": gaps,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("wrote", OUT, "gaps:", len(gaps))


if __name__ == "__main__":
    main()
