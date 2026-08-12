#!/usr/bin/env python3
"""Build a static, evidence-first snapshot for Andalucia 2026 elections."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import posixpath
import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.http import http_get_bytes
from publicdata_core.util import now_utc_iso, sha256_bytes


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("ui/gh-pages-next/public/elecciones/andalucia-2026/data/accountability.json")
DEFAULT_PUBLISHED_OUT = Path("etl/data/published/andalucia-2026-accountability.json")
DEFAULT_IMPACT_REVIEW_QUEUE_OUT = Path(
    "ui/gh-pages-next/public/elecciones/andalucia-2026/data/boja-impact-review-queue.csv"
)
DEFAULT_PUBLISHED_IMPACT_REVIEW_QUEUE_OUT = Path(
    "etl/data/published/andalucia-2026-boja-impact-review-queue.csv"
)
DEFAULT_PARLIAMENT_VOTE_REVIEW_QUEUE_OUT = Path(
    "ui/gh-pages-next/public/elecciones/andalucia-2026/data/parliament-vote-impact-review-queue.csv"
)
DEFAULT_PUBLISHED_PARLIAMENT_VOTE_REVIEW_QUEUE_OUT = Path(
    "etl/data/published/andalucia-2026-parliament-vote-impact-review-queue.csv"
)
DEFAULT_EXECUTION_EVIDENCE_QUEUE_OUT = Path(
    "ui/gh-pages-next/public/elecciones/andalucia-2026/data/execution-evidence-queue.csv"
)
DEFAULT_PUBLISHED_EXECUTION_EVIDENCE_QUEUE_OUT = Path(
    "etl/data/published/andalucia-2026-execution-evidence-queue.csv"
)
DEFAULT_EXECUTION_SOURCE_DISCOVERY = Path(
    "etl/data/published/andalucia-2026-execution-source-discovery.json"
)
DEFAULT_EXECUTION_EVIDENCE_RAW_DIR = Path("etl/data/raw/elections/andalucia_2026/execution_evidence")
DEFAULT_SOURCE_CATALOG = Path("etl/data/published/source-catalog-latest.json")
DEFAULT_RAW_DIR = Path("etl/data/raw/elections/andalucia_2026")
DEFAULT_PROGRAM_SOURCES = Path("etl/data/seeds/andalucia_2026_program_sources.json")
DEFAULT_BOJA_IMPACT_REVIEWS = Path("etl/data/seeds/andalucia_2026_boja_impact_reviews.json")
DEFAULT_PARLIAMENT_VOTE_REVIEWS = Path("etl/data/seeds/andalucia_2026_parliament_vote_reviews.json")
DEFAULT_ISSUE_REVIEWS = Path("etl/data/seeds/andalucia_2026_issue_reviews.json")
DEFAULT_EXECUTION_EVIDENCE_REVIEWS = Path("etl/data/seeds/andalucia_2026_execution_evidence_reviews.json")
DEFAULT_ACCOUNTABILITY_EVIDENCE_API = Path("ui/gh-pages-next/public/accountability-evidence/data/evidence-api.json")
PUBLIC_PARLIAMENT_VOTE_EVENTS_LIMIT = 80
PUBLIC_PARLIAMENT_VOTE_REVIEW_QUEUE_LIMIT = 120
PUBLIC_PARLIAMENT_VOTE_REVIEW_QUEUE_TOPIC_LIMIT = 8

BOJA_API_SEARCH_PAGINATION_URL = "https://datos.juntadeandalucia.es/api/v0/boja/get/search_pagination"
BOJA_API_DETAIL_URL_TEMPLATE = "https://datos.juntadeandalucia.es/api/v0/boja/{boja_id}"
BOJA_TERM_START_DATE = "2022-06-19"
BOJA_TERM_END_DATE = "2026-05-16"
PARLAMENTO_ANDALUCIA_BASE_URL = "https://www.parlamentodeandalucia.es"
PARLAMENTO_ANDALUCIA_INITIATIVES_PATH = (
    "/webdinamica/portal-web-parlamento/actividadparlamentaria/todaslasiniciativas/portipo.do"
)
PARLAMENTO_ANDALUCIA_VOTING_RESULTS_PATH = (
    "/webdinamica/portal-web-parlamento/composicionyfuncionamiento/resultadosvotaciones.do"
)
PARLAMENTO_ANDALUCIA_LEGISLATURE = 12
PARLAMENTO_ANDALUCIA_VOTE_GROUPS = {
    "PP": {"party_key": "pp", "party_acronym": "PP", "party_label": "PP"},
    "PS": {"party_key": "psoe-a", "party_acronym": "PSOE-A", "party_label": "PSOE-A"},
    "VO": {"party_key": "vox", "party_acronym": "VOX", "party_label": "VOX"},
    "PA": {"party_key": "pora", "party_acronym": "PorA", "party_label": "Por Andalucía"},
    "AA": {
        "party_key": "adelante-andalucia",
        "party_acronym": "ADELANTE ANDALUCIA",
        "party_label": "Adelante Andalucía",
    },
}
PARLAMENTO_ANDALUCIA_VOTE_GROUP_HEADERS = (
    ("popular andaluz", "PP"),
    ("psoe de andalucia", "PS"),
    ("vox en andalucia", "VO"),
    ("por andalucia", "PA"),
    ("mixto-adelante andalucia", "AA"),
)
PARLAMENTO_ANDALUCIA_VOTE_ROW_LABELS = (
    "TOTAL ABSTENCIONES",
    "DIPUTADOS AUSENTES",
    "TOTAL DIPUTADOS",
    "VOTOS DELEGADOS",
    "ABSTENCIONES",
    "TOTAL BLANCOS",
    "TOTAL SI",
    "TOTAL NO",
    "PRESENTES",
    "BLANCOS",
    "SI",
    "NO",
)

JUNTA_SUBVENTIONS_SEARCH_URL = "https://datos.juntadeandalucia.es/api/v0/subventions/search"
JUNTA_SUBVENTIONS_PRIORITY_PROGRAMS = ("42J", "44B", "44E", "44F", "45E", "51D")
JUNTA_SUBVENTIONS_PROGRAM_SAMPLE_SIZE = 80
JUNTA_TREASURY_2025_ARCHIVE_URL = (
    "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/"
    "58adcfb6-e01f-446a-9122-9f07e11c978a/resource/"
    "5610d3b1-4fc8-47f5-8243-7370f0202886/download/"
    "transparencia-presidencia-2025t4.7z"
)
JUNTA_TREASURY_2025_ARCHIVE_FILENAME = "tesoreria_2025_movimientos.7z"
JUNTA_TREASURY_2025_PAYMENTS_MEMBER = "2025T4_PAGOS_4.CSV"
PARLAMENTO_ANDALUCIA_MEMBER_POSITION_LABELS = {
    "si": "si",
    "sí": "si",
    "no": "no",
    "abstenciones": "abstenciones",
    "blancos": "blancos",
    "ausentes": "ausente",
}

OFFICIAL_CANDIDATURE_PDF_URL = (
    "https://www.juntaelectoralcentral.es/cs/jec/documentos/"
    "andalucia_2026_candidaturas_proclamadas.pdf"
)
OFFICIAL_CANDIDATURE_BOJA_URL = (
    "https://www.juntadeandalucia.es/eboja/2026/75/c01/"
    "BOJA26-207501-00079-5369-01_00336606.pdf"
)
OFFICIAL_CANDIDATURE_PAGE_URL = (
    "https://eleccionesparlamentoandalucia2026.es/el-proceso-electoral/candidaturas/"
)

ELECTION = {
    "election_id": "andalucia-2026-05-17",
    "name": "Elecciones al Parlamento de Andalucia 2026",
    "territory": "Andalucia",
    "date": "2026-05-17",
    "status": "convocada",
    "seats": 109,
    "candidature_source_url": OFFICIAL_CANDIDATURE_PDF_URL,
    "candidature_boja_url": OFFICIAL_CANDIDATURE_BOJA_URL,
    "candidature_page_url": OFFICIAL_CANDIDATURE_PAGE_URL,
}

FOCUS_CANDIDATES = [
    {
        "focus_id": "pp-juan-manuel-moreno-bonilla",
        "party_acronym": "PP",
        "person_name": "Juan Manuel Moreno Bonilla",
        "role_hint": "candidato_principal",
    },
    {
        "focus_id": "psoe-a-maria-jesus-montero-cuadrado",
        "party_acronym": "PSOE-A",
        "person_name": "Maria Jesus Montero Cuadrado",
        "role_hint": "candidata_principal",
    },
    {
        "focus_id": "vox-manuel-gavira-florentino",
        "party_acronym": "VOX",
        "person_name": "Manuel Gavira Florentino",
        "role_hint": "candidato_principal",
    },
    {
        "focus_id": "pora-antonio-maillo-canadas",
        "party_acronym": "PorA",
        "person_name": "Antonio Maillo Canadas",
        "role_hint": "candidato_principal",
    },
    {
        "focus_id": "adelante-jose-ignacio-garcia-sanchez",
        "party_acronym": "ADELANTE ANDALUCIA",
        "person_name": "Jose Ignacio Garcia Sanchez",
        "role_hint": "candidato_principal",
    },
]

SOURCE_GAP_LANES = [
    {
        "lane_id": "programas_2026",
        "label": "Programas y promesas 2026",
        "needed_for": "que dicen que les importa",
        "status": "missing_connector",
        "next_action": "Scrapear programas electorales oficiales por partido y guardar PDFs/texto como text_documents.",
        "evidence_tier": "tier_3_declared",
    },
    {
        "lane_id": "parlamento_andalucia_actividad",
        "label": "Votos, iniciativas e intervenciones en Parlamento de Andalucia",
        "needed_for": "que hicieron en sede parlamentaria",
        "status": "partial_source",
        "next_action": "Extender Parlamento de Andalucia de diputados actuales a iniciativas, votaciones y textos.",
        "evidence_tier": "tier_1_primary",
    },
    {
        "lane_id": "boja_normas_modificaciones",
        "label": "BOJA normas y modificaciones",
        "needed_for": "direccion real de cambios legales",
        "status": "missing_connector",
        "next_action": "Crear conector BOJA con versionado de normas, modificaciones y efectos por articulo.",
        "evidence_tier": "tier_1_primary",
    },
    {
        "lane_id": "dinero_ejecucion",
        "label": "Presupuestos, contratos, subvenciones y ejecucion",
        "needed_for": "si una medida tuvo recursos reales",
        "status": "partial_source",
        "next_action": "Reforzar BDNS/PLACSP/Junta presupuestos con filtros por organo, territorio y programa.",
        "evidence_tier": "tier_1_primary",
    },
    {
        "lane_id": "outcomes_servicios_publicos",
        "label": "Resultados: sanidad, agua, campo, empleo, espera, recursos",
        "needed_for": "impacto observable en vida real",
        "status": "missing_connector",
        "next_action": "Anadir indicadores oficiales SAS/IECA/ministerios y series comparables por fecha de decision.",
        "evidence_tier": "tier_2_official_structured",
    },
    {
        "lane_id": "prensa_leads",
        "label": "Prensa y acusaciones como leads",
        "needed_for": "tirar del hilo sin convertir acusaciones en conclusion",
        "status": "queue_only",
        "next_action": "Guardar leads de prensa y exigir fuente primaria antes de publicar culpa/merito.",
        "evidence_tier": "tier_5_lead_generation",
    },
]

EXECUTION_EVIDENCE_SOURCE_CANDIDATES = {
    "junta_presupuesto_2026_partidas_gastos": {
        "source_id": "junta_presupuesto_2026_partidas_gastos",
        "source_kind": "official_budget_open_data",
        "name": "Presupuesto de la Comunidad Autonoma de Andalucia 2026 - partidas de gastos",
        "landing_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/presupuesto-de-la-comunidad-autonoma-de-andalucia-2026",
        "source_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/171ed75b-9f2c-4525-910a-c37397da4ce8/resource/50eb97e4-0da7-4f61-a426-61891fd81fde/download/partidas-de-gastos.xlsx",
        "format": "xlsx",
        "status": "head_200_verified",
        "verified_at": "2026-05-16",
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "content_length_bytes": 1899223,
        "filter_hint": "Filtrar por seccion, servicio, programa y conceptos ligados a agua, montes, forestal, cultura, patrimonio, archivos, bibliotecas y fiscalidad.",
    },
    "junta_presupuesto_2026_objetivos_indicadores": {
        "source_id": "junta_presupuesto_2026_objetivos_indicadores",
        "source_kind": "official_budget_indicator_open_data",
        "name": "Presupuesto de Andalucia 2026 - objetivos, actuaciones e indicadores",
        "landing_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/presupuesto-de-la-comunidad-autonoma-de-andalucia-2026",
        "source_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/171ed75b-9f2c-4525-910a-c37397da4ce8/resource/da2826e1-5186-4433-b8c2-a93a18753664/download/objetivos-actuaciones-e-indicadores.xlsx",
        "format": "xlsx",
        "status": "head_200_verified",
        "verified_at": "2026-05-16",
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "content_length_bytes": 2154676,
        "filter_hint": "Cruzar objetivos e indicadores de programas con el cambio legal revisado antes de hablar de outcome.",
    },
    "ieca_ods_agua_631_111614": {
        "source_id": "ieca_ods_agua_631_111614",
        "source_kind": "official_outcome_series_json",
        "name": "IECA ODS 6.3.1 - aguas residuales depuradas adecuadamente",
        "landing_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/ods/listado-indicadores-6.htm",
        "source_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/intranet/admin/rest/v1.0/consulta/111614",
        "format": "json",
        "status": "get_200_verified",
        "verified_at": "2026-05-16",
        "content_type": "application/json;charset=utf-8",
        "content_length_bytes": 2949,
        "filter_hint": "Usar como serie observada pre-2026 para depuracion adecuada de aguas residuales; no prueba impacto posterior por si sola.",
    },
    "ieca_ods_educacion_abandono_115550": {
        "source_id": "ieca_ods_educacion_abandono_115550",
        "source_kind": "official_outcome_series_json",
        "name": "IECA ODS 4.1 - abandono temprano de la educacion",
        "landing_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/ods/listado-indicadores-4.htm",
        "source_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/intranet/admin/rest/v1.0/consulta/115550",
        "format": "json",
        "status": "get_200_verified",
        "verified_at": "2026-05-17",
        "content_type": "application/json;charset=utf-8",
        "content_length_bytes": 0,
        "filter_hint": "Usar como serie observada de resultado educativo; no prueba impacto de Ley 1/2026 por si sola.",
    },
    "ieca_ods_cultura_patrimonio_gasto_85763": {
        "source_id": "ieca_ods_cultura_patrimonio_gasto_85763",
        "source_kind": "official_outcome_series_json",
        "name": "IECA ODS 11.4 - gasto per capita en patrimonio cultural",
        "landing_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/ods/listado-indicadores-11.htm",
        "source_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/intranet/admin/rest/v1.0/consulta/85763",
        "format": "json",
        "status": "get_200_verified",
        "verified_at": "2026-05-17",
        "content_type": "application/json;charset=utf-8",
        "content_length_bytes": 0,
        "filter_hint": "Usar como serie observada de esfuerzo publico en patrimonio cultural; no prueba resultado cultural final por si sola.",
    },
    "ieca_ods_clima_gei_60509": {
        "source_id": "ieca_ods_clima_gei_60509",
        "source_kind": "official_outcome_series_json",
        "name": "IECA ODS 13.2 - emisiones GEI respecto a 2005",
        "landing_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/ods/listado-indicadores-13.htm",
        "source_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/intranet/admin/rest/v1.0/consulta/60509",
        "format": "json",
        "status": "get_200_verified",
        "verified_at": "2026-05-17",
        "content_type": "application/json;charset=utf-8",
        "content_length_bytes": 0,
        "filter_hint": "Usar como serie observada de emisiones GEI; no prueba impacto de la ley ambiental por si sola.",
    },
    "ieca_ods_aire_pm10_85172": {
        "source_id": "ieca_ods_aire_pm10_85172",
        "source_kind": "official_outcome_series_json",
        "name": "IECA ODS 11.6 - nivel medio de PM10 urbano",
        "landing_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/ods/listado-indicadores-11.htm",
        "source_url": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/intranet/admin/rest/v1.0/consulta/85172",
        "format": "json",
        "status": "get_200_verified",
        "verified_at": "2026-05-17",
        "content_type": "application/json;charset=utf-8",
        "content_length_bytes": 0,
        "filter_hint": "Usar como serie observada de calidad del aire urbano; no prueba impacto de gestion ambiental por si sola.",
    },
    "junta_subvenciones_programas_prioritarios": {
        "source_id": "junta_subvenciones_programas_prioritarios",
        "source_kind": "official_grant_awards_open_data",
        "name": "Junta de Andalucia - subvenciones otorgadas por programas prioritarios",
        "landing_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/subvenciones-otorgadas-por-la-junta-de-andalucia",
        "source_url": JUNTA_SUBVENTIONS_SEARCH_URL,
        "format": "json_search_sample",
        "status": "get_200_verified",
        "verified_at": "2026-05-17",
        "content_type": "application/json",
        "content_length_bytes": 0,
        "filter_hint": "Muestra reproducible de concesiones por programa presupuestario; documenta beneficiario/importe/concesion, no resultado final.",
    },
    "junta_tesoreria_2025_pagos_agregados": {
        "source_id": "junta_tesoreria_2025_pagos_agregados",
        "source_kind": "official_treasury_payment_aggregate_open_data",
        "name": "Movimientos de la Tesoreria General de la Junta de Andalucia 2025 - pagos agregados",
        "landing_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/movimientos-de-la-tesoreria-general-de-la-junta-de-andalucia-2025",
        "source_url": JUNTA_TREASURY_2025_ARCHIVE_URL,
        "format": "7z_csv_member",
        "status": "head_200_verified",
        "verified_at": "2026-05-17",
        "content_type": "application/zip",
        "content_length_bytes": 180817306,
        "filter_hint": "Usar el miembro 2025T4_PAGOS_4.CSV como pagos agregados mensuales por jerarquia y organo; no incluye beneficiario, entrega final ni outcome.",
    },
    "junta_contratos_menores_2025": {
        "source_id": "junta_contratos_menores_2025",
        "source_kind": "official_procurement_open_data",
        "name": "Contratos menores adjudicados por la Junta de Andalucia y entidades instrumentales 2025",
        "landing_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/contratos-menores-adjudicados-por-la-administracion-de-la-junta-de-andalucia-y-sus-entidades-instrumentales-ano-2025",
        "source_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/00510697-b39d-4e19-b142-14565baafabd/resource/33d80321-3ffc-4b3c-8b27-5e073bab8419/download/menores_2025_v1_20260122.json",
        "format": "json_zip_payload",
        "status": "head_200_verified",
        "verified_at": "2026-05-16",
        "content_type": "application/zip",
        "content_length_bytes": 78707967,
        "filter_hint": "Filtrar por organo contratante y objeto con agua, abastecimiento, montes, forestal, cultura, patrimonio, archivos, bibliotecas, riego y depuracion.",
    },
    "junta_contratos_menores_2024": {
        "source_id": "junta_contratos_menores_2024",
        "source_kind": "official_procurement_open_data",
        "name": "Contratos menores adjudicados por la Junta de Andalucia y entidades instrumentales 2024",
        "landing_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/contratacion-menor-plataforma-de-contratacion-andalucia-2024",
        "source_url": "https://www.juntadeandalucia.es/datosabiertos/portal/dataset/cdf0e880-0a19-46cf-a09e-856328d85700/resource/56a49a80-5d11-4559-b028-483e2eefa68a/download/menores_2024_v1_20250420.json",
        "format": "json",
        "status": "head_200_verified",
        "verified_at": "2026-05-16",
        "content_type": "application/json",
        "content_length_bytes": 97689409,
        "filter_hint": "Filtrar por organo contratante y objeto con agua, abastecimiento, saneamiento, montes, forestal, cultura, patrimonio, archivos, bibliotecas, riego y depuracion.",
    },
    "bdns_convocatorias": {
        "source_id": "bdns_convocatorias",
        "source_kind": "official_subsidy_registry",
        "name": "BDNS - convocatorias de subvenciones",
        "landing_url": "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias",
        "source_url": "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias",
        "format": "html_search",
        "status": "head_200_verified",
        "verified_at": "2026-05-16",
        "content_type": "text/html",
        "content_length_bytes": 1172,
        "filter_hint": "Buscar convocatorias Junta/Andalucia por agua, regadio, montes, agroambiente y organo concedente.",
    },
    "junta_perfiles_contratante_licitaciones": {
        "source_id": "junta_perfiles_contratante_licitaciones",
        "source_kind": "official_procurement_registry",
        "name": "Junta de Andalucia - perfiles del contratante y licitaciones",
        "landing_url": "https://juntadeandalucia.es/temas/contratacion-publica/perfiles-licitaciones.html",
        "source_url": "https://www.juntadeandalucia.es/temas/contratacion-publica/perfiles-licitaciones.html",
        "format": "html_registry",
        "status": "head_200_verified",
        "verified_at": "2026-05-16",
        "content_type": "text/html",
        "content_length_bytes": 129869,
        "filter_hint": "Usar como registro oficial complementario para licitaciones no cubiertas por el dump de contratos menores.",
    },
}

EXECUTION_EVIDENCE_RAW_FILES = {
    "junta_presupuesto_2026_partidas_gastos": "partidas-de-gastos.xlsx",
    "junta_presupuesto_2026_objetivos_indicadores": "objetivos-actuaciones-e-indicadores.xlsx",
    "ieca_ods_agua_631_111614": "ieca_ods_agua_631_111614.json",
    "ieca_ods_educacion_abandono_115550": "ieca_ods_educacion_abandono_115550.json",
    "ieca_ods_cultura_patrimonio_gasto_85763": "ieca_ods_cultura_patrimonio_gasto_85763.json",
    "ieca_ods_clima_gei_60509": "ieca_ods_clima_gei_60509.json",
    "ieca_ods_aire_pm10_85172": "ieca_ods_aire_pm10_85172.json",
    "junta_subvenciones_programas_prioritarios": "junta_subvenciones_programas_prioritarios.json",
    "junta_tesoreria_2025_pagos_agregados": JUNTA_TREASURY_2025_ARCHIVE_FILENAME,
    "junta_contratos_menores_2025": "menores_2025_v1_20260122.json",
    "junta_contratos_menores_2024": "menores_2024_v1_20250420.json",
}

EXECUTION_EVIDENCE_CANDIDATE_LIMIT = 6
MAX_DISCOVERY_EXECUTION_SOURCES_PER_GAP = 4

IECA_ODS_OUTCOME_UNIT_HINTS = {
    "ieca_ods_agua_631_111614": "Porcentaje",
    "ieca_ods_educacion_abandono_115550": "Porcentaje",
    "ieca_ods_cultura_patrimonio_gasto_85763": "Euros per capita",
    "ieca_ods_clima_gei_60509": "Porcentaje",
    "ieca_ods_aire_pm10_85172": "Microgramos por metro cubico",
}

POST_CHANGE_OUTCOME_MIN_YEAR = 2026

EXECUTION_TOPIC_SEARCH_PROFILES = {
    "campo_agua": {
        "program_terms": (
            "agua",
            "agric",
            "ganad",
            "pesca",
            "forestal",
            "biodiversidad",
            "desarrollo rural",
            "medio ambiente",
            "sostenibilidad",
        ),
        "section_terms": (
            "agricultura",
            "pesca",
            "agua",
            "desarrollo rural",
            "sostenibilidad",
            "medio ambiente",
            "emergencias",
        ),
        "indicator_terms": (
            "agua",
            "vertido",
            "hidrica",
            "regadio",
            "forestal",
            "incendios",
            "emergencias ambientales",
            "riesgos relacionados con el clima",
            "rural",
            "agraria",
        ),
    },
}

EXECUTION_EVIDENCE_XLSX_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}

ISSUE_EXECUTION_EVIDENCE_PLANS = {
    "sanidad": [
        {
            "gap_id": "missing_execution_owner",
            "evidence_need": "unidad ejecutora sanitaria",
            "review_question": "Que consejeria, SAS, agencia, hospital, distrito o unidad ejecuta la decision sanitaria revisada?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_perfiles_contratante_licitaciones",
            ),
            "search_terms": (
                "sanidad",
                "salud",
                "servicio andaluz de salud",
                "sas",
                "hospital",
                "atencion primaria",
                "asistencia sanitaria",
                "paciente",
            ),
            "expected_resolution": "Organo sanitario competente, expediente o programa oficial enlazado; sin esto no hay ejecucion atribuible.",
        },
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion sanitaria",
            "review_question": "Hay programa presupuestario, contrato, subvencion, pago o expediente que financie o ejecute la medida sanitaria?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "junta_contratos_menores_2025",
                "junta_contratos_menores_2024",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "sanidad",
                "salud",
                "servicio andaluz de salud",
                "sas",
                "hospital",
                "atencion primaria",
                "lista de espera",
                "asistencia sanitaria",
                "farmacia",
                "paciente",
            ),
            "expected_resolution": "Partida, expediente, contrato, convocatoria o pago con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado sanitario observable",
            "review_question": "Que indicador oficial permite medir lista de espera, actividad asistencial, atencion primaria u otro resultado sanitario tras la decision?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
            ),
            "search_terms": (
                "sanidad",
                "salud",
                "hospital",
                "atencion primaria",
                "lista de espera",
                "asistencia sanitaria",
                "paciente",
            ),
            "expected_resolution": "Serie o indicador sanitario con fecha base y fecha posterior; si no esta en presupuesto, hace falta loader SAS/estadistica sanitaria oficial.",
        },
    ],
    "vivienda": [
        {
            "gap_id": "missing_execution_owner",
            "evidence_need": "unidad ejecutora de vivienda",
            "review_question": "Que consejeria, AVRA, agencia, ayuntamiento o unidad ejecuta la decision de vivienda revisada?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_perfiles_contratante_licitaciones",
            ),
            "search_terms": (
                "vivienda",
                "alquiler",
                "vivienda protegida",
                "vpo",
                "rehabilitacion",
                "avra",
                "suelo",
            ),
            "expected_resolution": "Organo ejecutor, programa o expediente oficial de vivienda enlazado a la decision.",
        },
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion de vivienda",
            "review_question": "Hay programa presupuestario, contrato, ayuda, pago o promocion que financie vivienda, alquiler, VPO o rehabilitacion?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "junta_contratos_menores_2025",
                "junta_contratos_menores_2024",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "vivienda",
                "alquiler",
                "vivienda protegida",
                "vpo",
                "rehabilitacion",
                "parque publico",
                "avra",
                "suelo",
            ),
            "expected_resolution": "Partida, expediente, ayuda, contrato o pago con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado observable de vivienda",
            "review_question": "Que indicador oficial mide acceso a vivienda, alquiler, VPO, rehabilitacion o parque publico tras la decision?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
            ),
            "search_terms": (
                "vivienda",
                "alquiler",
                "vivienda protegida",
                "vpo",
                "rehabilitacion",
                "parque publico",
            ),
            "expected_resolution": "Serie o indicador con fecha base y fecha posterior; sin esto no hay impacto ciudadano.",
        },
    ],
    "fiscalidad": [
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "ejecucion de ayudas o impacto fiscal",
            "review_question": "Hay convocatoria, pago, partida, beneficiario o liquidacion que ejecute las medidas fiscales/ayudas revisadas?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "fiscal",
                "impuesto",
                "tribut",
                "hacienda",
                "borrasca",
                "ayuda",
                "agricultores",
                "ganaderos",
                "autonomos",
                "empleo",
            ),
            "expected_resolution": "Convocatoria, pago, partida o liquidacion con importe, beneficiario/sector y organo verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado economico observable",
            "review_question": "Que indicador oficial permite medir si las ayudas/fiscalidad cambiaron actividad, empleo, renta agraria o recuperacion tras las borrascas?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
            ),
            "search_terms": (
                "fiscal",
                "impuesto",
                "tribut",
                "borrasca",
                "ayuda",
                "actividad",
                "empleo",
                "autonomos",
                "agricultura",
            ),
            "expected_resolution": "Indicador o serie con fecha base y fecha posterior; sin esto no hay impacto atribuible.",
        },
    ],
    "empleo": [
        {
            "gap_id": "missing_execution_owner",
            "evidence_need": "unidad ejecutora de empleo",
            "review_question": "Que consejeria, SAE, entidad instrumental o unidad ejecuta la decision de empleo revisada?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_perfiles_contratante_licitaciones",
            ),
            "search_terms": (
                "empleo",
                "servicio andaluz de empleo",
                "sae",
                "trabajo",
                "formacion profesional para el empleo",
                "autonomos",
                "procesos selectivos",
                "bolsa unica",
            ),
            "expected_resolution": "Organo ejecutor, programa o expediente oficial de empleo enlazado a la decision.",
        },
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion de empleo",
            "review_question": "Hay programa presupuestario, ayuda, contrato, convocatoria o pago que ejecute la medida de empleo?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "junta_contratos_menores_2025",
                "junta_contratos_menores_2024",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "empleo",
                "servicio andaluz de empleo",
                "sae",
                "trabajo",
                "formacion profesional para el empleo",
                "orientacion profesional",
                "autonomos",
                "procesos selectivos",
                "bolsa unica",
            ),
            "expected_resolution": "Partida, expediente, ayuda, contrato o pago con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado observable de empleo",
            "review_question": "Que indicador oficial mide empleo, paro, formacion, insercion, autonomos o temporalidad tras la decision?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
            ),
            "search_terms": (
                "empleo",
                "paro",
                "trabajo",
                "insercion laboral",
                "formacion profesional para el empleo",
                "autonomos",
                "temporalidad",
            ),
            "expected_resolution": "Serie o indicador con fecha base y fecha posterior; sin esto no hay impacto ciudadano.",
        },
    ],
    "transparencia_corrupcion": [
        {
            "gap_id": "missing_execution_owner",
            "evidence_need": "unidad ejecutora de transparencia y anticorrupcion",
            "review_question": "Que organo, oficina, intervencion, consejeria o unidad ejecuta la decision de transparencia/anticorrupcion revisada?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_perfiles_contratante_licitaciones",
            ),
            "search_terms": (
                "transparencia",
                "corrupcion",
                "fraude",
                "oficina andaluza contra el fraude",
                "proteccion de la persona denunciante",
                "buen gobierno",
                "incompatibilidades",
                "alto cargo",
                "intervencion",
                "auditoria",
            ),
            "expected_resolution": "Organo ejecutor, competencia concreta o programa oficial enlazado; sin esto solo hay senal legal/parlamentaria.",
        },
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion de transparencia y anticorrupcion",
            "review_question": "Hay partida, contrato, ayuda, pago o expediente que financie transparencia, antifraude, denunciante, auditoria o control interno?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "junta_contratos_menores_2025",
                "junta_contratos_menores_2024",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "transparencia",
                "corrupcion",
                "fraude",
                "oficina andaluza contra el fraude",
                "proteccion de la persona denunciante",
                "buen gobierno",
                "incompatibilidades",
                "alto cargo",
                "intervencion",
                "auditoria",
                "control interno",
            ),
            "expected_resolution": "Partida, expediente, contrato, ayuda o pago con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado observable de transparencia y anticorrupcion",
            "review_question": "Que indicador oficial mide transparencia, denuncias, expedientes antifraude, auditorias, control interno o cumplimiento tras la decision?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
            ),
            "search_terms": (
                "transparencia",
                "corrupcion",
                "fraude",
                "denunciante",
                "auditoria",
                "intervencion",
                "control interno",
                "buen gobierno",
            ),
            "expected_resolution": "Serie o indicador con fecha base y fecha posterior; sin esto no hay impacto ciudadano.",
        },
    ],
    "seguridad_libertades": [
        {
            "gap_id": "missing_execution_owner",
            "evidence_need": "unidad ejecutora de seguridad/libertades",
            "review_question": "Que consejeria, agencia, policia autonomica/adscrita, Proteccion Civil, memoria democratica u organo ejecuta la decision?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_perfiles_contratante_licitaciones",
            ),
            "search_terms": (
                "seguridad",
                "libertad",
                "derechos",
                "proteccion civil",
                "emergencias",
                "policia",
                "memoria democratica",
            ),
            "expected_resolution": "Organo ejecutor o programa oficial enlazado; sin esto solo hay posicion parlamentaria.",
        },
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion de seguridad/libertades",
            "review_question": "Hay programa presupuestario, contrato, ayuda o pago ligado a seguridad, emergencias, derechos, memoria o libertades?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "junta_contratos_menores_2025",
                "junta_contratos_menores_2024",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "seguridad",
                "libertad",
                "derechos",
                "proteccion civil",
                "emergencias",
                "policia",
                "memoria democratica",
            ),
            "expected_resolution": "Partida, expediente, contrato, ayuda o pago con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado observable de seguridad/libertades",
            "review_question": "Que indicador oficial mide seguridad, emergencias, ejercicio de derechos o aplicacion de memoria/libertades tras la decision?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
            ),
            "search_terms": (
                "seguridad",
                "libertad",
                "derechos",
                "proteccion civil",
                "emergencias",
                "memoria democratica",
            ),
            "expected_resolution": "Indicador o serie con fecha base y fecha posterior; sin esto no hay impacto ciudadano.",
        },
    ],
    "campo_agua": [
        {
            "gap_id": "missing_execution_owner",
            "evidence_need": "unidad ejecutora",
            "review_question": "Que consejeria, direccion general, agencia o entidad ejecuta el cambio de montes/agua revisado?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_perfiles_contratante_licitaciones",
            ),
            "search_terms": ("agua", "canon", "montes", "forestal", "agricultura", "medio ambiente"),
            "expected_resolution": "Organo ejecutor, competencia concreta y fecha efectiva enlazados a fuente oficial.",
        },
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion",
            "review_question": "Hay programa presupuestario, contrato, subvencion o partida que financie la medida?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "junta_contratos_menores_2025",
                "junta_contratos_menores_2024",
                "bdns_convocatorias",
            ),
            "search_terms": ("canon", "agua", "abastecimiento", "depuracion", "riego", "montes", "forestal"),
            "expected_resolution": "Partida, expediente, convocatoria o contrato con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado observable",
            "review_question": "Que indicador oficial permite medir si el cambio mejoro, empeoro o no movio el resultado?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "ieca_ods_agua_631_111614",
            ),
            "search_terms": (
                "indicador",
                "agua",
                "aguas residuales",
                "depuracion",
                "saneamiento",
                "montes",
                "incendios",
                "abastecimiento",
                "regadio",
            ),
            "expected_resolution": "Serie o indicador con fecha base y fecha posterior; sin esto no hay impacto ciudadano.",
        },
    ],
    "cultura_patrimonio": [
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion",
            "review_question": "Hay programa presupuestario, contrato, subvencion o partida que financie patrimonio, museos, archivos o bibliotecas?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "junta_contratos_menores_2025",
                "junta_contratos_menores_2024",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "cultura",
                "patrimonio",
                "museo",
                "biblioteca",
                "archivo",
                "monumento",
                "bien cultural",
                "infraestructuras culturales",
            ),
            "expected_resolution": "Partida, expediente, convocatoria o contrato con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado observable",
            "review_question": "Que indicador oficial permite medir actividad, obra, acceso o conservacion cultural tras el cambio?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "ieca_ods_cultura_patrimonio_gasto_85763",
            ),
            "search_terms": (
                "cultura",
                "patrimonio",
                "museo",
                "biblioteca",
                "archivo",
                "monumento",
                "infraestructuras culturales",
                "patrimonio cultural",
                "conservacion",
            ),
            "expected_resolution": "Indicador o serie con fecha base y fecha posterior; sin esto no hay impacto ciudadano.",
        },
    ],
    "educacion": [
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion",
            "review_question": "Hay programa presupuestario, contrato, subvencion o partida que financie universidades, becas o aplicacion educativa?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "universidad",
                "universidades",
                "universidades publicas",
                "financiacion upa",
                "becas",
                "educacion",
                "formacion profesional",
                "ensenanzas universitarias",
                "uned",
            ),
            "expected_resolution": "Partida, expediente, convocatoria o contrato con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado observable",
            "review_question": "Que indicador oficial permite medir acceso, rendimiento, movilidad o financiacion universitaria tras el cambio?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "ieca_ods_educacion_abandono_115550",
            ),
            "search_terms": (
                "universidad",
                "universitaria",
                "universidades",
                "ensenanza universitaria",
                "educacion",
                "abandono temprano",
                "creditos aprobados",
                "movilidad",
                "beca",
            ),
            "expected_resolution": "Indicador o serie con fecha base y fecha posterior; sin esto no hay impacto ciudadano.",
        },
    ],
    "energia_clima": [
        {
            "gap_id": "missing_budget_execution",
            "evidence_need": "presupuesto y ejecucion",
            "review_question": "Hay programa presupuestario, contrato, subvencion o partida que financie gestion ambiental, calidad del aire o clima?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_partidas_gastos",
                "junta_presupuesto_2026_objetivos_indicadores",
                "junta_subvenciones_programas_prioritarios",
                "junta_tesoreria_2025_pagos_agregados",
                "bdns_convocatorias",
            ),
            "search_terms": (
                "gestion ambiental",
                "medio ambiente",
                "ambiental",
                "calidad del aire",
                "emisiones",
                "cambio climatico",
                "sostenibilidad",
                "clima",
            ),
            "expected_resolution": "Partida, expediente, convocatoria o contrato con importe, organo y objeto verificables.",
        },
        {
            "gap_id": "missing_outcomes",
            "evidence_need": "resultado observable",
            "review_question": "Que indicador oficial permite medir calidad del aire, emisiones o gestion ambiental tras el cambio?",
            "source_candidate_ids": (
                "junta_presupuesto_2026_objetivos_indicadores",
                "ieca_ods_clima_gei_60509",
                "ieca_ods_aire_pm10_85172",
            ),
            "search_terms": (
                "gestion ambiental",
                "medio ambiente",
                "ambiental",
                "calidad del aire",
                "emisiones",
                "gases de efecto invernadero",
                "pm10",
                "particulas",
                "planes de mejora",
                "autorizaciones de emisiones",
                "clima",
            ),
            "expected_resolution": "Indicador o serie con fecha base y fecha posterior; sin esto no hay impacto ciudadano.",
        },
    ],
}

PROGRAM_TOPIC_TERMS = {
    "sanidad": ("sanidad", "salud", "sas", "atencion primaria", "lista de espera", "hospital"),
    "vivienda": ("vivienda", "alquiler", "sareb", "vpo", "hipoteca"),
    "educacion": ("educacion", "formacion profesional", "universidad", "beca", "comedor escolar"),
    "empleo": ("empleo", "paro", "salario", "trabajadores", "autonomos"),
    "campo_agua": ("agricultura", "ganaderia", "pesca", "campo", "agua", "sequia", "regadio"),
    "fiscalidad": ("impuesto", "fiscalidad", "fiscal", "apoyo fiscal", "tribut", "tasas", "hacienda"),
    "cultura_patrimonio": ("cultura", "patrimonio", "museo", "biblioteca", "archiv", "monumento"),
    "seguridad_libertades": ("seguridad", "libertad", "policia", "derechos", "memoria"),
    "energia_clima": ("energia", "clima", "renovable", "fotovoltaica", "emergencia climatica"),
    "transparencia_corrupcion": ("transparencia", "corrupcion", "auditoria", "buen gobierno"),
}

PROGRAM_TOPIC_LABELS = {
    "sanidad": "Sanidad",
    "vivienda": "Vivienda",
    "educacion": "Educacion",
    "empleo": "Empleo",
    "campo_agua": "Campo y agua",
    "fiscalidad": "Fiscalidad",
    "cultura_patrimonio": "Cultura y patrimonio",
    "seguridad_libertades": "Seguridad y libertades",
    "energia_clima": "Energia y clima",
    "transparencia_corrupcion": "Transparencia y corrupcion",
}

BOJA_TOPIC_QUERIES = {
    "sanidad": "sanidad",
    "vivienda": "vivienda",
    "educacion": "educación",
    "empleo": "empleo",
    "campo_agua": "agua",
    "fiscalidad": "impuesto",
    "cultura_patrimonio": "patrimonio",
    "seguridad_libertades": "seguridad",
    "energia_clima": "energía",
    "transparencia_corrupcion": "transparencia",
}

BOJA_TOPIC_EXACT_RECORDS: tuple[dict[str, str], ...] = (
    {
        "topic_id": "cultura_patrimonio",
        "topic_query": "patrimonio cultural",
        "boja_id": "disposition.2026.65.1",
        "note": "Ley 4/2026 de Patrimonio Cultural de Andalucia.",
    },
    {
        "topic_id": "energia_clima",
        "topic_query": "gestion ambiental",
        "boja_id": "disposition.2026.55.1",
        "note": "Ley 2/2026 para la Gestion Ambiental de Andalucia.",
    },
    {
        "topic_id": "educacion",
        "topic_query": "ley universitaria",
        "boja_id": "disposition.2026.45.1",
        "note": "Ley 1/2026 Universitaria para Andalucia.",
    },
    {
        "topic_id": "fiscalidad",
        "topic_query": "borrascas",
        "boja_id": "disposition.2026.203802.1",
        "note": "Decreto-ley 1/2026 de apoyo fiscal y medidas agrarias/hidraulicas por borrascas.",
    },
    {
        "topic_id": "fiscalidad",
        "topic_query": "borrascas",
        "boja_id": "disposition.2026.56.1",
        "note": "Acuerdo de convalidacion del Decreto-ley 1/2026.",
    },
    {
        "topic_id": "fiscalidad",
        "topic_query": "borrascas",
        "boja_id": "disposition.2026.74.1",
        "note": "Decreto-ley 4/2026, modificacion del Decreto-ley 1/2026.",
    },
    {
        "topic_id": "fiscalidad",
        "topic_query": "borrascas",
        "boja_id": "disposition.2026.86.3",
        "note": "Acuerdo de convalidacion del Decreto-ley 4/2026.",
    },
)

BOJA_TOPIC_EXCLUSION_TERMS = {
    "cultura_patrimonio": (
        "patrimonio natural",
        "biodiversidad",
        "espacio natural",
        "espacios naturales",
        "red natura 2000",
    ),
    "sanidad": (
        "consejeria de agricultura",
        "consejería de agricultura",
        "sanidad vegetal",
        "fitosanitari",
        "produccion integrada",
        "producción integrada",
        "frutas y hortalizas",
        "ayudas directas y de mercados",
    ),
}

BOJA_TOPIC_REQUIRED_TERMS_WHEN_EXCLUDED = {
    "cultura_patrimonio": (
        "patrimonio cultural",
        "patrimonio historico",
        "patrimonio histórico",
        "cultura",
        "museo",
        "biblioteca",
        "archivo",
        "monumento",
    ),
    "sanidad": (
        "servicio andaluz de salud",
        "sistema sanitario",
        "salud publica",
        "salud pública",
        "asistencia sanitaria",
        "atencion primaria",
        "atención primaria",
        "hospital",
        "farmacia",
        "paciente",
        "sspa",
        "consejeria de salud",
        "consejería de salud",
        "consejeria de sanidad",
        "consejería de sanidad",
        "politica de salud",
        "política de salud",
    ),
}

PROGRAM_MEASURE_ACTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("aprobar", (r"\baprobaremos\b", r"\baprobar\b", r"^aprobacion\b")),
    ("blindar", (r"\bblindaremos\b", r"\bblindar\b")),
    ("crear", (r"\bcrearemos\b", r"\bcrear\b", r"^creacion\b")),
    ("defender", (r"\bdefenderemos\b", r"\bdefender\b", r"\bdefendemos\b")),
    ("derogar", (r"\bderogaremos\b", r"\bderogar\b", r"^derogacion\b")),
    ("desarrollar", (r"\bdesarrollaremos\b", r"\bdesarrollar\b", r"\bdesarrollando\b", r"^desarrollo\b")),
    ("dotar", (r"\bdotaremos\b", r"\bdotar\b", r"^dotacion\b")),
    ("eliminar", (r"\beliminaremos\b", r"\beliminar\b")),
    ("establecer", (r"\bestableceremos\b", r"\bestablecer\b", r"^establecimiento\b")),
    ("exigir", (r"\bexigiremos\b", r"\bexigir\b")),
    ("facilitar", (r"\bfacilitaremos\b", r"\bfacilitar\b")),
    ("financiar", (r"\bfinanciaremos\b", r"\bfinanciar\b", r"^financiacion\b")),
    ("garantizar", (r"\bgarantizaremos\b", r"\bgarantizar\b")),
    ("implantar", (r"\bimplantaremos\b", r"\bimplantar\b", r"^implantacion\b")),
    ("impulsar", (r"\bimpulsaremos\b", r"\bimpulsar\b", r"^impulso\b")),
    ("incrementar", (r"\bincrementaremos\b", r"\bincrementar\b", r"^incremento\b")),
    ("mejorar", (r"\bmejoraremos\b", r"\bmejorar\b", r"^mejora\b")),
    ("modernizar", (r"\bmodernizaremos\b", r"\bmodernizar\b")),
    ("potenciar", (r"\bpotenciaremos\b", r"\bpotenciar\b")),
    ("prohibir", (r"\bprohibiremos\b", r"\bprohibir\b", r"^prohibicion\b")),
    ("promover", (r"\bpromoveremos\b", r"\bpromover\b", r"\bfomentaremos\b", r"\bfomentar\b", r"^promocion\b")),
    ("recuperar", (r"\brecuperaremos\b", r"\brecuperar\b")),
    ("reducir", (r"\breduciremos\b", r"\breducir\b", r"\bdisminuiremos\b", r"\bdisminuir\b", r"^reduccion\b")),
    ("reforzar", (r"\breforzaremos\b", r"\breforzar\b", r"\bfortaleceremos\b", r"\bfortalecer\b")),
    ("regular", (r"\bregularemos\b", r"\bregular\b", r"^regulacion\b")),
)

BOJA_ACTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("modifica_norma", (r"\bmodifica(?:n|r|do|da|cion|ciones)?\b", r"nueva redaccion", r"queda redactad")),
    ("deroga_norma", (r"\bderoga(?:n|r|do|da|cion|ciones)?\b", r"\bqueda sin efecto\b")),
    ("aprueba_ley", (r"^\s*ley\s+\d+", r"\bse aprueba la ley\b")),
    ("aprueba_plan_estrategia", (r"\bse aprueba\b.*\b(plan|estrategia|programa)\b", r"\baprobar\b.*\b(plan|estrategia|programa)\b")),
    ("convoca_ayuda", (r"\bconvoca(?:n|r|toria|torias)?\b", r"\bayudas?\b", r"\bsubvenciones?\b")),
    ("regula", (r"\bregula(?:n|r|cion|ciones)?\b", r"\bestablece(?:n|r)?\b", r"\bse establecen\b")),
    ("estructura_organica", (r"\bestructura organica\b", r"\bcompetencias\b")),
)

BOJA_ACTION_REVIEW_HINTS = {
    "modifica_norma": "Identificar norma modificada, direccion material del cambio y organo responsable.",
    "deroga_norma": "Identificar norma derogada, efecto real y quien impulso o aprobo la derogacion.",
    "aprueba_ley": "Separar aprobacion formal, contenido sustantivo, votos y responsables.",
    "aprueba_plan_estrategia": "Distinguir declaracion estrategica de medidas ejecutadas y presupuesto.",
    "convoca_ayuda": "Enlazar convocatoria con presupuesto, beneficiarios, resoluciones y ejecucion.",
    "regula": "Revisar obligaciones, beneficiarios, restricciones y organo competente.",
    "estructura_organica": "Mapear competencias transferidas, unidad responsable y fechas efectivas.",
    "official_normative_reference": "Revisar manualmente si hay cambio legal sustantivo o solo referencia documental.",
}

BOJA_IMPACT_REVIEW_BATCH_SIZE = 12
BOJA_IMPACT_REVIEW_PRIORITY_ITEMS_LIMIT = 24

BOJA_IMPACT_REVIEW_ACTION_PRIORITY = {
    "deroga_norma": 42,
    "modifica_norma": 40,
    "aprueba_ley": 38,
    "regula": 34,
    "convoca_ayuda": 30,
    "estructura_organica": 24,
    "aprueba_plan_estrategia": 22,
    "official_normative_reference": 12,
}

BOJA_IMPACT_REVIEW_TOPIC_PRIORITY = {
    "sanidad": 18,
    "vivienda": 18,
    "educacion": 16,
    "empleo": 15,
    "campo_agua": 15,
    "fiscalidad": 13,
    "cultura_patrimonio": 13,
    "seguridad_libertades": 12,
    "energia_clima": 12,
    "transparencia_corrupcion": 12,
}

BOJA_IMPACT_REVIEW_QUESTIONS = (
    {
        "question_id": "legal_change",
        "question": "Que norma, plan, ayuda o regla cambia este fragmento?",
    },
    {
        "question_id": "citizen_direction",
        "question": "La direccion ciudadana es mejora, recorte, redistribucion, restriccion o sin efecto claro?",
    },
    {
        "question_id": "responsible_actor",
        "question": "Que organo, persona o partido puede atribuirse con fuente primaria?",
    },
    {
        "question_id": "impact_evidence_gap",
        "question": "Que presupuesto, ejecucion u outcome falta para validar impacto real?",
    },
)

PARLIAMENT_VOTE_REVIEW_QUESTIONS = (
    {
        "question_id": "vote_subject",
        "question": "Que expediente, enmienda o punto se votaba exactamente?",
    },
    {
        "question_id": "legal_effect",
        "question": "La mayoria del voto produjo aprobacion, rechazo, convalidacion, enmienda o solo tramite?",
    },
    {
        "question_id": "responsible_actor",
        "question": "Que grupo, diputado o cargo puede enlazarse como actor responsable con fuente primaria?",
    },
    {
        "question_id": "impact_evidence_gap",
        "question": "Que BOJA, presupuesto, ejecucion u outcome falta para valorar impacto ciudadano?",
    },
)

PARLIAMENT_VOTE_REVIEW_BATCH_SIZE = 12
PARLIAMENT_VOTE_REVIEW_PRIORITY_ITEMS_LIMIT = 24

PARLIAMENT_VOTE_REVIEW_TYPE_PRIORITY = {
    "DL": 30,
    "PL": 28,
    "PPL": 24,
    "PNLP": 22,
    "PPPL": 20,
    "ILPA": 18,
    "M": 16,
    "RP": 14,
    "ROCF": 12,
    "COM": 10,
    "sin_tipo": 8,
}

PARLIAMENT_VOTE_REVIEW_QUEUE_CSV_COLUMNS = (
    "review_item_id",
    "priority_rank",
    "priority_score",
    "review_batch_id",
    "priority_reason",
    "vote_event_id",
    "date",
    "session_number",
    "vote_number",
    "numexp",
    "initiative_id",
    "initiative_match_status",
    "initiative_type_code",
    "initiative_type_label",
    "topic_id",
    "topic_label",
    "topic_source",
    "majority_side",
    "total_si",
    "total_no",
    "total_abstenciones",
    "total_blancos",
    "member_votes_total",
    "party_positions_summary",
    "review_status",
    "legal_effect_status",
    "legal_effect_kind",
    "legal_effect_label",
    "legal_effect_confidence",
    "legal_effect_basis",
    "impact_status",
    "responsibility_status",
    "claim_status",
    "evidence_tier",
    "title",
    "review_hint",
    "review_questions",
    "source_url",
    "initiative_source_url",
    "source_locator",
)

BOJA_IMPACT_REVIEW_QUEUE_CSV_COLUMNS = (
    "review_item_id",
    "priority_rank",
    "priority_score",
    "review_batch_id",
    "priority_reason",
    "topic_id",
    "topic_label",
    "boja_id",
    "fragment_id",
    "date",
    "organisation",
    "type",
    "action_kind",
    "review_status",
    "impact_status",
    "responsibility_status",
    "candidate_direction",
    "claim_status",
    "evidence_tier",
    "evidence_excerpt",
    "review_hint",
    "review_questions",
    "source_url",
    "detail_url",
    "source_locator",
)

EXECUTION_EVIDENCE_QUEUE_CSV_COLUMNS = (
    "queue_item_id",
    "priority_rank",
    "topic_id",
    "topic_label",
    "gap_id",
    "evidence_need",
    "status",
    "review_question",
    "source_candidate_ids",
    "source_urls",
    "official_candidate_rows_total",
    "official_candidate_rows_by_source",
    "top_official_candidate_rows",
    "reviewed_evidence_rows_total",
    "top_reviewed_evidence_rows",
    "search_terms",
    "expected_resolution",
    "current_packet_status",
    "issue_review_status",
    "open_gaps",
)

PROGRAM_MEASURE_STARTERS = tuple(
    sorted(
        {
            "aprobar",
            "aprobacion",
            "blindar",
            "crear",
            "creacion",
            "defender",
            "derogar",
            "derogacion",
            "desarrollar",
            "desarrollo",
            "dotar",
            "dotacion",
            "eliminar",
            "establecer",
            "establecimiento",
            "exigir",
            "facilitar",
            "financiar",
            "financiacion",
            "garantizar",
            "implantar",
            "implantacion",
            "impulsar",
            "impulso",
            "incrementar",
            "incremento",
            "mejorar",
            "mejora",
            "modernizar",
            "potenciar",
            "prohibir",
            "prohibicion",
            "promover",
            "promocion",
            "fomentar",
            "recuperar",
            "reducir",
            "reduccion",
            "reforzar",
            "regular",
            "regulacion",
        }
    )
)

PARTY_ACCOUNTABILITY_ACTOR_KEYS = {
    "pp": {
        "actor_key": "party_id:1",
        "match_scope": "national_party_rollup",
        "match_note": "Source-backed PP party rollup in the national accountability ledger.",
    },
    "psoe-a": {
        "actor_key": "party_id:3",
        "match_scope": "national_party_rollup",
        "match_note": "Source-backed PSOE national party rollup; not a PSOE-A-only regional record.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Andalucia 2026 accountability snapshot")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB with people/mandates")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Static UI JSON output")
    parser.add_argument("--published-out", default=str(DEFAULT_PUBLISHED_OUT), help="Published JSON output")
    parser.add_argument(
        "--impact-review-queue-out",
        default=str(DEFAULT_IMPACT_REVIEW_QUEUE_OUT),
        help="Static UI CSV output for BOJA impact review queue",
    )
    parser.add_argument(
        "--published-impact-review-queue-out",
        default=str(DEFAULT_PUBLISHED_IMPACT_REVIEW_QUEUE_OUT),
        help="Published CSV output for BOJA impact review queue",
    )
    parser.add_argument(
        "--parliament-vote-review-queue-out",
        default=str(DEFAULT_PARLIAMENT_VOTE_REVIEW_QUEUE_OUT),
        help="Static UI CSV output for Parliament vote impact review queue",
    )
    parser.add_argument(
        "--published-parliament-vote-review-queue-out",
        default=str(DEFAULT_PUBLISHED_PARLIAMENT_VOTE_REVIEW_QUEUE_OUT),
        help="Published CSV output for Parliament vote impact review queue",
    )
    parser.add_argument(
        "--execution-evidence-queue-out",
        default=str(DEFAULT_EXECUTION_EVIDENCE_QUEUE_OUT),
        help="Static UI CSV output for execution/budget/outcome evidence queue",
    )
    parser.add_argument(
        "--published-execution-evidence-queue-out",
        default=str(DEFAULT_PUBLISHED_EXECUTION_EVIDENCE_QUEUE_OUT),
        help="Published CSV output for execution/budget/outcome evidence queue",
    )
    parser.add_argument(
        "--execution-evidence-raw-dir",
        default=str(DEFAULT_EXECUTION_EVIDENCE_RAW_DIR),
        help="Raw XLSX cache dir for official execution/budget/outcome evidence sources",
    )
    parser.add_argument(
        "--refresh-outcome-series",
        action="store_true",
        help="Refresh small official outcome-series JSON sources even when cached",
    )
    parser.add_argument("--source-catalog", default=str(DEFAULT_SOURCE_CATALOG), help="Source catalog JSON")
    parser.add_argument(
        "--accountability-evidence-api",
        default=str(DEFAULT_ACCOUNTABILITY_EVIDENCE_API),
        help="Published accountability Evidence API JSON to link actor records",
    )
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR), help="Raw document cache dir")
    parser.add_argument(
        "--program-sources",
        default=str(DEFAULT_PROGRAM_SOURCES),
        help="JSON seed with Andalucia 2026 program source URLs",
    )
    parser.add_argument(
        "--boja-impact-reviews",
        default=str(DEFAULT_BOJA_IMPACT_REVIEWS),
        help="JSON seed with reviewed BOJA legal-change impact rows",
    )
    parser.add_argument(
        "--parliament-vote-reviews",
        default=str(DEFAULT_PARLIAMENT_VOTE_REVIEWS),
        help="JSON seed with reviewed Parliament vote-impact rows",
    )
    parser.add_argument(
        "--issue-reviews",
        default=str(DEFAULT_ISSUE_REVIEWS),
        help="JSON seed with reviewed issue-level accountability rows",
    )
    parser.add_argument(
        "--execution-evidence-reviews",
        default=str(DEFAULT_EXECUTION_EVIDENCE_REVIEWS),
        help="JSON seed with reviewed budget/indicator execution evidence rows",
    )
    parser.add_argument("--from-text", default="", help="Use extracted candidatures text instead of network PDF")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout")
    parser.add_argument("--boja-date-from", default=BOJA_TERM_START_DATE, help="BOJA search lower date, yyyy-mm-dd")
    parser.add_argument("--boja-date-to", default=BOJA_TERM_END_DATE, help="BOJA search upper date, yyyy-mm-dd")
    parser.add_argument("--boja-api-size", type=int, default=40, help="Rows requested per BOJA topic search")
    parser.add_argument("--boja-max-per-topic", type=int, default=6, help="Published BOJA sample rows per topic")
    parser.add_argument(
        "--parliament-legislature",
        type=int,
        default=PARLAMENTO_ANDALUCIA_LEGISLATURE,
        help="Parlamento de Andalucia legislature to scrape",
    )
    parser.add_argument("--no-network", action="store_true", help="Do not fetch official PDF")
    parser.add_argument("--strict-network", action="store_true", help="Fail if official PDF cannot be fetched")
    return parser.parse_args()


def normalize_label(value: Any) -> str:
    text = str(value or "").strip()
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
    return re.sub(r"\s+", " ", text.translate(table).lower()).strip()


def stable_slug(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_label(value)).strip("-")
    return slug or "sin-dato"


def strip_person_prefix(value: str) -> str:
    return re.sub(r"^(DON|DOÑA)\s+", "", str(value or "").strip(), flags=re.IGNORECASE).strip()


def normalize_candidate_name(value: str) -> str:
    return normalize_label(strip_person_prefix(value))


def normalize_person_name_for_vote_match(value: str) -> str:
    normalized = normalize_candidate_name(value)
    replacements = (
        (r"\bmª\b", "maria"),
        (r"\bma\b", "maria"),
        (r"\bfco\b", "francisco"),
        (r"\bfca\b", "francisca"),
        (r"\bjose\s+mª\b", "jose maria"),
        (r"\bmiguel\s+a\b", "miguel angel"),
        (r"\brafael\s+a\b", "rafael antonio"),
        (r"\bgaspar\s+j\b", "gaspar jose"),
        (r"\bvictor\s+m\b", "victor manuel"),
    )
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized)
    normalized = normalized.replace(".", " ")
    return clean_line(normalized)


def invert_vote_member_name(value: str) -> str:
    text = clean_line(value)
    if "," not in text:
        return text
    surname, given = text.split(",", 1)
    return clean_line(f"{given} {surname}")


def extract_pdf_text(raw_path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        raise RuntimeError("pdftotext is required to parse official candidature PDF")
    completed = subprocess.run(
        [pdftotext, "-layout", str(raw_path), "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "pdftotext failed")
    return completed.stdout


def fetch_official_candidature_text(
    *,
    raw_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
) -> tuple[str, dict[str, Any]]:
    raw_path = raw_dir / "candidaturas_proclamadas.pdf"
    payload = b""
    content_type = ""
    status = "skipped"
    error = ""
    text = ""

    if raw_path.exists():
        payload = raw_path.read_bytes()
        status = "cached"
        try:
            text = extract_pdf_text(raw_path)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            if strict_network:
                raise

    if not text and not no_network:
        try:
            payload, content_type = http_get_bytes(OFFICIAL_CANDIDATURE_PDF_URL, timeout=timeout, max_attempts=1)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(payload)
            text = extract_pdf_text(raw_path)
            status = "ok"
            error = ""
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
            if strict_network:
                raise

    source = {
        "source_id": "jec_andalucia_2026_candidaturas_proclamadas",
        "name": "Candidaturas proclamadas Andalucia 2026",
        "url": OFFICIAL_CANDIDATURE_PDF_URL,
        "boja_url": OFFICIAL_CANDIDATURE_BOJA_URL,
        "page_url": OFFICIAL_CANDIDATURE_PAGE_URL,
        "format": "pdf",
        "status": status,
        "bytes": len(payload),
        "content_type": content_type,
        "content_sha256": sha256_bytes(payload) if payload else "",
        "raw_path": str(raw_path) if payload else "",
        "source_verified": bool(text) and "Candidaturas proclamadas" in text and "17 de mayo de 2026" in text,
        "error": error,
    }
    return text, source


def empty_program_report(seed_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_program_collection_v1",
        "status": "missing",
        "seed_path": str(seed_path),
        "sources_total": 0,
        "fetched_sources_total": 0,
        "verified_sources_total": 0,
        "text_extracted_sources_total": 0,
        "press_hosted_sources_total": 0,
        "party_domain_sources_total": 0,
        "party_keys_with_program_total": 0,
        "measures_total": 0,
        "parties_with_measures_total": 0,
        "topics_with_measures_total": 0,
        "source_gaps": [],
        "sources": [],
        "by_party": {},
        "measures": [],
        "measures_by_party": {},
        "measures_by_topic": [],
    }


def empty_accountability_evidence_report(path: Path | None = None) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_accountability_evidence_join_v1",
        "status": "missing",
        "source_path": str(path) if path else "",
        "source_entries_total": 0,
        "source_actor_answers_total": 0,
        "source_issue_answers_total": 0,
        "actors_by_key": {},
    }


def empty_boja_norms_report(raw_dir: Path | None = None) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_boja_normative_topic_report_v1",
        "status": "missing",
        "api_url": BOJA_API_SEARCH_PAGINATION_URL,
        "detail_api_url_template": BOJA_API_DETAIL_URL_TEMPLATE,
        "raw_dir": str(raw_dir or ""),
        "date_from": BOJA_TERM_START_DATE,
        "date_to": BOJA_TERM_END_DATE,
        "topics_total": 0,
        "topics_with_results_total": 0,
        "api_total_hits": 0,
        "records_total": 0,
        "details_available_total": 0,
        "details_fetched_total": 0,
        "details_cached_total": 0,
        "fragments_total": 0,
        "fragment_action_counts": [],
        "impact_review_queue_total": 0,
        "reviewed_impact_items_total": 0,
        "reviewed_impact_items": [],
        "reviewed_impact_items_by_topic": {},
        "impact_review_review_status_counts": [],
        "impact_review_action_counts": [],
        "impact_review_packet": {},
        "errors_total": 0,
        "topics": [],
        "records": [],
        "records_by_topic": {},
        "fragments": [],
        "fragments_by_topic": {},
        "impact_review_queue": [],
        "impact_review_queue_by_topic": {},
        "errors": [],
    }


def empty_parliament_activity_report(raw_dir: Path | None = None) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_parliament_activity_report_v1",
        "status": "missing",
        "source_id": "parlamento_andalucia_actividad_xii",
        "raw_dir": str(raw_dir or ""),
        "legislature": PARLAMENTO_ANDALUCIA_LEGISLATURE,
        "initiatives_url": "",
        "voting_results_url": "",
        "legislative_initiatives_total": 0,
        "legislative_initiatives_by_proponent": [],
        "legislative_initiatives_by_party_key": [],
        "legislative_initiatives_by_type": [],
        "legislative_initiatives_by_topic": [],
        "legislative_initiatives": [],
        "voting_documents_total": 0,
        "voting_documents": [],
        "parsed_vote_events_total": 0,
        "vote_events_with_initiative_total": 0,
        "vote_events_with_official_initiative_total": 0,
        "vote_events_with_legal_effect_triage_total": 0,
        "vote_events_with_party_totals_total": 0,
        "vote_events": [],
        "vote_events_by_party_position": [],
        "vote_events_by_party_topic": [],
        "vote_events_by_legal_effect": [],
        "vote_impact_review_queue_total": 0,
        "vote_impact_review_batches_total": 0,
        "reviewed_vote_items_total": 0,
        "vote_impact_review_packet": {},
        "vote_impact_review_queue": [],
        "vote_impact_review_queue_by_topic": {},
        "vote_impact_review_type_counts": [],
        "vote_impact_review_legal_effect_counts": [],
        "review_status": "missing_source",
        "claim_status": "no_public_claim",
        "errors_total": 0,
        "errors": [],
    }


def load_program_source_seed(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_program_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise RuntimeError(f"Program source seed without sources list: {path}")
    return {
        "schema_version": payload.get("schema_version") or "andalucia_2026_program_sources_v1",
        "status": "ok",
        "seed_path": str(path),
        "sources": [row for row in sources if isinstance(row, dict)],
    }


def pdf_page_count(raw_path: Path, text: str) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        completed = subprocess.run(
            [pdfinfo, str(raw_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode == 0:
            match = re.search(r"^Pages:\s*(\d+)\s*$", completed.stdout, flags=re.MULTILINE)
            if match:
                return int(match.group(1))
    return max(1, text.count("\f") + 1) if text.strip() else 0


def extract_program_text(raw_path: Path) -> tuple[str, str]:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return "", "RuntimeError: pdftotext is required to parse program PDF"

    candidates: list[tuple[str, str]] = []
    errors: list[str] = []
    for mode_name, args in (
        ("layout", [pdftotext, "-layout", str(raw_path), "-"]),
        ("raw", [pdftotext, "-raw", str(raw_path), "-"]),
    ):
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if completed.returncode == 0 and completed.stdout:
            candidates.append((completed.stdout, mode_name))
        else:
            errors.append(completed.stderr.strip() or f"{mode_name} pdftotext failed")
    if not candidates:
        return "", "; ".join(errors) or "pdftotext failed"
    text, mode_name = max(candidates, key=lambda item: program_text_quality(item[0]))
    return text, f"ok:{mode_name}"


def compact_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_label(text))


def program_text_quality(text: str) -> int:
    normalized = normalize_label(text)
    compact = compact_for_match(text)
    score = len(re.findall(r"\b(programa|andalucia|sanidad|vivienda|empleo|educacion|agua|fiscalidad)\b", normalized))
    score += sum(normalized.count(normalize_label(term)) for terms in PROGRAM_TOPIC_TERMS.values() for term in terms)
    score += 3 * sum(
        compact.count(compact_for_match(term))
        for term in ("programa de gobierno", "programa electoral", "hay esperanza", "tabla de contenido")
    )
    score -= min(500, sum(1 for ch in text if ord(ch) > 127 and ch not in "áéíóúüñÁÉÍÓÚÜÑ¿¡"))
    return score


def program_topic_hits(text: str) -> dict[str, int]:
    normalized = normalize_label(text)
    hits: dict[str, int] = {}
    for topic, terms in PROGRAM_TOPIC_TERMS.items():
        hits[topic] = sum(normalized.count(normalize_label(term)) for term in terms)
    return hits


def program_topic_label(topic_id: str) -> str:
    return PROGRAM_TOPIC_LABELS.get(topic_id, topic_id.replace("_", " ").title())


def detect_program_measure_action(text: str) -> str:
    normalized = normalize_label(text)
    for action, patterns in PROGRAM_MEASURE_ACTION_PATTERNS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return action
    return ""


def is_program_commitment_text(text: str) -> bool:
    normalized = normalize_label(strip_measure_prefix(text))
    if re.search(r"\b\w+remos\b", normalized):
        return True
    if re.search(r"\b(vamos a|seguiremos|continuaremos|nos comprometemos|proponemos|defendemos)\b", normalized):
        return True
    starters = "|".join(re.escape(term) for term in PROGRAM_MEASURE_STARTERS)
    return bool(re.match(rf"^(?:{starters})\b", normalized))


def clean_program_measure_line(line: str) -> str:
    line = clean_line(line.replace("\f", " "))
    return line.strip()


def is_program_measure_noise(line: str) -> bool:
    if not line:
        return True
    normalized = normalize_label(line)
    if len(normalized) < 8:
        return True
    if re.fullmatch(r"\d{1,4}", normalized):
        return True
    if re.search(r"(?:\.\s*){4,}", line):
        return True
    noise_terms = (
        "programa electoral",
        "programa de gobierno",
        "tabla de contenido",
        "indice",
        "pagina ",
        "tierra hermana",
        "hay esperanza",
    )
    return any(normalized.startswith(term) for term in noise_terms)


def starts_program_measure(line: str) -> bool:
    return bool(
        re.match(r"^\s*(?:\d{1,4}[.)]\s+|[•○●]\s+|[-–—]\s+|medida\s+\d{1,4}\s*[:.)-])", line, flags=re.I)
    )


def append_measure_line(base: str, line: str) -> str:
    if not base:
        return line
    if base.endswith("-"):
        return f"{base[:-1]}{line.lstrip()}"
    return f"{base} {line}"


def strip_measure_prefix(text: str) -> str:
    text = clean_line(text)
    text = re.sub(r"^(?:\d{1,4}[.)]\s+|[•○●]\s+|[-–—]\s+|medida\s+\d{1,4}\s*[:.)-]\s*)", "", text, flags=re.I)
    return clean_line(text)


def short_excerpt(text: str, *, max_words: int = 24, max_chars: int = 220) -> str:
    words = strip_measure_prefix(text).split()
    if len(words) > max_words:
        words = words[:max_words]
        out = " ".join(words).rstrip(".,;:") + "..."
    else:
        out = " ".join(words)
    if len(out) > max_chars:
        out = out[: max_chars - 3].rstrip(".,;: ") + "..."
    return out


def iter_program_measure_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for page_index, page_text in enumerate(text.split("\f"), start=1):
        active_text = ""
        active_start_line = 0

        def flush_active() -> None:
            nonlocal active_text, active_start_line
            candidate = strip_measure_prefix(active_text)
            if candidate:
                candidates.append(
                    {
                        "text": candidate,
                        "page": page_index,
                        "line": active_start_line,
                        "source_shape": "listed_measure",
                    }
                )
            active_text = ""
            active_start_line = 0

        for line_index, raw_line in enumerate(page_text.splitlines(), start=1):
            line = clean_program_measure_line(raw_line)
            if is_program_measure_noise(line):
                flush_active()
                continue
            if starts_program_measure(line):
                flush_active()
                active_text = line
                active_start_line = line_index
                continue
            if active_text:
                active_text = append_measure_line(active_text, line)
                if len(active_text) > 520:
                    flush_active()
                continue
            if detect_program_measure_action(line) and any(program_topic_hits(line).values()):
                candidates.append(
                    {
                        "text": strip_measure_prefix(line),
                        "page": page_index,
                        "line": line_index,
                        "source_shape": "inline_sentence",
                    }
                )
        flush_active()
    return candidates


def classify_program_measure_topics(text: str, limit: int = 2) -> list[dict[str, Any]]:
    hits = program_topic_hits(text)
    ranked = sorted(((topic, count) for topic, count in hits.items() if count), key=lambda item: (-item[1], item[0]))
    return [
        {"topic_id": topic, "topic_label": program_topic_label(topic), "hits": count}
        for topic, count in ranked[:limit]
    ]


def extract_program_measures(
    sources: list[dict[str, Any]],
    *,
    max_per_party: int = 24,
    max_per_party_topic: int = 4,
) -> list[dict[str, Any]]:
    measures: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    party_totals: dict[str, int] = defaultdict(int)
    party_topic_totals: dict[tuple[str, str], int] = defaultdict(int)

    for source in sources:
        text_path_value = str(source.get("text_path") or "")
        text_path = Path(text_path_value) if text_path_value else None
        text = text_path.read_text(encoding="utf-8", errors="replace") if text_path and text_path.is_file() else ""
        if not text.strip():
            continue
        party_key = str(source.get("party_key") or "")
        party_acronym = str(source.get("party_acronym") or party_key)
        party_name = str(source.get("party_name") or party_acronym)
        for candidate in iter_program_measure_candidates(text):
            raw_text = str(candidate.get("text") or "")
            action = detect_program_measure_action(raw_text)
            topics = classify_program_measure_topics(raw_text, limit=1)
            if not action or not topics or not is_program_commitment_text(raw_text):
                continue
            topic = topics[0]
            topic_id = topic["topic_id"]
            if party_totals[party_key] >= max_per_party:
                continue
            if party_topic_totals[(party_key, topic_id)] >= max_per_party_topic:
                continue
            excerpt = short_excerpt(raw_text)
            if excerpt.endswith("-") or raw_text.rstrip().endswith("-"):
                continue
            if len(excerpt) < 36:
                continue
            dedupe_key = (party_key, compact_for_match(excerpt)[:140])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            party_totals[party_key] += 1
            party_topic_totals[(party_key, topic_id)] += 1
            ordinal = party_totals[party_key]
            measures.append(
                {
                    "measure_id": f"{party_key}-{topic_id}-{ordinal:03d}",
                    "party_key": party_key,
                    "party_acronym": party_acronym,
                    "party_name": party_name,
                    "topic_id": topic_id,
                    "topic_label": topic["topic_label"],
                    "action_kind": action,
                    "source_id": source.get("source_id") or "",
                    "source_title": source.get("title") or "",
                    "source_url": source.get("url") or "",
                    "source_page_url": source.get("page_url") or "",
                    "source_officiality": source.get("officiality") or "",
                    "verification_status": source.get("verification_status") or "",
                    "evidence_tier": "tier_3_declared",
                    "claim_status": "declared_program_measure_not_assessed",
                    "interpretation_status": "needs_review_before_impact_claim",
                    "source_locator": {
                        "pdf_page": int(candidate.get("page") or 0),
                        "text_line": int(candidate.get("line") or 0),
                        "source_shape": candidate.get("source_shape") or "",
                    },
                    "evidence_excerpt": excerpt,
                    "excerpt_words": len(excerpt.split()),
                }
            )
    return measures


def summarize_program_measures(measures: list[dict[str, Any]]) -> dict[str, Any]:
    by_party: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_topic: dict[str, dict[str, Any]] = {}
    for measure in measures:
        by_party[str(measure["party_key"])].append(measure)
        topic_id = str(measure["topic_id"])
        topic = by_topic.setdefault(
            topic_id,
            {
                "topic_id": topic_id,
                "topic_label": measure.get("topic_label") or program_topic_label(topic_id),
                "measures_total": 0,
                "parties": defaultdict(int),
            },
        )
        topic["measures_total"] += 1
        topic["parties"][str(measure["party_key"])] += 1

    topic_rows: list[dict[str, Any]] = []
    for topic in by_topic.values():
        party_counts = [
            {"party_key": party_key, "measures_total": count}
            for party_key, count in sorted(topic["parties"].items(), key=lambda item: (-item[1], item[0]))
        ]
        topic_rows.append(
            {
                "topic_id": topic["topic_id"],
                "topic_label": topic["topic_label"],
                "measures_total": topic["measures_total"],
                "parties_total": len(party_counts),
                "party_counts": party_counts,
            }
        )

    return {
        "by_party": dict(by_party),
        "by_topic": sorted(topic_rows, key=lambda row: (-int(row["measures_total"]), row["topic_label"])),
    }


def compact_count_rows(rows: Any, limit: int = 4) -> list[dict[str, Any]]:
    if isinstance(rows, dict):
        items = [{"key": str(key), "count": int(value or 0)} for key, value in rows.items()]
    elif isinstance(rows, list):
        items = [
            {"key": str(row.get("key") or ""), "count": int(row.get("count") or 0)}
            for row in rows
            if isinstance(row, dict)
        ]
    else:
        items = []
    items = [row for row in items if row["key"]]
    return sorted(items, key=lambda row: (-row["count"], row["key"]))[:limit]


def compact_evidence_quote(value: Any, max_words: int = 18, max_chars: int = 180) -> str:
    text = clean_line(str(value or ""))
    if not text:
        return ""
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(".,;:") + "..."
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip(".,;: ") + "..."
    return text


def compact_evidence_sample(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_id": sample.get("entry_id") or "",
        "entry_kind": sample.get("entry_kind") or "",
        "accountability_role": sample.get("accountability_role") or "",
        "event_date": sample.get("event_date") or "",
        "issue_id": sample.get("issue_id") or "",
        "issue_label": compact_evidence_quote(sample.get("issue_label"), max_words=20),
        "title": compact_evidence_quote(sample.get("title"), max_words=16),
        "evidence_quote": compact_evidence_quote(sample.get("evidence_quote"), max_words=18),
        "evidence_tier": sample.get("evidence_tier") or "",
        "source_title": sample.get("source_title") or "",
        "source_url": sample.get("source_url") or "",
        "source_locator": sample.get("source_locator") or "",
    }


def compact_actor_answer(answer: dict[str, Any]) -> dict[str, Any]:
    coverage = answer.get("coverage") or {}
    confidence = answer.get("confidence") or {}
    freshness = answer.get("freshness") or {}
    return {
        "actor_key": answer.get("actor_key") or "",
        "actor_label": answer.get("actor_label") or "",
        "actor_kind": answer.get("actor_kind") or "",
        "answer_status": answer.get("answer_status") or "",
        "entries_total": int(coverage.get("entries_total") or 0),
        "issues_total": int(coverage.get("issues_total") or 0),
        "first_date": coverage.get("first_date") or "",
        "last_date": coverage.get("last_date") or "",
        "role_counts": compact_count_rows(answer.get("role_counts"), limit=4),
        "entry_kind_counts": compact_count_rows(answer.get("entry_kind_counts"), limit=4),
        "present_dimensions": list(answer.get("present_dimensions") or [])[:8],
        "missing_dimensions": list(answer.get("missing_dimensions") or [])[:8],
        "confidence_level": confidence.get("level") or "",
        "confidence_score": confidence.get("score"),
        "best_evidence_tier": (confidence.get("best_evidence_tier") if isinstance(confidence, dict) else ""),
        "freshness_level": freshness.get("level") or "",
        "dossier_route": (answer.get("routes") or {}).get("dossier") or "",
        "summary": compact_evidence_quote(answer.get("summary"), max_words=28, max_chars=240),
        "evidence_samples": [
            compact_evidence_sample(sample)
            for sample in (answer.get("evidence_samples") or [])[:2]
            if isinstance(sample, dict)
        ],
        "top_issues": [
            {
                "issue_id": issue.get("issue_id") or "",
                "entries_total": int(issue.get("entries_total") or 0),
                "first_date": issue.get("first_date") or "",
                "last_date": issue.get("last_date") or "",
                "role_counts": compact_count_rows(issue.get("role_counts"), limit=3),
            }
            for issue in (answer.get("top_issues") or [])[:3]
            if isinstance(issue, dict)
        ],
    }


def load_accountability_evidence_report(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return empty_accountability_evidence_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    actors_by_key: dict[str, dict[str, Any]] = {}
    for answer in payload.get("actor_answers") or []:
        if not isinstance(answer, dict):
            continue
        actor_key = str(answer.get("actor_key") or "")
        if actor_key:
            actors_by_key[actor_key] = compact_actor_answer(answer)
    coverage = payload.get("coverage") or {}
    return {
        "schema_version": "andalucia_2026_accountability_evidence_join_v1",
        "status": "ok",
        "source_path": str(path),
        "snapshot_date": payload.get("snapshot_date") or "",
        "source_entries_total": int(coverage.get("source_entries_total") or 0),
        "source_actor_answers_total": int(coverage.get("actor_answers_total") or len(actors_by_key)),
        "source_issue_answers_total": int(coverage.get("issue_answers_total") or 0),
        "actors_by_key": actors_by_key,
    }


def build_accountability_evidence_ref(
    evidence_report: dict[str, Any],
    actor_key: str,
    *,
    match_scope: str,
    match_note: str = "",
) -> dict[str, Any]:
    if not actor_key:
        return {
            "status": "not_matchable",
            "actor_key": "",
            "match_scope": match_scope,
            "match_note": match_note,
        }
    actor_answer = (evidence_report.get("actors_by_key") or {}).get(actor_key)
    if not actor_answer:
        return {
            "status": "missing_in_current_ledger",
            "actor_key": actor_key,
            "match_scope": match_scope,
            "match_note": match_note,
        }
    row = dict(actor_answer)
    row.update(
        {
            "status": "linked_accountability_evidence",
            "match_scope": match_scope,
            "match_note": match_note,
        }
    )
    return row


def program_heading_sample(text: str, limit: int = 10) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        normalized = normalize_label(line)
        if not line or len(line) < 4 or len(line) > 90:
            continue
        if normalized in seen:
            continue
        upperish = sum(1 for ch in line if ch.isupper()) >= max(3, int(len(line) * 0.45))
        indexed = bool(re.match(r"^(\d+\.|[A-Z]\.|BLOQUE|PROPUESTA|CAP[IÍ]TULO|[IVXLCDM]+\.)", line))
        if upperish or indexed:
            seen.add(normalized)
            out.append(line)
        if len(out) >= limit:
            break
    return out


def verify_program_text(text: str, verify_terms: list[Any]) -> tuple[str, list[str]]:
    normalized = normalize_label(text)
    compact_text = compact_for_match(text)
    missing: list[str] = []
    for term in verify_terms:
        raw = str(term or "").strip()
        if raw and normalize_label(raw) not in normalized and compact_for_match(raw) not in compact_text:
            missing.append(raw)
    if not text.strip():
        return "missing_text", missing
    if missing:
        return "fetched_unverified", missing
    return "verified_by_text", []


def collect_program_sources(
    *,
    seed_path: Path,
    raw_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
) -> dict[str, Any]:
    seed = load_program_source_seed(seed_path)
    if seed.get("status") != "ok":
        return seed

    program_dir = raw_dir / "programas"
    text_dir = program_dir / "text"
    sources: list[dict[str, Any]] = []
    by_party: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for seed_row in seed["sources"]:
        source_id = str(seed_row.get("source_id") or stable_slug(seed_row.get("title") or seed_row.get("url")))
        party_key = str(seed_row.get("party_key") or stable_slug(seed_row.get("party_acronym") or source_id))
        url = str(seed_row.get("url") or "")
        raw_path = program_dir / f"{source_id}.pdf"
        text_path = text_dir / f"{source_id}.txt"
        payload = raw_path.read_bytes() if raw_path.exists() else b""
        content_type = ""
        status = "cached" if payload else "missing"
        fetch_error = ""

        if not payload and url and not no_network:
            try:
                payload, content_type = http_get_bytes(url, timeout=timeout, max_attempts=1)
                program_dir.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(payload)
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                status = "error"
                fetch_error = f"{type(exc).__name__}: {exc}"
                if strict_network:
                    raise

        text = ""
        extract_status = "missing_payload"
        if payload:
            cached_text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
            text, extract_status = extract_program_text(raw_path)
            if not text and cached_text:
                text = cached_text
                extract_status = "cached"
            if text:
                text_path.parent.mkdir(parents=True, exist_ok=True)
                if not text_path.exists() or text_path.read_text(encoding="utf-8", errors="replace") != text:
                    text_path.write_text(text, encoding="utf-8")

        verify_terms = list(seed_row.get("verify_terms") or [])
        verification_status, missing_terms = verify_program_text(text, verify_terms)
        doc = {
            "source_id": source_id,
            "party_key": party_key,
            "party_acronym": seed_row.get("party_acronym") or "",
            "party_name": seed_row.get("party_name") or "",
            "title": seed_row.get("title") or "",
            "url": url,
            "page_url": seed_row.get("page_url") or "",
            "source_kind": seed_row.get("source_kind") or "",
            "officiality": seed_row.get("officiality") or "",
            "format": seed_row.get("format") or "pdf",
            "status": status,
            "fetch_error": fetch_error,
            "bytes": len(payload),
            "content_type": content_type,
            "content_sha256": sha256_bytes(payload) if payload else "",
            "raw_path": str(raw_path) if payload else "",
            "text_path": str(text_path) if text else "",
            "text_chars": len(text),
            "text_sha256": sha256_bytes(text.encode("utf-8")) if text else "",
            "page_count": pdf_page_count(raw_path, text) if payload else 0,
            "extract_status": extract_status,
            "verification_status": verification_status,
            "missing_verify_terms": missing_terms,
            "topic_hits": program_topic_hits(text) if text else {},
            "heading_sample": program_heading_sample(text),
            "measures_total": 0,
            "measure_topics": [],
            "claim_status": "raw_program_text_only",
        }
        sources.append(doc)
        by_party[party_key].append(doc)

    program_measures = extract_program_measures(sources)
    measure_summary = summarize_program_measures(program_measures)
    source_measure_counts: dict[str, int] = defaultdict(int)
    source_measure_topics: dict[str, set[str]] = defaultdict(set)
    for measure in program_measures:
        source_measure_counts[str(measure["source_id"])] += 1
        source_measure_topics[str(measure["source_id"])].add(str(measure["topic_id"]))
    for source in sources:
        source_id = str(source["source_id"])
        source["measures_total"] = source_measure_counts[source_id]
        source["measure_topics"] = sorted(source_measure_topics[source_id])
        if source["measures_total"]:
            source["claim_status"] = "declared_program_measures_extracted"

    fetched_sources = [row for row in sources if row["status"] in {"ok", "cached"} and row["bytes"] > 0]
    verified_sources = [row for row in sources if row["verification_status"] == "verified_by_text"]
    text_sources = [row for row in sources if row["text_chars"] > 0]
    return {
        "schema_version": "andalucia_2026_program_collection_v1",
        "status": "ok",
        "seed_path": str(seed_path),
        "sources_total": len(sources),
        "fetched_sources_total": len(fetched_sources),
        "verified_sources_total": len(verified_sources),
        "text_extracted_sources_total": len(text_sources),
        "press_hosted_sources_total": sum(1 for row in sources if row["officiality"] == "press_hosted_copy"),
        "party_domain_sources_total": sum(1 for row in sources if row["officiality"] in {"party_domain", "campaign_domain"}),
        "party_keys_with_program_total": len({row["party_key"] for row in text_sources}),
        "measures_total": len(program_measures),
        "parties_with_measures_total": len(measure_summary["by_party"]),
        "topics_with_measures_total": len(measure_summary["by_topic"]),
        "source_gaps": [
            {
                "party_key": row["party_key"],
                "source_id": row["source_id"],
                "status": row["status"],
                "verification_status": row["verification_status"],
                "next_action": "Buscar URL primaria del partido o repetir descarga con nueva fuente.",
            }
            for row in sources
            if row["status"] == "error" or row["verification_status"] != "verified_by_text"
        ],
        "sources": sources,
        "by_party": dict(by_party),
        "measures": program_measures,
        "measures_by_party": measure_summary["by_party"],
        "measures_by_topic": measure_summary["by_topic"],
    }


def strip_html_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = html.unescape(text)
    return clean_line(text)


def html_text_blocks(value: Any) -> list[str]:
    raw = str(value or "")
    if not raw.strip():
        return []
    raw = re.sub(r"</(?:p|div|li|h\d|br)\s*>", "\n", raw, flags=re.I)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return [clean_line(line) for line in raw.splitlines() if clean_line(line)]


def parliament_abs_url(href: str) -> str:
    return urllib.parse.urljoin(PARLAMENTO_ANDALUCIA_BASE_URL, str(href or ""))


def build_parliament_initiatives_url(*, legislature: int = PARLAMENTO_ANDALUCIA_LEGISLATURE) -> str:
    params = {
        "accion": "Ver iniciativas",
        "desdeanyo": "",
        "desdemes": "",
        "estado": "",
        "hastaanyo": "",
        "hastames": "",
        "legislatura": str(legislature),
        "seleccion": "publicadosen",
        "sinpaginacion": "1",
        "situacion": "",
        "tipoespecifico": "",
        "tipogeneral": "1",
    }
    return f"{PARLAMENTO_ANDALUCIA_BASE_URL}{PARLAMENTO_ANDALUCIA_INITIATIVES_PATH}?{urllib.parse.urlencode(params)}"


def build_parliament_initiative_url(numexp: str, *, legislature: int = PARLAMENTO_ANDALUCIA_LEGISLATURE) -> str:
    params = {
        "numexp": numexp,
        "accion": "Ver iniciativas",
        "desdeanyo": "",
        "desdemes": "",
        "estado": "",
        "hastaanyo": "",
        "hastames": "",
        "legislatura": str(legislature),
        "seleccion": "publicadosen",
        "sinpaginacion": "1",
        "situacion": "",
        "tipoespecifico": "",
        "tipogeneral": "1",
    }
    return f"{PARLAMENTO_ANDALUCIA_BASE_URL}{PARLAMENTO_ANDALUCIA_INITIATIVES_PATH}?{urllib.parse.urlencode(params)}"


def build_parliament_voting_results_url() -> str:
    return f"{PARLAMENTO_ANDALUCIA_BASE_URL}{PARLAMENTO_ANDALUCIA_VOTING_RESULTS_PATH}"


class ParliamentDefinitionListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[list[tuple[str, str, list[dict[str, str]]]]] = []
        self.in_dl = False
        self.in_field = ""
        self.current_text: list[str] = []
        self.current_links: list[dict[str, str]] = []
        self.current_link_href = ""
        self.current_link_text: list[str] = []
        self.current_block: list[tuple[str, str, list[dict[str, str]]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag == "dl" and "row" in attr.get("class", ""):
            self.in_dl = True
            self.current_block = []
        if not self.in_dl:
            return
        if tag in {"dt", "dd"}:
            self.in_field = tag
            self.current_text = []
            self.current_links = []
        elif tag == "a" and self.in_field == "dd":
            self.current_link_href = attr.get("href", "")
            self.current_link_text = []

    def handle_data(self, data: str) -> None:
        if not self.in_dl or not self.in_field:
            return
        self.current_text.append(data)
        if self.current_link_href:
            self.current_link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.in_dl:
            return
        if tag == "a" and self.current_link_href:
            self.current_links.append(
                {
                    "href": self.current_link_href,
                    "text": clean_line(" ".join(self.current_link_text)),
                }
            )
            self.current_link_href = ""
            self.current_link_text = []
            return
        if tag in {"dt", "dd"} and self.in_field == tag:
            self.current_block.append((tag, clean_line(" ".join(self.current_text)), list(self.current_links)))
            self.in_field = ""
            self.current_text = []
            self.current_links = []
            return
        if tag == "dl":
            if self.current_block:
                self.blocks.append(self.current_block)
            self.in_dl = False
            self.current_block = []


class ParliamentLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self.current_href = ""
        self.current_title = ""
        self.current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr = {key: value or "" for key, value in attrs}
        self.current_href = attr.get("href", "")
        self.current_title = attr.get("title", "")
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self.current_href:
            return
        self.links.append(
            {
                "href": self.current_href,
                "title": clean_line(self.current_title),
                "text": clean_line(" ".join(self.current_text)),
            }
        )
        self.current_href = ""
        self.current_title = ""
        self.current_text = []


def html_bytes_to_text(payload: bytes) -> str:
    return payload.decode("iso-8859-1", errors="replace")


def parliament_type_label(type_code: str) -> str:
    labels = {
        "DL": "Decreto-ley",
        "PL": "Proyecto de Ley",
        "PPL": "Proposicion de Ley",
        "PNLP": "Proposicion no de Ley en Pleno",
        "PPPL": "Proposicion de Ley ante Congreso",
        "ILPA": "Iniciativa legislativa popular",
        "M": "Mocion",
        "COM": "Comision/grupo de trabajo",
        "RP": "Resolucion Presidencia",
        "ROCF": "Regimen/ordenacion camara",
    }
    return labels.get(str(type_code or ""), str(type_code or "sin tipo"))


def parliament_initiative_type_code(numexp: str) -> str:
    match = re.search(r"/([A-Z]+)-\d+", str(numexp or ""))
    return match.group(1) if match else ""


def parliament_proponent_kind(proponent: str) -> str:
    normalized = normalize_label(proponent)
    if "consejo de gobierno" in normalized:
        return "executive_government"
    if "g.p." in normalized or "grupo parlamentario" in normalized:
        return "parliamentary_group"
    if "comision promotora" in normalized:
        return "popular_initiative_promoters"
    if "oficina andaluza contra el fraude" in normalized:
        return "oversight_body"
    if "pleno del parlamento" in normalized:
        return "parliament_officer"
    return "other"


def parliament_proponent_party_keys(proponent: str) -> list[str]:
    normalized = normalize_label(proponent)
    mapping = (
        ("popular de andalucia", "PP"),
        ("g.p. socialista", "PSOE-A"),
        ("vox en andalucia", "VOX"),
        ("por andalucia", "PorA"),
        ("mixto-adelante andalucia", "ADELANTE ANDALUCIA"),
    )
    return sorted({party_key for needle, party_key in mapping if needle in normalized})


def parse_parliament_initiatives_html(
    payload: bytes | str,
    *,
    legislature: int = PARLAMENTO_ANDALUCIA_LEGISLATURE,
) -> list[dict[str, Any]]:
    text = html_bytes_to_text(payload) if isinstance(payload, bytes) else str(payload or "")
    parser = ParliamentDefinitionListParser()
    parser.feed(text)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in parser.blocks:
        fields: dict[str, dict[str, Any]] = {}
        pending_label = ""
        for tag, value, links in block:
            if tag == "dt":
                pending_label = normalize_label(value).rstrip(":")
                continue
            if tag == "dd" and pending_label:
                fields[pending_label] = {"text": strip_html_text(value), "links": links}
                pending_label = ""
        numexp = str((fields.get("numero expediente") or {}).get("text") or "")
        if not numexp or numexp in seen:
            continue
        seen.add(numexp)
        proponent = str((fields.get("proponente") or {}).get("text") or "")
        excerpt = str((fields.get("extracto") or {}).get("text") or "")
        created_at = str((fields.get("fecha creacion") or {}).get("text") or "")
        type_code = parliament_initiative_type_code(numexp)
        topic_matches = classify_program_measure_topics(excerpt, limit=2)
        primary_topic_id = topic_matches[0]["topic_id"] if topic_matches else "sin_tema"
        party_keys = parliament_proponent_party_keys(proponent)
        records.append(
            {
                "initiative_id": stable_slug(f"parlamento-andalucia:{numexp}"),
                "source_id": "parlamento_andalucia_actividad_xii",
                "legislature": legislature,
                "numexp": numexp,
                "source_url": build_parliament_initiative_url(numexp, legislature=legislature),
                "created_at": created_at,
                "proponent": proponent,
                "proponent_kind": parliament_proponent_kind(proponent),
                "proponent_party_keys": party_keys,
                "type_code": type_code,
                "type_label": parliament_type_label(type_code),
                "topic_id": primary_topic_id,
                "topic_label": program_topic_label(primary_topic_id) if primary_topic_id != "sin_tema" else "Sin tema",
                "topic_matches": topic_matches,
                "evidence_excerpt": short_excerpt(excerpt, max_words=32, max_chars=300),
                "review_status": "needs_vote_outcome_link",
                "claim_status": "official_parliamentary_initiative_not_assessed",
                "interpretation_status": "needs_vote_actor_outcome_review",
                "evidence_tier": "tier_1_primary",
            }
        )
    return records


def parse_parliament_voting_documents_html(payload: bytes | str) -> list[dict[str, Any]]:
    text = html_bytes_to_text(payload) if isinstance(payload, bytes) else str(payload or "")
    parser = ParliamentLinkParser()
    parser.feed(text)
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in parser.links:
        href = str(link.get("href") or "")
        label = str(link.get("text") or "")
        title = str(link.get("title") or "")
        haystack = normalize_label(f"{label} {title} {href}")
        if "resultado votaciones" not in haystack and "sentido del voto" not in haystack:
            continue
        if "pdf.do" not in href:
            continue
        source_url = parliament_abs_url(href)
        if source_url in seen:
            continue
        seen.add(source_url)
        session_match = re.search(r"sesi[oó]n\s+n\.?[ºo]?\s*(\d+)", label, flags=re.I)
        doc_match = re.search(r"documento\s+n\.?[ºo]?\s*(\d+)", label, flags=re.I)
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", label)
        docs.append(
            {
                "document_id": stable_slug(f"parlamento-andalucia-votacion:{source_url}"),
                "label": label,
                "source_url": source_url,
                "session_number": session_match.group(1) if session_match else "",
                "document_number": doc_match.group(1) if doc_match else "",
                "date": date_match.group(1) if date_match else "",
                "evidence_tier": "tier_1_primary",
                "claim_status": "official_voting_document_not_interpreted",
                "interpretation_status": "needs_vote_table_extraction",
            }
        )
    return docs


def parliament_initiative_detail_cache_path(parl_dir: Path, initiative: dict[str, Any]) -> Path:
    key = stable_slug(
        str(initiative.get("numexp") or initiative.get("initiative_id") or initiative.get("source_url") or "unknown")
    )
    return parl_dir / "initiative_details" / f"{key}.html"


def should_collect_parliament_initiative_detail_votes(initiative: dict[str, Any]) -> bool:
    if not initiative.get("source_url"):
        return False
    topic_id = str(initiative.get("topic_id") or "")
    if topic_id in {"", "sin_tema"}:
        return False
    return True


def parse_parliament_initiative_detail_vote_documents(
    payload: bytes | str,
    initiative: dict[str, Any],
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for document in parse_parliament_voting_documents_html(payload):
        updated = dict(document)
        updated.update(
            {
                "discovery_source": "initiative_detail",
                "initiative_id": initiative.get("initiative_id") or "",
                "initiative_numexp": initiative.get("numexp") or "",
                "initiative_source_url": initiative.get("source_url") or "",
                "initiative_topic_id": initiative.get("topic_id") or "",
                "initiative_topic_label": initiative.get("topic_label") or "",
            }
        )
        docs.append(updated)
    return docs


def collect_parliament_initiative_detail_vote_documents(
    initiatives: list[dict[str, Any]],
    *,
    parl_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    documents: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for initiative in initiatives:
        if not should_collect_parliament_initiative_detail_votes(initiative):
            continue
        source_url = str(initiative.get("source_url") or "")
        cache_path = parliament_initiative_detail_cache_path(parl_dir, initiative)
        payload = cache_path.read_bytes() if cache_path.exists() else b""
        status = "cached" if payload else "missing"
        if not payload and not no_network:
            try:
                payload, _content_type = http_get_bytes(source_url, timeout=timeout, max_attempts=1)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(payload)
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                errors.append({"url": source_url, "error": f"{type(exc).__name__}: {exc}"})
                if strict_network:
                    raise
        vote_documents = (
            parse_parliament_initiative_detail_vote_documents(payload, initiative)
            if payload
            else []
        )
        documents.extend(vote_documents)
        pages.append(
            {
                "initiative_id": initiative.get("initiative_id") or "",
                "numexp": initiative.get("numexp") or "",
                "topic_id": initiative.get("topic_id") or "",
                "topic_label": initiative.get("topic_label") or "",
                "source_url": source_url,
                "cache_path": str(cache_path) if payload else "",
                "status": status,
                "vote_documents_total": len(vote_documents),
                "vote_document_urls": [str(document.get("source_url") or "") for document in vote_documents],
            }
        )
    return documents, pages, errors


def dedupe_parliament_voting_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents:
        source_url = str(document.get("source_url") or "")
        key = source_url or str(document.get("document_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(document)
    return deduped


def parliament_vote_row_key(label: str) -> str:
    return stable_slug(str(label or "").replace("SI", "si"))


def parse_parliament_vote_count_line(line: str) -> tuple[str, list[int]] | None:
    clean = normalize_label(line).upper()
    clean = clean.replace("SÍ", "SI")
    clean = re.sub(r"\s+", " ", clean).strip()
    for label in PARLAMENTO_ANDALUCIA_VOTE_ROW_LABELS:
        if clean == label or clean.startswith(f"{label} "):
            values = [int(value) for value in re.findall(r"\b\d{3}\b", clean[len(label) :])]
            if len(values) >= 6:
                return label, values[:6]
    return None


def parse_parliament_vote_count_table(block: str) -> dict[str, dict[str, int]]:
    table: dict[str, dict[str, int]] = {}
    columns = ("total", "pp", "ps", "vo", "pa", "aa")
    for line in block.splitlines():
        parsed = parse_parliament_vote_count_line(line)
        if not parsed:
            continue
        label, values = parsed
        table[parliament_vote_row_key(label)] = dict(zip(columns, values, strict=False))
    return table


def parliament_group_code_from_line(line: str) -> str:
    normalized = normalize_label(line)
    if "g.p." not in normalized:
        return ""
    for needle, group_code in PARLAMENTO_ANDALUCIA_VOTE_GROUP_HEADERS:
        if needle in normalized:
            return group_code
    return ""


def parliament_member_vote_position_from_line(line: str) -> str:
    if "***" not in line:
        return ""
    label = normalize_label(line.replace("*", " "))
    return PARLAMENTO_ANDALUCIA_MEMBER_POSITION_LABELS.get(label, "")


def parse_parliament_vote_member_line(line: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not re.search(r"\d{3}\s+\S", line):
        return rows
    for match in re.finditer(r"(?P<delegated>\(\*\))?\s*(?P<number>\d{3})\s+(?P<name>.*?)(?=\s+(?:\(\*\)\s*)?\d{3}\s+\S|$)", line):
        name = clean_line(match.group("name"))
        if not name or len(name) < 4:
            continue
        if any(token in normalize_label(name) for token in ("parlamento de andalucia", "legislatura")):
            continue
        rows.append(
            {
                "member_number": match.group("number"),
                "member_name": name,
                "member_name_inverted": invert_vote_member_name(name),
                "member_name_match_key": normalize_person_name_for_vote_match(invert_vote_member_name(name)),
                "delegated_vote": bool(match.group("delegated")),
            }
        )
    return rows


def parse_parliament_vote_member_votes(
    event_base: dict[str, Any],
    block: str,
) -> list[dict[str, Any]]:
    votes: list[dict[str, Any]] = []
    current_group_code = ""
    current_position = ""
    for raw_line in block.splitlines():
        group_code = parliament_group_code_from_line(raw_line)
        if group_code:
            current_group_code = group_code
            current_position = ""
            continue
        position = parliament_member_vote_position_from_line(raw_line)
        if position:
            current_position = position
            continue
        if not current_group_code or not current_position:
            continue
        group_meta = PARLAMENTO_ANDALUCIA_VOTE_GROUPS[current_group_code]
        for row in parse_parliament_vote_member_line(raw_line):
            vote_member_id = stable_slug(
                f"{event_base['vote_event_id']}:{current_group_code}:{row['member_number']}:{current_position}"
            )
            votes.append(
                {
                    "vote_member_id": vote_member_id,
                    "vote_event_id": event_base["vote_event_id"],
                    "document_id": event_base["document_id"],
                    "source_url": event_base["source_url"],
                    "date": event_base["date"],
                    "time": event_base["time"],
                    "session_number": event_base["session_number"],
                    "vote_number": event_base["vote_number"],
                    "numexp": event_base["numexp"],
                    "title": event_base["title"],
                    "group_code": current_group_code,
                    "party_key": group_meta["party_key"],
                    "party_acronym": group_meta["party_acronym"],
                    "party_label": group_meta["party_label"],
                    "vote_position": current_position,
                    "evidence_tier": "tier_1_primary",
                    "claim_status": "official_member_vote_not_interpreted",
                    "interpretation_status": "needs_candidate_identity_and_legal_effect_review",
                    **row,
                }
            )
    return votes


def parliament_party_vote_position(row: dict[str, Any]) -> str:
    present = int(row.get("presentes") or 0)
    if present <= 0:
        return "absent"
    counts = {
        "si": int(row.get("si") or 0),
        "no": int(row.get("no") or 0),
        "abstenciones": int(row.get("abstenciones") or 0),
        "blancos": int(row.get("blancos") or 0),
    }
    max_value = max(counts.values())
    if max_value <= 0:
        return "unknown"
    winners = [key for key, value in counts.items() if value == max_value]
    if len(winners) != 1:
        return "mixed"
    return winners[0]


def parliament_party_vote_totals(table: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for group_code, meta in PARLAMENTO_ANDALUCIA_VOTE_GROUPS.items():
        key = group_code.lower()
        row = {
            "group_code": group_code,
            "party_key": meta["party_key"],
            "party_acronym": meta["party_acronym"],
            "party_label": meta["party_label"],
            "si": int((table.get("total-si") or {}).get(key) or 0),
            "no": int((table.get("total-no") or {}).get(key) or 0),
            "abstenciones": int((table.get("total-abstenciones") or {}).get(key) or 0),
            "blancos": int((table.get("total-blancos") or {}).get(key) or 0),
            "presentes": int((table.get("presentes") or {}).get(key) or 0),
            "ausentes": int((table.get("diputados-ausentes") or {}).get(key) or 0),
            "total_diputados": int((table.get("total-diputados") or {}).get(key) or 0),
        }
        row["dominant_position"] = parliament_party_vote_position(row)
        row["position_status"] = "raw_group_tally_not_interpreted"
        out.append(row)
    return out


def parse_parliament_vote_events_text(document: dict[str, Any], text: str) -> list[dict[str, Any]]:
    chunks = re.split(r"(?=PARLAMENTO DE ANDALUC[ÍI]A\s*-\s*XII LEGISLATURA)", str(text or ""))
    events: list[dict[str, Any]] = []
    for chunk in chunks:
        if "VOTACI" not in chunk or "TÍTULO GENERAL DEL DEBATE" not in chunk:
            continue
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})", chunk)
        vote_match = re.search(r"VOTACI[ÓO]N\s+N[ºO]?\s+(\d+)", chunk)
        session_match = re.search(r"SESI[ÓO]N\s+(\d+)", chunk)
        protocol_match = re.search(r"PROTOCOLO\s+(\d+)", chunk)
        if not date_match or not vote_match:
            continue
        title_match = re.search(
            r"T[ÍI]TULO GENERAL DEL DEBATE\s+(.*?)(?:\n\s*\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})",
            chunk,
            flags=re.S,
        )
        title = ""
        if title_match:
            title = clean_line(" ".join(line.strip() for line in title_match.group(1).splitlines() if line.strip()))
        presiding_match = re.search(r"PRESIDE LA VOTACI[ÓO]N:\s*(.+)", chunk)
        table = parse_parliament_vote_count_table(chunk)
        total_si = int((table.get("total-si") or {}).get("total") or 0)
        total_no = int((table.get("total-no") or {}).get("total") or 0)
        total_abstenciones = int((table.get("total-abstenciones") or {}).get("total") or 0)
        total_blancos = int((table.get("total-blancos") or {}).get("total") or 0)
        majority_side = "si" if total_si > total_no else "no" if total_no > total_si else "tie_or_no_signal"
        numexp_match = re.search(r"\b\d{2}-\d{2}/[A-Z]+-\d{6}\b", title)
        vote_number = vote_match.group(1)
        event_id = stable_slug(f"{document.get('document_id') or document.get('source_url')}:{vote_number}")
        event = {
            "vote_event_id": event_id,
            "document_id": document.get("document_id") or "",
            "source_url": document.get("source_url") or "",
            "date": date_match.group(1),
            "time": date_match.group(2),
            "session_number": session_match.group(1) if session_match else document.get("session_number") or "",
            "protocol": protocol_match.group(1) if protocol_match else "",
            "vote_number": vote_number,
            "title": title,
            "numexp": numexp_match.group(0) if numexp_match else "",
            "presiding": clean_line(presiding_match.group(1)) if presiding_match else "",
            "total_si": total_si,
            "total_no": total_no,
            "total_abstenciones": total_abstenciones,
            "total_blancos": total_blancos,
            "majority_side": majority_side,
            "party_vote_totals": parliament_party_vote_totals(table),
            "raw_count_table": table,
            "evidence_tier": "tier_1_primary",
            "claim_status": "official_vote_count_not_interpreted",
            "interpretation_status": "needs_vote_context_and_outcome_review",
            "review_status": "needs_legal_effect_actor_and_impact_review",
            "review_questions": list(PARLIAMENT_VOTE_REVIEW_QUESTIONS),
        }
        member_votes = parse_parliament_vote_member_votes(event, chunk)
        event["member_votes_total"] = len(member_votes)
        event["member_votes"] = member_votes
        events.append(event)
    return events


def compact_parliament_initiative_for_vote(initiative: dict[str, Any]) -> dict[str, Any]:
    return {
        "initiative_id": initiative.get("initiative_id") or "",
        "numexp": initiative.get("numexp") or "",
        "source_url": initiative.get("source_url") or "",
        "type_code": initiative.get("type_code") or "",
        "type_label": initiative.get("type_label") or "",
        "topic_id": initiative.get("topic_id") or "",
        "topic_label": initiative.get("topic_label") or "",
        "proponent": initiative.get("proponent") or "",
        "proponent_kind": initiative.get("proponent_kind") or "",
        "proponent_party_keys": list(initiative.get("proponent_party_keys") or []),
        "evidence_excerpt": initiative.get("evidence_excerpt") or "",
        "claim_status": initiative.get("claim_status") or "",
        "interpretation_status": initiative.get("interpretation_status") or "",
    }


def enrich_parliament_vote_events_with_initiatives(
    vote_events: list[dict[str, Any]],
    initiatives: list[dict[str, Any]],
) -> int:
    initiatives_by_numexp = {
        str(initiative.get("numexp") or ""): initiative
        for initiative in initiatives
        if initiative.get("numexp")
    }
    matched_total = 0
    for event in vote_events:
        numexp = str(event.get("numexp") or "")
        initiative = initiatives_by_numexp.get(numexp)
        if not numexp:
            event["initiative_match_status"] = "missing_numexp"
            continue
        if not initiative:
            event["initiative_match_status"] = "not_found_in_official_initiative_index"
            continue
        matched_total += 1
        initiative_ref = compact_parliament_initiative_for_vote(initiative)
        event.update(
            {
                "initiative_match_status": "matched_official_initiative",
                "initiative": initiative_ref,
                "initiative_id": initiative_ref["initiative_id"],
                "initiative_source_url": initiative_ref["source_url"],
                "initiative_type_code": initiative_ref["type_code"],
                "initiative_type_label": initiative_ref["type_label"],
                "initiative_topic_id": initiative_ref["topic_id"],
                "initiative_topic_label": initiative_ref["topic_label"],
                "initiative_proponent": initiative_ref["proponent"],
                "initiative_proponent_kind": initiative_ref["proponent_kind"],
                "initiative_proponent_party_keys": initiative_ref["proponent_party_keys"],
            }
        )
        for member_vote in event.get("member_votes") or []:
            if not isinstance(member_vote, dict):
                continue
            member_vote.update(
                {
                    "initiative_match_status": "matched_official_initiative",
                    "initiative_id": initiative_ref["initiative_id"],
                    "initiative_source_url": initiative_ref["source_url"],
                    "initiative_type_code": initiative_ref["type_code"],
                    "initiative_type_label": initiative_ref["type_label"],
                    "initiative_topic_id": initiative_ref["topic_id"],
                    "initiative_topic_label": initiative_ref["topic_label"],
                    "initiative_proponent_kind": initiative_ref["proponent_kind"],
                }
            )
    for event in vote_events:
        apply_parliament_vote_context_triage(event)
    return matched_total


def infer_parliament_vote_type_code(event: dict[str, Any]) -> tuple[str, str]:
    existing = str(event.get("initiative_type_code") or "")
    if existing:
        return existing, "official_initiative"
    numexp_type = parliament_initiative_type_code(str(event.get("numexp") or ""))
    if numexp_type:
        return numexp_type, "numexp"
    normalized_title = normalize_label(event.get("title"))
    if "decreto-ley" in normalized_title:
        return "DL", "title_keyword"
    if "proyecto de ley" in normalized_title:
        return "PL", "title_keyword"
    if "proposicion no de ley" in normalized_title:
        return "PNLP", "title_keyword"
    if "proposicion de ley" in normalized_title:
        return "PPL", "title_keyword"
    if "mocion" in normalized_title:
        return "M", "title_keyword"
    if "solicitud de creacion" in normalized_title and (
        "comision" in normalized_title or "grupo de trabajo" in normalized_title
    ):
        return "COM", "title_keyword"
    return "sin_tipo", "no_type_signal"


def classify_parliament_vote_topic(event: dict[str, Any]) -> dict[str, Any]:
    initiative_topic_id = str(event.get("initiative_topic_id") or "")
    if initiative_topic_id and initiative_topic_id != "sin_tema":
        return {
            "topic_id": initiative_topic_id,
            "topic_label": event.get("initiative_topic_label") or program_topic_label(initiative_topic_id),
            "topic_source": "official_initiative",
            "topic_matches": list((event.get("initiative") or {}).get("topic_matches") or []),
        }
    topic_matches = classify_program_measure_topics(
        " ".join(
            str(value or "")
            for value in (
                event.get("title"),
                (event.get("initiative") or {}).get("evidence_excerpt"),
            )
        ),
        limit=2,
    )
    if topic_matches:
        primary = topic_matches[0]
        return {
            "topic_id": primary["topic_id"],
            "topic_label": primary["topic_label"],
            "topic_source": "vote_title_keyword_triage",
            "topic_matches": topic_matches,
        }
    return {
        "topic_id": "sin_tema",
        "topic_label": "Sin tema",
        "topic_source": "no_topic_signal",
        "topic_matches": [],
    }


def classify_parliament_vote_legal_effect(event: dict[str, Any]) -> dict[str, Any]:
    type_code = str(event.get("initiative_type_code") or "sin_tipo")
    title = str(event.get("title") or "")
    normalized_title = normalize_label(title)
    majority = str(event.get("majority_side") or "")
    type_source = str(event.get("initiative_type_source") or "unknown")
    status = "rule_triaged_needs_review"
    confidence = "medium"
    pattern = "generic_type"
    kind = "unclassified_vote"
    label = "efecto legal pendiente"

    def passed_rejected(passed_kind: str, rejected_kind: str, passed_label: str, rejected_label: str) -> tuple[str, str]:
        if majority == "si":
            return passed_kind, passed_label
        if majority == "no":
            return rejected_kind, rejected_label
        return "no_clear_majority", "sin mayoria clara"

    if type_code in {"PL", "PPL", "PPPL", "ILPA"}:
        if "debate final" in normalized_title:
            pattern = "debate_final"
            confidence = "high"
            kind, label = passed_rejected(
                "law_final_approval_vote_passed",
                "law_final_approval_vote_rejected",
                "aprobacion final de ley",
                "rechazo de aprobacion final de ley",
            )
        elif "toma en consideracion" in normalized_title:
            pattern = "toma_en_consideracion"
            kind, label = passed_rejected(
                "bill_consideration_vote_passed",
                "bill_consideration_vote_rejected",
                "toma en consideracion aprobada",
                "toma en consideracion rechazada",
            )
        elif "enmienda" in normalized_title:
            pattern = "enmienda"
            kind, label = passed_rejected(
                "bill_amendment_vote_passed",
                "bill_amendment_vote_rejected",
                "enmienda aprobada",
                "enmienda rechazada",
            )
        else:
            kind, label = passed_rejected(
                "legislative_bill_vote_passed",
                "legislative_bill_vote_rejected",
                "voto legislativo aprobado",
                "voto legislativo rechazado",
            )
    elif type_code == "DL":
        if "convalidacion" in normalized_title:
            pattern = "convalidacion_decreto_ley"
            confidence = "high"
            kind, label = passed_rejected(
                "decree_law_validation_vote_passed",
                "decree_law_validation_vote_not_passed_or_derogation_supported",
                "convalidacion de decreto-ley aprobada",
                "voto no favorable en convalidacion de decreto-ley",
            )
        else:
            kind, label = passed_rejected(
                "decree_law_vote_passed",
                "decree_law_vote_rejected",
                "voto sobre decreto-ley aprobado",
                "voto sobre decreto-ley rechazado",
            )
    elif type_code == "PNLP":
        pattern = "proposicion_no_de_ley"
        kind, label = passed_rejected(
            "nonbinding_resolution_vote_passed",
            "nonbinding_resolution_vote_rejected",
            "resolucion no vinculante aprobada",
            "resolucion no vinculante rechazada",
        )
    elif type_code == "M":
        pattern = "mocion"
        kind, label = passed_rejected(
            "motion_resolution_vote_passed",
            "motion_resolution_vote_rejected",
            "mocion aprobada",
            "mocion rechazada",
        )
    elif type_code == "COM":
        pattern = "committee_or_group_creation"
        kind, label = passed_rejected(
            "parliament_work_body_creation_vote_passed",
            "parliament_work_body_creation_vote_rejected",
            "creacion de organo de trabajo aprobada",
            "creacion de organo de trabajo rechazada",
        )
    else:
        status = "unreviewed"
        confidence = "unknown"
        pattern = "no_rule"

    return {
        "legal_effect_status": status,
        "legal_effect_kind": kind,
        "legal_effect_label": label,
        "legal_effect_confidence": confidence,
        "legal_effect_basis": f"type={type_code};majority={majority or 'sin_mayoria'};pattern={pattern};type_source={type_source}",
    }


def apply_parliament_vote_context_triage(event: dict[str, Any]) -> None:
    type_code, type_source = infer_parliament_vote_type_code(event)
    event["initiative_type_code"] = type_code
    event["initiative_type_label"] = event.get("initiative_type_label") or parliament_type_label(type_code)
    event["initiative_type_source"] = type_source
    topic = classify_parliament_vote_topic(event)
    event.update(topic)
    event.update(classify_parliament_vote_legal_effect(event))
    for member_vote in event.get("member_votes") or []:
        if not isinstance(member_vote, dict):
            continue
        member_vote.update(
            {
                "initiative_type_code": event.get("initiative_type_code") or "",
                "initiative_type_label": event.get("initiative_type_label") or "",
                "topic_id": event.get("topic_id") or "",
                "topic_label": event.get("topic_label") or "",
                "topic_source": event.get("topic_source") or "",
                "legal_effect_kind": event.get("legal_effect_kind") or "",
            }
        )


def summarize_parliament_vote_legal_effects(vote_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for event in vote_events:
        kind = str(event.get("legal_effect_kind") or "unclassified_vote")
        acc = totals.setdefault(
            kind,
            {
                "legal_effect_kind": kind,
                "legal_effect_label": event.get("legal_effect_label") or kind.replace("_", " "),
                "vote_events_total": 0,
                "status_counts": Counter(),
                "confidence_counts": Counter(),
                "initiative_type_counts": Counter(),
                "topic_counts": Counter(),
                "claim_status": "legal_effect_rule_triage_not_impact_claim",
                "interpretation_status": "needs_human_review_before_merit_or_responsibility_claim",
            },
        )
        acc["vote_events_total"] += 1
        acc["status_counts"][str(event.get("legal_effect_status") or "sin_estado")] += 1
        acc["confidence_counts"][str(event.get("legal_effect_confidence") or "sin_confianza")] += 1
        acc["initiative_type_counts"][str(event.get("initiative_type_code") or "sin_tipo")] += 1
        acc["topic_counts"][str(event.get("topic_id") or "sin_tema")] += 1
    out: list[dict[str, Any]] = []
    for row in totals.values():
        normalized = dict(row)
        normalized["status_counts"] = [
            {"key": key, "label": key.replace("_", " "), "count": count}
            for key, count in sorted(row["status_counts"].items(), key=lambda item: (-item[1], item[0]))
        ]
        normalized["confidence_counts"] = [
            {"key": key, "label": key.replace("_", " "), "count": count}
            for key, count in sorted(row["confidence_counts"].items(), key=lambda item: (-item[1], item[0]))
        ]
        normalized["initiative_type_counts"] = [
            {"key": key, "label": parliament_type_label(key), "count": count}
            for key, count in sorted(row["initiative_type_counts"].items(), key=lambda item: (-item[1], item[0]))
        ]
        normalized["topic_counts"] = [
            {"key": key, "label": program_topic_label(key) if key != "sin_tema" else "Sin tema", "count": count}
            for key, count in sorted(row["topic_counts"].items(), key=lambda item: (-item[1], item[0]))
        ]
        out.append(normalized)
    return sorted(out, key=lambda row: (-int(row["vote_events_total"]), row["legal_effect_label"]))


def summarize_parliament_party_vote_positions(vote_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for event in vote_events:
        for row in event.get("party_vote_totals") or []:
            party_key = str(row.get("party_key") or "")
            if not party_key:
                continue
            acc = totals.setdefault(
                party_key,
                {
                    "party_key": party_key,
                    "party_acronym": row.get("party_acronym") or "",
                    "party_label": row.get("party_label") or "",
                    "vote_events_total": 0,
                    "si": 0,
                    "no": 0,
                    "abstenciones": 0,
                    "blancos": 0,
                    "dominant_position_counts": Counter(),
                },
            )
            acc["vote_events_total"] += 1
            for key in ("si", "no", "abstenciones", "blancos"):
                acc[key] += int(row.get(key) or 0)
            acc["dominant_position_counts"][str(row.get("dominant_position") or "unknown")] += 1
    out = []
    for row in totals.values():
        normalized = dict(row)
        normalized["dominant_position_counts"] = [
            {"key": key, "count": count}
            for key, count in sorted(
                normalized["dominant_position_counts"].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        out.append(normalized)
    return sorted(out, key=lambda row: (-int(row["vote_events_total"]), row["party_acronym"]))


def summarize_parliament_party_topic_vote_positions(vote_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str], dict[str, Any]] = {}
    for event in vote_events:
        topic_id = str(event.get("topic_id") or event.get("initiative_topic_id") or "")
        if not topic_id:
            continue
        topic_label = str(event.get("topic_label") or event.get("initiative_topic_label") or program_topic_label(topic_id))
        for row in event.get("party_vote_totals") or []:
            party_key = str(row.get("party_key") or "")
            if not party_key:
                continue
            acc = totals.setdefault(
                (party_key, topic_id),
                {
                    "party_key": party_key,
                    "party_acronym": row.get("party_acronym") or "",
                    "party_label": row.get("party_label") or "",
                    "topic_id": topic_id,
                    "topic_label": topic_label,
                    "vote_events_total": 0,
                    "si": 0,
                    "no": 0,
                    "abstenciones": 0,
                    "blancos": 0,
                    "dominant_position_counts": Counter(),
                    "initiative_type_counts": Counter(),
                    "legal_effect_counts": Counter(),
                    "topic_source_counts": Counter(),
                    "claim_status": "official_vote_count_not_interpreted",
                    "interpretation_status": "needs_legal_effect_actor_and_impact_review",
                },
            )
            acc["vote_events_total"] += 1
            for key in ("si", "no", "abstenciones", "blancos"):
                acc[key] += int(row.get(key) or 0)
            acc["dominant_position_counts"][str(row.get("dominant_position") or "unknown")] += 1
            acc["initiative_type_counts"][str(event.get("initiative_type_code") or "sin_tipo")] += 1
            acc["legal_effect_counts"][str(event.get("legal_effect_kind") or "unclassified_vote")] += 1
            acc["topic_source_counts"][str(event.get("topic_source") or "sin_fuente")] += 1
    out = []
    for row in totals.values():
        normalized = dict(row)
        normalized["dominant_position_counts"] = [
            {"key": key, "count": count}
            for key, count in sorted(
                normalized["dominant_position_counts"].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        normalized["initiative_type_counts"] = [
            {"key": key, "label": parliament_type_label(key), "count": count}
            for key, count in sorted(
                normalized["initiative_type_counts"].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        normalized["legal_effect_counts"] = [
            {"key": key, "label": key.replace("_", " "), "count": count}
            for key, count in sorted(
                normalized["legal_effect_counts"].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        normalized["topic_source_counts"] = [
            {"key": key, "label": key.replace("_", " "), "count": count}
            for key, count in sorted(
                normalized["topic_source_counts"].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        out.append(normalized)
    return sorted(
        out,
        key=lambda row: (-int(row["vote_events_total"]), row["topic_label"], row["party_acronym"]),
    )


def compact_parliament_vote_party_positions(rows: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for row in rows:
        party = str(row.get("party_acronym") or row.get("party_label") or row.get("party_key") or "sin_partido")
        position = str(row.get("dominant_position") or "unknown")
        out.append(
            "{party}:{position}:si={si},no={no},abs={abs}".format(
                party=party,
                position=position,
                si=int(row.get("si") or 0),
                no=int(row.get("no") or 0),
                abs=int(row.get("abstenciones") or 0),
            )
        )
    return "; ".join(out)


def compact_public_parliament_vote_event(event: dict[str, Any]) -> dict[str, Any]:
    party_vote_totals = [row for row in event.get("party_vote_totals") or [] if isinstance(row, dict)]
    return {
        "vote_event_id": event.get("vote_event_id") or "",
        "document_id": event.get("document_id") or "",
        "source_url": event.get("source_url") or "",
        "date": event.get("date") or "",
        "session_number": event.get("session_number") or "",
        "vote_number": event.get("vote_number") or "",
        "numexp": event.get("numexp") or "",
        "title": compact_evidence_quote(event.get("title"), max_words=26, max_chars=240),
        "initiative_id": event.get("initiative_id") or "",
        "initiative_source_url": event.get("initiative_source_url") or "",
        "initiative_match_status": event.get("initiative_match_status") or "",
        "initiative_type_code": event.get("initiative_type_code") or "",
        "initiative_type_label": event.get("initiative_type_label") or "",
        "topic_id": event.get("topic_id") or "",
        "topic_label": event.get("topic_label") or "",
        "topic_source": event.get("topic_source") or "",
        "majority_side": event.get("majority_side") or "",
        "total_si": int(event.get("total_si") or 0),
        "total_no": int(event.get("total_no") or 0),
        "total_abstenciones": int(event.get("total_abstenciones") or 0),
        "total_blancos": int(event.get("total_blancos") or 0),
        "member_votes_total": int(event.get("member_votes_total") or 0),
        "party_positions_summary": compact_parliament_vote_party_positions(party_vote_totals),
        "member_vote_samples": list(event.get("member_vote_samples") or [])[:3],
        "legal_effect_status": event.get("legal_effect_status") or "",
        "legal_effect_kind": event.get("legal_effect_kind") or "",
        "legal_effect_label": event.get("legal_effect_label") or "",
        "review_status": event.get("review_status") or "",
        "effect_outcome": event.get("effect_outcome") or "",
        "claim_status": event.get("claim_status") or "",
        "interpretation_status": event.get("interpretation_status") or "",
    }


def compact_public_parliament_vote_review_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_item_id": item.get("review_item_id") or "",
        "vote_event_id": item.get("vote_event_id") or "",
        "priority_rank": int(item.get("priority_rank") or 0),
        "priority_score": int(item.get("priority_score") or 0),
        "review_batch_id": item.get("review_batch_id") or "",
        "date": item.get("date") or "",
        "session_number": item.get("session_number") or "",
        "vote_number": item.get("vote_number") or "",
        "numexp": item.get("numexp") or "",
        "title": compact_evidence_quote(item.get("title"), max_words=26, max_chars=240),
        "topic_id": item.get("topic_id") or "",
        "topic_label": item.get("topic_label") or "",
        "topic_source": item.get("topic_source") or "",
        "initiative_id": item.get("initiative_id") or "",
        "initiative_source_url": item.get("initiative_source_url") or "",
        "initiative_match_status": item.get("initiative_match_status") or "",
        "initiative_type_code": item.get("initiative_type_code") or "",
        "initiative_type_label": item.get("initiative_type_label") or "",
        "majority_side": item.get("majority_side") or "",
        "total_si": int(item.get("total_si") or 0),
        "total_no": int(item.get("total_no") or 0),
        "total_abstenciones": int(item.get("total_abstenciones") or 0),
        "total_blancos": int(item.get("total_blancos") or 0),
        "member_votes_total": int(item.get("member_votes_total") or 0),
        "party_positions_summary": item.get("party_positions_summary") or "",
        "member_vote_samples": list(item.get("member_vote_samples") or [])[:3],
        "legal_effect_status": item.get("legal_effect_status") or "",
        "legal_effect_kind": item.get("legal_effect_kind") or "",
        "legal_effect_label": item.get("legal_effect_label") or "",
        "legal_effect_confidence": item.get("legal_effect_confidence") or "",
        "impact_status": item.get("impact_status") or "",
        "responsibility_status": item.get("responsibility_status") or "",
        "candidate_direction": item.get("candidate_direction") or "",
        "review_status": item.get("review_status") or "",
        "effect_outcome": item.get("effect_outcome") or "",
        "review_summary": compact_evidence_quote(item.get("review_summary"), max_words=30, max_chars=260),
        "review_confidence": item.get("review_confidence") or "",
        "claim_status": item.get("claim_status") or "",
        "source_url": item.get("source_url") or "",
        "source_locator": item.get("source_locator") or "",
    }


def compact_public_parliament_vote_review_packet(packet: dict[str, Any]) -> dict[str, Any]:
    public_packet = {key: value for key, value in packet.items() if key not in {"priority_items", "batches"}}
    public_packet["priority_items"] = [
        compact_public_parliament_vote_review_item(item)
        for item in list(packet.get("priority_items") or [])[:PARLIAMENT_VOTE_REVIEW_PRIORITY_ITEMS_LIMIT]
        if isinstance(item, dict)
    ]
    public_packet["batches"] = [
        {key: value for key, value in batch.items() if key != "items"}
        for batch in packet.get("batches") or []
        if isinstance(batch, dict)
    ]
    public_packet["public_compaction"] = {
        "status": "full_review_items_available_in_csv_artifact",
        "queue_sample_limit": PUBLIC_PARLIAMENT_VOTE_REVIEW_QUEUE_LIMIT,
        "topic_queue_sample_limit": PUBLIC_PARLIAMENT_VOTE_REVIEW_QUEUE_TOPIC_LIMIT,
    }
    return public_packet


def build_public_parliament_vote_queue_by_topic(queue: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_topic: dict[str, list[dict[str, Any]]] = {}
    for item in queue:
        if not isinstance(item, dict):
            continue
        topic_id = str(item.get("topic_id") or "sin_tema")
        bucket = by_topic.setdefault(topic_id, [])
        if len(bucket) >= PUBLIC_PARLIAMENT_VOTE_REVIEW_QUEUE_TOPIC_LIMIT:
            continue
        bucket.append(compact_public_parliament_vote_review_item(item))
    return by_topic


def build_published_parliament_report(parliament_report: dict[str, Any]) -> dict[str, Any]:
    published = dict(parliament_report)
    full_vote_events = [row for row in parliament_report.get("vote_events") or [] if isinstance(row, dict)]
    full_vote_queue = [row for row in parliament_report.get("vote_impact_review_queue") or [] if isinstance(row, dict)]
    published["member_vote_samples"] = [
        compact_member_vote_sample(row) for row in list(parliament_report.get("member_votes") or [])[:24]
    ]
    published.pop("member_votes", None)
    published["vote_events"] = [
        compact_public_parliament_vote_event(row) for row in full_vote_events[:PUBLIC_PARLIAMENT_VOTE_EVENTS_LIMIT]
    ]
    published["vote_events_public_sample_limit"] = PUBLIC_PARLIAMENT_VOTE_EVENTS_LIMIT
    published["vote_impact_review_queue"] = [
        compact_public_parliament_vote_review_item(row)
        for row in full_vote_queue[:PUBLIC_PARLIAMENT_VOTE_REVIEW_QUEUE_LIMIT]
    ]
    published["vote_impact_review_queue_public_sample_limit"] = PUBLIC_PARLIAMENT_VOTE_REVIEW_QUEUE_LIMIT
    published["vote_impact_review_queue_by_topic"] = build_public_parliament_vote_queue_by_topic(full_vote_queue)
    published["vote_impact_review_queue_by_topic_public_sample_limit"] = (
        PUBLIC_PARLIAMENT_VOTE_REVIEW_QUEUE_TOPIC_LIMIT
    )
    published["vote_impact_review_packet"] = compact_public_parliament_vote_review_packet(
        parliament_report.get("vote_impact_review_packet") or {}
    )
    return published


def parliament_vote_review_margin_points(item: dict[str, Any]) -> int:
    yes = int(item.get("total_si") or 0)
    no = int(item.get("total_no") or 0)
    if yes == 0 and no == 0:
        return 0
    margin = abs(yes - no)
    if margin <= 2:
        return 24
    if margin <= 5:
        return 18
    if margin <= 10:
        return 14
    if margin <= 20:
        return 8
    return 4


def parliament_vote_review_priority_score(item: dict[str, Any]) -> int:
    type_code = str(item.get("initiative_type_code") or "sin_tipo")
    topic_id = str(item.get("topic_id") or "sin_tema")
    return (
        PARLIAMENT_VOTE_REVIEW_TYPE_PRIORITY.get(type_code, PARLIAMENT_VOTE_REVIEW_TYPE_PRIORITY["sin_tipo"])
        + BOJA_IMPACT_REVIEW_TOPIC_PRIORITY.get(topic_id, 8)
        + parliament_vote_review_margin_points(item)
        + (14 if item.get("initiative_match_status") == "matched_official_initiative" else 0)
        + (10 if int(item.get("member_votes_total") or 0) > 0 else 0)
        + (8 if item.get("party_positions_summary") else 0)
        + boja_review_recency_points(item.get("date"))
    )


def parliament_vote_review_priority_reason(item: dict[str, Any], score: int) -> str:
    type_code = str(item.get("initiative_type_code") or "sin_tipo")
    topic_id = str(item.get("topic_id") or "sin_tema")
    type_points = PARLIAMENT_VOTE_REVIEW_TYPE_PRIORITY.get(type_code, PARLIAMENT_VOTE_REVIEW_TYPE_PRIORITY["sin_tipo"])
    topic_points = BOJA_IMPACT_REVIEW_TOPIC_PRIORITY.get(topic_id, 8)
    margin_points = parliament_vote_review_margin_points(item)
    initiative_points = 14 if item.get("initiative_match_status") == "matched_official_initiative" else 0
    member_points = 10 if int(item.get("member_votes_total") or 0) > 0 else 0
    party_points = 8 if item.get("party_positions_summary") else 0
    recency_points = boja_review_recency_points(item.get("date"))
    return (
        f"tipo={type_code}:{type_points}; "
        f"tema={topic_id}:{topic_points}; "
        f"margen_si_no={abs(int(item.get('total_si') or 0) - int(item.get('total_no') or 0))}:{margin_points}; "
        f"expediente={item.get('initiative_match_status') or 'sin_match'}:{initiative_points}; "
        f"nominal={int(item.get('member_votes_total') or 0)}:{member_points}; "
        f"grupos={party_points}; "
        f"fecha={item.get('date') or 'sin_fecha'}:{recency_points}; "
        f"total={score}"
    )


def parliament_vote_review_count_rows(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(str(item.get(key) or "sin_dato") for item in items)
    out: list[dict[str, Any]] = []
    for value, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
        if key == "topic_id" and value != "sin_dato":
            label = program_topic_label(value)
        elif key == "initiative_type_code" and value != "sin_dato":
            label = parliament_type_label(value)
        elif key == "legal_effect_kind" and value != "sin_dato":
            label = value.replace("_", " ")
        else:
            label = value.replace("_", " ")
        out.append({"key": value, "label": label, "count": count})
    return out


def build_parliament_vote_review_item(event: dict[str, Any]) -> dict[str, Any]:
    party_vote_totals = [dict(row) for row in list(event.get("party_vote_totals") or []) if isinstance(row, dict)]
    topic_id = str(event.get("topic_id") or event.get("initiative_topic_id") or "sin_tema")
    type_code = str(event.get("initiative_type_code") or "sin_tipo")
    return {
        "review_item_id": stable_slug(f"parliament-vote-impact-review:{event.get('vote_event_id') or ''}"),
        "vote_event_id": event.get("vote_event_id") or "",
        "date": event.get("date") or "",
        "session_number": event.get("session_number") or "",
        "vote_number": event.get("vote_number") or "",
        "numexp": event.get("numexp") or "",
        "initiative_id": event.get("initiative_id") or "",
        "initiative_match_status": event.get("initiative_match_status") or "",
        "initiative_type_code": type_code,
        "initiative_type_label": event.get("initiative_type_label") or parliament_type_label(type_code),
        "topic_id": topic_id,
        "topic_label": event.get("topic_label") or event.get("initiative_topic_label") or program_topic_label(topic_id),
        "topic_source": event.get("topic_source") or "",
        "majority_side": event.get("majority_side") or "",
        "total_si": int(event.get("total_si") or 0),
        "total_no": int(event.get("total_no") or 0),
        "total_abstenciones": int(event.get("total_abstenciones") or 0),
        "total_blancos": int(event.get("total_blancos") or 0),
        "member_votes_total": int(event.get("member_votes_total") or 0),
        "party_vote_totals": party_vote_totals,
        "party_positions_summary": compact_parliament_vote_party_positions(party_vote_totals),
        "member_vote_samples": [
            compact_member_vote_sample(row)
            for row in list(event.get("member_votes") or [])[:6]
            if isinstance(row, dict)
        ],
        "review_status": "needs_human_review",
        "legal_effect_status": event.get("legal_effect_status") or "unreviewed",
        "legal_effect_kind": event.get("legal_effect_kind") or "unclassified_vote",
        "legal_effect_label": event.get("legal_effect_label") or "efecto legal pendiente",
        "legal_effect_confidence": event.get("legal_effect_confidence") or "unknown",
        "legal_effect_basis": event.get("legal_effect_basis") or "",
        "impact_status": "unreviewed",
        "responsibility_status": "actor_not_attributed",
        "candidate_direction": "unknown",
        "claim_status": "parliament_vote_review_queue_only_no_public_claim",
        "evidence_tier": event.get("evidence_tier") or "tier_1_primary",
        "title": compact_evidence_quote(event.get("title"), max_words=34, max_chars=320),
        "review_hint": "Triaje legal automatico desde tipo/titulo; confirmar efecto, actores, BOJA/dinero/outcomes y direccion ciudadana antes de puntuar.",
        "review_questions": [dict(question) for question in PARLIAMENT_VOTE_REVIEW_QUESTIONS],
        "source_url": event.get("source_url") or "",
        "initiative_source_url": event.get("initiative_source_url") or "",
        "source_locator": "{document_id}::vote:{vote_number}".format(
            document_id=event.get("document_id") or "",
            vote_number=event.get("vote_number") or "",
        ),
    }


def rank_parliament_vote_review_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        items,
        key=lambda item: (
            -parliament_vote_review_priority_score(item),
            -boja_review_date_rank(item.get("date")),
            str(item.get("topic_id") or ""),
            str(item.get("initiative_type_code") or ""),
            str(item.get("review_item_id") or ""),
        ),
    )
    for index, item in enumerate(ranked, start=1):
        score = parliament_vote_review_priority_score(item)
        batch_number = ((index - 1) // PARLIAMENT_VOTE_REVIEW_BATCH_SIZE) + 1
        item["priority_rank"] = index
        item["priority_score"] = score
        item["review_batch_id"] = f"parliament-vote-review-batch-{batch_number:03d}"
        item["priority_reason"] = parliament_vote_review_priority_reason(item, score)
    return ranked


def build_parliament_vote_review_packet(vote_events: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = rank_parliament_vote_review_items(
        [build_parliament_vote_review_item(event) for event in vote_events if isinstance(event, dict)]
    )
    batches: list[dict[str, Any]] = []
    for start in range(0, len(ranked), PARLIAMENT_VOTE_REVIEW_BATCH_SIZE):
        batch_items = ranked[start : start + PARLIAMENT_VOTE_REVIEW_BATCH_SIZE]
        if not batch_items:
            continue
        batch_id = str(batch_items[0].get("review_batch_id") or f"parliament-vote-review-batch-{len(batches) + 1:03d}")
        batches.append(
            {
                "batch_id": batch_id,
                "review_status": "needs_human_review",
                "claim_status": "batch_prioritization_only_no_public_claim",
                "items_total": len(batch_items),
                "priority_rank_from": int(batch_items[0].get("priority_rank") or 0),
                "priority_rank_to": int(batch_items[-1].get("priority_rank") or 0),
                "topic_counts": parliament_vote_review_count_rows(batch_items, "topic_id"),
                "initiative_type_counts": parliament_vote_review_count_rows(batch_items, "initiative_type_code"),
                "legal_effect_counts": parliament_vote_review_count_rows(batch_items, "legal_effect_kind"),
                "items": batch_items,
            }
        )
    return {
        "schema_version": "andalucia_2026_parliament_vote_impact_review_packet_v1",
        "status": "needs_review" if ranked else "empty",
        "items_total": len(ranked),
        "reviewed_items_total": 0,
        "batches_total": len(batches),
        "batch_size": PARLIAMENT_VOTE_REVIEW_BATCH_SIZE,
        "priority_items_limit": PARLIAMENT_VOTE_REVIEW_PRIORITY_ITEMS_LIMIT,
        "priority_method": {
            "status": "triage_only_not_public_assessment",
            "type_weights": PARLIAMENT_VOTE_REVIEW_TYPE_PRIORITY,
            "topic_weights": BOJA_IMPACT_REVIEW_TOPIC_PRIORITY,
            "margin_rule": "Closer yes/no margins get more review priority because responsibility turns on few votes.",
            "legal_effect_rule": "Legal-effect fields are rule triage from official type/title/majority, not reviewed impact findings.",
            "claim_rule": "Priority ranks order human review only; they are not merit, blame, or impact claims.",
        },
        "topic_counts": parliament_vote_review_count_rows(ranked, "topic_id"),
        "initiative_type_counts": parliament_vote_review_count_rows(ranked, "initiative_type_code"),
        "legal_effect_counts": parliament_vote_review_count_rows(ranked, "legal_effect_kind"),
        "priority_items": ranked[:PARLIAMENT_VOTE_REVIEW_PRIORITY_ITEMS_LIMIT],
        "batches": batches,
    }


def empty_parliament_vote_reviews_report(path: Path | None = None) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_parliament_vote_reviews_v1",
        "status": "missing",
        "source_path": str(path or ""),
        "reviews_total": 0,
        "applied_reviews_total": 0,
        "reviews": [],
        "reviews_by_item_id": {},
        "reviews_by_event_id": {},
    }


def load_parliament_vote_reviews(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_parliament_vote_reviews_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviews = [row for row in payload.get("reviews", []) if isinstance(row, dict)]
    reviews_by_item_id = {
        str(row.get("review_item_id") or ""): row
        for row in reviews
        if row.get("review_item_id")
    }
    reviews_by_event_id = {
        str(row.get("vote_event_id") or ""): row
        for row in reviews
        if row.get("vote_event_id")
    }
    return {
        "schema_version": payload.get("schema_version") or "andalucia_2026_parliament_vote_reviews_v1",
        "status": "ok",
        "source_path": str(path),
        "reviews_total": len(reviews),
        "applied_reviews_total": 0,
        "reviews": reviews,
        "reviews_by_item_id": reviews_by_item_id,
        "reviews_by_event_id": reviews_by_event_id,
    }


def is_reviewed_vote_item(item: dict[str, Any]) -> bool:
    return str(item.get("review_status") or "").startswith("reviewed_")


def compact_reviewed_vote_sample(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_item_id": item.get("review_item_id") or "",
        "vote_event_id": item.get("vote_event_id") or "",
        "date": item.get("date") or "",
        "numexp": item.get("numexp") or "",
        "vote_number": item.get("vote_number") or "",
        "title": compact_evidence_quote(item.get("title"), max_words=18, max_chars=180),
        "topic_id": item.get("topic_id") or "",
        "topic_label": item.get("topic_label") or "",
        "topic_source": item.get("topic_source") or "",
        "reviewed_issue_label": item.get("reviewed_issue_label") or item.get("topic_label") or "",
        "effect_outcome": item.get("effect_outcome") or "",
        "legal_effect_status": item.get("legal_effect_status") or "",
        "majority_side": item.get("majority_side") or "",
        "total_si": int(item.get("total_si") or 0),
        "total_no": int(item.get("total_no") or 0),
        "source_url": item.get("source_url") or "",
        "initiative_source_url": item.get("initiative_source_url") or "",
        "review_summary": item.get("review_summary") or "",
        "claim_status": item.get("claim_status") or "",
        "review_confidence": item.get("review_confidence") or "",
    }


def reviewed_vote_topic_from_review(review: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    explicit_topic_id = str(review.get("topic_id") or "").strip()
    if explicit_topic_id:
        return {
            "topic_id": explicit_topic_id,
            "topic_label": review.get("topic_label") or program_topic_label(explicit_topic_id),
            "topic_source": review.get("topic_source") or "review_seed_topic",
        }

    issue_label = normalize_label(review.get("reviewed_issue_label") or item.get("reviewed_issue_label") or "")
    title_text = normalize_label(" ".join(str(value or "") for value in (item.get("title"), review.get("review_summary"))))
    combined = f"{issue_label} {title_text}"
    keyword_map: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("cultura_patrimonio", ("patrimonio", "cultural", "cultura", "museo", "biblioteca", "archivo")),
        ("fiscalidad", ("fiscal", "tribut", "impuesto", "hacienda", "tasas")),
        ("campo_agua", ("monte", "montes", "forestal", "agricola", "agraria", "hidraulic", "regadio", "agua")),
        ("energia_clima", ("gestion ambiental", "medio ambiente", "ambiental", "climat", "energia")),
        ("educacion", ("universidad", "universitaria", "educacion", "formacion profesional")),
        ("sanidad", ("sanidad", "salud", "hospital", "atencion primaria")),
        ("vivienda", ("vivienda", "alquiler", "vpo")),
        ("empleo", ("empleo", "trabajo", "autonom")),
        ("transparencia_corrupcion", ("transparencia", "corrupcion", "buen gobierno")),
        ("seguridad_libertades", ("seguridad", "libertad", "derechos", "memoria")),
    )
    for topic_id, terms in keyword_map:
        if any(term in combined for term in terms):
            return {
                "topic_id": topic_id,
                "topic_label": program_topic_label(topic_id),
                "topic_source": "reviewed_issue_label_seed",
            }

    existing_topic_id = str(item.get("topic_id") or "")
    if existing_topic_id:
        return {
            "topic_id": existing_topic_id,
            "topic_label": item.get("topic_label") or program_topic_label(existing_topic_id),
            "topic_source": item.get("topic_source") or "existing_vote_topic",
        }
    return {
        "topic_id": "sin_tema",
        "topic_label": "Sin tema",
        "topic_source": "no_topic_signal",
    }


def apply_parliament_vote_reviews(
    parliament_report: dict[str, Any],
    review_report: dict[str, Any],
) -> dict[str, Any]:
    reviews_by_item_id = review_report.get("reviews_by_item_id") or {}
    reviews_by_event_id = review_report.get("reviews_by_event_id") or {}
    applied_by_event_id: dict[str, dict[str, Any]] = {}
    applied_total = 0
    for item in parliament_report.get("vote_impact_review_queue") or []:
        if not isinstance(item, dict):
            continue
        review = reviews_by_item_id.get(str(item.get("review_item_id") or "")) or reviews_by_event_id.get(
            str(item.get("vote_event_id") or "")
        )
        if not isinstance(review, dict):
            continue
        applied_total += 1
        topic = reviewed_vote_topic_from_review(review, item)
        item.update(
            {
                "review_status": review.get("review_status") or "reviewed_vote_result_only",
                "legal_effect_status": review.get("legal_effect_status") or "reviewed_vote_result_only",
                "effect_outcome": review.get("effect_outcome") or "",
                "impact_status": review.get("impact_status") or "outcome_not_reviewed",
                "responsibility_status": review.get("responsibility_status") or "party_positions_observed",
                "candidate_direction": review.get("candidate_direction") or "unknown",
                "reviewed_issue_label": review.get("reviewed_issue_label") or item.get("topic_label") or "",
                "topic_id": topic["topic_id"],
                "topic_label": topic["topic_label"],
                "topic_source": topic["topic_source"],
                "review_summary": review.get("review_summary") or "",
                "review_confidence": review.get("review_confidence") or "medium",
                "reviewed_at": review.get("reviewed_at") or "",
                "reviewed_by": review.get("reviewed_by") or "",
                "source_evidence": list(review.get("source_evidence") or []),
                "claim_status": "reviewed_legislative_vote_signal_no_merit_claim",
            }
        )
        applied_by_event_id[str(item.get("vote_event_id") or "")] = item
    for event in parliament_report.get("vote_events") or []:
        if not isinstance(event, dict):
            continue
        review_item = applied_by_event_id.get(str(event.get("vote_event_id") or ""))
        if not review_item:
            continue
        event["review_status"] = review_item.get("review_status") or event.get("review_status")
        event["legal_effect_status"] = review_item.get("legal_effect_status") or ""
        event["effect_outcome"] = review_item.get("effect_outcome") or ""
        event["topic_id"] = review_item.get("topic_id") or event.get("topic_id") or ""
        event["topic_label"] = review_item.get("topic_label") or event.get("topic_label") or ""
        event["topic_source"] = review_item.get("topic_source") or event.get("topic_source") or ""
        event["review_summary"] = review_item.get("review_summary") or ""
        for member_vote in event.get("member_votes") or []:
            if not isinstance(member_vote, dict):
                continue
            member_vote["topic_id"] = event.get("topic_id") or ""
            member_vote["topic_label"] = event.get("topic_label") or ""
            member_vote["topic_source"] = event.get("topic_source") or ""
    vote_events = list(parliament_report.get("vote_events") or [])
    parliament_report["vote_events_by_party_topic"] = summarize_parliament_party_topic_vote_positions(vote_events)
    parliament_report["reviewed_vote_items_total"] = applied_total
    parliament_report["vote_impact_review_review_status_counts"] = [
        {"key": key, "label": key.replace("_", " "), "count": count}
        for key, count in sorted(
            Counter(str(item.get("review_status") or "sin_dato") for item in parliament_report.get("vote_impact_review_queue") or []).items(),
            key=lambda row: (-row[1], row[0]),
        )
    ]
    if applied_total:
        packet = parliament_report.get("vote_impact_review_packet") or {}
        packet["status"] = "partially_reviewed"
        packet["reviewed_items_total"] = applied_total
        review_report["applied_reviews_total"] = applied_total
    return review_report


def party_position_effect_bucket(position: str, effect_outcome: str) -> str:
    if effect_outcome in {"approved_by_majority_yes", "decree_law_validated_by_majority_yes"}:
        if position == "si":
            return "supported_approved_effect_total"
        if position == "no":
            return "opposed_approved_effect_total"
        if position == "abstenciones":
            return "abstained_approved_effect_total"
    if effect_outcome == "rejected_by_majority_no":
        if position == "no":
            return "supported_rejected_effect_total"
        if position == "si":
            return "opposed_rejected_effect_total"
        if position == "abstenciones":
            return "abstained_rejected_effect_total"
    return "observed_other"


def vote_position_outcome_bucket(position: str, majority_side: str) -> str:
    if position == "abstenciones":
        return "abstained_on_reviewed_outcome_total"
    if position in {"si", "no"} and majority_side in {"si", "no"}:
        if position == majority_side:
            return "voted_with_reviewed_outcome_total"
        return "voted_against_reviewed_outcome_total"
    return "observed_other"


def summarize_reviewed_parliament_party_vote_impacts(review_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for item in review_items:
        if not isinstance(item, dict) or not is_reviewed_vote_item(item):
            continue
        effect_outcome = str(item.get("effect_outcome") or "")
        majority_side = str(item.get("majority_side") or "")
        for party_vote in item.get("party_vote_totals") or []:
            if not isinstance(party_vote, dict):
                continue
            party_key = str(party_vote.get("party_key") or "")
            if not party_key:
                continue
            acc = totals.setdefault(
                party_key,
                {
                    "party_key": party_key,
                    "party_acronym": party_vote.get("party_acronym") or "",
                    "party_label": party_vote.get("party_label") or "",
                    "reviewed_vote_events_total": 0,
                    "supported_approved_effect_total": 0,
                    "opposed_approved_effect_total": 0,
                    "abstained_approved_effect_total": 0,
                    "supported_rejected_effect_total": 0,
                    "opposed_rejected_effect_total": 0,
                    "abstained_rejected_effect_total": 0,
                    "voted_with_reviewed_outcome_total": 0,
                    "voted_against_reviewed_outcome_total": 0,
                    "abstained_on_reviewed_outcome_total": 0,
                    "observed_other": 0,
                    "reviewed_issue_counts": Counter(),
                    "sample_items": [],
                    "claim_status": "reviewed_legislative_vote_signal_no_merit_claim",
                    "interpretation_status": "legal_effect_reviewed_outcome_pending",
                },
            )
            acc["reviewed_vote_events_total"] += 1
            bucket = party_position_effect_bucket(str(party_vote.get("dominant_position") or ""), effect_outcome)
            acc[bucket] += 1
            outcome_bucket = vote_position_outcome_bucket(
                str(party_vote.get("dominant_position") or ""),
                majority_side,
            )
            if outcome_bucket != "observed_other" and outcome_bucket != bucket:
                acc[outcome_bucket] += 1
            issue_label = str(item.get("reviewed_issue_label") or item.get("topic_label") or "sin_issue")
            acc["reviewed_issue_counts"][issue_label] += 1
            if len(acc["sample_items"]) < 5:
                sample = compact_reviewed_vote_sample(item)
                sample["party_position"] = party_vote.get("dominant_position") or ""
                sample["party_si"] = int(party_vote.get("si") or 0)
                sample["party_no"] = int(party_vote.get("no") or 0)
                sample["party_abstenciones"] = int(party_vote.get("abstenciones") or 0)
                acc["sample_items"].append(sample)
    out = []
    for row in totals.values():
        normalized = dict(row)
        normalized["reviewed_issue_counts"] = [
            {"key": stable_slug(label), "label": label, "count": count}
            for label, count in sorted(
                normalized["reviewed_issue_counts"].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        out.append(normalized)
    return sorted(out, key=lambda row: (-int(row["reviewed_vote_events_total"]), row["party_acronym"]))


def compact_member_vote_sample(member_vote: dict[str, Any]) -> dict[str, Any]:
    return {
        "vote_member_id": member_vote.get("vote_member_id") or "",
        "vote_event_id": member_vote.get("vote_event_id") or "",
        "date": member_vote.get("date") or "",
        "numexp": member_vote.get("numexp") or "",
        "initiative_match_status": member_vote.get("initiative_match_status") or "",
        "initiative_id": member_vote.get("initiative_id") or "",
        "initiative_source_url": member_vote.get("initiative_source_url") or "",
        "initiative_type_code": member_vote.get("initiative_type_code") or "",
        "initiative_type_label": member_vote.get("initiative_type_label") or "",
        "initiative_topic_id": member_vote.get("initiative_topic_id") or "",
        "initiative_topic_label": member_vote.get("initiative_topic_label") or "",
        "topic_id": member_vote.get("topic_id") or member_vote.get("initiative_topic_id") or "",
        "topic_label": member_vote.get("topic_label") or member_vote.get("initiative_topic_label") or "",
        "legal_effect_kind": member_vote.get("legal_effect_kind") or "",
        "title": compact_evidence_quote(member_vote.get("title"), max_words=18, max_chars=180),
        "vote_position": member_vote.get("vote_position") or "",
        "group_code": member_vote.get("group_code") or "",
        "party_key": member_vote.get("party_key") or "",
        "member_number": member_vote.get("member_number") or "",
        "member_name": member_vote.get("member_name") or "",
        "delegated_vote": bool(member_vote.get("delegated_vote")),
        "source_url": member_vote.get("source_url") or "",
        "claim_status": member_vote.get("claim_status") or "",
        "interpretation_status": member_vote.get("interpretation_status") or "",
    }


def build_candidate_index_for_member_votes(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        key = normalize_person_name_for_vote_match(candidate.get("person_name") or "")
        if key:
            index[key].append(candidate)
    return index


def build_parliament_candidate_vote_summaries(
    candidates: list[dict[str, Any]],
    parliament_report: dict[str, Any],
    *,
    sample_limit: int = 5,
) -> list[dict[str, Any]]:
    candidate_index = build_candidate_index_for_member_votes(candidates)
    summaries: dict[str, dict[str, Any]] = {}
    for member_vote in parliament_report.get("member_votes") or []:
        if not isinstance(member_vote, dict):
            continue
        matches = candidate_index.get(str(member_vote.get("member_name_match_key") or ""))
        if not matches or len(matches) != 1:
            continue
        candidate = matches[0]
        candidate_id = str(candidate.get("candidate_id") or "")
        summary = summaries.setdefault(
            candidate_id,
            {
                "candidate_id": candidate_id,
                "person_name": candidate.get("person_name") or "",
                "province": candidate.get("province") or "",
                "party_acronym": candidate.get("party_acronym") or "",
                "party_key": stable_slug(candidate.get("party_acronym") or ""),
                "list_position": candidate.get("list_position") or 0,
                "candidate_type": candidate.get("candidate_type") or "",
                "person_id": candidate.get("person_id"),
                "vote_events_total": 0,
                "si": 0,
                "no": 0,
                "abstenciones": 0,
                "blancos": 0,
                "ausente": 0,
                "delegated_votes_total": 0,
                "sample_votes": [],
                "claim_status": "official_member_vote_history_not_interpreted",
                "interpretation_status": "needs_legal_effect_actor_and_impact_review",
                "evidence_tier": "tier_1_primary",
            },
        )
        position = str(member_vote.get("vote_position") or "unknown")
        if position in {"si", "no", "abstenciones", "blancos", "ausente"}:
            summary[position] += 1
        summary["vote_events_total"] += 1
        if member_vote.get("delegated_vote"):
            summary["delegated_votes_total"] += 1
        if len(summary["sample_votes"]) < sample_limit:
            summary["sample_votes"].append(compact_member_vote_sample(member_vote))
    return sorted(
        summaries.values(),
        key=lambda row: (-int(row["vote_events_total"]), row["party_acronym"], row["person_name"]),
    )


def build_reviewed_parliament_candidate_vote_summaries(
    candidates: list[dict[str, Any]],
    parliament_report: dict[str, Any],
    *,
    sample_limit: int = 5,
) -> list[dict[str, Any]]:
    reviewed_by_event_id = {
        str(item.get("vote_event_id") or ""): item
        for item in parliament_report.get("vote_impact_review_queue") or []
        if isinstance(item, dict) and is_reviewed_vote_item(item)
    }
    if not reviewed_by_event_id:
        return []
    candidate_index = build_candidate_index_for_member_votes(candidates)
    summaries: dict[str, dict[str, Any]] = {}
    for member_vote in parliament_report.get("member_votes") or []:
        if not isinstance(member_vote, dict):
            continue
        reviewed_item = reviewed_by_event_id.get(str(member_vote.get("vote_event_id") or ""))
        if not reviewed_item:
            continue
        matches = candidate_index.get(str(member_vote.get("member_name_match_key") or ""))
        if not matches or len(matches) != 1:
            continue
        candidate = matches[0]
        candidate_id = str(candidate.get("candidate_id") or "")
        summary = summaries.setdefault(
            candidate_id,
            {
                "candidate_id": candidate_id,
                "person_name": candidate.get("person_name") or "",
                "province": candidate.get("province") or "",
                "party_acronym": candidate.get("party_acronym") or "",
                "party_key": stable_slug(candidate.get("party_acronym") or ""),
                "list_position": candidate.get("list_position") or 0,
                "candidate_type": candidate.get("candidate_type") or "",
                "person_id": candidate.get("person_id"),
                "reviewed_vote_events_total": 0,
                "supported_approved_effect_total": 0,
                "opposed_approved_effect_total": 0,
                "abstained_approved_effect_total": 0,
                "supported_rejected_effect_total": 0,
                "opposed_rejected_effect_total": 0,
                "abstained_rejected_effect_total": 0,
                "voted_with_reviewed_outcome_total": 0,
                "voted_against_reviewed_outcome_total": 0,
                "abstained_on_reviewed_outcome_total": 0,
                "observed_other": 0,
                "sample_votes": [],
                "claim_status": "reviewed_legislative_vote_signal_no_merit_claim",
                "interpretation_status": "legal_effect_reviewed_outcome_pending",
                "evidence_tier": "tier_1_primary",
            },
        )
        bucket = party_position_effect_bucket(
            str(member_vote.get("vote_position") or ""),
            str(reviewed_item.get("effect_outcome") or ""),
        )
        summary["reviewed_vote_events_total"] += 1
        summary[bucket] += 1
        outcome_bucket = vote_position_outcome_bucket(
            str(member_vote.get("vote_position") or ""),
            str(reviewed_item.get("majority_side") or ""),
        )
        if outcome_bucket != "observed_other" and outcome_bucket != bucket:
            summary[outcome_bucket] += 1
        if len(summary["sample_votes"]) < sample_limit:
            sample = compact_member_vote_sample(member_vote)
            sample["reviewed_issue_label"] = reviewed_item.get("reviewed_issue_label") or ""
            sample["effect_outcome"] = reviewed_item.get("effect_outcome") or ""
            sample["legal_effect_status"] = reviewed_item.get("legal_effect_status") or ""
            sample["review_summary"] = reviewed_item.get("review_summary") or ""
            summary["sample_votes"].append(sample)
    return sorted(
        summaries.values(),
        key=lambda row: (-int(row["reviewed_vote_events_total"]), row["party_acronym"], row["person_name"]),
    )


def fetch_and_parse_parliament_voting_document(
    document: dict[str, Any],
    *,
    parl_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    pdf_dir = parl_dir / "vote_pdfs"
    text_dir = parl_dir / "vote_text"
    pdf_path = pdf_dir / f"{stable_slug(document.get('document_id') or document.get('source_url'))}.pdf"
    text_path = text_dir / f"{stable_slug(document.get('document_id') or document.get('source_url'))}.txt"
    payload = pdf_path.read_bytes() if pdf_path.exists() else b""
    status = "cached" if payload else "missing"
    if not payload and not no_network:
        try:
            payload, _content_type = http_get_bytes(str(document.get("source_url") or ""), timeout=timeout, max_attempts=1)
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(payload)
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            errors.append({"url": str(document.get("source_url") or ""), "error": f"{type(exc).__name__}: {exc}"})
            if strict_network:
                raise
    events: list[dict[str, Any]] = []
    text_chars = 0
    text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
    text_status = "cached" if text else "missing"
    if payload and not text:
        try:
            text = extract_pdf_text(pdf_path)
            text_dir.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding="utf-8")
            text_status = "ok"
        except Exception as exc:  # noqa: BLE001
            errors.append({"url": str(document.get("source_url") or ""), "error": f"{type(exc).__name__}: {exc}"})
            if strict_network:
                raise
    if text:
        try:
            text_chars = len(text)
            events = parse_parliament_vote_events_text(document, text)
        except Exception as exc:  # noqa: BLE001
            errors.append({"url": str(document.get("source_url") or ""), "error": f"{type(exc).__name__}: {exc}"})
            if strict_network:
                raise
    updated = dict(document)
    updated.update(
        {
            "pdf_status": status,
            "raw_pdf_path": str(pdf_path) if payload else "",
            "text_status": text_status,
            "raw_text_path": str(text_path) if text else "",
            "text_chars": text_chars,
            "parsed_vote_events_total": len(events),
        }
    )
    return updated, events, errors


def count_rows(rows: list[dict[str, Any]], key: str, *, label_key: str | None = None) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for row in rows:
        values = row.get(key)
        if isinstance(values, list):
            iterable = [str(value) for value in values if value]
            if not iterable:
                iterable = ["sin_dato"]
        else:
            iterable = [str(values or "sin_dato")]
        for value in iterable:
            counts[value] += 1
            if label_key and row.get(label_key):
                labels[value] = str(row.get(label_key) or value)
    return [
        {"key": value, "label": labels.get(value) or value.replace("_", " "), "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def collect_parlamento_andalucia_activity(
    *,
    raw_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
    legislature: int = PARLAMENTO_ANDALUCIA_LEGISLATURE,
) -> dict[str, Any]:
    report = empty_parliament_activity_report(raw_dir / "parlamento_andalucia")
    report["legislature"] = legislature
    parl_dir = raw_dir / "parlamento_andalucia"
    initiatives_url = build_parliament_initiatives_url(legislature=legislature)
    voting_results_url = build_parliament_voting_results_url()
    report["initiatives_url"] = initiatives_url
    report["voting_results_url"] = voting_results_url
    errors: list[dict[str, str]] = []

    def load_html(cache_name: str, url: str) -> tuple[bytes, str]:
        path = parl_dir / cache_name
        payload = path.read_bytes() if path.exists() else b""
        status = "cached" if payload else "missing"
        if not payload and not no_network:
            try:
                payload, _content_type = http_get_bytes(url, timeout=timeout, max_attempts=1)
                parl_dir.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
                if strict_network:
                    raise
        return payload, status

    initiatives_payload, initiatives_status = load_html(
        f"legislative_initiatives_leg{legislature}.html",
        initiatives_url,
    )
    voting_payload, voting_status = load_html("voting_results.html", voting_results_url)
    initiatives = parse_parliament_initiatives_html(initiatives_payload, legislature=legislature) if initiatives_payload else []
    voting_result_documents = parse_parliament_voting_documents_html(voting_payload) if voting_payload else []
    initiative_detail_vote_documents, initiative_detail_pages, initiative_detail_errors = (
        collect_parliament_initiative_detail_vote_documents(
            initiatives,
            parl_dir=parl_dir,
            timeout=timeout,
            no_network=no_network,
            strict_network=strict_network,
        )
        if initiatives
        else ([], [], [])
    )
    errors.extend(initiative_detail_errors)
    voting_documents = dedupe_parliament_voting_documents(
        [*voting_result_documents, *initiative_detail_vote_documents]
    )
    parsed_voting_documents: list[dict[str, Any]] = []
    vote_events: list[dict[str, Any]] = []
    for document in voting_documents:
        parsed_document, document_events, document_errors = fetch_and_parse_parliament_voting_document(
            document,
            parl_dir=parl_dir,
            timeout=timeout,
            no_network=no_network,
            strict_network=strict_network,
        )
        parsed_voting_documents.append(parsed_document)
        vote_events.extend(document_events)
        errors.extend(document_errors)
    vote_events_with_official_initiative_total = enrich_parliament_vote_events_with_initiatives(
        vote_events,
        initiatives,
    )
    member_votes = [
        member_vote
        for event in vote_events
        for member_vote in (event.get("member_votes") or [])
        if isinstance(member_vote, dict)
    ]
    compact_vote_events = []
    for event in vote_events:
        compact_event = {key: value for key, value in event.items() if key != "member_votes"}
        compact_event["member_vote_samples"] = [
            compact_member_vote_sample(row) for row in list(event.get("member_votes") or [])[:6]
        ]
        compact_vote_events.append(compact_event)
    vote_impact_review_packet = build_parliament_vote_review_packet(vote_events)
    ranked_vote_impact_review_queue = [
        item
        for batch in vote_impact_review_packet.get("batches", [])
        for item in list(batch.get("items") or [])
        if isinstance(item, dict)
    ]
    vote_impact_review_queue_by_topic: dict[str, list[dict[str, Any]]] = {}
    for item in ranked_vote_impact_review_queue:
        topic_id = str(item.get("topic_id") or "sin_tema")
        vote_impact_review_queue_by_topic.setdefault(topic_id, []).append(item)
    if initiatives_payload and strict_network and not initiatives:
        raise RuntimeError("Parlamento Andalucia initiatives page yielded zero parseable legislative initiatives")
    if voting_documents and strict_network and not vote_events:
        raise RuntimeError("Parlamento Andalucia voting PDFs yielded zero parseable vote events")
    report.update(
        {
            "status": "ok" if initiatives else "empty",
            "initiatives_status": initiatives_status,
            "voting_results_status": voting_status,
            "legislative_initiatives_total": len(initiatives),
            "legislative_initiatives_by_proponent": count_rows(initiatives, "proponent"),
            "legislative_initiatives_by_party_key": count_rows(initiatives, "proponent_party_keys"),
            "legislative_initiatives_by_type": count_rows(initiatives, "type_code", label_key="type_label"),
            "legislative_initiatives_by_topic": count_rows(initiatives, "topic_id", label_key="topic_label"),
            "legislative_initiatives": initiatives,
            "voting_result_documents_total": len(voting_result_documents),
            "initiative_detail_pages_checked_total": len(initiative_detail_pages),
            "initiative_detail_pages_with_vote_documents_total": sum(
                1 for page in initiative_detail_pages if int(page.get("vote_documents_total") or 0) > 0
            ),
            "initiative_detail_page_status_counts": count_rows(initiative_detail_pages, "status"),
            "initiative_detail_vote_documents_total": len(initiative_detail_vote_documents),
            "initiative_detail_vote_documents_new_total": max(0, len(voting_documents) - len(voting_result_documents)),
            "initiative_detail_pages": initiative_detail_pages[:24],
            "voting_documents_total": len(voting_documents),
            "voting_documents": parsed_voting_documents[:12],
            "parsed_vote_events_total": len(vote_events),
            "vote_events_with_initiative_total": sum(1 for event in vote_events if event.get("numexp")),
            "vote_events_with_official_initiative_total": vote_events_with_official_initiative_total,
            "vote_events_with_legal_effect_triage_total": sum(
                1 for event in vote_events if event.get("legal_effect_status") == "rule_triaged_needs_review"
            ),
            "vote_events_with_party_totals_total": sum(1 for event in vote_events if event.get("party_vote_totals")),
            "member_vote_records_total": len(member_votes),
            "member_votes_with_delegated_total": sum(1 for member_vote in member_votes if member_vote.get("delegated_vote")),
            "member_vote_samples": member_votes[:24],
            "member_votes": member_votes,
            "vote_events": compact_vote_events,
            "vote_events_by_party_position": summarize_parliament_party_vote_positions(vote_events),
            "vote_events_by_party_topic": summarize_parliament_party_topic_vote_positions(vote_events),
            "vote_events_by_legal_effect": summarize_parliament_vote_legal_effects(vote_events),
            "vote_impact_review_queue_total": len(ranked_vote_impact_review_queue),
            "reviewed_vote_items_total": int(vote_impact_review_packet.get("reviewed_items_total") or 0),
            "vote_impact_review_batches_total": int(vote_impact_review_packet.get("batches_total") or 0),
            "vote_impact_review_packet": vote_impact_review_packet,
            "vote_impact_review_queue": ranked_vote_impact_review_queue,
            "vote_impact_review_queue_by_topic": vote_impact_review_queue_by_topic,
            "vote_impact_review_type_counts": parliament_vote_review_count_rows(
                ranked_vote_impact_review_queue,
                "initiative_type_code",
            ),
            "vote_impact_review_legal_effect_counts": parliament_vote_review_count_rows(
                ranked_vote_impact_review_queue,
                "legal_effect_kind",
            ),
            "review_status": "vote_impact_review_queue_needs_human_review" if ranked_vote_impact_review_queue else "vote_counts_extracted_needs_actor_outcome_link" if vote_events else "needs_vote_actor_outcome_link" if initiatives else "missing_source",
            "claim_status": "official_parliament_activity_not_assessed",
            "errors_total": len(errors),
            "errors": errors,
        }
    )
    return report


def parse_boja_api_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("BOJA API response is not an object")
    results = data.get("results")
    if not isinstance(results, list):
        raise RuntimeError("BOJA API response without results list")
    return data


def parse_boja_detail_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("BOJA detail response is not an object")
    results = data.get("results")
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return results[0]
    if data.get("id"):
        return data
    return {}


def build_boja_detail_url(boja_id: str) -> str:
    return BOJA_API_DETAIL_URL_TEMPLATE.format(boja_id=urllib.parse.quote(str(boja_id), safe=""))


def fetch_boja_detail_record(
    *,
    boja_id: str,
    boja_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
) -> dict[str, Any]:
    detail_dir = boja_dir / "details"
    cache_path = detail_dir / f"{stable_slug(boja_id)}.json"
    payload = cache_path.read_bytes() if cache_path.exists() else b""
    status = "cached" if payload else "missing"
    error = ""
    detail: dict[str, Any] = {}
    url = build_boja_detail_url(boja_id)

    if not payload and not no_network:
        try:
            payload, _content_type = http_get_bytes(url, timeout=timeout, max_attempts=1)
            detail_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(payload)
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
            if strict_network:
                raise

    if payload:
        try:
            detail = parse_boja_detail_payload(payload)
            if status == "missing":
                status = "cached"
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
            if strict_network:
                raise

    return {
        "status": status,
        "url": url,
        "raw_path": str(cache_path) if payload else "",
        "detail": detail,
        "error": error,
    }


def is_boja_disposiciones_generales(row: dict[str, Any]) -> bool:
    section = normalize_label(row.get("titleSec") or "")
    return section.startswith("1. disposiciones generales")


def boja_pdf_url(row: dict[str, Any]) -> str:
    pdfs = row.get("pdf")
    if isinstance(pdfs, list):
        for pdf in pdfs:
            if isinstance(pdf, dict) and pdf.get("publicUrl"):
                return str(pdf["publicUrl"])
    return str(row.get("publicUrl") or "")


def detect_boja_action_kind(text: str, type_value: str = "") -> str:
    normalized = normalize_label(f"{type_value} {text}")
    for action, patterns in BOJA_ACTION_PATTERNS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return action
    return "official_normative_reference"


def boja_detail_text(detail: dict[str, Any]) -> str:
    blocks: list[str] = []
    for field in ("summaryNoHtml", "summary", "bodyNoHtml", "body"):
        blocks.extend(html_text_blocks(detail.get(field)))
    seen: set[str] = set()
    out: list[str] = []
    for block in blocks:
        key = compact_for_match(block)[:180]
        if key and key not in seen:
            seen.add(key)
            out.append(block)
    return "\n".join(out)


def boja_topic_hit_count(text: str, record: dict[str, Any]) -> int:
    normalized = normalize_label(text)
    topic_id = str(record.get("topic_id") or "")
    topic_query = str(record.get("topic_query") or "")
    topic_terms = tuple(PROGRAM_TOPIC_TERMS.get(topic_id, ())) + (topic_query, program_topic_label(topic_id))
    return sum(1 for term in topic_terms if term and normalize_label(term) in normalized)


def boja_fragment_score(block: str, *, record: dict[str, Any], field: str) -> tuple[int, str]:
    normalized = normalize_label(block)
    topic_hits = boja_topic_hit_count(block, record)
    action_kind = detect_boja_action_kind(block, str(record.get("type") or ""))
    score = topic_hits * 4
    if action_kind != "official_normative_reference":
        score += 8
    if field.startswith("summary"):
        score += 4
    if re.search(r"\b(articulo|acuerda|dispone|se aprueba|se modifica|se deroga|lineas de actuacion)\b", normalized):
        score += 3
    if len(block) > 80:
        score += 1
    return score, action_kind


def split_boja_excerpt_candidates(block: str) -> list[str]:
    cleaned = clean_line(block.replace("\f", " "))
    if not cleaned:
        return []
    candidates = [
        clean_line(part)
        for part in re.split(r"(?<=[.;:])\s+|\n+", cleaned)
        if len(clean_line(part)) >= 40
    ]
    return candidates or [cleaned]


def select_boja_excerpt_block(block: str, *, record: dict[str, Any], field: str) -> str:
    candidates = split_boja_excerpt_candidates(block)
    if len(candidates) <= 1:
        return candidates[0] if candidates else block
    scored: list[tuple[int, int, str]] = []
    for index, candidate in enumerate(candidates):
        score, _action_kind = boja_fragment_score(candidate, record=record, field=field)
        if len(candidate) > 420:
            score -= 1
        scored.append((score, -index, candidate))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return scored[0][2]


def extract_boja_fragments(
    record: dict[str, Any],
    detail: dict[str, Any],
    *,
    max_fragments: int = 2,
) -> list[dict[str, Any]]:
    source_fields: list[tuple[str, Any]] = [
        ("summaryNoHtml", detail.get("summaryNoHtml") or record.get("summary")),
        ("summary", detail.get("summary")),
        ("bodyNoHtml", detail.get("bodyNoHtml")),
        ("body", detail.get("body")),
    ]
    candidates: list[tuple[int, str, str, str, str]] = []
    seen: set[str] = set()
    for field, value in source_fields:
        for block in html_text_blocks(value):
            normalized_key = compact_for_match(block)[:220]
            if not normalized_key or normalized_key in seen:
                continue
            seen.add(normalized_key)
            if len(block) < 40:
                continue
            excerpt_block = select_boja_excerpt_block(block, record=record, field=field)
            if field.startswith("body") and boja_topic_hit_count(excerpt_block, record) <= 0:
                continue
            score, action_kind = boja_fragment_score(excerpt_block, record=record, field=field)
            if score <= 0:
                score, action_kind = boja_fragment_score(block, record=record, field=field)
            if score <= 0:
                continue
            candidates.append((score, field, action_kind, block, excerpt_block))

    if not candidates and record.get("summary"):
        score, action_kind = boja_fragment_score(str(record["summary"]), record=record, field="summary")
        candidates.append((score, "summary", action_kind, str(record["summary"]), str(record["summary"])))

    candidates.sort(key=lambda item: (-item[0], item[1], item[4]))
    selected_candidates: list[tuple[int, str, str, str, str]] = []
    selected_excerpt_keys: set[str] = set()
    for candidate in candidates:
        excerpt_key = compact_for_match(candidate[4])[:220]
        if excerpt_key and excerpt_key in selected_excerpt_keys:
            continue
        if excerpt_key:
            selected_excerpt_keys.add(excerpt_key)
        selected_candidates.append(candidate)
        if len(selected_candidates) >= max_fragments:
            break
    out: list[dict[str, Any]] = []
    for index, (_score, field, action_kind, _block, excerpt_block) in enumerate(selected_candidates, start=1):
        fragment_id = f"{record['boja_id']}-{record['topic_id']}-f{index:02d}"
        excerpt = short_excerpt(excerpt_block, max_words=36, max_chars=320)
        out.append(
            {
                "fragment_id": stable_slug(fragment_id),
                "boja_id": record.get("boja_id") or "",
                "topic_id": record.get("topic_id") or "",
                "topic_label": record.get("topic_label") or "",
                "date": record.get("date") or "",
                "organisation": record.get("organisation") or "",
                "type": record.get("type") or "",
                "action_kind": action_kind,
                "source_field": field,
                "source_url": record.get("source_url") or "",
                "source_locator": f"{record.get('boja_id') or ''}::{field}::{index}",
                "evidence_tier": "tier_1_primary",
                "claim_status": "official_normative_fragment_not_interpreted",
                "interpretation_status": "needs_direction_and_impact_review",
                "evidence_excerpt": excerpt,
                "excerpt_words": len(excerpt.split()),
            }
        )
    return out


def build_boja_impact_review_item(fragment: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    action_kind = str(fragment.get("action_kind") or record.get("action_kind") or "official_normative_reference")
    review_item_id = stable_slug(f"boja-impact-review:{fragment.get('fragment_id') or ''}")
    return {
        "review_item_id": review_item_id,
        "topic_id": fragment.get("topic_id") or record.get("topic_id") or "",
        "topic_label": fragment.get("topic_label") or record.get("topic_label") or "",
        "boja_id": fragment.get("boja_id") or record.get("boja_id") or "",
        "fragment_id": fragment.get("fragment_id") or "",
        "date": fragment.get("date") or record.get("date") or "",
        "organisation": fragment.get("organisation") or record.get("organisation") or "",
        "type": fragment.get("type") or record.get("type") or "",
        "action_kind": action_kind,
        "review_hint": BOJA_ACTION_REVIEW_HINTS.get(
            action_kind,
            BOJA_ACTION_REVIEW_HINTS["official_normative_reference"],
        ),
        "review_status": "needs_human_review",
        "impact_status": "unreviewed",
        "responsibility_status": "actor_not_attributed",
        "candidate_direction": "unknown",
        "claim_status": "impact_review_queue_only_no_public_claim",
        "evidence_tier": fragment.get("evidence_tier") or "tier_1_primary",
        "source_url": fragment.get("source_url") or record.get("source_url") or "",
        "detail_url": record.get("detail_url") or "",
        "source_locator": fragment.get("source_locator") or "",
        "record_summary": record.get("evidence_excerpt") or record.get("summary") or "",
        "evidence_excerpt": fragment.get("evidence_excerpt") or "",
        "review_questions": [dict(question) for question in BOJA_IMPACT_REVIEW_QUESTIONS],
    }


def boja_review_date_rank(value: Any) -> int:
    text = str(value or "").strip()
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return year * 10000 + month * 100 + day
    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return year * 10000 + month * 100 + day
    return 0


def boja_review_recency_points(value: Any) -> int:
    rank = boja_review_date_rank(value)
    if not rank:
        return 0
    year = rank // 10000
    month = (rank // 100) % 100
    quarter = max(1, min(4, ((month - 1) // 3) + 1))
    return max(0, (year - 2022) * 4 + quarter)


def impact_review_priority_score(item: dict[str, Any]) -> int:
    action_kind = str(item.get("action_kind") or "official_normative_reference")
    topic_id = str(item.get("topic_id") or "")
    return (
        BOJA_IMPACT_REVIEW_ACTION_PRIORITY.get(action_kind, BOJA_IMPACT_REVIEW_ACTION_PRIORITY["official_normative_reference"])
        + BOJA_IMPACT_REVIEW_TOPIC_PRIORITY.get(topic_id, 8)
        + boja_review_recency_points(item.get("date"))
    )


def impact_review_priority_reason(item: dict[str, Any], score: int) -> str:
    action_kind = str(item.get("action_kind") or "official_normative_reference")
    topic_id = str(item.get("topic_id") or "")
    action_points = BOJA_IMPACT_REVIEW_ACTION_PRIORITY.get(
        action_kind,
        BOJA_IMPACT_REVIEW_ACTION_PRIORITY["official_normative_reference"],
    )
    topic_points = BOJA_IMPACT_REVIEW_TOPIC_PRIORITY.get(topic_id, 8)
    recency_points = boja_review_recency_points(item.get("date"))
    return (
        f"accion={action_kind}:{action_points}; "
        f"tema={topic_id or 'sin_tema'}:{topic_points}; "
        f"fecha={item.get('date') or 'sin_fecha'}:{recency_points}; "
        f"total={score}"
    )


def boja_impact_review_count_rows(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(str(item.get(key) or "sin_dato") for item in items)
    out: list[dict[str, Any]] = []
    for value, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
        label = program_topic_label(value) if key == "topic_id" and value != "sin_dato" else value.replace("_", " ")
        out.append({"key": value, "label": label, "count": count})
    return out


def rank_boja_impact_review_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        items,
        key=lambda item: (
            -impact_review_priority_score(item),
            -boja_review_date_rank(item.get("date")),
            str(item.get("topic_id") or ""),
            str(item.get("action_kind") or ""),
            str(item.get("review_item_id") or ""),
        ),
    )
    for index, item in enumerate(ranked, start=1):
        score = impact_review_priority_score(item)
        batch_number = ((index - 1) // BOJA_IMPACT_REVIEW_BATCH_SIZE) + 1
        item["priority_rank"] = index
        item["priority_score"] = score
        item["review_batch_id"] = f"boja-impact-review-batch-{batch_number:03d}"
        item["priority_reason"] = impact_review_priority_reason(item, score)
    return ranked


def build_boja_impact_review_packet(items: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = rank_boja_impact_review_items(items)
    batches: list[dict[str, Any]] = []
    for start in range(0, len(ranked), BOJA_IMPACT_REVIEW_BATCH_SIZE):
        batch_items = ranked[start : start + BOJA_IMPACT_REVIEW_BATCH_SIZE]
        if not batch_items:
            continue
        batch_id = str(batch_items[0].get("review_batch_id") or f"boja-impact-review-batch-{len(batches) + 1:03d}")
        batches.append(
            {
                "batch_id": batch_id,
                "review_status": "needs_human_review",
                "claim_status": "batch_prioritization_only_no_public_claim",
                "items_total": len(batch_items),
                "priority_rank_from": int(batch_items[0].get("priority_rank") or 0),
                "priority_rank_to": int(batch_items[-1].get("priority_rank") or 0),
                "topic_counts": boja_impact_review_count_rows(batch_items, "topic_id"),
                "action_counts": boja_impact_review_count_rows(batch_items, "action_kind"),
                "items": batch_items,
            }
        )
    return {
        "schema_version": "andalucia_2026_boja_impact_review_packet_v1",
        "status": "needs_review" if ranked else "empty",
        "items_total": len(ranked),
        "reviewed_items_total": 0,
        "batches_total": len(batches),
        "batch_size": BOJA_IMPACT_REVIEW_BATCH_SIZE,
        "priority_items_limit": BOJA_IMPACT_REVIEW_PRIORITY_ITEMS_LIMIT,
        "priority_method": {
            "status": "triage_only_not_public_assessment",
            "action_weights": BOJA_IMPACT_REVIEW_ACTION_PRIORITY,
            "topic_weights": BOJA_IMPACT_REVIEW_TOPIC_PRIORITY,
            "recency_rule": "later BOJA dates get small tie-break points within 2022-2026.",
            "claim_rule": "Priority ranks order human review only; they are not merit, blame, or impact claims.",
        },
        "topic_counts": boja_impact_review_count_rows(ranked, "topic_id"),
        "action_counts": boja_impact_review_count_rows(ranked, "action_kind"),
        "priority_items": ranked[:BOJA_IMPACT_REVIEW_PRIORITY_ITEMS_LIMIT],
        "batches": batches,
    }


def empty_boja_impact_reviews_report(path: Path | None = None) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_boja_impact_reviews_v1",
        "status": "missing",
        "source_path": str(path) if path else "",
        "reviews_total": 0,
        "applied_reviews_total": 0,
        "reviews": [],
        "reviews_by_item_id": {},
    }


def load_boja_impact_reviews(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_boja_impact_reviews_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviews = [item for item in payload.get("reviews") or [] if isinstance(item, dict)]
    reviews_by_item_id: dict[str, dict[str, Any]] = {}
    for item in reviews:
        review_item_id = str(item.get("review_item_id") or "")
        if not review_item_id:
            continue
        reviews_by_item_id[review_item_id] = item
    return {
        "schema_version": payload.get("schema_version") or "andalucia_2026_boja_impact_reviews_v1",
        "status": "ok",
        "source_path": str(path),
        "reviews_total": len(reviews),
        "applied_reviews_total": 0,
        "reviews": reviews,
        "reviews_by_item_id": reviews_by_item_id,
    }


def compact_boja_impact_review_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_item_id": item.get("review_item_id") or "",
        "review_status": item.get("review_status") or "",
        "topic_id": item.get("topic_id") or "",
        "topic_label": item.get("topic_label") or "",
        "boja_id": item.get("boja_id") or "",
        "fragment_id": item.get("fragment_id") or "",
        "date": item.get("date") or "",
        "organisation": item.get("organisation") or "",
        "action_kind": item.get("action_kind") or "",
        "impact_status": item.get("impact_status") or "",
        "responsibility_status": item.get("responsibility_status") or "",
        "candidate_direction": item.get("candidate_direction") or "",
        "claim_status": item.get("claim_status") or "",
        "review_summary": item.get("review_summary") or "",
        "reviewed_legal_change_label": item.get("reviewed_legal_change_label") or "",
        "review_confidence": item.get("review_confidence") or "",
        "source_url": item.get("source_url") or "",
        "source_locator": item.get("source_locator") or "",
        "evidence_excerpt": item.get("evidence_excerpt") or "",
        "source_evidence": item.get("source_evidence") or [],
    }


def apply_boja_impact_reviews(
    boja_report: dict[str, Any],
    review_report: dict[str, Any],
) -> dict[str, Any]:
    reviews_by_item_id = review_report.get("reviews_by_item_id") or {}
    reviewed_items: list[dict[str, Any]] = []
    for item in boja_report.get("impact_review_queue") or []:
        if not isinstance(item, dict):
            continue
        review_item_id = str(item.get("review_item_id") or "")
        review = reviews_by_item_id.get(review_item_id)
        if not isinstance(review, dict):
            continue
        item["review_status"] = review.get("review_status") or "reviewed_legal_change_only"
        item["impact_status"] = review.get("impact_status") or "legal_change_documented_outcome_pending"
        item["responsibility_status"] = review.get("responsibility_status") or "official_publisher_observed"
        item["candidate_direction"] = review.get("candidate_direction") or "unknown"
        item["claim_status"] = review.get("claim_status") or "reviewed_boja_legal_change_no_merit_claim"
        item["review_summary"] = review.get("review_summary") or ""
        item["reviewed_legal_change_label"] = review.get("reviewed_legal_change_label") or ""
        item["review_confidence"] = review.get("review_confidence") or "medium"
        item["reviewed_by"] = review.get("reviewed_by") or ""
        item["reviewed_at"] = review.get("reviewed_at") or ""
        item["source_evidence"] = review.get("source_evidence") or []
        reviewed_items.append(item)

    reviewed_by_topic: dict[str, list[dict[str, Any]]] = {}
    for item in reviewed_items:
        topic_id = str(item.get("topic_id") or "sin_tema")
        reviewed_by_topic.setdefault(topic_id, []).append(compact_boja_impact_review_item(item))

    boja_report["reviewed_impact_items_total"] = len(reviewed_items)
    boja_report["reviewed_impact_items"] = [compact_boja_impact_review_item(item) for item in reviewed_items]
    boja_report["reviewed_impact_items_by_topic"] = reviewed_by_topic
    boja_report["impact_review_review_status_counts"] = [
        {"key": key, "count": count}
        for key, count in sorted(
            Counter(str(item.get("review_status") or "sin_dato") for item in boja_report.get("impact_review_queue") or []).items(),
            key=lambda row: (-row[1], row[0]),
        )
    ]

    for topic in boja_report.get("topics") or []:
        if not isinstance(topic, dict):
            continue
        topic_id = str(topic.get("topic_id") or "sin_tema")
        topic_reviewed = reviewed_by_topic.get(topic_id, [])
        topic["reviewed_impact_items_total"] = len(topic_reviewed)
        topic["reviewed_impact_items"] = topic_reviewed[:12]

    packet = boja_report.get("impact_review_packet") or {}
    if reviewed_items:
        packet["status"] = "partially_reviewed"
        packet["reviewed_items_total"] = len(reviewed_items)
        packet["review_status_counts"] = boja_report["impact_review_review_status_counts"]
        review_report["applied_reviews_total"] = len(reviewed_items)
    return review_report


def is_boja_record_topic_relevant(record: dict[str, Any], detail_text: str = "") -> bool:
    topic_id = str(record.get("topic_id") or "")
    exclusions = BOJA_TOPIC_EXCLUSION_TERMS.get(topic_id) or ()
    if not exclusions:
        return True
    haystack = normalize_label(
        " ".join(
            [
                str(record.get("summary") or ""),
                str(record.get("organisation") or ""),
                str(record.get("type") or ""),
                detail_text[:5000],
            ]
        )
    )
    if not any(normalize_label(term) in haystack for term in exclusions):
        return True
    required = BOJA_TOPIC_REQUIRED_TERMS_WHEN_EXCLUDED.get(topic_id) or ()
    return any(normalize_label(term) in haystack for term in required)


def compact_boja_norm_record(row: dict[str, Any], *, topic_id: str, topic_query: str) -> dict[str, Any]:
    summary = strip_html_text(row.get("summaryNoHtml") or row.get("summary") or "")
    action_kind = detect_boja_action_kind(summary, str(row.get("type") or ""))
    return {
        "boja_id": str(row.get("id") or ""),
        "topic_id": topic_id,
        "topic_label": program_topic_label(topic_id),
        "topic_query": topic_query,
        "date": str(row.get("date") or ""),
        "bulletin_number": int(row.get("number") or 0),
        "title_sec": strip_html_text(row.get("titleSec") or ""),
        "organisation": strip_html_text(row.get("organisation") or ""),
        "type": strip_html_text(row.get("type") or ""),
        "summary": summary,
        "evidence_excerpt": short_excerpt(summary, max_words=28, max_chars=260),
        "source_url": boja_pdf_url(row),
        "detail_url": build_boja_detail_url(str(row.get("id") or "")) if row.get("id") else "",
        "detail_status": "not_requested",
        "detail_raw_path": "",
        "detail_text_chars": 0,
        "action_kind": action_kind,
        "fragments_total": 0,
        "fragments": [],
        "evidence_tier": "tier_1_primary",
        "claim_status": "official_normative_record_not_interpreted",
        "interpretation_status": "needs_article_level_direction_review",
    }


def build_boja_search_url(
    *,
    query: str,
    date_from: str,
    date_to: str,
    size: int,
    page: int = 0,
) -> str:
    params: list[tuple[str, str]] = [
        ("order_by", "date"),
        ("mode", "DESC"),
        ("size", str(max(1, int(size)))),
        ("page", str(max(0, int(page)))),
        ("general", query),
        ("general_search_like", "true"),
        ("summaryNoHtml", "-"),
        ("date_from", date_from),
        ("date_to", date_to),
    ]
    for field in (
        "id",
        "organisation",
        "summaryNoHtml",
        "number",
        "date",
        "titleSec",
        "type",
        "publicUrl",
        "pathPdf",
    ):
        params.append(("campos", field))
    return f"{BOJA_API_SEARCH_PAGINATION_URL}?{urllib.parse.urlencode(params)}"


def collect_boja_normative_sources(
    *,
    raw_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
    date_from: str = BOJA_TERM_START_DATE,
    date_to: str = BOJA_TERM_END_DATE,
    api_size: int = 40,
    max_per_topic: int = 6,
    topic_queries: dict[str, str] | None = None,
    exact_records: tuple[dict[str, str], ...] | None = None,
) -> dict[str, Any]:
    using_default_topic_queries = topic_queries is None
    topic_queries = topic_queries or BOJA_TOPIC_QUERIES
    if exact_records is None:
        exact_records = BOJA_TOPIC_EXACT_RECORDS if using_default_topic_queries else ()
    boja_dir = raw_dir / "boja_normas"
    topics: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    fragments: list[dict[str, Any]] = []
    impact_review_queue: list[dict[str, Any]] = []
    records_by_topic: dict[str, list[dict[str, Any]]] = {}
    fragments_by_topic: dict[str, list[dict[str, Any]]] = {}
    impact_review_queue_by_topic: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []
    seen_records: set[tuple[str, str]] = set()
    detail_status_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    impact_review_action_counts: Counter[str] = Counter()

    def append_compact_record(compact: dict[str, Any], detail_report: dict[str, Any]) -> dict[str, Any] | None:
        detail_status = str(detail_report.get("status") or "missing")
        detail = detail_report.get("detail") if isinstance(detail_report.get("detail"), dict) else {}
        if detail_status in {"ok", "cached"} and not detail:
            detail_status = "empty"
        detail_text = boja_detail_text(detail) if detail else ""
        if not is_boja_record_topic_relevant(compact, detail_text):
            return None
        detail_status_counts[detail_status] += 1
        compact["detail_status"] = detail_status
        compact["detail_url"] = str(detail_report.get("url") or compact.get("detail_url") or "")
        compact["detail_raw_path"] = str(detail_report.get("raw_path") or "")
        compact["detail_text_chars"] = len(detail_text)
        if detail_report.get("error"):
            compact["detail_error"] = str(detail_report.get("error") or "")
        record_fragments = extract_boja_fragments(compact, detail or compact)
        compact["fragments"] = record_fragments
        compact["fragments_total"] = len(record_fragments)
        record_review_items = [build_boja_impact_review_item(fragment, compact) for fragment in record_fragments]
        compact["impact_review_queue"] = record_review_items
        compact["impact_review_queue_total"] = len(record_review_items)
        if record_fragments:
            compact["action_kind"] = record_fragments[0]["action_kind"]
        fragments.extend(record_fragments)
        impact_review_queue.extend(record_review_items)
        topic_id = str(compact.get("topic_id") or "")
        fragments_by_topic.setdefault(topic_id, []).extend(record_fragments)
        impact_review_queue_by_topic.setdefault(topic_id, []).extend(record_review_items)
        for fragment in record_fragments:
            action_counts[str(fragment.get("action_kind") or "official_normative_reference")] += 1
        for item in record_review_items:
            impact_review_action_counts[str(item.get("action_kind") or "official_normative_reference")] += 1
        records.append(compact)
        return compact

    for topic_id, query in topic_queries.items():
        cache_path = boja_dir / f"{stable_slug(topic_id)}.json"
        payload = cache_path.read_bytes() if cache_path.exists() else b""
        status = "cached" if payload else "missing"
        error = ""
        url = build_boja_search_url(query=query, date_from=date_from, date_to=date_to, size=api_size)
        content_type = ""

        if not payload and not no_network:
            try:
                payload, content_type = http_get_bytes(url, timeout=timeout, max_attempts=1)
                boja_dir.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(payload)
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
                errors.append({"topic_id": topic_id, "query": query, "url": url, "error": error})
                if strict_network:
                    raise

        topic_records: list[dict[str, Any]] = []
        total_hits = 0
        if payload:
            try:
                data = parse_boja_api_payload(payload)
                total_hits = int(data.get("total_hits") or data.get("hits") or 0)
                for row in data.get("results") or []:
                    if not isinstance(row, dict) or not is_boja_disposiciones_generales(row):
                        continue
                    compact = compact_boja_norm_record(row, topic_id=topic_id, topic_query=query)
                    if not compact["boja_id"] or not compact["summary"]:
                        continue
                    dedupe_key = (topic_id, compact["boja_id"])
                    if dedupe_key in seen_records:
                        continue
                    seen_records.add(dedupe_key)
                    detail_report = fetch_boja_detail_record(
                        boja_id=compact["boja_id"],
                        boja_dir=boja_dir,
                        timeout=timeout,
                        no_network=no_network,
                        strict_network=strict_network,
                    )
                    finalized = append_compact_record(compact, detail_report)
                    if not finalized:
                        continue
                    topic_records.append(finalized)
                    if len(topic_records) >= max_per_topic:
                        break
                if status == "missing":
                    status = "cached"
            except Exception as exc:  # noqa: BLE001
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
                errors.append({"topic_id": topic_id, "query": query, "url": url, "error": error})
                if strict_network:
                    raise

        for exact_record in exact_records:
            if str(exact_record.get("topic_id") or "") != topic_id:
                continue
            boja_id = str(exact_record.get("boja_id") or "")
            if not boja_id:
                continue
            dedupe_key = (topic_id, boja_id)
            if dedupe_key in seen_records:
                continue
            detail_report = fetch_boja_detail_record(
                boja_id=boja_id,
                boja_dir=boja_dir,
                timeout=timeout,
                no_network=no_network,
                strict_network=strict_network,
            )
            detail = detail_report.get("detail") if isinstance(detail_report.get("detail"), dict) else {}
            if not detail:
                continue
            compact = compact_boja_norm_record(
                {**detail, "id": detail.get("id") or boja_id},
                topic_id=topic_id,
                topic_query=str(exact_record.get("topic_query") or query),
            )
            if not compact["boja_id"] or not compact["summary"]:
                continue
            seen_records.add(dedupe_key)
            finalized = append_compact_record(compact, detail_report)
            if finalized:
                finalized["exact_record_note"] = exact_record.get("note") or ""
                topic_records.append(finalized)

        records_by_topic[topic_id] = topic_records
        topic_fragments = fragments_by_topic.get(topic_id, [])
        topic_review_items = impact_review_queue_by_topic.get(topic_id, [])
        topics.append(
            {
                "topic_id": topic_id,
                "topic_label": program_topic_label(topic_id),
                "query": query,
                "status": status,
                "api_url": url,
                "raw_path": str(cache_path) if payload else "",
                "content_type": content_type,
                "total_hits": total_hits,
                "records_total": len(topic_records),
                "details_available_total": sum(
                    1 for record in topic_records if record.get("detail_status") in {"ok", "cached"}
                ),
                "fragments_total": len(topic_fragments),
                "impact_review_queue_total": len(topic_review_items),
                "reviewed_impact_items_total": 0,
                "records": topic_records,
                "fragments": topic_fragments[:12],
                "impact_review_queue": topic_review_items[:12],
                "error": error,
            }
        )

    impact_review_packet = build_boja_impact_review_packet(impact_review_queue)
    ranked_impact_review_queue = [
        item
        for batch in impact_review_packet.get("batches", [])
        for item in batch.get("items", [])
        if isinstance(item, dict)
    ]
    ranked_impact_review_queue_by_topic: dict[str, list[dict[str, Any]]] = {}
    for item in ranked_impact_review_queue:
        topic_id = str(item.get("topic_id") or "")
        ranked_impact_review_queue_by_topic.setdefault(topic_id, []).append(item)
    for topic in topics:
        topic_id = str(topic.get("topic_id") or "")
        topic_review_items = ranked_impact_review_queue_by_topic.get(topic_id, [])
        topic["impact_review_queue_total"] = len(topic_review_items)
        topic["impact_review_queue"] = topic_review_items[:12]

    detail_ok = detail_status_counts["ok"]
    detail_cached = detail_status_counts["cached"]
    return {
        "schema_version": "andalucia_2026_boja_normative_topic_report_v1",
        "status": "ok" if any(topic["records_total"] for topic in topics) else "empty",
        "api_url": BOJA_API_SEARCH_PAGINATION_URL,
        "detail_api_url_template": BOJA_API_DETAIL_URL_TEMPLATE,
        "raw_dir": str(boja_dir),
        "date_from": date_from,
        "date_to": date_to,
        "topics_total": len(topics),
        "topics_with_results_total": sum(1 for topic in topics if topic["records_total"]),
        "api_total_hits": sum(int(topic["total_hits"] or 0) for topic in topics),
        "records_total": len(records),
        "details_available_total": detail_ok + detail_cached,
        "details_fetched_total": detail_ok,
        "details_cached_total": detail_cached,
        "fragments_total": len(fragments),
        "fragment_action_counts": [
            {"key": key, "count": count}
            for key, count in sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "impact_review_queue_total": len(impact_review_queue),
        "reviewed_impact_items_total": 0,
        "reviewed_impact_items": [],
        "reviewed_impact_items_by_topic": {},
        "impact_review_review_status_counts": [
            {"key": key, "count": count}
            for key, count in sorted(
                Counter(str(item.get("review_status") or "sin_dato") for item in ranked_impact_review_queue).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
        "impact_review_action_counts": [
            {"key": key, "count": count}
            for key, count in sorted(impact_review_action_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "impact_review_packet": impact_review_packet,
        "errors_total": len(errors),
        "topics": topics,
        "records": records,
        "records_by_topic": records_by_topic,
        "fragments": fragments,
        "fragments_by_topic": fragments_by_topic,
        "impact_review_queue": ranked_impact_review_queue,
        "impact_review_queue_by_topic": ranked_impact_review_queue_by_topic,
        "errors": errors,
    }


def build_evidence_lanes(
    program_report: dict[str, Any],
    boja_report: dict[str, Any] | None = None,
    parliament_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    lanes = [dict(lane) for lane in SOURCE_GAP_LANES]
    boja_report = boja_report or empty_boja_norms_report()
    parliament_report = parliament_report or empty_parliament_activity_report()
    for lane in lanes:
        if lane["lane_id"] == "programas_2026":
            fetched = int(program_report.get("fetched_sources_total") or 0)
            verified = int(program_report.get("verified_sources_total") or 0)
            total = int(program_report.get("sources_total") or 0)
            measures = int(program_report.get("measures_total") or 0)
            if measures > 0:
                lane["status"] = "declared_measures_extracted"
                lane["next_action"] = (
                    "Revisar resumen ciudadano e impacto antes de cruzar cada medida con BOJA, votos, dinero y resultados."
                )
            elif verified > 0:
                lane["status"] = "raw_sources_collected"
                lane["next_action"] = (
                    "Extraer medidas por bloque, enlazarlas a issues y someter interpretacion a revision antes de claims."
                )
            elif fetched > 0:
                lane["status"] = "raw_sources_unverified"
                lane["next_action"] = "Verificar texto de programas y reemplazar copias de prensa por URLs primarias del partido."
            else:
                lane["status"] = "missing_connector"
            lane["metrics"] = {
                "sources_total": total,
                "fetched_sources_total": fetched,
                "verified_sources_total": verified,
                "text_extracted_sources_total": int(program_report.get("text_extracted_sources_total") or 0),
                "press_hosted_sources_total": int(program_report.get("press_hosted_sources_total") or 0),
                "party_domain_sources_total": int(program_report.get("party_domain_sources_total") or 0),
                "measures_total": measures,
            }
        elif lane["lane_id"] == "parlamento_andalucia_actividad":
            initiatives = int(parliament_report.get("legislative_initiatives_total") or 0)
            voting_docs = int(parliament_report.get("voting_documents_total") or 0)
            vote_events = int(parliament_report.get("parsed_vote_events_total") or 0)
            vote_review_items = int(parliament_report.get("vote_impact_review_queue_total") or 0)
            if vote_review_items > 0:
                lane["status"] = "official_vote_review_queue"
                lane["next_action"] = (
                    "Confirmar triaje de efecto legal y resolver actor responsable, direccion ciudadana, dinero/ejecucion y outcomes antes de publicar responsabilidad."
                )
            elif vote_events > 0:
                lane["status"] = "official_vote_counts_extracted"
                lane["next_action"] = (
                    "Enlazar votos con expedientes, diputados/candidatos y outcomes antes de publicar responsabilidad."
                )
            elif initiatives > 0:
                lane["status"] = "official_initiatives_collected"
                lane["next_action"] = (
                    "Extraer tablas de voto y tramites por expediente para convertir actividad en responsabilidad revisada."
                )
            elif voting_docs > 0:
                lane["status"] = "official_voting_documents_collected"
                lane["next_action"] = "Parsear PDFs de sentido del voto y enlazarlos a expedientes legislativos."
            lane["metrics"] = {
                "legislative_initiatives_total": initiatives,
                "voting_documents_total": voting_docs,
                "parsed_vote_events_total": vote_events,
                "vote_events_with_initiative_total": int(parliament_report.get("vote_events_with_initiative_total") or 0),
                "vote_events_with_official_initiative_total": int(
                    parliament_report.get("vote_events_with_official_initiative_total") or 0
                ),
                "vote_events_with_legal_effect_triage_total": int(
                    parliament_report.get("vote_events_with_legal_effect_triage_total") or 0
                ),
                "party_topic_vote_rows_total": len(parliament_report.get("vote_events_by_party_topic") or []),
                "legal_effect_rows_total": len(parliament_report.get("vote_events_by_legal_effect") or []),
                "vote_impact_review_queue_total": vote_review_items,
                "reviewed_vote_items_total": int(parliament_report.get("reviewed_vote_items_total") or 0),
                "vote_impact_review_batches_total": int(parliament_report.get("vote_impact_review_batches_total") or 0),
                "errors_total": int(parliament_report.get("errors_total") or 0),
            }
        elif lane["lane_id"] == "boja_normas_modificaciones":
            records = int(boja_report.get("records_total") or 0)
            topics = int(boja_report.get("topics_with_results_total") or 0)
            fragments = int(boja_report.get("fragments_total") or 0)
            review_items = int(boja_report.get("impact_review_queue_total") or 0)
            reviewed_items = int(boja_report.get("reviewed_impact_items_total") or 0)
            if reviewed_items > 0:
                lane["status"] = "official_impact_review_partially_reviewed"
                lane["next_action"] = (
                    "Cruzar cambios legales revisados con responsable politico, presupuesto/ejecucion y outcomes antes de puntuar."
                )
            elif review_items > 0:
                lane["status"] = "official_impact_review_queue"
                lane["next_action"] = (
                    "Resolver cola de direccion, actor responsable, presupuesto/ejecucion y outcome antes de puntuar."
                )
            elif fragments > 0:
                lane["status"] = "official_fragments_extracted"
                lane["next_action"] = (
                    "Revisar direccion e impacto ciudadano de cada fragmento antes de atribuir valores, merito o culpa."
                )
            elif records > 0:
                lane["status"] = "official_records_collected"
                lane["next_action"] = (
                    "Revisar articulo/fragmento y direccion del cambio antes de atribuir impacto o valores del actor."
                )
            lane["metrics"] = {
                "records_total": records,
                "details_available_total": int(boja_report.get("details_available_total") or 0),
                "fragments_total": fragments,
                "impact_review_queue_total": review_items,
                "reviewed_impact_items_total": reviewed_items,
                "topics_with_results_total": topics,
                "api_total_hits": int(boja_report.get("api_total_hits") or 0),
                "errors_total": int(boja_report.get("errors_total") or 0),
                "date_from": boja_report.get("date_from") or "",
                "date_to": boja_report.get("date_to") or "",
            }
    return lanes


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def is_noise_line(line: str) -> bool:
    if not line:
        return True
    prefixes = (
        "Boletín Oficial",
        "BOJA",
        "Deposito Legal",
        "Depósito Legal",
        "Numero 75",
        "Número 75",
        "pagina ",
        "página ",
        "https://",
        "00336606",
        "1. Disposiciones generales",
        "JUNTA ELECTORAL",
        "Publicacion de candidaturas",
        "Publicación de candidaturas",
        "Elecciones al Parlamento",
        "Candidaturas proclamadas",
    )
    return any(line.startswith(prefix) for prefix in prefixes)


def parse_candidature_name(raw: str) -> tuple[str, str]:
    match = re.search(r"\(([^()]+)\)\s*$", raw)
    if not match:
        return raw.strip(), stable_slug(raw).upper()
    return raw.strip(), match.group(1).strip()


def parse_candidature_text(text: str) -> dict[str, Any]:
    province = ""
    current: dict[str, Any] | None = None
    pending_header: dict[str, Any] | None = None
    mode = "titular"
    lists: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if is_noise_line(line):
            continue

        province_match = re.search(r"Circunscripción electoral:\s*(.+)$", line)
        if province_match:
            province = province_match.group(1).strip()
            pending_header = None
            continue

        list_match = re.match(r"^Candidatura núm\.:\s*(\d+)\.\s*(.+)$", line)
        if list_match:
            name_raw, acronym = parse_candidature_name(list_match.group(2))
            current = {
                "list_id": f"{stable_slug(province)}-{int(list_match.group(1)):02d}-{stable_slug(acronym)}",
                "province": province,
                "list_number": int(list_match.group(1)),
                "candidature_name": name_raw,
                "party_acronym": acronym,
                "titular_candidates": [],
                "suplente_candidates": [],
            }
            lists.append(current)
            pending_header = current
            mode = "titular"
            continue

        person_match = re.match(r"^(\d+)\.\s+(DON|DOÑA)\s+(.+)$", line, flags=re.IGNORECASE)

        if pending_header and not person_match and line != "Suplentes":
            pending_header["candidature_name"] = f"{pending_header['candidature_name']} {line}".strip()
            pending_header["party_acronym"] = parse_candidature_name(pending_header["candidature_name"])[1]
            pending_header["list_id"] = (
                f"{stable_slug(pending_header['province'])}-"
                f"{int(pending_header['list_number']):02d}-"
                f"{stable_slug(pending_header['party_acronym'])}"
            )
            continue

        pending_header = None

        if line == "Suplentes":
            mode = "suplente"
            continue

        if current and person_match:
            position = int(person_match.group(1))
            honorific = person_match.group(2).upper()
            full_name = strip_person_prefix(f"{honorific} {person_match.group(3).strip()}")
            candidate = {
                "candidate_id": (
                    f"{current['list_id']}-{mode}-{position:02d}-"
                    f"{stable_slug(full_name)}"
                ),
                "province": current["province"],
                "list_id": current["list_id"],
                "list_number": current["list_number"],
                "party_acronym": current["party_acronym"],
                "candidature_name": current["candidature_name"],
                "candidate_type": mode,
                "list_position": position,
                "honorific": honorific,
                "person_name": full_name,
                "person_name_normalized": normalize_candidate_name(full_name),
                "source_url": OFFICIAL_CANDIDATURE_PDF_URL,
            }
            candidates.append(candidate)
            target = current["suplente_candidates"] if mode == "suplente" else current["titular_candidates"]
            target.append(candidate["candidate_id"])

    if not lists:
        raise RuntimeError("No candidatures parsed from official text")

    province_counts: dict[str, dict[str, int]] = {}
    for row in lists:
        province_counts.setdefault(row["province"], {"lists": 0, "titular_candidates": 0, "suplente_candidates": 0})
        province_counts[row["province"]]["lists"] += 1
        province_counts[row["province"]]["titular_candidates"] += len(row["titular_candidates"])
        province_counts[row["province"]]["suplente_candidates"] += len(row["suplente_candidates"])

    return {
        "lists": lists,
        "candidates": candidates,
        "province_counts": province_counts,
        "coverage": {
            "provinces_total": len(province_counts),
            "candidate_lists_total": len(lists),
            "titular_candidates_total": sum(1 for item in candidates if item["candidate_type"] == "titular"),
            "suplente_candidates_total": sum(1 for item in candidates if item["candidate_type"] == "suplente"),
        },
    }


def load_source_catalog(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sources": [], "actions": [], "status": "missing"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    useful_terms = ("andalucia", "boja", "bdns_autonomico", "parlamento_andalucia")

    def useful(row: dict[str, Any]) -> bool:
        haystack = normalize_label(json.dumps(row, ensure_ascii=False))
        return any(term in haystack for term in useful_terms)

    return {
        "status": "ok",
        "snapshot_date": payload.get("snapshot_date") or "",
        "sources": [row for row in payload.get("sources", []) if useful(row)],
        "actions": [row for row in payload.get("actions", []) if useful(row)],
    }


def open_db(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def load_person_index(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = conn.execute("SELECT person_id, full_name FROM persons").fetchall()
    for row in rows:
        index[normalize_label(row["full_name"])].append(
            {"person_id": int(row["person_id"]), "full_name": row["full_name"]}
        )
    return index


def load_mandates(conn: sqlite3.Connection, person_ids: set[int]) -> dict[int, list[dict[str, Any]]]:
    if not person_ids:
        return {}
    placeholders = ",".join("?" for _ in person_ids)
    rows = conn.execute(
        f"""
        SELECT
          m.person_id,
          m.role_title,
          m.level,
          m.territory_code,
          m.start_date,
          m.end_date,
          m.is_active,
          m.source_id,
          m.source_record_id,
          i.name AS institution_name,
          p.name AS party_name,
          p.acronym AS party_acronym
        FROM mandates m
        LEFT JOIN institutions i ON i.institution_id = m.institution_id
        LEFT JOIN parties p ON p.party_id = m.party_id
        WHERE m.person_id IN ({placeholders})
        ORDER BY COALESCE(m.start_date, ''), m.mandate_id
        """,
        tuple(sorted(person_ids)),
    ).fetchall()
    out: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[int(row["person_id"])].append(
            {
                "role_title": row["role_title"] or "",
                "institution_name": row["institution_name"] or "",
                "party_name": row["party_name"] or "",
                "party_acronym": row["party_acronym"] or "",
                "level": row["level"] or "",
                "territory_code": row["territory_code"] or "",
                "start_date": row["start_date"] or "",
                "end_date": row["end_date"] or "",
                "is_active": int(row["is_active"] or 0),
                "source_id": row["source_id"] or "",
                "source_record_id": row["source_record_id"] or "",
            }
        )
    return dict(out)


def enrich_candidates_with_db(candidates: list[dict[str, Any]], db_path: Path) -> dict[str, Any]:
    conn = open_db(db_path)
    if conn is None:
        return {
            "status": "missing_db",
            "matched_candidates_total": 0,
            "unique_person_matches_total": 0,
            "person_matches": {},
        }
    try:
        person_index = load_person_index(conn)
        possible_person_ids: set[int] = set()
        possible_matches_by_candidate: dict[str, list[dict[str, Any]]] = {}
        for candidate in candidates:
            matches = person_index.get(candidate["person_name_normalized"], [])
            possible_matches_by_candidate[candidate["candidate_id"]] = matches
            possible_person_ids.update(int(match["person_id"]) for match in matches)

        all_possible_mandates = load_mandates(conn, possible_person_ids)
        person_matches: dict[str, dict[str, Any]] = {}
        person_ids: set[int] = set()

        def resolve_candidate_match(matches: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
            if len(matches) == 1:
                return matches[0], "unique_exact"
            if len(matches) <= 0:
                return None, "not_matched"

            scored: list[tuple[int, dict[str, Any]]] = []
            for match in matches:
                score = 0
                for mandate in all_possible_mandates.get(int(match["person_id"]), []):
                    source_id = normalize_label(mandate.get("source_id"))
                    institution = normalize_label(mandate.get("institution_name"))
                    if source_id == "parlamento_andalucia_diputados":
                        score += 5
                    if institution == "parlamento de andalucia":
                        score += 3
                    if mandate.get("is_active"):
                        score += 1
                scored.append((score, match))
            scored.sort(key=lambda item: item[0], reverse=True)
            if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                return scored[0][1], "disambiguated_by_andalucia_mandate"
            return None, "ambiguous_exact"

        for candidate in candidates:
            matches = possible_matches_by_candidate.get(candidate["candidate_id"], [])
            match, status = resolve_candidate_match(matches)
            if match:
                candidate["person_id"] = match["person_id"]
                candidate["person_match_status"] = status
                person_ids.add(match["person_id"])
                person_matches[str(match["person_id"])] = match
            elif len(matches) > 1:
                candidate["person_match_status"] = status
                candidate["person_match_candidates"] = [m["person_id"] for m in matches[:5]]
            else:
                candidate["person_match_status"] = status

        mandates = {pid: all_possible_mandates.get(pid, []) for pid in person_ids}
        for candidate in candidates:
            pid = candidate.get("person_id")
            if pid:
                person_mandates = mandates.get(int(pid), [])
                candidate["mandate_count"] = len(person_mandates)
                candidate["active_mandate_count"] = sum(1 for row in person_mandates if row.get("is_active"))
                candidate["mandates_sample"] = person_mandates[-5:]
            else:
                candidate["mandate_count"] = 0
                candidate["active_mandate_count"] = 0
                candidate["mandates_sample"] = []

        return {
            "status": "ok",
            "matched_candidates_total": sum(1 for item in candidates if item.get("person_id")),
            "unique_person_matches_total": len(person_ids),
            "person_matches": person_matches,
        }
    finally:
        conn.close()


def compact_program_source(row: dict[str, Any]) -> dict[str, Any]:
    topic_hits = dict(row.get("topic_hits") or {})
    top_topics = sorted(topic_hits.items(), key=lambda item: (-int(item[1]), item[0]))[:5]
    return {
        "source_id": row.get("source_id") or "",
        "title": row.get("title") or "",
        "url": row.get("url") or "",
        "page_url": row.get("page_url") or "",
        "source_kind": row.get("source_kind") or "",
        "officiality": row.get("officiality") or "",
        "status": row.get("status") or "",
        "verification_status": row.get("verification_status") or "",
        "page_count": row.get("page_count") or 0,
        "text_chars": row.get("text_chars") or 0,
        "top_topics": [{"topic": topic, "hits": hits} for topic, hits in top_topics if hits],
        "heading_sample": list(row.get("heading_sample") or [])[:6],
        "measures_total": row.get("measures_total") or 0,
        "measure_topics": list(row.get("measure_topics") or [])[:8],
        "claim_status": row.get("claim_status") or "raw_program_text_only",
    }


def attach_candidate_accountability_status(
    candidates: list[dict[str, Any]],
    evidence_report: dict[str, Any],
) -> None:
    for candidate in candidates:
        person_id = candidate.get("person_id")
        actor_key = f"person_id:{person_id}" if person_id else ""
        evidence_ref = build_accountability_evidence_ref(
            evidence_report,
            actor_key,
            match_scope="person_id_exact",
            match_note="Exact person_id match against the published accountability Evidence API.",
        )
        candidate["accountability_actor_key"] = actor_key
        candidate["accountability_evidence_status"] = evidence_ref["status"]


def build_party_index(
    lists: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    program_report: dict[str, Any] | None = None,
    evidence_report: dict[str, Any] | None = None,
    boja_report: dict[str, Any] | None = None,
    parliament_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    by_party: dict[str, dict[str, Any]] = {}
    candidates_by_list = {candidate["candidate_id"]: candidate for candidate in candidates}
    programs_by_party = (program_report or {}).get("by_party") or {}
    measures_by_party = (program_report or {}).get("measures_by_party") or {}
    evidence_report = evidence_report or empty_accountability_evidence_report()
    boja_report = boja_report or empty_boja_norms_report()
    parliament_report = parliament_report or empty_parliament_activity_report()
    parliament_votes_by_party = {
        str(row.get("party_key") or ""): row
        for row in parliament_report.get("vote_events_by_party_position") or []
        if isinstance(row, dict)
    }
    reviewed_votes_by_party = {
        str(row.get("party_key") or ""): row
        for row in parliament_report.get("reviewed_vote_events_by_party") or []
        if isinstance(row, dict)
    }
    parliament_vote_topics_by_party: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in parliament_report.get("vote_events_by_party_topic") or []:
        if isinstance(row, dict):
            parliament_vote_topics_by_party[str(row.get("party_key") or "")].append(row)
    candidate_votes_by_id = {
        str(row.get("candidate_id") or ""): row
        for row in parliament_report.get("candidate_vote_summaries") or []
        if isinstance(row, dict)
    }
    reviewed_candidate_votes_by_id = {
        str(row.get("candidate_id") or ""): row
        for row in parliament_report.get("reviewed_candidate_vote_summaries") or []
        if isinstance(row, dict)
    }
    for row in lists:
        party_key = stable_slug(row["party_acronym"])
        program_sources = [compact_program_source(item) for item in programs_by_party.get(party_key, [])]
        program_measures = list(measures_by_party.get(party_key, []))
        program_verified = sum(1 for item in program_sources if item["verification_status"] == "verified_by_text")
        party_evidence_mapping = PARTY_ACCOUNTABILITY_ACTOR_KEYS.get(party_key, {})
        party_evidence = build_accountability_evidence_ref(
            evidence_report,
            str(party_evidence_mapping.get("actor_key") or ""),
            match_scope=str(party_evidence_mapping.get("match_scope") or "no_party_actor_mapping"),
            match_note=str(party_evidence_mapping.get("match_note") or "No conservative party mapping for this candidature key yet."),
        )
        party = by_party.setdefault(
            party_key,
            {
                "party_key": party_key,
                "party_acronym": row["party_acronym"],
                "list_name_variants": [],
                "provinces": [],
                "candidate_lists_total": 0,
                "titular_candidates_total": 0,
                "suplente_candidates_total": 0,
                "matched_candidates_total": 0,
                "lead_candidates": [],
                "assessment_status": "candidate_list_only",
                "program_sources": program_sources,
                "program_sources_total": len(program_sources),
                "program_verified_sources_total": program_verified,
                "program_measures_total": len(program_measures),
                "program_measure_topics": sorted({measure["topic_id"] for measure in program_measures}),
                "program_measure_samples": program_measures[:6],
                "accountability_evidence": party_evidence,
                "parliament_vote_summary": parliament_votes_by_party.get(party_key, {}),
                "reviewed_legislative_impact_summary": reviewed_votes_by_party.get(party_key, {}),
                "parliament_vote_topic_summary": parliament_vote_topics_by_party.get(party_key, [])[:8],
                "program_source_status": (
                    "program_text_ready"
                    if program_verified
                    else "program_source_unverified"
                    if program_sources
                    else "missing_program_source"
                ),
                "lanes": build_evidence_lanes(
                    program_report or empty_program_report(DEFAULT_PROGRAM_SOURCES),
                    boja_report,
                    parliament_report,
                ),
            },
        )
        if row["candidature_name"] not in party["list_name_variants"]:
            party["list_name_variants"].append(row["candidature_name"])
        party["provinces"].append(row["province"])
        party["candidate_lists_total"] += 1
        party["titular_candidates_total"] += len(row["titular_candidates"])
        party["suplente_candidates_total"] += len(row["suplente_candidates"])
        titulars = [candidates_by_list[cid] for cid in row["titular_candidates"] if cid in candidates_by_list]
        if titulars:
            lead = titulars[0]
            party["lead_candidates"].append(
                {
                    "province": row["province"],
                    "person_name": lead["person_name"],
                    "candidate_id": lead["candidate_id"],
                    "person_id": lead.get("person_id"),
                    "person_match_status": lead.get("person_match_status", "not_matched"),
                    "mandate_count": lead.get("mandate_count", 0),
                    "active_mandate_count": lead.get("active_mandate_count", 0),
                    "accountability_evidence_status": lead.get("accountability_evidence_status", "not_matchable"),
                    "parliament_vote_summary": candidate_votes_by_id.get(lead["candidate_id"], {}),
                    "reviewed_legislative_impact_summary": reviewed_candidate_votes_by_id.get(lead["candidate_id"], {}),
                }
            )
        party["matched_candidates_total"] += sum(
            1 for cid in row["titular_candidates"] + row["suplente_candidates"]
            if candidates_by_list.get(cid, {}).get("person_id")
        )

    parties = list(by_party.values())
    for party in parties:
        party["provinces"] = sorted(set(party["provinces"]))
        if party["matched_candidates_total"] > 0:
            party["assessment_status"] = "candidate_list_plus_actor_backbone"
    return sorted(parties, key=lambda p: (-p["candidate_lists_total"], p["party_acronym"]))


def build_focus_candidates(
    candidates: list[dict[str, Any]],
    program_report: dict[str, Any] | None = None,
    evidence_report: dict[str, Any] | None = None,
    boja_report: dict[str, Any] | None = None,
    parliament_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    by_name = {candidate["person_name_normalized"]: candidate for candidate in candidates}
    programs_by_party = (program_report or {}).get("by_party") or {}
    measures_by_party = (program_report or {}).get("measures_by_party") or {}
    evidence_report = evidence_report or empty_accountability_evidence_report()
    boja_report = boja_report or empty_boja_norms_report()
    parliament_report = parliament_report or empty_parliament_activity_report()
    candidate_votes_by_id = {
        str(row.get("candidate_id") or ""): row
        for row in parliament_report.get("candidate_vote_summaries") or []
        if isinstance(row, dict)
    }
    reviewed_candidate_votes_by_id = {
        str(row.get("candidate_id") or ""): row
        for row in parliament_report.get("reviewed_candidate_vote_summaries") or []
        if isinstance(row, dict)
    }
    out: list[dict[str, Any]] = []
    for focus in FOCUS_CANDIDATES:
        candidate = by_name.get(normalize_label(focus["person_name"]))
        row = dict(focus)
        party_key = stable_slug(focus["party_acronym"])
        program_sources = [compact_program_source(item) for item in programs_by_party.get(party_key, [])]
        program_measures = list(measures_by_party.get(party_key, []))
        program_verified = sum(1 for item in program_sources if item["verification_status"] == "verified_by_text")
        actor_key = f"person_id:{candidate.get('person_id')}" if candidate and candidate.get("person_id") else ""
        accountability_evidence = build_accountability_evidence_ref(
            evidence_report,
            actor_key,
            match_scope="person_id_exact",
            match_note="Exact person_id match against the published accountability Evidence API.",
        )
        if candidate:
            row.update(
                {
                    "candidate_id": candidate["candidate_id"],
                    "official_person_name": candidate["person_name"],
                    "province": candidate["province"],
                    "candidature_name": candidate["candidature_name"],
                    "list_position": candidate["list_position"],
                    "person_id": candidate.get("person_id"),
                    "person_match_status": candidate.get("person_match_status", "not_matched"),
                    "mandate_count": candidate.get("mandate_count", 0),
                    "active_mandate_count": candidate.get("active_mandate_count", 0),
                    "mandates_sample": candidate.get("mandates_sample", []),
                    "source_url": candidate["source_url"],
                    "assessment": {
                        "status": "not_assessed",
                        "reason": "Official candidate identity is known; merit/blame needs issue evidence before scoring.",
                    },
                    "program_sources": program_sources,
                    "program_sources_total": len(program_sources),
                    "program_verified_sources_total": program_verified,
                    "program_measures_total": len(program_measures),
                    "program_measure_topics": sorted({measure["topic_id"] for measure in program_measures}),
                    "program_measure_samples": program_measures[:5],
                    "accountability_evidence": accountability_evidence,
                    "parliament_vote_summary": candidate_votes_by_id.get(candidate["candidate_id"], {}),
                    "reviewed_legislative_impact_summary": reviewed_candidate_votes_by_id.get(candidate["candidate_id"], {}),
                    "program_source_status": (
                        "program_text_ready"
                        if program_verified
                        else "program_source_unverified"
                        if program_sources
                        else "missing_program_source"
                    ),
                    "lanes": build_evidence_lanes(
                        program_report or empty_program_report(DEFAULT_PROGRAM_SOURCES),
                        boja_report,
                        parliament_report,
                    ),
                }
            )
        else:
            row.update(
                {
                    "person_match_status": "not_in_official_candidate_pdf",
                    "assessment": {
                        "status": "blocked",
                        "reason": "Focus candidate was not found in parsed official candidature PDF.",
                    },
                    "program_sources": program_sources,
                    "program_sources_total": len(program_sources),
                    "program_verified_sources_total": program_verified,
                    "program_measures_total": len(program_measures),
                    "program_measure_topics": sorted({measure["topic_id"] for measure in program_measures}),
                    "program_measure_samples": program_measures[:5],
                    "accountability_evidence": build_accountability_evidence_ref(
                        evidence_report,
                        "",
                        match_scope="not_in_official_candidate_pdf",
                        match_note="Focus candidate was not found in parsed official candidature PDF.",
                    ),
                    "parliament_vote_summary": {},
                    "reviewed_legislative_impact_summary": {},
                    "program_source_status": (
                        "program_text_ready"
                        if program_verified
                        else "program_source_unverified"
                        if program_sources
                        else "missing_program_source"
                    ),
                    "lanes": build_evidence_lanes(
                        program_report or empty_program_report(DEFAULT_PROGRAM_SOURCES),
                        boja_report,
                        parliament_report,
                    ),
                }
            )
        out.append(row)
    return out


def primary_responsibility_gap(gaps: list[str]) -> str:
    return gaps[0] if gaps else "ready_for_issue_review"


def accountability_evidence_counts(evidence_ref: dict[str, Any]) -> tuple[int, int]:
    return int(evidence_ref.get("entries_total") or 0), int(evidence_ref.get("issues_total") or 0)


def empty_issue_reviews_report(path: Path | None = None) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_issue_reviews_v1",
        "status": "missing",
        "source_path": str(path or ""),
        "reviews_total": 0,
        "applied_reviews_total": 0,
        "reviews": [],
        "reviews_by_topic": {},
    }


def load_issue_reviews(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_issue_reviews_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviews = [row for row in payload.get("reviews", []) if isinstance(row, dict)]
    reviews_by_topic = {
        str(row.get("topic_id") or ""): row
        for row in reviews
        if row.get("topic_id")
    }
    return {
        "schema_version": payload.get("schema_version") or "andalucia_2026_issue_reviews_v1",
        "status": "ok",
        "source_path": str(path),
        "review_policy": payload.get("review_policy") or "",
        "reviews_total": len(reviews),
        "applied_reviews_total": 0,
        "reviews": reviews,
        "reviews_by_topic": reviews_by_topic,
    }


def compact_issue_level_review(review: dict[str, Any]) -> dict[str, Any]:
    topic_id = str(review.get("topic_id") or "")
    return {
        "review_id": review.get("review_id") or stable_slug(f"andalucia-2026-issue-review:{topic_id}"),
        "topic_id": topic_id,
        "topic_label": review.get("topic_label") or program_topic_label(topic_id),
        "review_status": review.get("review_status") or "",
        "claim_status": review.get("claim_status") or "",
        "interpretation_status": review.get("interpretation_status") or "",
        "citizen_direction_status": review.get("citizen_direction_status") or "",
        "citizen_direction_label": review.get("citizen_direction_label") or "",
        "responsible_actor_status": review.get("responsible_actor_status") or "",
        "responsible_actor_label": review.get("responsible_actor_label") or "",
        "execution_owner_status": review.get("execution_owner_status") or "",
        "execution_owner_label": review.get("execution_owner_label") or "",
        "budget_execution_status": review.get("budget_execution_status") or "",
        "budget_execution_label": review.get("budget_execution_label") or "",
        "outcome_status": review.get("outcome_status") or "",
        "merit_blame_status": review.get("merit_blame_status") or "",
        "review_summary": review.get("review_summary") or "",
        "review_confidence": review.get("review_confidence") or "",
        "reviewed_by": review.get("reviewed_by") or "",
        "reviewed_at": review.get("reviewed_at") or "",
        "evidence_refs": [
            {
                "source_kind": str(row.get("source_kind") or ""),
                "source_id": str(row.get("source_id") or ""),
                "source_url": str(row.get("source_url") or ""),
                "source_locator": str(row.get("source_locator") or ""),
                "evidence_excerpt": compact_evidence_quote(row.get("evidence_excerpt"), max_words=28, max_chars=240),
            }
            for row in review.get("evidence_refs") or []
            if isinstance(row, dict)
        ][:6],
        "execution_refs": [
            {
                "source_kind": str(row.get("source_kind") or ""),
                "source_id": str(row.get("source_id") or ""),
                "source_url": str(row.get("source_url") or ""),
                "source_locator": str(row.get("source_locator") or ""),
                "evidence_excerpt": compact_evidence_quote(row.get("evidence_excerpt"), max_words=28, max_chars=240),
            }
            for row in review.get("execution_refs") or []
            if isinstance(row, dict)
        ][:4],
        "budget_refs": [
            {
                "source_kind": str(row.get("source_kind") or ""),
                "source_id": str(row.get("source_id") or ""),
                "source_url": str(row.get("source_url") or ""),
                "source_locator": str(row.get("source_locator") or ""),
                "program_code": str(row.get("program_code") or ""),
                "program_name": str(row.get("program_name") or ""),
                "org_section": str(row.get("org_section") or ""),
                "budget_item": str(row.get("budget_item") or ""),
                "budget_project": str(row.get("budget_project") or ""),
                "amount_eur": parse_execution_amount(row.get("amount_eur")),
                "review_status": str(row.get("review_status") or ""),
                "evidence_excerpt": compact_evidence_quote(row.get("evidence_excerpt"), max_words=28, max_chars=240),
            }
            for row in review.get("budget_refs") or []
            if isinstance(row, dict)
        ][:4],
        "open_limitations": [str(value) for value in review.get("open_limitations") or [] if value][:8],
    }


def issue_review_has_direction(review: dict[str, Any]) -> bool:
    return str(review.get("citizen_direction_status") or "") in {
        "legal_direction_documented_outcome_pending",
        "direction_partially_reviewed_outcome_pending",
    }


def issue_review_has_actor_signal(review: dict[str, Any]) -> bool:
    return str(review.get("responsible_actor_status") or "") in {
        "legislative_and_publisher_actor_observed_execution_owner_pending",
        "legislative_publisher_and_execution_actor_observed_budget_pending",
        "responsible_actor_partially_observed",
    }


def issue_review_has_execution_owner(review: dict[str, Any]) -> bool:
    return str(review.get("execution_owner_status") or "") in {
        "execution_owner_linked_budget_amount_pending",
        "execution_owner_partially_observed",
    } or str(review.get("budget_execution_status") or "") == "budget_execution_linked"


def issue_review_has_budget_allocation(review: dict[str, Any]) -> bool:
    return str(review.get("budget_execution_status") or "") in {
        "budget_allocation_linked_execution_pending",
        "budget_allocation_and_contract_award_linked_outcome_pending",
        "budget_execution_linked",
    } or bool(review.get("budget_refs"))


BOJA_EXPECTED_REVIEWED_VOTE_EFFECT_OUTCOMES = {
    "approved_by_majority_yes",
    "decree_law_validated_by_majority_yes",
}

BOJA_EXPECTED_REVIEWED_VOTE_LEGAL_EFFECT_KINDS = {
    "law_final_approval_vote_passed",
    "decree_law_validation_vote_passed",
    "decree_law_vote_passed",
}


def reviewed_vote_expects_boja_legal_change(item: dict[str, Any]) -> bool:
    effect_outcome = str(item.get("effect_outcome") or "")
    legal_effect_kind = str(item.get("legal_effect_kind") or "")
    if effect_outcome not in BOJA_EXPECTED_REVIEWED_VOTE_EFFECT_OUTCOMES:
        return False
    return legal_effect_kind in BOJA_EXPECTED_REVIEWED_VOTE_LEGAL_EFFECT_KINDS


REVIEWED_VOTE_TOPIC_FALLBACKS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("patrimonio cultural", "cultura"), "cultura_patrimonio"),
    (("universidad", "universidades"), "educacion"),
    (("montes", "forestal"), "campo_agua"),
    (("gestion ambiental", "gestión ambiental", "ambiental"), "energia_clima"),
    (("apoyo fiscal", "fiscal", "borrasca"), "fiscalidad"),
)


def classify_reviewed_vote_citizen_topic(item: dict[str, Any]) -> dict[str, str]:
    existing_topic_id = str(item.get("topic_id") or "")
    if existing_topic_id and existing_topic_id != "sin_tema":
        return {
            "topic_id": existing_topic_id,
            "topic_label": str(item.get("topic_label") or program_topic_label(existing_topic_id)),
            "topic_source": str(item.get("topic_source") or "reviewed_vote_topic"),
        }
    text = " ".join(
        str(item.get(key) or "")
        for key in ("reviewed_issue_label", "title", "review_summary", "legal_effect_label", "numexp")
    )
    topics = classify_program_measure_topics(text, limit=1)
    if topics:
        topic = topics[0]
        return {
            "topic_id": str(topic.get("topic_id") or ""),
            "topic_label": str(topic.get("topic_label") or ""),
            "topic_source": "review_text_classifier",
        }
    normalized = normalize_label(text)
    for terms, topic_id in REVIEWED_VOTE_TOPIC_FALLBACKS:
        if any(normalize_label(term) in normalized for term in terms):
            return {
                "topic_id": topic_id,
                "topic_label": program_topic_label(topic_id),
                "topic_source": "review_label_fallback",
            }
    return {"topic_id": "sin_tema", "topic_label": "Sin tema", "topic_source": "no_topic_signal"}


def issue_packet_status(
    *,
    program_measures_total: int,
    reviewed_vote_items_total: int,
    reviewed_boja_legal_changes_total: int,
) -> str:
    if program_measures_total and reviewed_vote_items_total and reviewed_boja_legal_changes_total:
        return "program_vote_boja_reviewed"
    if program_measures_total and reviewed_vote_items_total:
        return "program_vote_reviewed"
    if program_measures_total and reviewed_boja_legal_changes_total:
        return "program_boja_reviewed"
    if reviewed_vote_items_total and reviewed_boja_legal_changes_total:
        return "vote_boja_reviewed"
    if program_measures_total:
        return "program_only"
    if reviewed_vote_items_total:
        return "reviewed_vote_only"
    if reviewed_boja_legal_changes_total:
        return "reviewed_boja_only"
    return "no_signal"


def issue_packet_gaps(
    *,
    program_measures_total: int,
    reviewed_vote_items_total: int,
    reviewed_boja_legal_changes_total: int,
    reviewed_vote_boja_expected_total: int = 0,
    observed_responsibility_claims_total: int,
    issue_review: dict[str, Any] | None = None,
) -> list[str]:
    gaps: list[str] = []
    issue_review = issue_review or {}
    if not program_measures_total:
        gaps.append("missing_program_measure")
    if not reviewed_vote_items_total:
        gaps.append("missing_reviewed_vote_signal")
    boja_gap_is_expected = reviewed_vote_items_total <= 0 or reviewed_vote_boja_expected_total > 0
    if not reviewed_boja_legal_changes_total and boja_gap_is_expected:
        gaps.append("missing_reviewed_boja_legal_change")
    if not issue_review_has_direction(issue_review):
        gaps.append("missing_citizen_direction")
    if not issue_review_has_actor_signal(issue_review):
        if observed_responsibility_claims_total and reviewed_boja_legal_changes_total:
            gaps.append("missing_execution_responsible_actor")
        else:
            gaps.append("missing_responsible_actor")
    else:
        if not issue_review_has_execution_owner(issue_review):
            gaps.append("missing_execution_owner")
    if str(issue_review.get("budget_execution_status") or "") != "budget_execution_linked":
        gaps.append("missing_budget_execution")
    if str(issue_review.get("outcome_status") or "") != "outcome_linked":
        gaps.append("missing_outcomes")
    return gaps


def ensure_issue_packet(packets: dict[str, dict[str, Any]], topic_id: str, topic_label: str) -> dict[str, Any]:
    key = topic_id or "sin_tema"
    return packets.setdefault(
        key,
        {
            "topic_id": key,
            "topic_label": topic_label or program_topic_label(key),
            "program_measures_total": 0,
            "program_parties_total": 0,
            "reviewed_vote_items_total": 0,
            "reviewed_vote_party_profiles_total": 0,
            "reviewed_vote_boja_expected_total": 0,
            "reviewed_vote_boja_not_expected_total": 0,
            "reviewed_boja_legal_changes_total": 0,
            "observed_responsibility_claims_total": 0,
            "observed_party_claims_total": 0,
            "observed_candidate_claims_total": 0,
            "program_party_counts": Counter(),
            "reviewed_vote_legal_effect_counts": Counter(),
            "party_profiles": {},
            "observed_responsibility_actor_profiles": {},
            "observed_responsibility_relation_counts": Counter(),
            "issue_review": {},
            "program_measure_samples": [],
            "reviewed_vote_samples": [],
            "reviewed_boja_samples": [],
            "observed_responsibility_claim_samples": [],
        },
    )


def ensure_issue_party_profile(packet: dict[str, Any], party_key: str, party_label: str) -> dict[str, Any]:
    profiles = packet["party_profiles"]
    return profiles.setdefault(
        party_key,
        {
            "party_key": party_key,
            "party_label": party_label or party_key,
            "program_measures_total": 0,
            "reviewed_vote_events_total": 0,
            "voted_with_reviewed_outcome_total": 0,
            "voted_against_reviewed_outcome_total": 0,
            "abstained_on_reviewed_outcome_total": 0,
            "supported_approved_effect_total": 0,
            "opposed_approved_effect_total": 0,
            "abstained_approved_effect_total": 0,
            "supported_rejected_effect_total": 0,
            "opposed_rejected_effect_total": 0,
            "abstained_rejected_effect_total": 0,
            "observed_other": 0,
        },
    )


def compact_issue_program_measure_sample(measure: dict[str, Any]) -> dict[str, Any]:
    return {
        "measure_id": measure.get("measure_id") or "",
        "party_key": measure.get("party_key") or "",
        "party_acronym": measure.get("party_acronym") or "",
        "action_kind": measure.get("action_kind") or "",
        "evidence_excerpt": measure.get("evidence_excerpt") or "",
        "source_url": measure.get("source_url") or "",
        "source_title": measure.get("source_title") or "",
        "claim_status": measure.get("claim_status") or "",
    }


def compact_issue_vote_sample(item: dict[str, Any], topic_info: dict[str, str]) -> dict[str, Any]:
    return {
        "review_item_id": item.get("review_item_id") or "",
        "vote_event_id": item.get("vote_event_id") or "",
        "date": item.get("date") or "",
        "numexp": item.get("numexp") or "",
        "title": compact_evidence_quote(item.get("title"), max_words=18, max_chars=180),
        "reviewed_issue_label": item.get("reviewed_issue_label") or "",
        "effect_outcome": item.get("effect_outcome") or "",
        "majority_side": item.get("majority_side") or "",
        "topic_id": topic_info.get("topic_id") or "",
        "topic_source": topic_info.get("topic_source") or "",
        "source_url": item.get("source_url") or "",
        "claim_status": item.get("claim_status") or "",
    }


def compact_issue_boja_sample(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_item_id": item.get("review_item_id") or "",
        "boja_id": item.get("boja_id") or "",
        "date": item.get("date") or "",
        "action_kind": item.get("action_kind") or "",
        "reviewed_legal_change_label": item.get("reviewed_legal_change_label") or "",
        "impact_status": item.get("impact_status") or "",
        "responsibility_status": item.get("responsibility_status") or "",
        "source_url": item.get("source_url") or "",
        "claim_status": item.get("claim_status") or "",
    }


def compact_issue_responsibility_claim_sample(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": claim.get("claim_id") or "",
        "actor_kind": claim.get("actor_kind") or "",
        "actor_key": claim.get("actor_key") or "",
        "actor_label": claim.get("actor_label") or "",
        "relation_to_outcome": claim.get("relation_to_outcome") or "",
        "vote_position": claim.get("vote_position") or "",
        "effect_outcome": claim.get("effect_outcome") or "",
        "statement": compact_evidence_quote(claim.get("statement"), max_words=24, max_chars=220),
        "source_url": claim.get("source_url") or "",
        "claim_status": claim.get("claim_status") or "",
    }


def ensure_issue_responsibility_actor_profile(packet: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    actor_kind = str(claim.get("actor_kind") or "actor")
    actor_key = str(claim.get("actor_key") or "")
    profile_key = f"{actor_kind}:{actor_key}"
    profiles = packet["observed_responsibility_actor_profiles"]
    return profiles.setdefault(
        profile_key,
        {
            "actor_kind": actor_kind,
            "actor_key": actor_key,
            "actor_label": claim.get("actor_label") or actor_key,
            "party_key": claim.get("party_key") or "",
            "claims_total": 0,
            "with_reviewed_outcome_total": 0,
            "against_reviewed_outcome_total": 0,
            "abstained_on_reviewed_outcome_total": 0,
            "observed_other_total": 0,
        },
    )


def normalize_issue_packet(packet: dict[str, Any]) -> dict[str, Any]:
    program_party_counts = [
        {"party_key": key, "measures_total": count}
        for key, count in sorted(packet["program_party_counts"].items(), key=lambda item: (-item[1], item[0]))
    ]
    party_profiles = sorted(
        packet["party_profiles"].values(),
        key=lambda row: (
            -int(row.get("reviewed_vote_events_total") or 0),
            -int(row.get("program_measures_total") or 0),
            str(row.get("party_key") or ""),
        ),
    )
    observed_actor_profiles = sorted(
        packet["observed_responsibility_actor_profiles"].values(),
        key=lambda row: (
            -int(row.get("claims_total") or 0),
            str(row.get("actor_kind") or ""),
            str(row.get("actor_label") or ""),
        ),
    )
    observed_relation_counts = [
        {"key": key, "count": count}
        for key, count in sorted(
            packet["observed_responsibility_relation_counts"].items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    program_measures_total = int(packet.get("program_measures_total") or 0)
    reviewed_vote_items_total = int(packet.get("reviewed_vote_items_total") or 0)
    reviewed_vote_boja_expected_total = int(packet.get("reviewed_vote_boja_expected_total") or 0)
    reviewed_vote_boja_not_expected_total = int(packet.get("reviewed_vote_boja_not_expected_total") or 0)
    reviewed_boja_legal_changes_total = int(packet.get("reviewed_boja_legal_changes_total") or 0)
    observed_responsibility_claims_total = int(packet.get("observed_responsibility_claims_total") or 0)
    issue_review = packet.get("issue_review") or {}
    out = {
        "topic_id": packet.get("topic_id") or "sin_tema",
        "topic_label": packet.get("topic_label") or "Sin tema",
        "status": issue_packet_status(
            program_measures_total=program_measures_total,
            reviewed_vote_items_total=reviewed_vote_items_total,
            reviewed_boja_legal_changes_total=reviewed_boja_legal_changes_total,
        ),
        "claim_status": "issue_evidence_packet_only_no_merit_or_blame_claim",
        "interpretation_status": "cross_source_evidence_ready_for_review",
        "program_measures_total": program_measures_total,
        "program_parties_total": len(program_party_counts),
        "reviewed_vote_items_total": reviewed_vote_items_total,
        "reviewed_vote_party_profiles_total": sum(
            1 for row in party_profiles if int(row.get("reviewed_vote_events_total") or 0) > 0
        ),
        "reviewed_vote_boja_expected_total": reviewed_vote_boja_expected_total,
        "reviewed_vote_boja_not_expected_total": reviewed_vote_boja_not_expected_total,
        "reviewed_vote_boja_expectation_status": (
            "boja_expected_for_approved_legal_effect"
            if reviewed_vote_boja_expected_total
            else "boja_not_expected_for_reviewed_vote_effects"
            if reviewed_vote_items_total
            else "boja_expectation_not_assessed_without_reviewed_vote"
        ),
        "reviewed_vote_legal_effect_counts": compact_count_rows(
            packet.get("reviewed_vote_legal_effect_counts") or {},
            limit=8,
        ),
        "reviewed_boja_legal_changes_total": reviewed_boja_legal_changes_total,
        "observed_responsibility_claims_total": observed_responsibility_claims_total,
        "observed_party_claims_total": int(packet.get("observed_party_claims_total") or 0),
        "observed_candidate_claims_total": int(packet.get("observed_candidate_claims_total") or 0),
        "observed_responsibility_actor_profiles_total": len(observed_actor_profiles),
        "issue_review_status": issue_review.get("review_status") or "",
        "issue_review_claim_status": issue_review.get("claim_status") or "",
        "issue_review": issue_review,
        "program_party_counts": program_party_counts[:8],
        "party_profiles": party_profiles[:8],
        "observed_responsibility_actor_profiles": observed_actor_profiles[:8],
        "observed_responsibility_relation_counts": observed_relation_counts[:8],
        "program_measure_samples": packet["program_measure_samples"][:4],
        "reviewed_vote_samples": packet["reviewed_vote_samples"][:4],
        "reviewed_boja_samples": packet["reviewed_boja_samples"][:4],
        "observed_responsibility_claim_samples": packet["observed_responsibility_claim_samples"][:4],
        "open_gaps": issue_packet_gaps(
            program_measures_total=program_measures_total,
            reviewed_vote_items_total=reviewed_vote_items_total,
            reviewed_boja_legal_changes_total=reviewed_boja_legal_changes_total,
            reviewed_vote_boja_expected_total=reviewed_vote_boja_expected_total,
            observed_responsibility_claims_total=observed_responsibility_claims_total,
            issue_review=issue_review,
        ),
    }
    return out


def build_issue_accountability_packets(
    program_report: dict[str, Any],
    parliament_report: dict[str, Any],
    boja_report: dict[str, Any],
    parties: list[dict[str, Any]],
    published_accountability_claims: dict[str, Any] | None = None,
    issue_reviews_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packets: dict[str, dict[str, Any]] = {}
    party_labels = {
        str(party.get("party_key") or ""): str(party.get("party_acronym") or party.get("party_key") or "")
        for party in parties
    }

    for measure in program_report.get("measures") or []:
        if not isinstance(measure, dict):
            continue
        topic_id = str(measure.get("topic_id") or "sin_tema")
        packet = ensure_issue_packet(packets, topic_id, str(measure.get("topic_label") or program_topic_label(topic_id)))
        party_key = str(measure.get("party_key") or "")
        party_label = str(measure.get("party_acronym") or party_labels.get(party_key) or party_key)
        packet["program_measures_total"] += 1
        if party_key:
            packet["program_party_counts"][party_key] += 1
            ensure_issue_party_profile(packet, party_key, party_label)["program_measures_total"] += 1
        if len(packet["program_measure_samples"]) < 4:
            packet["program_measure_samples"].append(compact_issue_program_measure_sample(measure))

    for item in parliament_report.get("vote_impact_review_queue") or []:
        if not isinstance(item, dict) or not is_reviewed_vote_item(item):
            continue
        topic_info = classify_reviewed_vote_citizen_topic(item)
        topic_id = topic_info["topic_id"]
        packet = ensure_issue_packet(packets, topic_id, topic_info["topic_label"])
        packet["reviewed_vote_items_total"] += 1
        legal_effect_kind = str(item.get("legal_effect_kind") or "unclassified_vote")
        packet["reviewed_vote_legal_effect_counts"][legal_effect_kind] += 1
        if reviewed_vote_expects_boja_legal_change(item):
            packet["reviewed_vote_boja_expected_total"] += 1
        else:
            packet["reviewed_vote_boja_not_expected_total"] += 1
        if len(packet["reviewed_vote_samples"]) < 4:
            packet["reviewed_vote_samples"].append(compact_issue_vote_sample(item, topic_info))
        effect_outcome = str(item.get("effect_outcome") or "")
        majority_side = str(item.get("majority_side") or "")
        for party_vote in item.get("party_vote_totals") or []:
            if not isinstance(party_vote, dict):
                continue
            party_key = str(party_vote.get("party_key") or "")
            if not party_key:
                continue
            profile = ensure_issue_party_profile(
                packet,
                party_key,
                str(party_vote.get("party_acronym") or party_vote.get("party_label") or party_labels.get(party_key) or party_key),
            )
            profile["reviewed_vote_events_total"] += 1
            position = str(party_vote.get("dominant_position") or "")
            profile[party_position_effect_bucket(position, effect_outcome)] += 1
            outcome_bucket = vote_position_outcome_bucket(position, majority_side)
            if outcome_bucket != "observed_other":
                profile[outcome_bucket] += 1

    for item in boja_report.get("reviewed_impact_items") or []:
        if not isinstance(item, dict):
            continue
        topic_id = str(item.get("topic_id") or "sin_tema")
        packet = ensure_issue_packet(packets, topic_id, str(item.get("topic_label") or program_topic_label(topic_id)))
        packet["reviewed_boja_legal_changes_total"] += 1
        if len(packet["reviewed_boja_samples"]) < 4:
            packet["reviewed_boja_samples"].append(compact_issue_boja_sample(item))

    for claim in (published_accountability_claims or {}).get("claims") or []:
        if not isinstance(claim, dict):
            continue
        topic_id = str(claim.get("topic_id") or "sin_tema")
        packet = ensure_issue_packet(packets, topic_id, str(claim.get("topic_label") or program_topic_label(topic_id)))
        actor_kind = str(claim.get("actor_kind") or "")
        packet["observed_responsibility_claims_total"] += 1
        if actor_kind == "candidate":
            packet["observed_candidate_claims_total"] += 1
        else:
            packet["observed_party_claims_total"] += 1
        relation = str(claim.get("relation_to_outcome") or "observed_other")
        packet["observed_responsibility_relation_counts"][relation] += 1
        actor_profile = ensure_issue_responsibility_actor_profile(packet, claim)
        actor_profile["claims_total"] += 1
        relation_key = f"{relation}_total" if relation in {
            "with_reviewed_outcome",
            "against_reviewed_outcome",
            "abstained_on_reviewed_outcome",
        } else "observed_other_total"
        actor_profile[relation_key] += 1
        if len(packet["observed_responsibility_claim_samples"]) < 4:
            packet["observed_responsibility_claim_samples"].append(compact_issue_responsibility_claim_sample(claim))

    applied_issue_reviews_total = 0
    for review in (issue_reviews_report or {}).get("reviews") or []:
        if not isinstance(review, dict):
            continue
        topic_id = str(review.get("topic_id") or "")
        if not topic_id:
            continue
        packet = ensure_issue_packet(packets, topic_id, str(review.get("topic_label") or program_topic_label(topic_id)))
        packet["issue_review"] = compact_issue_level_review(review)
        applied_issue_reviews_total += 1
    if issue_reviews_report is not None:
        issue_reviews_report["applied_reviews_total"] = applied_issue_reviews_total

    normalized_packets = sorted(
        (normalize_issue_packet(packet) for packet in packets.values()),
        key=lambda row: (
            -int(row.get("reviewed_vote_items_total") or 0),
            -int(row.get("observed_responsibility_claims_total") or 0),
            -int(row.get("reviewed_boja_legal_changes_total") or 0),
            -int(row.get("program_measures_total") or 0),
            str(row.get("topic_label") or ""),
        ),
    )
    return {
        "schema_version": "andalucia_2026_issue_accountability_packets_v1",
        "claim_status": "issue_evidence_packet_only_no_merit_or_blame_claim",
        "interpretation_status": "cross_source_evidence_ready_for_review",
        "packets_total": len(normalized_packets),
        "packets_with_program_vote_boja_total": sum(
            1 for row in normalized_packets if row.get("status") == "program_vote_boja_reviewed"
        ),
        "packets_with_reviewed_vote_total": sum(
            1 for row in normalized_packets if int(row.get("reviewed_vote_items_total") or 0) > 0
        ),
        "packets_with_reviewed_boja_total": sum(
            1 for row in normalized_packets if int(row.get("reviewed_boja_legal_changes_total") or 0) > 0
        ),
        "packets_with_observed_responsibility_total": sum(
            1 for row in normalized_packets if int(row.get("observed_responsibility_claims_total") or 0) > 0
        ),
        "packets_with_issue_review_total": sum(
            1 for row in normalized_packets if row.get("issue_review_status")
        ),
        "issue_reviews_total": applied_issue_reviews_total,
        "issue_direction_reviews_total": sum(
            1 for row in normalized_packets if issue_review_has_direction(row.get("issue_review") or {})
        ),
        "issue_actor_reviews_total": sum(
            1 for row in normalized_packets if issue_review_has_actor_signal(row.get("issue_review") or {})
        ),
        "issue_execution_owner_reviews_total": sum(
            1 for row in normalized_packets if issue_review_has_execution_owner(row.get("issue_review") or {})
        ),
        "issue_budget_allocation_reviews_total": sum(
            1 for row in normalized_packets if issue_review_has_budget_allocation(row.get("issue_review") or {})
        ),
        "party_topic_profiles_total": sum(len(row.get("party_profiles") or []) for row in normalized_packets),
        "observed_responsibility_claims_total": sum(
            int(row.get("observed_responsibility_claims_total") or 0) for row in normalized_packets
        ),
        "observed_responsibility_actor_profiles_total": sum(
            int(row.get("observed_responsibility_actor_profiles_total") or 0) for row in normalized_packets
        ),
        "packets": normalized_packets,
    }


def compact_execution_source_candidate(source_id: str) -> dict[str, Any]:
    source = dict(EXECUTION_EVIDENCE_SOURCE_CANDIDATES.get(source_id) or {})
    return {
        "source_id": source.get("source_id") or source_id,
        "source_kind": source.get("source_kind") or "",
        "name": source.get("name") or source_id,
        "landing_url": source.get("landing_url") or "",
        "source_url": source.get("source_url") or "",
        "format": source.get("format") or "",
        "status": source.get("status") or "",
        "verified_at": source.get("verified_at") or "",
        "content_type": source.get("content_type") or "",
        "content_length_bytes": int(source.get("content_length_bytes") or 0),
        "filter_hint": source.get("filter_hint") or "",
    }


def is_verified_execution_source_status(value: Any) -> bool:
    return str(value or "") in {"head_200_verified", "get_200_verified"}


def xlsx_column_index(cell_ref: str) -> int:
    letters = "".join(char for char in str(cell_ref or "") if char.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - 64
    return max(0, index - 1)


def xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for item in root.findall("a:si", EXECUTION_EVIDENCE_XLSX_NS):
        values.append("".join(text.text or "" for text in item.findall(".//a:t", EXECUTION_EVIDENCE_XLSX_NS)))
    return values


def xlsx_first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    first_sheet = workbook.find("a:sheets/a:sheet", EXECUTION_EVIDENCE_XLSX_NS)
    if first_sheet is None:
        raise RuntimeError("XLSX without sheet")
    rel_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    for rel in rels.findall("p:Relationship", EXECUTION_EVIDENCE_XLSX_NS):
        if rel.attrib.get("Id") == rel_id:
            target = str(rel.attrib.get("Target") or "").lstrip("/")
            if target.startswith("xl/"):
                return target
            return posixpath.normpath(posixpath.join("xl", target))
    raise RuntimeError("XLSX first sheet relationship not found")


def xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//a:t", EXECUTION_EVIDENCE_XLSX_NS))
    value = cell.find("a:v", EXECUTION_EVIDENCE_XLSX_NS)
    text = value.text if value is not None else ""
    if cell_type == "s" and text:
        try:
            return shared_strings[int(text)]
        except (IndexError, ValueError):
            return text
    return text or ""


def iter_xlsx_rows(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = xlsx_shared_strings(archive)
        sheet_path = xlsx_first_sheet_path(archive)
        root = ET.fromstring(archive.read(sheet_path))
        parsed_rows: list[list[str]] = []
        for row in root.findall(".//a:sheetData/a:row", EXECUTION_EVIDENCE_XLSX_NS):
            values: list[str] = []
            for cell in row.findall("a:c", EXECUTION_EVIDENCE_XLSX_NS):
                index = xlsx_column_index(cell.attrib.get("r", "A1"))
                while len(values) <= index:
                    values.append("")
                values[index] = xlsx_cell_value(cell, shared_strings).strip()
            parsed_rows.append(values)
        return parsed_rows


def load_xlsx_dict_rows(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    rows = iter_xlsx_rows(path)
    if not rows:
        return [], []
    header = [str(value or "").strip() for value in rows[0]]
    dict_rows: list[dict[str, Any]] = []
    for row_number, values in enumerate(rows[1:], start=2):
        if not any(str(value or "").strip() for value in values):
            continue
        row: dict[str, Any] = {"_row_number": row_number}
        for index, column in enumerate(header):
            if not column:
                continue
            row[column] = str(values[index] if index < len(values) else "").strip()
        dict_rows.append(row)
    return header, dict_rows


def load_json_list_dict_rows(path: Path, *, root_key: str | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if root_key and isinstance(payload, dict):
        raw_rows = payload.get(root_key) or []
    elif isinstance(payload, dict):
        raw_rows = next((value for value in payload.values() if isinstance(value, list)), [])
    else:
        raw_rows = payload
    if not isinstance(raw_rows, list):
        return [], []
    header: list[str] = []
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for row_number, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, dict):
            continue
        row: dict[str, Any] = {"_row_number": row_number}
        for key, value in raw_row.items():
            column = str(key or "").strip()
            if not column:
                continue
            if column not in seen:
                seen.add(column)
                header.append(column)
            row[column] = str(value or "").strip()
        rows.append(row)
    return header, rows


def load_pipe_csv_dict_rows_from_text(text: str) -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    header = [str(field or "").strip() for field in (reader.fieldnames or [])]
    rows: list[dict[str, Any]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        row: dict[str, Any] = {"_row_number": row_number}
        for key, value in raw_row.items():
            column = str(key or "").strip()
            if not column:
                continue
            row[column] = str(value or "").strip()
        if any(str(value or "").strip() for key, value in row.items() if key != "_row_number"):
            rows.append(row)
    return header, rows


def load_7z_member_pipe_csv_dict_rows(path: Path, member: str) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        proc = subprocess.run(
            ["7zz", "x", "-so", str(path), member],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("7zz is required to read Junta Treasury 7z source") from exc
    text = proc.stdout.decode("utf-8-sig", errors="replace")
    return load_pipe_csv_dict_rows_from_text(text)


def is_junta_contratos_menores_source(source_id: str) -> bool:
    return source_id.startswith("junta_contratos_menores_")


def is_junta_subventions_source(source_id: str) -> bool:
    return source_id == "junta_subvenciones_programas_prioritarios"


def is_junta_treasury_payment_source(source_id: str) -> bool:
    return source_id == "junta_tesoreria_2025_pagos_agregados"


def is_ieca_ods_outcome_series_source(source_id: str) -> bool:
    return source_id.startswith("ieca_ods_")


def download_file_streaming(url: str, path: Path, *, timeout: int) -> str:
    tmp_path = path.with_suffix(path.suffix + ".part")
    resume_from = tmp_path.stat().st_size if tmp_path.exists() else 0
    headers = {"User-Agent": "vota-source-fetch/1.0", "Accept-Encoding": "identity"}
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 200) or 200)
        write_mode = "ab" if resume_from and status == 206 else "wb"
        with tmp_path.open(write_mode) as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        content_type = str(response.headers.get("content-type") or "")
    tmp_path.replace(path)
    return content_type


def fetch_junta_treasury_archive(path: Path, *, timeout: int) -> str:
    return download_file_streaming(JUNTA_TREASURY_2025_ARCHIVE_URL, path, timeout=max(timeout, 120))


def fetch_junta_subventions_program_samples(path: Path, *, timeout: int) -> None:
    results: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for program in JUNTA_SUBVENTIONS_PRIORITY_PROGRAMS:
        params = {
            "regulatory_base": "-",
            "organism": "-",
            "program": program,
            "type": "-",
            "order_by": "grant_date",
            "mode": "DESC",
            "format": "json",
            "size": str(JUNTA_SUBVENTIONS_PROGRAM_SAMPLE_SIZE),
        }
        url = JUNTA_SUBVENTIONS_SEARCH_URL + "?" + urllib.parse.urlencode(params)
        payload, content_type = http_get_bytes(url, timeout=timeout, max_attempts=1)
        data = json.loads(payload.decode("utf-8"))
        rows = data.get("results") if isinstance(data, dict) else []
        row_count = 0
        if isinstance(rows, list):
            for raw_row in rows:
                if not isinstance(raw_row, dict):
                    continue
                row = dict(raw_row)
                row["_query_program"] = program
                row_id = str(row.get("id_seq") or row.get("id_system_internal") or f"{program}:{row_count}")
                if row_id in seen_ids:
                    continue
                seen_ids.add(row_id)
                results.append(row)
                row_count += 1
        queries.append(
            {
                "program": program,
                "url": url,
                "content_type": content_type,
                "rows_total": row_count,
                "total_hits": int(data.get("total_hits") or 0) if isinstance(data, dict) else 0,
            }
        )
    write_json(
        path,
        {
            "schema_version": "andalucia_2026_junta_subventions_program_sample_v1",
            "generated_at": now_utc_iso(),
            "source_url": JUNTA_SUBVENTIONS_SEARCH_URL,
            "programs": list(JUNTA_SUBVENTIONS_PRIORITY_PROGRAMS),
            "sample_size_per_program": JUNTA_SUBVENTIONS_PROGRAM_SAMPLE_SIZE,
            "queries": queries,
            "results_total": len(results),
            "results": results,
        },
    )


def ieca_metadata_label(item: dict[str, Any]) -> str:
    return normalize_label(" ".join(str(item.get(key) or "") for key in ("des", "alias", "cod", "name")))


def ieca_cell_text(cell: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(cell.get(key) or "").strip()
        if value:
            return value
    codes = cell.get("cod")
    if isinstance(codes, list) and codes:
        return "|".join(str(code) for code in codes)
    return ""


def parse_ieca_numeric_text(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or not re.search(r"\d", text):
        return None
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in {"-", ",", "."}:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def ieca_cell_has_numeric_value(cell: dict[str, Any]) -> bool:
    return parse_ieca_numeric_text(cell.get("val")) is not None or parse_ieca_numeric_text(cell.get("format")) is not None


def load_ieca_ods_outcome_series_rows(source_id: str, path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return [], []
    metainfo = payload.get("metainfo") if isinstance(payload.get("metainfo"), dict) else {}
    hierarchies = payload.get("hierarchies") if isinstance(payload.get("hierarchies"), list) else []
    measures = payload.get("measures") if isinstance(payload.get("measures"), list) else []
    data_rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    hierarchy_count = len(hierarchies)
    territory_index = 0
    year_index = 1
    for index, hierarchy in enumerate(hierarchies):
        if not isinstance(hierarchy, dict):
            continue
        label = ieca_metadata_label(hierarchy)
        if "territorio" in label:
            territory_index = index
        if "temporal" in label or "anual" in label:
            year_index = index
    measure_start = hierarchy_count if hierarchy_count else 2
    rows: list[dict[str, Any]] = []
    for raw_order, raw_row in enumerate(data_rows, start=1):
        if not isinstance(raw_row, list) or len(raw_row) < 3:
            continue
        territory = raw_row[territory_index] if territory_index < len(raw_row) and isinstance(raw_row[territory_index], dict) else {}
        period = raw_row[year_index] if year_index < len(raw_row) and isinstance(raw_row[year_index], dict) else {}
        measure_cells: list[tuple[int, str, dict[str, Any]]] = []
        for cell_index, cell in enumerate(raw_row[measure_start:], start=measure_start):
            if not isinstance(cell, dict):
                continue
            measure_index = cell_index - measure_start
            measure = measures[measure_index] if measure_index < len(measures) and isinstance(measures[measure_index], dict) else {}
            measure_cells.append((cell_index, ieca_metadata_label(measure), cell))
        value_cell: dict[str, Any] = {}
        value_cell_index = -1
        for cell_index, measure_label, cell in measure_cells:
            if "estado" in measure_label:
                continue
            if ieca_cell_has_numeric_value(cell):
                value_cell = cell
                value_cell_index = cell_index
                break
        if not value_cell:
            for cell_index, _measure_label, cell in measure_cells:
                if ieca_cell_has_numeric_value(cell):
                    value_cell = cell
                    value_cell_index = cell_index
                    break
        if not value_cell:
            continue
        state_cell: dict[str, Any] = {}
        for cell_index, measure_label, cell in measure_cells:
            if cell_index == value_cell_index:
                continue
            if "estado" in measure_label:
                state_cell = cell
                break
        if not state_cell:
            for cell_index, _measure_label, cell in measure_cells:
                if cell_index != value_cell_index:
                    state_cell = cell
                    break
        dimension_parts: list[str] = []
        for index, hierarchy in enumerate(hierarchies):
            if index in {territory_index, year_index} or index >= len(raw_row) or not isinstance(hierarchy, dict):
                continue
            cell = raw_row[index] if isinstance(raw_row[index], dict) else {}
            hierarchy_label = str(hierarchy.get("des") or hierarchy.get("alias") or f"Dimension {index + 1}").strip()
            cell_value = ieca_cell_text(cell, "des", "format", "val")
            if cell_value:
                dimension_parts.append(f"{hierarchy_label}: {cell_value}")
        period_codes = period.get("cod") if isinstance(period.get("cod"), list) else []
        year_text = str(period.get("des") or (period_codes[0] if period_codes else "")).strip()
        try:
            year_sort = int(year_text)
        except ValueError:
            year_sort = 0
        outcome_value = ieca_cell_text(value_cell, "val", "format")
        outcome_value_format = ieca_cell_text(value_cell, "format", "val")
        rows.append(
            {
                "_raw_order": raw_order,
                "_year_sort": year_sort,
                "indicator_title": str(metainfo.get("title") or ""),
                "indicator_activity": str(metainfo.get("activity") or ""),
                "indicator_periodicity": str(metainfo.get("periodicity") or ""),
                "indicator_unit": IECA_ODS_OUTCOME_UNIT_HINTS.get(source_id, "Valor"),
                "territory_code": "|".join(str(code) for code in territory.get("cod") or []),
                "territory_name": str(territory.get("des") or ""),
                "year": year_text,
                "outcome_value": outcome_value,
                "outcome_value_format": outcome_value_format,
                "outcome_status": ieca_cell_text(state_cell, "format", "val"),
                "outcome_dimension_context": "; ".join(dimension_parts),
            }
        )
    rows.sort(
        key=lambda row: (
            0 if normalize_label(row.get("territory_name")) == "andalucia" else 1,
            0
            if not row.get("outcome_dimension_context")
            or "ambos sexos" in normalize_label(row.get("outcome_dimension_context"))
            else 1,
            normalize_label(row.get("outcome_dimension_context")),
            -int(row.get("_year_sort") or 0),
            int(row.get("_raw_order") or 0),
        )
    )
    for row_number, row in enumerate(rows, start=1):
        row["_row_number"] = row_number
    annotate_ieca_outcome_series_rows(source_id, rows)
    header = [
        "indicator_title",
        "indicator_activity",
        "indicator_periodicity",
        "indicator_unit",
        "territory_code",
        "territory_name",
        "year",
        "outcome_value",
        "outcome_value_format",
        "outcome_status",
        "outcome_dimension_context",
    ]
    return header, rows


def outcome_series_year(row: dict[str, Any]) -> int:
    try:
        return int(str(row.get("year") or row.get("outcome_year") or "").strip())
    except ValueError:
        return 0


def outcome_series_numeric_value(row: dict[str, Any]) -> float | None:
    value = parse_ieca_numeric_text(row.get("outcome_value"))
    if value is not None:
        return value
    return parse_ieca_numeric_text(row.get("outcome_value_format"))


def preferred_ieca_outcome_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [
        row
        for row in rows
        if outcome_series_year(row) > 0
        and outcome_series_numeric_value(row) is not None
        and normalize_label(row.get("territory_name")) == "andalucia"
    ]
    if not eligible:
        eligible = [
            row
            for row in rows
            if outcome_series_year(row) > 0 and outcome_series_numeric_value(row) is not None
        ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        groups[normalize_label(row.get("outcome_dimension_context"))].append(row)
    if not groups:
        return []

    def group_key(item: tuple[str, list[dict[str, Any]]]) -> tuple[int, int, int, str]:
        dimension_key, group_rows = item
        is_preferred_dimension = not dimension_key or "ambos sexos" in dimension_key
        latest_year = max(outcome_series_year(row) for row in group_rows)
        return (
            0 if is_preferred_dimension else 1,
            -len({outcome_series_year(row) for row in group_rows}),
            -latest_year,
            dimension_key,
        )

    _dimension_key, selected_rows = sorted(groups.items(), key=group_key)[0]
    return sorted(selected_rows, key=lambda row: outcome_series_year(row))


def outcome_series_interval_years(periodicity: Any) -> int:
    label = normalize_label(periodicity)
    if "bienal" in label:
        return 2
    if "trimestral" in label or "quarter" in label:
        return 1
    if "mensual" in label or "month" in label:
        return 1
    return 1


def build_outcome_series_summary(
    *,
    source_id: str,
    topic_id: str,
    rows: list[dict[str, Any]],
    post_change_min_year: int = POST_CHANGE_OUTCOME_MIN_YEAR,
) -> dict[str, Any] | None:
    selected_rows = preferred_ieca_outcome_rows(rows)
    if not selected_rows:
        return None
    source = compact_execution_source_candidate(source_id)
    latest = max(selected_rows, key=outcome_series_year)
    first = min(selected_rows, key=outcome_series_year)
    pre_change_rows = [row for row in selected_rows if outcome_series_year(row) < post_change_min_year]
    baseline = max(pre_change_rows, key=outcome_series_year) if pre_change_rows else first
    post_change_rows = [row for row in selected_rows if outcome_series_year(row) >= post_change_min_year]
    latest_year = outcome_series_year(latest)
    baseline_year = outcome_series_year(baseline)
    interval_years = outcome_series_interval_years(latest.get("indicator_periodicity"))
    next_check_year = max(post_change_min_year, latest_year + interval_years)
    status = (
        "post_change_observed_needs_review"
        if post_change_rows
        else "waiting_for_post_change_period"
    )
    return {
        "series_id": stable_slug(f"post-change-outcome:{topic_id}:{source_id}"),
        "topic_id": topic_id,
        "topic_label": program_topic_label(topic_id),
        "source_id": source_id,
        "source_name": source.get("name") or source_id,
        "source_kind": source.get("source_kind") or "",
        "source_url": source.get("source_url") or "",
        "landing_url": source.get("landing_url") or "",
        "indicator_name": latest.get("indicator_title") or "",
        "indicator_unit": latest.get("indicator_unit") or "",
        "outcome_periodicity": latest.get("indicator_periodicity") or "",
        "outcome_territory": latest.get("territory_name") or "",
        "outcome_dimension_context": latest.get("outcome_dimension_context") or "",
        "first_year": str(outcome_series_year(first) or ""),
        "first_value": first.get("outcome_value") or "",
        "first_value_format": first.get("outcome_value_format") or first.get("outcome_value") or "",
        "baseline_year": str(baseline_year or ""),
        "baseline_value": baseline.get("outcome_value") or "",
        "baseline_value_format": baseline.get("outcome_value_format") or baseline.get("outcome_value") or "",
        "latest_year": str(latest_year or ""),
        "latest_value": latest.get("outcome_value") or "",
        "latest_value_format": latest.get("outcome_value_format") or latest.get("outcome_value") or "",
        "post_change_min_year": post_change_min_year,
        "post_change_rows_total": len(post_change_rows),
        "post_change_status": status,
        "next_post_change_check_year": next_check_year,
        "years_observed_total": len({outcome_series_year(row) for row in selected_rows}),
        "claim_status": "official_outcome_monitor_no_merit_or_blame",
        "interpretation_status": (
            "post_change_outcome_candidate_needs_causality_review"
            if post_change_rows
            else "official_series_baseline_waiting_for_post_change_data"
        ),
        "automation_command": "just etl-andalucia-2026-accountability-assist",
        "open_limitations": [
            "post_change_series_not_yet_reviewed" if post_change_rows else "post_change_period_not_available",
            "series_not_actor_linked",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ],
    }


def annotate_ieca_outcome_series_rows(source_id: str, rows: list[dict[str, Any]]) -> None:
    summary = build_outcome_series_summary(source_id=source_id, topic_id="", rows=rows)
    if not summary:
        return
    for row in rows:
        row["outcome_first_year"] = summary.get("first_year") or ""
        row["outcome_first_value"] = summary.get("first_value") or ""
        row["outcome_first_value_format"] = summary.get("first_value_format") or ""
        row["outcome_baseline_year"] = summary.get("baseline_year") or ""
        row["outcome_baseline_value"] = summary.get("baseline_value") or ""
        row["outcome_baseline_value_format"] = summary.get("baseline_value_format") or ""
        row["outcome_latest_year"] = summary.get("latest_year") or ""
        row["outcome_latest_value"] = summary.get("latest_value") or ""
        row["outcome_latest_value_format"] = summary.get("latest_value_format") or ""
        row["outcome_post_change_status"] = summary.get("post_change_status") or ""
        row["outcome_post_change_rows_total"] = summary.get("post_change_rows_total") or 0
        row["outcome_next_post_change_check_year"] = summary.get("next_post_change_check_year") or ""


def build_post_change_outcome_monitor(
    source_rows: dict[str, list[dict[str, Any]]],
    *,
    post_change_min_year: int = POST_CHANGE_OUTCOME_MIN_YEAR,
) -> dict[str, Any]:
    source_topics: dict[str, set[str]] = defaultdict(set)
    for topic_id, plans in ISSUE_EXECUTION_EVIDENCE_PLANS.items():
        for plan in plans:
            if str(plan.get("gap_id") or "") != "missing_outcomes":
                continue
            for source_id in plan.get("source_candidate_ids") or []:
                source_id = str(source_id or "")
                if is_ieca_ods_outcome_series_source(source_id):
                    source_topics[source_id].add(topic_id)

    series: list[dict[str, Any]] = []
    for source_id, topic_ids in sorted(source_topics.items()):
        rows = source_rows.get(source_id) or []
        for topic_id in sorted(topic_ids):
            summary = build_outcome_series_summary(
                source_id=source_id,
                topic_id=topic_id,
                rows=rows,
                post_change_min_year=post_change_min_year,
            )
            if summary:
                series.append(summary)
            else:
                source = compact_execution_source_candidate(source_id)
                series.append(
                    {
                        "series_id": stable_slug(f"post-change-outcome:{topic_id}:{source_id}:missing"),
                        "topic_id": topic_id,
                        "topic_label": program_topic_label(topic_id),
                        "source_id": source_id,
                        "source_name": source.get("name") or source_id,
                        "source_kind": source.get("source_kind") or "",
                        "source_url": source.get("source_url") or "",
                        "landing_url": source.get("landing_url") or "",
                        "post_change_min_year": post_change_min_year,
                        "post_change_rows_total": 0,
                        "post_change_status": "series_rows_missing",
                        "claim_status": "official_outcome_monitor_no_merit_or_blame",
                        "interpretation_status": "source_declared_but_rows_missing",
                        "automation_command": "just etl-andalucia-2026-accountability-assist",
                        "open_limitations": [
                            "series_rows_missing",
                            "causal_impact_not_claimed",
                            "merit_blame_not_scored",
                        ],
                    }
                )
    series.sort(
        key=lambda row: (
            0 if row.get("post_change_status") == "post_change_observed_needs_review" else 1,
            int(row.get("next_post_change_check_year") or 9999),
            str(row.get("topic_id") or ""),
            str(row.get("source_id") or ""),
        )
    )
    status_counts = Counter(str(row.get("post_change_status") or "") for row in series)
    return {
        "schema_version": "andalucia_2026_post_change_outcome_monitor_v1",
        "status": (
            "post_change_candidates_ready"
            if status_counts.get("post_change_observed_needs_review")
            else "waiting_for_post_change_data"
        ),
        "post_change_min_year": post_change_min_year,
        "series_total": len(series),
        "topics_total": len({str(row.get("topic_id") or "") for row in series}),
        "post_change_candidate_series_total": status_counts.get("post_change_observed_needs_review", 0),
        "waiting_series_total": status_counts.get("waiting_for_post_change_period", 0),
        "missing_series_total": status_counts.get("series_rows_missing", 0),
        "status_counts": dict(status_counts),
        "next_post_change_check_year": min(
            (int(row.get("next_post_change_check_year") or 9999) for row in series),
            default=post_change_min_year,
        ),
        "claim_status": "official_outcome_monitor_no_merit_or_blame",
        "automation_command": "just etl-andalucia-2026-accountability-assist",
        "series": series,
        "open_limitations": [
            "monitor_flags_series_availability_only",
            "post_change_series_needs_human_and_causal_review_before_merit_blame",
        ],
    }


def empty_post_change_outcome_monitor() -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_post_change_outcome_monitor_v1",
        "status": "not_collected",
        "post_change_min_year": POST_CHANGE_OUTCOME_MIN_YEAR,
        "series_total": 0,
        "topics_total": 0,
        "post_change_candidate_series_total": 0,
        "waiting_series_total": 0,
        "missing_series_total": 0,
        "status_counts": {},
        "next_post_change_check_year": POST_CHANGE_OUTCOME_MIN_YEAR,
        "claim_status": "official_outcome_monitor_no_merit_or_blame",
        "automation_command": "just etl-andalucia-2026-accountability-assist",
        "series": [],
        "open_limitations": [],
    }


def load_execution_source_dict_rows(source_id: str, path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if is_junta_contratos_menores_source(source_id):
        return load_json_list_dict_rows(path, root_key="Informe")
    if is_junta_subventions_source(source_id):
        return load_json_list_dict_rows(path, root_key="results")
    if is_junta_treasury_payment_source(source_id):
        return load_7z_member_pipe_csv_dict_rows(path, JUNTA_TREASURY_2025_PAYMENTS_MEMBER)
    if is_ieca_ods_outcome_series_source(source_id):
        return load_ieca_ods_outcome_series_rows(source_id, path)
    return load_xlsx_dict_rows(path)


def parse_execution_amount(value: Any) -> int:
    text = re.sub(r"[^\d,.-]", "", str(value or "")).strip()
    if not text:
        return 0
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return int(round(float(text)))
    except ValueError:
        return 0


def first_non_empty(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def first_value_with_key_terms(row: dict[str, Any], *terms: str) -> str:
    normalized_terms = [normalize_label(term) for term in terms if term]
    for key, value in row.items():
        normalized_key = normalize_label(key)
        if all(term in normalized_key for term in normalized_terms):
            text = str(value or "").strip()
            if text:
                return text
    return ""


def public_grant_beneficiary(row: dict[str, Any]) -> str:
    """Preserve beneficiary identity exactly as published by official source."""
    return str(row.get("beneficiary") or "").strip()


def values_with_key_terms(row: dict[str, Any], *terms: str) -> list[str]:
    normalized_terms = [normalize_label(term) for term in terms if term]
    values: list[str] = []
    for key, value in row.items():
        normalized_key = normalize_label(key)
        if all(term in normalized_key for term in normalized_terms):
            text = str(value or "").strip()
            if text:
                values.append(text)
    return values


def normalized_term_matches_text(normalized_term: str, normalized_text: str, *, strict_boundaries: bool = False) -> bool:
    if not normalized_term:
        return False
    if not strict_boundaries:
        return normalized_term in normalized_text
    pattern = r"(?<![a-z0-9])" + re.escape(normalized_term) + r"(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def cache_contract_execution_match_texts(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        row["_execution_match_primary_text"] = normalize_label(
            " ".join(
                values_with_key_terms(row, "objeto")
                + values_with_key_terms(row, "contrato")
                + values_with_key_terms(row, "cpv")
                + values_with_key_terms(row, "expediente")
                + values_with_key_terms(row, "titulo")
                + values_with_key_terms(row, "descripcion")
            )
        )
        row["_execution_match_context_text"] = normalize_label(
            " ".join(
                values_with_key_terms(row, "organo")
                + values_with_key_terms(row, "unidad")
                + values_with_key_terms(row, "lugar")
                + values_with_key_terms(row, "tipo")
            )
        )


def execution_candidate_match_score(
    *,
    source_id: str,
    row: dict[str, Any],
    search_terms: list[str],
) -> tuple[int, list[str]]:
    cached_primary_text = row.get("_execution_match_primary_text")
    cached_context_text = row.get("_execution_match_context_text")
    context_fields = (
        "ORG_SECCION_DESCRIPCION",
        "ORG_SERVICIO_DESCRIPCION",
        "FUN_PROGRAMA_DESCRIPCION",
        "FUN_POLITICA_GASTOS_DESCRIPCION",
        "FUN_POLITICA_GASTOS_VISOR",
    )
    if isinstance(cached_primary_text, str) or isinstance(cached_context_text, str):
        primary_text = str(cached_primary_text or "")
        context_text = str(cached_context_text or "")
    elif source_id == "junta_presupuesto_2026_partidas_gastos":
        primary_fields = (
            "FUN_PROGRAMA_DESCRIPCION",
            "ECO_PARTIDA_PRESUPUESTARIA",
            "FIN_FONDO_DESCRIPCION",
            "INV_PROYECTO_PRESUPUESTARIO_DESCRIPCION",
            "ORG_SERVICIO_DESCRIPCION",
        )
        primary_text = normalize_label(" ".join(str(row.get(field) or "") for field in primary_fields))
        context_text = normalize_label(" ".join(str(row.get(field) or "") for field in context_fields))
    elif is_junta_contratos_menores_source(source_id):
        primary_text = normalize_label(
            " ".join(
                values_with_key_terms(row, "objeto")
                + values_with_key_terms(row, "contrato")
                + values_with_key_terms(row, "cpv")
                + values_with_key_terms(row, "expediente")
                + values_with_key_terms(row, "titulo")
                + values_with_key_terms(row, "descripcion")
            )
        )
        context_text = normalize_label(
            " ".join(
                values_with_key_terms(row, "organo")
                + values_with_key_terms(row, "unidad")
                + values_with_key_terms(row, "lugar")
                + values_with_key_terms(row, "tipo")
            )
        )
    elif is_junta_subventions_source(source_id):
        primary_text = normalize_label(
            " ".join(
                str(row.get(field) or "")
                for field in (
                    "announcement",
                    "finality",
                    "name_program",
                    "regulatory_base",
                    "program",
                )
            )
        )
        context_text = normalize_label(
            " ".join(
                str(row.get(field) or "")
                for field in (
                    "organism",
                    "budget_application",
                    "beneficiary",
                    "type",
                    "grant_date",
                )
            )
        )
    elif is_junta_treasury_payment_source(source_id):
        primary_text = normalize_label(
            " ".join(
                str(row.get(field) or "")
                for field in (
                    "Den_Jerarquía_1",
                    "Den_Jerarquía_2",
                    "Den_Jerarquía_3",
                )
            )
        )
        context_text = normalize_label(
            " ".join(
                str(row.get(field) or "")
                for field in (
                    "Año",
                    "Mes",
                    "Id_Jerarquía_1",
                    "Id_Jerarquía_2",
                    "Id_Jerarquía_3",
                )
            )
        )
    elif is_ieca_ods_outcome_series_source(source_id):
        primary_text = normalize_label(
            " ".join(
                str(row.get(field) or "")
                for field in (
                    "indicator_title",
                    "indicator_activity",
                    "territory_name",
                    "year",
                    "outcome_value_format",
                )
            )
        )
        context_text = normalize_label(
            " ".join(
                str(row.get(field) or "")
                for field in (
                    "indicator_periodicity",
                    "indicator_unit",
                    "outcome_status",
                )
            )
        )
    else:
        primary_fields = (
            "OE_NOMBRE",
            "OE_DESCRIPCION",
            "OO_NOMBRE",
            "OO_DESCRIPCION",
            "ACT_NOMBRE",
            "ACT_DESCRIPCION",
            "IND_NOMBRE",
            "IND_FUENTE_INFORMACION",
            "IND_FORMULA_CALCULO",
            "IND_INTERPRETACION",
            "IND_OBSERVACIONES",
        )
        primary_text = normalize_label(" ".join(str(row.get(field) or "") for field in primary_fields))
        context_text = normalize_label(" ".join(str(row.get(field) or "") for field in context_fields))
    matched_terms: list[str] = []
    score = 0
    strict_term_boundaries = is_junta_treasury_payment_source(source_id)
    for term in search_terms:
        normalized_term = normalize_label(term)
        if not normalized_term:
            continue
        if normalized_term_matches_text(normalized_term, primary_text, strict_boundaries=strict_term_boundaries):
            score += 3
            matched_terms.append(term)
        elif normalized_term_matches_text(normalized_term, context_text, strict_boundaries=strict_term_boundaries):
            score += 1
            matched_terms.append(term)
    if source_id == "junta_presupuesto_2026_partidas_gastos" and score and parse_execution_amount(row.get("COM_IMPORTE")):
        score += 1
    if source_id == "junta_presupuesto_2026_objetivos_indicadores" and score and row.get("IND_CODIGO"):
        score += 1
    if is_junta_contratos_menores_source(source_id) and score and (
        parse_execution_amount(row.get("IMPORTE_ADJUDICACION_SIN_IVA"))
        or parse_execution_amount(row.get("VALOR_ESTIMADO"))
        or parse_execution_amount(first_value_with_key_terms(row, "importe"))
    ):
        score += 1
    if is_junta_subventions_source(source_id) and score and parse_execution_amount(row.get("amount")):
        score += 1
    if is_junta_treasury_payment_source(source_id) and score and parse_execution_amount(row.get("Importe_Pago")):
        score += 1
    if is_ieca_ods_outcome_series_source(source_id) and score and row.get("outcome_value"):
        score += 1
    return score, matched_terms


def compact_execution_candidate_row(
    *,
    source_id: str,
    topic_id: str,
    gap_id: str,
    row: dict[str, Any],
    source_file: Path,
    match_score: int,
    matched_terms: list[str],
) -> dict[str, Any]:
    source = compact_execution_source_candidate(source_id)
    row_number = int(row.get("_row_number") or 0)
    candidate: dict[str, Any] = {
        "candidate_row_id": stable_slug(
            f"execution-candidate:{source_id}:{row_number}:{row.get('FUN_PROGRAMA')}:{gap_id}"
        ),
        "source_id": source_id,
        "source_kind": source.get("source_kind") or "",
        "source_name": source.get("name") or source_id,
        "source_url": source.get("source_url") or "",
        "topic_id": topic_id,
        "gap_id": gap_id,
        "row_number": row_number,
        "source_file": source_file.name,
        "source_locator": f"{source_file.name}:fila {row_number}" if row_number else source_file.name,
        "match_status": "official_row_candidate_needs_review",
        "review_priority": (
            0
            if (
                gap_id == "missing_budget_execution"
                and source_id == "junta_presupuesto_2026_partidas_gastos"
            )
            or (
                gap_id in {"missing_execution_owner", "missing_outcomes"}
                and source_id == "junta_presupuesto_2026_objetivos_indicadores"
            )
            or (
                gap_id == "missing_outcomes"
                and is_ieca_ods_outcome_series_source(source_id)
            )
            or (
                gap_id == "missing_budget_execution"
                and is_junta_subventions_source(source_id)
            )
            or (
                gap_id == "missing_budget_execution"
                and is_junta_treasury_payment_source(source_id)
            )
            else 1
            if is_junta_contratos_menores_source(source_id)
            else 2
        ),
        "match_score": int(match_score),
        "matched_terms": matched_terms,
        "org_section": first_non_empty(row, "ORG_SECCION_DESCRIPCION", "ORG_SECCIONES_CONSOLIDADAS"),
        "org_service": str(row.get("ORG_SERVICIO_DESCRIPCION") or ""),
        "program_code": str(row.get("FUN_PROGRAMA") or ""),
        "program_name": str(row.get("FUN_PROGRAMA_DESCRIPCION") or ""),
        "policy_area": str(row.get("FUN_POLITICA_GASTOS_DESCRIPCION") or ""),
    }
    if source_id == "junta_presupuesto_2026_partidas_gastos":
        budget_project = str(row.get("INV_PROYECTO_PRESUPUESTARIO_DESCRIPCION") or "")
        budget_item = str(row.get("ECO_PARTIDA_PRESUPUESTARIA") or "")
        amount_eur = parse_execution_amount(row.get("COM_IMPORTE"))
        candidate.update(
            {
                "budget_chapter": str(row.get("ECO_CAPITULO_DESCRIPCION") or ""),
                "budget_item": budget_item,
                "budget_project": budget_project,
                "fund_description": str(row.get("FIN_FONDO_DESCRIPCION") or ""),
                "amount_eur": amount_eur,
                "summary": first_non_empty(
                    {"a": budget_project, "b": budget_item, "c": row.get("FUN_PROGRAMA_DESCRIPCION")},
                    "a",
                    "b",
                    "c",
                ),
            }
        )
    elif is_junta_contratos_menores_source(source_id):
        contract_object = first_non_empty(
            row,
            "OBJETO_CONTRATO",
            "OBJETO",
            "DESCRIPCION_CONTRATO",
            "TITULO_CONTRATO",
            "DESCRIPCION",
        ) or first_value_with_key_terms(row, "objeto")
        contracting_body = first_non_empty(
            row,
            "ORGANO_CONTRATACION",
            "ORGANO_CONTRATANTE",
            "DENOMINACION_ORGANO_CONTRATACION",
            "NOMBRE_ORGANO_CONTRATACION",
        ) or first_value_with_key_terms(row, "organo")
        expediente = first_non_empty(
            row,
            "NUMERO_EXPEDIENTE",
            "EXPEDIENTE",
            "CODIGO_EXPEDIENTE",
        ) or first_value_with_key_terms(row, "expediente")
        amount_eur = (
            parse_execution_amount(row.get("IMPORTE_ADJUDICACION_SIN_IVA"))
            or parse_execution_amount(row.get("VALOR_ESTIMADO"))
            or parse_execution_amount(first_value_with_key_terms(row, "importe"))
        )
        candidate.update(
            {
                "contract_object": contract_object,
                "contracting_body": contracting_body,
                "contract_reference": expediente,
                "contract_type": first_non_empty(row, "TIPO_CONTRATO", "TIPO") or first_value_with_key_terms(row, "tipo"),
                "award_date": first_non_empty(
                    row,
                    "FECHA_FORMALIZACION",
                    "FECHA_ADJUDICACION",
                    "FECHA_PUBLICACION_ADJUDICACION",
                ) or first_value_with_key_terms(row, "fecha"),
                "place": first_non_empty(
                    row,
                    "LUGAR_EJECUCION_DENOMINACION",
                    "LUGAR_EJECUCION",
                ) or first_value_with_key_terms(row, "lugar"),
                "cpv": first_non_empty(row, "CPV", "CPV_DESCRIPCION", "CPV_CODIGO") or first_value_with_key_terms(row, "cpv"),
                "amount_eur": amount_eur,
                "summary": first_non_empty(
                    {"a": contract_object, "b": expediente, "c": contracting_body},
                    "a",
                    "b",
                    "c",
                ),
            }
        )
    elif is_junta_subventions_source(source_id):
        beneficiary = public_grant_beneficiary(row)
        announcement = str(row.get("announcement") or "")
        finality = str(row.get("finality") or "")
        amount_eur = parse_execution_amount(row.get("amount"))
        candidate.update(
            {
                "program_code": str(row.get("program") or row.get("_query_program") or ""),
                "program_name": str(row.get("name_program") or ""),
                "grant_beneficiary": beneficiary,
                "grant_announcement": announcement,
                "grant_finality": finality,
                "grant_date": str(row.get("grant_date") or ""),
                "grant_year": str(row.get("award_year") or ""),
                "grant_type": str(row.get("type") or ""),
                "grant_organism": str(row.get("organism") or ""),
                "budget_application": str(row.get("budget_application") or ""),
                "regulatory_base": str(row.get("regulatory_base") or ""),
                "amount_eur": amount_eur,
                "summary": first_non_empty(
                    {"a": finality, "b": announcement, "c": beneficiary, "d": row.get("name_program")},
                    "a",
                    "b",
                    "c",
                    "d",
                ),
            }
        )
    elif is_junta_treasury_payment_source(source_id):
        hierarchy_1 = str(row.get("Den_Jerarquía_1") or "")
        hierarchy_2 = str(row.get("Den_Jerarquía_2") or "")
        hierarchy_3 = str(row.get("Den_Jerarquía_3") or "")
        amount_eur = parse_execution_amount(row.get("Importe_Pago"))
        candidate.update(
            {
                "source_locator": (
                    f"{source_file.name}:{JUNTA_TREASURY_2025_PAYMENTS_MEMBER}:fila {row_number}"
                    if row_number
                    else f"{source_file.name}:{JUNTA_TREASURY_2025_PAYMENTS_MEMBER}"
                ),
                "org_section": hierarchy_3,
                "treasury_year": str(row.get("Año") or ""),
                "treasury_month": str(row.get("Mes") or ""),
                "treasury_hierarchy_1": hierarchy_1,
                "treasury_hierarchy_2": hierarchy_2,
                "treasury_hierarchy_3": hierarchy_3,
                "amount_eur": amount_eur,
                "summary": first_non_empty(
                    {"a": hierarchy_3, "b": hierarchy_2, "c": hierarchy_1},
                    "a",
                    "b",
                    "c",
                ),
            }
        )
    elif is_ieca_ods_outcome_series_source(source_id):
        outcome_value = str(row.get("outcome_value") or "")
        outcome_value_format = str(row.get("outcome_value_format") or outcome_value)
        candidate.update(
            {
                "indicator_name": str(row.get("indicator_title") or ""),
                "indicator_unit": str(row.get("indicator_unit") or ""),
                "indicator_prevision": "",
                "outcome_territory": str(row.get("territory_name") or ""),
                "outcome_year": str(row.get("year") or ""),
                "outcome_value": outcome_value,
                "outcome_value_format": outcome_value_format,
                "outcome_periodicity": str(row.get("indicator_periodicity") or ""),
                "outcome_status": str(row.get("outcome_status") or ""),
                "outcome_dimension_context": str(row.get("outcome_dimension_context") or ""),
                "outcome_first_year": str(row.get("outcome_first_year") or ""),
                "outcome_first_value": str(row.get("outcome_first_value") or ""),
                "outcome_first_value_format": str(row.get("outcome_first_value_format") or ""),
                "outcome_baseline_year": str(row.get("outcome_baseline_year") or ""),
                "outcome_baseline_value": str(row.get("outcome_baseline_value") or ""),
                "outcome_baseline_value_format": str(row.get("outcome_baseline_value_format") or ""),
                "outcome_latest_year": str(row.get("outcome_latest_year") or row.get("year") or ""),
                "outcome_latest_value": str(row.get("outcome_latest_value") or outcome_value),
                "outcome_latest_value_format": str(
                    row.get("outcome_latest_value_format") or outcome_value_format
                ),
                "outcome_post_change_status": str(row.get("outcome_post_change_status") or ""),
                "outcome_post_change_rows_total": int(row.get("outcome_post_change_rows_total") or 0),
                "outcome_next_post_change_check_year": str(row.get("outcome_next_post_change_check_year") or ""),
                "summary": first_non_empty(
                    {
                        "a": row.get("indicator_title"),
                        "b": row.get("indicator_activity"),
                    },
                    "a",
                    "b",
                ),
            }
        )
    else:
        candidate.update(
            {
                "objective_code": str(row.get("OE_CODIGO") or ""),
                "objective_name": str(row.get("OE_NOMBRE") or ""),
                "operational_objective_name": str(row.get("OO_NOMBRE") or ""),
                "activity_code": str(row.get("ACT_CODIGO") or ""),
                "activity_name": str(row.get("ACT_NOMBRE") or ""),
                "indicator_code": str(row.get("IND_CODIGO") or ""),
                "indicator_name": str(row.get("IND_NOMBRE") or ""),
                "indicator_unit": str(row.get("IND_UNIDAD_MEDIDA") or ""),
                "indicator_prevision": str(row.get("IND_PREVISION") or ""),
                "summary": first_non_empty(
                    {
                        "a": row.get("IND_NOMBRE"),
                        "b": row.get("ACT_NOMBRE"),
                        "c": row.get("OO_NOMBRE"),
                        "d": row.get("OE_NOMBRE"),
                    },
                    "a",
                    "b",
                    "c",
                    "d",
                ),
            }
        )
    return candidate


def execution_candidate_signature(candidate: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(candidate.get("source_id") or ""),
        str(candidate.get("program_code") or ""),
        str(candidate.get("budget_project") or ""),
        str(candidate.get("budget_item") or ""),
        str(candidate.get("amount_eur") or ""),
        str(candidate.get("objective_code") or ""),
        str(candidate.get("activity_code") or ""),
        str(candidate.get("indicator_code") or ""),
        str(candidate.get("contract_reference") or ""),
        str(candidate.get("contract_object") or ""),
        str(candidate.get("contracting_body") or ""),
        str(candidate.get("grant_announcement") or ""),
        str(candidate.get("grant_beneficiary") or ""),
        str(candidate.get("grant_date") or ""),
        str(candidate.get("treasury_year") or ""),
        str(candidate.get("treasury_month") or ""),
        str(candidate.get("treasury_hierarchy_1") or ""),
        str(candidate.get("treasury_hierarchy_2") or ""),
        str(candidate.get("treasury_hierarchy_3") or ""),
        str(candidate.get("outcome_territory") or ""),
        str(candidate.get("outcome_year") or ""),
    )


def select_top_execution_candidate_rows(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    candidates.sort(
        key=lambda row: (
            int(row.get("review_priority") or 0),
            -int(row.get("match_score") or 0),
            str(row.get("source_id") or ""),
            int(row.get("row_number") or 0),
        )
    )
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        signature = execution_candidate_signature(candidate)
        if signature in seen:
            continue
        seen.add(signature)
        selected.append(candidate)
        if len(selected) >= limit:
            break
    selected_signatures = {execution_candidate_signature(row) for row in selected}
    missing_source_candidates: list[dict[str, Any]] = []
    selected_source_ids = {str(row.get("source_id") or "") for row in selected}
    for source_id in dict.fromkeys(str(row.get("source_id") or "") for row in candidates):
        if not source_id or source_id in selected_source_ids:
            continue
        source_candidate = next(
            (
                row
                for row in candidates
                if str(row.get("source_id") or "") == source_id
                and execution_candidate_signature(row) not in selected_signatures
            ),
            None,
        )
        if source_candidate is None:
            continue
        missing_source_candidates.append(source_candidate)
        selected_signatures.add(execution_candidate_signature(source_candidate))
    if missing_source_candidates:
        keep_count = max(0, int(limit) - len(missing_source_candidates))
        selected = selected[:keep_count] + missing_source_candidates[: int(limit) - keep_count]
    return selected


def collect_execution_evidence_candidates(
    *,
    raw_dir: Path,
    timeout: int,
    no_network: bool,
    strict_network: bool,
    refresh_outcome_series: bool = False,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_rows: dict[str, list[dict[str, Any]]] = {}
    source_files: list[dict[str, Any]] = []
    source_file_by_id: dict[str, Path] = {}
    for source_id, filename in EXECUTION_EVIDENCE_RAW_FILES.items():
        source = compact_execution_source_candidate(source_id)
        path = raw_dir / filename
        status = "raw_file_cached" if path.exists() else "raw_file_missing"
        error = ""
        content_type = source.get("content_type") or ""
        should_refresh = (
            bool(refresh_outcome_series)
            and path.exists()
            and is_ieca_ods_outcome_series_source(source_id)
            and not no_network
            and bool(source.get("source_url"))
        )
        if (not path.exists() or should_refresh) and not no_network and source.get("source_url"):
            try:
                if is_junta_subventions_source(source_id):
                    fetch_junta_subventions_program_samples(path, timeout=timeout)
                elif is_junta_treasury_payment_source(source_id):
                    content_type = fetch_junta_treasury_archive(path, timeout=timeout)
                else:
                    payload, content_type = http_get_bytes(str(source.get("source_url")), timeout=timeout, max_attempts=1)
                    path.write_bytes(payload)
                status = "raw_file_refreshed" if should_refresh else "raw_file_downloaded"
            except Exception as exc:  # pragma: no cover - network failure shape is environment-specific
                error = f"{type(exc).__name__}: {exc}"
                if strict_network:
                    raise RuntimeError(f"Execution evidence source fetch failed: {source_id}: {error}") from exc
                if should_refresh and path.exists():
                    status = "raw_file_refresh_failed_using_cache"
        if not path.exists():
            if strict_network:
                raise RuntimeError(f"Execution evidence source missing: {source_id}: {path}")
            source_files.append(
                {
                    "source_id": source_id,
                    "source_name": source.get("name") or source_id,
                    "source_url": source.get("source_url") or "",
                    "raw_path": str(path),
                    "status": status,
                    "rows_total": 0,
                    "error": error,
                }
            )
            continue
        try:
            _header, rows = load_execution_source_dict_rows(source_id, path)
            if is_junta_contratos_menores_source(source_id):
                cache_contract_execution_match_texts(rows)
            source_rows[source_id] = rows
            source_file_by_id[source_id] = path
            source_files.append(
                {
                    "source_id": source_id,
                    "source_name": source.get("name") or source_id,
                    "source_url": source.get("source_url") or "",
                    "raw_path": str(path),
                    "status": status,
                    "content_type": content_type,
                    "rows_total": len(rows),
                    "error": "",
                }
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if strict_network:
                raise RuntimeError(f"Execution evidence source parse failed: {source_id}: {error}") from exc
            source_files.append(
                {
                    "source_id": source_id,
                    "source_name": source.get("name") or source_id,
                    "source_url": source.get("source_url") or "",
                    "raw_path": str(path),
                    "status": "raw_file_parse_failed",
                    "rows_total": 0,
                    "error": error,
                }
            )

    groups_by_key: dict[str, dict[str, Any]] = {}
    for topic_id, plans in ISSUE_EXECUTION_EVIDENCE_PLANS.items():
        for plan in plans:
            gap_id = str(plan.get("gap_id") or "")
            group_key = f"{topic_id}:{gap_id}"
            candidates: list[dict[str, Any]] = []
            plan_source_ids = [str(source_id) for source_id in plan.get("source_candidate_ids") or [] if source_id]
            search_terms = [str(term) for term in plan.get("search_terms") or [] if term]
            for source_id in plan_source_ids:
                source_file = source_file_by_id.get(source_id, raw_dir / EXECUTION_EVIDENCE_RAW_FILES.get(source_id, ""))
                for row in source_rows.get(source_id) or []:
                    match_score, matched_terms = execution_candidate_match_score(
                        source_id=source_id,
                        row=row,
                        search_terms=search_terms,
                    )
                    if match_score < 3:
                        continue
                    candidates.append(
                        compact_execution_candidate_row(
                            source_id=source_id,
                            topic_id=topic_id,
                            gap_id=gap_id,
                            row=row,
                            source_file=source_file,
                            match_score=match_score,
                            matched_terms=matched_terms,
                        )
                    )
            top_candidate_rows = select_top_execution_candidate_rows(
                candidates,
                EXECUTION_EVIDENCE_CANDIDATE_LIMIT,
            )
            groups_by_key[group_key] = {
                "topic_id": topic_id,
                "gap_id": gap_id,
                "source_ids": plan_source_ids,
                "candidate_rows_total": len(candidates),
                "candidate_rows_by_source": dict(Counter(str(row.get("source_id") or "") for row in candidates)),
                "top_candidate_rows": top_candidate_rows,
            }

    candidate_rows_total = sum(int(group.get("candidate_rows_total") or 0) for group in groups_by_key.values())
    outcome_series_monitor = build_post_change_outcome_monitor(source_rows)
    return {
        "schema_version": "andalucia_2026_execution_candidate_rows_v1",
        "status": "official_candidate_rows_ready" if candidate_rows_total else "no_official_candidate_rows",
        "raw_dir": str(raw_dir),
        "source_files_total": len(source_files),
        "source_files_cached_total": sum(
            1
            for row in source_files
            if str(row.get("status") or "")
            in {"raw_file_cached", "raw_file_downloaded", "raw_file_refreshed", "raw_file_refresh_failed_using_cache"}
        ),
        "source_files_downloaded_total": sum(1 for row in source_files if row.get("status") == "raw_file_downloaded"),
        "source_files_refreshed_total": sum(1 for row in source_files if row.get("status") == "raw_file_refreshed"),
        "source_file_errors_total": sum(1 for row in source_files if row.get("error")),
        "outcome_series_monitor": outcome_series_monitor,
        "candidate_rows_total": candidate_rows_total,
        "budget_candidate_rows_total": sum(
            int(group.get("candidate_rows_total") or 0)
            for group in groups_by_key.values()
            if group.get("gap_id") == "missing_budget_execution"
        ),
        "contract_candidate_rows_total": sum(
            sum(
                int(total or 0)
                for source_id, total in (group.get("candidate_rows_by_source") or {}).items()
                if is_junta_contratos_menores_source(str(source_id))
            )
            for group in groups_by_key.values()
        ),
        "treasury_payment_candidate_rows_total": sum(
            sum(
                int(total or 0)
                for source_id, total in (group.get("candidate_rows_by_source") or {}).items()
                if is_junta_treasury_payment_source(str(source_id))
            )
            for group in groups_by_key.values()
        ),
        "outcome_candidate_rows_total": sum(
            int(group.get("candidate_rows_total") or 0)
            for group in groups_by_key.values()
            if group.get("gap_id") == "missing_outcomes"
        ),
        "source_files": source_files,
        "groups_by_key": groups_by_key,
    }


def empty_execution_evidence_candidate_report(raw_dir: Path = DEFAULT_EXECUTION_EVIDENCE_RAW_DIR) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_execution_candidate_rows_v1",
        "status": "not_collected",
        "raw_dir": str(raw_dir),
        "source_files_total": 0,
        "source_files_cached_total": 0,
        "source_files_downloaded_total": 0,
        "source_files_refreshed_total": 0,
        "source_file_errors_total": 0,
        "outcome_series_monitor": empty_post_change_outcome_monitor(),
        "candidate_rows_total": 0,
        "budget_candidate_rows_total": 0,
        "contract_candidate_rows_total": 0,
        "treasury_payment_candidate_rows_total": 0,
        "outcome_candidate_rows_total": 0,
        "source_files": [],
        "groups_by_key": {},
    }


def empty_execution_evidence_reviews_report(path: Path | None = None) -> dict[str, Any]:
    return {
        "schema_version": "andalucia_2026_execution_evidence_reviews_v1",
        "status": "missing",
        "source_path": str(path or ""),
        "reviews_total": 0,
        "applied_reviews_total": 0,
        "reviews": [],
        "reviews_by_candidate_row_id": {},
        "reviews_by_locator": {},
        "reviews_by_topic_gap": {},
    }


def execution_evidence_review_locator_key(
    *,
    topic_id: Any,
    gap_id: Any,
    source_id: Any,
    source_locator: Any,
) -> str:
    return "|".join(
        [
            str(topic_id or ""),
            str(gap_id or ""),
            str(source_id or ""),
            str(source_locator or ""),
        ]
    )


def load_execution_evidence_reviews(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_execution_evidence_reviews_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviews = [row for row in payload.get("reviews", []) if isinstance(row, dict)]
    reviews_by_candidate_row_id: dict[str, dict[str, Any]] = {}
    reviews_by_locator: dict[str, dict[str, Any]] = {}
    reviews_by_topic_gap: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reviews:
        candidate_row_id = str(row.get("candidate_row_id") or "")
        if candidate_row_id:
            reviews_by_candidate_row_id[candidate_row_id] = row
        locator_key = execution_evidence_review_locator_key(
            topic_id=row.get("topic_id"),
            gap_id=row.get("gap_id"),
            source_id=row.get("source_id"),
            source_locator=row.get("source_locator"),
        )
        if row.get("source_locator"):
            reviews_by_locator[locator_key] = row
        topic_gap_key = f"{row.get('topic_id') or ''}:{row.get('gap_id') or ''}"
        reviews_by_topic_gap[topic_gap_key].append(row)
    return {
        "schema_version": payload.get("schema_version") or "andalucia_2026_execution_evidence_reviews_v1",
        "status": "ok",
        "source_path": str(path),
        "review_policy": payload.get("review_policy") or "",
        "reviewed_at": payload.get("reviewed_at") or "",
        "reviews_total": len(reviews),
        "applied_reviews_total": 0,
        "reviews": reviews,
        "reviews_by_candidate_row_id": reviews_by_candidate_row_id,
        "reviews_by_locator": reviews_by_locator,
        "reviews_by_topic_gap": dict(reviews_by_topic_gap),
    }


def execution_evidence_review_for_candidate(
    candidate: dict[str, Any],
    review_report: dict[str, Any],
) -> dict[str, Any] | None:
    candidate_row_id = str(candidate.get("candidate_row_id") or "")
    if candidate_row_id:
        review = (review_report.get("reviews_by_candidate_row_id") or {}).get(candidate_row_id)
        if isinstance(review, dict):
            return review
    locator_key = execution_evidence_review_locator_key(
        topic_id=candidate.get("topic_id"),
        gap_id=candidate.get("gap_id"),
        source_id=candidate.get("source_id"),
        source_locator=candidate.get("source_locator"),
    )
    review = (review_report.get("reviews_by_locator") or {}).get(locator_key)
    return review if isinstance(review, dict) else None


def compact_reviewed_execution_evidence_row(
    review: dict[str, Any],
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = candidate or {}
    source_id = str(review.get("source_id") or candidate.get("source_id") or "")
    source = compact_execution_source_candidate(source_id) if source_id else {}
    return {
        "review_item_id": review.get("review_item_id") or "",
        "candidate_row_id": review.get("candidate_row_id") or candidate.get("candidate_row_id") or "",
        "topic_id": review.get("topic_id") or candidate.get("topic_id") or "",
        "gap_id": review.get("gap_id") or candidate.get("gap_id") or "",
        "source_id": source_id,
        "source_kind": review.get("source_kind") or candidate.get("source_kind") or source.get("source_kind") or "",
        "source_name": review.get("source_name") or candidate.get("source_name") or source.get("name") or source_id,
        "source_url": review.get("source_url") or candidate.get("source_url") or source.get("source_url") or "",
        "source_locator": review.get("source_locator") or candidate.get("source_locator") or "",
        "summary": review.get("summary") or review.get("reviewed_label") or candidate.get("summary") or "",
        "reviewed_label": review.get("reviewed_label") or review.get("summary") or candidate.get("summary") or "",
        "review_status": review.get("review_status") or "",
        "claim_status": review.get("claim_status") or "",
        "interpretation_status": review.get("interpretation_status") or "",
        "evidence_kind": review.get("evidence_kind") or "",
        "program_code": review.get("program_code") or candidate.get("program_code") or "",
        "program_name": review.get("program_name") or candidate.get("program_name") or "",
        "org_section": review.get("org_section") or candidate.get("org_section") or "",
        "org_service": review.get("org_service") or candidate.get("org_service") or "",
        "policy_area": review.get("policy_area") or candidate.get("policy_area") or "",
        "budget_item": review.get("budget_item") or candidate.get("budget_item") or "",
        "budget_project": review.get("budget_project") or candidate.get("budget_project") or "",
        "contract_object": review.get("contract_object") or candidate.get("contract_object") or "",
        "contracting_body": review.get("contracting_body") or candidate.get("contracting_body") or "",
        "contract_reference": review.get("contract_reference") or candidate.get("contract_reference") or "",
        "contract_type": review.get("contract_type") or candidate.get("contract_type") or "",
        "award_date": review.get("award_date") or candidate.get("award_date") or "",
        "place": review.get("place") or candidate.get("place") or "",
        "cpv": review.get("cpv") or candidate.get("cpv") or "",
        "grant_beneficiary": review.get("grant_beneficiary") or candidate.get("grant_beneficiary") or "",
        "grant_announcement": review.get("grant_announcement") or candidate.get("grant_announcement") or "",
        "grant_finality": review.get("grant_finality") or candidate.get("grant_finality") or "",
        "grant_date": review.get("grant_date") or candidate.get("grant_date") or "",
        "grant_year": review.get("grant_year") or candidate.get("grant_year") or "",
        "grant_type": review.get("grant_type") or candidate.get("grant_type") or "",
        "grant_organism": review.get("grant_organism") or candidate.get("grant_organism") or "",
        "budget_application": review.get("budget_application") or candidate.get("budget_application") or "",
        "regulatory_base": review.get("regulatory_base") or candidate.get("regulatory_base") or "",
        "treasury_year": review.get("treasury_year") or candidate.get("treasury_year") or "",
        "treasury_month": review.get("treasury_month") or candidate.get("treasury_month") or "",
        "treasury_hierarchy_1": review.get("treasury_hierarchy_1") or candidate.get("treasury_hierarchy_1") or "",
        "treasury_hierarchy_2": review.get("treasury_hierarchy_2") or candidate.get("treasury_hierarchy_2") or "",
        "treasury_hierarchy_3": review.get("treasury_hierarchy_3") or candidate.get("treasury_hierarchy_3") or "",
        "amount_eur": review.get("amount_eur", candidate.get("amount_eur")),
        "indicator_name": review.get("indicator_name") or candidate.get("indicator_name") or "",
        "indicator_prevision": review.get("indicator_prevision") or candidate.get("indicator_prevision") or "",
        "indicator_unit": review.get("indicator_unit") or candidate.get("indicator_unit") or "",
        "outcome_territory": review.get("outcome_territory") or candidate.get("outcome_territory") or "",
        "outcome_year": review.get("outcome_year") or candidate.get("outcome_year") or "",
        "outcome_value": review.get("outcome_value") or candidate.get("outcome_value") or "",
        "outcome_value_format": review.get("outcome_value_format") or candidate.get("outcome_value_format") or "",
        "outcome_periodicity": review.get("outcome_periodicity") or candidate.get("outcome_periodicity") or "",
        "outcome_first_year": review.get("outcome_first_year") or candidate.get("outcome_first_year") or "",
        "outcome_first_value": review.get("outcome_first_value") or candidate.get("outcome_first_value") or "",
        "outcome_first_value_format": review.get("outcome_first_value_format")
        or candidate.get("outcome_first_value_format")
        or "",
        "outcome_baseline_year": review.get("outcome_baseline_year") or candidate.get("outcome_baseline_year") or "",
        "outcome_baseline_value": review.get("outcome_baseline_value") or candidate.get("outcome_baseline_value") or "",
        "outcome_baseline_value_format": review.get("outcome_baseline_value_format")
        or candidate.get("outcome_baseline_value_format")
        or "",
        "outcome_latest_year": review.get("outcome_latest_year")
        or candidate.get("outcome_latest_year")
        or review.get("outcome_year")
        or candidate.get("outcome_year")
        or "",
        "outcome_latest_value": review.get("outcome_latest_value")
        or candidate.get("outcome_latest_value")
        or review.get("outcome_value")
        or candidate.get("outcome_value")
        or "",
        "outcome_latest_value_format": review.get("outcome_latest_value_format")
        or candidate.get("outcome_latest_value_format")
        or review.get("outcome_value_format")
        or candidate.get("outcome_value_format")
        or "",
        "outcome_post_change_status": review.get("outcome_post_change_status")
        or candidate.get("outcome_post_change_status")
        or "",
        "outcome_post_change_rows_total": int(
            review.get("outcome_post_change_rows_total")
            or candidate.get("outcome_post_change_rows_total")
            or 0
        ),
        "outcome_next_post_change_check_year": review.get("outcome_next_post_change_check_year")
        or candidate.get("outcome_next_post_change_check_year")
        or "",
        "review_summary": review.get("review_summary") or "",
        "review_confidence": review.get("review_confidence") or "",
        "reviewed_by": review.get("reviewed_by") or "",
        "reviewed_at": review.get("reviewed_at") or "",
        "source_evidence": list(review.get("source_evidence") or []),
        "open_limitations": list(review.get("open_limitations") or []),
    }


def reviewed_execution_evidence_rows_for_queue_item(
    *,
    topic_id: str,
    gap_id: str,
    top_candidate_rows: list[dict[str, Any]],
    review_report: dict[str, Any],
) -> list[dict[str, Any]]:
    reviewed_rows: list[dict[str, Any]] = []
    used_review_keys: set[str] = set()
    candidate_by_id = {
        str(row.get("candidate_row_id") or ""): row
        for row in top_candidate_rows
        if row.get("candidate_row_id")
    }
    for candidate in top_candidate_rows:
        review = execution_evidence_review_for_candidate(candidate, review_report)
        if not review:
            continue
        review_key = str(review.get("review_item_id") or review.get("candidate_row_id") or "")
        used_review_keys.add(review_key)
        reviewed_rows.append(compact_reviewed_execution_evidence_row(review, candidate))
    for review in (review_report.get("reviews_by_topic_gap") or {}).get(f"{topic_id}:{gap_id}", []):
        if not isinstance(review, dict):
            continue
        review_key = str(review.get("review_item_id") or review.get("candidate_row_id") or "")
        if review_key and review_key in used_review_keys:
            continue
        candidate = candidate_by_id.get(str(review.get("candidate_row_id") or ""))
        reviewed_rows.append(compact_reviewed_execution_evidence_row(review, candidate))
        if review_key:
            used_review_keys.add(review_key)
    return reviewed_rows


def execution_evidence_queue_item_status(
    *,
    gap_id: str,
    official_candidate_rows_total: int,
    reviewed_rows_total: int,
    reviewed_rows: list[dict[str, Any]] | None = None,
) -> str:
    if reviewed_rows_total:
        reviewed_kinds = {str(row.get("evidence_kind") or "") for row in (reviewed_rows or [])}
        if gap_id == "missing_budget_execution":
            if (
                "treasury_payment_aggregate" in reviewed_kinds
                and "grant_award" in reviewed_kinds
                and "contract_award" in reviewed_kinds
                and "budget_plan" in reviewed_kinds
            ):
                return "reviewed_budget_contract_grant_treasury_rows_delivery_and_outcome_pending"
            if "treasury_payment_aggregate" in reviewed_kinds and "grant_award" in reviewed_kinds and "budget_plan" in reviewed_kinds:
                return "reviewed_budget_grant_treasury_rows_delivery_and_outcome_pending"
            if "grant_award" in reviewed_kinds and "contract_award" in reviewed_kinds and "budget_plan" in reviewed_kinds:
                return "reviewed_budget_contract_grant_rows_execution_and_outcome_pending"
            if "grant_award" in reviewed_kinds and "budget_plan" in reviewed_kinds:
                return "reviewed_budget_grant_rows_execution_and_outcome_pending"
            if "treasury_payment_aggregate" in reviewed_kinds and "budget_plan" in reviewed_kinds:
                return "reviewed_budget_treasury_rows_delivery_and_outcome_pending"
            if "treasury_payment_aggregate" in reviewed_kinds:
                return "reviewed_treasury_payment_aggregate_rows_delivery_and_outcome_pending"
            if "grant_award" in reviewed_kinds:
                return "reviewed_grant_rows_delivery_and_outcome_pending"
            if "contract_award" in reviewed_kinds and "budget_plan" in reviewed_kinds:
                return "reviewed_budget_contract_rows_execution_and_outcome_pending"
            if "contract_award" in reviewed_kinds:
                return "reviewed_contract_rows_outcome_pending"
            return "reviewed_budget_plan_rows_execution_pending"
        if gap_id == "missing_outcomes":
            if "observed_outcome_series" in reviewed_kinds:
                return "reviewed_observed_outcome_baseline_rows_post_change_pending"
            return "reviewed_indicator_target_rows_outcome_pending"
        return "reviewed_execution_evidence_rows_no_execution_or_outcome_claim"
    if official_candidate_rows_total:
        return "official_candidate_rows_need_review"
    return "official_source_candidates_ready"


def build_issue_execution_evidence_queue(
    issue_accountability_packets: dict[str, Any],
    candidate_report: dict[str, Any] | None = None,
    execution_evidence_review_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_report = candidate_report or empty_execution_evidence_candidate_report()
    execution_evidence_review_report = (
        execution_evidence_review_report or empty_execution_evidence_reviews_report()
    )
    queue_items: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for packet in issue_accountability_packets.get("packets") or []:
        if not isinstance(packet, dict):
            continue
        topic_id = str(packet.get("topic_id") or "")
        open_gaps = {str(gap) for gap in packet.get("open_gaps") or [] if gap}
        for plan in ISSUE_EXECUTION_EVIDENCE_PLANS.get(topic_id, []):
            gap_id = str(plan.get("gap_id") or "")
            if gap_id not in open_gaps:
                continue
            plan_source_ids = [str(source_id) for source_id in plan.get("source_candidate_ids") or [] if source_id]
            source_ids.update(plan_source_ids)
            candidate_group = (candidate_report.get("groups_by_key") or {}).get(f"{topic_id}:{gap_id}") or {}
            top_candidate_rows = list(candidate_group.get("top_candidate_rows") or [])
            official_candidate_rows_total = int(candidate_group.get("candidate_rows_total") or len(top_candidate_rows))
            candidate_rows_by_source = {
                str(source_id): int(total or 0)
                for source_id, total in (candidate_group.get("candidate_rows_by_source") or {}).items()
            }
            reviewed_evidence_rows = reviewed_execution_evidence_rows_for_queue_item(
                topic_id=topic_id,
                gap_id=gap_id,
                top_candidate_rows=top_candidate_rows,
                review_report=execution_evidence_review_report,
            )
            queue_items.append(
                {
                    "queue_item_id": stable_slug(f"execution-evidence:{topic_id}:{gap_id}"),
                    "topic_id": topic_id,
                    "topic_label": packet.get("topic_label") or program_topic_label(topic_id),
                    "gap_id": gap_id,
                    "evidence_need": plan.get("evidence_need") or "",
                    "status": execution_evidence_queue_item_status(
                        gap_id=gap_id,
                        official_candidate_rows_total=official_candidate_rows_total,
                        reviewed_rows_total=len(reviewed_evidence_rows),
                        reviewed_rows=reviewed_evidence_rows,
                    ),
                    "review_question": plan.get("review_question") or "",
                    "source_candidate_ids": plan_source_ids,
                    "source_candidates": [
                        {
                            **compact_execution_source_candidate(source_id),
                            "official_candidate_rows_total": int(candidate_rows_by_source.get(source_id) or 0),
                        }
                        for source_id in plan_source_ids
                    ],
                    "official_candidate_rows_total": official_candidate_rows_total,
                    "official_candidate_rows_by_source": candidate_rows_by_source,
                    "official_candidate_rows": top_candidate_rows,
                    "reviewed_evidence_rows_total": len(reviewed_evidence_rows),
                    "reviewed_evidence_rows": reviewed_evidence_rows,
                    "search_terms": [str(term) for term in plan.get("search_terms") or [] if term],
                    "expected_resolution": plan.get("expected_resolution") or "",
                    "current_packet_status": packet.get("status") or "",
                    "issue_review_status": packet.get("issue_review_status") or "",
                    "open_gaps": sorted(open_gaps),
                }
            )
    queue_items.sort(
        key=lambda row: (
            0 if row.get("topic_id") == "campo_agua" else 1,
            str(row.get("gap_id") or ""),
            str(row.get("queue_item_id") or ""),
        )
    )
    for index, item in enumerate(queue_items, start=1):
        item["priority_rank"] = index
    source_candidates = [compact_execution_source_candidate(source_id) for source_id in sorted(source_ids)]
    reviewed_evidence_rows_total = sum(int(row.get("reviewed_evidence_rows_total") or 0) for row in queue_items)
    reviewed_budget_plan_rows_total = sum(
        1
        for item in queue_items
        for row in item.get("reviewed_evidence_rows") or []
        if str(row.get("evidence_kind") or "") == "budget_plan"
    )
    reviewed_contract_rows_total = sum(
        1
        for item in queue_items
        for row in item.get("reviewed_evidence_rows") or []
        if str(row.get("evidence_kind") or "") == "contract_award"
    )
    reviewed_grant_rows_total = sum(
        1
        for item in queue_items
        for row in item.get("reviewed_evidence_rows") or []
        if str(row.get("evidence_kind") or "") == "grant_award"
    )
    reviewed_treasury_payment_rows_total = sum(
        1
        for item in queue_items
        for row in item.get("reviewed_evidence_rows") or []
        if str(row.get("evidence_kind") or "") == "treasury_payment_aggregate"
    )
    reviewed_indicator_target_rows_total = sum(
        1
        for item in queue_items
        for row in item.get("reviewed_evidence_rows") or []
        if str(row.get("evidence_kind") or "") == "indicator_target"
    )
    reviewed_observed_outcome_rows_total = sum(
        1
        for item in queue_items
        for row in item.get("reviewed_evidence_rows") or []
        if str(row.get("evidence_kind") or "") == "observed_outcome_series"
    )
    if (
        reviewed_budget_plan_rows_total
        and reviewed_contract_rows_total
        and reviewed_grant_rows_total
        and reviewed_treasury_payment_rows_total
        and reviewed_indicator_target_rows_total
        and reviewed_observed_outcome_rows_total
    ):
        status = "reviewed_budget_contract_grant_treasury_indicator_baseline_rows_no_post_change_outcome_claim"
    elif reviewed_budget_plan_rows_total and reviewed_grant_rows_total and reviewed_treasury_payment_rows_total and reviewed_indicator_target_rows_total:
        status = "reviewed_budget_grant_treasury_indicator_rows_no_final_outcome_claim"
    elif reviewed_budget_plan_rows_total and reviewed_grant_rows_total and reviewed_indicator_target_rows_total:
        status = "reviewed_budget_grant_indicator_rows_no_final_outcome_claim"
    elif reviewed_budget_plan_rows_total and reviewed_contract_rows_total and reviewed_indicator_target_rows_total:
        status = "reviewed_budget_contract_indicator_rows_no_execution_or_outcome_claim"
    elif reviewed_budget_plan_rows_total and reviewed_indicator_target_rows_total:
        status = "reviewed_budget_indicator_rows_no_execution_or_outcome_claim"
    elif reviewed_contract_rows_total and reviewed_indicator_target_rows_total:
        status = "reviewed_contract_indicator_rows_no_outcome_claim"
    elif reviewed_budget_plan_rows_total:
        status = "reviewed_budget_plan_rows_execution_pending"
    elif reviewed_contract_rows_total:
        status = "reviewed_contract_rows_outcome_pending"
    elif reviewed_grant_rows_total:
        status = "reviewed_grant_rows_delivery_and_outcome_pending"
    elif reviewed_treasury_payment_rows_total:
        status = "reviewed_treasury_payment_aggregate_rows_delivery_and_outcome_pending"
    elif reviewed_observed_outcome_rows_total:
        status = "reviewed_observed_outcome_baseline_rows_post_change_pending"
    elif reviewed_indicator_target_rows_total:
        status = "reviewed_indicator_target_rows_outcome_pending"
    elif any(int(row.get("official_candidate_rows_total") or 0) > 0 for row in queue_items):
        status = "official_candidate_rows_need_review"
    elif queue_items:
        status = "official_source_candidates_ready"
    else:
        status = "no_execution_evidence_queue"
    if execution_evidence_review_report is not None:
        execution_evidence_review_report["applied_reviews_total"] = reviewed_evidence_rows_total
    return {
        "schema_version": "andalucia_2026_execution_evidence_queue_v1",
        "status": status,
        "claim_status": "execution_budget_outcome_queue_only_no_merit_or_blame_claim",
        "queue_total": len(queue_items),
        "topics_total": len({str(row.get("topic_id") or "") for row in queue_items}),
        "source_candidates_total": len(source_candidates),
        "verified_source_candidates_total": sum(
            1 for row in source_candidates if is_verified_execution_source_status(row.get("status"))
        ),
        "official_candidate_rows_total": sum(
            int(row.get("official_candidate_rows_total") or 0) for row in queue_items
        ),
        "reviewed_evidence_rows_total": reviewed_evidence_rows_total,
        "reviewed_budget_plan_rows_total": reviewed_budget_plan_rows_total,
        "reviewed_contract_rows_total": reviewed_contract_rows_total,
        "reviewed_grant_rows_total": reviewed_grant_rows_total,
        "reviewed_treasury_payment_rows_total": reviewed_treasury_payment_rows_total,
        "reviewed_indicator_target_rows_total": reviewed_indicator_target_rows_total,
        "reviewed_observed_outcome_rows_total": reviewed_observed_outcome_rows_total,
        "budget_candidate_rows_total": int(candidate_report.get("budget_candidate_rows_total") or 0),
        "contract_candidate_rows_total": int(candidate_report.get("contract_candidate_rows_total") or 0),
        "treasury_payment_candidate_rows_total": int(candidate_report.get("treasury_payment_candidate_rows_total") or 0),
        "outcome_candidate_rows_total": int(candidate_report.get("outcome_candidate_rows_total") or 0),
        "source_files_total": int(candidate_report.get("source_files_total") or 0),
        "source_files_cached_total": int(candidate_report.get("source_files_cached_total") or 0),
        "source_file_errors_total": int(candidate_report.get("source_file_errors_total") or 0),
        "source_candidates": source_candidates,
        "source_files": list(candidate_report.get("source_files") or []),
        "queue": queue_items,
        "open_limitations": [
            "reviewed_rows_are_budget_plans_indicator_targets_or_contract_awards",
            "official_candidate_rows_need_human_review",
            "budget_plan_not_execution",
            "contract_award_not_service_outcome",
            "grant_award_not_final_delivery_or_outcome",
            "treasury_payment_aggregate_not_beneficiary_delivery_or_outcome",
            "indicator_target_not_observed_outcome",
            "observed_outcome_baseline_not_post_change_impact",
            "budget_execution_not_linked",
            "outcome_not_linked",
            "merit_blame_not_scored",
        ],
    }


READINESS_BLOCKER_LABELS = {
    "program_measure_missing": "Falta programa o medida declarada verificable.",
    "reviewed_vote_missing": "Falta voto parlamentario revisado.",
    "reviewed_boja_missing": "Falta cambio BOJA revisado.",
    "citizen_direction_missing": "Falta direccion ciudadana revisada.",
    "responsible_actor_missing": "Falta actor responsable revisado.",
    "execution_source_plan_missing": "Falta plan de fuentes de ejecucion para este issue.",
    "budget_or_execution_review_missing": "Falta revisar dinero, contrato, ayuda o ejecucion.",
    "delivery_or_beneficiary_missing": "Hay dinero/contrato/ayuda parcial, pero falta entrega final o beneficiario completo.",
    "observed_outcome_missing": "Falta outcome oficial observado.",
    "post_change_outcome_missing": "Hay baseline/indicador, pero falta outcome posterior al cambio.",
    "causal_link_missing": "Falta vincular decision, ejecucion y outcome con causalidad revisada.",
    "merit_blame_review_missing": "Falta revision explicita de merito/culpa.",
}

READINESS_NEXT_ACTIONS = {
    "program_measure_missing": {
        "action_id": "collect_verified_program_measure",
        "label": "Scrapear programa verificable",
        "description": "Localizar PDF/texto oficial de programa y extraer medidas por issue.",
    },
    "reviewed_vote_missing": {
        "action_id": "review_parliament_vote_signal",
        "label": "Revisar voto parlamentario",
        "description": "Promover un item de la cola de votos a senal revisada con efecto legal y actores.",
    },
    "reviewed_boja_missing": {
        "action_id": "review_boja_legal_change",
        "label": "Revisar BOJA",
        "description": "Promover fragmento BOJA a cambio legal revisado con direccion y alcance.",
    },
    "citizen_direction_missing": {
        "action_id": "add_issue_direction_review",
        "label": "Anadir direccion del issue",
        "description": "Completar seed de revision por issue con direccion ciudadana y limitaciones.",
    },
    "responsible_actor_missing": {
        "action_id": "add_responsible_actor_review",
        "label": "Anadir actor responsable",
        "description": "Enlazar grupos, cargos, organos y fuente primaria del actor responsable.",
    },
    "execution_source_plan_missing": {
        "action_id": "add_execution_source_plan",
        "label": "Crear plan de fuentes de ejecucion",
        "description": "Declarar fuentes oficiales y terminos de busqueda para dinero, entrega y outcomes.",
    },
    "budget_or_execution_review_missing": {
        "action_id": "review_execution_evidence_rows",
        "label": "Revisar filas de ejecucion",
        "description": "Promover filas oficiales candidatas de presupuesto, contrato, subvencion o tesoreria.",
    },
    "delivery_or_beneficiary_missing": {
        "action_id": "find_delivery_or_beneficiary_evidence",
        "label": "Buscar entrega/beneficiario",
        "description": "Localizar resoluciones finales, actas, pagos desagregados o entregables verificables.",
    },
    "observed_outcome_missing": {
        "action_id": "collect_observed_outcome_series",
        "label": "Ingerir outcome observado",
        "description": "Anadir serie oficial observada, no solo objetivo o prevision presupuestaria.",
    },
    "post_change_outcome_missing": {
        "action_id": "collect_post_change_outcome_series",
        "label": "Esperar/ingerir outcome posterior",
        "description": "Capturar dato oficial posterior al cambio legal/ejecucion para comparar contra baseline.",
    },
    "causal_link_missing": {
        "action_id": "review_causal_link",
        "label": "Revisar causalidad",
        "description": "Conectar decision, ejecucion y outcome sin convertir correlacion en merito o culpa.",
    },
    "merit_blame_review_missing": {
        "action_id": "review_merit_blame",
        "label": "Revisar merito/culpa",
        "description": "Solo despues de outcome post-cambio y causalidad; publicar si la evidencia lo soporta.",
    },
}

READINESS_BLOCKER_PRIORITY = (
    "program_measure_missing",
    "reviewed_vote_missing",
    "reviewed_boja_missing",
    "citizen_direction_missing",
    "responsible_actor_missing",
    "execution_source_plan_missing",
    "budget_or_execution_review_missing",
    "delivery_or_beneficiary_missing",
    "observed_outcome_missing",
    "post_change_outcome_missing",
    "causal_link_missing",
    "merit_blame_review_missing",
)


def reviewed_execution_kind_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(row.get("evidence_kind") or "sin_tipo") for row in rows if isinstance(row, dict))


def reviewed_execution_rows_for_topic(queue_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in queue_items:
        rows.extend(row for row in item.get("reviewed_evidence_rows") or [] if isinstance(row, dict))
    return rows


def post_change_outcome_rows_total(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        if str(row.get("evidence_kind") or "") != "observed_outcome_series":
            continue
        if int(row.get("outcome_post_change_rows_total") or 0) > 0:
            total += 1
            continue
        if str(row.get("outcome_post_change_status") or "") == "post_change_observed_needs_review":
            total += 1
            continue
        status_text = normalize_label(
            " ".join(
                str(row.get(field) or "")
                for field in (
                    "review_status",
                    "claim_status",
                    "interpretation_status",
                    "outcome_status",
                )
            )
        )
        if "post change observed" in status_text or "post_change_observed" in status_text:
            total += 1
    return total


DELIVERY_EVIDENCE_HUNT_LIMIT_PER_TOPIC = 4
DELIVERY_EVIDENCE_TARGET_LIMIT_PER_HUNT = 4
DELIVERY_EVIDENCE_KIND_PRIORITY = {
    "grant_award": 0,
    "contract_award": 1,
    "treasury_payment_aggregate": 2,
    "budget_plan": 3,
}


def official_delivery_search_url(registry: str, query: str) -> str:
    encoded = urllib.parse.urlencode({"q": query})
    if registry == "junta_open_data":
        return f"https://www.juntadeandalucia.es/datosabiertos/portal/dataset/?{encoded}"
    if registry == "boja":
        return "https://www.juntadeandalucia.es/eboja/buscador/index.html?" + urllib.parse.urlencode(
            {"texto": query}
        )
    if registry == "bdns":
        return "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias"
    if registry == "junta_procurement_registry":
        return "https://www.juntadeandalucia.es/temas/contratacion-publica/perfiles-licitaciones.html"
    return ""


def delivery_query_text(*parts: Any, max_chars: int = 190) -> str:
    text = re.sub(r"\s+", " ", " ".join(str(part or "") for part in parts if str(part or "").strip())).strip()
    return text[:max_chars].strip()


def delivery_hunt_targets_for_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    evidence_kind = str(row.get("evidence_kind") or "")
    label = str(row.get("reviewed_label") or row.get("summary") or "")
    targets: list[tuple[str, str, str, str]] = []
    if evidence_kind == "contract_award":
        contract_reference = str(row.get("contract_reference") or "")
        contracting_body = str(row.get("contracting_body") or "")
        if contract_reference:
            targets.append(
                (
                    "junta_procurement_registry",
                    contract_reference,
                    "Abrir registro de contratacion para localizar expediente, adjudicatario, formalizacion o recepcion.",
                    "contract_exact_reference",
                )
            )
            targets.append(
                (
                    "boja",
                    delivery_query_text(contract_reference, "acta recepcion certificacion final"),
                    "Buscar recepcion, certificacion final o resolucion publicada.",
                    "contract_final_delivery",
                )
            )
        targets.append(
            (
                "junta_open_data",
                delivery_query_text(label, contracting_body, "adjudicatario recepcion"),
                "Buscar dataset o detalle adicional con adjudicatario, entrega o pago.",
                "contract_delivery_dataset",
            )
        )
    elif evidence_kind == "grant_award":
        beneficiary = str(row.get("grant_beneficiary") or "")
        announcement = str(row.get("grant_announcement") or "")
        finality = str(row.get("grant_finality") or label)
        targets.extend(
            [
                (
                    "bdns",
                    delivery_query_text(beneficiary, announcement, finality),
                    "Buscar convocatoria/concesion para documentar beneficiario, importe, justificacion y estado.",
                    "grant_bdns_detail",
                ),
                (
                    "boja",
                    delivery_query_text(beneficiary, announcement, "justificacion subvencion"),
                    "Buscar resolucion final, justificacion o reintegro publicado.",
                    "grant_final_resolution",
                ),
                (
                    "junta_open_data",
                    delivery_query_text(beneficiary, finality, "subvencion beneficiario"),
                    "Buscar dataset complementario con beneficiario o finalidad mas granular.",
                    "grant_open_data_detail",
                ),
            ]
        )
    elif evidence_kind == "treasury_payment_aggregate":
        hierarchy = " ".join(
            str(row.get(field) or "")
            for field in ("treasury_hierarchy_1", "treasury_hierarchy_2", "treasury_hierarchy_3")
        )
        targets.append(
            (
                "junta_open_data",
                delivery_query_text(hierarchy, "beneficiarios pagos tesoreria"),
                "Buscar pagos desagregados o dataset con tercero/beneficiario.",
                "treasury_beneficiary_breakdown",
            )
        )
    elif evidence_kind == "budget_plan":
        program_code = str(row.get("program_code") or "")
        targets.extend(
            [
                (
                    "junta_open_data",
                    delivery_query_text(program_code, label, "ejecucion pagos contratos subvenciones"),
                    "Buscar ejecucion presupuestaria o fuente secundaria oficial vinculable a la partida.",
                    "budget_execution_dataset",
                ),
                (
                    "boja",
                    delivery_query_text(program_code, label, "beneficiarios resolucion"),
                    "Buscar resolucion BOJA que convierta la partida en acto ejecutado.",
                    "budget_resolution",
                ),
            ]
        )

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for registry, query, purpose, target_kind in targets:
        query = delivery_query_text(query)
        if not query:
            continue
        signature = (registry, normalize_label(query))
        if signature in seen:
            continue
        seen.add(signature)
        out.append(
            {
                "target_id": stable_slug(f"{registry}:{target_kind}:{query}"),
                "registry": registry,
                "target_kind": target_kind,
                "query": query,
                "url": official_delivery_search_url(registry, query),
                "purpose": purpose,
            }
        )
        if len(out) >= DELIVERY_EVIDENCE_TARGET_LIMIT_PER_HUNT:
            break
    return out


def build_delivery_evidence_hunts_for_issue(
    *,
    topic_id: str,
    topic_label: str,
    execution_rows: list[dict[str, Any]],
    limit: int = DELIVERY_EVIDENCE_HUNT_LIMIT_PER_TOPIC,
) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in execution_rows
        if str(row.get("evidence_kind") or "")
        in {"budget_plan", "contract_award", "grant_award", "treasury_payment_aggregate"}
    ]
    candidates.sort(
        key=lambda row: (
            DELIVERY_EVIDENCE_KIND_PRIORITY.get(str(row.get("evidence_kind") or ""), 99),
            -int(parse_execution_amount(row.get("amount_eur")) or 0),
            str(row.get("source_id") or ""),
            str(row.get("source_locator") or ""),
        )
    )
    hunts: list[dict[str, Any]] = []
    seen_rows: set[str] = set()
    for row in candidates:
        source_locator = str(row.get("source_locator") or "")
        evidence_kind = str(row.get("evidence_kind") or "")
        row_signature = "|".join(
            [
                evidence_kind,
                str(row.get("source_id") or ""),
                source_locator,
                str(row.get("reviewed_label") or row.get("summary") or ""),
            ]
        )
        if row_signature in seen_rows:
            continue
        seen_rows.add(row_signature)
        search_targets = delivery_hunt_targets_for_row(row)
        if not search_targets:
            continue
        hunts.append(
            {
                "hunt_id": stable_slug(f"delivery-evidence:{topic_id}:{row_signature}"),
                "topic_id": topic_id,
                "topic_label": topic_label or program_topic_label(topic_id),
                "source_id": str(row.get("source_id") or ""),
                "source_kind": str(row.get("source_kind") or ""),
                "source_url": str(row.get("source_url") or ""),
                "source_locator": source_locator,
                "evidence_kind": evidence_kind,
                "reviewed_label": str(row.get("reviewed_label") or row.get("summary") or ""),
                "amount_eur": parse_execution_amount(row.get("amount_eur")),
                "contract_reference": str(row.get("contract_reference") or ""),
                "grant_beneficiary": str(row.get("grant_beneficiary") or ""),
                "program_code": str(row.get("program_code") or ""),
                "search_targets": search_targets,
                "search_targets_total": len(search_targets),
                "open_limitations": [str(value) for value in row.get("open_limitations") or [] if value][:6],
            }
        )
        if len(hunts) >= limit:
            break
    return hunts


def readiness_next_action(blocker_id: str, source_candidate_ids: list[str] | None = None) -> dict[str, Any]:
    base = dict(READINESS_NEXT_ACTIONS.get(blocker_id) or {})
    if not base:
        base = {
            "action_id": "review_evidence_gap",
            "label": "Revisar hueco",
            "description": READINESS_BLOCKER_LABELS.get(blocker_id, "Revisar evidencia faltante."),
        }
    base["blocker_id"] = blocker_id
    base["source_candidate_ids"] = list(source_candidate_ids or [])
    base["automation_command"] = "just etl-andalucia-2026-accountability-assist"
    return base


def issue_readiness_classification(
    *,
    packet: dict[str, Any],
    queue_items: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
    kind_counts: Counter[str],
    blockers: list[str],
) -> str:
    program_total = int(packet.get("program_measures_total") or 0)
    vote_total = int(packet.get("reviewed_vote_items_total") or 0)
    boja_total = int(packet.get("reviewed_boja_legal_changes_total") or 0)
    observed_claims_total = int(packet.get("observed_responsibility_claims_total") or 0)
    has_direction = "citizen_direction_missing" not in blockers
    has_actor = "responsible_actor_missing" not in blockers
    has_execution = bool(
        kind_counts.get("budget_plan")
        or kind_counts.get("contract_award")
        or kind_counts.get("grant_award")
        or kind_counts.get("treasury_payment_aggregate")
    )
    has_outcome_baseline = bool(kind_counts.get("observed_outcome_series"))
    has_indicator_target = bool(kind_counts.get("indicator_target"))
    has_post_change_outcome = post_change_outcome_rows_total(execution_rows) > 0
    has_queue = bool(queue_items)

    if (
        observed_claims_total
        and has_direction
        and has_actor
        and has_execution
        and has_outcome_baseline
        and has_post_change_outcome
        and "causal_link_missing" not in blockers
    ):
        return "publishable_merit_blame_ready"
    if (
        observed_claims_total
        and has_direction
        and has_actor
        and has_execution
        and has_outcome_baseline
        and has_post_change_outcome
    ):
        return "responsibility_execution_post_change_outcome_reviewed_causality_pending"
    if observed_claims_total and has_direction and has_actor and has_execution and has_outcome_baseline:
        return "responsibility_execution_and_baseline_reviewed_no_post_change_causality"
    if observed_claims_total and has_direction and has_actor and has_execution and has_indicator_target:
        return "responsibility_execution_and_indicator_targets_reviewed_outcome_pending"
    if observed_claims_total and has_direction and has_actor and has_execution:
        return "responsibility_and_execution_reviewed_outcome_pending"
    if observed_claims_total and has_direction and has_actor:
        return "responsibility_observed_execution_outcome_pending"
    if (vote_total or boja_total) and has_direction and has_actor:
        return "legal_direction_and_actor_reviewed_execution_pending"
    if program_total and (vote_total or boja_total):
        return "program_with_primary_legal_signal_needs_review"
    if program_total and has_queue:
        return "program_with_execution_source_queue"
    if program_total:
        return "program_only_needs_primary_evidence"
    return "insufficient_evidence"


def build_issue_readiness_report(
    issue_accountability_packets: dict[str, Any],
    execution_evidence_queue: dict[str, Any],
) -> dict[str, Any]:
    queue_by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in execution_evidence_queue.get("queue") or []:
        if not isinstance(item, dict):
            continue
        queue_by_topic[str(item.get("topic_id") or "")].append(item)

    issues: list[dict[str, Any]] = []
    primary_blockers: Counter[str] = Counter()
    classification_counts: Counter[str] = Counter()
    next_action_counts: Counter[str] = Counter()

    for packet in issue_accountability_packets.get("packets") or []:
        if not isinstance(packet, dict):
            continue
        topic_id = str(packet.get("topic_id") or "")
        queue_items = queue_by_topic.get(topic_id, [])
        execution_rows = reviewed_execution_rows_for_topic(queue_items)
        kind_counts = reviewed_execution_kind_counts(execution_rows)
        queue_source_ids = list(dict.fromkeys(
            str(source_id)
            for item in queue_items
            for source_id in item.get("source_candidate_ids") or []
            if source_id
        ))
        open_gaps = {str(gap) for gap in packet.get("open_gaps") or [] if gap}
        blockers: list[str] = []

        if "missing_program_measure" in open_gaps or int(packet.get("program_measures_total") or 0) <= 0:
            blockers.append("program_measure_missing")
        if "missing_reviewed_vote_signal" in open_gaps:
            blockers.append("reviewed_vote_missing")
        if "missing_reviewed_boja_legal_change" in open_gaps:
            blockers.append("reviewed_boja_missing")
        if "missing_citizen_direction" in open_gaps:
            blockers.append("citizen_direction_missing")
        if "missing_responsible_actor" in open_gaps:
            blockers.append("responsible_actor_missing")

        if "missing_budget_execution" in open_gaps:
            has_budget_like = bool(
                kind_counts.get("budget_plan")
                or kind_counts.get("contract_award")
                or kind_counts.get("grant_award")
                or kind_counts.get("treasury_payment_aggregate")
            )
            if not queue_items:
                blockers.append("execution_source_plan_missing")
            elif not has_budget_like:
                blockers.append("budget_or_execution_review_missing")
            else:
                blockers.append("delivery_or_beneficiary_missing")

        if "missing_outcomes" in open_gaps:
            has_observed_outcome = bool(kind_counts.get("observed_outcome_series"))
            if not has_observed_outcome:
                blockers.append("observed_outcome_missing")
            elif post_change_outcome_rows_total(execution_rows) <= 0:
                blockers.append("post_change_outcome_missing")
            else:
                blockers.append("causal_link_missing")

        if blockers and "causal_link_missing" not in blockers:
            blockers.append("causal_link_missing")
        if blockers and "merit_blame_review_missing" not in blockers:
            blockers.append("merit_blame_review_missing")

        blockers = sorted(set(blockers), key=lambda blocker: READINESS_BLOCKER_PRIORITY.index(blocker))
        primary_blocker = blockers[0] if blockers else "ready_for_merit_blame_review"
        if primary_blocker != "ready_for_merit_blame_review":
            primary_blockers[primary_blocker] += 1
        classification = issue_readiness_classification(
            packet=packet,
            queue_items=queue_items,
            execution_rows=execution_rows,
            kind_counts=kind_counts,
            blockers=blockers,
        )
        classification_counts[classification] += 1
        delivery_evidence_hunts = (
            build_delivery_evidence_hunts_for_issue(
                topic_id=topic_id,
                topic_label=str(packet.get("topic_label") or program_topic_label(topic_id)),
                execution_rows=execution_rows,
            )
            if "delivery_or_beneficiary_missing" in blockers
            else []
        )
        next_actions = [
            readiness_next_action(blocker, queue_source_ids if blocker in {"budget_or_execution_review_missing", "delivery_or_beneficiary_missing", "observed_outcome_missing", "post_change_outcome_missing"} else [])
            for blocker in blockers[:4]
        ]
        for action in next_actions:
            if action.get("blocker_id") != "delivery_or_beneficiary_missing":
                continue
            sample_targets = [
                target
                for hunt in delivery_evidence_hunts[:2]
                for target in (hunt.get("search_targets") or [])[:1]
            ][:3]
            action["delivery_evidence_hunts_total"] = len(delivery_evidence_hunts)
            action["delivery_evidence_search_targets_total"] = sum(
                int(hunt.get("search_targets_total") or 0) for hunt in delivery_evidence_hunts
            )
            action["sample_delivery_search_targets"] = sample_targets
        for action in next_actions[:1]:
            next_action_counts[str(action.get("action_id") or "")] += 1

        issues.append(
            {
                "topic_id": topic_id,
                "topic_label": packet.get("topic_label") or program_topic_label(topic_id),
                "classification": classification,
                "primary_blocker": primary_blocker,
                "primary_blocker_label": READINESS_BLOCKER_LABELS.get(primary_blocker, "Listo para revision."),
                "public_merit_blame_eligible": classification == "publishable_merit_blame_ready",
                "claim_status": "readiness_classifier_no_merit_or_blame_claim",
                "program_measures_total": int(packet.get("program_measures_total") or 0),
                "reviewed_vote_items_total": int(packet.get("reviewed_vote_items_total") or 0),
                "reviewed_boja_legal_changes_total": int(packet.get("reviewed_boja_legal_changes_total") or 0),
                "observed_responsibility_claims_total": int(packet.get("observed_responsibility_claims_total") or 0),
                "issue_review_status": packet.get("issue_review_status") or "",
                "execution_queue_items_total": len(queue_items),
                "reviewed_execution_evidence_rows_total": len(execution_rows),
                "reviewed_execution_evidence_kind_counts": [
                    {"key": key, "count": count}
                    for key, count in sorted(kind_counts.items(), key=lambda item: (-item[1], item[0]))
                ],
                "post_change_outcome_rows_total": post_change_outcome_rows_total(execution_rows),
                "delivery_evidence_hunts_total": len(delivery_evidence_hunts),
                "delivery_evidence_search_targets_total": sum(
                    int(hunt.get("search_targets_total") or 0) for hunt in delivery_evidence_hunts
                ),
                "delivery_evidence_hunts": delivery_evidence_hunts,
                "blockers": blockers,
                "next_actions": next_actions,
                "next_action": next_actions[0] if next_actions else {},
            }
        )

    issues.sort(
        key=lambda row: (
            0 if row["classification"].startswith("responsibility_execution") else 1,
            READINESS_BLOCKER_PRIORITY.index(row["primary_blocker"])
            if row["primary_blocker"] in READINESS_BLOCKER_PRIORITY
            else 999,
            -int(row["observed_responsibility_claims_total"]),
            str(row["topic_label"]),
        )
    )

    return {
        "schema_version": "andalucia_2026_accountability_readiness_v1",
        "status": "blocked_pending_post_change_outcomes_and_causality"
        if issues
        else "no_issue_packets",
        "claim_status": "readiness_classifier_no_merit_or_blame_claim",
        "topics_total": len(issues),
        "publishable_merit_blame_topics_total": sum(1 for row in issues if row["public_merit_blame_eligible"]),
        "topics_with_observed_responsibility_total": sum(
            1 for row in issues if int(row["observed_responsibility_claims_total"] or 0) > 0
        ),
        "topics_with_execution_evidence_total": sum(
            1 for row in issues if int(row["reviewed_execution_evidence_rows_total"] or 0) > 0
        ),
        "topics_with_observed_outcome_baseline_total": sum(
            1
            for row in issues
            for count in row["reviewed_execution_evidence_kind_counts"]
            if count["key"] == "observed_outcome_series" and int(count["count"] or 0) > 0
        ),
        "topics_with_post_change_outcome_total": sum(
            1 for row in issues if int(row["post_change_outcome_rows_total"] or 0) > 0
        ),
        "delivery_evidence_hunts_total": sum(int(row.get("delivery_evidence_hunts_total") or 0) for row in issues),
        "delivery_evidence_hunt_topics_total": sum(
            1 for row in issues if int(row.get("delivery_evidence_hunts_total") or 0) > 0
        ),
        "delivery_evidence_search_targets_total": sum(
            int(row.get("delivery_evidence_search_targets_total") or 0) for row in issues
        ),
        "classification_counts": [
            {"key": key, "count": count}
            for key, count in sorted(classification_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "primary_blocker_counts": [
            {
                "key": key,
                "label": READINESS_BLOCKER_LABELS.get(key, key),
                "count": count,
            }
            for key, count in sorted(
                primary_blockers.items(),
                key=lambda item: (READINESS_BLOCKER_PRIORITY.index(item[0]), item[0]),
            )
        ],
        "next_action_counts": [
            {"key": key, "count": count}
            for key, count in sorted(next_action_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "issues": issues,
        "automation_command": "just etl-andalucia-2026-accountability-assist",
        "open_limitations": [
            "classifier_is_readiness_only",
            "no_merit_blame_without_post_change_outcome",
            "no_merit_blame_without_causal_link_review",
        ],
    }


def reviewed_outcome_majority_side(effect_outcome: str) -> str:
    if effect_outcome in {"approved_by_majority_yes", "decree_law_validated_by_majority_yes"}:
        return "si"
    if effect_outcome == "rejected_by_majority_no":
        return "no"
    return ""


def observed_vote_relation_to_outcome(position: str, majority_side: str) -> str:
    if position == "abstenciones":
        return "abstained_on_reviewed_outcome"
    if position == "blancos":
        return "blank_vote_observed"
    if position in {"si", "no"} and majority_side in {"si", "no"}:
        if position == majority_side:
            return "with_reviewed_outcome"
        return "against_reviewed_outcome"
    return "observed_other"


def reviewed_effect_outcome_label(effect_outcome: str) -> str:
    labels = {
        "approved_by_majority_yes": "aprobada por mayoria si",
        "decree_law_validated_by_majority_yes": "decreto-ley convalidado por mayoria si",
        "rejected_by_majority_no": "rechazada por mayoria no",
    }
    return labels.get(effect_outcome, effect_outcome.replace("_", " ") if effect_outcome else "resultado revisado")


def build_accountability_claim_evidence(
    *,
    source_url: str,
    source_locator: str,
    review_summary: str,
    source_evidence: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    evidence_rows: list[dict[str, str]] = []
    for row in source_evidence or []:
        if not isinstance(row, dict):
            continue
        evidence_rows.append(
            {
                "source_kind": str(row.get("source_kind") or "official_vote_pdf_text"),
                "source_url": source_url,
                "source_locator": str(row.get("source_locator") or source_locator),
                "evidence_excerpt": compact_evidence_quote(
                    row.get("evidence_excerpt") or review_summary,
                    max_words=28,
                    max_chars=240,
                ),
            }
        )
    if not evidence_rows:
        evidence_rows.append(
            {
                "source_kind": "official_vote_pdf_text",
                "source_url": source_url,
                "source_locator": source_locator,
                "evidence_excerpt": compact_evidence_quote(review_summary, max_words=28, max_chars=240),
            }
        )
    return evidence_rows[:2]


def build_party_legislative_observation_claims(parliament_report: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for item in parliament_report.get("vote_impact_review_queue") or []:
        if not isinstance(item, dict) or not is_reviewed_vote_item(item):
            continue
        source_url = str(item.get("source_url") or "")
        source_locator = str(item.get("source_locator") or "")
        effect_outcome = str(item.get("effect_outcome") or "")
        majority_side = str(item.get("majority_side") or reviewed_outcome_majority_side(effect_outcome))
        outcome_label = reviewed_effect_outcome_label(effect_outcome)
        topic_id = str(item.get("topic_id") or "sin_tema")
        topic_label = str(item.get("topic_label") or program_topic_label(topic_id))
        for party_vote in item.get("party_vote_totals") or []:
            if not isinstance(party_vote, dict):
                continue
            party_key = str(party_vote.get("party_key") or "")
            if not party_key:
                continue
            position = str(party_vote.get("dominant_position") or "")
            relation = observed_vote_relation_to_outcome(position, majority_side)
            party_label = str(party_vote.get("party_label") or party_vote.get("party_acronym") or party_key)
            claims.append(
                {
                    "claim_id": stable_slug(
                        "andalucia-2026:party-legislative-observation:"
                        f"{item.get('review_item_id') or item.get('vote_event_id') or ''}:{party_key}"
                    ),
                    "claim_kind": "party_legislative_vote_observation",
                    "claim_status": "published_observed_responsibility_no_merit_or_blame",
                    "interpretation_status": "legal_effect_reviewed_outcome_pending",
                    "actor_kind": "party",
                    "actor_key": party_key,
                    "actor_label": party_label,
                    "party_key": party_key,
                    "party_label": party_label,
                    "topic_id": topic_id,
                    "topic_label": topic_label,
                    "date": item.get("date") or "",
                    "vote_event_id": item.get("vote_event_id") or "",
                    "review_item_id": item.get("review_item_id") or "",
                    "numexp": item.get("numexp") or "",
                    "title": compact_evidence_quote(item.get("title"), max_words=24, max_chars=220),
                    "reviewed_issue_label": item.get("reviewed_issue_label") or topic_label,
                    "vote_position": position,
                    "relation_to_outcome": relation,
                    "effect_position_bucket": party_position_effect_bucket(position, effect_outcome),
                    "effect_outcome": effect_outcome,
                    "effect_outcome_label": outcome_label,
                    "majority_side": majority_side,
                    "total_si": int(item.get("total_si") or 0),
                    "total_no": int(item.get("total_no") or 0),
                    "party_si": int(party_vote.get("si") or 0),
                    "party_no": int(party_vote.get("no") or 0),
                    "party_abstenciones": int(party_vote.get("abstenciones") or 0),
                    "evidence_tier": item.get("evidence_tier") or "tier_1_primary",
                    "review_confidence": item.get("review_confidence") or "",
                    "source_url": source_url,
                    "initiative_source_url": item.get("initiative_source_url") or "",
                    "evidence": build_accountability_claim_evidence(
                        source_url=source_url,
                        source_locator=source_locator,
                        review_summary=str(item.get("review_summary") or ""),
                        source_evidence=list(item.get("source_evidence") or []),
                    ),
                    "statement": (
                        f"{party_label} voto {position or 'sin dato'} en {topic_label}; "
                        f"resultado oficial revisado: {outcome_label} "
                        f"({int(item.get('total_si') or 0)} si / {int(item.get('total_no') or 0)} no)."
                    ),
                    "limitation": (
                        "Observa posicion y resultado legislativo. No atribuye merito, culpa, "
                        "impacto ciudadano, ejecucion, dinero ni outcome final."
                    ),
                }
            )
    return claims


def build_focus_candidate_legislative_observation_claims(
    focus_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for candidate in focus_candidates:
        if not isinstance(candidate, dict):
            continue
        summary = candidate.get("reviewed_legislative_impact_summary") or {}
        if not isinstance(summary, dict) or int(summary.get("reviewed_vote_events_total") or 0) <= 0:
            continue
        actor_key = str(candidate.get("candidate_id") or candidate.get("focus_id") or "")
        actor_label = str(candidate.get("official_person_name") or candidate.get("person_name") or actor_key)
        for sample in list(summary.get("sample_votes") or [])[:5]:
            if not isinstance(sample, dict):
                continue
            effect_outcome = str(sample.get("effect_outcome") or "")
            majority_side = reviewed_outcome_majority_side(effect_outcome)
            position = str(sample.get("vote_position") or "")
            topic_id = str(sample.get("topic_id") or sample.get("initiative_topic_id") or "sin_tema")
            topic_label = str(sample.get("topic_label") or sample.get("initiative_topic_label") or program_topic_label(topic_id))
            if topic_id in {"", "sin_tema"}:
                topic_info = reviewed_vote_topic_from_review(
                    {
                        "reviewed_issue_label": sample.get("reviewed_issue_label") or "",
                        "review_summary": sample.get("review_summary") or "",
                    },
                    sample,
                )
                topic_id = topic_info["topic_id"]
                topic_label = topic_info["topic_label"]
            claims.append(
                {
                    "claim_id": stable_slug(
                        "andalucia-2026:candidate-legislative-observation:"
                        f"{actor_key}:{sample.get('vote_member_id') or sample.get('vote_event_id') or ''}"
                    ),
                    "claim_kind": "candidate_legislative_vote_observation",
                    "claim_status": "published_observed_responsibility_no_merit_or_blame",
                    "interpretation_status": "legal_effect_reviewed_outcome_pending",
                    "actor_kind": "candidate",
                    "actor_key": actor_key,
                    "actor_label": actor_label,
                    "candidate_id": candidate.get("candidate_id") or "",
                    "person_id": candidate.get("person_id"),
                    "person_name": actor_label,
                    "party_key": str(candidate.get("party_key") or stable_slug(candidate.get("party_acronym") or "")),
                    "party_label": candidate.get("party_acronym") or "",
                    "province": candidate.get("province") or "",
                    "list_position": candidate.get("list_position") or "",
                    "topic_id": topic_id,
                    "topic_label": topic_label,
                    "date": sample.get("date") or "",
                    "vote_event_id": sample.get("vote_event_id") or "",
                    "vote_member_id": sample.get("vote_member_id") or "",
                    "numexp": sample.get("numexp") or "",
                    "title": compact_evidence_quote(sample.get("title"), max_words=24, max_chars=220),
                    "reviewed_issue_label": sample.get("reviewed_issue_label") or topic_label,
                    "vote_position": position,
                    "relation_to_outcome": observed_vote_relation_to_outcome(position, majority_side),
                    "effect_position_bucket": party_position_effect_bucket(position, effect_outcome),
                    "effect_outcome": effect_outcome,
                    "effect_outcome_label": reviewed_effect_outcome_label(effect_outcome),
                    "majority_side": majority_side,
                    "evidence_tier": summary.get("evidence_tier") or "tier_1_primary",
                    "source_url": sample.get("source_url") or "",
                    "initiative_source_url": sample.get("initiative_source_url") or "",
                    "evidence": build_accountability_claim_evidence(
                        source_url=str(sample.get("source_url") or ""),
                        source_locator=str(sample.get("vote_member_id") or sample.get("vote_event_id") or ""),
                        review_summary=str(sample.get("review_summary") or ""),
                    ),
                    "statement": (
                        f"{actor_label} voto {position or 'sin dato'} en {topic_label}; "
                        f"resultado oficial revisado: {reviewed_effect_outcome_label(effect_outcome)}."
                    ),
                    "limitation": (
                        "Observa voto nominal enlazado a candidatura. No atribuye merito, culpa, "
                        "impacto ciudadano, ejecucion, dinero ni outcome final."
                    ),
                }
            )
    return claims


def count_claim_rows(claims: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(str(row.get(key) or "sin_dato") for row in claims)
    out = []
    for value, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
        label = program_topic_label(value) if key == "topic_id" else value.replace("_", " ")
        out.append({"key": value, "label": label, "count": count})
    return out


def build_published_accountability_claims(
    parliament_report: dict[str, Any],
    focus_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    party_claims = build_party_legislative_observation_claims(parliament_report)
    candidate_claims = build_focus_candidate_legislative_observation_claims(focus_candidates)
    claims = sorted(
        party_claims + candidate_claims,
        key=lambda row: (
            str(row.get("topic_label") or ""),
            str(row.get("actor_kind") or ""),
            str(row.get("actor_label") or ""),
            str(row.get("claim_id") or ""),
        ),
    )
    return {
        "schema_version": "andalucia_2026_published_accountability_claims_v1",
        "claim_status": "published_observed_responsibility_no_merit_or_blame" if claims else "no_public_claims",
        "interpretation_status": "legal_effect_reviewed_outcome_pending" if claims else "no_reviewed_observations",
        "claims_total": len(claims),
        "party_claims_total": len(party_claims),
        "candidate_claims_total": len(candidate_claims),
        "actors_total": len({str(row.get("actor_kind") or "") + ":" + str(row.get("actor_key") or "") for row in claims}),
        "topics_total": len({str(row.get("topic_id") or "") for row in claims}),
        "claim_kind_counts": count_claim_rows(claims, "claim_kind"),
        "relation_to_outcome_counts": count_claim_rows(claims, "relation_to_outcome"),
        "topic_counts": count_claim_rows(claims, "topic_id"),
        "claims": claims[:120],
        "open_limitations": [
            "citizen_direction_not_reviewed",
            "budget_execution_not_linked",
            "outcomes_not_linked",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
        ],
    }


def build_responsibility_comparison(
    parties: list[dict[str, Any]],
    focus_candidates: list[dict[str, Any]],
    parliament_report: dict[str, Any],
    boja_report: dict[str, Any],
) -> dict[str, Any]:
    initiative_counts_by_party_key = {
        stable_slug(row.get("key")): int(row.get("count") or 0)
        for row in parliament_report.get("legislative_initiatives_by_party_key") or []
        if row.get("key") and row.get("key") != "sin_dato"
    }
    candidate_vote_counts_by_party_key: Counter[str] = Counter()
    reviewed_candidate_counts_by_party_key: Counter[str] = Counter()
    for row in parliament_report.get("candidate_vote_summaries") or []:
        if isinstance(row, dict) and row.get("party_key"):
            candidate_vote_counts_by_party_key[str(row.get("party_key"))] += 1
    for row in parliament_report.get("reviewed_candidate_vote_summaries") or []:
        if isinstance(row, dict) and row.get("party_key"):
            reviewed_candidate_counts_by_party_key[str(row.get("party_key"))] += 1

    party_profiles: list[dict[str, Any]] = []
    for party in parties:
        party_key = str(party.get("party_key") or "")
        evidence_ref = party.get("accountability_evidence") or {}
        evidence_entries, evidence_issues = accountability_evidence_counts(evidence_ref)
        vote_summary = party.get("parliament_vote_summary") or {}
        reviewed_summary = party.get("reviewed_legislative_impact_summary") or {}
        program_measures_total = int(party.get("program_measures_total") or 0)
        verified_program_sources_total = int(party.get("program_verified_sources_total") or 0)
        reviewed_vote_events_total = int(reviewed_summary.get("reviewed_vote_events_total") or 0)
        vote_events_total = int(vote_summary.get("vote_events_total") or 0)
        initiatives_total = int(initiative_counts_by_party_key.get(party_key, 0))
        gaps: list[str] = []
        if not verified_program_sources_total:
            gaps.append("missing_verified_program")
        if not vote_events_total:
            gaps.append("missing_parliament_vote_record")
        if not reviewed_vote_events_total:
            gaps.append("missing_reviewed_vote_signal")
        if not initiatives_total:
            gaps.append("missing_party_group_initiatives")
        if evidence_ref.get("status") != "linked_accountability_evidence":
            gaps.append("missing_accountability_ledger_link")
        status = (
            "traceable_program_votes_and_ledger"
            if not gaps
            else "traceable_program_and_votes"
            if program_measures_total and vote_events_total and reviewed_vote_events_total
            else "partial_traceability"
            if program_measures_total or vote_events_total or evidence_entries
            else "identity_only"
        )
        party_profiles.append(
            {
                "party_key": party_key,
                "party_acronym": party.get("party_acronym") or party_key,
                "party_label": party.get("party_label") or party.get("party_acronym") or party_key,
                "status": status,
                "candidate_lists_total": int(party.get("candidate_lists_total") or 0),
                "matched_candidates_total": int(party.get("matched_candidates_total") or 0),
                "candidate_nominal_vote_profiles_total": int(candidate_vote_counts_by_party_key.get(party_key, 0)),
                "candidate_reviewed_vote_profiles_total": int(reviewed_candidate_counts_by_party_key.get(party_key, 0)),
                "program_sources_total": int(party.get("program_sources_total") or 0),
                "verified_program_sources_total": verified_program_sources_total,
                "declared_program_measures_total": program_measures_total,
                "parliament_vote_events_total": vote_events_total,
                "reviewed_vote_events_total": reviewed_vote_events_total,
                "voted_with_reviewed_outcome_total": int(
                    reviewed_summary.get("voted_with_reviewed_outcome_total") or 0
                ),
                "voted_against_reviewed_outcome_total": int(
                    reviewed_summary.get("voted_against_reviewed_outcome_total") or 0
                ),
                "official_group_initiatives_total": initiatives_total,
                "accountability_evidence_status": evidence_ref.get("status") or "not_matchable",
                "accountability_entries_total": evidence_entries,
                "accountability_issues_total": evidence_issues,
                "primary_gap": primary_responsibility_gap(gaps),
                "open_gaps": gaps,
                "claim_status": "responsibility_evidence_comparison_only_no_merit_or_blame_claim",
            }
        )

    candidate_profiles: list[dict[str, Any]] = []
    for candidate in focus_candidates:
        evidence_ref = candidate.get("accountability_evidence") or {}
        evidence_entries, evidence_issues = accountability_evidence_counts(evidence_ref)
        vote_summary = candidate.get("parliament_vote_summary") or {}
        reviewed_summary = candidate.get("reviewed_legislative_impact_summary") or {}
        program_measures_total = int(candidate.get("program_measures_total") or 0)
        vote_events_total = int(vote_summary.get("vote_events_total") or 0)
        reviewed_vote_events_total = int(reviewed_summary.get("reviewed_vote_events_total") or 0)
        gaps = []
        if not candidate.get("candidate_id"):
            gaps.append("missing_official_candidate_match")
        if not candidate.get("person_id"):
            gaps.append("missing_person_id_match")
        if not program_measures_total:
            gaps.append("missing_verified_party_program_measures")
        if not vote_events_total:
            gaps.append("missing_nominal_parliament_vote_record")
        if not reviewed_vote_events_total:
            gaps.append("missing_reviewed_vote_signal")
        if evidence_ref.get("status") != "linked_accountability_evidence":
            gaps.append("missing_accountability_ledger_link")
        status = (
            "traceable_candidate_votes_and_ledger"
            if not gaps
            else "traceable_candidate_votes"
            if reviewed_vote_events_total
            else "traceable_candidate_identity"
            if candidate.get("candidate_id")
            else "blocked_identity"
        )
        candidate_profiles.append(
            {
                "focus_id": candidate.get("focus_id") or "",
                "candidate_id": candidate.get("candidate_id") or "",
                "person_id": candidate.get("person_id"),
                "person_name": candidate.get("official_person_name") or candidate.get("person_name") or "",
                "party_key": stable_slug(candidate.get("party_acronym")),
                "party_acronym": candidate.get("party_acronym") or "",
                "province": candidate.get("province") or "",
                "list_position": candidate.get("list_position") or "",
                "status": status,
                "person_match_status": candidate.get("person_match_status") or "",
                "mandate_count": int(candidate.get("mandate_count") or 0),
                "active_mandate_count": int(candidate.get("active_mandate_count") or 0),
                "declared_program_measures_total": program_measures_total,
                "parliament_vote_events_total": vote_events_total,
                "reviewed_vote_events_total": reviewed_vote_events_total,
                "voted_with_reviewed_outcome_total": int(
                    reviewed_summary.get("voted_with_reviewed_outcome_total") or 0
                ),
                "voted_against_reviewed_outcome_total": int(
                    reviewed_summary.get("voted_against_reviewed_outcome_total") or 0
                ),
                "accountability_evidence_status": evidence_ref.get("status") or "not_matchable",
                "accountability_entries_total": evidence_entries,
                "accountability_issues_total": evidence_issues,
                "primary_gap": primary_responsibility_gap(gaps),
                "open_gaps": gaps,
                "claim_status": "responsibility_evidence_comparison_only_no_merit_or_blame_claim",
            }
        )

    return {
        "schema_version": "andalucia_2026_responsibility_comparison_v1",
        "claim_status": "responsibility_evidence_comparison_only_no_merit_or_blame_claim",
        "interpretation_status": "evidence_readiness_not_moral_assessment",
        "party_profiles_total": len(party_profiles),
        "party_profiles_with_reviewed_vote_signals_total": sum(
            1 for row in party_profiles if int(row.get("reviewed_vote_events_total") or 0) > 0
        ),
        "candidate_profiles_total": len(candidate_profiles),
        "candidate_profiles_with_reviewed_vote_signals_total": sum(
            1 for row in candidate_profiles if int(row.get("reviewed_vote_events_total") or 0) > 0
        ),
        "shared_boja_impact_review_queue_total": int(boja_report.get("impact_review_queue_total") or 0),
        "shared_boja_reviewed_impact_items_total": int(boja_report.get("reviewed_impact_items_total") or 0),
        "party_profiles": sorted(
            party_profiles,
            key=lambda row: (
                -int(row.get("reviewed_vote_events_total") or 0),
                -int(row.get("parliament_vote_events_total") or 0),
                -int(row.get("declared_program_measures_total") or 0),
                str(row.get("party_acronym") or ""),
            ),
        ),
        "focus_candidate_profiles": candidate_profiles,
    }


def build_snapshot(
    *,
    candidature_text: str,
    candidature_source: dict[str, Any],
    db_path: Path = DEFAULT_DB,
    source_catalog_path: Path = DEFAULT_SOURCE_CATALOG,
    program_report: dict[str, Any] | None = None,
    boja_report: dict[str, Any] | None = None,
    parliament_report: dict[str, Any] | None = None,
    issue_reviews_report: dict[str, Any] | None = None,
    execution_evidence_candidate_report: dict[str, Any] | None = None,
    execution_evidence_review_report: dict[str, Any] | None = None,
    accountability_evidence_path: Path | None = None,
    accountability_evidence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = parse_candidature_text(candidature_text)
    db_report = enrich_candidates_with_db(parsed["candidates"], db_path)
    program_report = program_report or empty_program_report(DEFAULT_PROGRAM_SOURCES)
    boja_report = boja_report or empty_boja_norms_report(DEFAULT_RAW_DIR / "boja_normas")
    parliament_report = parliament_report or empty_parliament_activity_report(DEFAULT_RAW_DIR / "parlamento_andalucia")
    issue_reviews_report = issue_reviews_report or empty_issue_reviews_report(DEFAULT_ISSUE_REVIEWS)
    execution_evidence_candidate_report = (
        execution_evidence_candidate_report or empty_execution_evidence_candidate_report()
    )
    execution_evidence_review_report = (
        execution_evidence_review_report or empty_execution_evidence_reviews_report(DEFAULT_EXECUTION_EVIDENCE_REVIEWS)
    )
    post_change_outcome_monitor = (
        execution_evidence_candidate_report.get("outcome_series_monitor")
        if isinstance(execution_evidence_candidate_report.get("outcome_series_monitor"), dict)
        else empty_post_change_outcome_monitor()
    )
    accountability_evidence_report = accountability_evidence_report or load_accountability_evidence_report(
        accountability_evidence_path
    )
    attach_candidate_accountability_status(parsed["candidates"], accountability_evidence_report)
    candidate_vote_summaries = build_parliament_candidate_vote_summaries(parsed["candidates"], parliament_report)
    reviewed_party_vote_summaries = summarize_reviewed_parliament_party_vote_impacts(
        list(parliament_report.get("vote_impact_review_queue") or [])
    )
    reviewed_candidate_vote_summaries = build_reviewed_parliament_candidate_vote_summaries(
        parsed["candidates"],
        parliament_report,
    )
    parliament_report["candidate_vote_summaries"] = candidate_vote_summaries
    parliament_report["candidate_vote_summaries_total"] = len(candidate_vote_summaries)
    parliament_report["reviewed_vote_events_by_party"] = reviewed_party_vote_summaries
    parliament_report["reviewed_vote_events_by_party_total"] = len(reviewed_party_vote_summaries)
    parliament_report["reviewed_candidate_vote_summaries"] = reviewed_candidate_vote_summaries
    parliament_report["reviewed_candidate_vote_summaries_total"] = len(reviewed_candidate_vote_summaries)
    parliament_report["member_vote_candidate_matches_total"] = sum(
        int(row.get("vote_events_total") or 0) for row in candidate_vote_summaries
    )
    parliament_report["member_vote_match_status"] = (
        "candidate_name_exact_unique"
        if candidate_vote_summaries
        else "no_candidate_member_vote_matches"
    )
    evidence_lanes = build_evidence_lanes(program_report, boja_report, parliament_report)
    parties = build_party_index(
        parsed["lists"],
        parsed["candidates"],
        program_report,
        accountability_evidence_report,
        boja_report,
        parliament_report,
    )
    source_catalog = load_source_catalog(source_catalog_path)
    focus_candidates = build_focus_candidates(
        parsed["candidates"],
        program_report,
        accountability_evidence_report,
        boja_report,
        parliament_report,
    )
    responsibility_comparison = build_responsibility_comparison(
        parties,
        focus_candidates,
        parliament_report,
        boja_report,
    )
    published_accountability_claims = build_published_accountability_claims(
        parliament_report,
        focus_candidates,
    )
    issue_accountability_packets = build_issue_accountability_packets(
        program_report,
        parliament_report,
        boja_report,
        parties,
        published_accountability_claims,
        issue_reviews_report,
    )
    execution_evidence_queue = build_issue_execution_evidence_queue(
        issue_accountability_packets,
        execution_evidence_candidate_report,
        execution_evidence_review_report,
    )
    accountability_readiness = build_issue_readiness_report(
        issue_accountability_packets,
        execution_evidence_queue,
    )
    official_found = [row for row in focus_candidates if row.get("candidate_id")]
    candidates_with_accountability = [
        row for row in parsed["candidates"] if row.get("accountability_evidence_status") == "linked_accountability_evidence"
    ]
    focus_with_accountability = [
        row
        for row in focus_candidates
        if (row.get("accountability_evidence") or {}).get("status") == "linked_accountability_evidence"
    ]
    parties_with_accountability = [
        row
        for row in parties
        if (row.get("accountability_evidence") or {}).get("status") == "linked_accountability_evidence"
    ]
    focus_with_member_votes = [
        row for row in focus_candidates if int((row.get("parliament_vote_summary") or {}).get("vote_events_total") or 0) > 0
    ]
    published_parliament_report = build_published_parliament_report(parliament_report)

    coverage = dict(parsed["coverage"])
    has_program_text = int(program_report.get("text_extracted_sources_total") or 0) > 0
    has_program_measures = int(program_report.get("measures_total") or 0) > 0
    has_boja_impact_review_queue = int(boja_report.get("impact_review_queue_total") or 0) > 0
    has_parliament_activity = int(parliament_report.get("legislative_initiatives_total") or 0) > 0
    has_parliament_vote_review_queue = int(parliament_report.get("vote_impact_review_queue_total") or 0) > 0
    has_reviewed_vote_signals = int(parliament_report.get("reviewed_vote_items_total") or 0) > 0
    has_issue_reviews = int(issue_accountability_packets.get("issue_reviews_total") or 0) > 0
    coverage.update(
        {
            "distinct_party_keys_total": len(parties),
            "focus_candidates_total": len(focus_candidates),
            "focus_candidates_found_total": len(official_found),
            "matched_candidates_total": db_report["matched_candidates_total"],
            "candidates_with_accountability_evidence_total": len(candidates_with_accountability),
            "focus_candidates_with_accountability_evidence_total": len(focus_with_accountability),
            "parties_with_accountability_evidence_total": len(parties_with_accountability),
            "accountability_evidence_source_entries_total": int(
                accountability_evidence_report.get("source_entries_total") or 0
            ),
            "accountability_evidence_actor_answers_total": int(
                accountability_evidence_report.get("source_actor_answers_total") or 0
            ),
            "parties_with_actor_backbone_total": sum(
                1 for party in parties if party["assessment_status"] == "candidate_list_plus_actor_backbone"
            ),
            "program_sources_total": int(program_report.get("sources_total") or 0),
            "program_sources_fetched_total": int(program_report.get("fetched_sources_total") or 0),
            "program_sources_verified_total": int(program_report.get("verified_sources_total") or 0),
            "program_sources_text_extracted_total": int(program_report.get("text_extracted_sources_total") or 0),
            "program_parties_with_text_total": int(program_report.get("party_keys_with_program_total") or 0),
            "program_sources_press_hosted_total": int(program_report.get("press_hosted_sources_total") or 0),
            "program_measures_total": int(program_report.get("measures_total") or 0),
            "program_parties_with_measures_total": int(program_report.get("parties_with_measures_total") or 0),
            "program_topics_with_measures_total": int(program_report.get("topics_with_measures_total") or 0),
            "parliament_andalucia_legislative_initiatives_total": int(
                parliament_report.get("legislative_initiatives_total") or 0
            ),
            "parliament_andalucia_voting_result_documents_total": int(
                parliament_report.get("voting_result_documents_total") or 0
            ),
            "parliament_andalucia_initiative_detail_pages_checked_total": int(
                parliament_report.get("initiative_detail_pages_checked_total") or 0
            ),
            "parliament_andalucia_initiative_detail_vote_documents_total": int(
                parliament_report.get("initiative_detail_vote_documents_total") or 0
            ),
            "parliament_andalucia_initiative_detail_vote_documents_new_total": int(
                parliament_report.get("initiative_detail_vote_documents_new_total") or 0
            ),
            "parliament_andalucia_voting_documents_total": int(parliament_report.get("voting_documents_total") or 0),
            "parliament_andalucia_parsed_vote_events_total": int(
                parliament_report.get("parsed_vote_events_total") or 0
            ),
            "parliament_andalucia_vote_events_with_initiative_total": int(
                parliament_report.get("vote_events_with_initiative_total") or 0
            ),
            "parliament_andalucia_vote_events_with_official_initiative_total": int(
                parliament_report.get("vote_events_with_official_initiative_total") or 0
            ),
            "parliament_andalucia_vote_events_with_legal_effect_triage_total": int(
                parliament_report.get("vote_events_with_legal_effect_triage_total") or 0
            ),
            "parliament_andalucia_vote_events_with_party_totals_total": int(
                parliament_report.get("vote_events_with_party_totals_total") or 0
            ),
            "parliament_andalucia_party_topic_vote_rows_total": len(
                parliament_report.get("vote_events_by_party_topic") or []
            ),
            "parliament_andalucia_legal_effect_rows_total": len(
                parliament_report.get("vote_events_by_legal_effect") or []
            ),
            "parliament_andalucia_member_vote_records_total": int(
                parliament_report.get("member_vote_records_total") or 0
            ),
            "parliament_andalucia_member_vote_candidate_matches_total": int(
                parliament_report.get("member_vote_candidate_matches_total") or 0
            ),
            "parliament_andalucia_candidates_with_member_votes_total": int(
                parliament_report.get("candidate_vote_summaries_total") or 0
            ),
            "parliament_andalucia_focus_candidates_with_member_votes_total": len(focus_with_member_votes),
            "parliament_andalucia_party_group_initiatives_total": sum(
                int(row.get("count") or 0)
                for row in parliament_report.get("legislative_initiatives_by_party_key") or []
                if row.get("key") != "sin_dato"
            ),
            "parliament_andalucia_vote_impact_review_items_total": int(
                parliament_report.get("vote_impact_review_queue_total") or 0
            ),
            "parliament_andalucia_vote_impact_review_batches_total": int(
                parliament_report.get("vote_impact_review_batches_total") or 0
            ),
            "parliament_andalucia_priority_vote_review_items_total": len(
                (parliament_report.get("vote_impact_review_packet") or {}).get("priority_items") or []
            ),
            "parliament_andalucia_reviewed_vote_items_total": int(
                parliament_report.get("reviewed_vote_items_total") or 0
            ),
            "parliament_andalucia_reviewed_party_vote_summaries_total": int(
                parliament_report.get("reviewed_vote_events_by_party_total") or 0
            ),
            "parliament_andalucia_reviewed_candidate_vote_summaries_total": int(
                parliament_report.get("reviewed_candidate_vote_summaries_total") or 0
            ),
            "boja_norms_records_total": int(boja_report.get("records_total") or 0),
            "boja_norms_topics_with_results_total": int(boja_report.get("topics_with_results_total") or 0),
            "boja_norms_api_total_hits": int(boja_report.get("api_total_hits") or 0),
            "boja_norms_details_available_total": int(boja_report.get("details_available_total") or 0),
            "boja_norms_fragments_total": int(boja_report.get("fragments_total") or 0),
            "boja_norms_impact_review_items_total": int(boja_report.get("impact_review_queue_total") or 0),
            "boja_norms_impact_review_batches_total": int(
                (boja_report.get("impact_review_packet") or {}).get("batches_total") or 0
            ),
            "boja_norms_priority_review_items_total": len(
                (boja_report.get("impact_review_packet") or {}).get("priority_items") or []
            ),
            "boja_norms_reviewed_impact_items_total": int(boja_report.get("reviewed_impact_items_total") or 0),
            "responsibility_party_profiles_total": int(
                responsibility_comparison.get("party_profiles_total") or 0
            ),
            "responsibility_party_profiles_with_reviewed_vote_signals_total": int(
                responsibility_comparison.get("party_profiles_with_reviewed_vote_signals_total") or 0
            ),
            "responsibility_focus_candidate_profiles_total": int(
                responsibility_comparison.get("candidate_profiles_total") or 0
            ),
            "responsibility_focus_candidate_profiles_with_reviewed_vote_signals_total": int(
                responsibility_comparison.get("candidate_profiles_with_reviewed_vote_signals_total") or 0
            ),
            "issue_accountability_packets_total": int(issue_accountability_packets.get("packets_total") or 0),
            "issue_accountability_packets_with_program_vote_boja_total": int(
                issue_accountability_packets.get("packets_with_program_vote_boja_total") or 0
            ),
            "issue_accountability_packets_with_reviewed_vote_total": int(
                issue_accountability_packets.get("packets_with_reviewed_vote_total") or 0
            ),
            "issue_accountability_packets_with_reviewed_boja_total": int(
                issue_accountability_packets.get("packets_with_reviewed_boja_total") or 0
            ),
            "issue_accountability_packets_with_observed_responsibility_total": int(
                issue_accountability_packets.get("packets_with_observed_responsibility_total") or 0
            ),
            "issue_accountability_packets_with_issue_review_total": int(
                issue_accountability_packets.get("packets_with_issue_review_total") or 0
            ),
            "issue_accountability_issue_reviews_total": int(
                issue_accountability_packets.get("issue_reviews_total") or 0
            ),
            "issue_accountability_issue_direction_reviews_total": int(
                issue_accountability_packets.get("issue_direction_reviews_total") or 0
            ),
            "issue_accountability_issue_actor_reviews_total": int(
                issue_accountability_packets.get("issue_actor_reviews_total") or 0
            ),
            "issue_accountability_execution_owner_reviewed_total": int(
                issue_accountability_packets.get("issue_execution_owner_reviews_total") or 0
            ),
            "issue_accountability_budget_allocation_reviewed_total": int(
                issue_accountability_packets.get("issue_budget_allocation_reviews_total") or 0
            ),
            "issue_accountability_party_topic_profiles_total": int(
                issue_accountability_packets.get("party_topic_profiles_total") or 0
            ),
            "issue_accountability_observed_responsibility_claims_total": int(
                issue_accountability_packets.get("observed_responsibility_claims_total") or 0
            ),
            "issue_accountability_observed_actor_profiles_total": int(
                issue_accountability_packets.get("observed_responsibility_actor_profiles_total") or 0
            ),
            "issue_accountability_reviewed_issues_total": int(
                issue_accountability_packets.get("issue_reviews_total") or 0
            ),
            "issue_accountability_direction_reviewed_total": int(
                issue_accountability_packets.get("issue_direction_reviews_total") or 0
            ),
            "issue_accountability_actor_reviewed_total": int(
                issue_accountability_packets.get("issue_actor_reviews_total") or 0
            ),
            "issue_execution_evidence_queue_total": int(execution_evidence_queue.get("queue_total") or 0),
            "issue_execution_evidence_topics_total": int(execution_evidence_queue.get("topics_total") or 0),
            "issue_execution_evidence_source_candidates_total": int(
                execution_evidence_queue.get("source_candidates_total") or 0
            ),
            "issue_execution_evidence_verified_source_candidates_total": int(
                execution_evidence_queue.get("verified_source_candidates_total") or 0
            ),
            "issue_execution_evidence_official_candidate_rows_total": int(
                execution_evidence_queue.get("official_candidate_rows_total") or 0
            ),
            "issue_execution_evidence_reviewed_rows_total": int(
                execution_evidence_queue.get("reviewed_evidence_rows_total") or 0
            ),
            "issue_execution_evidence_reviewed_budget_plan_rows_total": int(
                execution_evidence_queue.get("reviewed_budget_plan_rows_total") or 0
            ),
            "issue_execution_evidence_reviewed_contract_rows_total": int(
                execution_evidence_queue.get("reviewed_contract_rows_total") or 0
            ),
            "issue_execution_evidence_reviewed_grant_rows_total": int(
                execution_evidence_queue.get("reviewed_grant_rows_total") or 0
            ),
            "issue_execution_evidence_reviewed_treasury_payment_rows_total": int(
                execution_evidence_queue.get("reviewed_treasury_payment_rows_total") or 0
            ),
            "issue_execution_evidence_reviewed_indicator_target_rows_total": int(
                execution_evidence_queue.get("reviewed_indicator_target_rows_total") or 0
            ),
            "issue_execution_evidence_reviewed_observed_outcome_rows_total": int(
                execution_evidence_queue.get("reviewed_observed_outcome_rows_total") or 0
            ),
            "accountability_readiness_topics_total": int(accountability_readiness.get("topics_total") or 0),
            "accountability_readiness_publishable_merit_blame_topics_total": int(
                accountability_readiness.get("publishable_merit_blame_topics_total") or 0
            ),
            "accountability_readiness_topics_with_observed_responsibility_total": int(
                accountability_readiness.get("topics_with_observed_responsibility_total") or 0
            ),
            "accountability_readiness_topics_with_execution_evidence_total": int(
                accountability_readiness.get("topics_with_execution_evidence_total") or 0
            ),
            "accountability_readiness_topics_with_observed_outcome_baseline_total": int(
                accountability_readiness.get("topics_with_observed_outcome_baseline_total") or 0
            ),
            "accountability_readiness_topics_with_post_change_outcome_total": int(
                accountability_readiness.get("topics_with_post_change_outcome_total") or 0
            ),
            "accountability_readiness_delivery_evidence_hunts_total": int(
                accountability_readiness.get("delivery_evidence_hunts_total") or 0
            ),
            "accountability_readiness_delivery_evidence_hunt_topics_total": int(
                accountability_readiness.get("delivery_evidence_hunt_topics_total") or 0
            ),
            "accountability_readiness_delivery_evidence_search_targets_total": int(
                accountability_readiness.get("delivery_evidence_search_targets_total") or 0
            ),
            "post_change_outcome_monitor_series_total": int(
                post_change_outcome_monitor.get("series_total") or 0
            ),
            "post_change_outcome_monitor_waiting_series_total": int(
                post_change_outcome_monitor.get("waiting_series_total") or 0
            ),
            "post_change_outcome_monitor_candidate_series_total": int(
                post_change_outcome_monitor.get("post_change_candidate_series_total") or 0
            ),
            "post_change_outcome_monitor_missing_series_total": int(
                post_change_outcome_monitor.get("missing_series_total") or 0
            ),
            "issue_execution_evidence_budget_candidate_rows_total": int(
                execution_evidence_queue.get("budget_candidate_rows_total") or 0
            ),
            "issue_execution_evidence_contract_candidate_rows_total": int(
                execution_evidence_queue.get("contract_candidate_rows_total") or 0
            ),
            "issue_execution_evidence_treasury_payment_candidate_rows_total": int(
                execution_evidence_queue.get("treasury_payment_candidate_rows_total") or 0
            ),
            "issue_execution_evidence_outcome_candidate_rows_total": int(
                execution_evidence_queue.get("outcome_candidate_rows_total") or 0
            ),
            "issue_execution_evidence_source_files_cached_total": int(
                execution_evidence_queue.get("source_files_cached_total") or 0
            ),
            "published_accountability_claims_total": int(
                published_accountability_claims.get("claims_total") or 0
            ),
            "published_observed_responsibility_claims_total": int(
                published_accountability_claims.get("claims_total") or 0
            ),
            "published_party_legislative_claims_total": int(
                published_accountability_claims.get("party_claims_total") or 0
            ),
            "published_candidate_legislative_claims_total": int(
                published_accountability_claims.get("candidate_claims_total") or 0
            ),
            "program_measure_reviews_total": 0,
            "published_merit_blame_claims_total": 0,
            "source_gaps_total": len(SOURCE_GAP_LANES) + len(program_report.get("source_gaps") or []),
        }
    )

    return {
        "schema_version": "andalucia_2026_accountability_snapshot_v1",
        "generated_at": now_utc_iso(),
        "election": ELECTION,
        "sources": [candidature_source],
        "source_catalog": source_catalog,
        "program_sources": program_report,
        "parliament_activity": published_parliament_report,
        "boja_norms": boja_report,
        "accountability_evidence": {
            key: value
            for key, value in accountability_evidence_report.items()
            if key != "actors_by_key"
        },
        "coverage": coverage,
        "province_counts": parsed["province_counts"],
        "parties": parties,
        "focus_candidates": focus_candidates,
        "responsibility_comparison": responsibility_comparison,
        "issue_accountability_packets": issue_accountability_packets,
        "issue_accountability_reviews": {
            key: value
            for key, value in issue_reviews_report.items()
            if key != "reviews_by_topic"
        },
        "issue_execution_evidence_queue": execution_evidence_queue,
        "accountability_readiness": accountability_readiness,
        "post_change_outcome_monitor": post_change_outcome_monitor,
        "execution_evidence_reviews": {
            key: value
            for key, value in execution_evidence_review_report.items()
            if key not in {"reviews_by_candidate_row_id", "reviews_by_locator", "reviews_by_topic_gap"}
        },
        "published_accountability_claims": published_accountability_claims,
        "candidate_lists": parsed["lists"],
        "candidates": parsed["candidates"],
        "evidence_lanes": evidence_lanes,
        "method": {
            "current_public_claim_status": (
                "candidate_identity_programs_boja_reviewed_votes_observed_responsibility_issue_direction_and_execution_owner_reviews"
                if has_program_measures and has_boja_impact_review_queue and has_reviewed_vote_signals
                and int(published_accountability_claims.get("claims_total") or 0) > 0 and has_issue_reviews
                and int(issue_accountability_packets.get("issue_execution_owner_reviews_total") or 0) > 0
                else
                "candidate_identity_programs_boja_reviewed_votes_observed_responsibility_and_issue_direction_reviews"
                if has_program_measures and has_boja_impact_review_queue and has_reviewed_vote_signals
                and int(published_accountability_claims.get("claims_total") or 0) > 0 and has_issue_reviews
                else
                "candidate_identity_programs_boja_reviewed_votes_and_observed_responsibility_claims"
                if has_program_measures and has_boja_impact_review_queue and has_reviewed_vote_signals
                and int(published_accountability_claims.get("claims_total") or 0) > 0
                else
                "candidate_identity_programs_boja_queue_and_reviewed_vote_signals"
                if has_program_measures and has_boja_impact_review_queue and has_reviewed_vote_signals
                else
                "candidate_identity_declared_program_measures_parliament_and_boja_review_queues"
                if has_program_measures and has_boja_impact_review_queue and has_parliament_vote_review_queue
                else
                "candidate_identity_declared_program_measures_parliament_activity_and_boja_review_queue"
                if has_program_measures and has_boja_impact_review_queue and has_parliament_activity
                else
                "candidate_identity_declared_program_measures_and_boja_impact_review_queue"
                if has_program_measures and has_boja_impact_review_queue
                else
                "candidate_identity_declared_program_measures_and_boja_fragments"
                if has_program_measures and int(boja_report.get("fragments_total") or 0) > 0
                else
                "candidate_identity_declared_program_measures_and_boja_normative_records"
                if has_program_measures and int(boja_report.get("records_total") or 0) > 0
                else "candidate_identity_and_declared_program_measures"
                if has_program_measures
                else "candidate_identity_and_raw_programs"
                if has_program_text
                else "candidate_identity_only"
            ),
            "claim_rule": (
                "No merit, blame, policy direction, or real-world impact claim is published until "
                "it resolves to primary evidence rows or an explicit reviewed interpretation."
            ),
            "law_change_rule": (
                "Legal texts need article/fragment-level simplification plus direction-of-change review "
                "before a party/person value claim is shown."
            ),
            "press_rule": "Press/social allegations are lead generation only until matched to primary data.",
        },
        "estado_operativo": {
            "ahora": "Candidaturas oficiales parseadas, actores enlazados, programas 2026 descargados, medidas declaradas extraidas, primeros enlaces a ledger historico publicado, actividad legislativa oficial del Parlamento andaluz indexada con triaje de efecto legal, cola de revision de votos y primeras senales legislativas revisadas, BOJA oficial agrupado por bloque con fragmentos normativos y cola de revision de impacto, paquetes por issue que cruzan programa, votos revisados y BOJA revisado, claims observados de responsabilidad legislativa, primera revision de direccion/actor por issue sin scoring, y cola de fuentes oficiales para ejecucion/presupuesto/outcomes.",
            "vamos": "Convertir medidas programaticas, BOJA, Parlamento Andalucia, dinero y resultados en evidencia por issue.",
            "siguiente": "Ingerir fuentes candidatas de presupuesto, contratos, subvenciones e indicadores; luego resolver unidad ejecutora, ejecucion y outcome antes de atribuir responsabilidad regional.",
        },
        "db_report": db_report,
    }


def write_json(path: Path, payload: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def compact_review_questions(questions: Any) -> str:
    if not isinstance(questions, list):
        return ""
    out: list[str] = []
    for question in questions:
        if isinstance(question, dict):
            qid = clean_line(str(question.get("question_id") or "question"))
            text = clean_line(str(question.get("question") or ""))
            if text:
                out.append(f"{qid}: {text}")
        elif question:
            out.append(clean_line(str(question)))
    return " | ".join(out)


def impact_review_queue_csv_text(items: list[dict[str, Any]]) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(BOJA_IMPACT_REVIEW_QUEUE_CSV_COLUMNS), extrasaction="ignore")
    writer.writeheader()
    for item in items:
        row = {key: item.get(key, "") for key in BOJA_IMPACT_REVIEW_QUEUE_CSV_COLUMNS}
        row["review_questions"] = compact_review_questions(item.get("review_questions"))
        writer.writerow(row)
    return buffer.getvalue()


def parliament_vote_review_queue_csv_text(items: list[dict[str, Any]]) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(PARLIAMENT_VOTE_REVIEW_QUEUE_CSV_COLUMNS),
        extrasaction="ignore",
    )
    writer.writeheader()
    for item in items:
        row = {key: item.get(key, "") for key in PARLIAMENT_VOTE_REVIEW_QUEUE_CSV_COLUMNS}
        row["review_questions"] = compact_review_questions(item.get("review_questions"))
        writer.writerow(row)
    return buffer.getvalue()


def compact_execution_candidate_csv_rows(candidates: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for candidate in candidates[:6]:
        summary = first_non_empty(
            candidate,
            "summary",
            "budget_project",
            "indicator_name",
            "contract_object",
            "grant_finality",
            "grant_announcement",
            "treasury_hierarchy_3",
            "treasury_hierarchy_2",
            "activity_name",
            "program_name",
        )
        locator = str(candidate.get("source_locator") or "")
        amount = int(candidate.get("amount_eur") or 0)
        amount_suffix = f" ({amount} EUR)" if amount else ""
        parts.append(f"{locator}: {summary}{amount_suffix}".strip())
    return " | ".join(part for part in parts if part)


def compact_reviewed_execution_evidence_csv_rows(reviews: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for review in reviews[:3]:
        summary = first_non_empty(
            review,
            "reviewed_label",
            "summary",
            "budget_project",
            "indicator_name",
            "grant_finality",
            "grant_announcement",
            "treasury_hierarchy_3",
            "treasury_hierarchy_2",
            "program_name",
        )
        locator = str(review.get("source_locator") or "")
        status = str(review.get("review_status") or "")
        value = format_reviewed_execution_value(review)
        suffix = f" [{status}]" if status else ""
        value_suffix = f" ({value})" if value else ""
        parts.append(f"{locator}: {summary}{value_suffix}{suffix}".strip())
    return " | ".join(part for part in parts if part)


def format_reviewed_execution_value(row: dict[str, Any]) -> str:
    amount = int(row.get("amount_eur") or 0)
    if amount:
        return f"{amount} EUR"
    indicator_prevision = str(row.get("indicator_prevision") or "").strip()
    indicator_unit = str(row.get("indicator_unit") or "").strip()
    if indicator_prevision and indicator_unit:
        return f"{indicator_prevision} {indicator_unit}"
    return indicator_prevision


def execution_evidence_queue_csv_text(items: list[dict[str, Any]]) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(EXECUTION_EVIDENCE_QUEUE_CSV_COLUMNS),
        extrasaction="ignore",
    )
    writer.writeheader()
    for item in items:
        row = {key: item.get(key, "") for key in EXECUTION_EVIDENCE_QUEUE_CSV_COLUMNS}
        row["source_candidate_ids"] = "|".join(str(value) for value in item.get("source_candidate_ids") or [])
        row["source_urls"] = "|".join(
            str(source.get("source_url") or "")
            for source in item.get("source_candidates") or []
            if isinstance(source, dict) and source.get("source_url")
        )
        row["official_candidate_rows_total"] = int(item.get("official_candidate_rows_total") or 0)
        row["official_candidate_rows_by_source"] = "|".join(
            f"{source_id}:{total}"
            for source_id, total in sorted((item.get("official_candidate_rows_by_source") or {}).items())
        )
        row["top_official_candidate_rows"] = compact_execution_candidate_csv_rows(
            list(item.get("official_candidate_rows") or [])
        )
        row["reviewed_evidence_rows_total"] = int(item.get("reviewed_evidence_rows_total") or 0)
        row["top_reviewed_evidence_rows"] = compact_reviewed_execution_evidence_csv_rows(
            list(item.get("reviewed_evidence_rows") or [])
        )
        row["search_terms"] = "|".join(str(value) for value in item.get("search_terms") or [])
        row["open_gaps"] = "|".join(str(value) for value in item.get("open_gaps") or [])
        writer.writerow(row)
    return buffer.getvalue()


def write_impact_review_queue_csv(path: Path, items: list[dict[str, Any]]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = impact_review_queue_csv_text(items)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def write_parliament_vote_review_queue_csv(path: Path, items: list[dict[str, Any]]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = parliament_vote_review_queue_csv_text(items)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def write_execution_evidence_queue_csv(path: Path, items: list[dict[str, Any]]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = execution_evidence_queue_csv_text(items)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    args = parse_args()
    if args.from_text:
        candidature_text = Path(args.from_text).read_text(encoding="utf-8")
        candidature_source = {
            "source_id": "jec_andalucia_2026_candidaturas_proclamadas",
            "name": "Candidaturas proclamadas Andalucia 2026",
            "url": OFFICIAL_CANDIDATURE_PDF_URL,
            "boja_url": OFFICIAL_CANDIDATURE_BOJA_URL,
            "page_url": OFFICIAL_CANDIDATURE_PAGE_URL,
            "format": "pdftotext_fixture",
            "status": "from_text",
            "bytes": 0,
            "content_type": "text/plain",
            "content_sha256": sha256_bytes(candidature_text.encode("utf-8")),
            "raw_path": args.from_text,
            "source_verified": "Candidaturas proclamadas" in candidature_text,
            "error": "",
        }
    else:
        candidature_text, candidature_source = fetch_official_candidature_text(
            raw_dir=Path(args.raw_dir),
            timeout=args.timeout,
            no_network=bool(args.no_network),
            strict_network=bool(args.strict_network),
        )
    if not candidature_text:
        raise RuntimeError("No candidature text available; run without --no-network or pass --from-text")

    program_report = collect_program_sources(
        seed_path=Path(args.program_sources),
        raw_dir=Path(args.raw_dir),
        timeout=args.timeout,
        no_network=bool(args.no_network),
        strict_network=bool(args.strict_network),
    )
    boja_report = collect_boja_normative_sources(
        raw_dir=Path(args.raw_dir),
        timeout=args.timeout,
        no_network=bool(args.no_network),
        strict_network=bool(args.strict_network),
        date_from=str(args.boja_date_from),
        date_to=str(args.boja_date_to),
        api_size=int(args.boja_api_size),
        max_per_topic=int(args.boja_max_per_topic),
    )
    boja_impact_review_report = apply_boja_impact_reviews(
        boja_report,
        load_boja_impact_reviews(Path(args.boja_impact_reviews)),
    )
    parliament_report = collect_parlamento_andalucia_activity(
        raw_dir=Path(args.raw_dir),
        timeout=args.timeout,
        no_network=bool(args.no_network),
        strict_network=bool(args.strict_network),
        legislature=int(args.parliament_legislature),
    )
    parliament_vote_review_report = apply_parliament_vote_reviews(
        parliament_report,
        load_parliament_vote_reviews(Path(args.parliament_vote_reviews)),
    )
    issue_reviews_report = load_issue_reviews(Path(args.issue_reviews))
    execution_evidence_candidate_report = collect_execution_evidence_candidates(
        raw_dir=Path(args.execution_evidence_raw_dir),
        timeout=args.timeout,
        no_network=bool(args.no_network),
        strict_network=bool(args.strict_network),
        refresh_outcome_series=bool(args.refresh_outcome_series),
    )
    execution_evidence_review_report = load_execution_evidence_reviews(Path(args.execution_evidence_reviews))
    snapshot = build_snapshot(
        candidature_text=candidature_text,
        candidature_source=candidature_source,
        db_path=Path(args.db),
        source_catalog_path=Path(args.source_catalog),
        program_report=program_report,
        boja_report=boja_report,
        parliament_report=parliament_report,
        issue_reviews_report=issue_reviews_report,
        execution_evidence_candidate_report=execution_evidence_candidate_report,
        execution_evidence_review_report=execution_evidence_review_report,
        accountability_evidence_path=Path(args.accountability_evidence_api),
    )
    snapshot["parliament_vote_reviews"] = {
        key: value
        for key, value in parliament_vote_review_report.items()
        if key not in {"reviews_by_item_id", "reviews_by_event_id"}
    }
    snapshot["boja_impact_reviews"] = {
        key: value
        for key, value in boja_impact_review_report.items()
        if key != "reviews_by_item_id"
    }
    changed_out = write_json(Path(args.out), snapshot)
    changed_published = write_json(Path(args.published_out), snapshot) if args.published_out else False
    queue_items = list((snapshot.get("boja_norms") or {}).get("impact_review_queue") or [])
    changed_queue_out = (
        write_impact_review_queue_csv(Path(args.impact_review_queue_out), queue_items)
        if args.impact_review_queue_out
        else False
    )
    changed_published_queue = (
        write_impact_review_queue_csv(Path(args.published_impact_review_queue_out), queue_items)
        if args.published_impact_review_queue_out
        else False
    )
    parliament_vote_queue_items = list(
        (snapshot.get("parliament_activity") or {}).get("vote_impact_review_queue") or []
    )
    changed_parliament_vote_queue_out = (
        write_parliament_vote_review_queue_csv(
            Path(args.parliament_vote_review_queue_out),
            parliament_vote_queue_items,
        )
        if args.parliament_vote_review_queue_out
        else False
    )
    changed_published_parliament_vote_queue = (
        write_parliament_vote_review_queue_csv(
            Path(args.published_parliament_vote_review_queue_out),
            parliament_vote_queue_items,
        )
        if args.published_parliament_vote_review_queue_out
        else False
    )
    execution_evidence_queue_items = list(
        (snapshot.get("issue_execution_evidence_queue") or {}).get("queue") or []
    )
    changed_execution_evidence_queue_out = (
        write_execution_evidence_queue_csv(
            Path(args.execution_evidence_queue_out),
            execution_evidence_queue_items,
        )
        if args.execution_evidence_queue_out
        else False
    )
    changed_published_execution_evidence_queue = (
        write_execution_evidence_queue_csv(
            Path(args.published_execution_evidence_queue_out),
            execution_evidence_queue_items,
        )
        if args.published_execution_evidence_queue_out
        else False
    )
    print(
        "OK Andalucia 2026 accountability snapshot -> {out} ({out_state}), {pub} ({pub_state}), "
        "queue_csv={queue_out} ({queue_state}), queue_pub={queue_pub} ({queue_pub_state}); "
        "vote_queue_csv={vote_queue_out} ({vote_queue_state}), vote_queue_pub={vote_queue_pub} ({vote_queue_pub_state}); "
        "execution_queue_csv={execution_queue_out} ({execution_queue_state}), "
        "execution_queue_pub={execution_queue_pub} ({execution_queue_pub_state}); "
        "parties={parties} lists={lists} candidates={candidates} "
        "programs={programs}/{programs_total} measures={measures} parliament_initiatives={parliament_initiatives} "
        "vote_docs={vote_docs} vote_events={vote_events} boja_records={boja_records} "
        "review_queue={review_queue} review_batches={review_batches} "
        "vote_review_queue={vote_review_queue} vote_review_batches={vote_review_batches} "
        "execution_queue={execution_queue} execution_candidate_rows={execution_candidate_rows}".format(
            out=args.out,
            out_state="updated" if changed_out else "unchanged",
            pub=args.published_out or "no-published-out",
            pub_state="updated" if changed_published else "unchanged",
            queue_out=args.impact_review_queue_out or "no-queue-out",
            queue_state="updated" if changed_queue_out else "unchanged",
            queue_pub=args.published_impact_review_queue_out or "no-queue-published-out",
            queue_pub_state="updated" if changed_published_queue else "unchanged",
            vote_queue_out=args.parliament_vote_review_queue_out or "no-vote-queue-out",
            vote_queue_state="updated" if changed_parliament_vote_queue_out else "unchanged",
            vote_queue_pub=args.published_parliament_vote_review_queue_out or "no-vote-queue-published-out",
            vote_queue_pub_state="updated" if changed_published_parliament_vote_queue else "unchanged",
            execution_queue_out=args.execution_evidence_queue_out or "no-execution-queue-out",
            execution_queue_state="updated" if changed_execution_evidence_queue_out else "unchanged",
            execution_queue_pub=args.published_execution_evidence_queue_out or "no-execution-queue-published-out",
            execution_queue_pub_state="updated" if changed_published_execution_evidence_queue else "unchanged",
            parties=snapshot["coverage"]["distinct_party_keys_total"],
            lists=snapshot["coverage"]["candidate_lists_total"],
            candidates=snapshot["coverage"]["titular_candidates_total"]
            + snapshot["coverage"]["suplente_candidates_total"],
            programs=snapshot["coverage"]["program_sources_verified_total"],
            programs_total=snapshot["coverage"]["program_sources_total"],
            measures=snapshot["coverage"]["program_measures_total"],
            parliament_initiatives=snapshot["coverage"].get("parliament_andalucia_legislative_initiatives_total", 0),
            vote_docs=snapshot["coverage"].get("parliament_andalucia_voting_documents_total", 0),
            vote_events=snapshot["coverage"].get("parliament_andalucia_parsed_vote_events_total", 0),
            boja_records=(
                f"{snapshot['coverage']['boja_norms_records_total']}/"
                f"{snapshot['coverage'].get('boja_norms_fragments_total', 0)} fragments"
            ),
            review_queue=snapshot["coverage"].get("boja_norms_impact_review_items_total", 0),
            review_batches=snapshot["coverage"].get("boja_norms_impact_review_batches_total", 0),
            vote_review_queue=snapshot["coverage"].get("parliament_andalucia_vote_impact_review_items_total", 0),
            vote_review_batches=snapshot["coverage"].get("parliament_andalucia_vote_impact_review_batches_total", 0),
            execution_queue=snapshot["coverage"].get("issue_execution_evidence_queue_total", 0),
            execution_candidate_rows=snapshot["coverage"].get(
                "issue_execution_evidence_official_candidate_rows_total",
                0,
            ),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
