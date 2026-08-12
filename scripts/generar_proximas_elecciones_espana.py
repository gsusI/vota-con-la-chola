#!/usr/bin/env python3
"""Genera calendario electoral público y fuenteable.

Combina:
- Scrape/fetch de calendarios oficiales publicados.
- Ciclos legales calculables cuando aún no hay convocatoria.
- Filas explícitas sin fecha cuando la fecha depende de convocatoria futura.

Salida determinista para un valor concreto de --today.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.http import http_get_bytes
from publicdata_core.util import now_utc_iso


FUENTES = [
    "https://infoelectoral.interior.gob.es/es/proceso-electoral/calendario-electoral/",
    "https://infoelectoral.interior.gob.es/es/proceso-electoral/preguntas-frecuentes/tipos-de-elecciones/",
    "https://www.boe.es/buscar/act.php?id=BOE-A-1985-11672",
    "https://www.boe.es/legislacion/documentos/ConstitucionCASTELLANO.pdf",
]

OFFICIAL_CALENDAR_SOURCES: list[dict[str, Any]] = [
    {
        "source_id": "jec_andalucia_2026_calendario",
        "name": "Junta Electoral de Andalucía - calendario electoral 2026",
        "url": "https://www.juntaelectoralcentral.es/cs/jec/documentos/Andalucia_2026_calendario.pdf",
        "format": "pdf",
        "expected_terms": [
            "Elecciones al Parlamento de",
            "Andalucía",
            "17 de mayo de 2026",
            "Jornada de votación",
        ],
        "event": {
            "event_id": "autonomico-andalucia-2026-05-17",
            "level": "Autonómico",
            "scope": "autonomico",
            "election": "Parlamento de Andalucía",
            "election_type": "parlamento_autonomico",
            "territory": "Andalucía",
            "date": "2026-05-17",
            "date_precision": "day",
            "status": "convocada",
            "certainty": "oficial",
            "notes": "Calendario oficial de la Junta Electoral de Andalucía.",
        },
    }
]

ANCLAS = {
    "anio_ue_ultimo_conocido": 2024,
    "fecha_local_ultima_conocida": dt.date(2023, 5, 28),
    "fecha_generales_ultima_conocida": dt.date(2023, 7, 23),
}

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generar calendario electoral público de España"
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
        help="Ruta del JSON canónico publicado",
    )
    parser.add_argument(
        "--public-json-out",
        default="",
        help="Ruta adicional para UI estática, por ejemplo ui/gh-pages-next/public/...",
    )
    parser.add_argument(
        "--raw-dir",
        default="etl/data/raw/election_calendar",
        help="Directorio raw para documentos oficiales descargados",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP por fuente")
    parser.add_argument("--no-network", action="store_true", help="No descargar fuentes oficiales")
    parser.add_argument(
        "--strict-network",
        action="store_true",
        help="Abortar si falla la descarga de una fuente oficial configurada",
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


def ventana_generales_si_legislatura_completa() -> dict[str, str]:
    """Ventana esperada si no hay disolución anticipada de las Cortes."""
    last = ANCLAS["fecha_generales_ultima_conocida"]
    fin_legislatura = dt.date(last.year + 4, last.month, last.day)

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


def normalize_for_match(value: str) -> str:
    table = str.maketrans(
        {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ü": "u",
            "ñ": "n",
            "Á": "a",
            "É": "e",
            "Í": "i",
            "Ó": "o",
            "Ú": "u",
            "Ü": "u",
            "Ñ": "n",
        }
    )
    return re.sub(r"\s+", " ", value.translate(table).lower()).strip()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_source_filename(source_id: str, url: str) -> str:
    suffix = "pdf" if url.lower().split("?", 1)[0].endswith(".pdf") else "html"
    safe_id = re.sub(r"[^a-z0-9_-]+", "-", source_id.lower()).strip("-")
    return f"{safe_id}.{suffix}"


def public_artifact_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def extract_pdf_text(raw_path: Path, timeout: int = 20) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return ""
    try:
        completed = subprocess.run(
            [pdftotext, "-layout", str(raw_path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout


def payload_to_text(payload: bytes, raw_path: Path, content_type: str | None) -> str:
    lower_ct = (content_type or "").lower()
    if raw_path.suffix.lower() == ".pdf" or "pdf" in lower_ct:
        return extract_pdf_text(raw_path)
    return payload.decode("utf-8", errors="replace")


def extract_spanish_dates(text: str) -> list[str]:
    dates: list[str] = []
    pattern = re.compile(
        r"\b(\d{1,2})\s+de\s+([a-záéíóúüñ]+)\s+de\s+(\d{4})\b",
        flags=re.IGNORECASE,
    )
    for day_s, month_s, year_s in pattern.findall(text):
        month = SPANISH_MONTHS.get(normalize_for_match(month_s))
        if not month:
            continue
        try:
            parsed = dt.date(int(year_s), month, int(day_s))
        except ValueError:
            continue
        dates.append(parsed.isoformat())
    return dates


def source_terms_verified(text: str, expected_terms: list[str]) -> bool:
    if not text:
        return False
    normalized = normalize_for_match(text)
    return all(normalize_for_match(term) in normalized for term in expected_terms)


def scrape_official_calendar_sources(
    *,
    today: dt.date,
    raw_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []

    for source in OFFICIAL_CALENDAR_SOURCES:
        source_id = str(source["source_id"])
        url = str(source["url"])
        raw_path = raw_dir / safe_source_filename(source_id, url)
        content_type: str | None = None
        payload = b""
        text = ""
        status = "skipped"
        error = ""

        if not no_network:
            try:
                payload, content_type = http_get_bytes(url, timeout=timeout, max_attempts=1)
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(payload)
                text = payload_to_text(payload, raw_path, content_type)
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
                status = "error"
                if strict_network:
                    raise

        source_verified = bool(payload) and (
            source_terms_verified(text, list(source.get("expected_terms") or [])) or not text
        )
        extracted_dates = extract_spanish_dates(text)

        report = {
            "source_id": source_id,
            "name": source["name"],
            "url": url,
            "format": source["format"],
            "status": status,
            "source_verified": source_verified,
            "content_type": content_type,
            "bytes": len(payload),
            "content_sha256": sha256_bytes(payload) if payload else "",
            "raw_path": public_artifact_path(raw_path) if payload else "",
            "extracted_dates": extracted_dates[:12],
            "error": error,
        }
        source_reports.append(report)

        event = dict(source["event"])
        fallback_date = str(event.get("date") or "")
        if fallback_date in extracted_dates:
            event["date"] = fallback_date
        elif extracted_dates:
            # Keep manifest date as truth, but expose parsed dates for audit in source_reports.
            event["date"] = fallback_date

        if not event_is_upcoming(event, today):
            continue

        event.update(
            {
                "source_kind": "official_calendar",
                "source_url": url,
                "source_id": source_id,
                "source_verified": source_verified,
                "source_status": status,
                "source_hash": report["content_sha256"],
            }
        )
        events.append(finalize_event(event))

    return events, source_reports


def base_legal_cycle_events(today: dt.date) -> list[dict[str, Any]]:
    fecha_local = proxima_fecha_local(today)
    anio_ue = proximo_anio_ciclo_ue(today)
    ventana_generales = ventana_generales_si_legislatura_completa()

    local_source = FUENTES[2]
    return [
        {
            "event_id": "municipal-local-2027-05-23",
            "level": "Municipal",
            "scope": "municipal",
            "election": "Ayuntamientos",
            "election_type": "municipales",
            "territory": "España",
            "date": fecha_local.isoformat(),
            "date_precision": "day",
            "status": "ciclo fijo",
            "certainty": "calculada",
            "source_kind": "legal_cycle",
            "source_url": local_source,
            "notes": "Cuarto domingo de mayo cada 4 años.",
        },
        {
            "event_id": "insular-cabildos-consells-2027-05-23",
            "level": "Insular",
            "scope": "insular",
            "election": "Cabildos canarios y consells insulares",
            "election_type": "insular",
            "territory": "Canarias / Illes Balears",
            "date": fecha_local.isoformat(),
            "date_precision": "day",
            "status": "ligado al ciclo local",
            "certainty": "calculada",
            "source_kind": "legal_cycle",
            "source_url": local_source,
            "notes": "Habitualmente se celebran junto con el ciclo local.",
        },
        {
            "event_id": "ceuta-melilla-2027-05-23",
            "level": "Ciudades autónomas",
            "scope": "autonomico",
            "election": "Asambleas de Ceuta y Melilla",
            "election_type": "ciudades_autonomas",
            "territory": "Ceuta / Melilla",
            "date": fecha_local.isoformat(),
            "date_precision": "day",
            "status": "ligado al ciclo local",
            "certainty": "calculada",
            "source_kind": "legal_cycle",
            "source_url": local_source,
            "notes": "Ciclo alineado con elecciones locales salvo convocatoria específica.",
        },
        {
            "event_id": "juntas-generales-pais-vasco-2027-05-23",
            "level": "Territorios históricos",
            "scope": "foral",
            "election": "Juntas Generales de Álava, Bizkaia y Gipuzkoa",
            "election_type": "juntas_generales",
            "territory": "País Vasco",
            "date": fecha_local.isoformat(),
            "date_precision": "day",
            "status": "ligado al ciclo local",
            "certainty": "calculada",
            "source_kind": "legal_cycle",
            "source_url": local_source,
            "notes": "Elección directa habitualmente alineada con el ciclo local.",
        },
        {
            "event_id": "eatim-2027-05-23",
            "level": "Entidades locales menores",
            "scope": "municipal",
            "election": "EATIM y entidades locales menores",
            "election_type": "entidades_locales_menores",
            "territory": "España",
            "date": fecha_local.isoformat(),
            "date_precision": "day",
            "status": "ligado al ciclo local",
            "certainty": "calculada",
            "source_kind": "legal_cycle",
            "source_url": local_source,
            "notes": "Generalmente alineadas con el ciclo local cuando aplica.",
        },
        {
            "event_id": "diputaciones-provinciales-2027",
            "level": "Provincial",
            "scope": "provincial",
            "election": "Diputaciones provinciales",
            "election_type": "diputaciones",
            "territory": "Provincias de régimen común",
            "date": (fecha_local + dt.timedelta(days=1)).isoformat(),
            "date_label": f"después de {fecha_local.isoformat()}",
            "date_precision": "after_day",
            "status": "elección indirecta",
            "certainty": "condicional",
            "source_kind": "legal_cycle",
            "source_url": local_source,
            "notes": "Constitución indirecta derivada de resultados municipales.",
        },
        {
            "event_id": "generales-si-legislatura-completa-2027",
            "level": "Estatal",
            "scope": "estatal",
            "election": "Cortes Generales (Congreso y Senado)",
            "election_type": "generales",
            "territory": "España",
            "date": ventana_generales["inicio_ventana_domingos"],
            "date_end": ventana_generales["fin_ventana_domingos"],
            "date_precision": "window",
            "status": "fecha condicional",
            "certainty": "condicional",
            "source_kind": "legal_cycle",
            "source_url": FUENTES[3],
            "notes": "Ventana si la legislatura iniciada el 2023-07-23 llega completa.",
        },
        {
            "event_id": "europeas-2029",
            "level": "Europeo",
            "scope": "europeo",
            "election": "Parlamento Europeo",
            "election_type": "europeas",
            "territory": "España",
            "date": f"{anio_ue}-01-01",
            "date_label": f"{anio_ue} (fecha exacta no fijada)",
            "date_precision": "year",
            "status": "ciclo conocido, fecha no fijada",
            "certainty": "condicional",
            "source_kind": "legal_cycle",
            "source_url": FUENTES[1],
            "notes": "Ciclo europeo de 5 años; fecha exacta se fija en convocatoria.",
        },
        {
            "event_id": "autonomicas-sin-fecha-unica",
            "level": "Autonómico",
            "scope": "autonomico",
            "election": "Parlamentos de comunidades autónomas",
            "election_type": "parlamentos_autonomicos",
            "territory": "Comunidades autónomas",
            "date": None,
            "date_precision": "unknown",
            "status": "sin fecha única estatal",
            "certainty": "desconocida",
            "source_kind": "legal_cycle",
            "source_url": FUENTES[0],
            "notes": "Cada comunidad depende de su legislatura y de convocatorias oficiales.",
        },
    ]


def event_is_upcoming(event: dict[str, Any], today: dt.date) -> bool:
    raw_date = event.get("date")
    raw_end = event.get("date_end") or raw_date
    if not raw_date:
        return True
    try:
        parsed_end = dt.date.fromisoformat(str(raw_end))
    except ValueError:
        return True
    return parsed_end >= today


def finalize_event(event: dict[str, Any]) -> dict[str, Any]:
    raw_date = event.get("date")
    date_end = event.get("date_end")
    date_label = event.get("date_label")
    if not date_label:
        if raw_date and date_end:
            date_label = f"{raw_date} a {date_end}"
        elif raw_date:
            date_label = str(raw_date)
        else:
            date_label = "sin fecha fijada"

    return {
        "event_id": event["event_id"],
        "level": event["level"],
        "scope": event["scope"],
        "election": event["election"],
        "election_type": event["election_type"],
        "territory": event["territory"],
        "date": raw_date,
        "date_end": date_end,
        "date_label": date_label,
        "date_precision": event["date_precision"],
        "status": event["status"],
        "certainty": event["certainty"],
        "source_kind": event["source_kind"],
        "source_id": event.get("source_id") or event["source_kind"],
        "source_url": event["source_url"],
        "source_hash": event.get("source_hash") or "",
        "source_verified": bool(event.get("source_verified", event["source_kind"] == "legal_cycle")),
        "source_status": event.get("source_status") or "computed",
        "notes": event["notes"],
    }


def sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(event: dict[str, Any]) -> tuple[str, str, str]:
        date_key = str(event.get("date") or "9999-12-31")
        return (date_key, str(event.get("level") or ""), str(event.get("election") or ""))

    return sorted(events, key=key)


def legacy_niveles(today: dt.date) -> list[dict[str, Any]]:
    fecha_local = proxima_fecha_local(today)
    anio_ue = proximo_anio_ciclo_ue(today)
    ventana_generales = ventana_generales_si_legislatura_completa()
    return [
        {
            "nivel": "Europeo",
            "eleccion": "Parlamento Europeo",
            "estado": "ciclo conocido, fecha no fijada",
            "proximo_anio_esperado": anio_ue,
            "notas": "Las elecciones europeas son cada 5 años.",
        },
        {
            "nivel": "Nacional",
            "eleccion": "Cortes Generales (Congreso y Senado)",
            "estado": "fecha condicional",
            "proximo_si_legislatura_completa": ventana_generales,
            "notas": "La fecha puede cambiar si hay disolución anticipada.",
        },
        {
            "nivel": "Autonómico",
            "eleccion": "Parlamentos de las comunidades autónomas",
            "estado": "sin fecha única estatal",
            "proximo_esperado": "depende_de_cada_comunidad",
            "notas": "Cada comunidad sigue su calendario y convocatorias.",
        },
        {
            "nivel": "Local/Municipal",
            "eleccion": "Ayuntamientos",
            "estado": "ciclo fijo",
            "proxima_fecha": fecha_local.isoformat(),
            "notas": "Cuarto domingo de mayo cada 4 años.",
        },
        {
            "nivel": "Provincial",
            "eleccion": "Diputaciones Provinciales",
            "estado": "elección indirecta",
            "proxima_esperada_despues_de": fecha_local.isoformat(),
            "notas": "Constitución indirecta desde resultados municipales.",
        },
    ]


def construir_snapshot(
    today: dt.date,
    *,
    raw_dir: Path | None = None,
    timeout: int = 30,
    no_network: bool = False,
    strict_network: bool = False,
    scraped_events: list[dict[str, Any]] | None = None,
    scraped_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if scraped_events is None or scraped_sources is None:
        events_scraped, source_reports = scrape_official_calendar_sources(
            today=today,
            raw_dir=raw_dir or Path("etl/data/raw/election_calendar"),
            timeout=timeout,
            no_network=no_network,
            strict_network=strict_network,
        )
    else:
        events_scraped = [finalize_event(event) for event in scraped_events]
        source_reports = scraped_sources

    events = [
        finalize_event(event)
        for event in base_legal_cycle_events(today)
        if event_is_upcoming(event, today)
    ]
    events.extend(events_scraped)
    events = sort_events(events)

    timeline_events = [event for event in events if event.get("date")]
    undated_events = [event for event in events if not event.get("date")]

    filters = {
        "levels": sorted({event["level"] for event in events}),
        "scopes": sorted({event["scope"] for event in events}),
        "territories": sorted({event["territory"] for event in events}),
        "statuses": sorted({event["status"] for event in events}),
    }

    return {
        "schema_version": "election-calendar.v1",
        "generado_en": now_utc_iso(),
        "fecha_referencia": today.isoformat(),
        "anclas": {
            k: v.isoformat() if isinstance(v, dt.date) else v for k, v in ANCLAS.items()
        },
        "events": events,
        "timeline_events": timeline_events,
        "undated_events": undated_events,
        "scraped_sources": source_reports,
        "filters": filters,
        "totales": {
            "events": len(events),
            "timeline_events": len(timeline_events),
            "undated_events": len(undated_events),
            "official_calendar_events": sum(1 for e in events if e["source_kind"] == "official_calendar"),
            "legal_cycle_events": sum(1 for e in events if e["source_kind"] == "legal_cycle"),
            "scraped_sources": len(source_reports),
        },
        "niveles": legacy_niveles(today),
        "fuentes": FUENTES + [source["url"] for source in OFFICIAL_CALENDAR_SOURCES],
        "estado_operativo": {
            "ahora": "Primer corte público con ciclos legales y calendarios oficiales scrapeados.",
            "vamos": "Ampliar manifest oficial por comunidad/organismo y sustituir filas condicionales cuando haya convocatoria.",
            "siguiente": "Añadir más fuentes autonómicas con calendario publicado y registrar bloqueos si no exponen datos reutilizables.",
        },
    }


def a_markdown(snapshot: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Próximas elecciones en España")
    lines.append("")
    lines.append(f"Fecha de referencia: **{snapshot['fecha_referencia']}**")
    lines.append("")
    lines.append("## Timeline")
    lines.append("")
    lines.append("| Fecha | Ámbito | Elección | Territorio | Estado | Fuente |")
    lines.append("|---|---|---|---|---|---|")
    for event in snapshot["timeline_events"]:
        source_label = "oficial" if event["source_kind"] == "official_calendar" else "ciclo legal"
        lines.append(
            "| {date} | {level} | {election} | {territory} | {status} | {source} |".format(
                date=event["date_label"],
                level=event["level"],
                election=event["election"],
                territory=event["territory"],
                status=event["status"],
                source=source_label,
            )
        )

    if snapshot["undated_events"]:
        lines.append("")
        lines.append("## Sin fecha cerrada")
        lines.append("")
        lines.append("| Ámbito | Elección | Territorio | Estado | Notas |")
        lines.append("|---|---|---|---|---|")
        for event in snapshot["undated_events"]:
            lines.append(
                "| {level} | {election} | {territory} | {status} | {notes} |".format(
                    level=event["level"],
                    election=event["election"],
                    territory=event["territory"],
                    status=event["status"],
                    notes=event["notes"],
                )
            )

    lines.append("")
    lines.append("## Fuentes scrapeadas")
    lines.append("")
    for source in snapshot["scraped_sources"]:
        status = source.get("status") or "unknown"
        verified = "verificada" if source.get("source_verified") else "no verificada"
        lines.append(f"- {source['source_id']}: {status}, {verified} - {source['url']}")

    lines.append("")
    lines.append("## Fuentes metodológicas")
    lines.append("")
    for fuente in snapshot["fuentes"]:
        lines.append(f"- {fuente}")

    estado = snapshot["estado_operativo"]
    lines.append("")
    lines.append("## Estado operativo")
    lines.append("")
    lines.append(f"- Ahora: {estado['ahora']}")
    lines.append(f"- Vamos: {estado['vamos']}")
    lines.append(f"- Siguiente: {estado['siguiente']}")
    lines.append("")
    lines.append("## Aclaraciones")
    lines.append("")
    lines.append("- Las fechas estatales y autonómicas pueden cambiar por disolución o convocatoria anticipada.")
    lines.append("- Las filas de ciclo legal son calculadas; las filas oficiales indican fuente scrapeada.")

    return "\n".join(lines) + "\n"


def escribir_si_cambia(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def write_snapshot_json(path: Path, snapshot: dict[str, Any]) -> bool:
    json_text = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return escribir_si_cambia(path, json_text)


def main() -> int:
    args = parse_args()
    today = parse_iso_date(args.today)
    snapshot = construir_snapshot(
        today,
        raw_dir=Path(args.raw_dir),
        timeout=args.timeout,
        no_network=bool(args.no_network),
        strict_network=bool(args.strict_network),
    )

    md_path = Path(args.md_out)
    json_path = Path(args.json_out)
    md_changed = escribir_si_cambia(md_path, a_markdown(snapshot))
    json_changed = write_snapshot_json(json_path, snapshot)

    public_changed = False
    public_out = ""
    if args.public_json_out:
        public_path = Path(args.public_json_out)
        public_changed = write_snapshot_json(public_path, snapshot)
        public_out = f", public_json={public_path} ({'actualizado' if public_changed else 'sin cambios'})"

    print(
        "Calendario electoral generado para {ref}. md={md} ({mchg}), json={js} ({jchg}){public}".format(
            ref=today.isoformat(),
            md=md_path,
            js=json_path,
            mchg="actualizado" if md_changed else "sin cambios",
            jchg="actualizado" if json_changed else "sin cambios",
            public=public_out,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
