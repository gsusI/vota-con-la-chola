from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ...politicos_es.http import http_get_bytes, payload_looks_like_html
from ...politicos_es.raw import raw_output_path
from ...politicos_es.types import Extracted
from ...politicos_es.util import now_utc_iso, sha256_bytes, stable_json
from ..config import INFOELECTORAL_BASE, SOURCE_CONFIG


def basic_auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def parse_api_payload(payload: bytes) -> list[dict[str, Any]]:
    if not payload:
        raise RuntimeError("Respuesta inesperada (payload vacio)")
    if payload_looks_like_html(payload):
        raise RuntimeError("Respuesta inesperada (HTML recibido)")
    obj = json.loads(payload.decode("utf-8", errors="replace"))
    if not isinstance(obj, dict):
        raise RuntimeError("Respuesta inesperada (no dict)")
    if str(obj.get("cod")) != "200":
        raise RuntimeError(f"Respuesta API con cod={obj.get('cod')}")
    data = obj.get("data")
    if not isinstance(data, list):
        raise RuntimeError("Respuesta inesperada (data no list)")
    return [row for row in data if isinstance(row, dict)]


def extract_ambito(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"\(([^)]+)\)", value)
    if not m:
        return None
    ambito = m.group(1).strip()
    return ambito or None


class InfoelectoralDescargasConnector:
    source_id = "infoelectoral_descargas"

    # Credenciales shippeadas en el JS del propio sitio (ver AGENTS.md).
    _user = "apiInfoelectoral"
    _password = "apiInfoelectoralPro"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or SOURCE_CONFIG[self.source_id]["default_url"]

    def _get_json(self, url: str, timeout: int) -> list[dict[str, Any]]:
        headers = {"Authorization": basic_auth_header(self._user, self._password)}
        # En este entorno, el sitio puede fallar verificacion TLS; usar modo inseguro
        # de forma quirurgica solo para este host.
        payload, _ct = http_get_bytes(url, timeout, headers=headers, insecure_ssl=True)
        return parse_api_payload(payload)

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
    ) -> Extracted:
        resolved_url = self.resolve_url(url_override, timeout)
        fetched_at = now_utc_iso()

        if from_file is not None:
            payload = from_file.read_bytes()
            records = json.loads(payload.decode("utf-8", errors="replace"))
            if not isinstance(records, list):
                raise RuntimeError("Sample invalida: se esperaba una lista JSON")
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(payload)
            return Extracted(
                source_id=self.source_id,
                source_url=f"file://{from_file.resolve()}",
                resolved_url=f"file://{from_file.resolve()}",
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(payload),
                content_type="application/json",
                bytes=len(payload),
                note="from-file",
                payload=payload,
                records=[r for r in records if isinstance(r, dict)],
            )

        try:
            notes: list[str] = []

            def safe_get(url: str, label: str) -> list[dict[str, Any]] | None:
                try:
                    return self._get_json(url, timeout)
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"{label}: {type(exc).__name__}: {exc}")
                    return None

            tipos = safe_get(f"{INFOELECTORAL_BASE}convocatorias/tipos/", "tipos")
            if tipos is None:
                raise RuntimeError("No fue posible recuperar el catálogo de tipos")

            records: list[dict[str, Any]] = []
            for row in tipos:
                tipo = str(row.get("cod") or "").strip()
                if not tipo:
                    continue
                records.append(
                    {
                        "kind": "tipo_convocatoria",
                        "tipo_convocatoria": tipo,
                        "descripcion": str(row.get("descripcion") or "").strip(),
                    }
                )

            # Convocatorias por tipo.
            for tipo in sorted({r["tipo_convocatoria"] for r in records if r.get("kind") == "tipo_convocatoria"}):
                conv_url = f"{INFOELECTORAL_BASE}convocatorias?{urlencode({'tipoConvocatoria': tipo})}"
                convocatorias = safe_get(conv_url, f"convocatorias[{tipo}]")
                if convocatorias is None:
                    continue
                for c in convocatorias:
                    cod = str(c.get("cod") or "").strip()
                    if not cod:
                        continue
                    convocatoria_id = f"tipo:{tipo}|conv:{cod}"
                    records.append(
                        {
                            "kind": "convocatoria",
                            "convocatoria_id": convocatoria_id,
                            "tipo_convocatoria": str(c.get("tipoConvocatoria") or tipo),
                            "cod": cod,
                            "fecha": str(c.get("fecha") or "").strip() or None,
                            "descripcion": str(c.get("descripcion") or "").strip() or None,
                            "ambito_territorio": str(c.get("ambitoTerritorio") or "").strip() or None,
                        }
                    )

                    arch_url = f"{INFOELECTORAL_BASE}archivos/extraccion?{urlencode({'tipoConvocatoria': tipo, 'idConvocatoria': cod})}"
                    archivos = safe_get(arch_url, f"archivos[{tipo}:{cod}]")
                    if archivos is None:
                        continue
                    for a in archivos:
                        nombre_doc = str(a.get("nombreDoc") or "").strip()
                        if not nombre_doc:
                            continue
                        download_url = str(a.get("url") or "").strip()
                        if not download_url:
                            # fallback compatible con el JS antiguo (ruta relativa)
                            download_url = f"https://infoelectoral.interior.gob.es/estaticos/docxl/apliextr/{nombre_doc}"
                        archivo_id = f"{convocatoria_id}|doc:{nombre_doc}"
                        descripcion = str(a.get("descripcion") or "").strip() or None
                        records.append(
                            {
                                "kind": "archivo_extraccion",
                                "archivo_id": archivo_id,
                                "convocatoria_id": convocatoria_id,
                                "tipo_convocatoria": tipo,
                                "id_convocatoria": cod,
                                "descripcion": descripcion,
                                "nombre_doc": nombre_doc,
                                "ambito": extract_ambito(descripcion),
                                "download_url": download_url,
                            }
                        )

            if not records:
                raise RuntimeError(f"No se pudo extraer ningun registro: {'; '.join(notes)}")

            payload = json.dumps(records, ensure_ascii=True, sort_keys=True).encode("utf-8")
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(payload)
            note = "network"
            if notes:
                note = f"network-with-partial-errors ({'; '.join(notes)})"
            return Extracted(
                source_id=self.source_id,
                source_url=resolved_url,
                resolved_url=resolved_url,
                fetched_at=fetched_at,
                raw_path=raw_path,
                content_sha256=sha256_bytes(payload),
                content_type="application/json",
                bytes=len(payload),
                note=note,
                payload=payload,
                records=records,
            )
        except Exception as exc:  # noqa: BLE001
            if strict_network:
                raise
            sample = Path(SOURCE_CONFIG[self.source_id]["fallback_file"])
            payload = sample.read_bytes()
            records = json.loads(payload.decode("utf-8", errors="replace"))
            if not isinstance(records, list):
                records = []
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
                note=f"network-error-fallback: {type(exc).__name__}: {exc}",
                payload=payload,
                records=[r for r in records if isinstance(r, dict)],
            )
