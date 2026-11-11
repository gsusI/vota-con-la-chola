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


def mandate_series(safeguards: list[dict], snapshot: str) -> list[dict]:
    rows = []
    for sg in safeguards:
        for term in sg.get("mandate_terms") or []:
            took = term.get("successor_took_office")
            end_ref = took or snapshot
            expired = max(0, (date.fromisoformat(end_ref) - date.fromisoformat(term["mandate_end"])).days)
            rows.append({"safeguard": sg["id"], "body": term.get("body") or sg["name"], "term": term.get("term"),
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


REPRODUCIBLE_KEYS = ("decree_laws", "budgets", "freezer", "vdem", "mandates", "tc_delays")


def build_payload(seed: dict) -> dict:
    safeguards = load_safeguards(seed)
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
        "decree_laws": dl,
        "budgets": budget_series(seed),
        "freezer": freezer_series(),
        "vdem": vdem_series(),
        "mandates": mandate_series(safeguards, seed["snapshot_date"]),
        "tc_delays": tc_delay_series(safeguards),
        "context": seed.get("context", {}),
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
    p = sub.add_parser("fetch-congreso-plazos")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.set_defaults(func=cmd_fetch_congreso_plazos)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
