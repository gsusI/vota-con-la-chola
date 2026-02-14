"""Extractor for Infoelectoral official process catalog + dataset endpoints."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
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
    if isinstance(obj, dict):
        if "cod" in obj and str(obj.get("cod")) != "200":
            raise RuntimeError(f"Respuesta API con cod={obj.get('cod')}")
        if "data" in obj:
            data = obj.get("data")
            if isinstance(data, list):
                return [row for row in data if isinstance(row, dict)]
        if "results" in obj and isinstance(obj.get("results"), list):
            return [row for row in obj["results"] if isinstance(row, dict)]
        if isinstance(obj, dict):
            return [obj]
        raise RuntimeError("Respuesta inesperada (payload no list)")
    if isinstance(obj, list):
        return [row for row in obj if isinstance(row, dict)]
    raise RuntimeError("Respuesta inesperada (JSON no soportado)")


def _pick(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        raw = row.get(key)
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            return value
    return None


class InfoelectoralProcesosConnector:
    source_id = "infoelectoral_procesos"

    # Credenciales shippeadas en el JS del propio sitio.
    _user = "apiInfoelectoral"
    _password = "apiInfoelectoralPro"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or SOURCE_CONFIG[self.source_id]["default_url"]

    def _get_json(self, url: str, timeout: int) -> list[dict[str, Any]]:
        headers = {"Authorization": basic_auth_header(self._user, self._password)}
        payload, _ct = http_get_bytes(url, timeout, headers=headers, insecure_ssl=True)
        return parse_api_payload(payload)

    def _extract_from_convocatorias(self, timeout: int) -> tuple[list[dict[str, Any]], list[str]]:
        """Fallback extractor when the historical `/min/procesos/` endpoint is removed.

        We derive a "proceso" per convocatoria and attach available extraction files as datasets.
        This keeps strict-network runs reproducible while preserving raw source traceability.
        """

        notes: list[str] = []
        records: list[dict[str, Any]] = []

        tipos = self._get_json(f"{INFOELECTORAL_BASE}convocatorias/tipos/", timeout)
        if not tipos:
            return [], ["sin tipos de convocatoria"]

        # Convocatorias por tipo + archivos de extraccion.
        for row in tipos:
            if not isinstance(row, dict):
                continue
            tipo = str(row.get("cod") or "").strip()
            if not tipo:
                continue

            conv_url = f"{INFOELECTORAL_BASE}convocatorias?{urlencode({'tipoConvocatoria': tipo})}"
            try:
                convocatorias = self._get_json(conv_url, timeout)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"convocatorias[{tipo}]: {type(exc).__name__}: {exc}")
                continue

            for c in convocatorias:
                if not isinstance(c, dict):
                    continue
                cod = str(c.get("cod") or "").strip()
                if not cod:
                    continue

                proceso_id = f"tipo:{tipo}|conv:{cod}"
                fecha = str(c.get("fecha") or "").strip() or None
                descripcion = str(c.get("descripcion") or "").strip() or None
                ambito = str(c.get("ambitoTerritorio") or "").strip() or None

                records.append(
                    {
                        "kind": "proceso",
                        "proceso_id": proceso_id,
                        "nombre": descripcion or proceso_id,
                        "tipo": tipo,
                        "ambito": ambito,
                        "estado": None,
                        "fecha": fecha,
                        "detalle_url": None,
                        # Keep the upstream row for traceability/debugging.
                        "convocatoria": c,
                    }
                )

                arch_url = f"{INFOELECTORAL_BASE}archivos/extraccion?{urlencode({'tipoConvocatoria': tipo, 'idConvocatoria': cod})}"
                try:
                    archivos = self._get_json(arch_url, timeout)
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"archivos[{tipo}:{cod}]: {type(exc).__name__}: {exc}")
                    continue

                for a in archivos:
                    if not isinstance(a, dict):
                        continue
                    nombre_doc = str(a.get("nombreDoc") or "").strip()
                    if not nombre_doc:
                        continue
                    download_url = str(a.get("url") or "").strip()
                    if not download_url:
                        download_url = f"https://infoelectoral.interior.gob.es/estaticos/docxl/apliextr/{nombre_doc}"

                    ext = None
                    if "." in nombre_doc:
                        ext = nombre_doc.rsplit(".", 1)[-1].strip().lower() or None
                    ds_name = str(a.get("descripcion") or "").strip() or None

                    records.append(
                        {
                            "kind": "proceso_resultado",
                            "proceso_dataset_id": f"{proceso_id}|doc:{nombre_doc}",
                            "proceso_id": proceso_id,
                            "nombre": ds_name or nombre_doc,
                            "tipo_dato": "archivo_extraccion",
                            "url": download_url,
                            "formato": ext,
                            "fecha": fecha,
                            "archivo_extraccion": a,
                        }
                    )

        return records, notes

    @staticmethod
    def _normalize_proceso(row: dict[str, Any]) -> dict[str, Any] | None:
        proceso_id = _pick(row, "proceso_id", "id", "cod", "codigo", "codigo_proc")
        if not proceso_id:
            return None
        return {
            "kind": "proceso",
            "proceso_id": proceso_id,
            "nombre": _pick(row, "nombre", "name", "titulo", "titulo_proceso") or proceso_id,
            "tipo": _pick(row, "tipo", "tipo_proceso", "ambito_proceso"),
            "ambito": _pick(row, "ambito", "ambito_territorial", "ambitoTerritorial", "ambito_geo"),
            "estado": _pick(row, "estado", "estado_proceso", "fase"),
            "fecha": _pick(row, "fecha", "fecha_proceso", "fechaInicio", "fecha_proceso_inicio"),
            "detalle_url": _pick(row, "detalle_url", "url_detalle", "detalleUrl"),
        }

    @staticmethod
    def _extract_dataset_rows(row: dict[str, Any], proceso_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in ("datasets", "resultados", "resultados_descarga", "resultats", "archivos", "resultados_descargables"):
            raw = row.get(key)
            if isinstance(raw, list):
                rows.extend(raw)
            elif isinstance(raw, dict):
                rows.extend(raw.values())
        if not rows:
            return []

        records: list[dict[str, Any]] = []
        for idx, dataset_row in enumerate(rows):
            if not isinstance(dataset_row, dict):
                continue
            dataset_id = _pick(dataset_row, "proceso_dataset_id", "id", "dataset_id", "codigo", "cod")
            url = _pick(dataset_row, "url", "link", "enlace", "archivo", "ruta", "file")
            if not url:
                continue
            if not dataset_id:
                dataset_id = f"{proceso_id}|dataset:{idx}"

            records.append(
                {
                    "kind": "proceso_resultado",
                    "proceso_dataset_id": dataset_id,
                    "proceso_id": proceso_id,
                    "nombre": _pick(dataset_row, "nombre", "name", "titulo", "descripcion", "titulo_dataset") or url,
                    "tipo_dato": _pick(
                        dataset_row,
                        "tipo_dato",
                        "tipo",
                        "tipo_dataset",
                        "clase",
                        "mimetype",
                    ),
                    "url": url,
                    "formato": _pick(dataset_row, "formato", "extension", "file_type", "mime"),
                    "fecha": _pick(
                        dataset_row,
                        "fecha",
                        "fecha_publicacion",
                        "fecha_actualizacion",
                        "fecha_proceso",
                    ),
                }
            )
        return records

    def _extract_record_batches(self, payload: bytes) -> list[dict[str, Any]]:
        raw_rows = parse_api_payload(payload)
        records: list[dict[str, Any]] = []
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            proceso_record = self._normalize_proceso(row)
            if not proceso_record:
                continue
            records.append(proceso_record)
            records.extend(self._extract_dataset_rows(row, proceso_record["proceso_id"]))
        return records

    def _fetch_dataset_from_proceso(self, proceso_id: str, timeout: int) -> list[dict[str, Any]]:
        notes = []
        for path in (f"procesos/{proceso_id}/resultados", f"procesos/{proceso_id}/datasets"):
            try:
                rows = self._get_json(f"{INFOELECTORAL_BASE}{path}", timeout)
                # if row format is {data:[{...}], cod:...}, keep records.
                out: list[dict[str, Any]] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    out.append(
                        {
                            "kind": "proceso_resultado",
                            "proceso_dataset_id": _pick(
                                row, "proceso_dataset_id", "id", "dataset_id", "codigo", "cod"
                            )
                            or f"{proceso_id}|dataset-extra",
                            "proceso_id": proceso_id,
                            "nombre": _pick(row, "nombre", "name", "titulo", "descripcion") or "Resultado",
                            "tipo_dato": _pick(
                                row, "tipo_dato", "tipo", "tipo_dataset", "clase", "mimetype"
                            ),
                            "url": _pick(row, "url", "link", "enlace", "archivo", "ruta", "file") or "",
                            "formato": _pick(row, "formato", "extension", "file_type", "mime"),
                            "fecha": _pick(row, "fecha", "fecha_publicacion", "fecha_actualizacion"),
                        }
                    )
                return [r for r in out if r.get("url")]
            except Exception as exc:  # noqa: BLE001
                notes.append(f"{path}: {type(exc).__name__}: {exc}")
                continue
        if notes:
            # Let caller decide if this matters; caller already tracks partial errors.
            return []
        return []

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
            rows = json.loads(payload.decode("utf-8", errors="replace"))
            if not isinstance(rows, list):
                rows = self._extract_record_batches(payload)
            records = []
            for row in rows:
                if isinstance(row, dict) and str(row.get("kind") or "").strip():
                    records.append(row)
                elif isinstance(row, dict):
                    maybe = self._normalize_proceso(row)
                    if maybe:
                        records.append(maybe)
                        records.extend(self._extract_dataset_rows(row, maybe["proceso_id"]))
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
                records=records,
            )

        try:
            notes: list[str] = []
            try:
                procesos_rows = self._get_json(resolved_url, timeout)
            except HTTPError as exc:
                # The historical endpoint started returning 404 in this environment.
                # Keep strict-network behavior (fail on unexpected HTML), but adapt to API drift.
                if int(getattr(exc, "code", 0) or 0) != 404:
                    raise
                procesos_rows = []
                notes.append(f"default_url_404: {resolved_url}")
            records: list[dict[str, Any]] = []
            for row in procesos_rows:
                if not isinstance(row, dict):
                    continue
                proceso = self._normalize_proceso(row)
                if not proceso:
                    continue
                records.append(proceso)
                records.extend(self._extract_dataset_rows(row, proceso["proceso_id"]))

            # Fallback: derive procesos from convocatorias/archivos when /procesos is missing.
            if not records:
                derived, derived_notes = self._extract_from_convocatorias(timeout)
                records.extend(derived)
                notes.extend(derived_notes)

            for rec in [r for r in records if r.get("kind") == "proceso"]:
                if not any(
                    r.get("kind") == "proceso_resultado" and r.get("proceso_id") == rec.get("proceso_id")
                    for r in records
                ):
                    extra = self._fetch_dataset_from_proceso(rec["proceso_id"], timeout)
                    if extra:
                        records.extend(extra)
                    else:
                        notes.append(f"proceso_id {rec['proceso_id']}: sin resultados directos")

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
            rows = json.loads(payload.decode("utf-8", errors="replace"))
            if not isinstance(rows, list):
                raise RuntimeError(f"Muestra invalida: se esperaba una lista JSON ({self.source_id})")
            raw_rows = [
                r
                for r in rows
                if isinstance(r, dict) and str(r.get("kind") or "").strip()
            ]
            if not raw_rows:
                raw_rows = [record for record in self._extract_record_batches(payload) if record]
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
                records=[
                    r
                    for r in raw_rows
                    if isinstance(r, dict) and str(r.get("kind") or "").strip()
                ],
            )
