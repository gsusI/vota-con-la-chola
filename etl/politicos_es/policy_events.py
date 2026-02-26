from __future__ import annotations

import json
import re
import sqlite3
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlsplit, urlunsplit
from typing import Any

from .http import http_get_bytes
from .raw import raw_output_path
from .util import (
    clean_text,
    normalize_key_part,
    normalize_ws,
    now_utc_iso,
    parse_date_flexible,
    sha256_bytes,
    stable_json,
)


MONCLOA_INSTRUMENTS: dict[str, tuple[str, str, str]] = {
    "moncloa_referencias": (
        "exec_reference",
        "Referencia del Consejo de Ministros",
        "Referencia oficial publicada por La Moncloa.",
    ),
    "moncloa_rss_referencias": (
        "exec_rss_reference",
        "RSS de referencias/resumenes del Consejo de Ministros",
        "Entrada RSS de La Moncloa relacionada con referencias o resumenes.",
    ),
}

BOE_INSTRUMENTS: dict[str, tuple[str, str, str]] = {
    "boe_legal_document": (
        "boe_legal_document",
        "Documento legal BOE",
        "Documento normativo o acto oficial publicado en BOE (referencia BOE-A/BOE-B/otros).",
    ),
    "boe_daily_summary": (
        "boe_daily_summary",
        "Sumario diario BOE",
        "Entrada de sumario diario del BOE (referencia BOE-S).",
    ),
}

BOE_REF_RE = re.compile(r"\b(BOE-[A-Z]-\d{4}-\d+)\b", flags=re.I)

MONEY_POLICY_INSTRUMENTS: dict[str, tuple[str, str, str]] = {
    "placsp_contratacion": (
        "public_contracting",
        "Contratacion publica",
        "Evento de contratacion publica derivado de PLACSP (licitacion/adjudicacion).",
    ),
    "bdns_subvenciones": (
        "public_subsidy",
        "Subvencion publica",
        "Evento de subvencion/ayuda publica derivado de BDNS/SNPSAP.",
    ),
}

PLACSP_SOURCE_IDS = ("placsp_sindicacion", "placsp_autonomico")
BDNS_SOURCE_IDS = ("bdns_api_subvenciones", "bdns_autonomico")
MONEY_SOURCE_IDS = PLACSP_SOURCE_IDS + BDNS_SOURCE_IDS
BDNS_BASE = "https://www.pap.hacienda.gob.es"
MONEY_DOMAIN_CANONICAL_KEY = "impuestos_gasto_fiscalidad"
PLACSP_DETAIL_BASE = "https://contrataciondelestado.es"


_POLICY_EVENT_DOMAIN_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sanidad_salud_publica", ("sanidad", "salud", "hospital", "vacuna", "vacun", "sistema sanitario")),
    ("educacion_capital_humano", ("educaci", "universidad", "colegio", "escol", "beca", "docente")),
    ("vivienda_urbanismo", ("vivienda", "alquiler", "hipotec", "saneamiento", "suelo", "urban")),
    ("justicia_seguridad", ("justicia", "seguridad", "polic", "fiscal", "penal", "juez", "fiscal")),
    ("energia_medio_ambiente", ("energia", "medio ambiente", "clim", "renovable", "emision", "CO2", "carbon")),
    ("infraestructura_transporte", ("transpor", "carretera", "ferrocarril", "tren", "metro", "puerto", "avi")),
    ("proteccion_social_pensiones", ("pension", "prestaci", "subsid", "renta", "familia", "infancia")),
    (
        "impuestos_gasto_fiscalidad",
        (
            "impuesto",
            "impuestos",
            "hacienda",
            "presupuest",
            "presupuesto",
            "subvenci",
            "contrat",
            "licit",
            "gasto",
        ),
    ),
    ("proteccion_social_pensiones", ("paro", "empleo", "desemple", "salario", "jubilac")),
)


def _normalize_domain_key(raw: Any) -> str | None:
    value = normalize_ws(str(raw or ""))
    return value.lower() if value else None


def _domain_id_by_canonical_key(
    conn: sqlite3.Connection,
    cache: dict[str, int | None],
    canonical_key: str | None,
) -> int | None:
    key = _normalize_domain_key(canonical_key)
    if key is None:
        return None
    if key in cache:
        return cache[key]
    row = conn.execute("SELECT domain_id FROM domains WHERE canonical_key = ?", (key,)).fetchone()
    value = int(row["domain_id"]) if row else None
    cache[key] = value
    return value


def _canonicalize_bdns_url(raw_url: str | None) -> str | None:
    if raw_url is None:
        return None
    text = str(raw_url).strip()
    if not text:
        return None
    absolute = urljoin(BDNS_BASE, text)
    parts = urlsplit(absolute)
    if not parts.netloc:
        return None
    scheme = "https" if not parts.scheme or parts.scheme.lower() == "" else "https" if parts.scheme.lower() == "http" else parts.scheme.lower()
    return urlunsplit((scheme, parts.netloc.lower(), parts.path, parts.query, ""))


def _infer_policy_event_domain_key(
    *,
    source_id: str,
    title: str,
    summary: str | None,
    source_url: str | None,
    raw_payload: dict[str, Any],
) -> str | None:
    source_id_norm = normalize_ws(source_id)
    if source_id_norm.startswith("placsp_") or source_id_norm.startswith("bdns_"):
        return MONEY_DOMAIN_CANONICAL_KEY

    candidates = " ".join(
        part for part in (title, source_id, source_url or "", str(raw_payload.get("summary_text") or ""), str(raw_payload.get("description") or ""))
        if part
    ).lower()
    for domain_key, hints in _POLICY_EVENT_DOMAIN_HINTS:
        for hint in hints:
            if hint.lower() in candidates:
                return domain_key
    return None


def _normalize_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def _normalize_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    token = str(value).strip()
    if not token:
        return None
    token = token.replace("EUR", "").replace("eur", "").replace("€", "").replace(" ", "")
    if not token:
        return None
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        parts = token.split(",")
        if len(parts) == 2 and len(parts[1]) <= 3:
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def _extract_source_url(payload: dict[str, Any]) -> str | None:
    for key in (
        "source_url",
        "source_url_raw",
        "url",
        "guid",
        "link",
        "feed_url",
        "url_detalle",
        "urlDetalle",
        "url_convocatoria",
        "urlConvocatoria",
    ):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _money_source_url_fallback(source_id: str, source_record_id: str, payload: dict[str, Any]) -> str | None:
    source_id_norm = normalize_ws(source_id)
    record_id = normalize_ws(source_record_id)
    if source_id_norm.startswith("bdns_"):
        convocatoria = normalize_ws(str(payload.get("convocatoria_id") or ""))
        concesion = normalize_ws(str(payload.get("concesion_id") or ""))
        explicit_url = _canonicalize_bdns_url(
            str(payload.get("source_url") or payload.get("urlConvocatoria") or payload.get("url_detalle") or payload.get("urlDetalle") or "")
        )
        if explicit_url:
            return explicit_url
        if convocatoria and concesion:
            return f"{BDNS_BASE}/bdnstrans/GE/es/concesiones/{quote_plus(concesion)}?convocatoria={quote_plus(convocatoria)}"
        if convocatoria:
            return f"{BDNS_BASE}/bdnstrans/GE/es/convocatorias/{quote_plus(convocatoria)}"
        if record_id:
            return f"{BDNS_BASE}/bdnstrans/GE/es/resultados?record_id={quote_plus(record_id)}"
    elif source_id_norm.startswith("placsp_"):
        expediente = normalize_ws(str(payload.get("expediente") or ""))
        if expediente:
            return f"urn:placsp:{expediente}"
        if record_id:
            return f"urn:placsp:record:{record_id}"
    elif record_id:
        return f"urn:{source_id_norm}:{record_id}"
    return None


