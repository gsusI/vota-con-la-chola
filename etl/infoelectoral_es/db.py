from __future__ import annotations

import sqlite3
from typing import Any

from ..politicos_es.util import now_utc_iso
from .config import SOURCE_CONFIG


def seed_sources(conn: sqlite3.Connection) -> None:
    ts = now_utc_iso()
    for source_id, cfg in SOURCE_CONFIG.items():
        conn.execute(
            """
            INSERT INTO sources (
              source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
              name=excluded.name,
              scope=excluded.scope,
              default_url=excluded.default_url,
              data_format=excluded.data_format,
              is_active=1,
              updated_at=excluded.updated_at
            """,
            (
                source_id,
                cfg["name"],
                cfg["scope"],
                cfg["default_url"],
                cfg["format"],
                ts,
                ts,
            ),
        )
    conn.commit()


def upsert_tipo_convocatoria(
    conn: sqlite3.Connection,
    *,
    tipo_convocatoria: str,
    descripcion: str,
    source_id: str,
    source_record_pk: int | None,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
) -> None:
    conn.execute(
        """
        INSERT INTO infoelectoral_convocatoria_tipos (
          tipo_convocatoria, descripcion, source_id, source_record_pk, source_snapshot_date,
          raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tipo_convocatoria) DO UPDATE SET
          descripcion=excluded.descripcion,
          source_id=excluded.source_id,
          source_record_pk=COALESCE(excluded.source_record_pk, infoelectoral_convocatoria_tipos.source_record_pk),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, infoelectoral_convocatoria_tipos.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            tipo_convocatoria,
            descripcion,
            source_id,
            source_record_pk,
            snapshot_date,
            raw_payload,
            now_iso,
            now_iso,
        ),
    )


def upsert_convocatoria(
    conn: sqlite3.Connection,
    *,
    convocatoria_id: str,
    tipo_convocatoria: str,
    cod: str,
    fecha: str | None,
    descripcion: str | None,
    ambito_territorio: str | None,
    source_id: str,
    source_record_pk: int | None,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
) -> None:
    conn.execute(
        """
        INSERT INTO infoelectoral_convocatorias (
          convocatoria_id, tipo_convocatoria, cod, fecha, descripcion, ambito_territorio,
          source_id, source_record_pk, source_snapshot_date, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(convocatoria_id) DO UPDATE SET
          tipo_convocatoria=excluded.tipo_convocatoria,
          cod=excluded.cod,
          fecha=excluded.fecha,
          descripcion=excluded.descripcion,
          ambito_territorio=excluded.ambito_territorio,
          source_id=excluded.source_id,
          source_record_pk=COALESCE(excluded.source_record_pk, infoelectoral_convocatorias.source_record_pk),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, infoelectoral_convocatorias.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            convocatoria_id,
            tipo_convocatoria,
            cod,
            fecha,
            descripcion,
            ambito_territorio,
            source_id,
            source_record_pk,
            snapshot_date,
            raw_payload,
            now_iso,
            now_iso,
        ),
    )


def upsert_archivo_extraccion(
    conn: sqlite3.Connection,
    *,
    archivo_id: str,
    convocatoria_id: str,
    tipo_convocatoria: str,
    id_convocatoria: str,
    descripcion: str | None,
    nombre_doc: str,
    ambito: str | None,
    download_url: str,
    source_id: str,
    source_record_pk: int | None,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
    ) -> None:
    conn.execute(
        """
        INSERT INTO infoelectoral_archivos_extraccion (
          archivo_id, convocatoria_id, tipo_convocatoria, id_convocatoria, descripcion,
          nombre_doc, ambito, download_url,
          source_id, source_record_pk, source_snapshot_date,
          raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(archivo_id) DO UPDATE SET
          convocatoria_id=excluded.convocatoria_id,
          tipo_convocatoria=excluded.tipo_convocatoria,
          id_convocatoria=excluded.id_convocatoria,
          descripcion=excluded.descripcion,
          nombre_doc=excluded.nombre_doc,
          ambito=excluded.ambito,
          download_url=excluded.download_url,
          source_id=excluded.source_id,
          source_record_pk=COALESCE(excluded.source_record_pk, infoelectoral_archivos_extraccion.source_record_pk),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, infoelectoral_archivos_extraccion.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            archivo_id,
            convocatoria_id,
            tipo_convocatoria,
            id_convocatoria,
            descripcion,
            nombre_doc,
            ambito,
            download_url,
            source_id,
            source_record_pk,
            snapshot_date,
            raw_payload,
            now_iso,
            now_iso,
        ),
        )


def upsert_proceso(
    conn: sqlite3.Connection,
    *,
    proceso_id: str,
    nombre: str,
    tipo: str | None,
    ambito: str | None,
    estado: str | None,
    fecha: str | None,
    detalle_url: str | None,
    source_id: str,
    source_record_pk: int | None,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
) -> None:
    conn.execute(
        """
        INSERT INTO infoelectoral_procesos (
          proceso_id, nombre, tipo, ambito, estado, fecha, detalle_url,
          source_id, source_record_pk, source_snapshot_date, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(proceso_id) DO UPDATE SET
          nombre=excluded.nombre,
          tipo=excluded.tipo,
          ambito=excluded.ambito,
          estado=excluded.estado,
          fecha=excluded.fecha,
          detalle_url=excluded.detalle_url,
          source_id=excluded.source_id,
          source_record_pk=COALESCE(excluded.source_record_pk, infoelectoral_procesos.source_record_pk),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, infoelectoral_procesos.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            proceso_id,
            nombre,
            tipo,
            ambito,
            estado,
            fecha,
            detalle_url,
            source_id,
            source_record_pk,
            snapshot_date,
            raw_payload,
            now_iso,
            now_iso,
        ),
    )


def upsert_proceso_resultado(
    conn: sqlite3.Connection,
    *,
    proceso_dataset_id: str,
    proceso_id: str,
    nombre: str,
    tipo_dato: str | None,
    url: str,
    formato: str | None,
    fecha: str | None,
    source_id: str,
    source_record_pk: int | None,
    snapshot_date: str | None,
    raw_payload: str,
    now_iso: str,
) -> None:
    conn.execute(
        """
        INSERT INTO infoelectoral_proceso_resultados (
          proceso_dataset_id, proceso_id, nombre, tipo_dato, url, formato, fecha,
          source_id, source_record_pk, source_snapshot_date, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(proceso_dataset_id) DO UPDATE SET
          proceso_id=excluded.proceso_id,
          nombre=excluded.nombre,
          tipo_dato=excluded.tipo_dato,
          url=excluded.url,
          formato=excluded.formato,
          fecha=excluded.fecha,
          source_id=excluded.source_id,
          source_record_pk=COALESCE(excluded.source_record_pk, infoelectoral_proceso_resultados.source_record_pk),
          source_snapshot_date=COALESCE(excluded.source_snapshot_date, infoelectoral_proceso_resultados.source_snapshot_date),
          raw_payload=excluded.raw_payload,
          updated_at=excluded.updated_at
        """,
        (
            proceso_dataset_id,
            proceso_id,
            nombre,
            tipo_dato,
            url,
            formato,
            fecha,
            source_id,
            source_record_pk,
            snapshot_date,
            raw_payload,
            now_iso,
            now_iso,
        ),
    )
