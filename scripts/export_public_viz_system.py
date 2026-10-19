#!/usr/bin/env python3
"""Export /visualizaciones/sistema/ (slice 0: pensions + public finances) to sistema.json.

Inputs, all with sha256 in the output:
- European Commission, 2024 Ageing Report, statistical annex (country fiches xlsx, raw cache): the official baseline
  for Spain (GDP growth, HICP, interest rate, employment, pensioners, gross public pension spending, migration
  sensitivities).
- The public-finance DB (scripts/ingest_public_finance_es.py): 2025 general-government accounts (EDP), employment,
  population, OECD Taxing Wages schedule for the typical case's marginal rate.
- The carga-fiscal page JSON: typical cases 1 and 4 (computed there, checked here, never recomputed).
- The edge catalog (etl/data/manual/system_model/catalog.json, built with scripts/system_model_kit.py merge).
- The voting-aid v2 snapshot: votes related to each lever.

The engine (ui/site/app/visualizaciones/sistema/engine.mjs) works in deviations from this baseline. When an input is
missing (CI checkouts) the committed artifact is kept.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from export_public_viz_fiscal import Store, interp  # noqa: E402
from ingest_employment_es import xlsx_rows, xlsx_sheet  # noqa: E402

DEFAULT_DB = REPO_ROOT / "etl/data/staging/public-finance-es.db"
AR_XLSX = REPO_ROOT / "etl/data/raw/system_model/ar2024_countryfiches.xlsx"
AR_URL = ("https://economy-finance.ec.europa.eu/document/download/e248db46-f876-4e72-8821-efae678e81ea_en"
          "?filename=2024_Ageing_Report-Statistical_annex_all_countryfiches.xlsx")
AR_PAGE = "https://economy-finance.ec.europa.eu/publications/2024-ageing-report-economic-and-budgetary-projections-eu-member-states-2022-2070_en"
AR_FICHE = ("https://economy-finance.ec.europa.eu/document/download/392994f2-c025-4066-bea8-f65cf4bcd411_en"
            "?filename=2024-ageing-report-country-fiche-Spain.pdf")
CATALOG = REPO_ROOT / "etl/data/manual/system_model/catalog.json"
DATA_DIR = REPO_ROOT / "ui/site/public/visualizaciones/data"
FISCAL_JSON = DATA_DIR / "carga-fiscal.json"
VOTING_AID = REPO_ROOT / "ui/site/public/citizen/data/voting_aid_generales_v2.json"
OUT_JSON = DATA_DIR / "sistema.json"
OUT_CSV = DATA_DIR / "sistema.csv"

BASE_YEAR = 2025  # last year with general-government accounts
POLICY_START = 2026
LAST_YEAR = 2050

# Engine parameter -> where it comes from in the catalog (card parameter or extra_parameters name).
PARAMS = [
    "lambda_renovacion", "kappa_cohorte", "permanencia_empleo", "prestacion_alternativa", "tipo_marginal_irpf_pension",
    "multiplicador_transferencias", "multiplicador_impuestos", "persistencia_multiplicador", "semielasticidad_saldo",
    "traslado_cotizacion_salario", "elasticidad_empleo_coste", "base_cotizacion_pib", "recaudacion_por_1pct_empleo",
    "recaudacion_por_punto_iva", "traslado_iva_precios", "cuota_iva_general", "indiciacion_salarios", "prima_por_deuda",
    "cuota_refinanciacion",
]
# Model constants from cards (central value, no uncertainty in the engine) or from the law.
CARD_CONSTANTS = {"new_pension_relative": "new_pension_relative", "labour_output_elasticity": "elasticidad_producto_empleo"}
BENCHMARKS = ["B01_revaluation_2023_cost", "B02_irp_savings", "B03_dsm_spain"]

# Votes in the voting-aid snapshot that touch each lever (matched on the plain-language summary).
LEVER_VOTES = {
    "reval": r"(sub(e|ida)[^.]{0,40}pensiones|revaloric)",
    "age": r"jubila(ción|rse)[^.]{0,60}(anticipad|65 años|penaliz|antes)",
    "contrib": r"(rebajar|bonificar|bonificaciones)[^.]{0,40}(cotizaci|cuotas)",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r(v, d=3):
    return None if v is None else round(float(v), d)


def col_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def ar_rows(payload: bytes, sheet: str) -> dict[str, dict[int, float]]:
    """{row label: {year: value}} for one country sheet; header rows carry the years (D = 2022 ... AZ = 2070)."""
    rows = xlsx_rows(xlsx_sheet(payload, sheet))
    years: dict[str, int] = {}
    out: dict[str, dict[int, float]] = {}
    for i in sorted(rows):
        row = rows[i]
        cells = {k: v for k, v in row.items() if k != "B"}
        if str(row.get("D", "")).strip() == "2022":
            years = {k: int(float(v)) for k, v in cells.items() if re.fullmatch(r"\d{4}(\.0)?", str(v).strip())}
            continue
        label = str(row.get("B", "")).strip()
        if not label or not years:
            continue
        values = {}
        for k, v in cells.items():
            if k in years:
                try:
                    values[years[k]] = float(v)
                except (TypeError, ValueError):
                    pass
        if values and label not in out:
            out[label] = values
    return out


def load_catalog() -> dict:
    cards = json.loads(CATALOG.read_text(encoding="utf-8"))["edges"]
    by_param: dict[str, dict] = {}
    for card in cards:
        specs = [card["parameter"], *(card.get("extra_parameters") or [])]
        for spec in specs:
            by_param[spec["name"]] = {"spec": spec, "card": card}
    return {"cards": cards, "by_param": by_param}


def related_votes(lever: str) -> list[dict]:
    snap = json.loads(VOTING_AID.read_text(encoding="utf-8"))
    parties = [p["party_id"] for p in snap["parties"]]
    labels = {p["party_id"]: p["label"] for p in snap["parties"]}
    seen = {}
    for st in snap["statements"]:
        for v in st["votes"]:
            text = f"{v.get('summary_yes', '')}"
            if re.search(LEVER_VOTES[lever], text, re.I) and v["id"] not in seen:
                seen[v["id"]] = {
                    "id": v["id"], "date": v["vote_date"], "summary": v.get("summary_yes", ""), "title": v["title"],
                    "approved": v["approved"], "url": v["source_url"],
                    "statement": {"id": st["statement_id"], "text": st["text"]},
                    "parties": {parties[j]: c for j, c in enumerate(v["parties"]) if j < len(parties)},
                }
    rows = sorted(seen.values(), key=lambda x: x["date"], reverse=True)
    return {"party_labels": labels, "party_order": parties, "votes": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    missing = [p for p in (args.db, AR_XLSX, CATALOG, FISCAL_JSON, VOTING_AID) if not p.exists()]
    if missing:
        print(f"inputs missing ({', '.join(str(p.relative_to(REPO_ROOT)) for p in missing)}); keeping committed artifact")
        return 0

    payload = AR_XLSX.read_bytes()
    a = ar_rows(payload, "ESa")
    b = ar_rows(payload, "ESb")
    years = list(range(BASE_YEAR, LAST_YEAR + 1))

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    store = Store(conn)
    gd_meur = store.annual("eurostat_sdmx", "GD.S13", "MIO_EUR", "ES")
    gd_pct = store.annual("eurostat_sdmx", "GD.S13", "PC_GDP", "ES")
    int_meur = store.annual("eurostat_sdmx", "D41PAY.S13", "MIO_EUR", "ES")
    main_ = {code: store.annual("eurostat_sdmx", f"{code}.S13", "PC_GDP", "ES") for code in ("TR", "TE", "B9", "D41PAY")}
    pe = {code: store.annual("eurostat_sdmx", code, "THS_PER", "ES") for code in ("EMP_DC", "POP_NC")}
    cofog_pct = {code: store.annual("eurostat_sdmx", f"{code}.TE.S13", "PC_GDP", "ES") for code in ("GF1002", "GF1003")}

    def tw(measure: str, level: str, unit: str) -> dict[int, float]:
        suffix = "" if measure == "AV_TW" else "._Z"
        return store.annual("oecd_taxing_wages", f"{measure}.S_C0.{level}{suffix}", unit, "ESP")

    fiscal = json.loads(FISCAL_JSON.read_text(encoding="utf-8"))
    cases = {row["key"]: row for row in fiscal["segments"]["cases"]["rows"]}
    p1, p4 = cases["p1_young_renter_madrid"], cases["p4_retired_owner_interior"]
    cy = fiscal["segments"]["cases"]["year"]
    # Persona 1's marginal rate (IRPF + worker contributions) from the same OECD schedule the tax page uses: the slope
    # of total personal tax between 67 % and 100 % of the average wage.
    aw = tw("GEBT", "AW100", "XDC")[cy]
    npatr = {m: tw("NPATR", lvl, "PT_WG_EARN_G")[cy] for m, lvl in ((0.67, "AW67"), (1.0, "AW100"), (1.67, "AW167"))}
    ssc = {m: tw("AV_R_EMPEE_SSC", lvl, "PT_WG_EARN_G")[cy] for m, lvl in ((0.67, "AW67"), (1.0, "AW100"), (1.67, "AW167"))}
    m1 = p1["gross"] / aw
    lo_m, hi_m = (0.67, 1.0) if m1 <= 1.0 else (1.0, 1.67)
    marginal_total = (npatr[hi_m] * hi_m - npatr[lo_m] * lo_m) / (hi_m - lo_m) / 100
    worker_ssc = interp(sorted(ssc.items()), m1) / 100

    cat = load_catalog()
    params = {}
    for name in PARAMS:
        hit = cat["by_param"].get(name)
        if not hit:
            raise SystemExit(f"catalog has no card for parameter {name}")
        spec, card = hit["spec"], hit["card"]
        params[name] = {"low": spec["low"], "central": spec["central"], "high": spec["high"], "unit": spec["unit"],
                        "layer": card["layer"], "edge": card["id"], "grade": card["grade"], "debate": None}
        if card.get("debate") and spec is card["parameter"]:
            params[name]["debate"] = card["debate"]
    constants_card = {key: cat["by_param"][name]["spec"]["central"] for key, name in CARD_CONSTANTS.items()}
    mei = cat["by_param"].get("mei_tipo_2029")
    rate_card = cat["by_param"].get("indiciacion_pensiones_ipc")

    # ---- baseline (current law, Ageing Report 2024) and the 2025 starting point (EDP accounts)
    gdp_meur = gd_meur[BASE_YEAR] / gd_pct[BASE_YEAR] * 100
    implicit0 = int_meur[BASE_YEAR] / gd_meur[BASE_YEAR - 1] * 100
    primary0 = main_["B9"][BASE_YEAR] + main_["D41PAY"][BASE_YEAR]
    pens = b["Public pensions, gross"]
    phi = params["cuota_refinanciacion"]["central"]
    emp = a["Employment (20-74y; millions)"]
    base = {k: [] for k in ("pension_pct", "primary_balance_pct", "nominal_growth", "market_rate", "implicit_rate",
                            "debt_pct", "deficit_pct", "interest_pct", "pensioners_k", "employment_k",
                            "real_growth", "hicp", "migration_low_pp", "migration_high_pp")}
    debt, implicit = gd_pct[BASE_YEAR], implicit0
    for y in years:
        g_real, hicp = a["Potential GDP (growth rate)"][y], a["HICP (growth rate)"][y]
        g_nom = ((1 + g_real / 100) * (1 + hicp / 100) - 1) * 100
        market = a["Nominal interest rate"][y]
        pb = primary0 - (pens[y] - pens[BASE_YEAR])
        if y == BASE_YEAR:
            interest = main_["D41PAY"][BASE_YEAR]
            deficit = -main_["B9"][BASE_YEAR]
        else:
            implicit = (1 - phi) * implicit + phi * market
            interest = implicit / 100 * debt / (1 + g_nom / 100)
            debt = debt * (1 + implicit / 100) / (1 + g_nom / 100) - pb
            deficit = interest - pb
        base["pension_pct"].append(r(pens[y], 3))
        base["primary_balance_pct"].append(r(pb, 3))
        base["nominal_growth"].append(r(g_nom, 3))
        base["market_rate"].append(r(market, 3))
        base["implicit_rate"].append(r(implicit, 3))
        base["debt_pct"].append(r(debt, 3))
        base["deficit_pct"].append(r(deficit, 3))
        base["interest_pct"].append(r(interest, 3))
        base["pensioners_k"].append(r(b["Pensioners (public, 1000 persons)"][y], 1))
        base["employment_k"].append(r(pe["EMP_DC"][BASE_YEAR] * emp[y] / emp[BASE_YEAR], 1))
        base["real_growth"].append(r(g_real, 3))
        base["hicp"].append(r(hicp, 3))
        # Official sensitivities, % of GDP difference in pension spending (no difference in the base year).
        base["migration_low_pp"].append(r(b["Lower migration (-33%)"].get(y, 0.0) - b["Lower migration (-33%)"].get(BASE_YEAR, 0.0), 4))
        base["migration_high_pp"].append(r(b["Higher migration (+33%)"].get(y, 0.0) - b["Higher migration (+33%)"].get(BASE_YEAR, 0.0), 4))

    # ---- gates on inputs
    gates = []
    cofog_2024 = cofog_pct["GF1002"][2024] + cofog_pct["GF1003"][2024]
    gap = pens[2024] - cofog_2024
    gates.append({"id": "baseline_vs_cofog_2024", "ok": 0 <= gap <= 2.0, "value": r(gap, 2),
                  "detail": f"Ageing Report gross public pensions 2024 {pens[2024]:.2f} % vs COFOG old age + survivors "
                            f"{cofog_2024:.1f} %: the AR also counts disability pensions and is gross of nothing else"})
    pop_ar = a["Population (million)"][BASE_YEAR] * 1000
    pop_gap = abs(pop_ar / pe["POP_NC"][BASE_YEAR] - 1) * 100
    gates.append({"id": "population_2025", "ok": pop_gap < 2.5, "value": r(pop_gap, 2),
                  "detail": f"EUROPOP2023 {pop_ar:.0f} k vs Eurostat national accounts {pe['POP_NC'][BASE_YEAR]:.0f} k"})
    if not all(g["ok"] for g in gates):
        raise SystemExit(f"input gate failed: {[g for g in gates if not g['ok']]}")

    benchmarks = {}
    for bid in BENCHMARKS:
        card = next((c for c in cat["cards"] if c["id"] == bid), None)
        if card:
            benchmarks[bid] = {"value": card["parameter"]["central"], "low": card["parameter"]["low"],
                               "high": card["parameter"]["high"], "unit": card["parameter"]["unit"],
                               "derivation": card["derivation"], "sources": card["sources"]}

    hicp_idx = {int(p["period"]): p["value"] for p in store.series("eurostat_sdmx", "CP00", "INX_A_AVG").get("ES", [])}
    backtest_inputs = {
        "gdp_2022_meur": r(gd_meur[2022] / gd_pct[2022] * 100, 0),
        "pension_pct_ar_2022": r(pens[2022], 3),
        "hicp_rates": {str(y): r((hicp_idx[y] / hicp_idx[y - 1] - 1) * 100, 3) for y in range(2014, 2019)},
    }
    model = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "slice": "0: pensiones y cuentas públicas",
        "years": years,
        "policy_start": POLICY_START,
        "start": {
            "year": BASE_YEAR, "debt_pct": r(gd_pct[BASE_YEAR], 2), "deficit_pct": r(-main_["B9"][BASE_YEAR], 2),
            "interest_pct": r(main_["D41PAY"][BASE_YEAR], 2), "revenue_pct": r(main_["TR"][BASE_YEAR], 2),
            "spending_pct": r(main_["TE"][BASE_YEAR], 2), "primary_balance_pct": r(primary0, 2),
            "implicit_rate": r(implicit0, 3), "gdp_meur": r(gdp_meur, 0), "population": r(pe["POP_NC"][BASE_YEAR] * 1000, 0),
            "employment_k": r(pe["EMP_DC"][BASE_YEAR], 1), "pension_pct_ar": r(pens[BASE_YEAR], 2),
            "pension_pct_cofog_2024": r(cofog_2024, 2),
        },
        "baseline": base,
        "params": params,
        "constants": {
            "employer_share": 5 / 6,  # MEI split (RDL 2/2023): 0.5 of 0.6 pp employer, 0.1 worker
            "employer_rate": 0.30,  # employer contribution rate on the general base, rounded (orden de cotización)
            "vat_standard_rate": 0.21,
            "age_phase_in_per_year": 1 / 6,  # two months a year, the pace of Ley 27/2011 from 2019
            "incidence_lag_years": 3,
            "employment_adjust_per_year": 0.5,
            "wage_tax_rate": 0.56,  # contributions on the base (~36 %) + average marginal IRPF on wages (~20 %)
            **constants_card,
        },
        "constants_notes": {
            "employer_share": "Reparto del MEI (RDL 2/2023): de 0,6 pp en 2023, 0,5 a cargo de la empresa y 0,1 del trabajador.",
            "employer_rate": "Tipo empresarial aproximado sobre la base general (contingencias comunes, desempleo, FOGASA, FP y MEI): 30 %.",
            "vat_standard_rate": "Tipo general del IVA: 21 % (Ley 37/1992, art. 90).",
            "age_phase_in_per_year": "Supuesto: el retraso de la edad se aplica a dos meses por año, el ritmo de la Ley 27/2011 desde 2019.",
            "incidence_lag_years": "Supuesto: el traslado de la cotización a salarios se completa en tres años.",
            "employment_adjust_per_year": "Supuesto: el empleo recorre cada año la mitad de la distancia hasta su nuevo nivel.",
            "wage_tax_rate": "Supuesto: un euro menos de salario bruto pierde unos 56 céntimos de ingresos (cotización total de la base, en torno al 36 %, más un IRPF marginal medio en torno al 20 %).",
            "new_pension_relative": "Pensión media de las altas de jubilación frente a la media de todas (ficha del catálogo).",
            "labour_output_elasticity": "Elasticidad del PIB potencial al empleo en la función de producción de la Comisión (ficha del catálogo).",
        },
        "mei_2029": mei["spec"]["central"] if mei else None,
        "cpi_rule": rate_card["card"]["note_es"] if rate_card else None,
        "personas": {
            "p1": {"key": p1["key"], "gross": p1["gross"], "net": p1["net"], "year": cy, "marginal_total": r(marginal_total, 4),
                   "worker_ssc_rate": r(worker_ssc, 4), "aw_multiple": r(m1, 3), "rent_month": p1.get("rent_month")},
            "p4": {"key": p4["key"], "gross": p4["gross"], "net": p4["net"], "year": cy},
        },
        "edges": cat["cards"],
        "benchmarks": benchmarks,
        "backtest_inputs": backtest_inputs,
        "votes": {lever: related_votes(lever) for lever in LEVER_VOTES},
        "gates": gates,
        "sources": {
            "ageing_report": {"label": "Comisión Europea · Ageing Report 2024, anexo estadístico (fichas por país)",
                              "page": AR_PAGE, "url": AR_URL, "fiche": AR_FICHE, "sha256": sha256(AR_XLSX),
                              "retrieved_at": "2026-10-19"},
            "eurostat_edp": {"label": "Eurostat · déficit y deuda (gov_10dd_edpt1), cuentas de las AAPP (gov_10a_main), empleo y población (nama_10_pe), COFOG (gov_10a_exp)",
                             "page": "https://ec.europa.eu/eurostat/databrowser/view/gov_10dd_edpt1/default/table",
                             "indicators": store.provenance.get("eurostat_sdmx", [])},
            "oecd_taxing_wages": {"label": "OCDE · Taxing Wages (réplica DBnomics), tipo marginal del caso 1",
                                  "page": "https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP",
                                  "indicators": store.provenance.get("oecd_taxing_wages", [])},
            "carga_fiscal": {"label": "Visualizaciones · Carga fiscal (casos tipo 1 y 4)", "page": "/visualizaciones/carga-fiscal/",
                             "file": "/visualizaciones/data/carga-fiscal.json", "sha256": sha256(FISCAL_JSON),
                             "generated_at": fiscal.get("generated_at")},
            "catalog": {"label": "Catálogo de relaciones causales del simulador", "file": "etl/data/manual/system_model/catalog.json",
                        "sha256": sha256(CATALOG)},
            "voting_aid": {"label": "Test de voto v2 (votaciones del Congreso)", "page": "/citizen/vota/",
                           "file": "/citizen/data/voting_aid_generales_v2.json", "sha256": sha256(VOTING_AID)},
        },
    }
    OUT_JSON.write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    buf = io.StringIO()
    w = csv.writer(buf)
    keys = list(base)
    w.writerow(["year", *keys])
    for j, y in enumerate(years):
        w.writerow([y, *[base[k][j] for k in keys]])
    OUT_CSV.write_text(buf.getvalue(), encoding="utf-8")
    size = OUT_JSON.stat().st_size
    if size > 1_000_000:
        raise SystemExit(f"sistema.json is {size} bytes (> 1 MB budget)")
    print(json.dumps({"out": OUT_JSON.name, "bytes": size, "edges": len(cat["cards"]),
                      "debt_2050": base["debt_pct"][-1], "pension_2050": base["pension_pct"][-1], "gates": gates},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