def _canonicalize_placsp_url(raw_url: str | None) -> str | None:
    if raw_url is None:
        return None
    text = normalize_ws(str(raw_url))
    if not text:
        return None
    absolute = urljoin(PLACSP_DETAIL_BASE, text)
    parts = urlsplit(absolute)
    if not parts.netloc:
        return None
    scheme = (
        "https" if not parts.scheme or parts.scheme.lower() == "" else "https" if parts.scheme.lower() == "http" else parts.scheme.lower()
    )
    return urlunsplit((scheme, parts.netloc.lower(), parts.path, parts.query, ""))


def _decode_placsp_detail_html(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "charset=" in ct:
        encoding = ct.split("charset=", 1)[1].split(";", 1)[0].strip()
        if encoding:
            try:
                return payload.decode(encoding, errors="replace")
            except LookupError:
                pass
    return payload.decode("utf-8", errors="replace")


def _is_placsp_detail_blocked(html_text: str) -> bool:
    h = html_text.lower()
    if "web application firewall has denied your transaction" in h:
        return True
    if "you may want to clear the cookies in your browser" in h:
        return True
    if "<title>error</title>" in h and "web application firewall" in h:
        return True
    if "acceso denegado" in h and "contratacion" in h:
        return True
    return False


def _extract_dtdd_pairs(html_text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for key_html, value_html in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", html_text, flags=re.I | re.S):
        key_norm = normalize_key_part(clean_text(key_html))
        if not key_norm:
            continue
        value = normalize_ws(clean_text(value_html))
        if value and key_norm not in pairs:
            pairs[key_norm] = value
    return pairs


def _extract_key_value_lines(html_text: str) -> dict[str, str]:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", html_text)
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr|/td|/th)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    values: dict[str, str] = {}
    for line in text.splitlines():
        normalized = normalize_ws(unescape(line))
        if not normalized:
            continue
        match = re.match(r"^(?P<k>[^:]{2,120}?)\s*:\s*(?P<v>.+)$", normalized)
        if not match:
            continue
        key = normalize_key_part(unescape(match.group("k")))
        value = normalize_ws(unescape(match.group("v")))
        if key and value and key not in values:
            values[key] = value
    return values


def _extract_placsp_span_pairs(html_text: str) -> dict[str, str]:
    spans: list[tuple[str, str]] = []
    pairs: dict[str, str] = {}
    for match in re.finditer(r"<span\b[^>]*id=['\"]([^'\"]+)[\"'][^>]*>(.*?)</span>", html_text, flags=re.I | re.S):
        span_id = normalize_ws(str(match.group(1))).lower()
        span_text = normalize_ws(clean_text(match.group(2)))
        if not span_id or not span_text:
            continue
        spans.append((span_id, span_text))

    for index, (span_id, span_text) in enumerate(spans):
        if "label_" not in span_id:
            continue
        key = normalize_key_part(span_text)
        if not key or key in pairs:
            continue
        value: str | None = None
        for next_id, next_text in spans[index + 1 : index + 8]:
            if "label_" in next_id:
                break
            if "text_" not in next_id:
                continue
            if next_text:
                value = next_text
                break
        if value is not None:
            pairs[key] = value

    return pairs


def _extract_raw_text(html_text: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", html_text)
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr|/td|/th)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(text)


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        text = normalize_ws(str(value or ""))
        if text:
            return text
    return None


def _extract_labeled_value(mapping: dict[str, str], *needles: str) -> str | None:
    for needle in needles:
        value = mapping.get(normalize_key_part(needle))
        if value:
            return value
    for key, value in mapping.items():
        if not key or not value:
            continue
        for needle in needles:
            if normalize_key_part(needle) in key:
                return value
    return None


def _extract_cpv_from_text(value: str) -> tuple[str | None, str | None]:
    text = normalize_ws(value)
    if not text:
        return None, None
    match = re.search(r"\b(\d{8})\b(?:\s*[-–—]\s*(.+?))?(?:\s|$)", text)
    if not match:
        return None, None
    code = normalize_ws(match.group(1))
    label = normalize_ws(match.group(2) or "")
    return code, label if label else None


def _classify_placsp_doc_kind(label: str, doc_url: str) -> str:
    text = normalize_key_part(f"{label} {doc_url}")
    if "sello tiempo" in text or "sello" in text or "timestamp" in text:
        return "timestamp"
    if "acta" in text:
        return "minutes"
    if "pliego" in text:
        return "tender_documents"
    if "aviso" in text or "anuncio" in text or "licitacion" in text:
        return "notice"
    if "documento pdf" in text:
        return "document_pdf"
    if "documento html" in text:
        return "document_html"
    if "documento xml" in text:
        return "document_xml"
    if "notice" in text and "xml" in text:
        return "notice_xml"
    url_lower = doc_url.lower()
    if url_lower.endswith(".pdf"):
        return "document_pdf"
    if url_lower.endswith(".xml"):
        return "document_xml"
    if url_lower.endswith(".html") or url_lower.endswith(".htm"):
        return "document_html"
    if "document" in text:
        return "document"
    return "attachment"


def _extract_placsp_contract_detail_documents(html_text: str, source_url: str) -> list[dict[str, Any]]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, flags=re.I | re.S)
    docs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for row in rows:
        links = re.findall(r"<a[^>]*href=([\"'])(.*?)\1([^>]*)>(.*?)</a>", row, flags=re.I | re.S)
        if not links:
            continue
        cell_texts = [normalize_ws(clean_text(cell)) for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.I | re.S)]
        if not cell_texts:
            cell_texts = [normalize_ws(clean_text(cell)) for cell in re.split(r"<t[hd][^>]*>|</t[hd]>", row)]
        row_date: str | None = None
        for candidate in cell_texts:
            row_date = parse_date_flexible(candidate.replace("/", "-"))
            if row_date:
                break

        fallback_label = _first_non_empty(*cell_texts[1:])
        for _quote, href, attrs, anchor_label in links:
            if not href:
                continue
            href_norm = normalize_ws(str(href))
            if not href_norm or href_norm.lower().startswith("javascript:") or href_norm.lower().startswith("mailto:"):
                continue
            resolved = _canonicalize_placsp_url(href_norm)
            if not resolved:
                continue
            resolved_clean = resolved.rstrip("/")
            if resolved_clean in ("https://contrataciondelestado.es", "https://contrataciondelestado.es?"):
                continue
            anchor_text = normalize_ws(clean_text(anchor_label))
            title_match = re.search(r"\btitle\s*=\s*([\"'])(.*?)\1", attrs, flags=re.I | re.S)
            anchor_title = normalize_ws(title_match.group(2)) if title_match else None
            doc_label = _first_non_empty(fallback_label, anchor_title, anchor_text)
            if not doc_label:
                continue
            lowered = normalize_key_part(doc_label)
            if all(token not in lowered for token in ("document", "doc", "acta", "anuncio", "pliego", "sello", "pdf", "xml", "html", "adenda", "sello de tiempo", "timestamp")):
                continue
            kind = _classify_placsp_doc_kind(doc_label, resolved)
            doc_key = (str(source_url), resolved, kind)
            if doc_key in seen:
                continue
            seen.add(doc_key)
            docs.append(
                {
                    "source_url": resolved,
                    "doc_kind": kind,
                    "doc_label": doc_label,
                    "doc_reference_date": row_date,
                    "content_type_hint": None,
                    "doc_payload_json": stable_json({"anchor_text": anchor_text, "cells": [c for c in cell_texts if c]}),
                }
            )

    return docs


