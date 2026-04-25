#!/usr/bin/env python3
"""Export static benchmark cases for /responsibility-explainer/.

This slice is intentionally conservative. It does not claim to solve a full
public-failure case. It publishes:

- the accountability questions the product should eventually answer,
- the official parliamentary evidence already present in the repo,
- and the explicit gaps that still block full attribution.
"""

from __future__ import annotations

import argparse
import copy
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path("etl/data/staging/parlamentario-es.db")
DEFAULT_OUT_DIR = Path("ui/gh-pages-next/public/responsibility-explainer/data")
DEFAULT_CASE_SEED = Path("etl/data/seeds/responsibility_explainer_cases_seed_v1.json")
DEFAULT_SITE_ORIGIN = "https://gsusI.github.io"
DEFAULT_BASE_PATH = "/vota-con-la-chola"

DANA_CASE = {
    "case_id": "dana-valencia-2024",
    "title": "DANA Valencia 2024",
    "short_label": "DANA Valencia 2024",
    "summary": (
        "Benchmark de accountability para una catastrofe publica: que avisos existieron, "
        "quien tenia deber de actuar, que decisiones u omisiones precedieron el dano, "
        "y que respuesta normativa y parlamentaria quedo documentada."
    ),
    "current_scope_note": (
        "Este slice cubre evidencia parlamentaria ya cargada, anclajes oficiales de deber/competencia "
        "y una primera capa de exposicion regulatoria pre-desastre con blancos concretos de auditoria, "
        "todos normalizados bajo control del repo. No demuestra por si solo causalidad ni reconstruye "
        "todavia la cadena operativa completa."
    ),
    "geography": "Comunitat Valenciana",
    "incident_window": {
        "label": "Octubre-noviembre 2024",
        "start_date": "2024-10-28",
        "end_date": "2024-11-04",
    },
    "initiative_ids": [
        "congreso:leg15:exp:121/000039/0000",
        "congreso:leg15:exp:121/000042/0000",
        "congreso:leg15:exp:121/000044/0000",
        "congreso:leg15:exp:121/000078/0000",
        "congreso:leg15:exp:122/000148/0000",
        "congreso:leg15:exp:122/000152/0000",
        "congreso:ley:7:2024",
        "congreso:ley:8:2024",
        "congreso:ley:12:2025",
        "senado:leg15:exp:622/000055",
        "senado:leg15:exp:622/000063",
    ],
    "questions": [
        {
            "question_id": "warning_timeline",
            "category": "Avisos",
            "prompt": "Que avisos meteorologicos, hidrologicos y de proteccion civil existieron antes del peor dano?",
            "support_rule": "warning_timeline_events",
            "next_evidence_needed": [
                "normalizar avisos AEMET/CHJ/Proteccion Civil",
                "timeline minuto a minuto de alertas y mensajes publicos",
            ],
        },
        {
            "question_id": "duty_chain",
            "category": "Deber de actuar",
            "prompt": "Que administraciones y cargos tenian la competencia y el deber de alertar, coordinar y evacuar?",
            "support_rule": "normative_duties",
            "next_evidence_needed": [
                "grafo de competencias actor->cargo->plan activado",
                "obligaciones normativas aterrizadas a personas, turnos y centros operativos",
            ],
        },
        {
            "question_id": "structural_exposure",
            "category": "Regulacion y exposicion",
            "prompt": "Que reglas de suelo, agua, licencias y gobernanza pudieron dejar viviendas, infraestructuras y sistemas de alerta mas expuestos al dano?",
            "support_rule": "structural_risk_factors",
            "next_evidence_needed": [
                "cruce de cartografia inundable con planeamiento y licencias",
                "trazabilidad de quien aprobo, informo o tolero usos vulnerables",
            ],
        },
        {
            "question_id": "operational_decisions",
            "category": "Decisiones u omisiones",
            "prompt": "Que decisiones operativas se tomaron, cuales se retrasaron y cuales no ocurrieron cuando debian?",
            "support_rule": "missing",
            "next_evidence_needed": [
                "actas, ordenes y cronologia operativa",
                "comparecencias y transcripciones oficiales de la gestion de la emergencia",
            ],
        },
        {
            "question_id": "parliamentary_response",
            "category": "Respuesta institucional",
            "prompt": "Que medidas normativas y parlamentarias se adoptaron despues de la DANA?",
            "support_rule": "parliamentary_response",
            "next_evidence_needed": [
                "seguir tramitacion completa de los expedientes ligados a la DANA",
            ],
        },
        {
            "question_id": "parliamentary_votes",
            "category": "Rastro legislativo",
            "prompt": "Que votos formales quedaron enlazados a esas medidas y como se resolvieron?",
            "support_rule": "parliamentary_votes",
            "next_evidence_needed": [
                "mejorar enlaces voto->iniciativa para expedientes todavia sin voto asociado",
            ],
        },
        {
            "question_id": "reviewed_measures",
            "category": "Cambios concretos",
            "prompt": "Que cambios concretos y citizen-facing ya se pueden explicar a partir del texto oficial revisado?",
            "support_rule": "reviewed_measures",
            "next_evidence_needed": [
                "ampliar revision humana de medidas DANA y paquetes de reconstruccion",
            ],
        },
        {
            "question_id": "harm_attribution",
            "category": "Atribucion de dano",
            "prompt": "Que parte del dano prevenible puede atribuirse a fallos normativos, de coordinacion o de decision?",
            "support_rule": "missing",
            "next_evidence_needed": [
                "outcomes de victimas y afectacion territorial",
                "cadena causal con hallazgos administrativos y judiciales",
            ],
        },
    ],
    "known_gaps": [
        "No hay todavia una cronologia normalizada de avisos AEMET/CHJ/Proteccion Civil.",
        "No hay aun un grafo de competencias de emergencia que cierre personas concretas, turnos y organos operativos durante la DANA.",
        "No hay todavia cruce reproducible entre cartografia inundable, planeamiento urbanistico, licencias y ocupacion real del territorio.",
        "No hay todavia expedientes municipales, sectoriales o hidraulicos enlazados fila a fila a los blancos de auditoria ya publicados.",
        "No hay actas operativas, ordenes internas ni decisiones de mando enlazadas como evidencia estructurada.",
        "No hay todavia hallazgos judiciales o administrativos integrados en un caso trazable.",
    ],
    "next_lanes": [
        "captura sistematica de PGOU, licencias y expedientes por municipio prioritario",
        "cruce de planeamiento, licencias y zonas inundables",
        "modelo de competencia y deber de actuar para emergencias",
        "timeline de avisos y decisiones con fuentes primarias",
        "normalizacion de comparecencias/comisiones de investigacion",
        "enlace entre decisiones, outcomes y evidencia de dano",
    ],
}

