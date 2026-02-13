from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from ..politicos_es.util import now_utc_iso

def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _source_record_hash(row: Mapping[str, Any]) -> str:
    source_hash = str(row["source_record_content_sha256"] or "").strip()
    if source_hash:
        return source_hash
    return _sha256_text(str(row["source_raw_payload"] or ""))


def _source_record_payload(row: Mapping[str, Any]) -> dict[str, Any] | None:
    raw_payload = row["source_raw_payload"]
    if not raw_payload:
        return None
    try:
        parsed = json.loads(str(raw_payload))
    except Exception:  # noqa: BLE001
        return None
    return parsed if isinstance(parsed, dict) else None


def _source_payload_from_row(
    source_id: str,
    row: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "source_id": source_id,
        "source_record_id": row["source_record_id"],
        "source_record_pk": row["source_record_pk"],
        "source_snapshot_date": row["source_snapshot_date"],
        "source_payload": _source_record_payload(row),
        "source_hash": _source_record_hash(row),
    }


def _build_descargas_snapshot(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    tipos = conn.execute(
        """
        SELECT
          t.tipo_convocatoria,
          t.descripcion,
          t.source_snapshot_date,
          t.raw_payload AS tipo_raw_payload,
          sr.source_record_id AS tipo_source_record_id,
          sr.source_record_pk,
          sr.content_sha256 AS source_record_content_sha256,
          sr.raw_payload AS source_raw_payload
        FROM infoelectoral_convocatoria_tipos t
        LEFT JOIN source_records sr
          ON sr.source_record_pk = t.source_record_pk
        ORDER BY CAST(t.tipo_convocatoria AS INTEGER), t.tipo_convocatoria
        """
    ).fetchall()

    convocatorias = conn.execute(
        """
        SELECT
          c.convocatoria_id,
          c.tipo_convocatoria,
          c.cod,
          c.fecha,
          c.descripcion,
          c.ambito_territorio,
          c.source_snapshot_date,
          c.raw_payload AS convocatoria_raw_payload,
          sr.source_record_id AS convocatoria_source_record_id,
          sr.source_record_pk,
          sr.content_sha256 AS source_record_content_sha256,
          sr.raw_payload AS source_raw_payload
        FROM infoelectoral_convocatorias c
        LEFT JOIN source_records sr
          ON sr.source_record_pk = c.source_record_pk
        ORDER BY c.tipo_convocatoria, c.cod, c.convocatoria_id
        """
    ).fetchall()

    archivos = conn.execute(
        """
        SELECT
          a.archivo_id,
          a.convocatoria_id,
          a.tipo_convocatoria,
          a.id_convocatoria,
          a.descripcion,
          a.nombre_doc,
          a.ambito,
          a.download_url,
          a.source_snapshot_date,
          a.raw_payload AS archivo_raw_payload,
          sr.source_record_id AS archivo_source_record_id,
          sr.source_record_pk,
          sr.content_sha256 AS source_record_content_sha256,
          sr.raw_payload AS source_raw_payload
        FROM infoelectoral_archivos_extraccion a
        LEFT JOIN source_records sr
          ON sr.source_record_pk = a.source_record_pk
        ORDER BY a.tipo_convocatoria, a.id_convocatoria, a.nombre_doc, a.archivo_id
        """
    ).fetchall()

    archivos_by_convocatoria: dict[str, list[dict[str, Any]]] = {}
    for row in archivos:
        convocatoria_id = str(row["convocatoria_id"] or "")
        if not convocatoria_id:
            continue
        archivos_by_convocatoria.setdefault(convocatoria_id, []).append(
            {
                "archivo_id": row["archivo_id"],
                "tipo_convocatoria": row["tipo_convocatoria"],
                "id_convocatoria": row["id_convocatoria"],
                "descripcion": row["descripcion"],
                "nombre_doc": row["nombre_doc"],
                "ambito": row["ambito"],
                "download_url": row["download_url"],
                "source": _source_payload_from_row(
                    "infoelectoral_descargas",
                    {
                        "source_record_id": row["archivo_source_record_id"],
                        "source_record_pk": row["source_record_pk"],
                        "source_snapshot_date": row["source_snapshot_date"],
                        "source_record_content_sha256": row["source_record_content_sha256"],
                        "source_raw_payload": row["source_raw_payload"],
                    },
                ),
            }
        )

    convocatorias_by_tipo: dict[str, list[dict[str, Any]]] = {}
    for row in convocatorias:
        tipo = str(row["tipo_convocatoria"] or "")
        if not tipo:
            continue
        convocatoria_id = str(row["convocatoria_id"] or "")
        convocatorias_by_tipo.setdefault(tipo, []).append(
            {
                "convocatoria_id": convocatoria_id,
                "codigo": row["cod"],
                "fecha": row["fecha"],
                "descripcion": row["descripcion"],
                "ambito_territorio": row["ambito_territorio"],
                "source": _source_payload_from_row(
                    "infoelectoral_descargas",
                    {
                        "source_record_id": row["convocatoria_source_record_id"],
                        "source_record_pk": row["source_record_pk"],
                        "source_snapshot_date": row["source_snapshot_date"],
                        "source_record_content_sha256": row["source_record_content_sha256"],
                        "source_raw_payload": row["source_raw_payload"],
                    },
                ),
                "archivos": archivos_by_convocatoria.get(convocatoria_id, []),
            }
        )

    tipos_payload: list[dict[str, Any]] = []
    for row in tipos:
        tipo = str(row["tipo_convocatoria"] or "")
        if not tipo:
            continue
        tipos_payload.append(
            {
                "tipo_convocatoria": tipo,
                "descripcion": row["descripcion"],
                "convocatorias": convocatorias_by_tipo.get(tipo, []),
                "source": _source_payload_from_row(
                    "infoelectoral_descargas",
                    {
                        "source_record_id": row["tipo_source_record_id"],
                        "source_record_pk": row["source_record_pk"],
                        "source_snapshot_date": row["source_snapshot_date"],
                        "source_record_content_sha256": row["source_record_content_sha256"],
                        "source_raw_payload": row["tipo_raw_payload"],
                    },
                ),
            }
        )
    return tipos_payload


def _build_procesos_snapshot(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    procesos = conn.execute(
        """
        SELECT
          p.proceso_id,
          p.nombre,
          p.tipo,
          p.ambito,
          p.estado,
          p.fecha,
          p.detalle_url,
          p.source_snapshot_date,
          p.raw_payload AS proceso_raw_payload,
          sr.source_record_id AS proceso_source_record_id,
          sr.source_record_pk,
          sr.content_sha256 AS source_record_content_sha256,
          sr.raw_payload AS source_raw_payload
        FROM infoelectoral_procesos p
        LEFT JOIN source_records sr
          ON sr.source_record_pk = p.source_record_pk
        ORDER BY p.fecha DESC, p.proceso_id
        """
    ).fetchall()

    resultados = conn.execute(
        """
        SELECT
          r.proceso_dataset_id,
          r.proceso_id,
          r.nombre,
          r.tipo_dato,
          r.url,
          r.formato,
          r.fecha,
          r.source_snapshot_date,
          r.raw_payload AS resultado_raw_payload,
          sr.source_record_id AS resultado_source_record_id,
          sr.source_record_pk,
          sr.content_sha256 AS source_record_content_sha256,
          sr.raw_payload AS source_raw_payload
        FROM infoelectoral_proceso_resultados r
        LEFT JOIN source_records sr
          ON sr.source_record_pk = r.source_record_pk
        ORDER BY r.proceso_id, r.proceso_dataset_id
        """
    ).fetchall()

    resultados_by_proceso: dict[str, list[dict[str, Any]]] = {}
    for row in resultados:
        proceso_id = str(row["proceso_id"] or "")
        if not proceso_id:
            continue
        resultados_by_proceso.setdefault(proceso_id, []).append(
            {
                "proceso_dataset_id": row["proceso_dataset_id"],
                "nombre": row["nombre"],
                "tipo_dato": row["tipo_dato"],
                "url": row["url"],
                "formato": row["formato"],
                "fecha": row["fecha"],
                "source": _source_payload_from_row(
                    "infoelectoral_procesos",
                    {
                        "source_record_id": row["resultado_source_record_id"],
                        "source_record_pk": row["source_record_pk"],
                        "source_snapshot_date": row["source_snapshot_date"],
                        "source_record_content_sha256": row["source_record_content_sha256"],
                        "source_raw_payload": row["source_raw_payload"],
                    },
                ),
            }
        )

    procesos_payload: list[dict[str, Any]] = []
    for row in procesos:
        proceso_id = str(row["proceso_id"] or "")
        if not proceso_id:
            continue
        procesos_payload.append(
            {
                "proceso_id": row["proceso_id"],
                "nombre": row["nombre"],
                "tipo": row["tipo"],
                "ambito": row["ambito"],
                "estado": row["estado"],
                "fecha": row["fecha"],
                "detalle_url": row["detalle_url"],
                "resultados": resultados_by_proceso.get(proceso_id, []),
                "source": _source_payload_from_row(
                    "infoelectoral_procesos",
                    {
                        "source_record_id": row["proceso_source_record_id"],
                        "source_record_pk": row["source_record_pk"],
                        "source_snapshot_date": row["source_snapshot_date"],
                        "source_record_content_sha256": row["source_record_content_sha256"],
                        "source_raw_payload": row["proceso_raw_payload"],
                    },
                ),
            }
        )
    return procesos_payload


def build_infoelectoral_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
) -> dict[str, Any]:
    source_rows = conn.execute(
        """
        SELECT
          s.source_id,
          s.default_url,
          s.name
        FROM sources s
        WHERE s.source_id IN ('infoelectoral_descargas', 'infoelectoral_procesos')
        ORDER BY s.source_id
        """
    ).fetchall()

    tipos_payload = _build_descargas_snapshot(conn)
    procesos_payload = _build_procesos_snapshot(conn)

    source_ids = [row["source_id"] for row in source_rows]
    source_names = {row["source_id"]: row["name"] for row in source_rows}
    source_default_urls = {row["source_id"]: row["default_url"] for row in source_rows}

    total_tipos = len(tipos_payload)
    total_convocatorias = sum(len(x.get("convocatorias", [])) for x in tipos_payload)
    total_archivos = sum(
        len(conv.get("archivos", []))
        for x in tipos_payload
        for conv in x.get("convocatorias", [])
    )
    total_procesos = len(procesos_payload)
    total_resultados = sum(len(x.get("resultados", [])) for x in procesos_payload)

    filters = {
        "source_ids": source_ids,
        "source_names": source_names,
        "source_default_urls": source_default_urls,
    }

    return {
        "fecha_referencia": snapshot_date,
        "generado_en": now_utc_iso(),
        "filtros": filters,
        "tipos": tipos_payload,
        "procesos": procesos_payload,
        "totales": {
            "tipos": total_tipos,
            "convocatorias": total_convocatorias,
            "archivos_extraccion": total_archivos,
            "procesos": total_procesos,
            "resultados": total_resultados,
            "source_ids": len(source_ids),
        },
    }


def write_json_if_changed(path: Path, obj: Any) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    prev = path.read_text(encoding="utf-8") if path.exists() else None
    if prev == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


__all__ = ["build_infoelectoral_snapshot", "write_json_if_changed"]
