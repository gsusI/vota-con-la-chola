#!/usr/bin/env python3
"""Backfill time-aware initiative text versions and vote->text links.

This creates a minimal versioning layer for parliamentary initiatives so later
review queues can reason about "what text existed when this vote happened?"

Current scope:
- primary source: downloaded `parl_initiative_docs` rows
- preferred text snapshots: `doc_kind='bocg'`
- initial target: `congreso_iniciativas`
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json
from scripts.backfill_initiative_doc_excerpts import (
    extract_from_pdf,
    extract_from_xml_or_html,
    should_parse_as_pdf,
)


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_DOC_SOURCE_ID = "parl_initiative_docs"
DEFAULT_DOC_KIND = "bocg"
DEFAULT_INITIATIVE_SOURCE_IDS = "congreso_iniciativas"

SPANISH_MONTHS = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "setiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}

DATE_RE = re.compile(r"\b(\d{1,2})\s+de\s+([a-záéíóúü]+)\s+de\s+(\d{4})\b", re.IGNORECASE)
SLASH_DATE_RE = re.compile(r"\b(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{2,4})\b")
ABBR_DATE_RE = re.compile(r"\b(?P<day>\d{1,2})-(?P<month>[A-Za-zÁÉÍÓÚÜ]{3})-(?P<year>\d{2,4})\b")
DOC_CODE_RE = re.compile(r"/(?P<code>[^/?#]+?)(?:\.[A-Za-z0-9]+)?$")
CONGRESO_BOCG_RE = re.compile(
    r"BOCG-(?P<leg>\d+)-(?P<series>[A-Z])-(?P<doc_number>\d+)-(?P<version_order>\d+)$",
    re.IGNORECASE,
)
SENADO_GLOBAL_ENMIENDAS_RE = re.compile(
    r"^/(?P<legis>legis\d+)/expedientes/(?P<tipo>\d+)/enmiendas/global_enmiendas_vetos_\d+_(?P<num>\d{9})\.xml$",
    re.IGNORECASE,
)
SENADO_INI_XML_RE = re.compile(
    r"^/(?P<legis>legis\d+)/expedientes/(?P<tipo>\d+)/xml/INI-3-(?P<num>\d{9})\.xml$",
    re.IGNORECASE,
)
WS_RE = re.compile(r"\s+")

INTRO_VOTE_PREFIXES = (
    "debates de totalidad",
    "toma en consideración",
    "toma en consideracion",
)
SENADO_AMENDMENT_VOTE_PREFIXES = (
    "enmienda ",
    "enmiendas ",
    "propuesta de veto",
    "propuestas de veto",
)
SENADO_FINAL_VOTE_PREFIXES = (
    "votación final sobre el conjunto",
    "votacion final sobre el conjunto",
)
MONTH_ABBR = {
    "ene": "01",
    "feb": "02",
    "mar": "03",
    "abr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "ago": "08",
    "sep": "09",
    "set": "09",
    "oct": "10",
    "nov": "11",
    "dic": "12",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill initiative text versions")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--initiative-source-ids",
        default=DEFAULT_INITIATIVE_SOURCE_IDS,
        help="CSV of parl_initiatives.source_id values to include",
    )
    p.add_argument(
        "--initiative-id",
        action="append",
        default=[],
        help="Specific initiative_id to include (repeatable)",
    )
    p.add_argument("--doc-source-id", default=DEFAULT_DOC_SOURCE_ID, help="text_documents.source_id")
    p.add_argument("--doc-kind", default=DEFAULT_DOC_KIND, help="parl_initiative_documents.doc_kind")
    p.add_argument(
        "--only-vote-linked",
        action="store_true",
        help="Restrict to initiatives already linked in parl_vote_event_initiatives",
    )
    p.add_argument("--limit-initiatives", type=int, default=0, help="0 means no limit")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON summary output path")
    return p.parse_args()


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _parse_source_ids(raw: str) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").split(","):
        item = _norm(token)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)


def _doc_code_from_url(url: str) -> str:
    m = DOC_CODE_RE.search(_norm(url))
    return _norm(m.group("code")) if m else ""


def _parse_year_token(raw: str) -> str:
    token = _norm(raw)
    if not token.isdigit():
        return ""
    if len(token) == 4:
        return token
    if len(token) == 2:
        year = int(token)
        return str(1900 + year if year >= 80 else 2000 + year)
    return ""


def _senado_identity_from_url(url: str) -> dict[str, str] | None:
    token = _norm(url)
    if not token:
        return None
    parsed = urlparse(token)
    host = _norm(parsed.netloc).lower()
    if not host.endswith("senado.es"):
        return None
    path = _norm(parsed.path)
    m = SENADO_GLOBAL_ENMIENDAS_RE.match(path)
    if m:
        legis_token = _norm(m.group("legis"))
        leg_match = re.search(r"(\d+)$", legis_token)
        return {
            "family": "global_enmiendas_vetos",
            "legislature": _norm(leg_match.group(1) if leg_match else ""),
            "tipo": _norm(m.group("tipo")),
            "num": _norm(m.group("num")),
        }
    m = SENADO_INI_XML_RE.match(path)
    if m:
        legis_token = _norm(m.group("legis"))
        leg_match = re.search(r"(\d+)$", legis_token)
        return {
            "family": "ini_xml",
            "legislature": _norm(leg_match.group(1) if leg_match else ""),
            "tipo": _norm(m.group("tipo")),
            "num": _norm(m.group("num")),
        }
    qmap: dict[str, str] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        norm_key = _norm(key)
        if norm_key and norm_key not in qmap:
            qmap[norm_key] = _norm(value)
    if _norm(qmap.get("tipoFich")) == "3":
        legis = _norm(qmap.get("legis"))
        tipo = _norm(qmap.get("tipoEx"))
        num = _norm(qmap.get("numEx"))
        if legis.isdigit() and tipo.isdigit() and num.isdigit():
            return {
                "family": "tipoFich3",
                "legislature": legis,
                "tipo": tipo,
                "num": num.zfill(6),
            }
    return None


def _looks_like_senado_shell_excerpt(text: str) -> bool:
    lower = _normalize_excerpt(text).lower()
    if not lower:
        return False
    if "iniciativas parlamentarias | senado de espa" in lower:
        return True
    if "!function(" in lower and "boomerang" in lower:
        return True
    if lower.startswith("ir al contenido") and "preguntas frecuentes" in lower and "mapa web" in lower:
        return True
    return False


def _looks_like_senado_detail_excerpt(text: str, initiative_title: str) -> bool:
    lower = _normalize_excerpt(text).lower()
    if not lower:
        return False
    markers = 0
    for needle in (
        "autor:",
        "situación:",
        "situacion:",
        "fecha de presentación:",
        "fecha de presentacion:",
        "procedimiento:",
        "tramitación seguida",
        "tramitacion seguida",
        "calificación",
        "calificacion",
        "datos abiertos",
    ):
        if needle in lower:
            markers += 1
    title = _norm(initiative_title).lower()
    title_hit = bool(title and title in lower)
    return bool(markers >= 3 or (title_hit and markers >= 2))


def _normalize_excerpt(text: str) -> str:
    return WS_RE.sub(" ", _norm(text))


def _parse_published_date(text: str) -> str:
    normalized = _normalize_excerpt(text)
    m = DATE_RE.search(normalized)
    if m:
        day = f"{int(m.group(1)):02d}"
        month = SPANISH_MONTHS.get(_norm(m.group(2)).lower(), "")
        year = _norm(m.group(3))
        if month and year:
            return f"{year}-{month}-{day}"
    m = SLASH_DATE_RE.search(normalized)
    if m:
        year = _parse_year_token(m.group("year"))
        month = f"{int(m.group('month')):02d}"
        day = f"{int(m.group('day')):02d}"
        if year:
            return f"{year}-{month}-{day}"
    m = ABBR_DATE_RE.search(normalized)
    if m:
        year = _parse_year_token(m.group("year"))
        month = MONTH_ABBR.get(_norm(m.group("month")).lower()[:3], "")
        day = f"{int(m.group('day')):02d}"
        if year and month:
            return f"{year}-{month}-{day}"
    return ""


def _infer_chamber(url: str, initiative_source_id: str) -> str:
    lower = _norm(url).lower()
    init_src = _norm(initiative_source_id).lower()
    if "/cong/" in lower or init_src.startswith("congreso_"):
        return "congreso"
    if "/sen/" in lower or "senado" in lower or init_src.startswith("senado_"):
        return "senado"
    if "boe.es" in lower:
        return "boe"
    return "unknown"


def _extract_excerpt(doc_row: dict[str, Any]) -> str:
    raw_path = Path(_norm(doc_row.get("raw_path")))
    if raw_path.exists() and raw_path.is_file():
        raw_bytes = raw_path.read_bytes()
        if should_parse_as_pdf(_norm(doc_row.get("content_type")), raw_path):
            text = extract_from_pdf(raw_bytes, raw_path)
        else:
            text = extract_from_xml_or_html(raw_bytes)
        text = _norm(text)
        if text:
            return text[:6000]
    return _norm(doc_row.get("text_excerpt"))


def _infer_stage_kind(
    text: str,
    *,
    version_order: int,
    initiative_title: str,
    doc_url: str,
    chamber: str,
) -> tuple[str, str]:
    lower = _normalize_excerpt(text).lower()
    label = ""
    if chamber == "senado":
        senate_meta = _senado_identity_from_url(doc_url)
        if senate_meta:
            if _norm(senate_meta.get("family")) == "global_enmiendas_vetos":
                return ("senate_amendments", "Enmiendas y vetos del Senado")
            if _norm(senate_meta.get("family")) in {"ini_xml", "tipoFich3"}:
                return ("initial_text", "Texto inicial")
    if "acuerdo de derogación" in lower or "acuerdo de derogacion" in lower:
        return ("derogation_resolution", "Acuerdo de derogación")
    if "acuerdo de convalidación" in lower or "acuerdo de convalidacion" in lower:
        return ("convalidation_resolution", "Acuerdo de convalidación")
    if "enmiendas del senado" in lower or "enmiendas aprobadas por el senado" in lower:
        return ("senate_amendments", "Enmiendas del Senado")
    if "texto remitido por el senado" in lower:
        return ("senate_amendments", "Texto remitido por el Senado")
    if "dictamen de la comisión" in lower or "dictamen de la comision" in lower:
        return ("committee_report", "Dictamen de la comisión")
    if "informe de la ponencia" in lower:
        return ("committee_report", "Informe de la ponencia")
    if "texto final" in lower:
        return ("final_text", "Texto final")
    if "texto aprobado" in lower:
        return ("final_text", "Texto aprobado")
    if version_order <= 1 and (
        "proyecto de ley" in lower
        or "proposición de ley" in lower
        or "proposicion de ley" in lower
        or "resolución de" in lower
        or "resolucion de" in lower
        or _norm(initiative_title).lower().startswith("ley ")
    ):
        return ("initial_text", "Texto inicial")
    if version_order > 1:
        label = f"Versión {version_order}"
        return ("subsequent_text", label)
    return ("unknown", label or "Texto no clasificado")


def _version_sort_key(version: dict[str, Any]) -> tuple[str, int, str]:
    return (
        _norm(version.get("published_date")) or "9999-99-99",
        int(version.get("version_order") or 0),
        _norm(version.get("document_code")),
    )


def _stable_version_id(initiative_id: str, source_record_pk: int, doc_url: str) -> str:
    token = f"{_norm(initiative_id)}|{int(source_record_pk or 0)}|{_norm(doc_url)}"
    return "initver:" + sha256_bytes(token.encode("utf-8"))[:32]


def parse_doc_version_metadata(doc_row: dict[str, Any]) -> dict[str, Any] | None:
    doc_url = _norm(doc_row.get("doc_url"))
    initiative_id = _norm(doc_row.get("initiative_id"))
    source_record_pk = int(doc_row.get("source_record_pk") or 0)
    initiative_source_id = _norm(doc_row.get("initiative_source_id"))
    initiative_title = _norm(doc_row.get("initiative_title"))
    content_type = _norm(doc_row.get("content_type")).lower()
    excerpt = _extract_excerpt(doc_row)
    document_code = _doc_code_from_url(doc_url)
    chamber = _infer_chamber(doc_url, initiative_source_id)
    version_order = 0
    doc_series = ""
    doc_number = ""
    if chamber == "congreso":
        m = CONGRESO_BOCG_RE.search(document_code)
        if m:
            doc_series = _norm(m.group("series")).upper()
            doc_number = _norm(m.group("doc_number"))
            version_order = int(m.group("version_order") or 0)
    elif chamber == "senado":
        senate_meta = _senado_identity_from_url(doc_url)
        if senate_meta:
            family = _norm(senate_meta.get("family"))
            legislature = _norm(senate_meta.get("legislature"))
            tipo = _norm(senate_meta.get("tipo"))
            num = _norm(senate_meta.get("num"))
            if family == "tipoFich3" and (
                not excerpt
                or (
                    _looks_like_senado_shell_excerpt(excerpt)
                    and not _looks_like_senado_detail_excerpt(excerpt, initiative_title)
                )
            ):
                return None
            doc_series = tipo
            doc_number = num
            if family in {"ini_xml", "tipoFich3"}:
                document_code = f"SENADO-INI-3-{legislature}-{tipo}-{num}"
                version_order = 1
            elif family == "global_enmiendas_vetos":
                document_code = f"SENADO-ENMIENDAS-{legislature}-{tipo}-{num}"
                version_order = 2
    published_date = _parse_published_date(excerpt)
    stage_kind, stage_label = _infer_stage_kind(
        excerpt,
        version_order=version_order,
        initiative_title=initiative_title,
        doc_url=doc_url,
        chamber=chamber,
    )
    return {
        "initiative_text_version_id": _stable_version_id(initiative_id, source_record_pk, doc_url),
        "initiative_id": initiative_id,
        "chamber": chamber,
        "doc_kind": _norm(doc_row.get("doc_kind")),
        "document_code": document_code,
        "doc_series": doc_series,
        "doc_number": doc_number,
        "version_order": int(version_order or 0),
        "published_date": published_date,
        "stage_kind": stage_kind,
        "stage_label": stage_label,
        "source_id": _norm(doc_row.get("doc_source_id")),
        "source_url": doc_url,
        "source_record_pk": source_record_pk,
        "raw_payload_json": stable_json(
            {
                "initiative_source_id": initiative_source_id,
                "initiative_title": initiative_title,
                "text_excerpt_preview": excerpt[:800],
            }
        ),
    }


def choose_primary_version_for_vote(vote_row: dict[str, Any], versions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not versions:
        return None
    ordered = sorted(versions, key=_version_sort_key)
    title = _norm(vote_row.get("title")).lower()
    subgroup_title = _norm(vote_row.get("subgroup_title")).lower()
    subgroup_text = _norm(vote_row.get("subgroup_text")).lower()
    vote_label = " ".join((title, subgroup_title, subgroup_text)).strip()
    vote_date = _norm(vote_row.get("vote_date"))

    def _result(chosen: dict[str, Any], method: str, confidence: float) -> dict[str, Any]:
        return {
            "initiative_text_version_id": _norm(chosen["initiative_text_version_id"]),
            "link_method": method,
            "confidence": float(confidence),
            "raw_payload_json": stable_json(
                {
                    "vote_date": vote_date,
                    "vote_label": vote_label,
                    "chosen_stage_kind": _norm(chosen.get("stage_kind")),
                    "chosen_published_date": _norm(chosen.get("published_date")),
                    "versions_considered": len(ordered),
                }
            ),
        }

    def _latest_stage(stage_kinds: set[str]) -> dict[str, Any] | None:
        matches = [v for v in ordered if _norm(v.get("stage_kind")) in stage_kinds]
        return matches[-1] if matches else None

    if len(ordered) == 1:
        chosen = ordered[0]
        method = "single_version"
        confidence = 0.95 if _norm(chosen.get("published_date")) else 0.75
        return _result(chosen, method, confidence)

    if any(title.startswith(prefix) for prefix in INTRO_VOTE_PREFIXES):
        initial = next((v for v in ordered if _norm(v.get("stage_kind")) == "initial_text"), ordered[0])
        confidence = 0.95 if _norm(initial.get("stage_kind")) == "initial_text" else 0.8
        return _result(initial, "initial_version_for_intro_vote", confidence)

    if not title.startswith("enmiendas del senado") and any(title.startswith(prefix) for prefix in SENADO_AMENDMENT_VOTE_PREFIXES):
        amendments = _latest_stage({"senate_amendments"})
        if amendments:
            return _result(amendments, "latest_prior_stage_match", 0.93)

    if any(title.startswith(prefix) for prefix in SENADO_FINAL_VOTE_PREFIXES):
        final_like = _latest_stage({"senate_amendments", "final_text", "subsequent_text"})
        if final_like:
            return _result(final_like, "latest_prior_stage_match", 0.9)

    prior = [v for v in ordered if _norm(v.get("published_date")) and _norm(v.get("published_date")) <= vote_date]
    if prior:
        if "enmiendas del senado" in vote_label:
            senate_prior = [
                v
                for v in prior
                if _norm(v.get("stage_kind")) in {"senate_amendments", "final_text", "subsequent_text"}
            ]
            if senate_prior:
                return _result(senate_prior[-1], "latest_prior_stage_match", 0.9)
        chosen = prior[-1]
        method = "latest_prior_published_version"
        confidence = 0.88 if _norm(chosen.get("stage_kind")) != "unknown" else 0.82
        return _result(chosen, method, confidence)

    fallback = ordered[-1]
    return _result(fallback, "fallback_latest_version", 0.55)


def _fetch_doc_rows(
    conn: Any,
    *,
    initiative_source_ids: tuple[str, ...],
    initiative_ids: tuple[str, ...] = (),
    doc_source_id: str,
    doc_kind: str,
    only_vote_linked: bool,
    limit_initiatives: int,
) -> list[dict[str, Any]]:
    if not initiative_source_ids:
        return []
    marks = ",".join("?" for _ in initiative_source_ids)
    where = [f"i.source_id IN ({marks})", "d.doc_kind = ?"]
    params: list[Any] = [*initiative_source_ids, _norm(doc_kind)]
    if initiative_ids:
        id_marks = ",".join("?" for _ in initiative_ids)
        where.append(f"i.initiative_id IN ({id_marks})")
        params.extend(initiative_ids)
    if only_vote_linked:
        where.append("EXISTS (SELECT 1 FROM parl_vote_event_initiatives pvi WHERE pvi.initiative_id = i.initiative_id)")
    rows = conn.execute(
        f"""
        SELECT
          i.initiative_id,
          i.source_id AS initiative_source_id,
          i.title AS initiative_title,
          d.doc_kind,
          d.doc_url,
          d.source_record_pk,
          td.source_id AS doc_source_id,
          td.content_type,
          td.raw_path,
          td.text_excerpt
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        JOIN text_documents td
          ON td.source_record_pk = d.source_record_pk
         AND td.source_id = ?
        WHERE {' AND '.join(where)}
        ORDER BY i.initiative_id ASC, d.doc_url ASC
        """,
        [_norm(doc_source_id), *params],
    ).fetchall()
    out: list[dict[str, Any]] = []
    seen_inits: list[str] = []
    allowed: set[str] = set()
    limit_i = max(0, int(limit_initiatives or 0))
    for row in rows:
        initiative_id = _norm(row["initiative_id"])
        if limit_i > 0 and initiative_id not in allowed:
            if len(seen_inits) >= limit_i:
                continue
            seen_inits.append(initiative_id)
            allowed.add(initiative_id)
        out.append({key: row[key] for key in row.keys()})
    return out


def _fetch_votes_for_initiatives(conn: Any, initiative_ids: list[str]) -> list[dict[str, Any]]:
    if not initiative_ids:
        return []
    marks = ",".join("?" for _ in initiative_ids)
    rows = conn.execute(
        f"""
        SELECT
          pvi.initiative_id,
          pve.vote_event_id,
          pve.vote_date,
          pve.title,
          pve.subgroup_title,
          pve.subgroup_text
        FROM parl_vote_event_initiatives pvi
        JOIN parl_vote_events pve ON pve.vote_event_id = pvi.vote_event_id
        WHERE pvi.initiative_id IN ({marks})
        ORDER BY pvi.initiative_id ASC, pve.vote_date ASC, pve.vote_event_id ASC
        """,
        initiative_ids,
    ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def backfill_versions(
    conn: Any,
    *,
    initiative_source_ids: tuple[str, ...],
    initiative_ids: tuple[str, ...] = (),
    doc_source_id: str,
    doc_kind: str,
    only_vote_linked: bool,
    limit_initiatives: int,
    dry_run: bool,
) -> dict[str, Any]:
    doc_rows = _fetch_doc_rows(
        conn,
        initiative_source_ids=initiative_source_ids,
        initiative_ids=initiative_ids,
        doc_source_id=doc_source_id,
        doc_kind=doc_kind,
        only_vote_linked=only_vote_linked,
        limit_initiatives=limit_initiatives,
    )
    now_iso = now_utc_iso()
    version_rows: list[tuple[Any, ...]] = []
    versions_by_initiative: dict[str, list[dict[str, Any]]] = {}
    parsed_versions: list[dict[str, Any]] = []
    skipped_docs = 0

    for row in doc_rows:
        version = parse_doc_version_metadata(row)
        if version is None:
            skipped_docs += 1
            continue
        parsed_versions.append(version)
        versions_by_initiative.setdefault(_norm(version["initiative_id"]), []).append(version)
        version_rows.append(
            (
                _norm(version["initiative_text_version_id"]),
                _norm(version["initiative_id"]),
                _norm(version["chamber"]),
                _norm(version["doc_kind"]),
                _norm(version["document_code"]) or None,
                _norm(version["doc_series"]) or None,
                _norm(version["doc_number"]) or None,
                int(version["version_order"] or 0) or None,
                _norm(version["published_date"]) or None,
                _norm(version["stage_kind"]),
                _norm(version["stage_label"]) or None,
                _norm(version["source_id"]),
                _norm(version["source_url"]) or None,
                int(version["source_record_pk"] or 0) or None,
                _norm(version["raw_payload_json"]) or "{}",
                now_iso,
                now_iso,
            )
        )

    vote_rows = _fetch_votes_for_initiatives(conn, sorted(versions_by_initiative.keys()))
    vote_link_rows: list[tuple[Any, ...]] = []
    for vote in vote_rows:
        initiative_id = _norm(vote["initiative_id"])
        chosen = choose_primary_version_for_vote(vote, versions_by_initiative.get(initiative_id, []))
        if not chosen:
            continue
        vote_link_rows.append(
            (
                _norm(vote["vote_event_id"]),
                initiative_id,
                _norm(chosen["initiative_text_version_id"]),
                _norm(chosen["link_method"]),
                float(chosen["confidence"] or 0.0),
                1,
                _norm(chosen["raw_payload_json"]) or "{}",
                now_iso,
                now_iso,
            )
        )

    if not dry_run and version_rows:
        with conn:
            conn.executemany(
                """
                INSERT INTO parl_initiative_text_versions (
                  initiative_text_version_id, initiative_id, chamber, doc_kind,
                  document_code, doc_series, doc_number, version_order, published_date,
                  stage_kind, stage_label, source_id, source_url, source_record_pk,
                  raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(initiative_text_version_id) DO UPDATE SET
                  initiative_id = excluded.initiative_id,
                  chamber = excluded.chamber,
                  doc_kind = excluded.doc_kind,
                  document_code = excluded.document_code,
                  doc_series = excluded.doc_series,
                  doc_number = excluded.doc_number,
                  version_order = excluded.version_order,
                  published_date = excluded.published_date,
                  stage_kind = excluded.stage_kind,
                  stage_label = excluded.stage_label,
                  source_id = excluded.source_id,
                  source_url = excluded.source_url,
                  source_record_pk = excluded.source_record_pk,
                  raw_payload_json = excluded.raw_payload_json,
                  updated_at = excluded.updated_at
                """,
                version_rows,
            )
            if vote_link_rows:
                conn.executemany(
                    """
                    INSERT INTO parl_vote_event_text_versions (
                      vote_event_id, initiative_id, initiative_text_version_id,
                      link_method, confidence, is_primary, raw_payload_json,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(vote_event_id, initiative_id, is_primary) DO UPDATE SET
                      initiative_text_version_id = excluded.initiative_text_version_id,
                      link_method = excluded.link_method,
                      confidence = excluded.confidence,
                      raw_payload_json = excluded.raw_payload_json,
                      updated_at = excluded.updated_at
                    """,
                    vote_link_rows,
                )

    return {
        "initiative_source_ids": list(initiative_source_ids),
        "initiative_ids": list(initiative_ids),
        "doc_source_id": _norm(doc_source_id),
        "doc_kind": _norm(doc_kind),
        "dry_run": bool(dry_run),
        "initiatives_seen": len(versions_by_initiative),
        "docs_seen": len(doc_rows),
        "docs_skipped": int(skipped_docs),
        "versions_upserted": len(version_rows),
        "vote_links_upserted": len(vote_link_rows),
        "stage_kind_counts": {
            key: sum(1 for version in parsed_versions if _norm(version["stage_kind"]) == key)
            for key in sorted({_norm(version["stage_kind"]) for version in parsed_versions})
        },
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    initiative_source_ids = _parse_source_ids(args.initiative_source_ids)
    initiative_ids = tuple(_norm(value) for value in (args.initiative_id or ()) if _norm(value))
    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        summary = backfill_versions(
            conn,
            initiative_source_ids=initiative_source_ids,
            initiative_ids=initiative_ids,
            doc_source_id=_norm(args.doc_source_id) or DEFAULT_DOC_SOURCE_ID,
            doc_kind=_norm(args.doc_kind) or DEFAULT_DOC_KIND,
            only_vote_linked=bool(args.only_vote_linked),
            limit_initiatives=max(0, int(args.limit_initiatives or 0)),
            dry_run=bool(args.dry_run),
        )

    if _norm(args.out):
        out_path = Path(_norm(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
