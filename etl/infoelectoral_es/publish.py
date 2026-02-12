from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..politicos_es.util import now_utc_iso


def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _source_record_hash(row: sqlite3.Row) -> str:
    source_hash = str(row["source_record_content_sha256"] or "").strip()
    if source_hash:
        return source_hash
    return _sha256_text(str(row["source_raw_payload"] or ""))


def _source_record_payload(row: sqlite3.Row) -> dict[str, Any] | None:
    raw_payload = row["source_raw_payload"]
    if not raw_payload:
        return None
    try:
        parsed = json.loads(str(raw_payload))
    except Exception:  # noqa: BLE001
        return None
    return parsed if isinstance(parsed, dict) else None


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
        WHERE s.source_id = 'infoelectoral_descargas'
        LIMIT 1
        """
    ).fetchall()

    source_info = source_rows[0] if source_rows else None

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
                "source": {
                    "source_id": "infoelectoral_descargas",
                    "source_record_id": row["archivo_source_record_id"],
                    "source_record_pk": row["source_record_pk"],
                    "source_snapshot_date": row["source_snapshot_date"],
                    "source_payload": _source_record_payload(row),
                    "source_hash": _source_record_hash(row),
                },
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
                "source": {
                    "source_id": "infoelectoral_descargas",
                    "source_record_id": row["convocatoria_source_record_id"],
                    "source_record_pk": row["source_record_pk"],
                    "source_snapshot_date": row["source_snapshot_date"],
                    "source_payload": _source_record_payload(row),
                    "source_hash": _source_record_hash(row),
                },
                "archivos": archivos_by_convocatoria.get(convocatoria_id, []),
            }
        )

    tipos_payload: list[dict[str, Any]] = []
    for row in tipos:
        tipo = str(row["tipo_convocatoria"] or "")
        if not tipo:
            continue
        payload = {
            "tipo_convocatoria": tipo,
            "descripcion": row["descripcion"],
            "convocatorias": convocatorias_by_tipo.get(tipo, []),
            "source": {
                "source_id": "infoelectoral_descargas",
                "source_record_id": row["tipo_source_record_id"],
                "source_record_pk": row["source_record_pk"],
                "source_snapshot_date": row["source_snapshot_date"],
                "source_payload": _source_record_payload(row),
                "source_hash": _source_record_hash(row),
            },
        }
        tipos_payload.append(payload)

    total_tipos = len(tipos_payload)
    total_convocatorias = sum(len(x.get("convocatorias", [])) for x in tipos_payload)
    total_archivos = sum(
        len(conv.get("archivos", []))
        for x in tipos_payload
        for conv in x.get("convocatorias", [])
    )

    filters = {"source_id": "infoelectoral_descargas"}
    if source_info:
        filters.update(
            {
                "source_name": source_info["name"],
                "source_default_url": source_info["default_url"],
            }
        )

    return {
        "fecha_referencia": snapshot_date,
        "generado_en": now_utc_iso(),
        "filtros": filters,
        "tipos": tipos_payload,
        "totales": {
            "tipos": total_tipos,
            "convocatorias": total_convocatorias,
            "archivos_extraccion": total_archivos,
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
