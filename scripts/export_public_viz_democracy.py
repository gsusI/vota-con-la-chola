#!/usr/bin/env python3
"""Export /visualizaciones/democracia/ data: the separation-of-powers safeguard map and its series.

Subcommands
  fetch-boe-eli   Crawl the BOE ELI tree (/eli/es/{rdl,l,lo}/YYYY/MM/DD/N) and store the inventory of royal
                  decree-laws, laws and organic laws as a raw payload (gzip JSON + sha256 of every listing page).
  fetch-peers     Download the peer index series (V-Dem via the Our World in Data mirror, ...) as raw payloads.
  build           Read the seed (etl/data/seeds/democracy_safeguards_v1.json), the raw payloads in
                  etl/data/seeds/democracy_safeguards_v1.d/raw/ and the Congress initiatives DB, and write
                  ui/site/public/visualizaciones/data/democracia.{json,csv}.

Every published number is computed here from a stored payload whose sha256 is recorded in the seed manifest, so the
validator (scripts/validate_democracy_safeguards.py) can recompute it. Network is used only by fetch-*.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = REPO_ROOT / "etl/data/seeds/democracy_safeguards_v1.json"
SEED_DIR = REPO_ROOT / "etl/data/seeds/democracy_safeguards_v1.d"
RAW_DIR = SEED_DIR / "raw"
MANIFEST = RAW_DIR / "manifest.json"
SAFEGUARD_DIR = SEED_DIR / "safeguards"
SNAPSHOT_LIMIT = "2026-11-11"
DEFAULT_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/democracia.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/democracia.csv"

ELI_ROOT = "https://www.boe.es/eli/es"
ELI_TYPES = {"rdl": "Real Decreto-ley", "l": "Ley", "lo": "Ley Orgánica"}
FIRST_YEAR = 1979
UA = "vota-con-la-chola-etl/1.0 (+https://votaconlachola.org)"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def http_get(url: str, timeout: int = 40, tries: int = 4) -> bytes:
    last: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def save_raw(name: str, payload: bytes, meta: dict) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / name).write_bytes(payload)
    manifest = load_manifest()
    entry = {**meta, "file": name, "sha256": sha256_bytes(payload), "bytes": len(payload)}
    manifest[name] = entry
    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), ensure_ascii=False, indent=2) + "\n")
    return entry


def read_raw(name: str) -> bytes:
    """Read a raw payload and check it against the manifest sha256 (the reproducibility contract)."""
    entry = load_manifest().get(name)
    if entry is None:
        raise LookupError(f"raw payload {name} not in manifest")
    payload = (RAW_DIR / name).read_bytes()
    if sha256_bytes(payload) != entry["sha256"]:
        raise ValueError(f"sha256 mismatch for {name}")
    return payload


# --------------------------------------------------------------------------------------------- fetch: BOE ELI tree


def _children(url: str, pattern: str) -> tuple[list[str], str]:
    body = http_get(url)
    found = sorted(set(re.findall(pattern, body.decode("utf-8", "replace"))))
    return found, sha256_bytes(body)


def crawl_eli(kind: str, years: list[int], workers: int = 8) -> tuple[list[dict], dict]:
    pages: dict[str, str] = {}

    def year_task(year: int) -> list[dict]:
        out = []
        url = f"{ELI_ROOT}/{kind}/{year}"
        months, digest = _children(url, rf"/eli/es/{kind}/{year}/(\d\d)(?=[\"'/])")
        pages[url] = digest
        for mm in months:
            murl = f"{url}/{mm}"
            days, digest = _children(murl, rf"/eli/es/{kind}/{year}/{mm}/(\d\d)(?=[\"'/])")
            pages[murl] = digest
            for dd in days:
                durl = f"{murl}/{dd}"
                nums, digest = _children(durl, rf"/eli/es/{kind}/{year}/{mm}/{dd}/(\d+)(?=[\"'/])")
                pages[durl] = digest
                for n in nums:
                    out.append({"type": kind, "date": f"{year}-{mm}-{dd}", "number": int(n),
                                "eli": f"{ELI_ROOT}/{kind}/{year}/{mm}/{dd}/{n}"})
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = [row for chunk in pool.map(year_task, years) for row in chunk]
    rows.sort(key=lambda r: (r["type"], r["date"], r["number"]))
    return rows, pages


def cmd_fetch_boe_eli(args: argparse.Namespace) -> int:
    years = list(range(args.first_year, args.last_year + 1))
    inventory: list[dict] = []
    pages: dict[str, str] = {}
    for kind in ELI_TYPES:
        rows, kind_pages = crawl_eli(kind, years, workers=args.workers)
        print(f"{kind}: {len(rows)} norms from {len(kind_pages)} listing pages", file=sys.stderr)
        inventory.extend(rows)
        pages.update(kind_pages)
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {"source": "BOE, European Legislation Identifier tree", "root": ELI_ROOT, "retrieved_at": retrieved,
               "years": [years[0], years[-1]], "norms": inventory,
               "listing_pages_sha256": dict(sorted(pages.items()))}
    raw = gzip.compress(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(), mtime=0)
    entry = save_raw("boe_eli_inventory.json.gz", raw, {
        "source_id": "boe_eli", "url": ELI_ROOT, "retrieved_at": retrieved,
        "note": "Inventory of /eli/es/{rdl,l,lo}/YYYY/MM/DD/N crawled from the BOE ELI listing pages; sha256 of each listing page inside."})
    print(json.dumps(entry, indent=2))
    return 0


# --------------------------------------------------------------------------------------------- fetch: other sources

BOE_API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
OWID_VDEM = {
    "libdem": "liberal-democracy-index",
    "jucon": "judicial-constraints-on-the-executive-index",
    "legcon": "legislative-constraints-on-the-executive-index",
}
PEER_CODES = ["ESP", "DEU", "FRA", "ITA", "PRT", "POL", "HUN"]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_fetch_boe_budgets(args: argparse.Namespace) -> int:
    query = {"query": {"query_string": {"query": "titulo:(Presupuestos Generales del Estado para) and rango@codigo:1300"}}}
    url = f"{BOE_API}?limit=-1&query={urllib.parse.quote(json.dumps(query))}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
    json.loads(body)  # must be JSON
    print(json.dumps(save_raw("boe_budget_laws.json", body, {
        "source_id": "boe_legislacion_consolidada", "url": url, "retrieved_at": now_utc(),
        "note": "BOE open-data API, consolidated legislation: laws whose title contains 'Presupuestos Generales del Estado para'."}), indent=2))
    return 0


def cmd_fetch_peers(args: argparse.Namespace) -> int:
    for key, slug in OWID_VDEM.items():
        url = f"https://ourworldindata.org/grapher/{slug}.csv?v=1&csvType=full&useColumnShortNames=true"
        body = http_get(url)
        rows = list(csv.reader(io.StringIO(body.decode("utf-8"))))
        if len(rows) < 1000:
            raise RuntimeError(f"{url}: unexpected size {len(rows)}")
        print(json.dumps(save_raw(f"owid_vdem_{key}.csv.gz", gzip.compress(body, mtime=0), {
            "source_id": "vdem_owid_mirror", "url": url, "retrieved_at": now_utc(),
            "official_page": "https://www.v-dem.net/data/the-v-dem-dataset/",
            "note": "V-Dem country-year index (central estimate) through the Our World in Data mirror: the official V-Dem download sits behind a web form."}), indent=2))
    return 0


def cmd_fetch_congreso_plazos(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = conn.execute(
        """
        SELECT legislature, expediente, type, title, author_text, presented_date, qualified_date, current_status,
               deadlines_text, source_url, source_snapshot_date
        FROM parl_initiatives
        WHERE legislature = '15' AND substr(expediente, 1, 3) IN ('121', '122', '123', '124', '125')
        ORDER BY expediente
        """
    ).fetchall()
    cols = ["legislature", "expediente", "type", "title", "author_text", "presented_date", "qualified_date",
            "current_status", "deadlines_text", "source_url", "source_snapshot_date"]
    data = [dict(zip(cols, r)) for r in rows]
    snapshot = max(r["source_snapshot_date"] for r in data)
    payload = {"source": "Congreso de los Diputados, datos abiertos de iniciativas (XV legislatura)",
               "snapshot_date": snapshot, "rows": data}
    raw = gzip.compress(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(), mtime=0)
    print(json.dumps(save_raw("congreso_xv_plazos.json.gz", raw, {
        "source_id": "congreso_iniciativas", "url": "https://www.congreso.es/es/opendata/iniciativas",
        "retrieved_at": snapshot, "note": "Bills of the XV legislature (121-125) with their deadline history, extracted from the project's Congress open-data ingest (parl_initiatives)."}), indent=2))
    return 0


# --------------------------------------------------------------------------------------------- build helpers


def load_seed() -> dict:
    return json.loads(SEED.read_text())


def government_at(day: str, governments: list[dict]) -> dict | None:
    for gov in governments:
        if gov["start"] <= day and (gov.get("end") is None or day < gov["end"]):
            return gov
    return None


def eli_inventory() -> dict:
    return json.loads(gzip.decompress(read_raw("boe_eli_inventory.json.gz")))


def legislature_of(day: str, legislatures: list[dict]) -> str | None:
    for leg in legislatures:
        if leg["start"] <= day and (leg.get("end") is None or day < leg["end"]):
            return leg["id"]
    return None


def decree_law_series(seed: dict) -> dict:
    inv = eli_inventory()
    by_year: dict[int, Counter] = defaultdict(Counter)
    max_num: dict[tuple[str, int], int] = defaultdict(int)
    for row in inv["norms"]:
        year = int(row["date"][:4])
        by_year[year][row["type"]] += 1
        max_num[(row["type"], year)] = max(max_num[(row["type"], year)], row["number"])
    years = sorted(y for y in by_year if y >= FIRST_YEAR)
    annual = []
    for y in years:
        c = by_year[y]
        laws = c["l"] + c["lo"]
        annual.append({
            "year": y, "rdl": c["rdl"], "l": c["l"], "lo": c["lo"], "laws": laws,
            "rdl_per_law": round(c["rdl"] / laws, 2) if laws else None,
            "rdl_share": round(100 * c["rdl"] / (c["rdl"] + laws), 1) if (c["rdl"] + laws) else None,
            "numbering_gap": {k: max_num[(k, y)] - c[k] for k in ELI_TYPES if max_num[(k, y)] != c[k]},
        })
    legs = seed["legislatures"]
    per_leg: dict[str, Counter] = defaultdict(Counter)
    for row in inv["norms"]:
        leg = legislature_of(row["date"], legs)
        if leg:
            per_leg[leg][row["type"]] += 1
    legislature_rows = []
    for leg in legs:
        c = per_leg.get(leg["id"], Counter())
        laws = c["l"] + c["lo"]
        start = date.fromisoformat(leg["start"])
        end = date.fromisoformat(leg["end"]) if leg.get("end") else date.fromisoformat(inv["retrieved_at"][:10])
        months = (end - start).days / 30.4375
        legislature_rows.append({
            "id": leg["id"], "label": leg["label"], "start": leg["start"], "end": leg.get("end"),
            "governments": leg["governments"], "rdl": c["rdl"], "laws": laws, "l": c["l"], "lo": c["lo"],
            "rdl_share": round(100 * c["rdl"] / (c["rdl"] + laws), 1) if (c["rdl"] + laws) else None,
            "rdl_per_month": round(c["rdl"] / months, 2) if months > 0 else None,
            "months": round(months, 1), "ongoing": leg.get("end") is None,
        })
    return {"annual": annual, "legislatures": legislature_rows, "retrieved_at": inv["retrieved_at"],
            "partial_year": int(inv["retrieved_at"][:4])}


def government_series(seed: dict) -> list[dict]:
    """Decree-laws and laws per government (president), with monthly rates so short and long terms compare."""
    inv = eli_inventory()
    govs = seed["governments"]
    counts: dict[str, Counter] = defaultdict(Counter)
    for row in inv["norms"]:
        if row["date"] < f"{FIRST_YEAR}-01-01":
            continue
        gov = government_at(row["date"], govs)
        if gov:
            counts[gov["id"]][row["type"]] += 1
    today = inv["retrieved_at"][:10]
    out = []
    for gov in govs:
        start = max(gov["start"], f"{FIRST_YEAR}-01-01")
        end = gov.get("end") or today
        months = (date.fromisoformat(end) - date.fromisoformat(start)).days / 30.4375
        c = counts[gov["id"]]
        laws = c["l"] + c["lo"]
        out.append({"id": gov["id"], "president": gov["president"], "party": gov["party"], "start": start,
                    "end": gov.get("end"), "months": round(months, 1), "rdl": c["rdl"], "laws": laws,
                    "rdl_per_month": round(c["rdl"] / months, 2), "laws_per_month": round(laws / months, 2),
                    "rdl_share": round(100 * c["rdl"] / (c["rdl"] + laws), 1) if (c["rdl"] + laws) else None})
    return out


BUDGET_TITLE = re.compile(r"Presupuestos Generales del Estado para (?:el año )?(\d{4})\.?$")


def budget_series(seed: dict, first: int = 1983) -> dict:
    data = json.loads(read_raw("boe_budget_laws.json"))["data"]
    laws = {}
    for row in data:
        m = BUDGET_TITLE.search(row["titulo"].strip())
        if not m or not row["titulo"].startswith("Ley "):
            continue
        year = int(m.group(1))
        pub = f"{row['fecha_publicacion'][:4]}-{row['fecha_publicacion'][4:6]}-{row['fecha_publicacion'][6:]}"
        laws[year] = {"law": row["titulo"].split(",")[0], "published": pub, "boe": row["identificador"],
                      "url": f"https://www.boe.es/buscar/act.php?id={row['identificador']}"}
    last = int(load_manifest()["boe_budget_laws.json"]["retrieved_at"][:4])
    rows = []
    for year in range(first, last + 1):
        law = laws.get(year)
        if law is None:
            status, days = "prorrogado", None
        elif law["published"] <= f"{year - 1}-12-31":
            status, days = "a_tiempo", 0
        else:
            status = "tarde"
            days = (date.fromisoformat(law["published"]) - date(year, 1, 1)).days
        gov = government_at(f"{year}-01-01", seed["governments"])
        rows.append({"year": year, "status": status, "days_prorrogued": days if status != "prorrogado" else 365,
                     "government_on_jan1": gov["id"] if gov else None, **({"law": law} if law else {})})
    return {"years": rows, "first": first, "last": last,
            "prorrogued_years": [r["year"] for r in rows if r["status"] == "prorrogado"],
            "late_years": [r["year"] for r in rows if r["status"] == "tarde"]}


DEADLINE = re.compile(r"Hasta: (\d\d)/(\d\d)/(\d{4}) \(\d\d:\d\d\) (.*?)(?= Hasta:|$)")
GOV_GROUPS = ("Socialista", "SUMAR")


def author_bucket(expediente: str, author: str) -> str:
    kind = expediente[:3]
    if kind == "121":
        return "gobierno"
    if kind == "124":
        return "senado"
    if kind == "125":
        return "ccaa"
    groups = re.findall(r"Grupo Parlamentario ([^G]+?)(?= Grupo Parlamentario|$)", author or "")
    names = {g.strip() for g in groups}
    if not names:
        return "otros"
    if any("Popular" in n for n in names):
        return "pp" if len(names) == 1 else "conjunta_con_pp"
    if names == {"VOX"}:
        return "vox"
    if all(any(k in n for k in GOV_GROUPS) for n in names):
        return "grupos_gobierno"
    return "otros_grupos"


def freezer_series() -> dict:
    payload = json.loads(gzip.decompress(read_raw("congreso_xv_plazos.json.gz")))
    snapshot = payload["snapshot_date"]
    bills = []
    for row in payload["rows"]:
        marks = [(f"{y}-{m}-{d}", label.strip()) for d, m, y, label in DEADLINE.findall(row["deadlines_text"] or "")]
        amend = [(day, label) for day, label in marks if "enmiendas" in label.lower() and "Pleno" not in label]
        if not amend:
            continue
        first = min(day for day, label in amend if not label.startswith("Ampliación")) if any(
            not label.startswith("Ampliación") for _, label in amend) else min(day for day, _ in amend)
        last = max(day for day, _ in amend)
        extensions = sum(1 for _, label in amend if label.startswith("Ampliación"))
        status = row["current_status"] or ""
        open_amend = status.endswith("Enmiendas")
        bills.append({"expediente": row["expediente"], "title": row["title"], "author": row["author_text"],
                      "bucket": author_bucket(row["expediente"], row["author_text"]), "status": status,
                      "extensions": extensions, "first_deadline": first, "last_deadline": last,
                      "days_in_amendments": (date.fromisoformat(min(last, snapshot) if open_amend else last) - date.fromisoformat(first)).days,
                      "still_in_amendments": open_amend})
    groups = defaultdict(list)
    for b in bills:
        groups[b["bucket"]].append(b)
    summary = []
    for bucket, items in sorted(groups.items()):
        ext = sorted(b["extensions"] for b in items)
        summary.append({"bucket": bucket, "bills": len(items), "median_extensions": ext[len(ext) // 2],
                        "max_extensions": ext[-1], "still_in_amendments": sum(b["still_in_amendments"] for b in items),
                        "with_10_or_more": sum(b["extensions"] >= 10 for b in items)})
    bills.sort(key=lambda b: -b["extensions"])
    return {"snapshot_date": snapshot, "legislature": "XV", "total_extensions": sum(b["extensions"] for b in bills),
            "bills_in_amendments": len(bills), "summary": summary, "bills": bills}


def vdem_series(first: int = 1975) -> dict:
    out: dict[str, dict] = {}
    latest = 0
    for key in OWID_VDEM:
        text = gzip.decompress(read_raw(f"owid_vdem_{key}.csv.gz")).decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        col = [c for c in reader.fieldnames if c.endswith("__estimate_best")][0]
        series: dict[str, list] = defaultdict(list)
        for row in reader:
            if row["code"] in PEER_CODES and int(row["year"]) >= first and row[col] != "":
                series[row["code"]].append({"year": int(row["year"]), "value": round(float(row[col]), 3)})
                latest = max(latest, int(row["year"]))
        out[key] = {code: sorted(series[code], key=lambda p: p["year"]) for code in PEER_CODES}
    return {"indices": out, "latest_year": latest, "countries": PEER_CODES}


BODY_SHORT = {"cgpj_renovacion": "CGPJ", "tc_renovacion": "Tribunal Constitucional", "defensor_pueblo": "Defensor del Pueblo",
              "tribunal_cuentas": "Tribunal de Cuentas", "rtve_consejo": "Consejo de RTVE"}


def mandate_series(safeguards: list[dict], snapshot: str) -> list[dict]:
    rows = []
    for sg in safeguards:
        for term in sg.get("mandate_terms") or []:
            took = term.get("successor_took_office")
            end_ref = took or snapshot
            expired = max(0, (date.fromisoformat(end_ref) - date.fromisoformat(term["mandate_end"])).days)
            rows.append({"safeguard": sg["id"], "body": BODY_SHORT.get(sg["id"], sg["name"]) + (f" ({term['body']})" if term.get("body") else ""), "term": term.get("term"),
                         "mandate_start": term["mandate_start"], "mandate_end": term["mandate_end"],
                         "successor_took_office": took, "days_expired": expired, "ongoing": took is None,
                         "sources": term.get("sources", [])})
    return rows


def tc_delay_series(safeguards: list[dict]) -> list[dict]:
    rows = []
    for sg in safeguards:
        for ep in sg.get("episodes", []):
            rem = ep.get("remedy")
            if rem and rem.get("act_date") and rem.get("date"):
                rows.append({"safeguard": sg["id"], "episode": ep["id"], "by": rem["by"], "ruling": rem.get("ruling"),
                             "act_date": rem["act_date"], "ruling_date": rem["date"],
                             "days": (date.fromisoformat(rem["date"]) - date.fromisoformat(rem["act_date"])).days,
                             "government": (ep.get("power_holder") or {}).get("government")})
    return sorted(rows, key=lambda r: r["act_date"])


def load_safeguards(seed: dict) -> list[dict]:
    docs = [json.loads(p.read_text()) for p in sorted(SAFEGUARD_DIR.glob("*.json"))]
    order = {sid: i for i, sid in enumerate(seed.get("order", []))}
    docs.sort(key=lambda d: (order.get(d["id"], 999), d["id"]))
    for d in docs:
        d.pop("_hints", None)
    return docs


def load_context() -> dict:
    path = SEED_DIR / "context.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text())
    doc.pop("_hints", None)
    return doc


SENATE_MAX = 266  # upper bound of the Senate size (208 elected + at most 58 designated): elected seats above 2/5 of it block for sure
MAJORITY_SHARE = {"3/5": 3 / 5, "2/3": 2 / 3}


def load_seats() -> dict:
    path = SEED_DIR / "seats.json"
    return json.loads(path.read_text()) if path.exists() else {"elections": []}


def legislatures_between(start: str, end: str | None, legislatures: list[dict], snapshot: str) -> list[dict]:
    end = end or snapshot
    return [leg for leg in legislatures if leg["start"] <= end and (leg.get("end") is None or leg["end"] > start)]


def qualified_arithmetic(rule: str, chambers: list[str], legs: list[dict], seats: dict) -> list[dict]:
    """For each legislature: who could block a qualified majority alone, and which pairs of the largest could together.

    Congress: exact seats (JEC). Senate: elected seats only; a family is reported as blocking only when its elected
    seats alone exceed (1 - share) of the largest possible Senate, otherwise the Senate is 'no determinado'."""
    share = MAJORITY_SHARE[rule]
    by_leg = {e["legislature"]: e for e in seats.get("elections", [])}
    out = []
    for leg in legs:
        el = by_leg.get(leg["id"])
        if not el:
            out.append({"legislature": leg["id"], "status": "sin_tabla"})
            continue
        row = {"legislature": leg["id"], "election": el["election"], "boe_ref": el["boe_ref"], "url": el["url"],
               "status": el.get("status", "completa"), "rule": rule}
        congress = {k: v for k, v in (el.get("congress") or {}).items() if v}
        senate = {k: v for k, v in (el.get("senate_elected") or {}).items() if v}
        if "Congreso" in chambers:
            if sum(congress.values()) != 350:
                row["congress"] = None
            else:
                needed = int(-(-350 * share // 1))  # ceil
                alone = sorted([k for k, v in congress.items() if v > 350 - needed], key=lambda k: -congress[k])
                top = sorted(congress, key=lambda k: -congress[k])[:5]
                pairs = [[a, b] for i, a in enumerate(top) for b in top[i + 1:]
                         if a not in alone and b not in alone and congress[a] + congress[b] > 350 - needed]
                row["congress"] = {"needed": needed, "seats": dict(sorted(congress.items(), key=lambda kv: -kv[1])),
                                   "block_alone": alone, "block_pairs": pairs}
        if "Senado" in chambers:
            if sum(senate.values()) != 208:
                row["senate"] = None
            else:
                threshold = SENATE_MAX * (1 - share)
                alone = sorted([k for k, v in senate.items() if v > threshold and k != "Sin atribuir"], key=lambda k: -senate[k])
                row["senate"] = {"elected": dict(sorted(senate.items(), key=lambda kv: -kv[1])), "block_alone_certain": alone,
                                 "determined": bool(alone), "threshold_elected": round(threshold, 1)}
        if all(row.get(k) is None for k in ("congress", "senate")):
            row["status"] = "sin_tabla"
        out.append(row)
    return out


def attach_arithmetic(safeguards: list[dict], seed: dict) -> None:
    seats = load_seats()
    for sg in safeguards:
        for ep in sg.get("episodes", []):
            maj = (ep.get("power_holder") or {}).get("majority")
            if maj:
                legs = legislatures_between(ep["start"], ep.get("end"), seed["legislatures"], seed["snapshot_date"])
                ep["arithmetic"] = qualified_arithmetic(maj["rule"], maj.get("chambers", ["Congreso", "Senado"]), legs, seats)


REPRODUCIBLE_KEYS = ("decree_laws", "budgets", "freezer", "vdem", "mandates", "tc_delays")


def build_payload(seed: dict) -> dict:
    all_docs = load_safeguards(seed)
    verified = seed.get("reviews", {}).get("verified", {})
    safeguards = [d for d in all_docs if d["id"] in verified]
    undocumented = set(seed.get("reviews", {}).get("pending_documentation", {}).get("ids", []))
    pending = [{"id": d["id"], "name": d["name"], "group": d["group"],
                "status": "pendiente_documentar" if d["id"] in undocumented else "en_revision",
                "rule": {k: d["rule"].get(k) for k in ("text", "articles", "url")} if d["id"] in undocumented else None}
               for d in all_docs if d["id"] not in verified]
    attach_arithmetic(safeguards, seed)
    manifest = load_manifest()
    dl = decree_law_series(seed)
    dl["governments"] = government_series(seed)
    return {
        "generated_from": {"seed": str(SEED.relative_to(REPO_ROOT)), "raw": {k: {"sha256": v["sha256"], "url": v["url"], "retrieved_at": v["retrieved_at"], **({"official_page": v["official_page"]} if v.get("official_page") else {})} for k, v in manifest.items()}},
        "snapshot_date": seed["snapshot_date"],
        "classes": seed["classes"],
        "episode_kinds": seed["episode_kinds"],
        "governments": seed["governments"],
        "legislatures": seed["legislatures"],
        "safeguards": safeguards,
        "pending": pending,
        "review_rule": seed.get("reviews", {}).get("rule"),
        "review_sample_size": len(seed.get("reviews", {}).get("sample10", {}).get("ids", [])),
        "decree_laws": dl,
        "budgets": budget_series(seed),
        "freezer": freezer_series(),
        "vdem": vdem_series(),
        "mandates": mandate_series(safeguards, seed["snapshot_date"]),
        "tc_delays": tc_delay_series(safeguards),
        "context": load_context(),
    }


def write_csv(payload: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["series", "key", "subkey", "value", "unit", "source"])
    for row in payload["decree_laws"]["annual"]:
        for k in ("rdl", "l", "lo"):
            w.writerow(["normas_por_año", row["year"], k, row[k], "normas", "BOE ELI"])
    for row in payload["decree_laws"]["governments"]:
        w.writerow(["decretos_ley_por_mes_de_gobierno", row["president"], row["party"], row["rdl_per_month"], "decretos-ley/mes", "BOE ELI"])
    for row in payload["budgets"]["years"]:
        w.writerow(["presupuestos", row["year"], row["status"], row["days_prorrogued"], "días de prórroga", "BOE"])
    for row in payload["mandates"]:
        w.writerow(["mandato_caducado", row["body"], row["term"], row["days_expired"], "días", "BOE"])
    for row in payload["tc_delays"]:
        w.writerow(["retraso_remedio", row["ruling"], row["safeguard"], row["days"], "días", row["by"]])
    for b in payload["freezer"]["bills"]:
        w.writerow(["ampliaciones_enmiendas_xv", b["expediente"], b["bucket"], b["extensions"], "ampliaciones", "Congreso"])
    for key, by_code in payload["vdem"]["indices"].items():
        for code, points in by_code.items():
            for p in points:
                w.writerow([f"vdem_{key}", code, p["year"], p["value"], "índice 0-1", "V-Dem vía OWID"])
    for sg in payload["safeguards"]:
        w.writerow(["salvaguarda", sg["id"], sg["classification"], len(sg["episodes"]), "episodios", sg["rule"]["url"]])
    return buf.getvalue()


SERIES_OUT = SEED_DIR / "decree_laws_series.json"


def cmd_series(args: argparse.Namespace) -> int:
    """Write the decree-law series alone (read by the sibling /democracia/partidos/ ledger)."""
    seed = load_seed()
    dl = decree_law_series(seed)
    dl["governments"] = government_series(seed)
    dl["source"] = {"raw": "raw/boe_eli_inventory.json.gz", "sha256": load_manifest()["boe_eli_inventory.json.gz"]["sha256"],
                    "url": ELI_ROOT, "method": "Count of /eli/es/{rdl,l,lo}/YYYY/MM/DD/N per year; numbering_gap lists years where the count differs from the highest official number (none expected)."}
    SERIES_OUT.write_text(json.dumps(dl, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {SERIES_OUT.relative_to(REPO_ROOT)}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    payload = build_payload(load_seed())
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    OUT_CSV.write_text(write_csv(payload))
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)} ({OUT_JSON.stat().st_size // 1024} KB), {len(payload['safeguards'])} safeguards")
    return 0


# --------------------------------------------------------------------------------------------- kit (for drafting agents)

KIT_CACHE = Path("/tmp/vclc-democracy-cache")
PEER_LINKS = {
    "DEU": [("Grundgesetz, un articulo por pagina (art_63, art_81, art_111, art_115a...)", "https://www.gesetze-im-internet.de/gg/art_63.html"),
            ("BVerfGG (§4 mandato, §7a eleccion supletoria de jueces)", "https://www.gesetze-im-internet.de/bverfgg/__7a.html")],
    "FRA": [("Constitution de 1958 en Legifrance (403 a curl: leer con WebFetch, citar igual)", "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000571356")],
    "ITA": [("Costituzione, PDF de la Corte costituzionale (kit grep funciona)", "https://www.cortecostituzionale.it/documenti/pubblicazioni/testo-Costituzione.pdf")],
    "PRT": [("Constituicao, Assembleia da Republica", "https://www.parlamento.pt/Legislacao/Paginas/ConstituicaoRepublicaPortuguesa.aspx"),
            ("Constituicao consolidada, Diario da Republica (alternativa)", "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-aprovacao-constituicao/1976-34520775")],
    "EU": [("Informes sobre el Estado de Derecho (429 a scripts a veces: reintentar o WebFetch)", "https://commission.europa.eu/strategy-and-policy/policies/justice-and-fundamental-rights/upholding-rule-law/rule-law/rule-law-mechanism_en"),
           ("Comision de Venecia (502 intermitente)", "https://www.venice.coe.int/webforms/documents/by_country.aspx")],
}
KNOWN_BLOCKED = ["congreso.es (403 a scripts: usar BOE / BOCG en boe.es o el PDF del Diario de Sesiones)",
                 "lamoncloa.gob.es (TLS)", "legifrance.gouv.fr (403)", "conseil-constitutionnel.fr (403)",
                 "venice.coe.int (502 intermitente: reintentar o citar la pagina de la opinion)"]


def _cached_get(url: str) -> bytes:
    KIT_CACHE.mkdir(parents=True, exist_ok=True)
    path = KIT_CACHE / sha256_bytes(url.encode())
    if path.exists():
        return path.read_bytes()
    body = http_get(url, tries=2)
    path.write_bytes(body)
    return body


def _text_of(body: bytes, url: str) -> str:
    if body[:5] == b"%PDF-":
        tmp = KIT_CACHE / (sha256_bytes(url.encode()) + ".pdf")
        tmp.write_bytes(body)
        import subprocess
        return subprocess.run(["pdftotext", "-layout", str(tmp), "-"], capture_output=True, text=True).stdout
    import html as htmlmod
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", text)))


def kit_boe_search(args: argparse.Namespace) -> int:
    """Search BOE titles (all sections, incl. TC rulings in section T). Prints ref, date, title (<=300 chars)."""
    import html as htmlmod
    params = {"campo[1]": "TITULOS", "dato[1]": args.text, "operador[1]": "and", "accion": "Buscar", "page_hits": str(args.limit)}
    if args.section:
        params.update({"campo[0]": "ORIS", f"dato[0][{args.section}]": args.section, "operador[0]": "and"})
    if args.year_from or args.year_to:
        params.update({"campo[6]": "FPU", "dato[6][0]": f"{args.year_from or 1978}-01-01", "dato[6][1]": f"{args.year_to or 2026}-12-31", "operador[6]": "and"})
    url = "https://www.boe.es/buscar/boe.php?" + urllib.parse.urlencode(params)
    body = _cached_get(url).decode("utf-8", "replace")
    items = re.findall(r'<li class="resultado-busqueda">(.*?)</ul>', body, re.S)
    if not items:
        print("sin resultados")
    for it in items[: args.limit]:
        ref = re.search(r"id=(BOE-[A-Z]-\d+-\d+)", it)
        pub = re.search(r'linea-pub">\s*BOE (\d+) de (\d\d/\d\d/\d{4})', it)
        title = re.findall(r"<p>(.*?)</p>", it, re.S)
        title = re.sub(r"\s+", " ", htmlmod.unescape(re.sub("<[^>]+>", "", title[-1]))).strip() if title else ""
        print(f"{ref.group(1) if ref else '?'} | BOE {pub.group(2) if pub else '?'} | https://www.boe.es/buscar/doc.php?id={ref.group(1) if ref else ''} | {title[:args.chars]}")
    return 0


def kit_boe_doc(args: argparse.Namespace) -> int:
    """Title, publication date and (optionally) a grep of the text of BOE documents by reference."""
    for ref in args.refs:
        url = f"https://www.boe.es/buscar/doc.php?id={ref}"
        import html as htmlmod
        body = htmlmod.unescape(_cached_get(url).decode("utf-8", "replace"))
        m = re.search(r'<h3 class="documento-tit">(.*?)</h3>', body, re.S)
        pub = re.search(r"BOE\W+n[uú]m\.\s+\d+, de ([^,]+?),", re.sub(r"<[^>]+>", " ", body))
        title = re.sub(r"\s+", " ", re.sub("<[^>]+>", "", m.group(1))).strip() if m else "?"
        print(f"{ref} | {pub.group(1) if pub else '?'} | {title[:300]}")
        if args.grep:
            text = _text_of(body.encode(), url)
            text = text[text.find(title[:40]) + len(title):] if title[:40] in text else text
            for hit in list(re.finditer(args.grep, text, re.I))[: args.max]:
                print("   …" + text[max(0, hit.start() - args.context): hit.end() + args.context] + "…")
    return 0


def boe_articles(ref: str, anchors: list[str], limit: int = 2500) -> dict[str, str]:
    """Consolidated text of articles of a BOE norm (act.php), by block anchor (CE: a159; LOTC: adieciseis...)."""
    import html as htmlmod
    body = _cached_get(f"https://www.boe.es/buscar/act.php?id={ref}").decode("utf-8", "replace")
    out = {}
    for anchor in anchors:
        i = body.find(f'<div class="bloque" id="{anchor}"')
        if i < 0:
            out[anchor] = "(no encontrado)"
            continue
        j = body.find('<div class="bloque"', i + 10)
        text = re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", body[i:j if j > 0 else i + 20000]))).strip()
        text = re.sub(r"^\[Bloque \d+: #\w+\]\s*", "", text)
        text = re.sub(r"\s(Téngase en cuenta|Se modifica por|Redactado conforme|Ver Sentencia|Ver texto consolidado|Ir a la versión).*$", "", text)
        out[anchor] = text[:limit]
    return out


def kit_boe_articles(args: argparse.Namespace) -> int:
    for anchor, text in boe_articles(args.ref, args.anchors).items():
        print(f"[{anchor}] {text}")
    return 0


def kit_grep(args: argparse.Namespace) -> int:
    """Fetch a page or PDF (cached), strip tags, print bounded context around each regex hit."""
    try:
        text = _text_of(_cached_get(args.url), args.url)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {exc}")
        return 1
    hits = list(re.finditer(args.pattern, text, re.I))
    print(f"{len(text)} chars, {len(hits)} hits")
    for hit in hits[: args.max]:
        print("…" + text[max(0, hit.start() - args.context): hit.end() + args.context].replace("\n", " ") + "…")
    return 0


def kit_peers(args: argparse.Namespace) -> int:
    for code, links in PEER_LINKS.items():
        for label, url in links:
            print(f"{code} | {label} | {url}")
    print("Bloqueados conocidos: " + "; ".join(KNOWN_BLOCKED))
    return 0


def kit_govs(args: argparse.Namespace) -> int:
    seed = load_seed()
    for g in seed["governments"]:
        print(f"{g['id']:13} {g['president']:30} {g['party']:5} {g['start']} -> {g['end'] or 'hoy'}")
    for leg in seed["legislatures"]:
        print(f"leg {leg['id']:5} {leg['start']} -> {leg['end'] or 'hoy'} gobiernos: {','.join(leg['governments'])}")
    print("Cortes disueltas el 2026-10-05 (RD 806/2026), elecciones el 2026-11-29: desde entonces Gobierno de Sanchez con Cortes disueltas.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch-boe-eli")
    p.add_argument("--first-year", type=int, default=FIRST_YEAR)
    p.add_argument("--last-year", type=int, default=date.today().year)
    p.add_argument("--workers", type=int, default=8)
    p.set_defaults(func=cmd_fetch_boe_eli)
    sub.add_parser("fetch-boe-budgets").set_defaults(func=cmd_fetch_boe_budgets)
    sub.add_parser("fetch-peers").set_defaults(func=cmd_fetch_peers)
    sub.add_parser("build").set_defaults(func=cmd_build)
    sub.add_parser("series").set_defaults(func=cmd_series)
    kit = sub.add_parser("kit", help="helpers for drafting agents").add_subparsers(dest="kit", required=True)
    k = kit.add_parser("boe-search", help='e.g. kit boe-search "Sentencia 68/2007"  |  kit boe-search "decreto-ley extraordinaria y urgente necesidad nulidad" --year-from 2015')
    k.add_argument("text")
    k.add_argument("--year-from", type=int)
    k.add_argument("--year-to", type=int)
    k.add_argument("--section", choices=["1", "2", "3", "4", "5", "T"], help="T = Tribunal Constitucional, 1 = disposiciones generales, 2 = autoridades y personal (nombramientos), 3 = otras disposiciones")
    k.add_argument("--limit", type=int, default=15)
    k.add_argument("--chars", type=int, default=300)
    k.set_defaults(func=kit_boe_search)
    k = kit.add_parser("boe-doc", help='e.g. kit boe-doc BOE-A-2026-20742 BOE-T-2007-8660 --grep "fallo|declarar"')
    k.add_argument("refs", nargs="+")
    k.add_argument("--grep")
    k.add_argument("--context", type=int, default=160)
    k.add_argument("--max", type=int, default=3)
    k.set_defaults(func=kit_boe_doc)
    k = kit.add_parser("grep", help='e.g. kit grep https://www.gesetze-im-internet.de/gg/art_63.html "Bundestag"')
    k.add_argument("url")
    k.add_argument("pattern")
    k.add_argument("--context", type=int, default=200)
    k.add_argument("--max", type=int, default=5)
    k.set_defaults(func=kit_grep)
    k = kit.add_parser("boe-articles", help="e.g. kit boe-articles BOE-A-1978-31229 a159 a122  |  LOTC: kit boe-articles BOE-A-1979-23709 adieciseis")
    k.add_argument("ref")
    k.add_argument("anchors", nargs="+")
    k.set_defaults(func=kit_boe_articles)
    kit.add_parser("peers", help="pre-checked official links for DE/FR/IT/PT/EU and known blocked hosts").set_defaults(func=kit_peers)
    kit.add_parser("govs", help="governments and legislatures with dates").set_defaults(func=kit_govs)
    p = sub.add_parser("fetch-congreso-plazos")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.set_defaults(func=cmd_fetch_congreso_plazos)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
