#!/usr/bin/env python3
"""Export /visualizaciones/carga-fiscal/ data from the public-finance DB (scripts/ingest_public_finance_es.py).

Reads only normalized tables: the latest release of each indicator (indicator_* contract), statutory rates (same
contract, interval_kind='legal_validity') and BOE complexity (legal_norms, legal_norm_lineage_edges,
legal_norm_text_metrics). Writes the page JSON (with per-source provenance: URL, retrieval date, sha256) and a long CSV.
When the DB is missing (CI checkouts) the committed artifact is kept.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "etl/data/staging/public-finance-es.db"
OUT_JSON = REPO_ROOT / "ui/site/public/visualizaciones/data/carga-fiscal.json"
OUT_CSV = REPO_ROOT / "ui/site/public/visualizaciones/data/carga-fiscal.csv"

FIRST_YEAR = 1925
OECD_AREAS = ["ESP", "OECD_REP", "DEU", "FRA", "ITA", "PRT"]
COMPOSITION = {
    "T_1100": "IRPF y otros impuestos sobre la renta de personas",
    "T_1200": "Impuesto sobre Sociedades",
    "T_2100": "Cotizaciones sociales a cargo del trabajador",
    "T_2200": "Cotizaciones sociales a cargo de la empresa",
    "T_2300": "Cotizaciones de autónomos y no empleados",
    "T_4000": "Impuestos sobre la propiedad",
    "T_5000": "Impuestos sobre bienes y servicios (IVA, especiales…)",
}
SOURCE_PAGES = {
    "imf_fpp": ("FMI · Public Finances in Modern History (Mauro, Romeu, Binder y Zaman, 2015)", "https://www.imf.org/external/datamapper/datasets/FPP"),
    "oecd_revenue_statistics": ("OCDE · Revenue Statistics, tablas comparativas (réplica DBnomics)", "https://db.nomics.world/OECD/DSD_REV_COMP_OECD@DF_RSOECD"),
    "eurostat_sdmx": ("Eurostat · gov_10a_taxag (agregados fiscales de contabilidad nacional)", "https://ec.europa.eu/eurostat/databrowser/view/gov_10a_taxag/default/table"),
    "worldbank_wdi": ("Banco Mundial · población (SP.POP.TOTL) e IPC (FP.CPI.TOTL)", "https://data.worldbank.org/indicator/FP.CPI.TOTL?locations=ES"),
    "vclc_tax_law_rates": ("Tipos legales: una norma o fuente citada por cambio", "https://www.boe.es/"),
    "boe_api_legal": ("BOE · API de legislación consolidada", "https://www.boe.es/datosabiertos/api/api.php"),
}


def r(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.provenance: dict[str, list[dict]] = defaultdict(list)

    def series(self, source_id: str, indicator_code: str, unit_code: str) -> dict[str, list[dict]]:
        """Latest release of an indicator as {geography_code: [observation]}; deleted rows are dropped."""
        row = self.conn.execute(
            """
            SELECT r.indicator_release_id, r.source_url, r.source_content_sha256, r.source_snapshot_date,
                   r.source_metadata_json
            FROM indicator_definitions d JOIN indicator_releases r USING (indicator_id)
            WHERE d.source_id = ? AND d.indicator_code = ? AND d.unit_code = ?
            ORDER BY r.source_snapshot_date DESC, r.created_at DESC LIMIT 1
            """,
            (source_id, indicator_code, unit_code),
        ).fetchone()
        if row is None:
            raise LookupError(f"indicator {source_id}:{indicator_code}:{unit_code} not loaded")
        release_id, url, sha, snapshot, meta = row
        self.provenance[source_id].append({
            "indicator": f"{indicator_code} ({unit_code})", "url": url, "sha256": sha,
            "snapshot_date": snapshot, "retrieved_at": json.loads(meta or "{}").get("retrieved_at"),
        })
        out: dict[str, list[dict]] = defaultdict(list)
        for geo, period, value in self.conn.execute(
            """
            SELECT s.geography_code, o.period_label, o.value_decimal
            FROM indicator_observation_versions o JOIN indicator_series_versions s USING (indicator_series_version_id)
            WHERE o.indicator_release_id = ? AND o.revision_state != 'deleted' AND o.value_decimal IS NOT NULL
            ORDER BY s.geography_code, o.period_start
            """,
            (release_id,),
        ):
            out[geo].append({"period": period, "value": float(value)})
        return out

    def annual(self, source_id: str, indicator_code: str, unit_code: str, geo: str) -> dict[int, float]:
        return {int(p["period"]): p["value"] for p in self.series(source_id, indicator_code, unit_code).get(geo, [])}


def points(mapping: dict[int, float], digits: int = 2, since: int | None = None) -> list[dict]:
    return [{"year": y, "value": r(v, digits)} for y, v in sorted(mapping.items()) if since is None or y >= since]


def statutory_rates(conn: sqlite3.Connection) -> dict | None:
    rows = conn.execute(
        """
        SELECT d.indicator_code, o.period_start, o.value_decimal, o.raw_value_json, e.source_url
        FROM indicator_definitions d
        JOIN indicator_releases r ON r.indicator_id = d.indicator_id
        JOIN indicator_observation_versions o ON o.indicator_release_id = r.indicator_release_id
        JOIN indicator_observation_evidence e USING (indicator_observation_version_id)
        WHERE d.source_id = 'vclc_tax_law_rates' AND o.revision_state != 'deleted'
          AND r.indicator_release_id = (
            SELECT r2.indicator_release_id FROM indicator_releases r2 WHERE r2.indicator_id = d.indicator_id
            ORDER BY r2.source_snapshot_date DESC, r2.created_at DESC LIMIT 1)
        ORDER BY d.indicator_code, o.period_start
        """
    ).fetchall()
    if not rows:
        return None
    series: dict[str, list[dict]] = defaultdict(list)
    for code, start, value, raw, url in rows:
        cited = json.loads(raw)
        series[code].append({
            "from_year": int(start[:4]), "value_pct": float(value), "label": cited.get("label"),
            "source": cited.get("source"), "source_url": url, "locator": cited.get("locator"),
            "confidence": cited.get("confidence"), "note": cited.get("note"),
        })
    return {"series": dict(series)}


def complexity(conn: sqlite3.Connection) -> dict | None:
    laws = conn.execute(
        """
        SELECT n.norm_id, n.boe_id, n.title, n.effective_date, n.topic_hint
        FROM legal_norms n
        WHERE EXISTS (SELECT 1 FROM legal_norm_lineage_edges e WHERE e.related_norm_id = n.norm_id)
        ORDER BY n.boe_id
        """
    ).fetchall()
    if not laws:
        return None
    amendments = []
    for norm_id, boe_id, title, enacted, topic in laws:
        by_year: dict[str, int] = defaultdict(int)
        # One amending norm counts once per law, in the year it was published.
        for (year,) in conn.execute(
            """
            SELECT substr(MIN(evidence_date), 1, 4) FROM legal_norm_lineage_edges
            WHERE related_norm_id = ? GROUP BY norm_id
            """,
            (norm_id,),
        ):
            by_year[year] += 1
        amendments.append({
            "law": title, "boe_id": boe_id, "topic": topic, "enacted": enacted,
            "url": f"https://www.boe.es/buscar/act.php?id={boe_id}",
            "by_year": dict(sorted(by_year.items())), "total": sum(by_year.values()),
        })
    lengths, structure = [], []
    for boe_id, title, topic, kind, version_date, words, words_ex, arts, adic, trans, finals in conn.execute(
        """
        SELECT n.boe_id, n.title, n.topic_hint, m.version_kind, m.version_date, m.words, m.words_excl_preamble,
               m.articles, m.disp_adicionales, m.disp_transitorias, m.disp_finales
        FROM legal_norm_text_metrics m JOIN legal_norms n USING (norm_id)
        ORDER BY n.topic_hint, m.version_date
        """
    ):
        short = title.split(",")[0]
        lengths.append({
            "tax": (topic or "").removeprefix("tributario:"), "law": short, "boe_id": boe_id,
            "year": int(version_date[:4]),
            "version": "original" if kind == "original" else f"consolidated-{version_date}",
            "words": words, "words_excl_preamble": words_ex, "articles": arts,
        })
        if kind == "consolidated":
            structure.append({
                "law": short, "boe_id": boe_id, "url": f"https://www.boe.es/buscar/act.php?id={boe_id}",
                "words_excl_preamble": words_ex,
                "counts": {"articulos": arts, "disp_adicionales": adic, "disp_transitorias": trans, "disp_finales": finals},
            })
    return {"amendments": amendments, "law_length": lengths, "structure": structure}


def build(conn: sqlite3.Connection) -> dict:
    store = Store(conn)
    imf = store.annual("imf_fpp", "rev", "PT_GDP", "ESP")
    oecd = {code: store.series("oecd_revenue_statistics", f"TAX_REV.S13.{code}", "PT_B1GQ") for code in ["_T", *COMPOSITION]}
    oecd_eur = store.annual("oecd_revenue_statistics", "TAX_REV.S13._T", "XDC", "ESP")
    eurostat = store.series("eurostat_sdmx", "D2_D5_D91_D61_M_D995.S13_S212", "PC_GDP")
    pop = store.annual("worldbank_wdi", "SP.POP.TOTL", "PERSONS", "ESP")
    cpi = store.annual("worldbank_wdi", "FP.CPI.TOTL", "IDX2010", "ESP")

    def annual(code: str, area: str) -> dict[int, float]:
        return {int(p["period"]): p["value"] for p in oecd[code].get(area, [])}

    esp = {code: annual(code, "ESP") for code in oecd}
    years = sorted(esp["_T"])
    last_year = years[-1]
    # Revenue per person in constant euros of the last CPI year available within the revenue series.
    base_year = max(y for y in cpi if y <= last_year)
    per_capita = [
        {"year": y, "value": r(oecd_eur[y] * 1e9 / pop[y] * cpi[base_year] / cpi[y], 0)}
        for y in years if y in oecd_eur and y in pop and y in cpi
    ]
    by_payer = [
        {
            "year": y,
            "households": r(sum(esp[c].get(y, 0.0) for c in ("T_1100", "T_2100", "T_2300"))),
            "companies": r(sum(esp[c].get(y, 0.0) for c in ("T_1200", "T_2200"))),
            "consumption": r(esp["T_5000"].get(y)),
            "property": r(esp["T_4000"].get(y)),
        }
        for y in years
    ]
    eu = {geo: {int(p["period"]): p["value"] for p in rows} for geo, rows in eurostat.items()}

    # Consolidated figure: who pays, per country, in the latest year every area reports every category,
    # against each country's 1965 total.
    by_area = {area: {code: annual(code, area) for code in oecd} for area in OECD_AREAS}
    comp_year = max(set.intersection(*(set(series) for area in by_area.values() for series in area.values())))
    first_year = years[0]
    peers_composition = []
    for area, cat in by_area.items():
        total = cat["_T"][comp_year]
        parts = {
            "households": sum(cat[c][comp_year] for c in ("T_1100", "T_2100", "T_2300")),
            "companies": sum(cat[c][comp_year] for c in ("T_1200", "T_2200")),
            "consumption": cat["T_5000"][comp_year],
            "property": cat["T_4000"][comp_year],
        }
        parts["other"] = max(0.0, total - sum(parts.values()))
        peers_composition.append({
            "area": area, "total": r(total), "base_total": r(cat["_T"].get(first_year)),
            **{k: r(v) for k, v in parts.items()},
        })
    rates = statutory_rates(conn)
    comp = complexity(conn)

    sources = {}
    for source_id, releases in store.provenance.items():
        label, page = SOURCE_PAGES[source_id]
        retrieved = max((rel["retrieved_at"] or "" for rel in releases), default="") or None
        sources[source_id] = {"label": label, "page": page, "retrieved_at": retrieved, "releases": releases}
    for key, present in (("vclc_tax_law_rates", rates), ("boe_api_legal", comp)):
        if present:
            label, page = SOURCE_PAGES[key]
            sources[key] = {"label": label, "page": page, "retrieved_at": None, "releases": []}

    first_oecd = esp["_T"][years[0]]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "storage": "SQLite public-finance-es.db: indicator_* contract (releases, revisions, evidence per value), "
        "legal_norms, legal_norm_lineage_edges, legal_norm_text_metrics; built by scripts/ingest_public_finance_es.py",
        "headline": {
            "first_year": FIRST_YEAR,
            "first_value_imf": r(imf[FIRST_YEAR]),
            "oecd_first_year": years[0],
            "oecd_first_value": r(first_oecd),
            "last_year": last_year,
            "last_value": r(esp["_T"][last_year]),
            "multiple_oecd": r(esp["_T"][last_year] / first_oecd),
            "per_capita_first": per_capita[0],
            "per_capita_last": per_capita[-1],
            "per_capita_base_year": base_year,
        },
        "long_run": {
            "imf_revenue_pct_gdp": points(imf, since=FIRST_YEAR),
            "oecd_tax_pct_gdp": points(esp["_T"]),
        },
        "per_capita_real_eur": per_capita,
        "composition_pct_gdp": {code: points(esp[code]) for code in COMPOSITION},
        "composition_labels": COMPOSITION,
        "by_payer_pct_gdp": by_payer,
        "peers_pct_gdp": {area: points(annual("_T", area)) for area in OECD_AREAS},
        "peers_composition": {"year": comp_year, "base_year": first_year, "areas": peers_composition},
        "eu27_pct_gdp": [
            {"year": y, "es": r(eu.get("ES", {}).get(y)), "eu27": r(v)} for y, v in sorted(eu.get("EU27_2020", {}).items())
        ],
        "statutory_rates": rates,
        "complexity": comp,
        "sources": sources,
    }


def write_csv(data: dict, path: Path) -> None:
    rows: list[tuple] = []
    for row in data["long_run"]["imf_revenue_pct_gdp"]:
        rows.append(("imf_fpp", "ingresos_publicos_pct_pib", "ESP", row["year"], row["value"]))
    for area, pts in data["peers_pct_gdp"].items():
        rows.extend(("oecd_revenue_statistics", "_T_pct_pib", area, p["year"], p["value"]) for p in pts)
    for code, pts in data["composition_pct_gdp"].items():
        rows.extend(("oecd_revenue_statistics", f"{code}_pct_pib", "ESP", p["year"], p["value"]) for p in pts)
    for row in data["eu27_pct_gdp"]:
        rows.append(("eurostat_sdmx", "carga_fiscal_pct_pib", "ES", row["year"], row["es"]))
        rows.append(("eurostat_sdmx", "carga_fiscal_pct_pib", "EU27_2020", row["year"], row["eu27"]))
    base = data["headline"]["per_capita_base_year"]
    rows.extend(
        ("oecd+worldbank", f"recaudacion_por_habitante_eur_{base}", "ESP", p["year"], p["value"]) for p in data["per_capita_real_eur"]
    )
    for key, changes in (data.get("statutory_rates") or {}).get("series", {}).items():
        rows.extend(("vclc_tax_law_rates", f"{key}_desde", "ESP", c["from_year"], c["value_pct"]) for c in changes)
    for law in (data.get("complexity") or {}).get("amendments", []):
        rows.extend(("boe_api_legal", f"normas_modificadoras_{law['boe_id']}", "ESP", int(y), n) for y, n in law["by_year"].items())
    for row in (data.get("complexity") or {}).get("law_length", []):
        rows.append(
            ("boe_api_legal", f"palabras_sin_preambulo_{row['boe_id']}_{row['version']}", "ESP", row["year"], row["words_excl_preamble"])
        )
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["fuente", "serie", "area", "anio", "valor"])
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if not args.db.exists():
        if OUT_JSON.exists():
            print(f"export_public_viz_fiscal: {args.db.name} not found; keeping committed artifact", file=sys.stderr)
            return 0
        raise SystemExit(f"missing {args.db}; run scripts/ingest_public_finance_es.py first")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    data = build(conn)
    conn.close()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_csv(data, OUT_CSV)
    h = data["headline"]
    print(
        f"carga-fiscal: {h['oecd_first_year']} {h['oecd_first_value']}% -> {h['last_year']} {h['last_value']}% PIB "
        f"(x{h['multiple_oecd']}); {OUT_JSON.stat().st_size // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
