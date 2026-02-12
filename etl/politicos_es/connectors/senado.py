from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..fetch import fetch_payload
from ..http import http_get_bytes, validate_network_payload
from ..parsers import parse_csv_source
from ..raw import fallback_payload_from_sample, raw_output_path
from ..types import Extracted
from ..util import (
    clean_text,
    normalize_ws,
    now_utc_iso,
    parse_date_flexible,
    pick_value,
    sha256_bytes,
    stable_json,
    split_spanish_name,
)
from .base import BaseConnector


SENADO_GRUPOS_URL = "https://www.senado.es/web/ficopendataservlet?tipoFich=4&legis=15"
SENADO_FICHA_GRUPO_URL_TEMPLATE = (
    "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=2&cod={group_code}"
)
SENADO_FICHA_SENADOR_URL_TEMPLATE = (
    "https://www.senado.es/web/ficopendataservlet?tipoFich=1&cod={idweb}&legis=15"
)
SENADO_MONTHS = {
    "ENE": "01",
    "FEB": "02",
    "MAR": "03",
    "ABR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AGO": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DIC": "12",
}


def parse_senado_date(value: str | None) -> str | None:
    if not value:
        return None
    text = clean_text(value)
    if not text:
        return None
    direct = parse_date_flexible(text)
    if direct:
        return direct

    upper = text.upper()
    match = re.search(r"(\d{1,2})-([A-Z]{3})-(\d{4})", upper)
    if match:
        day = int(match.group(1))
        month = SENADO_MONTHS.get(match.group(2))
        year = int(match.group(3))
        if month:
            return f"{year:04d}-{month}-{day:02d}"

    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def extract_senado_procedencia(value: str | None) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if ":" in text:
        text = text.split(":", 1)[1]
    return normalize_ws(text.rstrip("."))


def parse_senado_group_codes(payload: bytes) -> list[str]:
    root = ET.fromstring(payload)
    codes: list[str] = []
    seen: set[str] = set()
    for node in root.findall(".//Grupo/datosCabecera/codigo"):
        code = clean_text(node.text)
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def select_senado_credencial(
    credenciales: list[ET.Element], preferred_cred: str | None
) -> ET.Element | None:
    if not credenciales:
        return None
    pref = clean_text(preferred_cred) if preferred_cred else ""
    if pref:
        for cred in credenciales:
            num = clean_text(cred.findtext("numCred"))
            if num == pref:
                return cred
    return credenciales[-1]


def build_senado_records(timeout: int) -> list[dict[str, Any]]:
    grupos_payload, grupos_ct = http_get_bytes(SENADO_GRUPOS_URL, timeout)
    validate_network_payload("senado_senadores", grupos_payload, grupos_ct)
    group_codes = parse_senado_group_codes(grupos_payload)
    if not group_codes:
        raise RuntimeError("No se encontraron grupos parlamentarios del Senado")

    active_by_id: dict[str, dict[str, str]] = {}
    for group_code in group_codes:
        url = SENADO_FICHA_GRUPO_URL_TEMPLATE.format(group_code=group_code)
        payload, ct = http_get_bytes(url, timeout)
        validate_network_payload("senado_senadores", payload, ct)
        root = ET.fromstring(payload)
        for member in root.findall(".//compSenador"):
            idweb = clean_text(member.findtext("Idweb"))
            if not idweb:
                continue

            name = clean_text(member.findtext("Nombre"))
            family = clean_text(member.findtext("Apellidos"))
            periods = member.findall("./periodosPertenencia/periodo")
            best_period: dict[str, str] | None = None
            for period in periods:
                fecha_baja = clean_text(period.findtext("FechaBaja"))
                if fecha_baja:
                    continue
                start_date = parse_senado_date(period.findtext("FechaAlta"))
                candidate = {
                    "idweb": idweb,
                    "nombre": name,
                    "apellidos": family,
                    "credencial": clean_text(period.findtext("Credencial")),
                    "proced_lugar": clean_text(period.findtext("ProcedLugar")),
                    "start_date": start_date or "",
                    "group_code": group_code,
                }
                if not best_period:
                    best_period = candidate
                    continue
                best_start = best_period["start_date"]
                if start_date and (not best_start or start_date > best_start):
                    best_period = candidate
            if not best_period:
                continue
            prev = active_by_id.get(idweb)
            if not prev or best_period["start_date"] > prev["start_date"]:
                active_by_id[idweb] = best_period

    records: list[dict[str, Any]] = []
    for idweb, member in sorted(active_by_id.items()):
        detail_url = SENADO_FICHA_SENADOR_URL_TEMPLATE.format(idweb=idweb)
        root: ET.Element | None = None
        detail_error: str | None = None
        try:
            detail_payload, detail_ct = http_get_bytes(detail_url, timeout)
            validate_network_payload("senado_senadores", detail_payload, detail_ct)
            root = ET.fromstring(detail_payload)
        except Exception as exc:  # noqa: BLE001
            # Robustness: a single broken detail endpoint shouldn't kill the whole run.
            detail_error = f"{type(exc).__name__}: {exc}"

        datos = root.find(".//datosPersonales") if root is not None else None
        nombre = clean_text(datos.findtext("nombre") if datos is not None else None) or member["nombre"]
        apellidos = clean_text(datos.findtext("apellidos") if datos is not None else None) or member["apellidos"]
        full_name = normalize_ws(f"{nombre} {apellidos}")

        credenciales = root.findall(".//credenciales/credencial") if root is not None else []
        selected_cred = select_senado_credencial(credenciales, member.get("credencial")) if root is not None else None
        proced_literal = member.get("proced_lugar", "")
        start_date = member.get("start_date", "")
        party_name = ""
        party_name_full = ""
        group_name = ""
        if selected_cred is not None:
            party_siglas = clean_text(selected_cred.findtext("partidoSiglas"))
            party_name_full = clean_text(selected_cred.findtext("partidoNombre"))
            if not party_name_full:
                party_name_full = clean_text(selected_cred.findtext("formElecNombre"))

            party_name = party_siglas or party_name_full
            proced_literal = clean_text(selected_cred.findtext("procedLiteral")) or proced_literal
            start_date = parse_senado_date(selected_cred.findtext("procedFecha")) or start_date

        if root is not None:
            for group in root.findall(".//gruposParlamentarios/grupoParlamentario"):
                baja = clean_text(group.findtext("grupoBajaFec"))
                if not baja:
                    group_name = clean_text(group.findtext("grupoNombre"))
                    break
            if not group_name:
                group_name = clean_text(root.findtext(".//gruposParlamentarios/grupoParlamentario/grupoNombre"))
        if not group_name:
            group_name = clean_text(member.get("group_code")) or ""

        records.append(
            {
                "source_record_id": f"idweb:{idweb}",
                "id": idweb,
                "nombre": nombre,
                "apellidos": apellidos,
                "full_name": full_name,
                "partido": party_name,
                "partido_nombre": party_name_full,
                "grupo": group_name,
                "provincia": extract_senado_procedencia(proced_literal),
                "fecha_inicio": start_date,
                "detail_error": detail_error,
            }
        )
    return records


