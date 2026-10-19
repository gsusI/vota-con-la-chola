#!/usr/bin/env python3
"""Export /visualizaciones/sistema/ (slices 0-2: pensions, public finances, taxes, housing) to sistema.json.

Inputs, all with sha256 in the output:
- European Commission, 2024 Ageing Report, statistical annex (country fiches xlsx, raw cache): the official baseline
  for Spain (GDP growth, HICP, interest rate, employment, pensioners, gross public pension spending, migration
  sensitivities).
- The public-finance DB (scripts/ingest_public_finance_es.py): 2025 general-government accounts (EDP), employment,
  population, OECD Taxing Wages schedule for the typical case's marginal rate.
- The carga-fiscal page JSON: typical cases 1 and 4 (computed there, checked here, never recomputed).
- The edge catalog (etl/data/manual/system_model/catalog.json, built with scripts/system_model_kit.py merge).
- The voting-aid v2 snapshot: votes related to each lever.
- Housing (slice 2, scripts/system_model_housing.py): the housing page JSON (vivienda.json: completions, census stock,
  tourist dwellings, ECV cells, SERPAVI rents of the typical cases), INE household projection (table 54562, raw
  cache) and Eurostat population 25-34 (raw cache).

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
import system_model_incidence as incidence  # noqa: E402
import system_model_housing as housing  # noqa: E402
from housing_ecv_microdata import MICRO_PAGE, MICRO_URL  # noqa: E402

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
ECV_ZIP = REPO_ROOT / "etl/data/raw/housing/apis/ine_ecv_microdatos_2025.zip"
ECV_YEAR = 2025
HBS_STR = REPO_ROOT / "etl/data/raw/system_model/eurostat_hbs_str_t223_es.json"
HBS_EXP = REPO_ROOT / "etl/data/raw/system_model/eurostat_hbs_exp_t133_es.json"
HBS_YEAR, HBS_CHECK_YEAR = "2015", "2020"  # 2015: last wave before the pandemic distorted spending (2020 is the check)
VIVIENDA_JSON = DATA_DIR / "vivienda.json"
INE_PROH = REPO_ROOT / "etl/data/raw/system_model/ine_proh_54562.json"
INE_PROH_URL = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/54562?nult=30"
EUROSTAT_PJAN = REPO_ROOT / "etl/data/raw/housing/apis/eurostat_demo_pjangroup.json"
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
    "cuota_refinanciacion", "recaudacion_por_punto_irpf", "recaudacion_por_punto_irpf_alto", "pareto_a_alto", "eti_general",
    "eti_alta", "recaudacion_por_punto_iva_reducido", "recaudacion_por_punto_sociedades", "semielasticidad_base_sociedades",
    "traslado_sociedades_salarios", "salarios_pib",
    # slice 2, housing
    "respuesta_oferta_tope", "elasticidad_oferta_privada", "hip_sobre_ltv80", "hip_sobre_ltv90", "hip_sobre_ltv70",
    "hip_sobre_lti6", "hip_sobre_lti45", "conversion_turistica", "cumplimiento_tope", "traslado_escasez_alquiler",
    "renovacion_contratos", "retardo_obra_publica", "retardo_obra_privada", "coste_vivienda_publica", "renta_social_mes",
    "cuota_financiacion_publica", "desplazamiento_obra_privada", "absorcion_suelo", "respuesta_alquiler_parque",
    "elasticidad_emancipacion", "personas_por_hogar_nuevo", "hogares_por_inmigrante", "perdida_credito_restringido",
    "elasticidad_precio_credito", "elasticidad_credito_precio", "cuota_credito_nuevo", "sustitucion_alquiler",
]
# Model constants from cards (central value, no uncertainty in the engine) or from the law.
CARD_CONSTANTS = {"new_pension_relative": "new_pension_relative", "labour_output_elasticity": "elasticidad_producto_empleo"}
BENCHMARKS = ["B01_revaluation_2023_cost", "B02_irp_savings", "B03_dsm_spain", "B04_irpf_concentration",
              "B05_catalonia_2020", "B06_boom_credit", "B07_tourist_rents"]

# Votes in the voting-aid snapshot that touch each lever (matched on the plain-language summary).
LEVER_VOTES = {
    "reval": r"(sub(e|ida)[^.]{0,40}pensiones|revaloric)",
    "age": r"jubila(ción|rse)[^.]{0,60}(anticipad|65 años|penaliz|antes)",
    "contrib": r"(rebajar|bonificar|bonificaciones)[^.]{0,40}(cotizaci|cuotas)",
    "irpf": r"IRPF[^.]{0,80}(tramo|tipo|deflact|bajar|rebaja|subir|mínimo exento)|(bajar|rebaja|subir)[^.]{0,40}IRPF",
    "iva": r"\bIVA\b[^.]{0,60}(general|reducido|alimentos|18 %|8 %)|(bajar|rebaja)[^.]{0,30}\bIVA\b",
    "corp": r"[Ss]ociedades",
    "tope": r"(control de rentas|rebaj\w* por ley[^.]{0,30}alquiler|topes? del alquiler|tope del 2|índice de actualización del alquiler|limitar precios)",
    "turistico": r"(viviendas?|pisos?|alquiler)[^.]{0,25}tur[ií]stic",
    "publica": r"(vivienda (protegida|pública|social|asequible)|parque público|SAREB|gasto en vivienda)",
    "suelo": r"(liberar suelo|transformación de suelo|urbanismo|licencias de vivienda(?! tur)|trabas administrativas|millón de viviendas|más oferta)",
    "credito": r"(avales públicos|hipotecad|hipotecas? )",
}
MAX_VOTES = 12


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
    rows = sorted(seen.values(), key=lambda x: x["date"], reverse=True)[:MAX_VOTES]
    return {"party_labels": labels, "party_order": parties, "votes": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--provisional", type=Path, help="development only: JSON of parameters not yet in the catalog")
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    missing = [p for p in (args.db, AR_XLSX, CATALOG, FISCAL_JSON, VOTING_AID, ECV_ZIP, HBS_STR, HBS_EXP, VIVIENDA_JSON,
                           INE_PROH, EUROSTAT_PJAN) if not p.exists()]
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

    def marginal_at(m: float) -> float:
        lo, hi = (0.67, 1.0) if m <= 1.0 else (1.0, 1.67)
        return (npatr[hi] * hi - npatr[lo] * lo) / (hi - lo) / 100

    # Average IRPF-only marginal rate around the average wage (both sides of AW100, minus worker contributions).
    irpf_marginal_avg = (marginal_at(0.9) + marginal_at(1.1)) / 2 - ssc[1.0] / 100
    p2, p5 = cases["p2_family_renter_metro"], cases["p5_professional_madrid"]

    def persona(row: dict, earners: list[float]) -> dict:
        liable = [incidence.liable_bases(wage_gross=w) for w in earners]
        gross = sum(earners)
        return {"key": row["key"], "gross": row["gross"], "net": row["net"], "year": cy,
                "marginal_total": r(sum(marginal_at(w / aw) * w for w in earners) / gross, 4),
                "worker_ssc_rate": r(interp(sorted(ssc.items()), earners[0] / aw) / 100, 4),
                "irpf_liable": r(sum(a for a, _ in liable), 0), "irpf_above_top": r(sum(b for _, b in liable), 0),
                # What the case pays today (tax page's direct taxes minus worker contributions): the most a tax cut can return.
                "irpf_paid": r(row["direct_taxes"] - sum(w * interp(sorted(ssc.items()), w / aw) / 100 for w in earners), 0),
                "earners": [r(w, 0) for w in earners]}

    cat = load_catalog()
    provisional = json.loads(args.provisional.read_text(encoding="utf-8")) if args.provisional else {}
    params = {}
    for name in PARAMS:
        hit = cat["by_param"].get(name)
        if not hit and name in provisional:  # development only: never publish with provisional values
            params[name] = {**provisional[name], "debate": provisional[name].get("debate"), "provisional": True}
            continue
        if not hit:
            raise SystemExit(f"catalog has no card for parameter {name}")
        spec, card = hit["spec"], hit["card"]
        params[name] = {"low": spec["low"], "central": spec["central"], "high": spec["high"], "unit": spec["unit"],
                        "layer": card["layer"], "edge": card["id"], "grade": spec.get("grade", card["grade"]), "debate": None}
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
                               "derivation": card["derivation"], "sources": card["sources"],
                               "extra": [{"name": x["name"], "central": x["central"], "low": x["low"], "high": x["high"],
                                          "unit": x["unit"]} for x in card.get("extra_parameters") or []]}
    # The Catalan backtest is independent only if the compliance card does not come from the same studies.
    if "B05_catalonia_2020" in benchmarks and "cumplimiento_tope" in cat["by_param"]:
        urls = {src["url"] for src in cat["by_param"]["cumplimiento_tope"]["card"]["sources"]}
        benchmarks["B05_catalonia_2020"]["same_study"] = any(src["url"] in urls for src in benchmarks["B05_catalonia_2020"]["sources"])

    # ---- incidence by quintile (offline microsimulation; docs §12)
    ecv = incidence.ecv_shares(ECV_ZIP.read_bytes(), ECV_YEAR)
    hbs = {y: incidence.vat_shares(incidence.hbs_vat(HBS_STR, y), incidence.hbs_spending(HBS_EXP, y)) for y in (HBS_YEAR, HBS_CHECK_YEAR)}
    for y, structure in ((y, incidence.hbs_vat(HBS_STR, y)) for y in (HBS_YEAR, HBS_CHECK_YEAR)):
        spend = incidence.hbs_spending(HBS_EXP, y)
        tot = sum(spend.values())
        hbs[y]["national_basket"] = {rate: r(sum(spend[q] * structure[q].get(rate, 0.0) for q in spend) / tot, 4)
                                     for rate in ("21", "10", "4", "x")}
        hbs[y]["structure"] = structure
    incidence_block = {"ecv": ecv, "vat": {**hbs[HBS_YEAR], "year": HBS_YEAR, "check": {"year": HBS_CHECK_YEAR, **hbs[HBS_CHECK_YEAR]}}}
    comp = fiscal["composition_pct_gdp"]["T_1200"]
    corp_revenue_pct = comp[-1]["value"]
    std_gap = abs(incidence_block["vat"]["national_basket"]["21"] - cat["by_param"]["cuota_iva_general"]["spec"]["central"])
    gates.append({"id": "vat_basket_vs_hicp", "ok": std_gap <= 0.1, "value": r(std_gap, 3),
                  "detail": "standard-rate share of household spending (HBS + law, own calculation) vs the HICP-based card E13b"})
    if not gates[-1]["ok"]:
        raise SystemExit(f"input gate failed: {gates[-1]}")
    real_index, acc = [], 1.0
    for j, y in enumerate(years):
        if j:
            acc *= 1 + base["real_growth"][j] / 100
        real_index.append(r(acc, 5))
    base["real_index"] = real_index

    # ---- housing (slice 2): baseline and starting point read from vivienda.json and the raw cache
    viv = json.loads(VIVIENDA_JSON.read_text(encoding="utf-8"))
    housing_inputs, housing_gates = housing.housing_block(viv, INE_PROH, EUROSTAT_PJAN, a["Population (million)"],
                                                          a["Net migration (thousands)"], years)
    gates.extend(housing_gates)
    if not all(g["ok"] for g in housing_gates):
        raise SystemExit(f"input gate failed: {[g for g in housing_gates if not g['ok']]}")

    hicp_idx = {int(p["period"]): p["value"] for p in store.series("eurostat_sdmx", "CP00", "INX_A_AVG").get("ES", [])}
    backtest_inputs = {
        "ecv_top20_base_share": ecv["top20_base_share"],
        "icw_vat_by_quintile": fiscal["segments"]["cases"]["vat_by_quintile"],
        "gdp_2022_meur": r(gd_meur[2022] / gd_pct[2022] * 100, 0),
        "pension_pct_ar_2022": r(pens[2022], 3),
        "hicp_rates": {str(y): r((hicp_idx[y] / hicp_idx[y - 1] - 1) * 100, 3) for y in range(2014, 2019)},
    }
    model = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "slice": "0-2: pensiones, cuentas públicas, impuestos y vivienda",
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
            "irpf_marginal_avg": r(irpf_marginal_avg, 4),
            "irpf_marginal_top": 0.45,
            "vat_reduced_rate": 0.10,
            "vat_reduced_basket_share": incidence_block["vat"]["national_basket"]["10"],
            "corp_revenue_pct": corp_revenue_pct,
            "irpf_revenue_pct": fiscal["composition_pct_gdp"]["T_1100"][-1]["value"],
            "emancipation_adjust_per_year": 0.5,
            **constants_card,
        },
        "constants_notes": {
            "employer_share": "Reparto del MEI (RDL 2/2023): de 0,6 pp en 2023, 0,5 a cargo de la empresa y 0,1 del trabajador.",
            "employer_rate": "Tipo empresarial aproximado sobre la base general (contingencias comunes, desempleo, FOGASA, FP y MEI): 30 %.",
            "vat_standard_rate": "Tipo general del IVA: 21 % (Ley 37/1992, art. 90).",
            "age_phase_in_per_year": "Supuesto: el retraso de la edad se aplica a dos meses por año, el ritmo de la Ley 27/2011 desde 2019.",
            "incidence_lag_years": "Supuesto: el traslado de la cotización a salarios se completa en tres años.",
            "employment_adjust_per_year": "Supuesto: el empleo recorre cada año la mitad de la distancia hasta su nuevo nivel.",
            "irpf_marginal_avg": "Tipo marginal medio del IRPF en torno al salario medio, de la escala de la OCDE (Taxing Wages) sin cotizaciones: se usa para la respuesta de la base (elasticidad de la renta gravable).",
            "irpf_marginal_top": "Tipo marginal aproximado por encima de 60.000 €: 22,5 % de la escala estatal más una escala autonómica típica en torno al 22,5 % (varía por comunidad).",
            "vat_reduced_rate": "Tipo reducido del IVA: 10 % (Ley 37/1992, art. 91.Uno).",
            "vat_reduced_basket_share": "Parte del gasto de consumo de los hogares gravada al 10 %, con la Encuesta de Presupuestos Familiares de Eurostat (2015) y los tipos de la Ley 37/1992 por grupo de gasto (cálculo propio).",
            "irpf_revenue_pct": "Recaudación de impuestos sobre la renta de las personas en % del PIB (OCDE, último año de la página de carga fiscal): lo más que puede perderse al quitar el IRPF.",
            "corp_revenue_pct": "Recaudación del Impuesto sobre Sociedades en % del PIB, último año de la serie de la OCDE que usa la página de carga fiscal.",
            "wage_tax_rate": "Supuesto: un euro menos de salario bruto pierde unos 56 céntimos de ingresos (cotización total de la base, en torno al 36 %, más un IRPF marginal medio en torno al 20 %).",
            "emancipation_adjust_per_year": "Supuesto: los hogares latentes (jóvenes que se emancipan cuando baja el alquiler) recorren cada año la mitad de la distancia hasta su nuevo nivel.",
            "new_pension_relative": "Pensión media de las altas de jubilación frente a la media de todas (ficha del catálogo).",
            "labour_output_elasticity": "Elasticidad del PIB potencial al empleo en la función de producción de la Comisión (ficha del catálogo).",
        },
        "mei_2029": mei["spec"]["central"] if mei else None,
        "cpi_rule": rate_card["card"]["note_es"] if rate_card else None,
        "personas": {
            "p1": {**persona(p1, [p1["gross"]]), "aw_multiple": r(m1, 3), "rent_month": p1.get("rent_month")},
            # Two earners at 100 % and 67 % of the OECD average wage (Taxing Wages), as on the tax page.
            "p2": persona(p2, [aw, 0.67 * aw]),
            "p4": {"key": p4["key"], "gross": p4["gross"], "net": p4["net"], "year": cy, "pension_gross": p4["gross"],
                   "irpf_liable": r(incidence.liable_bases(pension_gross=p4["gross"])[0], 0),
                   "irpf_above_top": r(incidence.liable_bases(pension_gross=p4["gross"])[1], 0), "irpf_paid": p4["direct_taxes"]},
            "p5": persona(p5, [p5["gross"]]),
        },
        "incidence": incidence_block,
        "housing": housing_inputs,
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
            "ecv_microdata": {"label": f"INE · Encuesta de Condiciones de Vida {ECV_YEAR}, microdatos (renta de {ECV_YEAR - 1})",
                              "page": MICRO_PAGE, "url": MICRO_URL.format(year=ECV_YEAR),
                              "sha256": sha256(ECV_ZIP)},
            "eurostat_hbs": {"label": "Eurostat · Encuesta de Presupuestos Familiares por quintil (hbs_str_t223, hbs_exp_t133)",
                             "page": "https://ec.europa.eu/eurostat/databrowser/view/hbs_str_t223/default/table",
                             "sha256": sha256(HBS_STR) + " / " + sha256(HBS_EXP), "retrieved_at": "2026-10-19"},
            "boe_iva": {"label": "BOE · Ley 37/1992 del IVA (arts. 20, 90 y 91), tipos por grupo de gasto",
                        "page": "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740"},
            "vivienda": {"label": "Visualizaciones · Vivienda (obra terminada, parque, celdas de la ECV, alquileres SERPAVI de los casos tipo)",
                         "page": "/visualizaciones/vivienda/", "file": "/visualizaciones/data/vivienda.json",
                         "sha256": sha256(VIVIENDA_JSON), "generated_at": viv.get("generated_at")},
            "ine_proh": {"label": "INE · Proyección de Hogares 2026-2041 (tabla 54562)",
                         "page": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736176954&idp=1254735572981",
                         "url": INE_PROH_URL, "sha256": sha256(INE_PROH), "retrieved_at": "2026-10-19"},
            "eurostat_pop": {"label": "Eurostat · población por grupo de edad (demo_pjangroup), 25-34 años",
                             "page": "https://ec.europa.eu/eurostat/databrowser/view/demo_pjangroup/default/table",
                             "sha256": sha256(EUROSTAT_PJAN)},
            "voting_aid": {"label": "Test de voto v2 (votaciones del Congreso)", "page": "/citizen/vota/",
                           "file": "/citizen/data/voting_aid_generales_v2.json", "sha256": sha256(VOTING_AID)},
        },
    }
    if any(p.get("provisional") for p in params.values()) and args.out == OUT_JSON:
        raise SystemExit("provisional parameters: write to --out elsewhere, never to the published JSON")
    out_json = args.out
    out_json.write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    buf = io.StringIO()
    w = csv.writer(buf)
    keys = list(base)
    w.writerow(["year", *keys])
    for j, y in enumerate(years):
        w.writerow([y, *[base[k][j] for k in keys]])
    if out_json == OUT_JSON:
        OUT_CSV.write_text(buf.getvalue(), encoding="utf-8")
    size = out_json.stat().st_size
    if size > 1_000_000:
        raise SystemExit(f"sistema.json is {size} bytes (> 1 MB budget)")
    print(json.dumps({"out": out_json.name, "bytes": size, "edges": len(cat["cards"]),
                      "debt_2050": base["debt_pct"][-1], "pension_2050": base["pension_pct"][-1], "gates": gates},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
