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
    normalize_key_part,
    normalize_ws,
    now_utc_iso,
    parse_date_flexible,
    pick_value,
    sha256_bytes,
    stable_json,
    split_spanish_name,
)
from .base import BaseConnector


SENADO_DEFAULT_LEGISLATURES: tuple[str, ...] = ("14", "15")
SENADO_GRUPOS_URL = "https://www.senado.es/web/ficopendataservlet?tipoFich=4&legis={legis}"
SENADO_SENADORES_URL = "https://www.senado.es/web/ficopendataservlet?tipoFich=6&legis={legis}"
SENADO_FICHA_GRUPO_URL_TEMPLATE = (
    "https://www.senado.es/web/ficopendataservlet?legis={legis}&tipoFich=2&cod={group_code}"
)
SENADO_FICHA_SENADOR_URL_TEMPLATE = (
    "https://www.senado.es/web/ficopendataservlet?tipoFich=1&cod={idweb}&legis={legis}"
)

SENADO_PARTY_ALIASES = {
    "indep": "Independientes",
    "independientes": "Independientes",
    "independiente": "Independientes",
    "ccpv": "CCPV",
    "ciudadanos": "Ciudadanos",
}


def normalize_senado_party_name(raw: str | None) -> str | None:
    text = clean_text(raw or "")
    if not text:
        return None
    key = normalize_key_part(text)
    return SENADO_PARTY_ALIASES.get(key, text)


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


def _build_senado_tipo6_records(payload: bytes, *, legis: str) -> list[dict[str, Any]]:
    # tipoFich=6 returns a flat roster with no stable ids. We still ingest it to
    # support vote->person_id matching for older legislatures where group-based
    # endpoints (tipoFich=4/2/1) sometimes return empty payloads.
    root = ET.fromstring(payload)
    out: list[dict[str, Any]] = []
    for node in root.findall(".//senadores/senador"):
        nombre = clean_text(node.findtext("nombre"))
        apellidos = clean_text(node.findtext("apellidos"))
        if not (nombre or apellidos):
            continue

        full_name = normalize_ws(f"{nombre} {apellidos}").strip()
        if not full_name:
            continue

        proced_literal = clean_text(node.findtext("procedLiteral"))
        group_siglas = clean_text(node.findtext("grupoSiglas"))
        group_name = clean_text(node.findtext("grupoNombre"))
        group_cod = clean_text(node.findtext("grupoCod"))

        # Deterministic-ish synthetic key (we don't have idweb here).
        srid_seed = stable_json(
            {
                "legis": str(legis),
                "full_name": full_name,
                "proced": proced_literal,
                "grupo_cod": group_cod,
                "grupo_siglas": group_siglas,
                "grupo_nombre": group_name,
            }
        )
        srid = sha256_bytes(srid_seed.encode("utf-8"))[:24]
        out.append(
            {
                "source_record_id": f"tipo6:leg{legis}:{srid}",
                "id": f"tipo6:{srid}",
                "nombre": nombre,
                "apellidos": apellidos,
                "full_name": full_name,
                # Best-effort: use the parliamentary group as a party-ish signal.
                "partido": group_siglas or group_name,
                "partido_nombre": group_name,
                "grupo": group_name or group_siglas,
                "provincia": extract_senado_procedencia(proced_literal),
                "fecha_inicio": None,
                "fecha_fin": None,
                "is_active": False,
                "detail_error": "tipoFich=6",
            }
        )
    return out