CASH_PAYMENT_LIMIT_CASE = {
    "case_id": "cash-payment-limit-spain",
    "title": "Limite de pagos en efectivo en Espana",
    "short_label": "Pagos en efectivo 1.000 EUR",
    "summary": (
        "Benchmark P2 para una regla formal estatal: que norma fija el limite general de pagos "
        "en efectivo a 1.000 euros, quien la cambia, quien la promulga y quien la aplica hoy."
    ),
    "current_scope_note": (
        "Este slice cubre el ledger formal minimo para la regla vigente: normas de base, "
        "lectura oficial publicada por la AEAT, el acto legal que rebajo el limite de 2.500 a "
        "1.000 euros y la cadena basica aprobacion->promulgacion->aplicacion. No cubre todavia "
        "estadisticas de sancion, versionado parlamentario completo ni el grafo competencial de "
        "quien puede cambiar hoy la regla."
    ),
    "named_accountability": [
        {
            "actor_id": "gobierno-autor-proyecto-ley-121-000033",
            "actor_label": "Gobierno de Espana",
            "actor_type": "institution",
            "role": "Autor del proyecto de ley",
            "responsibility_summary": (
                "El expediente 121/000033 identifica al Gobierno como autor del proyecto que termino "
                "en la Ley 11/2021."
            ),
            "source_title": "Congreso de los Diputados - expediente 121/000033",
            "source_url": "https://www.congreso.es/es/web/guest/proyectos-de-ley?_iniciativas_id=121/000033&_iniciativas_legislatura=XIV&_iniciativas_mode=mostrarDetalle&p_p_id=iniciativas&p_p_lifecycle=0&p_p_mode=view&p_p_state=normal",
            "source_locator": "Autor: Gobierno; presentado el 14/10/2020",
            "source_note": "Responsabilidad gubernamental de iniciativa legislativa, no voto individual.",
        },
        {
            "actor_id": "maria-jesus-montero-cash-limit",
            "actor_label": "Maria Jesus Montero Cuadrado",
            "actor_type": "person",
            "role": "Ministra de Hacienda y portavoz del Gobierno",
            "responsibility_summary": (
                "Presento publicamente la medida en Consejo de Ministros: bajar el limite de pagos "
                "en efectivo de 2.500 a 1.000 euros para operaciones entre profesionales o empresarios."
            ),
            "source_title": "La Moncloa - Intervencion de Maria Jesus Montero",
            "source_url": "https://www.lamoncloa.gob.es/consejodeministros/Paginas/EnlaceTranscripciones2020/131020-portavoz.aspx",
            "source_locator": "13/10/2020; anteproyecto de Ley contra el fraude fiscal",
            "source_note": "El voto nominal del Congreso tambien la lista con voto si el 30/06/2021.",
        },
        {
            "actor_id": "pedro-sanchez-promulgation-countersign",
            "actor_label": "Pedro Sanchez Perez-Castejon",
            "actor_type": "person",
            "role": "Presidente del Gobierno",
            "responsibility_summary": (
                "Figura en el BOE como Presidente del Gobierno que firma la ley publicada el 9 de julio "
                "de 2021; el voto nominal del Congreso tambien lo lista con voto si."
            ),
            "source_title": "BOE-A-2021-11473 - Ley 11/2021",
            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2021-11473",
            "source_locator": "firma final de la ley; Madrid, 9 de julio de 2021",
            "source_note": "Firma gubernamental de promulgacion/publicacion.",
        },
        {
            "actor_id": "felipe-vi-sanction-promulgation",
            "actor_label": "Felipe VI",
            "actor_type": "formal_head_of_state",
            "role": "Jefatura del Estado",
            "responsibility_summary": (
                "Sanciona y manda guardar la Ley 11/2021 en la formula final del BOE."
            ),
            "source_title": "BOE-A-2021-11473 - Ley 11/2021",
            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2021-11473",
            "source_locator": "formula final: Felipe R.",
            "source_note": "Actor formal de promulgacion; no es un cargo de partido.",
        },
        {
            "actor_id": "congreso-hacienda-ponentes-121-000033",
            "actor_label": "Ponentes del Congreso en la Comision de Hacienda",
            "actor_type": "named_group",
            "role": "Ponencia parlamentaria del proyecto",
            "responsibility_summary": (
                "El Congreso identifica por nombre a los ponentes que trabajaron el expediente antes de "
                "la aprobacion con competencia legislativa plena."
            ),
            "person_names": [
                "Javier Bas Corugeira",
                "Ferran Bel Accensi",
                "Patricia Blanquer Alcaraz",
                "Carolina Espana Reina",
                "Jose Maria Figaredo Alvarez-Sala",
                "Juan Bernardo Fuentes Curbelo",
                "Txema Guijarro Garcia",
                "Rodrigo Jimenez Revuelta",
                "Laura Lopez Dominguez",
                "Joan Margall Sastre",
                "Maria Carmen Martinez Granados",
                "Oskar Matute Garcia de Jalon",
                "Jose Maria Mazon Ramos",
                "Montse Minguez Garcia",
                "Idoia Sagastizabal Unzetabarrenetxea",
            ],
            "source_title": "Congreso de los Diputados - expediente 121/000033",
            "source_url": "https://www.congreso.es/es/web/guest/proyectos-de-ley?_iniciativas_id=121/000033&_iniciativas_legislatura=XIV&_iniciativas_mode=mostrarDetalle&p_p_id=iniciativas&p_p_lifecycle=0&p_p_mode=view&p_p_state=normal",
            "source_locator": "Ponentes del proyecto",
            "source_note": "Nombres oficiales del expediente parlamentario.",
        },
        {
            "actor_id": "congreso-final-rollcall-2021-06-30",
            "actor_label": "Voto nominal del Congreso del 30/06/2021",
            "actor_type": "roll_call",
            "role": "Votacion plenaria final sobre enmiendas del Senado",
            "responsibility_summary": (
                "La votacion nominal oficial permite ver cada diputado por nombre y sentido de voto: "
                "277 si, 51 no, 4 abstenciones y 18 no votan en el bloque 'Resto de enmiendas'."
            ),
            "source_title": "Congreso - VOT_20210630175720.pdf",
            "source_url": "https://www.congreso.es/webpublica/opendata/votaciones/Leg14/Sesion112/20210630/Votacion005/VOT_20210630175720.pdf",
            "source_locator": "Sesion 112, votacion 5, 30/06/2021",
            "source_note": "Lista nominal completa; no aisla por si sola el articulo 18 de pagos en efectivo.",
        },
    ],
    "geography": "Espana",
    "incident_window": {
        "label": "Desde 11 julio 2021",
        "start_date": "2021-07-11",
        "end_date": "",
    },
    "initiative_ids": [],
    "questions": [
        {
            "question_id": "formal_rule",
            "category": "Regla formal",
            "prompt": "Que norma fija hoy el limite general de pagos en efectivo a 1.000 euros y desde cuando aplica?",
            "support_rule": "governing_rules",
            "next_evidence_needed": [
                "versionado historico 2012->2021 del articulo 7",
                "dossier parlamentario enlazado a la reforma de 2021",
            ],
        },
        {
            "question_id": "formal_enforcement_chain",
            "category": "Cadena formal",
            "prompt": "Que organos aprueban, promulgan y aplican formalmente esta limitacion?",
            "support_rule": "responsibility_links",
            "next_evidence_needed": [
                "grafo competencial Ministerio/AEAT/BOE con organo concreto",
            ],
        },
        {
            "question_id": "sanction_mechanics",
            "category": "Aplicacion administrativa",
            "prompt": "Como entra en juego administrativamente: denuncia, tramitacion, resolucion y recaudacion de sanciones?",
            "support_rule": "administrative_acts",
            "next_evidence_needed": [
                "resoluciones, manuales operativos o estadisticas de tramitacion",
            ],
        },
        {
            "question_id": "official_interpretation",
            "category": "Lectura oficial",
            "prompt": "Que lectura oficial delimita cuando aplica el limite y por que se rebajo de 2.500 a 1.000 euros?",
            "support_rule": "official_findings",
            "next_evidence_needed": [
                "FAQs oficiales y criterios interpretativos por supuestos frontera",
            ],
        },
        {
            "question_id": "who_can_change_now",
            "category": "Quien puede cambiarlo hoy",
            "prompt": "Que institucion o nivel de gobierno puede elevar, bajar o excepcionar hoy este limite?",
            "support_rule": "missing",
            "next_evidence_needed": [
                "grafo competencial Cortes/Gobierno/Ministerio y, si aplica, marco UE",
            ],
        },
        {
            "question_id": "real_enforcement",
            "category": "Aplicacion real",
            "prompt": "Con que intensidad se inspecciona y sanciona realmente este limite en la practica?",
            "support_rule": "missing",
            "next_evidence_needed": [
                "estadisticas de expedientes, resoluciones y recaudacion por ejercicio",
            ],
        },
    ],
    "known_gaps": [
        "No hay todavia estadisticas publicadas integradas de expedientes, sanciones firmes o recaudacion por esta infraccion.",
        "No hay aun un grafo competencial completo que cierre quien puede modificar hoy la regla y por que instrumento.",
        "No hay todavia el dossier parlamentario completo de la reforma de 2021 enlazado dentro del caso.",
        "No hay todavia criterios oficiales agregados para todos los supuestos frontera de aplicacion.",
    ],
    "next_lanes": [
        "ingesta BOE y rastro parlamentario de la reforma de 2021",
        "grafo de competencia Ministerio de Hacienda / AEAT / Cortes Generales",
        "estadisticas y resoluciones de enforcement si el upstream las publica",
        "ampliar a otras reglas formales de trazabilidad financiera o fiscal",
    ],
}