class SenadoSenadoresConnector(BaseConnector):
    source_id = "senado_senadores"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        if url_override:
            return url_override
        return SENADO_GRUPOS_URL

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        if from_file is not None:
            resolved_url = f"file://{from_file.resolve()}"
            fetched = fetch_payload(
                source_id=self.source_id,
                source_url=resolved_url,
                raw_dir=raw_dir,
                timeout=timeout,
                from_file=from_file,
                strict_network=strict_network,
            )
            records = parse_csv_source(fetched["payload"])
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

        resolved_url = self.resolve_url(url_override, timeout)
        try:
            records = build_senado_records(timeout)
            payload_obj = {"source": "senado_open_data", "records": records}
            payload = json.dumps(payload_obj, ensure_ascii=True, sort_keys=True).encode("utf-8")
            fetched_at = now_utc_iso()
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(payload)
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(payload),
                content_type="application/json",
                bytes=len(payload),
                note="network",
                payload=payload,
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
            records = parse_csv_source(fetched["payload"])
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
        full_name = pick_value(
            record,
            (
                "full_name",
                "nombre_completo",
                "nombre completo",
                "senador",
                "senadora",
                "nombre",
                "NOMBRE",
            ),
        )
        given_name = pick_value(record, ("given_name", "nombre", "NOMBRE", "name", "Nombre"))
        family_name = pick_value(record, ("apellidos", "APELLIDOS", "surname", "family_name"))

        if given_name and family_name and (
            not full_name or normalize_ws(full_name).lower() == normalize_ws(given_name).lower()
        ):
            full_name = normalize_ws(f"{given_name} {family_name}")
        if full_name and "," in full_name:
            given_guess, family_guess, full_name = split_spanish_name(full_name)
            given_name = given_name or given_guess
            family_name = family_name or family_guess

        if not full_name:
            return None

        party_name = pick_value(record, ("partido", "siglas", "grupo", "grupo_parlamentario"))
        territory = pick_value(record, ("provincia", "circunscripcion", "territorio", "comunidad"))

        source_record_id = pick_value(
            record,
            ("source_record_id", "id", "ID", "codigo", "cod", "codParlamentario"),
        )
        if not source_record_id:
            source_record_id = sha256_bytes(stable_json(record).encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": normalize_ws(full_name),
            "given_name": normalize_ws(given_name) if given_name else None,
            "family_name": normalize_ws(family_name) if family_name else None,
            "gender": pick_value(record, ("sexo", "gender", "genero")),
            "party_name": normalize_ws(party_name) if party_name else None,
            "territory_code": normalize_ws(territory) if territory else "",
            "institution_territory_code": "",
            "birth_date": parse_date_flexible(pick_value(record, ("birth_date", "fecha_nacimiento"))),
            "start_date": parse_date_flexible(pick_value(record, ("start_date", "fecha_inicio", "inicio_mandato"))),
            "end_date": parse_date_flexible(pick_value(record, ("end_date", "fecha_fin"))),
            "source_record_id": source_record_id,
            "role_title": cfg["role_title"],
            "level": cfg["level"],
            "institution_name": cfg["institution_name"],
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }
