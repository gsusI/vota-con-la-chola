#!/usr/bin/env python3
"""Genera una instantanea de niveles electorales de Espana y sus proximas fechas.

Comportamiento idempotente:
- Salida determinista para un valor concreto de --today.
- Solo escribe archivos cuando cambia su contenido.

Este script combina:
- Ciclos legales fijos (municipales y niveles ligados a municipales, ciclo UE).
- Niveles condicionales donde la fecha exacta no esta fijada por adelantado.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List

FUENTES = [
    "https://infoelectoral.interior.gob.es/es/proceso-electoral/preguntas-frecuentes/tipos-de-elecciones/",
    "https://infoelectoral.interior.gob.es/es/proceso-electoral/preguntas-frecuentes/tipos-de-elecciones/elecciones-al-parlamento-europeo/index.html",
    "https://www.boe.es/buscar/act.php?id=BOE-A-1985-11672",  # LOREG
    "https://www.boe.es/legislacion/documentos/ConstitucionCASTELLANO.pdf",  # Constitucion
]

ANCLAS = {
    "anio_ue_ultimo_conocido": 2024,
    "fecha_local_ultima_conocida": dt.date(2023, 5, 28),
    "fecha_generales_ultima_conocida": dt.date(2023, 7, 23),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generar instantanea de proximas elecciones por nivel en Espana"
    )
    parser.add_argument(
        "--today",
        default=dt.date.today().isoformat(),
        help="Fecha de referencia en formato YYYY-MM-DD (por defecto: hoy)",
    )
    parser.add_argument(
        "--md-out",
        default="docs/proximas-elecciones-espana.md",
        help="Ruta del archivo Markdown de salida",
    )
    parser.add_argument(
        "--json-out",
        default="etl/data/published/proximas-elecciones-espana.json",
        help="Ruta del archivo JSON de salida",
    )
    return parser.parse_args()


def parse_iso_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def cuarto_domingo_de_mayo(year: int) -> dt.date:
    domingos = [
        dt.date(year, 5, day)
        for day in range(1, 32)
        if dt.date(year, 5, day).weekday() == 6
    ]
    return domingos[3]


def proxima_fecha_local(today: dt.date) -> dt.date:
    year = ANCLAS["fecha_local_ultima_conocida"].year
    while True:
        fecha = cuarto_domingo_de_mayo(year)
        if fecha >= today:
            return fecha
        year += 4


def proximo_anio_ciclo_ue(today: dt.date) -> int:
    year = ANCLAS["anio_ue_ultimo_conocido"]
    while year < today.year:
        year += 5
    return year


def ventana_generales_si_legislatura_completa() -> Dict[str, str]:
    """Ventana esperada si no hay disolucion anticipada de las Cortes."""
    last = ANCLAS["fecha_generales_ultima_conocida"]
    fin_legislatura = dt.date(last.year + 4, last.month, last.day)

    # Rango constitucional: entre 30 y 60 dias desde fin de legislatura.
    inicio_ventana = fin_legislatura + dt.timedelta(days=30)
    fin_ventana = fin_legislatura + dt.timedelta(days=60)

    primer_domingo = inicio_ventana + dt.timedelta(days=(6 - inicio_ventana.weekday()) % 7)
    ultimo_domingo = fin_ventana - dt.timedelta(days=(fin_ventana.weekday() - 6) % 7)

    return {
        "fin_legislatura": fin_legislatura.isoformat(),
        "inicio_ventana": inicio_ventana.isoformat(),
        "fin_ventana": fin_ventana.isoformat(),
        "inicio_ventana_domingos": primer_domingo.isoformat(),
        "fin_ventana_domingos": ultimo_domingo.isoformat(),
    }


def construir_snapshot(today: dt.date) -> Dict[str, Any]:
    fecha_local = proxima_fecha_local(today)
    anio_ue = proximo_anio_ciclo_ue(today)
    ventana_generales = ventana_generales_si_legislatura_completa()

    niveles: List[Dict[str, Any]] = [
        {
            "nivel": "Europeo",
            "eleccion": "Parlamento Europeo",
            "estado": "ciclo conocido, fecha no fijada",
            "proximo_anio_esperado": anio_ue,
            "notas": (
                "Las elecciones europeas son cada 5 anos. "
                "La fecha exacta en Espana se fija en la convocatoria oficial."
            ),
        },
        {
            "nivel": "Nacional",
            "eleccion": "Cortes Generales (Congreso y Senado)",
            "estado": "fecha condicional",
            "proximo_si_legislatura_completa": ventana_generales,
            "notas": (
                "La fecha puede cambiar si hay disolucion anticipada. "
                "La ventana mostrada asume legislatura completa desde 2023-07-23."
            ),
        },
        {
            "nivel": "Autonomico",
            "eleccion": "Parlamentos de las comunidades autonomas",
            "estado": "sin fecha unica estatal",
            "proximo_esperado": "depende_de_cada_comunidad",
            "notas": (
                "No existe una fecha unica para todas las autonomicas. "
                "Cada comunidad sigue su propio calendario y convocatorias."
            ),
        },
        {
            "nivel": "Local/Municipal",
            "eleccion": "Ayuntamientos",
            "estado": "ciclo fijo",
            "proxima_fecha": fecha_local.isoformat(),
            "notas": "Cuarto domingo de mayo cada 4 anos.",
        },
        {
            "nivel": "Insular",
            "eleccion": "Cabildos (Canarias) y Consells (Baleares)",
            "estado": "ligado al ciclo local",
            "proxima_fecha": fecha_local.isoformat(),
            "notas": "Se celebran junto con el ciclo local.",
        },
        {
            "nivel": "Ciudades autonomas",
            "eleccion": "Asambleas de Ceuta y Melilla",
            "estado": "ligado al ciclo local",
            "proxima_fecha": fecha_local.isoformat(),
            "notas": "Se celebran junto con el ciclo local.",
        },
        {
            "nivel": "Territorios historicos (Pais Vasco)",
            "eleccion": "Juntas Generales (Alava, Bizkaia, Gipuzkoa)",
            "estado": "ligado al ciclo local",
            "proxima_fecha": fecha_local.isoformat(),
            "notas": "Eleccion directa habitualmente alineada con el ciclo local.",
        },
        {
            "nivel": "Entidades locales menores",
            "eleccion": "EATIM / entidades locales menores",
            "estado": "ligado al ciclo local",
            "proxima_fecha": fecha_local.isoformat(),
            "notas": "Generalmente alineadas con el ciclo local cuando aplica.",
        },
        {
            "nivel": "Provincial",
            "eleccion": "Diputaciones Provinciales",
            "estado": "eleccion indirecta",
            "proxima_esperada_despues_de": fecha_local.isoformat(),
            "notas": "Se constituyen en general de forma indirecta desde resultados municipales.",
        },
    ]

    generado_en = dt.datetime.combine(
        today, dt.time(0, 0, 0, tzinfo=dt.timezone.utc)
    ).isoformat()

    return {
        "generado_en": generado_en,
        "fecha_referencia": today.isoformat(),
        "anclas": {
            k: v.isoformat() if isinstance(v, dt.date) else v for k, v in ANCLAS.items()
        },
        "niveles": niveles,
        "fuentes": FUENTES,
    }


def a_markdown(snapshot: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Proximas elecciones en Espana (por nivel)")
    lines.append("")
    lines.append(f"Fecha de referencia: **{snapshot['fecha_referencia']}**")
    lines.append("")
    lines.append("| Nivel | Eleccion | Proxima | Estado | Notas |")
    lines.append("|---|---|---|---|---|")

    for item in snapshot["niveles"]:
        proxima = "-"
        if "proxima_fecha" in item:
            proxima = item["proxima_fecha"]
        elif "proximo_anio_esperado" in item:
            proxima = str(item["proximo_anio_esperado"])
        elif "proximo_esperado" in item:
            proxima = item["proximo_esperado"]
        elif "proxima_esperada_despues_de" in item:
            proxima = f"despues de {item['proxima_esperada_despues_de']}"
        elif "proximo_si_legislatura_completa" in item:
            w = item["proximo_si_legislatura_completa"]
            proxima = (
                f"si legislatura completa: {w['inicio_ventana_domingos']} a {w['fin_ventana_domingos']}"
            )

        lines.append(
            "| {nivel} | {eleccion} | {proxima} | {estado} | {notas} |".format(
                nivel=item["nivel"],
                eleccion=item["eleccion"],
                proxima=proxima,
                estado=item["estado"],
                notas=item["notas"],
            )
        )

    lines.append("")
    lines.append("## Fuentes")
    lines.append("")
    for fuente in snapshot["fuentes"]:
        lines.append(f"- {fuente}")

    lines.append("")
    lines.append("## Aclaraciones")
    lines.append("")
    lines.append("- Las fechas nacionales y muchas autonomicas son legales/politicamente condicionales.")
    lines.append("- Este archivo es una instantanea calculada, no una convocatoria legal.")

    return "\n".join(lines) + "\n"


def escribir_si_cambia(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    args = parse_args()
    today = parse_iso_date(args.today)
    snapshot = construir_snapshot(today)

    md_text = a_markdown(snapshot)
    json_text = json.dumps(snapshot, ensure_ascii=True, indent=2, sort_keys=True) + "\n"

    md_path = Path(args.md_out)
    json_path = Path(args.json_out)

    md_changed = escribir_si_cambia(md_path, md_text)
    json_changed = escribir_si_cambia(json_path, json_text)

    print(
        "Instantanea generada para {ref}. md={md} ({mchg}), json={js} ({jchg})".format(
            ref=today.isoformat(),
            md=md_path,
            js=json_path,
            mchg="actualizado" if md_changed else "sin cambios",
            jchg="actualizado" if json_changed else "sin cambios",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
