from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.text_documents import (
    backfill_initiative_documents_from_parl_initiatives,
    backfill_text_documents_from_topic_evidence,
)
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes


class TestParlTextDocuments(unittest.TestCase):
    def test_backfill_text_documents_from_topic_evidence_reads_file_url_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "text-docs.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            html_path = td_path / "texto_integro.html"
            html_path.write_text(
                (
                    "<html><body>"
                    "<div class='textoIntegro'>"
                    "<p style='text-align:center'><a name='(Página22)'><b>Página 22</b></a></p>"
                    "<p class='textoCompleto'>Hola <b>mundo</b>. Intervención X.</p>"
                    "<p style='text-align:center'><a name='(Página23)'><b>Página 23</b></a></p>"
                    "<p class='textoCompleto'>Otra página.</p>"
                    "</div>"
                    "</body></html>"
                ),
                encoding="utf-8",
            )

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                ckey = canonical_key(full_name="Persona Demo", birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Persona Demo", ckey, now, now),
                )
                person_id = int(
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )

                sr_payload = '{"kind":"intervention","id":"test"}'
                sr_sha = sha256_bytes(sr_payload.encode("utf-8"))
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "test:1", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "test:1"),
                    ).fetchone()["source_record_pk"]
                )

                # Minimal evidence row: we only need source_url + source_record_pk.
                file_url = f"file://{html_path}#(Página22)"
                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, NULL,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', ?, ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, file_url, sr_pk, now, now),
                )
                conn.commit()

                result1 = backfill_text_documents_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    raw_dir=raw_dir,
                    timeout=5,
                    limit=50,
                    only_missing=True,
                    strict_network=True,
                    dry_run=False,
                )
                self.assertEqual(result1["failures"], [])
                self.assertGreaterEqual(int(result1.get("upserted", 0)), 1)
                excerpt = conn.execute(
                    "SELECT text_excerpt FROM text_documents WHERE source_record_pk = ?",
                    (sr_pk,),
                ).fetchone()["text_excerpt"]
                self.assertIn("Intervención X", excerpt)
                # Ensure we extracted only the requested page, not the next one.
                self.assertNotIn("Otra página", excerpt)

                ev_excerpt = conn.execute(
                    "SELECT excerpt FROM topic_evidence WHERE source_record_pk = ?",
                    (sr_pk,),
                ).fetchone()["excerpt"]
                self.assertIn("Intervención X", ev_excerpt)

                # Re-run: should be idempotent (no extra rows).
                result2 = backfill_text_documents_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    raw_dir=raw_dir,
                    timeout=5,
                    limit=50,
                    only_missing=True,
                    strict_network=True,
                    dry_run=False,
                )
                self.assertEqual(result2["failures"], [])
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) AS c FROM text_documents").fetchone()["c"]),
                    1,
                )

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()

    def test_backfill_initiative_documents_archive_fallback_recovers_prior_404(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-archive-hit.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                original_url = "https://www.senado.es/legis15/publicaciones/pdf/senado/bocg/BOCG_D_15_123_456.PDF"
                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente,
                      links_bocg_json, links_ds_json,
                      source_id, source_url, source_snapshot_date, raw_payload,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:ini:test:1",
                        "15",
                        "610/000001",
                        json.dumps([original_url], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-22",
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO document_fetches (
                      doc_url, source_id,
                      first_attempt_at, last_attempt_at,
                      attempts, fetched_ok,
                      last_http_status, last_error
                    ) VALUES (?, ?, ?, ?, 1, 0, 404, ?)
                    """,
                    (original_url, "parl_initiative_docs", now, now, "HTTP Error 404: Not Found"),
                )
                conn.commit()

                archive_timestamp = "20240102112233"
                archive_url = f"https://web.archive.org/web/{archive_timestamp}id_/{original_url}"
                available_url = f"https://archive.org/wayback/available?url={quote(original_url, safe='')}"

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == available_url:
                        payload = {
                            "archived_snapshots": {
                                "closest": {
                                    "available": True,
                                    "timestamp": archive_timestamp,
                                    "url": archive_url,
                                }
                            }
                        }
                        return json.dumps(payload, ensure_ascii=True).encode("utf-8"), "application/json"
                    if url == archive_url:
                        return b"%PDF-1.4 archived-payload", "application/pdf"
                    if url == original_url:
                        raise AssertionError("direct original URL should not be retried when archive-first is active")
                    raise AssertionError(f"unexpected URL: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-22",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        only_linked_to_votes=False,
                        only_missing=True,
                        retry_forbidden=False,
                        archive_fallback=True,
                        archive_timeout=5,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(int(result.get("fetched_ok") or 0), 1)
                self.assertEqual(int(result.get("archive_fetched_ok") or 0), 1)
                self.assertEqual(int(result.get("archive_lookup_attempted") or 0), 1)
                self.assertEqual(int(result.get("archive_hits") or 0), 1)
                self.assertEqual(result.get("failures"), [])
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) AS c FROM text_documents").fetchone()["c"]),
                    1,
                )
                sr = conn.execute(
                    """
                    SELECT raw_payload
                    FROM source_records
                    WHERE source_id = 'parl_initiative_docs'
                      AND source_record_id = ?
                    """,
                    (original_url,),
                ).fetchone()
                self.assertIsNotNone(sr)
                sr_payload = json.loads(str(sr["raw_payload"] or "{}"))
                self.assertEqual(str(sr_payload.get("fetch_method")), "archive_wayback")
                self.assertEqual(str(sr_payload.get("fetched_from_url")), archive_url)

                fetch_row = conn.execute(
                    "SELECT fetched_ok, last_http_status FROM document_fetches WHERE doc_url = ?",
                    (original_url,),
                ).fetchone()
                self.assertEqual(int(fetch_row["fetched_ok"]), 1)
                self.assertEqual(int(fetch_row["last_http_status"]), 200)
            finally:
                conn.close()

    def test_backfill_initiative_documents_archive_fallback_no_snapshot_keeps_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-archive-miss.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                original_url = "https://www.senado.es/legis10/publicaciones/xml/global_enmiendas_vetos_000001.xml"
                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente,
                      links_bocg_json, links_ds_json,
                      source_id, source_url, source_snapshot_date, raw_payload,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:ini:test:2",
                        "10",
                        "621/000001",
                        json.dumps([original_url], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-22",
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO document_fetches (
                      doc_url, source_id,
                      first_attempt_at, last_attempt_at,
                      attempts, fetched_ok,
                      last_http_status, last_error
                    ) VALUES (?, ?, ?, ?, 1, 0, 404, ?)
                    """,
                    (original_url, "parl_initiative_docs", now, now, "HTTP Error 404: Not Found"),
                )
                conn.commit()

                available_url = f"https://archive.org/wayback/available?url={quote(original_url, safe='')}"

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == available_url:
                        payload = {"archived_snapshots": {}}
                        return json.dumps(payload, ensure_ascii=True).encode("utf-8"), "application/json"
                    if url == original_url:
                        raise AssertionError("direct original URL should not be retried when archive-first is active")
                    raise AssertionError(f"unexpected URL: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-22",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        only_linked_to_votes=False,
                        only_missing=True,
                        retry_forbidden=False,
                        archive_fallback=True,
                        archive_timeout=5,
                        strict_network=False,
                        dry_run=False,
                    )

                self.assertEqual(int(result.get("fetched_ok") or 0), 0)
                self.assertEqual(int(result.get("archive_fetched_ok") or 0), 0)
                self.assertEqual(int(result.get("archive_lookup_attempted") or 0), 1)
                self.assertEqual(int(result.get("archive_hits") or 0), 0)
                self.assertGreaterEqual(len(result.get("failures") or []), 1)
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) AS c FROM text_documents").fetchone()["c"]),
                    0,
                )
                fetch_row = conn.execute(
                    "SELECT attempts, fetched_ok, last_http_status FROM document_fetches WHERE doc_url = ?",
                    (original_url,),
                ).fetchone()
                self.assertGreaterEqual(int(fetch_row["attempts"]), 2)
                self.assertEqual(int(fetch_row["fetched_ok"]), 0)
                self.assertEqual(int(fetch_row["last_http_status"]), 404)
            finally:
                conn.close()

    def test_backfill_initiative_documents_derives_ini_url_from_global_enmiendas(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-derived-ini.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                global_url = "http://www.senado.es/legis10/expedientes/610/enmiendas/global_enmiendas_vetos_10_610000777.xml"
                derived_ini_url = "http://www.senado.es/legis10/expedientes/610/xml/INI-3-610000777.xml"

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente,
                      links_bocg_json, links_ds_json,
                      source_id, source_url, source_snapshot_date, raw_payload,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:leg10:exp:610/000777",
                        "10",
                        "610/000777",
                        json.dumps([global_url], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-22",
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.commit()

                called_urls: list[str] = []

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    called_urls.append(url)
                    if url == derived_ini_url:
                        payload = (
                            "<?xml version='1.0' encoding='ISO-8859-1'?>"
                            "<fichaExpediente><enmiendas><enmienda><enmCantidad>0</enmCantidad></enmienda></enmiendas></fichaExpediente>"
                        ).encode("latin-1", errors="replace")
                        return payload, "application/xml"
                    if url == global_url:
                        raise AssertionError("global URL should not be selected before derived INI with max-docs=1")
                    raise AssertionError(f"unexpected URL: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-22",
                        limit_initiatives=20,
                        max_docs_per_initiative=1,
                        only_linked_to_votes=False,
                        only_missing=True,
                        retry_forbidden=False,
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(int(result.get("derived_ini_candidates") or 0), 1)
                self.assertEqual(int(result.get("derived_ini_selected") or 0), 1)
                self.assertEqual(int(result.get("fetched_ok") or 0), 1)
                self.assertEqual(called_urls, [derived_ini_url])
                row = conn.execute(
                    """
                    SELECT source_url
                    FROM text_documents
                    WHERE source_id = 'parl_initiative_docs'
                    ORDER BY text_document_id DESC
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(str(row["source_url"] or ""), derived_ini_url)
            finally:
                conn.close()

    def test_backfill_initiative_documents_skips_redundant_senado_global_urls_when_alt_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-senado-redundant-global.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                global_url = "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000123.xml"
                detail_url = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000123"

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente,
                      links_bocg_json, links_ds_json,
                      source_id, source_url, source_snapshot_date, raw_payload,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:leg15:exp:600/000123",
                        "15",
                        "600/000123",
                        json.dumps([global_url], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-22",
                        "{}",
                        now,
                        now,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "parl_initiative_docs",
                        detail_url,
                        "2026-02-22",
                        '{"url":"https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000123"}',
                        "sha-senado-detail-600000123",
                        now,
                        now,
                    ),
                )
                sr_pk = int(
                    conn.execute(
                        """
                        SELECT source_record_pk
                        FROM source_records
                        WHERE source_id = 'parl_initiative_docs'
                          AND source_record_id = ?
                        """,
                        (detail_url,),
                    ).fetchone()["source_record_pk"]
                )

                conn.execute(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk,
                      fetched_at, content_type, content_sha256, bytes, raw_path,
                      text_excerpt, text_chars, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "parl_initiative_docs",
                        detail_url,
                        sr_pk,
                        now,
                        "application/xml",
                        "sha-senado-detail-600000123",
                        321,
                        "raw/detail.xml",
                        "",
                        0,
                        now,
                        now,
                    ),
                )

                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents (
                      initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "senado:leg15:exp:600/000123",
                            "bocg",
                            detail_url,
                            sr_pk,
                            now,
                            now,
                        ),
                        (
                            "senado:leg15:exp:600/000123",
                            "bocg",
                            global_url,
                            None,
                            now,
                            now,
                        ),
                    ],
                )
                conn.commit()

                called_urls: list[str] = []

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    called_urls.append(url)
                    raise AssertionError(f"unexpected network call: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-22",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        only_linked_to_votes=False,
                        only_missing=True,
                        retry_forbidden=False,
                        archive_fallback=True,
                        archive_timeout=5,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(called_urls, [])
                self.assertEqual(int(result.get("initiatives_seen") or 0), 1)
                self.assertEqual(int(result.get("urls_to_fetch") or 0), 0)
                self.assertGreaterEqual(int(result.get("skipped_redundant_global_urls") or 0), 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