def parse_placsp_contract_detail_page(
    payload: bytes,
    *,
    source_url: str,
    content_type: str | None = None,
) -> dict[str, Any]:
    html_text = _decode_placsp_detail_html(payload, content_type)
    if _is_placsp_detail_blocked(html_text):
        raise RuntimeError(
            f"Detalle PLACSP bloqueado por WAF/cookies: {source_url}"
        )
    values = _extract_dtdd_pairs(html_text)
    values.update(_extract_key_value_lines(html_text))
    values.update(_extract_placsp_span_pairs(html_text))
    text_blob = normalize_ws(re.sub(r"\s+", " ", _extract_raw_text(html_text)))

    if not values:
        if "contrataciondelestado" in normalize_key_part(text_blob):
            raise RuntimeError(f"No se encontró estructura clave en detalle PLACSP: {source_url}")
        raise RuntimeError(f"Respuesta HTML sin campos parseables para detalle PLACSP: {source_url}")

    if "titulo" not in values and "subject of the contract" not in values:
        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.I | re.S)
        if title_match:
            values["subject of the contract"] = normalize_ws(clean_text(title_match.group(1)))

    file_number = _extract_labeled_value(
        values,
        "file",
        "numero de expediente",
        "numeroexpediente",
        "número de expediente",
        "file number",
        "file reference",
    )
    if not file_number:
        fallback_file = re.search(r"\b\d{4}/[A-Za-z0-9.-]+/\d+\b", text_blob)
        file_number = normalize_ws(fallback_file.group(0)) if fallback_file else None

    cpv_raw = _extract_labeled_value(values, "cpv", "cpv code", "codigo cpv")
    cpv_code = None
    cpv_label = None
    if cpv_raw:
        cpv_code, cpv_label = _extract_cpv_from_text(cpv_raw)
        if cpv_code is None:
            m = re.search(r"\b\d{8}\b", cpv_raw)
            if m:
                cpv_code = normalize_ws(m.group(0))

    if not cpv_code:
        cpv_raw_alt = re.search(r"\b\d{8}\b-\s*[^ \n]{3,}", text_blob)
        if cpv_raw_alt:
            cpv_code, cpv_label = _extract_cpv_from_text(cpv_raw_alt.group(0))

    base_budget = _normalize_amount(
        _extract_labeled_value(
            values,
            "base bidding budget without taxes",
            "base budget",
            "presupuesto base",
            "presupuesto base sin iva",
        )
    )
    estimated_value = _normalize_amount(
        _extract_labeled_value(
            values,
            "estimated value of the contract",
            "estimated value",
            "importe de adjudicacion",
            "importe estimado del contrato",
            "valor estimado del contrato",
        )
    )

    published_at = parse_date_flexible(
        _first_non_empty(
            _extract_labeled_value(values, "publication date", "fecha publicacion", "published"),
            _extract_labeled_value(values, "fecha publicacion", "anuncio", "posted"),
        )
        or ""
    )
    awarded_at = parse_date_flexible(
        _first_non_empty(
            _extract_labeled_value(values, "awarded date", "fecha adjudicacion", "fecha de adjudicacion", "fecha concesion"),
            _extract_labeled_value(values, "fecha de adjudicacion", "award date"),
        )
        or ""
    )
    submission_deadline = parse_date_flexible(
        _first_non_empty(
            _extract_labeled_value(values, "end date for submission of offers", "fecha limite de presentacion", "deadline", "fecha limite"),
            _extract_labeled_value(
                values,
                "fecha fin de presentacion de oferta",
                "fecha fin de presentacion",
                "fecha fin presentacion",
                "fin de presentacion",
            ),
        )
        or ""
    )

    documents = _extract_placsp_contract_detail_documents(html_text, source_url)

    detail_payload: dict[str, Any] = {
        "source_url": source_url,
        "file_number": file_number,
        "contract_id": _first_non_empty(_extract_labeled_value(values, "contract id", "id contrato"), file_number),
        "notice_type": _extract_labeled_value(values, "type of contract", "notice type", "tipo de contrato", "tipo"),
        "cpv_code": cpv_code,
        "cpv_label": cpv_label,
        "contracting_authority": _extract_labeled_value(
            values,
            "contracting party",
            "organo de contratacion",
            "entidad adjudicadora",
            "entidad contratante",
        ),
        "state": _extract_labeled_value(
            values,
            "state of the tender",
            "contracting state",
            "estado de la licitacion",
            "estado",
        ),
        "territory_code": _extract_labeled_value(
            values,
            "place of execution",
            "territory",
            "lugar de ejecucion",
            "lugar",
        ),
        "procedure_type": _extract_labeled_value(
            values,
            "procurement procedure",
            "procedimiento",
            "procedure",
        ),
        "processing_type": _extract_labeled_value(
            values,
            "processing type",
            "sistema de contratacion",
            "system of contracting",
        ),
        "method_of_presentation": _extract_labeled_value(
            values,
            "method of presenting the offer",
            "metodo de presentacion de la oferta",
            "metodo presentacion",
        ),
        "base_budget_eur": base_budget,
        "estimated_value_eur": estimated_value,
        "submission_deadline": submission_deadline,
        "published_at": published_at,
        "awarded_at": awarded_at,
        "tender_title": _first_non_empty(
            _extract_labeled_value(values, "subject of the contract", "asunto", "objeto", "titulo"),
            values.get("subject of the contract"),
        ),
        "raw_detail_text": text_blob,
        "documents": documents,
    }
    if not detail_payload["file_number"] and not detail_payload["contracting_authority"] and not detail_payload["cpv_code"] and not detail_payload["raw_detail_text"]:
        raise RuntimeError(f"No se pudo extraer detalle útil de PLACSP: {source_url}")
    return detail_payload


def _extract_boe_ref(payload: dict[str, Any], source_record_id: str) -> str | None:
    for candidate in (
        payload.get("boe_ref"),
        source_record_id,
        payload.get("title"),
        payload.get("description"),
        payload.get("source_url"),
        payload.get("source_url_raw"),
    ):
        if candidate is None:
            continue
        text = str(candidate).strip()
        if not text:
            continue
        match = BOE_REF_RE.search(text)
        if match:
            return str(match.group(1)).upper()
    return None


