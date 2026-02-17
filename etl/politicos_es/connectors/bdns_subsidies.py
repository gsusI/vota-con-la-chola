from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import (
    normalize_key_part,
    normalize_ws,
    now_utc_iso,
    parse_date_flexible,
    pick_value,
    sha256_bytes,
    stable_json,
)
from .base import BaseConnector


BDNS_BASE = "https://www.pap.hacienda.gob.es"


def _flatten_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("results", "items", "data", "convocatorias", "subvenciones", "rows"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        nested_lists = [v for v in data.values() if isinstance(v, list)]
        for candidate in nested_lists:
            dict_rows = [row for row in candidate if isinstance(row, dict)]
            if dict_rows:
                return dict_rows
        return [data]
    return []


def _canonical_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    absolute = urljoin(BDNS_BASE, raw_url.strip())
    parts = urlsplit(absolute)
    if not parts.netloc:
        return None
    scheme = "https" if parts.scheme.lower() in {"http", "https", ""} else parts.scheme.lower()
    return urlunsplit((scheme, parts.netloc.lower(), parts.path, parts.query, ""))


def _parse_datetime_iso(raw: str | None) -> str | None:
    if not raw:
        return None
    text = normalize_ws(raw)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    date_only = parse_date_flexible(text)
    if date_only:
        return f"{date_only}T00:00:00+00:00"
    return None


def _parse_decimal(raw_value: Any) -> float | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    token = normalize_ws(str(raw_value)).replace(" ", "")
    token = token.replace("EUR", "").replace("eur", "").replace("€", "").strip()
    if not token:
        return None
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        parts = token.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "." in token:
        parts = token.split(".")
        if not (len(parts) == 2 and len(parts[1]) <= 2):
            token = token.replace(".", "")
    try:
        return float(token)
    except ValueError:
        return None


def _normalize_token(raw: str | None) -> str:
    text = normalize_key_part(raw or "")
    return text.replace(" ", "_")


def build_source_record_id(record: dict[str, Any]) -> str:
    concesion_id = _normalize_token(str(record.get("concesion_id") or ""))
    convocatoria_id = _normalize_token(str(record.get("convocatoria_id") or ""))
    beneficiario_id = _normalize_token(str(record.get("beneficiario_id") or ""))
    beneficiario = _normalize_token(str(record.get("beneficiario") or ""))
    source_url = normalize_ws(str(record.get("source_url") or ""))
    amount = record.get("importe_eur")
    published = normalize_ws(str(record.get("published_at_iso") or ""))
    raw_fingerprint = sha256_bytes(stable_json(record.get("raw_row") or {}).encode("utf-8"))[:24]

    if concesion_id:
        return f"concesion:{concesion_id}"
    if convocatoria_id and beneficiario_id:
        return f"conv:{convocatoria_id}:benid:{beneficiario_id}"
    if convocatoria_id and beneficiario:
        return f"conv:{convocatoria_id}:ben:{beneficiario}"
    if convocatoria_id and amount is not None and published:
        amount_token = str(amount).replace(".", "_")
        return f"conv:{convocatoria_id}:amount:{amount_token}:date:{published[:10]}"
    if source_url:
        return f"url:{sha256_bytes(source_url.encode('utf-8'))[:24]}"
    return f"row:{raw_fingerprint}"


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        source_record_id = str(record.get("source_record_id") or "").strip()
        if not source_record_id:
            source_record_id = build_source_record_id(record)
            record = {**record, "source_record_id": source_record_id}
        current = by_id.get(source_record_id)
        if current is None:
            by_id[source_record_id] = dict(record)
            continue
        for key in (
            "source_url",
            "convocatoria_id",
            "concesion_id",
            "organo_convocante",
            "beneficiario",
            "beneficiario_id",
            "importe_eur",
            "published_at_iso",
            "summary_text",
        ):
            if current.get(key) in (None, "") and record.get(key) not in (None, ""):
                current[key] = record.get(key)
    return [by_id[key] for key in sorted(by_id)]


def parse_bdns_records(payload: bytes, *, feed_url: str, content_type: str | None) -> list[dict[str, Any]]:
    payload_sig = sha256_bytes(payload)
    if payload_looks_like_html(payload):
        raise RuntimeError(f"Respuesta HTML inesperada para BDNS feed (payload_sig={payload_sig})")

    try:
        parsed = json.loads(payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON invalido para BDNS ({exc}; payload_sig={payload_sig})") from exc

    rows = _flatten_rows(parsed)
    extracted: list[dict[str, Any]] = []
    for row in rows:
        source_url = _canonical_url(
            pick_value(
                row,
                (
                    "source_url",
                    "url",
                    "link",
                    "enlace",
                    "url_convocatoria",
                    "urlConvocatoria",
                    "url_detalle",
                    "urlDetalle",
                ),
            )
        )
        convocatoria_id = pick_value(
            row,
            (
                "convocatoria_id",
                "id_convocatoria",
                "idConvocatoria",
                "codigo_bdns",
                "codigoBDNS",
                "expediente",
                "codigo",
            ),
        )
        concesion_id = pick_value(
            row,
            (
                "concesion_id",
                "id_concesion",
                "idConcesion",
                "resolucion_id",
                "id",
            ),
        )
        beneficiario = pick_value(
            row,
            (
                "beneficiario",
                "beneficiario_nombre",
                "beneficiarioNombre",
                "nombre_beneficiario",
                "nombreBeneficiario",
                "beneficiary_name",
                "razon_social",
            ),
        )
        beneficiario_id = pick_value(
            row,
            (
                "beneficiario_id",
                "beneficiario_nif",
                "beneficiarioNif",
                "nif_beneficiario",
                "nifBeneficiario",
                "beneficiary_id",
                "cif",
                "nif",
            ),
        )
        organo_convocante = pick_value(
            row,
            (
                "organo_convocante",
                "organoConvocante",
                "organo_concedente",
                "organoConcedente",
                "unidad_tramitadora",
                "unidadTramitadora",
            ),
        )
        importe_eur = _parse_decimal(
            pick_value(
                row,
                (
                    "importe",
                    "importe_eur",
                    "importe_euros",
                    "importeConcedido",
                    "cuantia",
                    "amount",
                ),
            )
        )
        published_at_iso = _parse_datetime_iso(
            pick_value(
                row,
                (
                    "fecha_publicacion",
                    "fechaPublicacion",
                    "published_at",
                    "fecha_concesion",
                    "fechaConcesion",
                    "fecha",
                ),
            )
        )
        territory_code = pick_value(
            row,
            ("territory_code", "ccaa", "comunidad_autonoma", "comunidadAutonoma", "codigo_territorio"),
        )
        program_code = pick_value(row, ("programa", "program_code", "linea_subvencion", "lineaSubvencion"))

        record: dict[str, Any] = {
            "record_kind": "bdns_subsidy_record",
            "source_feed": "bdns_api",
            "feed_url": feed_url,
            "source_url": source_url,
            "convocatoria_id": convocatoria_id,
            "concesion_id": concesion_id,
            "organo_convocante": organo_convocante,
            "beneficiario": beneficiario,
            "beneficiario_id": beneficiario_id,
            "program_code": program_code,
            "territory_code": territory_code,
            "importe_eur": importe_eur,
            "currency": "EUR" if importe_eur is not None else None,
            "published_at_iso": published_at_iso,
            "summary_text": pick_value(row, ("descripcion", "objeto", "titulo", "title")),
            "raw_row": row,
        }
        record["source_record_id"] = build_source_record_id(record)
        extracted.append(record)

    records = _dedupe_records(extracted)
    if records:
        return records
    raise RuntimeError(f"No se encontraron registros parseables en BDNS ({payload_sig})")


class _BdnsBaseConnector(BaseConnector):
    ingest_mode = "source_records_only"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or SOURCE_CONFIG[self.source_id]["default_url"]

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        if from_file is not None:
            if from_file.is_dir():
                all_records: list[dict[str, Any]] = []
                for sample in sorted(from_file.glob("*.json")):
                    payload = sample.read_bytes()
                    all_records.extend(
                        parse_bdns_records(
                            payload,
                            feed_url=f"file://{sample.resolve()}",
                            content_type="application/json",
                        )
                    )
                records = _dedupe_records(all_records)
                if not records:
                    raise RuntimeError(f"No se encontraron JSON parseables en directorio BDNS: {from_file}")
                serialized = json.dumps(
                    {"source": f"{self.source_id}_dir", "dir": str(from_file), "records": records},
                    ensure_ascii=True,
                    sort_keys=True,
                ).encode("utf-8")
                fetched_at = now_utc_iso()
                raw_path = raw_output_path(raw_dir, self.source_id, "json")
                raw_path.write_bytes(serialized)
                return Extracted(
                    source_id=self.source_id,
                    source_url=f"file://{from_file.resolve()}",
                    resolved_url=f"file://{from_file.resolve()}",
                    fetched_at=fetched_at,
                    raw_path=raw_path,
                    content_sha256=sha256_bytes(serialized),
                    content_type="application/json",
                    bytes=len(serialized),
                    note="from-dir",
                    payload=serialized,
                    records=records,
                )

            resolved_url = f"file://{from_file.resolve()}"
            payload = from_file.read_bytes()
            records = parse_bdns_records(payload, feed_url=resolved_url, content_type="application/json")
            serialized = json.dumps(
                {"source": f"{self.source_id}_file", "file": str(from_file), "records": records},
                ensure_ascii=True,
                sort_keys=True,
            ).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(serialized)
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(serialized),
                content_type="application/json",
                bytes=len(serialized),
                note="from-file",
                payload=serialized,
                records=records,
            )

        resolved_url = self.resolve_url(url_override, timeout)
        try:
            payload, content_type = http_get_bytes(resolved_url, timeout)
            records = parse_bdns_records(payload, feed_url=resolved_url, content_type=content_type)
            serialized = json.dumps(
                {"source": f"{self.source_id}_network", "feed_url": resolved_url, "records": records},
                ensure_ascii=True,
                sort_keys=True,
            ).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(serialized)
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(serialized),
                content_type="application/json",
                bytes=len(serialized),
                note="network",
                payload=serialized,
                records=records,
            )
        except Exception as exc:  # noqa: BLE001
            if strict_network:
                raise
            fetched = fallback_payload_from_sample(
                self.source_id,
                raw_dir,
                note=f"network-error-fallback: {type(exc).__name__}: {exc}",
            )
            records = parse_bdns_records(
                fetched["payload"],
                feed_url=fetched["source_url"],
                content_type=fetched.get("content_type"),
            )
            return Extracted(
                source_id=self.source_id,
                source_url=fetched["source_url"],
                resolved_url=fetched["resolved_url"],
                fetched_at=fetched["fetched_at"],
                raw_path=fetched["raw_path"],
                content_sha256=fetched["content_sha256"],
                content_type=fetched["content_type"],
                bytes=fetched["bytes"],
                note=fetched.get("note", ""),
                payload=fetched["payload"],
                records=records,
            )

    def normalize(self, record: dict[str, Any], snapshot_date: str | None) -> dict[str, Any] | None:
        source_record_id = str(record.get("source_record_id") or "").strip()
        if not source_record_id:
            source_record_id = build_source_record_id(record)
        if not source_record_id:
            return None
        return {
            "source_record_id": source_record_id,
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }


class BdnsApiSubvencionesConnector(_BdnsBaseConnector):
    source_id = "bdns_api_subvenciones"


class BdnsAutonomicoConnector(_BdnsBaseConnector):
    source_id = "bdns_autonomico"