CASE_DEFS = [DANA_CASE, CASH_PAYMENT_LIMIT_CASE]


def case_defs_by_id() -> dict[str, dict[str, Any]]:
    return {safe_text(case_def.get("case_id")): case_def for case_def in CASE_DEFS if safe_text(case_def.get("case_id"))}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta benchmarks estaticos para /responsibility-explainer/")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la SQLite base del benchmark")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Directorio de salida JSON")
    p.add_argument("--seed", default=str(DEFAULT_CASE_SEED), help="JSON con evidencia seed por caso")
    p.add_argument("--site-origin", default=DEFAULT_SITE_ORIGIN, help="Origen publico del sitio")
    p.add_argument("--base-path", default=DEFAULT_BASE_PATH, help="Base path publico")
    p.add_argument("--max-initiatives", type=int, default=12, help="Maximo de iniciativas destacadas por caso")
    p.add_argument("--max-votes", type=int, default=12, help="Maximo de votos destacados por caso")
    p.add_argument("--max-measures", type=int, default=12, help="Maximo de medidas revisadas por caso")
    return p.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def parse_json_list(value: Any) -> list[Any]:
    text = safe_text(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def clean_text_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [safe_text(item) for item in items if safe_text(item)]


def clean_question_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": safe_text(row.get("question_id")),
        "category": safe_text(row.get("category")),
        "prompt": safe_text(row.get("prompt")),
        "support_rule": safe_text(row.get("support_rule")),
        "next_evidence_needed": clean_text_list(row.get("next_evidence_needed")),
    }


def merge_case_def(base_case_def: dict[str, Any] | None, case_seed: dict[str, Any] | None) -> dict[str, Any]:
    out = copy.deepcopy(base_case_def or {})
    if isinstance(case_seed, dict):
        case_id = safe_text(case_seed.get("case_id"))
        if case_id:
            out["case_id"] = case_id
        for key in ("title", "short_label", "summary", "current_scope_note", "geography"):
            value = safe_text(case_seed.get(key))
            if value:
                out[key] = value
        for key in ("initiative_ids", "known_gaps", "next_lanes"):
            values = clean_text_list(case_seed.get(key))
            if values:
                out[key] = values
        incident_window = case_seed.get("incident_window")
        if isinstance(incident_window, dict):
            merged_incident = copy.deepcopy(out.get("incident_window") or {})
            for key in ("label", "start_date", "end_date"):
                value = safe_text(incident_window.get(key))
                if value:
                    merged_incident[key] = value
            if merged_incident:
                out["incident_window"] = merged_incident
        raw_questions = case_seed.get("questions")
        if isinstance(raw_questions, list):
            questions = [
                clean_question_row(row)
                for row in raw_questions
                if isinstance(row, dict) and safe_text(row.get("question_id")) and safe_text(row.get("prompt"))
            ]
            if questions:
                out["questions"] = questions
        raw_named_accountability = case_seed.get("named_accountability")
        if isinstance(raw_named_accountability, list):
            named_accountability = clean_named_accountability_rows(raw_named_accountability)
            if named_accountability:
                out["named_accountability"] = named_accountability
    return out


def load_case_seed_map(seed_path: Path) -> dict[str, dict[str, Any]]:
    if not seed_path.exists():
        return {}
    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw_cases = payload.get("cases") if isinstance(payload, dict) else []
    if not isinstance(raw_cases, list):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for item in raw_cases:
        if not isinstance(item, dict):
            continue
        case_id = safe_text(item.get("case_id"))
        if not case_id:
            continue
        out[case_id] = item
    return out


