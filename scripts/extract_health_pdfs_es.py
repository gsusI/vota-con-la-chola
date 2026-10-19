#!/usr/bin/env python3
"""Extract health indicators published only as PDF by the Ministerio de Sanidad into curated, cited JSON.

1. SISLE-SNS waiting lists: the official semiannual «Indicadores resumen» PDFs cached by
   `scripts/ingest_health_es.py --fetch-pdfs` under etl/data/raw/health/sisle/ (one per cut date, 2003-2025; URL +
   retrieval time in *.meta.json) -> etl/data/manual/health/sisle_sns.json. Each value is read from the report's own
   TOTAL row (never from chart labels or from a later report's «evolución» chart). Series breaks declared by the
   Ministry (coverage changes, estimated regions) are hand-recorded as `breaks` with the footnote quoted.
2. EGSP (Estadística de Gasto Sanitario Público): public health spending per inhabitant by region, 2002-2024, from
   etl/data/raw/health/egsp/egspGastoReal.pdf -> etl/data/manual/health/egsp_ccaa.json.

Every row carries the PDF URL and sha256, the page and the literal table line it was read from, so a person can
check every value. Requires `pdftotext` (poppler).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "etl/data/raw/health/sisle"
OUT = REPO_ROOT / "etl/data/manual/health/sisle_sns.json"
EGSP_PDF = REPO_ROOT / "etl/data/raw/health/egsp/egspGastoReal.pdf"
EGSP_OUT = REPO_ROOT / "etl/data/manual/health/egsp_ccaa.json"
EGSP_PAGE = "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/gastoSanitario2005/home.htm"
# EGSP region labels -> SISLE labels (the ingest maps both to INE region codes).
EGSP_REGIONS = {
    "COMUNIDADES AUTÓNOMAS": "TOTAL", "Andalucía": "ANDALUCÍA", "Aragón": "ARAGON", "Asturias": "PDO DE ASTURIAS",
    "Illes Balears": "BALEARES", "Canarias": "CANARIAS", "Cantabria": "CANTABRIA", "Castilla y León": "CASTILLA Y LEON",
    "Castilla-La Mancha": "CASTILLA-LA MANCHA", "Cataluña": "CATALUÑA", "Comunitat Valenciana": "COMUNIDAD VALENCIANA",
    "Extremadura": "EXTREMADURA", "Galicia": "GALICIA", "Comunidad de Madrid": "MADRID", "Región de Murcia": "MURCIA",
    "Navarra": "C. FORAL DE NAVARRA", "País Vasco": "PAÍS VASCO", "La Rioja": "RIOJA",
}
LIST_PAGE = "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/listaEspera.htm"
ARCHIVE_PAGE = "https://www.sanidad.gob.es/estadEstudios/estadisticas/inforRecopilaciones/listaEsperaInfAnt.htm"
MONTHS = {"JUNIO": "06-30", "DICIEMBRE": "12-31"}
SKIP = {"Datos_ccaa_dic2025_rectificado.pdf", "Nota_Aclaratoria_Rectificacion_Dic_2025.pdf"}
REGIONS = [
    "ANDALUCÍA", "ARAGON", "PDO DE ASTURIAS", "BALEARES", "CANARIAS", "CANTABRIA", "CASTILLA Y LEON",
    "CASTILLA-LA MANCHA", "CATALUÑA", "COMUNIDAD VALENCIANA", "EXTREMADURA", "GALICIA", "MADRID", "MURCIA",
    "C. FORAL DE NAVARRA", "PAÍS VASCO", "RIOJA", "CEUTA", "MELILLA",
]
NUM = r"-?\d{1,3}(?:\.\d{3})+|-?\d+(?:,\d+)?%?"


def pages_of(pdf: Path) -> list[str]:
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True).stdout
    return text.decode("utf-8", errors="replace").split("\f")


def tokens(line: str) -> list[str]:
    return re.findall(NUM, line)


def as_int(token: str) -> int:
    return int(token.replace(".", ""))


def as_float(token: str) -> float:
    return float(token.rstrip("%").replace(".", "").replace(",", "."))


def squash(line: str) -> str:
    return re.sub(r"\s{2,}", "  ", line.strip())


def cut_date(page: str) -> str | None:
    m = re.search(r"DATOS A (\d+) DE\s*(JUNIO|DICIEMBRE) DE (\d{4})", page.upper())
    return f"{m.group(3)}-{MONTHS[m.group(2)]}" if m else None


def total_line(page: str, min_tokens: int = 3) -> str | None:
    for line in page.splitlines():
        if re.match(r"^\s*TOTAL\s+-?\d", line) and len(tokens(line)) >= min_tokens:
            return line
    return None


def is_region_page(page: str) -> bool:
    return sum(bool(re.match(rf"^\s*{re.escape(r)}\s+\d", line)) for r in REGIONS for line in page.splitlines()) >= 10


def column_offset(lines: list[str], word: str) -> int:
    hits = [line.upper().find(word) for line in lines if word in line.upper()]
    return min(hits) if hits else 10**6


def footnotes(page: str, after: str) -> list[str]:
    lines = page.splitlines()
    idx = next(i for i, line in enumerate(lines) if line == after)
    return [squash(line) for line in lines[idx + 1 : idx + 8] if re.match(r"^\s*(\(\*|\(\d\)|\*|Nota)", line)]


def surgery(pages: list[str]) -> dict | None:
    for number, page in enumerate(pages, start=1):
        if "QUIR" not in page.upper() or is_region_page(page) or "ESPECIALIDADES" not in page.upper():
            continue
        line = total_line(page, 4)
        if not line:
            continue
        toks = tokens(line)
        decimals = [i for i, t in enumerate(toks) if "," in t]
        if not decimals:
            continue
        # Patients: the largest thousands-separated integer before the first decimal (later ones are differences).
        patients = max((as_int(t) for t in toks[: decimals[0]] if "." in t or len(t) >= 5), default=None)
        rate = as_float(toks[decimals[0]])
        pct = as_float(toks[decimals[0] + 1])
        days = as_float(toks[decimals[0] + 2])
        note = None
        if patients is None or not 30e6 < patients / rate * 1000 < 55e6:
            # Dec 2019: the national row lost its patient count (only the change survives); the regional table's
            # TOTAL row of the same report carries it with identical rate/share/days.
            for other in pages:
                alt = total_line(other, 4) if is_region_page(other) and "QUIR" in other.upper() else None
                alt_toks = tokens(alt) if alt else []
                if alt_toks and as_float(alt_toks[1]) == rate and as_float(alt_toks[3]) == days and "," not in alt_toks[0]:
                    patients, note = as_int(alt_toks[0]), f"patients from the regional table TOTAL row: {squash(alt)}"
                    break
        return {
            "cut_date": cut_date(page), "page": number, "quote": squash(line), "footnotes": footnotes(page, line),
            "patients": patients, "rate_per_1000": rate, "pct_over_6_months": pct, "mean_days": days,
            **({"note": note} if note else {}),
        }
    return None


def consultations(pages: list[str]) -> dict | None:
    """National first specialist visits: the «Total primeras consultas» table, or (2025+) the regional table TOTAL."""
    fallback = None
    for number, page in enumerate(pages, start=1):
        upper = page.upper()
        if "CONSULTAS" not in upper or "QUIR" in upper:
            continue
        line = total_line(page)
        if not line:
            continue
        lines = page.splitlines()
        toks = tokens(line)
        if is_region_page(page):
            # Regional tables list rate, mean days, share over 60 days.
            if fallback is None and "," in toks[0]:
                fallback = {
                    "cut_date": cut_date(page), "page": number, "quote": squash(line), "footnotes": footnotes(page, line),
                    "rate_per_1000": as_float(toks[0]), "mean_days": as_float(toks[1]), "pct_over_60_days": as_float(toks[2]),
                    "table": "regional TOTAL row",
                }
            continue
        if "TOTAL PRIMERAS CONSULTAS" not in upper:
            continue
        header = lines[max(0, lines.index(line) - 12) : lines.index(line)]
        rest = toks[1:]
        if any("DIFERENCIA" in h.upper() for h in header) and len(rest) >= 3:
            rest = rest[1:]  # change in the rate since the previous cut
        # Column order changed over the years: read it from the header layout (pdftotext keeps columns aligned).
        days_first = column_offset(header, "TIEMPO MEDIO") < min(column_offset(header, "PORCENTAJE"), column_offset(header, "ASIGNADA"))
        days, pct = (rest[0], rest[1]) if days_first else (rest[1], rest[0])
        return {
            "cut_date": cut_date(page), "page": number, "quote": squash(line), "footnotes": footnotes(page, line),
            "rate_per_1000": as_float(toks[0]), "mean_days": as_float(days), "pct_over_60_days": as_float(pct),
            "table": "Total primeras consultas",
        }
    return fallback


def regions(pages: list[str]) -> list[dict]:
    """Selected procedures (RD 605/2003) by region: the only regional surgery table kept comparable since 2016."""
    for number, page in enumerate(pages, start=1):
        upper = page.upper()
        if not ("QUIR" in upper and "COMUNIDADES AUT" in upper and "PROCESOS SELECCIONADOS" in upper and "ANDALUC" in upper):
            continue
        if "TASA" not in upper and "PACIENTES/1000" not in upper:
            continue
        rows = []
        for line in page.splitlines():
            name = next((r for r in REGIONS if re.match(rf"^\s*{re.escape(r)}\s+\d", line)), None)
            if name is None and re.match(r"^\s*TOTAL\s+\d", line):
                name = "TOTAL"
            if not name:
                continue
            toks = tokens(line[line.upper().index(name.upper()) + len(name):])
            if len(toks) < 4:
                continue
            rows.append({
                "region": name, "page": number, "quote": squash(line), "patients": as_int(toks[0]),
                "rate_per_1000": as_float(toks[1]), "pct_over_6_months": as_float(toks[2]), "mean_days": as_float(toks[3]),
            })
        if len(rows) >= 18:
            return rows
    return []


def egsp() -> dict:
    """«Gasto sanitario público consolidado: euros por habitante. Sector de gasto Comunidades Autónomas»."""
    meta = json.loads(EGSP_PDF.with_name(EGSP_PDF.name + ".meta.json").read_text(encoding="utf-8"))
    pages = pages_of(EGSP_PDF)
    for number, page in enumerate(pages, start=1):
        if "Euros por habitante" not in page or "Sector de gasto Comunidades" not in page:
            continue
        lines = page.splitlines()
        header = next(line for line in lines if re.match(r"^\s*2002\s+2003", line))
        years = [int(y) for y in re.findall(r"(\d{4})", header)]
        provisional = [int(y) for y in re.findall(r"(\d{4})\(\*\)", header)]
        rows = []
        for line in lines:
            label = next((k for k in EGSP_REGIONS if re.search(rf"{re.escape(k)}\s+\d", line)), None)
            if not label:
                continue
            values = re.findall(r"\d{1,3}(?:\.\d{3})*", line[line.index(label) + len(label):])
            if len(values) != len(years):
                raise SystemExit(f"egsp: {label}: {len(values)} values for {len(years)} years")
            rows.append({"region": EGSP_REGIONS[label], "label": label, "page": number, "quote": squash(line),
                         "values": {str(y): as_int(v) for y, v in zip(years, values)}})
        if len(rows) != len(EGSP_REGIONS):
            raise SystemExit(f"egsp: expected {len(EGSP_REGIONS)} rows, got {len(rows)}")
        return {
            "source": {
                "name": "Ministerio de Sanidad - Estadística de Gasto Sanitario Público (EGSP), serie 2002-2024",
                "page": EGSP_PAGE, "url": meta["url"], "retrieved_at": meta["retrieved_at"],
                "sha256": hashlib.sha256(EGSP_PDF.read_bytes()).hexdigest(), "file": EGSP_PDF.name,
                "table": "Gasto sanitario público consolidado. Euros por habitante. Sector de gasto Comunidades Autónomas",
                "unit": "euros corrientes por habitante (población residente a 1 de julio, INE)",
                "provisional_years": provisional,
                "method": "scripts/extract_health_pdfs_es.py: pdftotext -layout, one row per region",
            },
            "rows": rows,
        }
    raise SystemExit("egsp: per-inhabitant regional table not found")


EGSP_STRUCTURE = {
    "economica": ["Remuneración del personal", "Consumo intermedio", "Consumo de capital fijo", "Conciertos",
                  "Transferencias corrientes", "Gasto de capital", "GASTO TOTAL SECTORES", "TOTAL CONSOLIDADO"],
    "funcional": ["Servicios hospitalarios y especializados", "Servicios primarios de salud", "Servicios de salud pública",
                  "Servicios colectivos de salud", "Farmacia", "Traslado, protesis y ap. terapéuticos", "Gasto de capital",
                  "TOTAL CONSOLIDADO"],
}


def egsp_structure() -> dict:
    """National consolidated public health spending by economic and functional classification, 2002-2024 (thousand €)."""
    meta = json.loads(EGSP_PDF.with_name(EGSP_PDF.name + ".meta.json").read_text(encoding="utf-8"))
    pages = pages_of(EGSP_PDF)
    for number, page in enumerate(pages, start=1):
        if "CLASIFICACIÓN ECONÓMICO-PRESUPUESTARIA" not in page or "CLASIFICACIÓN FUNCIONAL" not in page:
            continue
        lines = page.splitlines()
        header = next(line for line in lines if re.match(r"^\s*2002\s+2003", line))
        years = [int(y) for y in re.findall(r"(\d{4})", header)][:23]
        out = {"economica": [], "funcional": []}
        section = None
        for line in lines:
            if "CLASIFICACIÓN ECONÓMICO-PRESUPUESTARIA" in line:
                section = "economica"
                continue
            if "CLASIFICACIÓN FUNCIONAL" in line:
                section = "funcional"
                continue
            if "AGREGADOS DE CONTABILIDAD" in line:
                section = None
            if section is None:
                continue
            label = next((k for k in EGSP_STRUCTURE[section] if line.strip().startswith(k)), None)
            if not label:
                continue
            values = re.findall(r"\d{1,3}(?:\.\d{3})+|\d+", line[line.index(label) + len(label):])[: len(years)]
            if len(values) != len(years):
                raise SystemExit(f"egsp structure: {label}: {len(values)} values")
            out[section].append({"label": label, "page": number, "quote": squash(line)[:160],
                                 "values": {str(y): as_int(v) for y, v in zip(years, values)}})
        for section, rows in out.items():
            # Economic items add up to the sum of sectors (before removing transfers between them); functions add up
            # to the consolidated total.
            total = next(r for r in rows if r["label"] == ("GASTO TOTAL SECTORES" if section == "economica" else "TOTAL CONSOLIDADO"))
            parts = [r for r in rows if r["label"] not in ("TOTAL CONSOLIDADO", "GASTO TOTAL SECTORES")]
            for y in map(str, years):
                gap = abs(sum(r["values"][y] for r in parts) - total["values"][y])
                if gap > 5:  # thousand euros of rounding
                    raise SystemExit(f"egsp structure: {section} {y} parts do not add up ({gap})")
        return {
            "source": {
                "name": "Ministerio de Sanidad - EGSP 2002-2024, gasto sanitario público consolidado por clasificación económica y funcional",
                "page": EGSP_PAGE, "url": meta["url"], "retrieved_at": meta["retrieved_at"],
                "sha256": hashlib.sha256(EGSP_PDF.read_bytes()).hexdigest(), "file": EGSP_PDF.name,
                "unit": "miles de euros corrientes", "method": "scripts/extract_health_pdfs_es.py: pdftotext -layout; each row checked against the TOTAL CONSOLIDADO row",
            },
            **out,
        }
    raise SystemExit("egsp structure: page not found")


AGE_PROFILE_PDF = REPO_ROOT / "etl/data/raw/health/ageprofile/funcas_dt673_2012.pdf"
AGE_GROUPS = ["0a4", "5a9", "10a14", "15a19", "20a24", "25a29", "30a34", "35a39", "40a44", "45a49", "50a54", "55a59",
              "60a64", "65a69", "70a74", "75a79", "80 y más"]


def age_profile() -> dict:
    """Public health spending per person by 5-year age group, Spain (Blanco, Urbanos y Thuissard, Funcas DT 673/2012,
    appendix table 15, both sexes, constant 1998 euros). Used only as relative cost weights for age standardisation."""
    meta = json.loads(AGE_PROFILE_PDF.with_name(AGE_PROFILE_PDF.name + ".meta.json").read_text(encoding="utf-8"))
    pages = pages_of(AGE_PROFILE_PDF)
    for number, page in enumerate(pages, start=1):
        if "Tabla 15. Gasto sanitario total" not in page:
            continue
        rows = []
        for line in page.splitlines():
            label = next((g for g in AGE_GROUPS if re.match(rf"^\s*{re.escape(g)}\s+\d", line)), None)
            if label:
                values = re.findall(r"-?\d+(?:,\d+)?|\d{1,3}(?:\.\d{3})+", line[line.index(label) + len(label):])
                rows.append({"age": label, "page": number, "quote": squash(line),
                             "euros_1998": {"1998": int(values[0]), "2003": int(values[1]), "2008": int(values[2])}})
            elif line.strip().startswith("Población Total"):
                values = re.findall(r"\d+", line)
                total = {"page": number, "quote": squash(line), "euros_1998": {"1998": int(values[0]), "2003": int(values[1]), "2008": int(values[2])}}
        if len(rows) != len(AGE_GROUPS):
            raise SystemExit(f"age profile: {len(rows)} rows")
        return {
            "source": {
                "name": "Blanco Moreno, Urbanos Garrido y Thuissard Vasallo (2012), Distribución del gasto sanitario público por "
                "edad y sexo en España: análisis de la década 1998-2008, Funcas, Documento de trabajo 673, apéndice, tabla 15",
                "url": meta["url"], "retrieved_at": meta["retrieved_at"], "file": AGE_PROFILE_PDF.name,
                "sha256": hashlib.sha256(AGE_PROFILE_PDF.read_bytes()).hexdigest(),
                "page_url": "https://www.funcas.es/documentos_trabajo/distribucion-del-gasto-sanitario-publico-por-edad-y-sexo-en-espana-analisis-de-la-decada-1998-2008/",
                "note": "Perfil español; la Comisión Europea (Ageing Report 2024, gráfico I.2.2) publica perfiles por edad solo como gráfico, sin datos.",
            },
            "rows": rows, "total": total,
        }
    raise SystemExit("age profile: table 15 not found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    reports, surgery_rows, consult_rows, region_rows = [], [], [], []
    for pdf in sorted(RAW_DIR.glob("*.pdf")):
        meta = json.loads(pdf.with_name(pdf.name + ".meta.json").read_text(encoding="utf-8"))
        ref = {"file": pdf.name, "url": meta["url"], "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
               "retrieved_at": meta["retrieved_at"]}
        if pdf.name in SKIP:
            # Cited, not parsed: the Dec 2025 rectification note and the regional annex.
            reports.append({**ref, "cut_date": "2025-12-31", "role": "annex"})
            continue
        pages = pages_of(pdf)
        s = surgery(pages)
        c = consultations(pages)
        g = regions(pages)
        date = (s or {}).get("cut_date") or (c or {}).get("cut_date")
        reports.append({**ref, "cut_date": date})
        if s:
            surgery_rows.append({**s, "report": pdf.name})
        if c:
            consult_rows.append({**c, "report": pdf.name})
        for row in g:
            region_rows.append({**row, "cut_date": date, "report": pdf.name})
    reports.sort(key=lambda r: (r["cut_date"] or "", r.get("role", ""), r["file"]))
    surgery_rows.sort(key=lambda r: r["cut_date"])
    consult_rows.sort(key=lambda r: r["cut_date"])
    region_rows.sort(key=lambda r: (r["region"], r["cut_date"]))
    existing = json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {}
    data = {
        "source": {
            "name": "Ministerio de Sanidad - Sistema de Información sobre Listas de Espera del SNS (SISLE-SNS)",
            "page": LIST_PAGE, "archive": ARCHIVE_PAGE,
            "method": "scripts/extract_health_pdfs_es.py: pdftotext -layout; each value from the report's own TOTAL row",
        },
        "reports": reports,
        "surgery": surgery_rows,
        "consultations": consult_rows,
        "surgery_selected_by_region": region_rows,
        # Hand-curated parts (breaks, overrides, revisions) survive re-extraction.
        "breaks": existing.get("breaks", []),
        "overrides": existing.get("overrides", []),
        "revisions": existing.get("revisions", []),
    }
    for override in data["overrides"]:
        target = next(r for r in data[override["series"]] if r["cut_date"] == override["cut_date"])
        target.update(override["values"])
        target["override_note"] = override["note"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"sisle: {len(surgery_rows)} surgery, {len(consult_rows)} consultation cuts, {len(region_rows)} region rows")
    if EGSP_PDF.exists():
        spend = egsp()
        EGSP_OUT.write_text(json.dumps(spend, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"egsp: {len(spend['rows'])} regions")
        structure = egsp_structure()
        (EGSP_OUT.parent / "egsp_estructura.json").write_text(json.dumps(structure, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"egsp structure: {len(structure['economica'])} economic, {len(structure['funcional'])} functional rows")
    if AGE_PROFILE_PDF.exists():
        profile = age_profile()
        (EGSP_OUT.parent / "perfil_gasto_edad.json").write_text(json.dumps(profile, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"age profile: {len(profile['rows'])} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
