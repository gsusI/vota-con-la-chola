from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import SOURCE_CONFIG
from ..fetch import fetch_payload
from ..parsers import parse_csv_source, parse_xlsx_source
from ..types import Extracted
from ..util import normalize_ws, parse_date_flexible, pick_value, sha256_bytes, split_spanish_name, stable_json
from .base import BaseConnector


class MunicipalConcejalesConnector(BaseConnector):
    source_id = "municipal_concejales"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        if url_override:
            return url_override
        return SOURCE_CONFIG[self.source_id]["default_url"]

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        resolved_url = (
            f"file://{from_file.resolve()}" if from_file else self.resolve_url(url_override, timeout)
        )
        fetched = fetch_payload(
            source_id=self.source_id,
            source_url=resolved_url,
            raw_dir=raw_dir,
            timeout=timeout,
            from_file=from_file,
            strict_network=strict_network,
        )
        payload = fetched["payload"]
        if payload.startswith(b"PK\x03\x04"):
            records = parse_xlsx_source(payload)
        else:
            records = parse_csv_source(payload)
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
                "nombre_completo",
                "nombre completo",
                "concejal",
                "persona",
                "cargo_nombre",
                "electo",
                "nombre",
                "name",
            ),
        )

        given_name = pick_value(
            record,
            (
                "given_name",
                "nombre",
                "name",
                "first_name",
                "nombre persona",
            ),
        )
        first_surname = pick_value(
            record,
            (
                "apellidos",
                "apellido",
                "1er apellido",
                "primer apellido",
                "apellido1",
                "surname",
                "family_name",
                "last_name",
            ),
        )
        second_surname = pick_value(
            record,
            (
                "2o apellido",
                "2º apellido",
                "segundo apellido",
                "apellido2",
                "middle_surname",
            ),
        )
        family_name = normalize_ws(" ".join(part for part in (first_surname, second_surname) if part)) or None

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

        municipality_name = pick_value(
            record,
            (
                "municipio",
                "nombre_municipio",
                "municipality",
                "entidad_local",
                "ayuntamiento",
                "localidad",
            ),
        )
        territory_code = pick_value(
            record,
            (
                "codigo_ine",
                "cod_ine",
                "ine",
                "codigo_municipio",
                "cod_municipio",
                "id_municipio",
                "municipality_code",
            ),
        )
        province = pick_value(record, ("provincia", "province"))
        person_territory = normalize_ws(territory_code or province or "")
        institution_territory = normalize_ws(territory_code or "")

        role_title = pick_value(
            record,
            (
                "cargo",
                "cargo_municipal",
                "rol",
                "role",
                "puesto",
                "responsabilidad",
                "delegacion",
            ),
        )
        if not role_title:
            role_title = SOURCE_CONFIG[self.source_id]["role_title"]

        institution_name = SOURCE_CONFIG[self.source_id]["institution_name"]
        if municipality_name:
            institution_name = f"Ayuntamiento de {normalize_ws(municipality_name)}"

        party_name = pick_value(
            record,
            (
                "partido",
                "siglas",
                "candidatura",
                "grupo",
                "grupo_politico",
                "formacion_politica",
                "party",
            ),
        )

        source_record_id = pick_value(
            record,
            (
                "id",
                "ID",
                "source_record_id",
                "id_cargo",
                "id_concejal",
                "id_persona",
            ),
        )
        if not source_record_id:
            fingerprint = "|".join(
                (
                    normalize_ws(full_name),
                    person_territory,
                    normalize_ws(role_title),
                    parse_date_flexible(
                        pick_value(
                            record,
                            (
                                "fecha_inicio",
                                "start_date",
                                "inicio_mandato",
                                "fecha de posesion",
                            ),
                        )
                    )
                    or "",
                )
            )
            source_record_id = sha256_bytes(fingerprint.encode("utf-8"))[:24]

        cfg = SOURCE_CONFIG[self.source_id]
        return {
            "full_name": normalize_ws(full_name),
            "given_name": normalize_ws(given_name) if given_name else None,
            "family_name": normalize_ws(family_name) if family_name else None,
            "gender": pick_value(record, ("sexo", "gender", "genero")),
            "party_name": normalize_ws(party_name) if party_name else None,
            "territory_code": person_territory,
            "institution_territory_code": institution_territory,
            "birth_date": parse_date_flexible(
                pick_value(record, ("fecha_nacimiento", "birth_date", "birthDate"))
            ),
            "start_date": parse_date_flexible(
                pick_value(
                    record,
                    ("fecha_inicio", "start_date", "inicio_mandato", "fecha de posesion"),
                )
            ),
            "end_date": parse_date_flexible(pick_value(record, ("fecha_fin", "end_date", "fin_mandato"))),
            "source_record_id": source_record_id,
            "role_title": normalize_ws(role_title),
            "level": cfg["level"],
            "institution_name": institution_name,
            "source_snapshot_date": snapshot_date,
            "raw_payload": stable_json(record),
        }