def ensure_money_policy_instruments(conn: sqlite3.Connection) -> dict[str, int]:
    now_iso = now_utc_iso()
    instrument_ids: dict[str, int] = {}
    for source_id, (code, label, description) in MONEY_POLICY_INSTRUMENTS.items():
        row = conn.execute(
            """
            INSERT INTO policy_instruments (code, label, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            RETURNING policy_instrument_id
            """,
            (code, label, description, now_iso, now_iso),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No se pudo resolver policy_instrument_id para {code}")
        instrument_ids[source_id] = int(row["policy_instrument_id"])
    return instrument_ids


def ensure_moncloa_policy_instruments(conn: sqlite3.Connection) -> dict[str, int]:
    now_iso = now_utc_iso()
    instrument_ids: dict[str, int] = {}
    for source_id, (code, label, description) in MONCLOA_INSTRUMENTS.items():
        row = conn.execute(
            """
            INSERT INTO policy_instruments (code, label, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            RETURNING policy_instrument_id
            """,
            (code, label, description, now_iso, now_iso),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No se pudo resolver policy_instrument_id para {code}")
        instrument_ids[source_id] = int(row["policy_instrument_id"])
    return instrument_ids


def ensure_boe_policy_instruments(conn: sqlite3.Connection) -> dict[str, int]:
    now_iso = now_utc_iso()
    instrument_ids: dict[str, int] = {}
    for key, (code, label, description) in BOE_INSTRUMENTS.items():
        row = conn.execute(
            """
            INSERT INTO policy_instruments (code, label, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            RETURNING policy_instrument_id
            """,
            (code, label, description, now_iso, now_iso),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"No se pudo resolver policy_instrument_id para {code}")
        instrument_ids[key] = int(row["policy_instrument_id"])
    return instrument_ids


def backfill_moncloa_policy_events(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = ("moncloa_referencias", "moncloa_rss_referencias"),
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    instruments = ensure_moncloa_policy_instruments(conn)

    stats: dict[str, Any] = {
        "sources": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "policy_events_upserted": 0,
        "policy_events_with_domain_id": 0,
        "policy_events_unresolved_domain": 0,
        "skips": [],
    }
    domain_cache: dict[str, int | None] = {}

    rows = conn.execute(
        f"""
        SELECT
          sr.source_record_pk,
          sr.source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.raw_payload
        FROM source_records sr
        WHERE sr.source_id IN ({",".join("?" for _ in source_ids)})
        ORDER BY sr.source_id, sr.source_record_id
        """,
        source_ids,
    ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_id = str(row["source_record_id"])
        source_record_pk = int(row["source_record_pk"])
        raw_payload = str(row["raw_payload"] or "")
        source_snapshot_date = row["source_snapshot_date"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        # Discovery index pages are not policy events.
        if source_record_id.endswith(":index.aspx"):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "discovery_index_row",
                }
            )
            continue

        source_url = _extract_source_url(payload)
        if not source_url:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "missing_source_url",
                }
            )
            continue

        # Rule: if event_date is not extractable reliably, keep published_date and leave event_date NULL.
        event_date = _normalize_iso_date(payload.get("event_date_iso"))
        published_date = _normalize_iso_date(payload.get("published_at_iso"))
        if published_date is None:
            published_date = event_date

        title = str(payload.get("title") or "").strip() or "Referencia Consejo de Ministros"
        summary_text = payload.get("summary_text")
        summary = str(summary_text).strip() if summary_text is not None else None
        if summary == "":
            summary = None

        policy_event_id = f"moncloa:{source_id}:{source_record_id}"
        instrument_id = instruments[source_id]
        conn.execute(
            """
            INSERT INTO policy_events (
              policy_event_id,
              event_date,
              published_date,
              domain_id,
              policy_instrument_id,
              title,
              summary,
              amount_eur,
              currency,
              institution_id,
              admin_level_id,
              territory_id,
              scope,
              source_id,
              source_url,
              source_record_pk,
              source_snapshot_date,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_event_id) DO UPDATE SET
              event_date=excluded.event_date,
              published_date=excluded.published_date,
              policy_instrument_id=excluded.policy_instrument_id,
              title=excluded.title,
              summary=excluded.summary,
              scope=excluded.scope,
              source_url=excluded.source_url,
              source_record_pk=excluded.source_record_pk,
              source_snapshot_date=excluded.source_snapshot_date,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                policy_event_id,
                event_date,
                published_date,
                instrument_id,
                title,
                summary,
                "ejecutivo",
                source_id,
                source_url,
                source_record_pk,
                source_snapshot_date,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["source_records_mapped"] += 1
        stats["policy_events_upserted"] += 1

    conn.commit()

    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({})".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    with_url_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({}) AND source_url IS NOT NULL AND trim(source_url) <> ''".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    null_event_with_published_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({}) AND event_date IS NULL AND published_date IS NOT NULL".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    stats["policy_events_total"] = int(total_row["c"] if total_row else 0)
    stats["policy_events_with_source_url"] = int(with_url_row["c"] if with_url_row else 0)
    stats["policy_events_null_event_date_with_published"] = int(
        null_event_with_published_row["c"] if null_event_with_published_row else 0
    )
    return stats


def backfill_money_policy_events(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = MONEY_SOURCE_IDS,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    instruments = ensure_money_policy_instruments(conn)

    stats: dict[str, Any] = {
        "sources": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "policy_events_upserted": 0,
        "policy_events_with_domain_id": 0,
        "policy_events_unresolved_domain": 0,
        "skips": [],
    }
    domain_cache: dict[str, int | None] = {}

    rows = conn.execute(
        f"""
        SELECT
          sr.source_record_pk,
          sr.source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.raw_payload
        FROM source_records sr
        WHERE sr.source_id IN ({",".join("?" for _ in source_ids)})
        ORDER BY sr.source_id, sr.source_record_id
        """,
        source_ids,
    ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_id = str(row["source_record_id"])
        source_record_pk = int(row["source_record_pk"])
        raw_payload = str(row["raw_payload"] or "")
        source_snapshot_date = row["source_snapshot_date"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        source_url = _extract_source_url(payload)
        if not source_url:
            source_url = _money_source_url_fallback(source_id, source_record_id, payload)

        if source_id in PLACSP_SOURCE_IDS:
            canonical_source_id = "placsp_contratacion"
            instrument_id = instruments[canonical_source_id]
            expediente = str(payload.get("expediente") or "").strip()
            organo = str(payload.get("organo_contratacion") or "").strip()
            cpv = str(payload.get("cpv") or "").strip()
            title = str(payload.get("title") or "").strip()
            if not title:
                title = f"Contratacion publica {expediente}".strip() if expediente else "Contratacion publica"
            summary_parts = [part for part in (organo, cpv) if part]
            summary = " | ".join(summary_parts) if summary_parts else None
            event_date = None
            published_date = _normalize_iso_date(payload.get("published_at_iso")) or _normalize_iso_date(
                source_snapshot_date
            )
            amount_eur = _normalize_amount(payload.get("amount_eur"))
            currency = str(payload.get("currency") or "").strip() or ("EUR" if amount_eur is not None else None)
            policy_event_id = f"money:placsp:{source_id}:{source_record_id}"
        elif source_id in BDNS_SOURCE_IDS:
            canonical_source_id = "bdns_subvenciones"
            instrument_id = instruments[canonical_source_id]
            convocatoria = str(payload.get("convocatoria_id") or "").strip()
            concesion = str(payload.get("concesion_id") or "").strip()
            beneficiario = str(payload.get("beneficiario") or "").strip()
            title = convocatoria or concesion or "Subvencion publica"
            if beneficiario:
                title = f"{title} - {beneficiario}"
            # Ambiguous causal timing -> keep event_date NULL and rely on published_date.
            event_date = None
            published_date = _normalize_iso_date(payload.get("published_at_iso")) or _normalize_iso_date(
                source_snapshot_date
            )
            amount_eur = _normalize_amount(payload.get("importe_eur"))
            currency = str(payload.get("currency") or "").strip() or ("EUR" if amount_eur is not None else None)
            summary = str(payload.get("organo_convocante") or "").strip() or None
            policy_event_id = f"money:bdns:{source_id}:{source_record_id}"
        else:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "unsupported_source_id",
                }
            )
            continue

        domain_key = _infer_policy_event_domain_key(
            source_id=source_id,
            title=title,
            summary=summary,
            source_url=source_url,
            raw_payload=payload,
        )
        domain_id = _domain_id_by_canonical_key(conn, domain_cache, domain_key)
        if domain_id is None:
            stats["policy_events_unresolved_domain"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "unresolved_domain",
                    "domain_key": domain_key,
                }
            )
        else:
            stats["policy_events_with_domain_id"] += 1

        conn.execute(
            """
            INSERT INTO policy_events (
              policy_event_id,
              event_date,
              published_date,
              domain_id,
              policy_instrument_id,
              title,
              summary,
              amount_eur,
              currency,
              institution_id,
              admin_level_id,
              territory_id,
              scope,
              source_id,
              source_url,
              source_record_pk,
              source_snapshot_date,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_event_id) DO UPDATE SET
              event_date=excluded.event_date,
              published_date=excluded.published_date,
              domain_id=excluded.domain_id,
              policy_instrument_id=excluded.policy_instrument_id,
              title=excluded.title,
              summary=excluded.summary,
              amount_eur=excluded.amount_eur,
              currency=excluded.currency,
              scope=excluded.scope,
              source_id=excluded.source_id,
              source_url=excluded.source_url,
              source_record_pk=excluded.source_record_pk,
              source_snapshot_date=excluded.source_snapshot_date,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                policy_event_id,
                event_date,
                published_date,
                domain_id,
                instrument_id,
                title,
                summary,
                amount_eur,
                currency,
                "dinero",
                canonical_source_id,
                source_url,
                source_record_pk,
                source_snapshot_date,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["source_records_mapped"] += 1
        stats["policy_events_upserted"] += 1

    conn.commit()

    canonical_sources = ("placsp_contratacion", "bdns_subvenciones")
    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN (?, ?)",
        canonical_sources,
    ).fetchone()
    with_url_row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM policy_events
        WHERE source_id IN (?, ?)
          AND source_url IS NOT NULL
          AND trim(source_url) <> ''
        """,
        canonical_sources,
    ).fetchone()
    with_pk_row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM policy_events
        WHERE source_id IN (?, ?)
          AND source_record_pk IS NOT NULL
        """,
        canonical_sources,
    ).fetchone()
    by_source_rows = conn.execute(
        """
        SELECT source_id, COUNT(*) AS c
        FROM policy_events
        WHERE source_id IN (?, ?)
        GROUP BY source_id
        ORDER BY source_id
        """,
        canonical_sources,
    ).fetchall()
    stats["policy_events_total"] = int(total_row["c"] if total_row else 0)
    stats["policy_events_with_source_url"] = int(with_url_row["c"] if with_url_row else 0)
    stats["policy_events_with_source_record_pk"] = int(with_pk_row["c"] if with_pk_row else 0)
    stats["policy_events_by_source"] = {str(row["source_id"]): int(row["c"]) for row in by_source_rows}
    return stats


