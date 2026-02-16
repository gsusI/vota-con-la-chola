from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..politicos_es.db import finish_run, start_run, upsert_source_record
from ..politicos_es.util import now_utc_iso, sha256_bytes, stable_json
from .config import SOURCE_CONFIG
from .connectors import InfoelectoralDescargasConnector, InfoelectoralProcesosConnector
from .db import (
    upsert_archivo_extraccion,
    upsert_convocatoria,
    upsert_proceso,
    upsert_proceso_resultado,
    upsert_tipo_convocatoria,
)


def ingest_one_source(
    conn: sqlite3.Connection,
    connector: InfoelectoralDescargasConnector | InfoelectoralProcesosConnector,
    raw_dir: Path,
    timeout: int,
    from_file: Path | None,
    url_override: str | None,
    snapshot_date: str | None,
    strict_network: bool,
) -> tuple[int, int, str]:
    source_id = connector.source_id
    resolved_url = (
        f"file://{from_file.resolve()}" if from_file else connector.resolve_url(url_override, timeout)
    )
    run_id = start_run(conn, source_id, resolved_url)
    try:
        extracted = connector.extract(
            raw_dir=raw_dir,
            timeout=timeout,
            from_file=from_file,
            url_override=url_override,
            strict_network=strict_network,
        )

        now_iso = now_utc_iso()
        # Keep per-run fetch metadata (used by ops dashboards).
        conn.execute(
            """
            INSERT INTO run_fetches (
              run_id, source_id, source_url, fetched_at, raw_path, content_sha256, content_type, bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
              source_id=excluded.source_id,
              source_url=excluded.source_url,
              fetched_at=excluded.fetched_at,
              raw_path=excluded.raw_path,
              content_sha256=excluded.content_sha256,
              content_type=excluded.content_type,
              bytes=excluded.bytes
            """,
            (
                run_id,
                source_id,
                extracted.source_url,
                extracted.fetched_at,
                str(extracted.raw_path),
                extracted.content_sha256,
                extracted.content_type,
                extracted.bytes,
            ),
        )
        conn.execute(
            """
            INSERT INTO raw_fetches (
              run_id, source_id, source_url, fetched_at, raw_path, content_sha256, content_type, bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, content_sha256) DO NOTHING
            """,
            (
                run_id,
                source_id,
                extracted.source_url,
                extracted.fetched_at,
                str(extracted.raw_path),
                extracted.content_sha256,
                extracted.content_type,
                extracted.bytes,
            ),
        )

        records_seen = 0
        loaded = 0

        tipos: list[dict[str, Any]] = []
        convocatorias: list[dict[str, Any]] = []
        archivos: list[dict[str, Any]] = []
        procesos: list[dict[str, Any]] = []
        resultados: list[dict[str, Any]] = []
        for r in extracted.records:
            if not isinstance(r, dict):
                continue
            records_seen += 1
            kind = str(r.get("kind") or "")
            if kind == "tipo_convocatoria":
                tipos.append(r)
            elif kind == "convocatoria":
                convocatorias.append(r)
            elif kind == "archivo_extraccion":
                archivos.append(r)
            elif kind == "proceso":
                procesos.append(r)
            elif kind == "proceso_resultado":
                resultados.append(r)

        def assert_foreign_key_integrity() -> None:
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if not violations:
                return
            sample = ", ".join(
                f"{row['table']}.{row['rowid']} -> {row['parent']}[{row['fkid']}]"
                for row in violations[:10]
            )
            extra = f", ... (+{len(violations)-10} more)" if len(violations) > 10 else ""
            raise RuntimeError(
                f"foreign key check fallado en {source_id}: {len(violations)} violaciones "
                f"(ej: {sample}{extra})"
            )

        # Upsert in FK order: tipos -> convocatorias -> archivos.
        for r in tipos:
            tipo = str(r.get("tipo_convocatoria") or "").strip()
            if not tipo:
                continue
            raw_payload = stable_json(r)
            srid = f"tipo:{tipo}"
            srpk = upsert_source_record(
                conn=conn,
                source_id=source_id,
                source_record_id=srid,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                now_iso=now_iso,
            )
            upsert_tipo_convocatoria(
                conn,
                tipo_convocatoria=tipo,
                descripcion=str(r.get("descripcion") or "").strip(),
                source_id=source_id,
                source_record_pk=srpk,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                now_iso=now_iso,
            )
            loaded += 1

        for r in convocatorias:
            convocatoria_id = str(r.get("convocatoria_id") or "").strip()
            tipo = str(r.get("tipo_convocatoria") or "").strip()
            cod = str(r.get("cod") or "").strip()
            if not convocatoria_id or not tipo or not cod:
                continue
            raw_payload = stable_json(r)
            srid = f"conv:{convocatoria_id}"
            srpk = upsert_source_record(
                conn=conn,
                source_id=source_id,
                source_record_id=srid,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                now_iso=now_iso,
            )
            upsert_convocatoria(
                conn,
                convocatoria_id=convocatoria_id,
                tipo_convocatoria=tipo,
                cod=cod,
                fecha=r.get("fecha"),
                descripcion=r.get("descripcion"),
                ambito_territorio=r.get("ambito_territorio"),
                source_id=source_id,
                source_record_pk=srpk,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                now_iso=now_iso,
            )
            loaded += 1

        for r in archivos:
            archivo_id = str(r.get("archivo_id") or "").strip()
            convocatoria_id = str(r.get("convocatoria_id") or "").strip()
            tipo = str(r.get("tipo_convocatoria") or "").strip()
            id_convocatoria = str(r.get("id_convocatoria") or "").strip()
            nombre_doc = str(r.get("nombre_doc") or "").strip()
            download_url = str(r.get("download_url") or "").strip()
            if not archivo_id or not convocatoria_id or not tipo or not id_convocatoria or not nombre_doc or not download_url:
                continue
            raw_payload = stable_json(r)
            srid = f"arch:{archivo_id}"
            srpk = upsert_source_record(
                conn=conn,
                source_id=source_id,
                source_record_id=srid,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                now_iso=now_iso,
            )
            upsert_archivo_extraccion(
                conn,
                archivo_id=archivo_id,
                convocatoria_id=convocatoria_id,
                tipo_convocatoria=tipo,
                id_convocatoria=id_convocatoria,
                descripcion=r.get("descripcion"),
                nombre_doc=nombre_doc,
                ambito=r.get("ambito"),
                download_url=download_url,
                source_id=source_id,
                source_record_pk=srpk,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                now_iso=now_iso,
            )
            loaded += 1

        proceso_ids = set()
        # upsert procesos before result rows.
        for r in procesos:
            proceso_id = str(r.get("proceso_id") or "").strip()
            if not proceso_id:
                continue
            raw_payload = stable_json(r)
            srid = f"proc:{proceso_id}"
            srpk = upsert_source_record(
                conn=conn,
                source_id=source_id,
                source_record_id=srid,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                now_iso=now_iso,
            )
            upsert_proceso(
                conn,
                proceso_id=proceso_id,
                nombre=str(r.get("nombre") or "").strip() or proceso_id,
                tipo=r.get("tipo"),
                ambito=r.get("ambito"),
                estado=r.get("estado"),
                fecha=r.get("fecha"),
                detalle_url=r.get("detalle_url"),
                source_id=source_id,
                source_record_pk=srpk,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                now_iso=now_iso,
            )
            proceso_ids.add(proceso_id)
            loaded += 1

        for r in resultados:
            proceso_dataset_id = str(r.get("proceso_dataset_id") or "").strip()
            proceso_id = str(r.get("proceso_id") or "").strip()
            url = str(r.get("url") or "").strip()
            if not proceso_dataset_id or not proceso_id or not url:
                continue
            if proceso_id not in proceso_ids:
                # No process row in this batch; skip if FK would fail.
                continue
            raw_payload = stable_json(r)
            srid = f"pres:{proceso_dataset_id}"
            srpk = upsert_source_record(
                conn=conn,
                source_id=source_id,
                source_record_id=srid,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                now_iso=now_iso,
            )
            upsert_proceso_resultado(
                conn,
                proceso_dataset_id=proceso_dataset_id,
                proceso_id=proceso_id,
                nombre=str(r.get("nombre") or "").strip() or url,
                tipo_dato=r.get("tipo_dato"),
                url=url,
                formato=r.get("formato"),
                fecha=r.get("fecha"),
                source_id=source_id,
                source_record_pk=srpk,
                snapshot_date=snapshot_date,
                raw_payload=raw_payload,
                now_iso=now_iso,
            )
            loaded += 1

        if records_seen > 0 and loaded == 0:
            raise RuntimeError(
                "abortado: records_seen > 0 y records_loaded == 0 "
                f"({source_id}: seen={records_seen}, loaded={loaded})"
            )

        min_loaded = SOURCE_CONFIG.get(source_id, {}).get("min_records_loaded_strict")
        if strict_network and extracted.note == "network" and isinstance(min_loaded, int) and loaded < min_loaded:
            raise RuntimeError(
                f"strict-network abortado: records_loaded < min_records_loaded_strict "
                f"({source_id}: loaded={loaded}, min={min_loaded})"
            )

        assert_foreign_key_integrity()
        conn.commit()
        note = extracted.note or ""
        finish_run(
            conn,
            run_id,
            status="ok",
            message=f"Ingesta completada: {loaded}/{records_seen} ({note})",
            records_seen=records_seen,
            records_loaded=loaded,
            fetched_at=extracted.fetched_at,
            raw_path=extracted.raw_path,
        )
        return records_seen, loaded, note
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        finish_run(
            conn,
            run_id,
            status="error",
            message=f"{type(exc).__name__}: {exc}",
            records_seen=0,
            records_loaded=0,
            fetched_at=None,
            raw_path=None,
        )
        raise
