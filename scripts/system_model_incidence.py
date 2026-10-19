"""Who pays each tax lever of /visualizaciones/sistema/, by income quintile (offline, standard library only).

The engine computes national totals (revenue in % of GDP, with behaviour); this module only splits them between
quintiles. Shares come from microdata, totals from the model (calibrated on administrative data), so the browser
multiplies two small tables instead of simulating households.

Rules fixed before computing (docs/etl/sprints/SISTEMA-COMPLEJO-20261019/README.md §12):
- Quintiles: persons ranked by equivalised disposable income (HY020 / HX240) with weight DB090 x members, as Eurostat;
  each household belongs to the quintile of its equivalised income; household amounts weighted by DB090.
- IRPF general base per person (2024 rules, simplified): wages x (1 - 6.47 % worker contributions) + self-employment +
  unemployment, old-age, survivor, sickness and disability benefits + household rental income split between adults
  (16+); minus 2,000 EUR of «otros gastos» when there is labour or pension income and the art. 20 reduction for low
  net labour income (7,302 EUR up to 14,852, falling 1.75 per euro to zero at 19,747.5). +1 pp on every bracket costs
  1 % of (base - personal minimum 5,550); +1 pp above 60,000 costs 1 % of (base - 60,000). Savings income (interest,
  dividends) is in the savings base and out of both levers. No joint filing, no family minimums, no regional detail.
- VAT: household consumption structure by quintile from the Household Budget Survey (Eurostat hbs_str_t223, wave 2015,
  before the pandemic distorted 2020) and mean consumption per household (hbs_exp_t133), each COICOP group taxed at
  its structural rate (Ley 37/1992: art. 90 general 21 %, art. 91 reduced 10 % and 4 %, art. 20 exempt; imputed rents
  out). The 2020 wave is computed too, as a check.
- Contributions: gross wages (PY010G). Corporate tax: capital income (HY090G) for the share borne by owners, wages for
  the share borne by workers. Pensions: old-age, survivor and disability benefits (PY100G + PY110G + PY130G).
"""

from __future__ import annotations

import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

from housing_ecv_microdata import _csv, _num

WORKER_SSC = 0.0647  # general regime worker rate 2024 (4.70 + 1.55 + 0.10 + 0.12 MEI)
PERSONAL_MINIMUM = 5550.0
TOP_THRESHOLD = 60000.0
QUINTILES = ("Q1", "Q2", "Q3", "Q4", "Q5")

# Structural VAT rate of each COICOP group (Ley 37/1992). Values: {rate: share of the group}; "x" = exempt or no VAT.
VAT_RATES = {
    "CP0111": {"4": 0.5, "10": 0.5},  # bread and flour 4 %; pasta, rice, other cereals 10 %
    "CP0112": {"10": 1}, "CP0113": {"10": 1}, "CP0114": {"4": 1}, "CP0115": {"10": 1}, "CP0116": {"4": 1},
    "CP0117": {"4": 1}, "CP0118": {"10": 1}, "CP0119": {"10": 1}, "CP012": {"10": 1},
    "CP02": {"21": 1}, "CP03": {"21": 1},
    "CP041": {"x": 1}, "CP043": {"21": 1}, "CP044": {"10": 1}, "CP045": {"21": 1},
    "CP051": {"21": 1}, "CP052": {"21": 1}, "CP053": {"21": 1}, "CP054": {"21": 1}, "CP055": {"21": 1},
    "CP0561": {"21": 1}, "CP0562": {"x": 1},
    "CP0611": {"4": 1}, "CP0612": {"10": 1}, "CP0613": {"10": 1}, "CP062": {"x": 1}, "CP063": {"x": 1},
    "CP071": {"21": 1}, "CP072": {"21": 1}, "CP073": {"10": 1},
    "CP081": {"x": 1}, "CP082": {"21": 1}, "CP083": {"21": 1},
    "CP091": {"21": 1}, "CP092": {"21": 1}, "CP093": {"21": 1}, "CP094": {"10": 1}, "CP095": {"4": 1}, "CP096": {"21": 1},
    "CP10": {"x": 1}, "CP111": {"10": 1}, "CP112": {"10": 1},
    "CP121": {"21": 1}, "CP123": {"21": 1}, "CP124": {"x": 1}, "CP125": {"x": 1}, "CP126": {"x": 1}, "CP127": {"21": 1},
}