def backfill_placsp_contract_details(
    conn: sqlite3.Connection,
    *,
    raw_dir: Path,
    source_ids: tuple[str, ...] = PLACSP_SOURCE_IDS,
    limit: int | None = None,
    only_missing: bool = False,
    strict_network: bool = False,
    timeout: int = 45,
    dry_run: bool = False,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    stats: dict[str, Any] = {
        "source_ids": list(source_ids),
        "source_records_seen": 0,
        "source_records_fetched": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "source_record_details_upserted": 0,
        "source_record_details_inserted": 0,
        "source_record_details_updated": 0,
        "documents_upserted": 0,
        "skips": [],
    }

    if not source_ids:
        raise ValueError("Debe indicar al menos un source_id")

    placeholders = ",".join("?" for _ in source_ids)
    if only_missing:
        rows = conn.execute(
            f"""
            SELECT
              sr.source_record_pk,
              sr.source_id,
              sr.source_record_id,
              sr.source_snapshot_date,
              sr.raw_payload
            FROM source_records sr
            WHERE sr.source_id IN ({placeholders})
              AND NOT EXISTS (
                SELECT 1
                FROM placsp_contract_detail_records pdr
                WHERE pdr.source_id = sr.source_id
                  AND pdr.source_record_pk = sr.source_record_pk
              )
            ORDER BY sr.source_id, sr.source_record_id
            """
            + (f" LIMIT {int(limit)}" if limit is not None and limit > 0 else "")
            ,
            source_ids,
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT
              sr.source_record_pk,
              sr.source_id,
              sr.source_record_id,
              sr.source_snapshot_date,
              sr.raw_payload
            FROM source_records sr
            WHERE sr.source_id IN ({placeholders})
            ORDER BY sr.source_id, sr.source_record_id
            """
            + (f" LIMIT {int(limit)}" if limit is not None and limit > 0 else ""),
            source_ids,
        ).fetchall()
    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_pk = int(row["source_record_pk"])
        source_record_id = str(row["source_record_id"])
        source_snapshot_date = row["source_snapshot_date"]
        raw_payload = str(row["raw_payload"] or "")

        if source_id not in PLACSP_SOURCE_IDS:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "unsupported_source_id",
                }
            )
            continue

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        raw_source_url = _extract_source_url(payload) or ""
        source_url = _canonicalize_placsp_url(raw_source_url)
        if not source_url:
            source_url = _money_source_url_fallback(source_id, source_record_id, payload)
            if not source_url:
                stats["source_records_skipped"] += 1
                stats["skips"].append(
                    {
                        "source_id": source_id,
                        "source_record_id": source_record_id,
                        "reason": "missing_source_url",
                    }
                )
                continue
        if not source_url.lower().startswith(("http://", "https://")):
            if strict_network:
                raise RuntimeError(f"Source URL no HTTP para detalle PLACSP: {source_url}")
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "source_url_not_http",
                }
            )
            continue

        if only_missing:
            existing = conn.execute(
                "SELECT 1 FROM placsp_contract_detail_records WHERE source_id = ? AND source_record_pk = ?",
                (source_id, source_record_pk),
            ).fetchone()
            if existing:
                stats["source_records_skipped"] += 1
                stats["skips"].append(
                    {
                        "source_id": source_id,
                        "source_record_id": source_record_id,
                        "reason": "already_had_detail",
                    }
                )
                continue

        try:
            detail_bytes, detail_ct = http_get_bytes(source_url, timeout=timeout)
            parsed = parse_placsp_contract_detail_page(
                detail_bytes,
                source_url=source_url,
                content_type=detail_ct,
            )
            stats["source_records_fetched"] += 1
        except Exception as exc:  # noqa: BLE001
            if strict_network:
                raise
            error_text = str(exc).lower()
            reason = "detail_fetch_or_parse_error"
            if "waf" in error_text or "blocked por waf" in error_text or "web application firewall" in error_text:
                reason = "detail_fetch_blocked"
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": reason,
                    "error": str(exc),
                }
            )
            continue

        detail_documents = parsed.pop("documents", [])
        detail_raw_payload = dict(parsed)
        detail_raw_payload["source_url"] = source_url
        detail_raw_payload["source_record_pk"] = source_record_pk
        detail_raw_payload["source_record_id"] = source_record_id
        normalized_detail_payload = stable_json(detail_raw_payload)
        detail_html_sha = sha256_bytes(detail_bytes)
        detail_raw_payload_path = raw_output_path(raw_dir, f"{source_id}_detail", "html")
        detail_raw_path = detail_raw_payload_path.with_name(
            f"{detail_raw_payload_path.stem}_{source_record_pk}_{detail_html_sha[:8]}.html"
        )
        detail_raw_path.parent.mkdir(parents=True, exist_ok=True)

        if not dry_run:
            detail_raw_path.write_bytes(detail_bytes)

            existed = conn.execute(
                "SELECT 1 FROM placsp_contract_detail_records WHERE source_id = ? AND source_record_pk = ?",
                (source_id, source_record_pk),
            ).fetchone()

            conn.execute(
                """
                INSERT INTO placsp_contract_detail_records (
                  source_id, source_record_pk, source_record_id, source_snapshot_date, source_url, source_url_raw,
                  file_number, contract_id, notice_type, cpv_code, cpv_label, contracting_authority, state,
                  territory_code, procedure_type, processing_type, method_of_presentation, submission_deadline,
                  base_budget_eur, estimated_value_eur, published_at, awarded_at, tender_title, raw_payload,
                  source_html_sha256, raw_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, source_record_pk) DO UPDATE SET
                  source_record_id=excluded.source_record_id,
                  source_snapshot_date=excluded.source_snapshot_date,
                  source_url=excluded.source_url,
                  source_url_raw=excluded.source_url_raw,
                  file_number=excluded.file_number,
                  contract_id=excluded.contract_id,
                  notice_type=excluded.notice_type,
                  cpv_code=excluded.cpv_code,
                  cpv_label=excluded.cpv_label,
                  contracting_authority=excluded.contracting_authority,
                  state=excluded.state,
                  territory_code=excluded.territory_code,
                  procedure_type=excluded.procedure_type,
                  processing_type=excluded.processing_type,
                  method_of_presentation=excluded.method_of_presentation,
                  submission_deadline=excluded.submission_deadline,
                  base_budget_eur=excluded.base_budget_eur,
                  estimated_value_eur=excluded.estimated_value_eur,
                  published_at=excluded.published_at,
                  awarded_at=excluded.awarded_at,
                  tender_title=excluded.tender_title,
                  raw_payload=excluded.raw_payload,
                  source_html_sha256=excluded.source_html_sha256,
                  raw_path=excluded.raw_path,
                  updated_at=excluded.updated_at
                """,
                (
                    source_id,
                    source_record_pk,
                    source_record_id,
                    source_snapshot_date,
                    source_url,
                    raw_source_url or None,
                    _first_non_empty(detail_raw_payload.get("file_number")),
                    _first_non_empty(detail_raw_payload.get("contract_id")),
                    normalize_ws(str(detail_raw_payload.get("notice_type") or "")) or None,
                    normalize_ws(str(detail_raw_payload.get("cpv_code") or "")) or None,
                    normalize_ws(str(detail_raw_payload.get("cpv_label") or "")) or None,
                    normalize_ws(str(detail_raw_payload.get("contracting_authority") or "")) or None,
                    normalize_ws(str(detail_raw_payload.get("state") or "")) or None,
                    normalize_ws(str(detail_raw_payload.get("territory_code") or "")) or None,
                    normalize_ws(str(detail_raw_payload.get("procedure_type") or "")) or None,
                    normalize_ws(str(detail_raw_payload.get("processing_type") or "")) or None,
                    normalize_ws(str(detail_raw_payload.get("method_of_presentation") or "")) or None,
                    detail_raw_payload.get("submission_deadline"),
                    detail_raw_payload.get("base_budget_eur"),
                    detail_raw_payload.get("estimated_value_eur"),
                    detail_raw_payload.get("published_at"),
                    detail_raw_payload.get("awarded_at"),
                    normalize_ws(str(detail_raw_payload.get("tender_title") or "")) or None,
                    normalized_detail_payload,
                    detail_html_sha,
                    str(detail_raw_path),
                    now_iso,
                    now_iso,
                ),
            )

            if detail_documents:
                doc_params: list[tuple[Any, ...]] = []
                for doc in detail_documents:
                    doc_url = _canonicalize_placsp_url(doc.get("source_url") or "")
                    if not doc_url:
                        continue
                    doc_params.append(
                        (
                            source_id,
                            source_record_pk,
                            doc_url,
                            source_record_id,
                            normalize_ws(str(doc.get("doc_kind") or "")) or None,
                            normalize_ws(str(doc.get("doc_label") or "")) or None,
                            doc.get("doc_reference_date"),
                            doc.get("content_type_hint"),
                            normalize_ws(str(doc.get("doc_payload_json") or "")) or "{}",
                            now_iso,
                            now_iso,
                        )
                    )
                if doc_params:
                    conn.executemany(
                        """
                        INSERT INTO placsp_contract_detail_documents (
                          source_id, source_record_pk, source_url, source_record_id,
                          doc_kind, doc_label, doc_reference_date, content_type_hint, doc_payload_json,
                          created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_record_pk, source_url, doc_kind) DO UPDATE SET
                          source_record_id=excluded.source_record_id,
                          doc_label=excluded.doc_label,
                          doc_reference_date=excluded.doc_reference_date,
                          content_type_hint=excluded.content_type_hint,
                          doc_payload_json=excluded.doc_payload_json,
                          updated_at=excluded.updated_at
                        """,
                        doc_params,
                    )
                    stats["documents_upserted"] += len(doc_params)

            if existed:
                stats["source_record_details_updated"] += 1
            else:
                stats["source_record_details_inserted"] += 1
            stats["source_record_details_upserted"] += 1

        stats["source_records_mapped"] += 1

    if not dry_run:
        conn.commit()
    return stats


def backfill_money_contract_records(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = PLACSP_SOURCE_IDS,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    stats: dict[str, Any] = {
        "source_ids": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "money_contract_records_upserted": 0,
        "money_contract_records_inserted": 0,
        "money_contract_records_updated": 0,
        "money_contract_records_with_detail": 0,
        "money_contract_records_amount_from_detail": 0,
        "skips": [],
    }

    placeholders = ",".join("?" for _ in source_ids)
    has_detail_join = False
    try:
        conn.execute("SELECT 1 FROM placsp_contract_detail_records LIMIT 1").fetchone()
        has_detail_join = True
    except sqlite3.OperationalError:
        has_detail_join = False

    if has_detail_join:
        rows = conn.execute(
            f"""
            SELECT
              sr.source_record_pk,
              sr.source_id,
              sr.source_record_id,
              sr.source_snapshot_date,
              sr.raw_payload,
              pdr.file_number,
              pdr.contract_id AS detail_contract_id,
              pdr.notice_type AS detail_notice_type,
              pdr.cpv_code AS detail_cpv_code,
              pdr.cpv_label AS detail_cpv_label,
              pdr.contracting_authority AS detail_contracting_authority,
              pdr.state AS detail_contract_state,
              pdr.territory_code AS detail_territory_code,
              pdr.procedure_type AS detail_procedure_type,
              pdr.processing_type AS detail_processing_type,
              pdr.method_of_presentation AS detail_method_of_presentation,
              pdr.base_budget_eur AS detail_base_budget_eur,
              pdr.estimated_value_eur AS detail_estimated_value_eur,
              pdr.published_at AS detail_published_at,
              pdr.awarded_at AS detail_awarded_at,
              pdr.tender_title AS detail_tender_title
            FROM source_records sr
            LEFT JOIN placsp_contract_detail_records pdr
              ON pdr.source_id = sr.source_id
             AND pdr.source_record_pk = sr.source_record_pk
            WHERE sr.source_id IN ({placeholders})
            ORDER BY sr.source_id, sr.source_record_id
            """,
            source_ids,
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT
              sr.source_record_pk,
              sr.source_id,
              sr.source_record_id,
              sr.source_snapshot_date,
              sr.raw_payload
            FROM source_records sr
            WHERE sr.source_id IN ({placeholders})
            ORDER BY sr.source_id, sr.source_record_id
            """,
            source_ids,
        ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_pk = int(row["source_record_pk"])
        source_record_id = str(row["source_record_id"])
        raw_payload = str(row["raw_payload"] or "")
        source_snapshot_date = row["source_snapshot_date"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        if source_id not in PLACSP_SOURCE_IDS:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "unsupported_source_id",
                }
            )
            continue

        source_url = _extract_source_url(payload)
        if not source_url:
            source_url = _money_source_url_fallback(source_id, source_record_id, payload)

        cpv_value = row["detail_cpv_code"] if has_detail_join else payload.get("cpv")
        if not cpv_value:
            cpv_value = payload.get("cpv")
        cpv_label = row["detail_cpv_label"] if has_detail_join else payload.get("cpv_label")

        if isinstance(cpv_value, list):
            cpv_codes = sorted(
                value
                for value in (
                    normalize_ws(str(value))
                    for value in cpv_value
                    if normalize_ws(str(value))
                )
            )
            cpv_code = ", ".join(cpv_codes)
        else:
            cpv_code = normalize_ws(str(cpv_value or ""))

        published_date = _normalize_iso_date(
            payload.get("published_at_iso")
            or payload.get("published_at")
            or row["detail_published_at"]
            or source_snapshot_date
        )
        awarded_date = _normalize_iso_date(payload.get("awarded_at_iso") or payload.get("awarded_date") or row["detail_awarded_at"])
        amount_from_detail = _first_non_empty(
            row["detail_estimated_value_eur"] if has_detail_join else None,
            row["detail_base_budget_eur"] if has_detail_join else None,
        )
        amount_eur = _normalize_amount(amount_from_detail)
        if amount_eur is None:
            amount_eur = _normalize_amount(payload.get("amount_eur"))
        if amount_eur is not None and amount_from_detail:
            stats["money_contract_records_amount_from_detail"] += 1

        contract_id = _first_non_empty(
            row["detail_contract_id"] if has_detail_join else None,
            row["file_number"] if has_detail_join else None,
            normalize_ws(str(payload.get("expediente") or "")),
        )
        lot_id = normalize_ws(str(payload.get("lot_id") or "")) or None
        notice_type = _first_non_empty(
            row["detail_notice_type"] if has_detail_join else None,
            normalize_ws(str(payload.get("notice_type") or "")),
        )
        contracting_authority = _first_non_empty(
            row["detail_contracting_authority"] if has_detail_join else None,
            normalize_ws(str(payload.get("organo_contratacion") or "")),
        )
        procedure_type = _first_non_empty(
            row["detail_procedure_type"] if has_detail_join else None,
            normalize_ws(str(payload.get("procedure_type") or "")),
        )
        territory_code = _first_non_empty(
            row["detail_territory_code"] if has_detail_join else None,
            normalize_ws(str(payload.get("territory_code") or "")),
        )
        if has_detail_join and any(
            value is not None for value in (
                row["detail_contracting_authority"],
                row["detail_cpv_code"],
                row["detail_procedure_type"],
                row["detail_tender_title"],
            )
        ):
            stats["money_contract_records_with_detail"] += 1

        currency = normalize_ws(str(payload.get("currency") or ""))
        if not currency:
            currency = "EUR" if amount_eur is not None else None

        existed = conn.execute(
            "SELECT 1 FROM money_contract_records WHERE source_id = ? AND source_record_pk = ?",
            (source_id, source_record_pk),
        ).fetchone()

        conn.execute(
            """
            INSERT INTO money_contract_records (
              source_id, source_record_pk, source_record_id, source_snapshot_date, source_url, contract_id, lot_id,
              notice_type, cpv_code, cpv_label, contracting_authority, procedure_type, territory_code,
              published_date, awarded_date, amount_eur, currency, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, source_record_pk) DO UPDATE SET
              source_record_id=excluded.source_record_id,
              source_snapshot_date=excluded.source_snapshot_date,
              source_url=excluded.source_url,
              contract_id=excluded.contract_id,
              lot_id=excluded.lot_id,
              notice_type=excluded.notice_type,
              cpv_code=excluded.cpv_code,
              cpv_label=excluded.cpv_label,
              contracting_authority=excluded.contracting_authority,
              procedure_type=excluded.procedure_type,
              territory_code=excluded.territory_code,
              published_date=excluded.published_date,
              awarded_date=excluded.awarded_date,
              amount_eur=excluded.amount_eur,
              currency=excluded.currency,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                source_id,
                source_record_pk,
                source_record_id,
                source_snapshot_date,
                source_url,
                contract_id,
                lot_id,
                notice_type,
                cpv_code,
                normalize_ws(str(cpv_label or "")) or None,
                contracting_authority,
                procedure_type,
                territory_code,
                published_date,
                awarded_date,
                amount_eur,
                currency,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["source_records_mapped"] += 1
        stats["money_contract_records_upserted"] += 1
        if existed:
            stats["money_contract_records_updated"] += 1
        else:
            stats["money_contract_records_inserted"] += 1

    conn.commit()

    total_row = conn.execute(
        f"SELECT COUNT(*) AS c FROM money_contract_records WHERE source_id IN ({placeholders})",
        source_ids,
    ).fetchone()
    with_url_row = conn.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM money_contract_records
        WHERE source_id IN ({placeholders})
          AND source_url IS NOT NULL
          AND trim(source_url) <> ''
        """,
        source_ids,
    ).fetchone()
    stats["money_contract_records_total"] = int(total_row["c"] if total_row else 0)
    stats["money_contract_records_with_source_url"] = int(with_url_row["c"] if with_url_row else 0)
    return stats


def backfill_money_subsidy_records(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = BDNS_SOURCE_IDS,
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    stats: dict[str, Any] = {
        "source_ids": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "money_subsidy_records_upserted": 0,
        "money_subsidy_records_inserted": 0,
        "money_subsidy_records_updated": 0,
        "skips": [],
    }

    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"""
        SELECT
          sr.source_record_pk,
          sr.source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.raw_payload
        FROM source_records sr
        WHERE sr.source_id IN ({placeholders})
        ORDER BY sr.source_id, sr.source_record_id
        """,
        source_ids,
    ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_pk = int(row["source_record_pk"])
        source_record_id = str(row["source_record_id"])
        raw_payload = str(row["raw_payload"] or "")
        source_snapshot_date = row["source_snapshot_date"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        if source_id not in BDNS_SOURCE_IDS:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "unsupported_source_id",
                }
            )
            continue

        source_url = _extract_source_url(payload)
        if not source_url:
            source_url = _money_source_url_fallback(source_id, source_record_id, payload)

        published_date = _normalize_iso_date(
            payload.get("published_at_iso")
            or payload.get("fecha_publicacion")
            or payload.get("published_at")
        )
        concession_date = _normalize_iso_date(payload.get("concession_date") or payload.get("fecha_concesion"))
        amount_eur = _normalize_amount(payload.get("importe_eur") or payload.get("importe"))
        currency = normalize_ws(str(payload.get("currency") or payload.get("moneda") or ""))
        if not currency and amount_eur is not None:
            currency = "EUR"

        existed = conn.execute(
            "SELECT 1 FROM money_subsidy_records WHERE source_id = ? AND source_record_pk = ?",
            (source_id, source_record_pk),
        ).fetchone()

        conn.execute(
            """
            INSERT INTO money_subsidy_records (
              source_id, source_record_pk, source_record_id, source_snapshot_date, source_url,
              call_id, grant_id, granting_body, beneficiary_name, beneficiary_identifier, program_code,
              territory_code, published_date, concession_date, amount_eur, currency, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, source_record_pk) DO UPDATE SET
              source_record_id=excluded.source_record_id,
              source_snapshot_date=excluded.source_snapshot_date,
              source_url=excluded.source_url,
              call_id=excluded.call_id,
              grant_id=excluded.grant_id,
              granting_body=excluded.granting_body,
              beneficiary_name=excluded.beneficiary_name,
              beneficiary_identifier=excluded.beneficiary_identifier,
              program_code=excluded.program_code,
              territory_code=excluded.territory_code,
              published_date=excluded.published_date,
              concession_date=excluded.concession_date,
              amount_eur=excluded.amount_eur,
              currency=excluded.currency,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                source_id,
                source_record_pk,
                source_record_id,
                source_snapshot_date,
                source_url,
                normalize_ws(str(payload.get("convocatoria_id") or "")) or None,
                normalize_ws(str(payload.get("concesion_id") or "")) or None,
                normalize_ws(str(payload.get("organo_convocante") or "")) or None,
                normalize_ws(str(payload.get("beneficiario") or "")) or None,
                normalize_ws(str(payload.get("beneficiario_id") or "")) or None,
                normalize_ws(str(payload.get("program_code") or "")) or None,
                normalize_ws(str(payload.get("territory_code") or "")) or None,
                published_date,
                concession_date,
                amount_eur,
                currency or None,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["source_records_mapped"] += 1
        stats["money_subsidy_records_upserted"] += 1
        if existed:
            stats["money_subsidy_records_updated"] += 1
        else:
            stats["money_subsidy_records_inserted"] += 1

    conn.commit()

    total_row = conn.execute(
        f"SELECT COUNT(*) AS c FROM money_subsidy_records WHERE source_id IN ({placeholders})",
        source_ids,
    ).fetchone()
    with_url_row = conn.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM money_subsidy_records
        WHERE source_id IN ({placeholders})
          AND source_url IS NOT NULL
          AND trim(source_url) <> ''
        """,
        source_ids,
    ).fetchone()
    stats["money_subsidy_records_total"] = int(total_row["c"] if total_row else 0)
    stats["money_subsidy_records_with_source_url"] = int(with_url_row["c"] if with_url_row else 0)
    return stats


def backfill_money_staging(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = MONEY_SOURCE_IDS,
) -> dict[str, Any]:
    source_contract_ids = tuple(value for value in source_ids if value in PLACSP_SOURCE_IDS)
    source_subsidy_ids = tuple(value for value in source_ids if value in BDNS_SOURCE_IDS)
    source_unknown_ids = tuple(
        value for value in source_ids if value not in PLACSP_SOURCE_IDS and value not in BDNS_SOURCE_IDS
    )
    if source_unknown_ids:
        raise ValueError(f"unsupported source_ids for money staging: {', '.join(source_unknown_ids)}")

    result: dict[str, Any] = {
        "sources": list(source_ids),
        "contracts": {},
        "subsidies": {},
    }
    if source_contract_ids:
        result["contracts"] = backfill_money_contract_records(conn, source_ids=source_contract_ids)
    if source_subsidy_ids:
        result["subsidies"] = backfill_money_subsidy_records(conn, source_ids=source_subsidy_ids)
    return result


def backfill_boe_policy_events(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] = ("boe_api_legal",),
) -> dict[str, Any]:
    now_iso = now_utc_iso()
    instruments = ensure_boe_policy_instruments(conn)

    stats: dict[str, Any] = {
        "sources": list(source_ids),
        "source_records_seen": 0,
        "source_records_mapped": 0,
        "source_records_skipped": 0,
        "policy_events_upserted": 0,
        "skips": [],
    }

    rows = conn.execute(
        f"""
        SELECT
          sr.source_record_pk,
          sr.source_id,
          sr.source_record_id,
          sr.source_snapshot_date,
          sr.raw_payload
        FROM source_records sr
        WHERE sr.source_id IN ({",".join("?" for _ in source_ids)})
        ORDER BY sr.source_id, sr.source_record_id
        """,
        source_ids,
    ).fetchall()

    for row in rows:
        stats["source_records_seen"] += 1
        source_id = str(row["source_id"])
        source_record_id = str(row["source_record_id"])
        source_record_pk = int(row["source_record_pk"])
        raw_payload = str(row["raw_payload"] or "")
        source_snapshot_date = row["source_snapshot_date"]
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "invalid_json_payload",
                }
            )
            continue
        if not isinstance(payload, dict):
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "payload_not_object",
                }
            )
            continue

        source_url = _extract_source_url(payload)
        if not source_url:
            stats["source_records_skipped"] += 1
            stats["skips"].append(
                {
                    "source_id": source_id,
                    "source_record_id": source_record_id,
                    "reason": "missing_source_url",
                }
            )
            continue

        boe_ref = _extract_boe_ref(payload, source_record_id) or ""
        title = str(payload.get("title") or "").strip() or (boe_ref or "Documento BOE")
        description = payload.get("description")
        summary = str(description).strip() if description is not None else None
        if summary == "":
            summary = None

        # Rule: keep event_date NULL for BOE feed rows unless a future deterministic
        # event-date contract is added. published_date remains the corroboration date.
        event_date = None
        published_date = _normalize_iso_date(payload.get("published_at_iso"))
        if published_date is None:
            published_date = _normalize_iso_date(source_snapshot_date)

        if boe_ref.startswith("BOE-S-") or "sumario" in title.lower():
            instrument_id = instruments["boe_daily_summary"]
        else:
            instrument_id = instruments["boe_legal_document"]

        id_suffix = boe_ref or source_record_id
        policy_event_id = f"boe:{source_id}:{id_suffix}"
        conn.execute(
            """
            INSERT INTO policy_events (
              policy_event_id,
              event_date,
              published_date,
              domain_id,
              policy_instrument_id,
              title,
              summary,
              amount_eur,
              currency,
              institution_id,
              admin_level_id,
              territory_id,
              scope,
              source_id,
              source_url,
              source_record_pk,
              source_snapshot_date,
              raw_payload,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_event_id) DO UPDATE SET
              event_date=excluded.event_date,
              published_date=excluded.published_date,
              policy_instrument_id=excluded.policy_instrument_id,
              title=excluded.title,
              summary=excluded.summary,
              scope=excluded.scope,
              source_url=excluded.source_url,
              source_record_pk=excluded.source_record_pk,
              source_snapshot_date=excluded.source_snapshot_date,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                policy_event_id,
                event_date,
                published_date,
                instrument_id,
                title,
                summary,
                "legal",
                source_id,
                source_url,
                source_record_pk,
                source_snapshot_date,
                raw_payload,
                now_iso,
                now_iso,
            ),
        )
        stats["source_records_mapped"] += 1
        stats["policy_events_upserted"] += 1

    conn.commit()

    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({})".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    with_url_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({}) AND source_url IS NOT NULL AND trim(source_url) <> ''".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    null_event_with_published_row = conn.execute(
        "SELECT COUNT(*) AS c FROM policy_events WHERE source_id IN ({}) AND event_date IS NULL AND published_date IS NOT NULL".format(
            ",".join("?" for _ in source_ids)
        ),
        source_ids,
    ).fetchone()
    stats["policy_events_total"] = int(total_row["c"] if total_row else 0)
    stats["policy_events_with_source_url"] = int(with_url_row["c"] if with_url_row else 0)
    stats["policy_events_null_event_date_with_published"] = int(
        null_event_with_published_row["c"] if null_event_with_published_row else 0
    )
    return stats