def _parse_legislatures(value: str | None) -> tuple[str, ...]:
    if not value:
        return SENADO_DEFAULT_LEGISLATURES
    values = [normalize_ws(v) for v in value.replace(";", ",").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for token in values:
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return tuple(out)


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


def _senado_period_records(member: ET.Element) -> list[dict[str, str | None]]:
    periods_by_key: dict[tuple[str, str], dict[str, str | None]] = {}
    for period in member.findall("./periodosPertenencia/periodo"):
        start_date = parse_senado_date(period.findtext("FechaAlta"))
        end_date = parse_senado_date(period.findtext("FechaBaja"))
        key = (start_date or "", end_date or "")
        if key in periods_by_key:
            continue
        periods_by_key[key] = {
            "start_date": start_date,
            "end_date": end_date,
            "credencial": clean_text(period.findtext("Credencial")),
        }

    periods = list(periods_by_key.values())
    if periods:
        return periods
    return [{"start_date": None, "end_date": None, "credencial": ""}]


def build_senado_records(
    timeout: int,
    legislatures: tuple[str, ...] | None = None,
    *,
    include_details: bool = True,
) -> list[dict[str, Any]]:
    legislatures = legislatures or SENADO_DEFAULT_LEGISLATURES
    members_by_id: dict[str, list[dict[str, Any]]] = {}
    tipo6_records: list[dict[str, Any]] = []

    for legis in legislatures:
        grupos_payload, grupos_ct = http_get_bytes(
            SENADO_GRUPOS_URL.format(legis=legis),
            timeout,
        )
        validate_network_payload("senado_senadores", grupos_payload, grupos_ct)
        try:
            group_codes = parse_senado_group_codes(grupos_payload) if grupos_payload else []
        except Exception:  # noqa: BLE001
            group_codes = []
        if not group_codes:
            # Some legislatures return HTTP 200 with empty payload for tipoFich=4.
            # Fall back to tipoFich=6 roster (no ids/dates, but good enough for name matching).
            roster_payload, roster_ct = http_get_bytes(
                SENADO_SENADORES_URL.format(legis=legis),
                timeout,
            )
            validate_network_payload("senado_senadores", roster_payload, roster_ct)
            try:
                tipo6_records.extend(_build_senado_tipo6_records(roster_payload, legis=str(legis)))
            except Exception:  # noqa: BLE001
                # If even the roster fails to parse, skip this legislature.
                continue
            continue

        for group_code in group_codes:
            url = SENADO_FICHA_GRUPO_URL_TEMPLATE.format(legis=legis, group_code=group_code)
            payload, ct = http_get_bytes(url, timeout)
            validate_network_payload("senado_senadores", payload, ct)
            root = ET.fromstring(payload)
            for member in root.findall(".//compSenador"):
                idweb = clean_text(member.findtext("Idweb"))
                if not idweb:
                    continue

                name = clean_text(member.findtext("Nombre"))
                family = clean_text(member.findtext("Apellidos"))
                proced_lugar = clean_text(member.findtext("ProcedLugar"))
                periods = _senado_period_records(member)

                members_by_id.setdefault(idweb, [])
                for period in periods:
                    members_by_id[idweb].append(
                        {
                            "idweb": idweb,
                            "nombre": name,
                            "apellidos": family,
                            "legis": legis,
                            "credencial": period["credencial"] or "",
                            "proced_lugar": proced_lugar,
                            "start_date": period["start_date"] or "",
                            "end_date": period["end_date"] or "",
                            "group_code": f"{legis}:{group_code}",
                        }
                    )

    records: list[dict[str, Any]] = []
    for idweb, entries in sorted(members_by_id.items()):
        ordered = sorted(
            entries,
            key=lambda item: (
                item["end_date"] == "",  # active first
                item["start_date"] or "",
                item["credencial"],
            ),
            reverse=True,
        )
        active_seen = False
        for member in ordered:
            is_active = not bool(member["end_date"])
            if is_active and not active_seen:
                source_record_id = f"idweb:{idweb}"
                active_seen = True
            else:
                source_record_id = f"idweb:{idweb}:{member['start_date'] or 'sin-fecha'}:{member['end_date'] or 'sin-fin'}"

            records.append(
                {
                    "idweb": idweb,
                    "source_record_id": source_record_id,
                    "nombre": member["nombre"],
                    "apellidos": member["apellidos"],
                    # Preserve the legislature for this specific membership period.
                    "legis": member["legis"],
                    "fecha_inicio": member["start_date"],
                    "fecha_fin": member["end_date"],
                    "credencial": member["credencial"],
                    "proced_lugar": member["proced_lugar"],
                    "is_active": is_active,
                    "group_code": member["group_code"],
                }
            )

    deduped_records: list[dict[str, Any]] = []
    seen_srids: set[str] = set()
    for candidate in records:
        srid = str(candidate["source_record_id"])
        if srid in seen_srids:
            continue
        seen_srids.add(srid)
        deduped_records.append(candidate)

    records = deduped_records

    if not members_by_id and not tipo6_records:
        raise RuntimeError("No se encontraron senadores del Senado en las legislaturas configuradas")

    enriched: list[dict[str, Any]] = []
    if not include_details:
        for record in records:
            nombre = clean_text(str(record.get("nombre") or ""))
            apellidos = clean_text(str(record.get("apellidos") or ""))
            full_name = normalize_ws(f"{nombre} {apellidos}").strip()
            enriched.append(
                {
                    "source_record_id": record["source_record_id"],
                    "id": record["idweb"],
                    "nombre": nombre,
                    "apellidos": apellidos,
                    "full_name": full_name,
                    "partido": "",
                    "partido_nombre": "",
                    "grupo": clean_text(str(record.get("group_code") or "")),
                    "provincia": extract_senado_procedencia(str(record.get("proced_lugar") or "")),
                    "fecha_inicio": str(record.get("fecha_inicio") or ""),
                    "fecha_fin": str(record.get("fecha_fin") or ""),
                    "is_active": bool(record.get("is_active")),
                    "detail_error": "skipped-details",
                }
            )
    else:
        detail_cache: dict[tuple[str, str], ET.Element | None] = {}
        for record in records:
            legis = str(record.get("legis") or "15")
            cache_key = (str(record["idweb"]), legis)
            root: ET.Element | None = None
            detail_error: str | None = None
            if cache_key not in detail_cache:
                detail_url = SENADO_FICHA_SENADOR_URL_TEMPLATE.format(legis=legis, idweb=record["idweb"])
                try:
                    detail_payload, detail_ct = http_get_bytes(detail_url, timeout)
                    validate_network_payload("senado_senadores", detail_payload, detail_ct)
                    detail_cache[cache_key] = ET.fromstring(detail_payload)
                except Exception as exc:  # noqa: BLE001
                    # Keep cache for failed details to avoid repeated retries per period.
                    detail_cache[cache_key] = None
                    detail_error = f"{type(exc).__name__}: {exc}"

            cached_root = detail_cache[cache_key]
            if cached_root is None:
                detail_error = detail_error or "no-detail"
            else:
                root = cached_root

            datos = root.find(".//datosPersonales") if root is not None else None
            nombre = clean_text(datos.findtext("nombre") if datos is not None else None) or record["nombre"]
            apellidos = clean_text(datos.findtext("apellidos") if datos is not None else None) or record["apellidos"]
            full_name = normalize_ws(f"{nombre} {apellidos}")

            credenciales = root.findall(".//credenciales/credencial") if root is not None else []
            selected_cred = select_senado_credencial(credenciales, record["credencial"]) if root is not None else None
            proced_literal = str(record["proced_lugar"] or "")
            start_date = str(record["fecha_inicio"] or "")
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
                group_name = clean_text(str(record["group_code"]))

            enriched.append(
                {
                    "source_record_id": record["source_record_id"],
                    "id": record["idweb"],
                    "nombre": nombre,
                    "apellidos": apellidos,
                    "full_name": full_name,
                    "partido": party_name,
                    "partido_nombre": party_name_full,
                    "grupo": group_name,
                    "provincia": extract_senado_procedencia(proced_literal),
                    "fecha_inicio": start_date,
                    "fecha_fin": str(record["fecha_fin"] or ""),
                    "is_active": bool(record["is_active"]),
                    "detail_error": detail_error,
                }
            )
    if tipo6_records:
        # Ensure stable output order.
        tipo6_records = sorted(tipo6_records, key=lambda r: (str(r.get("full_name") or ""), str(r.get("source_record_id") or "")))
        enriched = [*tipo6_records, *enriched]
    return enriched

class SenadoSenadoresConnector(BaseConnector):
    source_id = "senado_senadores"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        if url_override:
            return url_override
        return SENADO_GRUPOS_URL.format(legis=",".join(SENADO_DEFAULT_LEGISLATURES))

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
            legislation_match = re.search(r"legis=([0-9]+(?:[\s,;][0-9]+)*)", str(resolved_url))
            skip_details = bool(re.search(r"(?:^|[?&])(skip_details|senado_skip_details)=1(?:&|$)", str(resolved_url)))
            include_details = not skip_details
            records = build_senado_records(
                timeout,
                _parse_legislatures(legislation_match.group(1) if legislation_match else None),
                include_details=include_details,
            )
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

        party_name = normalize_senado_party_name(
            pick_value(record, ("partido", "siglas", "grupo", "grupo_parlamentario"))
        )
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