def _art20(net_labour: float) -> float:
    if net_labour <= 14852:
        return 7302.0
    if net_labour <= 19747.5:
        return max(0.0, 7302 - 1.75 * (net_labour - 14852))
    return 0.0


def liable_bases(wage_gross: float = 0.0, pension_gross: float = 0.0, other: float = 0.0) -> tuple[float, float]:
    """(base - personal minimum, base - 60,000), floored at zero, with the same simplified 2024 rules as the survey."""
    labour = wage_gross * (1 - WORKER_SSC) + pension_gross
    net_labour = max(0.0, labour - (2000.0 if labour > 0 else 0.0))
    base = max(0.0, net_labour - _art20(net_labour) + other) if labour > 0 else max(0.0, other)
    return max(0.0, base - PERSONAL_MINIMUM), max(0.0, base - TOP_THRESHOLD)


def ecv_shares(payload: bytes, year: int) -> dict:
    outer = zipfile.ZipFile(io.BytesIO(payload))
    weight = {int(r["DB030"]): float(r["DB090"]) for r in _csv(outer, year, "D")}
    hh = {}
    for h in _csv(outer, year, "H"):
        hid = int(h["HB030"])
        members = _num(h.get("HX040", "")) or 0
        hh[hid] = {
            "w": weight[hid], "members": members, "disp": _num(h["HY020"]) or 0.0, "gross": _num(h.get("HY010", "")) or 0.0,
            "cu": _num(h.get("HX240", "")) or 0.0, "rent": _num(h.get("HY040G", "")) or 0.0,
            "capital": _num(h.get("HY090G", "")) or 0.0, "adults": 0,
            "wages": 0.0, "pensions": 0.0, "base_all": 0.0, "base_top": 0.0,
        }
    people = defaultdict(list)
    for p in _csv(outer, year, "P"):
        hid = int(p["PB030"]) // 100
        if hid not in hh:
            continue
        g = {k: _num(p.get(k, "")) or 0.0 for k in ("PY010G", "PY050G", "PY090G", "PY100G", "PY110G", "PY120G", "PY130G")}
        people[hid].append(g)
        hh[hid]["adults"] += 1
    persons_base = []  # (base, household weight) for the concentration check
    for hid, h in hh.items():
        share_rent = h["rent"] / h["adults"] if h["adults"] else 0.0
        for g in people.get(hid, []):
            labour = g["PY010G"] * (1 - WORKER_SSC) + g["PY090G"] + g["PY100G"] + g["PY110G"] + g["PY120G"] + g["PY130G"]
            net_labour = max(0.0, labour - (2000.0 if labour > 0 else 0.0))
            base = max(0.0, net_labour - _art20(net_labour) + g["PY050G"] + share_rent) if labour > 0 else max(0.0, g["PY050G"] + share_rent)
            h["base_all"] += max(0.0, base - PERSONAL_MINIMUM)
            h["base_top"] += max(0.0, base - TOP_THRESHOLD)
            h["wages"] += g["PY010G"]
            h["pensions"] += g["PY100G"] + g["PY110G"] + g["PY130G"]
            if base > 0:
                persons_base.append((base, h["w"]))

    # Person-weighted quintile thresholds of equivalised disposable income.
    units = sorted(((h["disp"] / h["cu"], h["w"] * h["members"]) for h in hh.values() if h["cu"] > 0), key=lambda u: u[0])
    total = sum(w for _, w in units)
    cuts, acc, k = [], 0.0, 1
    for value, w in units:
        acc += w
        while k < 5 and acc >= total * k / 5:
            cuts.append(value)
            k += 1
    agg = {q: defaultdict(float) for q in QUINTILES}
    for h in hh.values():
        if h["cu"] <= 0:
            continue
        eq = h["disp"] / h["cu"]
        q = QUINTILES[sum(eq > c for c in cuts)]
        a = agg[q]
        a["households"] += h["w"]
        a["persons"] += h["w"] * h["members"]
        for key in ("disp", "gross", "wages", "pensions", "capital", "base_all", "base_top"):
            a[key] += h["w"] * h[key]
    sums = {key: sum(agg[q][key] for q in QUINTILES) for key in ("wages", "pensions", "capital", "base_all", "base_top")}

    # Concentration: share of the base held by the top 20 % of persons with a positive base (≈ declarants).
    persons_base.sort()
    tw = sum(w for _, w in persons_base)
    tb = sum(b * w for b, w in persons_base)
    acc, top = 0.0, 0.0
    for b, w in reversed(persons_base):
        if acc >= 0.2 * tw:
            break
        take = min(w, 0.2 * tw - acc)
        top += b * take
        acc += take
    return {
        "year": year, "income_year": year - 1,
        "cuts_eq_income": [round(c) for c in cuts],
        "quintiles": [
            {"q": q, "households": round(agg[q]["households"]), "persons": round(agg[q]["persons"]),
             "disposable_per_household": round(agg[q]["disp"] / agg[q]["households"]),
             "gross_per_household": round(agg[q]["gross"] / agg[q]["households"]),
             **{f"share_{key}": round(agg[q][key] / sums[key], 4) if sums[key] else 0.0
                for key in ("wages", "pensions", "capital", "base_all", "base_top")}}
            for q in QUINTILES
        ],
        "top20_base_share": round(top / tb * 100, 1) if tb else None,
    }