def load_seed_rows(case_seed: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(case_seed, dict):
        return []
    raw_rows = case_seed.get(key)
    if not isinstance(raw_rows, list):
        return []
    return [row for row in raw_rows if isinstance(row, dict)]


def clean_seed_row(row: dict[str, Any], allowed_keys: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in allowed_keys:
        value = row.get(key)
        if isinstance(value, list):
            out[key] = [safe_text(item) for item in value if safe_text(item)]
        else:
            out[key] = safe_text(value)
    return out


def clean_named_accountability_rows(rows: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cleaned = clean_seed_row(
            row,
            (
                "actor_id",
                "actor_label",
                "actor_type",
                "role",
                "responsibility_summary",
                "person_names",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        if not isinstance(cleaned.get("person_names"), list):
            cleaned["person_names"] = []
        if safe_text(cleaned.get("actor_id")) or safe_text(cleaned.get("actor_label")):
            out.append(cleaned)
    return out


def load_normative_duties(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "normative_duties")
    return [
        clean_seed_row(
            row,
            (
                "duty_id",
                "category",
                "actor",
                "actor_scope",
                "duty_summary",
                "why_it_matters",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("duty_id")) or safe_text(row.get("actor")) or safe_text(row.get("duty_summary"))
    ]


def load_warning_channels(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "warning_channels")
    return [
        clean_seed_row(
            row,
            (
                "channel_id",
                "channel_name",
                "operator",
                "scope",
                "signal_summary",
                "why_next",
                "source_title",
                "source_url",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("channel_id")) or safe_text(row.get("channel_name")) or safe_text(row.get("signal_summary"))
    ]


def load_warning_timeline_events(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "warning_timeline_events")
    return [
        clean_seed_row(
            row,
            (
                "event_id",
                "channel_id",
                "channel_name",
                "operator",
                "event_time",
                "event_precision",
                "signal_level",
                "event_summary",
                "why_it_matters",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("event_id")) or safe_text(row.get("event_time")) or safe_text(row.get("event_summary"))
    ]


def load_governing_rules(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "governing_rules")
    return [
        clean_seed_row(
            row,
            (
                "rule_id",
                "rule_kind",
                "title",
                "duty_summary",
                "exposure_mechanism",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("rule_id")) or safe_text(row.get("title")) or safe_text(row.get("duty_summary"))
    ]


def load_official_findings(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "official_findings")
    return [
        clean_seed_row(
            row,
            (
                "finding_id",
                "category",
                "entity_name",
                "finding_date",
                "finding_summary",
                "accountability_implication",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("finding_id")) or safe_text(row.get("entity_name")) or safe_text(row.get("finding_summary"))
    ]


def load_administrative_acts(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "administrative_acts")
    return [
        clean_seed_row(
            row,
            (
                "act_id",
                "act_type",
                "entity_name",
                "act_date",
                "status",
                "act_summary",
                "accountability_implication",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("act_id")) or safe_text(row.get("entity_name")) or safe_text(row.get("act_summary"))
    ]


def load_responsibility_links(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "responsibility_links")
    return [
        clean_seed_row(
            row,
            (
                "link_id",
                "actor",
                "actor_scope",
                "linked_object_type",
                "linked_object_id",
                "role_in_chain",
                "obligation_basis",
                "accountability_question",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("link_id")) or safe_text(row.get("actor")) or safe_text(row.get("role_in_chain"))
    ]


def load_structural_risk_factors(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "structural_risk_factors")
    return [
        clean_seed_row(
            row,
            (
                "factor_id",
                "category",
                "title",
                "risk_mechanism",
                "accountability_focus",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("factor_id")) or safe_text(row.get("title")) or safe_text(row.get("risk_mechanism"))
    ]


def load_structural_audit_targets(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "structural_audit_targets")
    return [
        clean_seed_row(
            row,
            (
                "target_id",
                "category",
                "title",
                "geography",
                "why_priority",
                "audit_question",
                "documents_to_audit",
                "authority_chain",
                "next_join_needed",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("target_id")) or safe_text(row.get("title")) or safe_text(row.get("audit_question"))
    ]


def load_structural_evidence_rows(case_seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = load_seed_rows(case_seed, "structural_evidence_rows")
    return [
        clean_seed_row(
            row,
            (
                "evidence_id",
                "target_id",
                "entity_name",
                "signal_type",
                "certainty",
                "signal_title",
                "pre_dana_reading",
                "why_it_matters",
                "source_title",
                "source_url",
                "source_locator",
                "source_note",
            ),
        )
        for row in rows
        if safe_text(row.get("evidence_id")) or safe_text(row.get("entity_name")) or safe_text(row.get("signal_title"))
    ]


def load_case_defs_from_db(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not table_exists(conn, "responsibility_explainer_cases"):
        return []
    case_rows = conn.execute(
        """
        SELECT
          case_id,
          title,
          short_label,
          summary,
          current_scope_note,
          geography,
          incident_window_label,
          incident_start_date,
          incident_end_date,
          initiative_ids_json,
          known_gaps_json,
          next_lanes_json
        FROM responsibility_explainer_cases
        WHERE is_active = 1
        ORDER BY sort_order ASC, case_id ASC
        """
    ).fetchall()
    if not case_rows:
        return []

    builtin_cases = case_defs_by_id()
    questions_by_case: dict[str, list[dict[str, Any]]] = {}
    if table_exists(conn, "responsibility_explainer_questions"):
        question_rows = conn.execute(
            """
            SELECT
              case_id,
              question_id,
              category,
              prompt,
              support_rule,
              next_evidence_needed_json
            FROM responsibility_explainer_questions
            ORDER BY case_id ASC, question_order ASC, question_id ASC
            """
        ).fetchall()
        for row in question_rows:
            case_id = safe_text(row["case_id"])
            if not case_id:
                continue
            questions_by_case.setdefault(case_id, []).append(
                {
                    "question_id": safe_text(row["question_id"]),
                    "category": safe_text(row["category"]),
                    "prompt": safe_text(row["prompt"]),
                    "support_rule": safe_text(row["support_rule"]),
                    "next_evidence_needed": clean_text_list(parse_json_list(row["next_evidence_needed_json"])),
                }
            )

    out: list[dict[str, Any]] = []
    for row in case_rows:
        case_id = safe_text(row["case_id"])
        if not case_id:
            continue
        base_case_def = builtin_cases.get(case_id)
        case_def = merge_case_def(
            base_case_def,
            {
                "case_id": case_id,
                "title": safe_text(row["title"]),
                "short_label": safe_text(row["short_label"]),
                "summary": safe_text(row["summary"]),
                "current_scope_note": safe_text(row["current_scope_note"]),
                "geography": safe_text(row["geography"]),
                "incident_window": {
                    "label": safe_text(row["incident_window_label"]),
                    "start_date": safe_text(row["incident_start_date"]),
                    "end_date": safe_text(row["incident_end_date"]),
                },
                "initiative_ids": clean_text_list(parse_json_list(row["initiative_ids_json"])),
                "known_gaps": clean_text_list(parse_json_list(row["known_gaps_json"])),
                "next_lanes": clean_text_list(parse_json_list(row["next_lanes_json"])),
            },
        )
        if questions_by_case.get(case_id):
            case_def["questions"] = questions_by_case[case_id]
        if safe_text(case_def.get("case_id")) and safe_text(case_def.get("title")):
            out.append(case_def)
    return out


def load_normative_duties_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_normative_duties"):
        rows = conn.execute(
            """
            SELECT
              duty_id,
              category,
              actor,
              actor_scope,
              duty_summary,
              why_it_matters,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_normative_duties
            WHERE case_id = ?
            ORDER BY duty_order ASC, duty_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "duty_id": safe_text(row["duty_id"]),
                    "category": safe_text(row["category"]),
                    "actor": safe_text(row["actor"]),
                    "actor_scope": safe_text(row["actor_scope"]),
                    "duty_summary": safe_text(row["duty_summary"]),
                    "why_it_matters": safe_text(row["why_it_matters"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_normative_duties(case_seed)


def load_warning_channels_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_warning_channels"):
        rows = conn.execute(
            """
            SELECT
              channel_id,
              channel_name,
              operator,
              scope,
              signal_summary,
              why_next,
              source_title,
              source_url,
              source_note
            FROM responsibility_explainer_warning_channels
            WHERE case_id = ?
            ORDER BY channel_order ASC, channel_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "channel_id": safe_text(row["channel_id"]),
                    "channel_name": safe_text(row["channel_name"]),
                    "operator": safe_text(row["operator"]),
                    "scope": safe_text(row["scope"]),
                    "signal_summary": safe_text(row["signal_summary"]),
                    "why_next": safe_text(row["why_next"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_warning_channels(case_seed)


def load_warning_timeline_events_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_warning_timeline_events"):
        rows = conn.execute(
            """
            SELECT
              event_id,
              channel_id,
              channel_name,
              operator,
              event_time,
              event_precision,
              signal_level,
              event_summary,
              why_it_matters,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_warning_timeline_events
            WHERE case_id = ?
            ORDER BY event_order ASC, event_time ASC, event_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "event_id": safe_text(row["event_id"]),
                    "channel_id": safe_text(row["channel_id"]),
                    "channel_name": safe_text(row["channel_name"]),
                    "operator": safe_text(row["operator"]),
                    "event_time": safe_text(row["event_time"]),
                    "event_precision": safe_text(row["event_precision"]),
                    "signal_level": safe_text(row["signal_level"]),
                    "event_summary": safe_text(row["event_summary"]),
                    "why_it_matters": safe_text(row["why_it_matters"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_warning_timeline_events(case_seed)


def load_governing_rules_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_governing_rules"):
        rows = conn.execute(
            """
            SELECT
              rule_id,
              rule_kind,
              title,
              duty_summary,
              exposure_mechanism,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_governing_rules
            WHERE case_id = ?
            ORDER BY rule_order ASC, rule_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "rule_id": safe_text(row["rule_id"]),
                    "rule_kind": safe_text(row["rule_kind"]),
                    "title": safe_text(row["title"]),
                    "duty_summary": safe_text(row["duty_summary"]),
                    "exposure_mechanism": safe_text(row["exposure_mechanism"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_governing_rules(case_seed)


def load_official_findings_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_official_findings"):
        rows = conn.execute(
            """
            SELECT
              finding_id,
              category,
              entity_name,
              finding_date,
              finding_summary,
              accountability_implication,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_official_findings
            WHERE case_id = ?
            ORDER BY finding_order ASC, finding_date ASC, finding_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "finding_id": safe_text(row["finding_id"]),
                    "category": safe_text(row["category"]),
                    "entity_name": safe_text(row["entity_name"]),
                    "finding_date": safe_text(row["finding_date"]),
                    "finding_summary": safe_text(row["finding_summary"]),
                    "accountability_implication": safe_text(row["accountability_implication"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_official_findings(case_seed)


def load_administrative_acts_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_administrative_acts"):
        rows = conn.execute(
            """
            SELECT
              act_id,
              act_type,
              entity_name,
              act_date,
              status,
              act_summary,
              accountability_implication,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_administrative_acts
            WHERE case_id = ?
            ORDER BY act_order ASC, act_date ASC, act_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "act_id": safe_text(row["act_id"]),
                    "act_type": safe_text(row["act_type"]),
                    "entity_name": safe_text(row["entity_name"]),
                    "act_date": safe_text(row["act_date"]),
                    "status": safe_text(row["status"]),
                    "act_summary": safe_text(row["act_summary"]),
                    "accountability_implication": safe_text(row["accountability_implication"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_administrative_acts(case_seed)


def load_responsibility_links_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_responsibility_links"):
        rows = conn.execute(
            """
            SELECT
              link_id,
              actor,
              actor_scope,
              linked_object_type,
              linked_object_id,
              role_in_chain,
              obligation_basis,
              accountability_question,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_responsibility_links
            WHERE case_id = ?
            ORDER BY link_order ASC, link_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "link_id": safe_text(row["link_id"]),
                    "actor": safe_text(row["actor"]),
                    "actor_scope": safe_text(row["actor_scope"]),
                    "linked_object_type": safe_text(row["linked_object_type"]),
                    "linked_object_id": safe_text(row["linked_object_id"]),
                    "role_in_chain": safe_text(row["role_in_chain"]),
                    "obligation_basis": safe_text(row["obligation_basis"]),
                    "accountability_question": safe_text(row["accountability_question"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_responsibility_links(case_seed)


def load_structural_risk_factors_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_structural_risk_factors"):
        rows = conn.execute(
            """
            SELECT
              factor_id,
              category,
              title,
              risk_mechanism,
              accountability_focus,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_structural_risk_factors
            WHERE case_id = ?
            ORDER BY factor_order ASC, factor_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "factor_id": safe_text(row["factor_id"]),
                    "category": safe_text(row["category"]),
                    "title": safe_text(row["title"]),
                    "risk_mechanism": safe_text(row["risk_mechanism"]),
                    "accountability_focus": safe_text(row["accountability_focus"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_structural_risk_factors(case_seed)


def load_structural_audit_targets_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_structural_audit_targets"):
        rows = conn.execute(
            """
            SELECT
              target_id,
              category,
              title,
              geography,
              why_priority,
              audit_question,
              documents_to_audit_json,
              authority_chain,
              next_join_needed,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_structural_audit_targets
            WHERE case_id = ?
            ORDER BY target_order ASC, target_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "target_id": safe_text(row["target_id"]),
                    "category": safe_text(row["category"]),
                    "title": safe_text(row["title"]),
                    "geography": safe_text(row["geography"]),
                    "why_priority": safe_text(row["why_priority"]),
                    "audit_question": safe_text(row["audit_question"]),
                    "documents_to_audit": clean_text_list(parse_json_list(row["documents_to_audit_json"])),
                    "authority_chain": safe_text(row["authority_chain"]),
                    "next_join_needed": safe_text(row["next_join_needed"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_structural_audit_targets(case_seed)


def load_structural_evidence_rows_for_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    case_seed: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if table_exists(conn, "responsibility_explainer_structural_evidence_rows"):
        rows = conn.execute(
            """
            SELECT
              evidence_id,
              target_id,
              entity_name,
              signal_type,
              certainty,
              signal_title,
              pre_dana_reading,
              why_it_matters,
              source_title,
              source_url,
              source_locator,
              source_note
            FROM responsibility_explainer_structural_evidence_rows
            WHERE case_id = ?
            ORDER BY evidence_order ASC, evidence_id ASC
            """,
            (case_id,),
        ).fetchall()
        if rows:
            return [
                {
                    "evidence_id": safe_text(row["evidence_id"]),
                    "target_id": safe_text(row["target_id"]),
                    "entity_name": safe_text(row["entity_name"]),
                    "signal_type": safe_text(row["signal_type"]),
                    "certainty": safe_text(row["certainty"]),
                    "signal_title": safe_text(row["signal_title"]),
                    "pre_dana_reading": safe_text(row["pre_dana_reading"]),
                    "why_it_matters": safe_text(row["why_it_matters"]),
                    "source_title": safe_text(row["source_title"]),
                    "source_url": safe_text(row["source_url"]),
                    "source_locator": safe_text(row["source_locator"]),
                    "source_note": safe_text(row["source_note"]),
                }
                for row in rows
            ]
    return load_structural_evidence_rows(case_seed)


def sanitize_public_label(value: str) -> str:
    raw = safe_text(value)
    if not raw:
        return ""
    path = Path(raw)
    if not path.is_absolute():
        return raw
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def unique_nonempty(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        token = safe_text(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def infer_snapshot_date(conn: sqlite3.Connection) -> str:
    candidates: list[str] = []
    queries = [
        ("parl_initiatives", "SELECT MAX(source_snapshot_date) AS d FROM parl_initiatives"),
        ("parl_vote_events", "SELECT MAX(source_snapshot_date) AS d FROM parl_vote_events"),
        ("parl_initiative_measure_points", "SELECT MAX(substr(updated_at, 1, 10)) AS d FROM parl_initiative_measure_points"),
    ]
    for table_name, sql in queries:
        if not table_exists(conn, table_name):
            continue
        row = conn.execute(sql).fetchone()
        value = safe_text(row["d"] if row else "")
        if value:
            candidates.append(value[:10])
    return max(candidates) if candidates else now_utc_iso()[:10]


def load_initiatives(conn: sqlite3.Connection, case_def: dict[str, Any]) -> list[dict[str, Any]]:
    if not table_exists(conn, "parl_initiatives"):
        return []

    initiative_ids = [safe_text(item) for item in case_def.get("initiative_ids") or [] if safe_text(item)]
    if not initiative_ids:
        return []

    placeholders = ",".join("?" for _ in initiative_ids)
    rows = conn.execute(
        f"""
        SELECT
          initiative_id,
          source_id,
          title,
          type,
          current_status,
          presented_date,
          source_url,
          links_bocg_json,
          links_ds_json
        FROM parl_initiatives
        WHERE initiative_id IN ({placeholders})
        ORDER BY presented_date DESC, initiative_id ASC
        """,
        initiative_ids,
    ).fetchall()

    vote_counts: dict[str, int] = {}
    if table_exists(conn, "parl_vote_event_initiatives"):
        vote_rows = conn.execute(
            f"""
            SELECT initiative_id, COUNT(DISTINCT vote_event_id) AS c
            FROM parl_vote_event_initiatives
            WHERE initiative_id IN ({placeholders})
            GROUP BY initiative_id
            """,
            initiative_ids,
        ).fetchall()
        vote_counts = {safe_text(row["initiative_id"]): int(row["c"] or 0) for row in vote_rows}

    measure_counts: dict[str, int] = {}
    if table_exists(conn, "parl_initiative_measure_points"):
        measure_rows = conn.execute(
            f"""
            SELECT initiative_id, COUNT(*) AS c
            FROM parl_initiative_measure_points
            WHERE initiative_id IN ({placeholders})
            GROUP BY initiative_id
            """,
            initiative_ids,
        ).fetchall()
        measure_counts = {safe_text(row["initiative_id"]): int(row["c"] or 0) for row in measure_rows}

    document_counts: dict[str, int] = {}
    document_links: dict[str, list[str]] = {}
    if table_exists(conn, "parl_initiative_documents"):
        document_rows = conn.execute(
            f"""
            SELECT initiative_id, doc_url
            FROM parl_initiative_documents
            WHERE initiative_id IN ({placeholders})
            ORDER BY initiative_id ASC, doc_kind ASC, doc_url ASC
            """,
            initiative_ids,
        ).fetchall()
        for row in document_rows:
            initiative_id = safe_text(row["initiative_id"])
            document_counts[initiative_id] = int(document_counts.get(initiative_id, 0)) + 1
            document_links.setdefault(initiative_id, []).append(safe_text(row["doc_url"]))

    out: list[dict[str, Any]] = []
    for row in rows:
        initiative_id = safe_text(row["initiative_id"])
        official_links = unique_nonempty(
            [safe_text(row["source_url"])]
            + [safe_text(item) for item in parse_json_list(row["links_bocg_json"])]
            + [safe_text(item) for item in parse_json_list(row["links_ds_json"])]
            + document_links.get(initiative_id, [])
        )
        out.append(
            {
                "initiative_id": initiative_id,
                "source_id": safe_text(row["source_id"]),
                "title": safe_text(row["title"]),
                "type": safe_text(row["type"]),
                "current_status": safe_text(row["current_status"]),
                "presented_date": safe_text(row["presented_date"]),
                "vote_events_count": int(vote_counts.get(initiative_id, 0)),
                "measure_points_count": int(measure_counts.get(initiative_id, 0)),
                "official_documents_count": int(document_counts.get(initiative_id, 0)),
                "official_links": official_links[:6],
            }
        )

    out.sort(
        key=lambda item: (
            -int(item["measure_points_count"]),
            -int(item["vote_events_count"]),
            safe_text(item["presented_date"]),
            safe_text(item["initiative_id"]),
        )
    )
    return out


def load_votes(conn: sqlite3.Connection, initiative_ids: list[str], *, max_votes: int) -> list[dict[str, Any]]:
    if not initiative_ids or not table_exists(conn, "parl_vote_event_initiatives") or not table_exists(conn, "parl_vote_events"):
        return []

    placeholders = ",".join("?" for _ in initiative_ids)
    rows = conn.execute(
        f"""
        SELECT
          e.vote_event_id,
          e.source_id,
          e.vote_date,
          e.title,
          e.totals_yes,
          e.totals_no,
          e.totals_abstain,
          e.totals_present,
          e.source_url,
          l.initiative_id
        FROM parl_vote_event_initiatives l
        JOIN parl_vote_events e ON e.vote_event_id = l.vote_event_id
        WHERE l.initiative_id IN ({placeholders})
        ORDER BY e.vote_date DESC, e.vote_event_id ASC
        LIMIT ?
        """,
        [*initiative_ids, int(max_votes)],
    ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "vote_event_id": safe_text(row["vote_event_id"]),
                "initiative_id": safe_text(row["initiative_id"]),
                "source_id": safe_text(row["source_id"]),
                "vote_date": safe_text(row["vote_date"]),
                "title": safe_text(row["title"]),
                "totals": {
                    "yes": int(row["totals_yes"] or 0),
                    "no": int(row["totals_no"] or 0),
                    "abstain": int(row["totals_abstain"] or 0),
                    "present": int(row["totals_present"] or 0),
                },
                "source_url": safe_text(row["source_url"]),
            }
        )
    return out


def load_measures(conn: sqlite3.Connection, initiative_ids: list[str], *, max_measures: int) -> list[dict[str, Any]]:
    if not initiative_ids or not table_exists(conn, "parl_initiative_measure_points"):
        return []

    placeholders = ",".join("?" for _ in initiative_ids)
    rows = conn.execute(
        f"""
        SELECT
          initiative_id,
          measure_rank,
          measure_title,
          citizen_summary,
          COALESCE(policy_area, '') AS policy_area,
          COALESCE(measure_status, '') AS measure_status,
          COALESCE(primary_vote_event_ids_json, '[]') AS primary_vote_event_ids_json
        FROM parl_initiative_measure_points
        WHERE initiative_id IN ({placeholders})
        ORDER BY initiative_id ASC, measure_rank ASC
        LIMIT ?
        """,
        [*initiative_ids, int(max_measures)],
    ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "initiative_id": safe_text(row["initiative_id"]),
                "measure_rank": int(row["measure_rank"] or 0),
                "measure_title": safe_text(row["measure_title"]),
                "citizen_summary": safe_text(row["citizen_summary"]),
                "policy_area": safe_text(row["policy_area"]),
                "measure_status": safe_text(row["measure_status"]),
                "primary_vote_event_ids": [safe_text(item) for item in parse_json_list(row["primary_vote_event_ids_json"]) if safe_text(item)],
            }
        )
    return out


def derive_question_status(case_def: dict[str, Any], coverage: dict[str, int]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for question in case_def.get("questions") or []:
        rule = safe_text(question.get("support_rule"))
        if rule == "parliamentary_response":
            status = "partial" if int(coverage.get("initiatives_total", 0)) > 0 else "missing"
        elif rule == "parliamentary_votes":
            status = "partial" if int(coverage.get("vote_events_total", 0)) > 0 else "missing"
        elif rule == "reviewed_measures":
            status = "partial" if int(coverage.get("reviewed_measures_total", 0)) > 0 else "missing"
        elif rule == "normative_duties":
            status = "partial" if int(coverage.get("normative_duties_total", 0)) > 0 else "missing"
        elif rule == "warning_timeline_events":
            status = "partial" if int(coverage.get("warning_timeline_events_total", 0)) > 0 else "missing"
        elif rule == "governing_rules":
            status = "partial" if int(coverage.get("governing_rules_total", 0)) > 0 else "missing"
        elif rule == "official_findings":
            status = "partial" if int(coverage.get("official_findings_total", 0)) > 0 else "missing"
        elif rule == "administrative_acts":
            status = "partial" if int(coverage.get("administrative_acts_total", 0)) > 0 else "missing"
        elif rule == "responsibility_links":
            status = "partial" if int(coverage.get("responsibility_links_total", 0)) > 0 else "missing"
        elif rule == "structural_risk_factors":
            status = "partial" if int(coverage.get("structural_risk_factors_total", 0)) > 0 else "missing"
        else:
            status = "missing"

        out.append(
            {
                "question_id": safe_text(question.get("question_id")),
                "category": safe_text(question.get("category")),
                "prompt": safe_text(question.get("prompt")),
                "status": status,
                "status_label": "Parcial" if status == "partial" else "Pendiente",
                "next_evidence_needed": list(question.get("next_evidence_needed") or []),
            }
        )
    return out


def build_case_payload(
    conn: sqlite3.Connection,
    *,
    case_def: dict[str, Any],
    case_seed: dict[str, Any] | None = None,
    snapshot_date: str,
    site_origin: str,
    base_path: str,
    max_initiatives: int,
    max_votes: int,
    max_measures: int,
    db_label: str,
) -> dict[str, Any]:
    resolved_case_def = copy.deepcopy(case_def)
    case_id = safe_text(resolved_case_def.get("case_id"))
    initiatives = load_initiatives(conn, resolved_case_def)[: max(1, int(max_initiatives))]
    initiative_ids = [item["initiative_id"] for item in initiatives]
    votes = load_votes(conn, initiative_ids, max_votes=max_votes)
    measures = load_measures(conn, initiative_ids, max_measures=max_measures)
    normative_duties = load_normative_duties_for_case(conn, case_id=case_id, case_seed=case_seed)
    warning_channels = load_warning_channels_for_case(conn, case_id=case_id, case_seed=case_seed)
    warning_timeline_events = load_warning_timeline_events_for_case(conn, case_id=case_id, case_seed=case_seed)
    governing_rules = load_governing_rules_for_case(conn, case_id=case_id, case_seed=case_seed)
    official_findings = load_official_findings_for_case(conn, case_id=case_id, case_seed=case_seed)
    administrative_acts = load_administrative_acts_for_case(conn, case_id=case_id, case_seed=case_seed)
    responsibility_links = load_responsibility_links_for_case(conn, case_id=case_id, case_seed=case_seed)
    structural_risk_factors = load_structural_risk_factors_for_case(conn, case_id=case_id, case_seed=case_seed)
    structural_audit_targets = load_structural_audit_targets_for_case(conn, case_id=case_id, case_seed=case_seed)
    structural_evidence_rows = load_structural_evidence_rows_for_case(conn, case_id=case_id, case_seed=case_seed)
    named_accountability = clean_named_accountability_rows(resolved_case_def.get("named_accountability") or [])

    coverage = {
        "initiatives_total": len(initiatives),
        "initiatives_with_votes_total": sum(1 for item in initiatives if int(item["vote_events_count"]) > 0),
        "initiatives_with_measure_points_total": sum(1 for item in initiatives if int(item["measure_points_count"]) > 0),
        "vote_events_total": len(votes),
        "reviewed_measures_total": len(measures),
        "official_documents_total": sum(int(item["official_documents_count"]) for item in initiatives),
        "normative_duties_total": len(normative_duties),
        "warning_channels_total": len(warning_channels),
        "warning_timeline_events_total": len(warning_timeline_events),
        "governing_rules_total": len(governing_rules),
        "official_findings_total": len(official_findings),
        "administrative_acts_total": len(administrative_acts),
        "responsibility_links_total": len(responsibility_links),
        "named_accountability_total": len(named_accountability),
        "structural_risk_factors_total": len(structural_risk_factors),
        "structural_audit_targets_total": len(structural_audit_targets),
        "structural_evidence_rows_total": len(structural_evidence_rows),
    }

    questions = derive_question_status(resolved_case_def, coverage)
    question_status_counts = {
        "partial": sum(1 for item in questions if item["status"] == "partial"),
        "missing": sum(1 for item in questions if item["status"] == "missing"),
    }
    case_path = f"/responsibility-explainer/{case_id}/"

    return {
        "meta": {
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "schema_version": "responsibility_explainer_case_v1",
            "case_id": case_id,
            "snapshot_db": db_label,
        },
        "case": {
            "case_id": case_id,
            "title": resolved_case_def["title"],
            "short_label": resolved_case_def["short_label"],
            "summary": resolved_case_def["summary"],
            "geography": resolved_case_def["geography"],
            "incident_window": resolved_case_def["incident_window"],
            "current_scope_note": resolved_case_def["current_scope_note"],
            "canonical_path": case_path,
            "canonical_url": f"{site_origin.rstrip('/')}{base_path}{case_path}",
        },
        "coverage": coverage,
        "question_status_counts": question_status_counts,
        "normative_evidence": {
            "scope_label": "Anclajes oficiales de deber, coordinacion y canales de aviso ya resumidos desde fuentes primarias",
            "normative_duties": normative_duties,
            "warning_channels": warning_channels,
            "warning_timeline_events": warning_timeline_events,
        },
        "accountability_ledger": {
            "scope_label": (
                "Capa generica de accountability para reglas, hallazgos oficiales, actos administrativos "
                "y cadenas de responsabilidad previas o posteriores al dano"
            ),
            "governing_rules": governing_rules,
            "official_findings": official_findings,
            "administrative_acts": administrative_acts,
            "responsibility_links": responsibility_links,
            "named_accountability": named_accountability,
        },
        "structural_evidence": {
            "scope_label": (
                "Reglas de suelo, agua, licencias y gobernanza que pueden haber amplificado la exposicion "
                "previa al desastre, junto con blancos concretos de auditoria y primeras filas de evidencia "
                "para pasar de la norma al expediente"
            ),
            "structural_risk_factors": structural_risk_factors,
            "structural_audit_targets": structural_audit_targets,
            "evidence_rows": structural_evidence_rows,
        },
        "questions": questions,
        "parliamentary_evidence": {
            "scope_label": "Respuesta parlamentaria y normativa ya presente en el repo",
            "initiatives": initiatives,
            "votes": votes,
            "reviewed_measures": measures,
        },
        "gaps": {
            "known_gaps": list(resolved_case_def.get("known_gaps") or []),
            "next_lanes": list(resolved_case_def.get("next_lanes") or []),
        },
    }


def build_manifest(case_payloads: list[dict[str, Any]], *, snapshot_date: str, db_label: str) -> dict[str, Any]:
    cases = []
    for payload in case_payloads:
        case_info = payload["case"]
        coverage = payload["coverage"]
        status_counts = payload["question_status_counts"]
        cases.append(
            {
                "case_id": case_info["case_id"],
                "title": case_info["title"],
                "summary": case_info["summary"],
                "canonical_path": case_info["canonical_path"],
                "coverage": coverage,
                "question_status_counts": status_counts,
            }
        )
    return {
        "meta": {
            "generated_at": now_utc_iso(),
            "snapshot_date": snapshot_date,
            "schema_version": "responsibility_explainer_manifest_v1",
            "snapshot_db": db_label,
            "total_cases": len(cases),
        },
        "cases": cases,
    }


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_dir = Path(args.out_dir)
    seed_path = Path(args.seed)
    db_label = sanitize_public_label(str(db_path))
    if not db_path.exists():
        print(f"ERROR: no existe DB -> {db_path}")
        return 2
    case_seed_map = load_case_seed_map(seed_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        snapshot_date = infer_snapshot_date(conn)
        db_case_defs = load_case_defs_from_db(conn)
        case_defs = db_case_defs or [
            merge_case_def(case_def, case_seed_map.get(case_def["case_id"]))
            for case_def in CASE_DEFS
        ]
        case_payloads = [
            build_case_payload(
                conn,
                case_def=case_def,
                case_seed=case_seed_map.get(case_def["case_id"]),
                snapshot_date=snapshot_date,
                site_origin=str(args.site_origin),
                base_path=str(args.base_path),
                max_initiatives=int(args.max_initiatives),
                max_votes=int(args.max_votes),
                max_measures=int(args.max_measures),
                db_label=db_label,
            )
            for case_def in case_defs
        ]
    finally:
        conn.close()

    manifest = build_manifest(case_payloads, snapshot_date=snapshot_date, db_label=db_label)
    save_json(out_dir / "manifest.json", manifest)
    for payload in case_payloads:
        save_json(out_dir / f"{payload['case']['case_id']}.json", payload)

    print(
        "OK responsibility explainer snapshot -> "
        + str(out_dir)
        + f" (cases={len(case_payloads)} snapshot_date={snapshot_date})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