def hbs_vat(path: Path, year: str) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    ids, size = d["id"], d["size"]
    stride, pos = 1, {}
    for i in range(len(ids) - 1, -1, -1):
        pos[ids[i]] = stride
        stride *= size[i]

    def get(**kw):
        idx = sum(d["dimension"][dim]["category"]["index"][v] * pos[dim] for dim, v in kw.items())
        return d["value"].get(str(idx))

    out = {}
    for q in QUINTILES:
        code = f"QU{q[1]}"
        by_rate = defaultdict(float)
        for coicop, rates in VAT_RATES.items():
            pm = get(freq="A", quant_inc=code, coicop=coicop, unit="PM", geo="ES", time=year) or 0.0
            for rate, part in rates.items():
                by_rate[rate] += pm * part
        taxed = sum(by_rate.values())
        out[q] = {rate: round(v / taxed, 4) for rate, v in sorted(by_rate.items())}
    return out


def hbs_spending(path: Path, year: str) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    ids, size = d["id"], d["size"]
    stride, pos = 1, {}
    for i in range(len(ids) - 1, -1, -1):
        pos[ids[i]] = stride
        stride *= size[i]
    out = {}
    for q in QUINTILES:
        idx = sum(d["dimension"][dim]["category"]["index"][v] * pos[dim]
                  for dim, v in {"freq": "A", "quant_inc": f"QU{q[1]}", "unit": "PPS_HH", "geo": "ES", "time": year}.items())
        out[q] = d["value"].get(str(idx))
    return out


def vat_shares(structure: dict, spending: dict) -> dict:
    """Share of the base at each rate held by each quintile (equal household counts in the HBS quintiles)."""
    out = {}
    for rate in ("21", "10"):
        raw = {q: spending[q] * structure[q].get(rate, 0.0) for q in QUINTILES}
        tot = sum(raw.values())
        out[rate] = {q: round(raw[q] / tot, 4) for q in QUINTILES}
    allv = {q: sum(spending[q] * structure[q].get(r, 0.0) * float(r) / (100 + float(r)) for r in ("21", "10", "4")) for q in QUINTILES}
    return {"by_rate": out, "national_standard_share": round(
        sum(spending[q] * structure[q].get("21", 0.0) for q in QUINTILES) / sum(spending[q] * (1 - structure[q].get("x", 0.0)) for q in QUINTILES), 4),
        "vat_paid_pps": {q: round(v) for q, v in allv.items()}}
