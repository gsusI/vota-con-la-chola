from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote, unquote

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.text_documents import (
    _PlaywrightFetchConfig,
    _PlaywrightFetcher,
    _ensure_playwright_nodejs_runtime,
    _senado_direct_variant_urls,
    backfill_initiative_documents_from_parl_initiatives,
    backfill_text_documents_from_topic_evidence,
)
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes


class TestParlTextDocuments(unittest.TestCase):
    def test_senado_direct_variant_urls_support_ini_xml_path_family(self) -> None:
        ini_url = "http://www.senado.es/legis9/expedientes/610/xml/INI-3-610000127.xml"
        variants = _senado_direct_variant_urls(ini_url)
        self.assertIn(
            "http://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=9&id1=610&id2=000127",
            variants,
        )
        self.assertIn(
            "http://www.senado.es/web/ficopendataservlet?legis=9&tipoFich=3&tipoEx=610&numEx=000127",
            variants,
        )
        self.assertIn(
            "http://www.senado.es/web/ficopendataservlet?legis=9&tipoFich=12&tipoEx=610&numEx=000127",
            variants,
        )

    def test_ensure_playwright_nodejs_runtime_uses_system_node_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pkg_dir = td_path / "playwright_pkg"
            driver_node = pkg_dir / "driver" / "node"
            driver_cli = pkg_dir / "driver" / "package" / "cli.js"
            driver_node.parent.mkdir(parents=True, exist_ok=True)
            driver_cli.parent.mkdir(parents=True, exist_ok=True)
            driver_node.write_text("#!/bin/false\n", encoding="utf-8")
            driver_cli.write_text("console.log('ok')\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True), patch(
                "etl.parlamentario_es.text_documents.shutil.which",
                return_value="/usr/local/bin/node",
            ), patch(
                "etl.parlamentario_es.text_documents._command_exit_code",
                side_effect=[-9, 0],
            ):
                meta = _ensure_playwright_nodejs_runtime(pkg_dir)
                self.assertEqual(os.environ.get("PLAYWRIGHT_NODEJS_PATH"), "/usr/local/bin/node")

            self.assertTrue(bool(meta.get("fallback_applied")))
            self.assertEqual(meta.get("driver_node_rc"), -9)
            self.assertEqual(meta.get("system_cli_rc"), 0)
            self.assertEqual(meta.get("effective_nodejs_path"), "<abs>/node")

    def test_ensure_playwright_nodejs_runtime_respects_existing_env(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pkg_dir = td_path / "playwright_pkg"
            pkg_dir.mkdir(parents=True, exist_ok=True)

            with patch.dict(os.environ, {"PLAYWRIGHT_NODEJS_PATH": "/custom/node"}, clear=True), patch(
                "etl.parlamentario_es.text_documents._command_exit_code",
                side_effect=AssertionError("should not probe when env already set"),
            ):
                meta = _ensure_playwright_nodejs_runtime(pkg_dir)

            self.assertFalse(bool(meta.get("fallback_applied")))
            self.assertEqual(meta.get("effective_nodejs_path"), "<abs>/node")

    def test_ensure_playwright_nodejs_runtime_falls_back_when_driver_probe_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            pkg_dir = td_path / "playwright_pkg"
            driver_node = pkg_dir / "driver" / "node"
            driver_cli = pkg_dir / "driver" / "package" / "cli.js"
            driver_node.parent.mkdir(parents=True, exist_ok=True)
            driver_cli.parent.mkdir(parents=True, exist_ok=True)
            driver_node.write_text("#!/bin/false\n", encoding="utf-8")
            driver_cli.write_text("console.log('ok')\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True), patch(
                "etl.parlamentario_es.text_documents.shutil.which",
                return_value="/usr/local/bin/node",
            ), patch(
                "etl.parlamentario_es.text_documents._command_exit_code",
                side_effect=[None, 0],
            ):
                meta = _ensure_playwright_nodejs_runtime(pkg_dir)
                self.assertEqual(os.environ.get("PLAYWRIGHT_NODEJS_PATH"), "/usr/local/bin/node")

            self.assertTrue(bool(meta.get("fallback_applied")))
            self.assertIsNone(meta.get("driver_node_rc"))
            self.assertEqual(meta.get("system_cli_rc"), 0)
            self.assertEqual(meta.get("effective_nodejs_path"), "<abs>/node")

    def test_playwright_fetcher_warmup_403_does_not_block_request(self) -> None:
        cfg = _PlaywrightFetchConfig(user_data_dir="/tmp/fake", headless=True)
        fetcher = _PlaywrightFetcher(cfg)

        class _SeedResp:
            status = 403

        class _Page:
            def goto(self, url, wait_until, timeout):  # noqa: ANN001
                return _SeedResp()

        class _Resp:
            status = 200
            headers = {"content-type": "application/pdf"}

            def body(self) -> bytes:
                return b"%PDF-fake"

        class _Request:
            def get(self, url, headers=None, timeout=0):  # noqa: ANN001
                return _Resp()

        class _Ctx:
            request = _Request()

        fetcher._page = _Page()
        fetcher._ctx = _Ctx()

        payload, content_type = fetcher.get_bytes(
            "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000001",
            timeout_seconds=5,
            headers=None,
        )
        self.assertEqual(payload, b"%PDF-fake")
        self.assertEqual(content_type, "application/pdf")
        self.assertTrue(bool(fetcher.runtime_meta.get("warmup_attempted")))
        self.assertEqual(fetcher.runtime_meta.get("warmup_status"), 403)
        self.assertTrue(bool(fetcher.runtime_meta.get("warmup_soft_failed")))
        self.assertFalse(bool(fetcher.runtime_meta.get("warmup_ok")))
        self.assertEqual(fetcher.runtime_meta.get("last_fetch_status"), 200)

    def test_playwright_fetcher_warmup_exception_does_not_block_request(self) -> None:
        cfg = _PlaywrightFetchConfig(user_data_dir="/tmp/fake", headless=True)
        fetcher = _PlaywrightFetcher(cfg)

        class _Page:
            def goto(self, url, wait_until, timeout):  # noqa: ANN001
                raise RuntimeError("warmup-timeout")

        class _Resp:
            status = 200
            headers = {"content-type": "text/html"}

            def body(self) -> bytes:
                return b"<html>ok</html>"

        class _Request:
            def get(self, url, headers=None, timeout=0):  # noqa: ANN001
                return _Resp()

        class _Ctx:
            request = _Request()

        fetcher._page = _Page()
        fetcher._ctx = _Ctx()

        payload, content_type = fetcher.get_bytes(
            "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=15&id1=610&id2=000001",
            timeout_seconds=5,
            headers=None,
        )
        self.assertIn(b"ok", payload)
        self.assertEqual(content_type, "text/html")
        self.assertTrue(bool(fetcher.runtime_meta.get("warmup_attempted")))
        self.assertEqual(fetcher.runtime_meta.get("warmup_status"), None)
        self.assertIn("warmup-timeout", str(fetcher.runtime_meta.get("warmup_error") or ""))
        self.assertTrue(bool(fetcher.runtime_meta.get("warmup_soft_failed")))
        self.assertFalse(bool(fetcher.runtime_meta.get("warmup_ok")))
        self.assertEqual(fetcher.runtime_meta.get("last_fetch_status"), 200)

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

    def test_backfill_initiative_documents_archive_fallback_404_no_snapshot_uses_direct_variant(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-archive-miss-direct-variant.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                original_url = (
                    "https://www.senado.es/web/actividadparlamentaria/iniciativas/"
                    "detalleiniciativa/index.html?legis=10&id1=610&id2=000001"
                )
                variant_url = (
                    "https://www.senado.es/web/ficopendataservlet"
                    "?legis=10&tipoFich=3&tipoEx=610&numEx=000001"
                )
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
                        "senado:ini:test:archive-miss-direct-variant",
                        "10",
                        "610/000001",
                        "[]",
                        json.dumps([original_url], ensure_ascii=True),
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-03-01",
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

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url.startswith("https://archive.org/wayback/available?url="):
                        payload = {"archived_snapshots": {}}
                        return json.dumps(payload, ensure_ascii=True).encode("utf-8"), "application/json"
                    if url == variant_url:
                        return b"<html><body>detalle fallback variant payload</body></html>", "text/html"
                    if url == original_url:
                        raise AssertionError("direct original URL should not be retried when archive-first is active")
                    raise AssertionError(f"unexpected URL: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-03-01",
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
                self.assertEqual(int(result.get("archive_lookup_attempted") or 0), 1)
                self.assertEqual(int(result.get("archive_hits") or 0), 0)
                self.assertEqual(int(result.get("archive_fetched_ok") or 0), 0)
                self.assertEqual(int(result.get("direct_variant_attempted_urls") or 0), 1)
                self.assertGreaterEqual(int(result.get("direct_variant_candidate_urls") or 0), 1)
                self.assertEqual(int(result.get("direct_variant_fetched_ok") or 0), 1)
                self.assertEqual(result.get("failures"), [])

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
                self.assertEqual(str(sr_payload.get("fetch_method")), "direct_variant")
                self.assertEqual(str(sr_payload.get("fetched_from_url")), variant_url)

                fetch_row = conn.execute(
                    "SELECT attempts, fetched_ok, last_http_status FROM document_fetches WHERE doc_url = ?",
                    (original_url,),
                ).fetchone()
                self.assertGreaterEqual(int(fetch_row["attempts"]), 2)
                self.assertEqual(int(fetch_row["fetched_ok"]), 1)
                self.assertEqual(int(fetch_row["last_http_status"]), 200)
            finally:
                conn.close()

    def test_backfill_initiative_documents_archive_fallback_supports_custom_403_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-archive-403.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                original_url = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000064"
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
                        "senado:ini:test:403",
                        "14",
                        "622/000064",
                        json.dumps([original_url], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-28",
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
                    ) VALUES (?, ?, ?, ?, 1, 0, 403, ?)
                    """,
                    (original_url, "parl_initiative_docs", now, now, "HTTP Error 403: Forbidden"),
                )
                conn.commit()

                archive_timestamp = "20240229120000"
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
                        return b"<html><body>archived detalle</body></html>", "text/html"
                    if url == original_url:
                        raise AssertionError("direct original URL should not be retried when archive-first is active for 403")
                    raise AssertionError(f"unexpected URL: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-28",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        only_linked_to_votes=False,
                        only_missing=True,
                        retry_forbidden=False,
                        archive_fallback=True,
                        archive_fallback_http_statuses=(403, 404),
                        archive_timeout=5,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(int(result.get("fetched_ok") or 0), 1)
                self.assertEqual(int(result.get("archive_lookup_attempted") or 0), 1)
                self.assertEqual(int(result.get("archive_hits") or 0), 1)
                self.assertEqual(int(result.get("archive_fetched_ok") or 0), 1)
                self.assertEqual(result.get("archive_fallback_http_statuses"), [403, 404])
            finally:
                conn.close()

    def test_backfill_initiative_documents_archive_fallback_uses_senado_url_variants(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-archive-variant-hit.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                original_url = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000064"
                variant_url = "http://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000064"
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
                        "senado:ini:test:archive-variant",
                        "14",
                        "622/000064",
                        json.dumps([original_url], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-03-01",
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

                archive_timestamp = "20240301101010"
                archive_url = f"https://web.archive.org/web/{archive_timestamp}id_/{variant_url}"

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url.startswith("https://archive.org/wayback/available?url="):
                        probe_url = unquote(url.split("url=", 1)[1])
                        if probe_url == variant_url:
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
                        return json.dumps({"archived_snapshots": {}}, ensure_ascii=True).encode("utf-8"), "application/json"
                    if url == archive_url:
                        return b"<html><body>variant archived payload</body></html>", "text/html"
                    if url == original_url:
                        raise AssertionError("direct original URL should not be retried when archive-first is active")
                    raise AssertionError(f"unexpected URL: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-03-01",
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
                self.assertGreaterEqual(int(result.get("archive_lookup_probe_requests") or 0), 2)
                self.assertEqual(int(result.get("archive_hits") or 0), 1)
                self.assertEqual(int(result.get("archive_variant_hits") or 0), 1)
                self.assertEqual(result.get("failures"), [])
            finally:
                conn.close()

    def test_backfill_initiative_documents_archive_fallback_uses_senado_endpoint_family_probes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-archive-family-hit.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                original_url = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000096"
                detail_seed_url = (
                    "https://www.senado.es/web/actividadparlamentaria/iniciativas/"
                    "detalleiniciativa/index.html?legis=14&id1=622&id2=000096"
                )
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
                        "senado:ini:test:archive-family",
                        "14",
                        "622/000096",
                        json.dumps([original_url], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-03-01",
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

                archive_timestamp = "20240302121212"
                archive_url = f"https://web.archive.org/web/{archive_timestamp}id_/{detail_seed_url}"

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url.startswith("https://archive.org/wayback/available?url="):
                        probe_url = unquote(url.split("url=", 1)[1])
                        if probe_url == detail_seed_url:
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
                        return json.dumps({"archived_snapshots": {}}, ensure_ascii=True).encode("utf-8"), "application/json"
                    if url == archive_url:
                        return b"<html><body>family archived payload</body></html>", "text/html"
                    if url == original_url:
                        raise AssertionError("direct original URL should not be retried when archive-first is active")
                    raise AssertionError(f"unexpected URL: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-03-01",
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
                self.assertEqual(int(result.get("archive_variant_hits") or 0), 1)
                self.assertGreaterEqual(int(result.get("archive_lookup_probe_requests") or 0), 3)
                self.assertEqual(result.get("failures"), [])
            finally:
                conn.close()

    def test_backfill_initiative_documents_retry_http_statuses_filters_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-retry-status-filter.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                url_404 = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=621&numEx=000047"
                url_403 = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=621&numEx=000048"
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
                        "senado:ini:test:status-filter",
                        "14",
                        "621/000047",
                        json.dumps([url_404, url_403], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-28",
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
                    (url_404, "parl_initiative_docs", now, now, "HTTP Error 404: Not Found"),
                )
                conn.execute(
                    """
                    INSERT INTO document_fetches (
                      doc_url, source_id,
                      first_attempt_at, last_attempt_at,
                      attempts, fetched_ok,
                      last_http_status, last_error
                    ) VALUES (?, ?, ?, ?, 1, 0, 403, ?)
                    """,
                    (url_403, "parl_initiative_docs", now, now, "HTTP Error 403: Forbidden"),
                )
                conn.commit()

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == url_404:
                        return b"<html><body>ok 404 retried</body></html>", "text/html"
                    raise AssertionError(f"unexpected URL fetched: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-28",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        only_linked_to_votes=False,
                        only_missing=True,
                        retry_forbidden=True,
                        retry_http_statuses=(404,),
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(result.get("retry_http_statuses"), [404])
                self.assertEqual(int(result.get("candidate_urls") or 0), 2)
                self.assertEqual(int(result.get("urls_to_fetch") or 0), 1)
                self.assertEqual(int(result.get("skipped_retry_http_statuses") or 0), 1)
                self.assertEqual(int(result.get("fetched_ok") or 0), 1)
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) AS c FROM text_documents").fetchone()["c"]),
                    1,
                )
                fetch_403 = conn.execute(
                    "SELECT attempts, fetched_ok, last_http_status FROM document_fetches WHERE doc_url = ?",
                    (url_403,),
                ).fetchone()
                self.assertEqual(int(fetch_403["attempts"]), 1)
                self.assertEqual(int(fetch_403["fetched_ok"]), 0)
                self.assertEqual(int(fetch_403["last_http_status"]), 403)
            finally:
                conn.close()

    def test_backfill_initiative_documents_retry_http_statuses_uses_snapshot_status_for_stable_cohort(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-retry-snapshot-status.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                url_500 = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=610&numEx=000101"
                url_404 = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=610&numEx=000102"
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
                        "senado:ini:test:stable-snapshot",
                        "15",
                        "610/000101",
                        json.dumps([url_500, url_404], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-28",
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
                    ) VALUES (?, ?, ?, ?, 1, 0, 500, ?)
                    """,
                    (url_500, "parl_initiative_docs", now, now, "HTTP Error 500: Internal Server Error"),
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
                    (url_404, "parl_initiative_docs", now, now, "HTTP Error 404: Not Found"),
                )
                conn.commit()

                selected_urls = (url_500, url_404)
                selected_status = {url_500: 500, url_404: 404}

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == url_500:
                        return b"<html><body>ok stable retry</body></html>", "text/html"
                    raise AssertionError(f"unexpected URL fetched: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result_first = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-28",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        selected_doc_urls=selected_urls,
                        selected_doc_status_by_url=selected_status,
                        only_linked_to_votes=False,
                        only_missing=False,
                        retry_forbidden=True,
                        retry_http_statuses=(500,),
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(result_first.get("retry_http_statuses"), [500])
                self.assertEqual(int(result_first.get("selected_doc_urls_total") or 0), 2)
                self.assertEqual(int(result_first.get("selected_doc_urls_with_snapshot_status") or 0), 2)
                self.assertEqual(int(result_first.get("selected_doc_status_used_for_retry") or 0), 2)
                self.assertEqual(int(result_first.get("urls_to_fetch") or 0), 1)
                self.assertEqual(int(result_first.get("skipped_retry_http_statuses") or 0), 1)
                self.assertEqual(int(result_first.get("fetched_ok") or 0), 1)

                fetch_500_after_first = conn.execute(
                    "SELECT attempts, fetched_ok, last_http_status FROM document_fetches WHERE doc_url = ?",
                    (url_500,),
                ).fetchone()
                self.assertEqual(int(fetch_500_after_first["attempts"]), 2)
                self.assertEqual(int(fetch_500_after_first["fetched_ok"]), 1)
                self.assertEqual(int(fetch_500_after_first["last_http_status"]), 200)

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result_second = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-28",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        selected_doc_urls=selected_urls,
                        selected_doc_status_by_url=selected_status,
                        only_linked_to_votes=False,
                        only_missing=False,
                        retry_forbidden=True,
                        retry_http_statuses=(500,),
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                # Even after url_500 transitioned to HTTP 200 in document_fetches,
                # retry filter remains stable because snapshot status says 500.
                self.assertEqual(int(result_second.get("urls_to_fetch") or 0), 1)
                self.assertEqual(int(result_second.get("skipped_retry_http_statuses") or 0), 1)
                self.assertEqual(int(result_second.get("fetched_ok") or 0), 1)
                self.assertEqual(int(result_second.get("selected_doc_status_used_for_retry") or 0), 2)

                fetch_500_after_second = conn.execute(
                    "SELECT attempts, fetched_ok, last_http_status FROM document_fetches WHERE doc_url = ?",
                    (url_500,),
                ).fetchone()
                self.assertEqual(int(fetch_500_after_second["attempts"]), 3)
                self.assertEqual(int(fetch_500_after_second["fetched_ok"]), 1)
                self.assertEqual(int(fetch_500_after_second["last_http_status"]), 200)
            finally:
                conn.close()

    def test_backfill_initiative_documents_snapshot_status_stabilizes_forbidden_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-snapshot-forbidden-filter.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                url_403 = "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=14&id1=621&id2=000066"
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
                        "senado:ini:test:stable-forbidden",
                        "14",
                        "621/000066",
                        json.dumps([url_403], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-28",
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
                    ) VALUES (?, ?, ?, ?, 1, 0, 403, ?)
                    """,
                    (url_403, "parl_initiative_docs", now, now, "HTTP Error 403: Forbidden"),
                )
                conn.commit()

                available_url = f"https://archive.org/wayback/available?url={quote(url_403, safe='')}"
                variant_url_tipo3 = (
                    "https://www.senado.es/web/ficopendataservlet"
                    "?legis=14&tipoFich=3&tipoEx=621&numEx=000066"
                )
                variant_url_tipo12 = (
                    "https://www.senado.es/web/ficopendataservlet"
                    "?legis=14&tipoFich=12&tipoEx=621&numEx=000066"
                )

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == available_url:
                        payload = {"archived_snapshots": {}}
                        return json.dumps(payload, ensure_ascii=True).encode("utf-8"), "application/json"
                    if url == url_403:
                        raise AssertionError("direct URL should not be fetched when archive-first snapshot filter applies")
                    if url in {variant_url_tipo3, variant_url_tipo12}:
                        raise HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)
                    raise AssertionError(f"unexpected URL: {url}")

                kwargs = dict(
                    conn=conn,
                    initiative_source_ids=("senado_iniciativas",),
                    raw_dir=raw_dir,
                    timeout=5,
                    snapshot_date="2026-02-28",
                    limit_initiatives=20,
                    max_docs_per_initiative=3,
                    selected_doc_urls=(url_403,),
                    selected_doc_status_by_url={url_403: 403},
                    only_linked_to_votes=False,
                    only_missing=False,
                    retry_forbidden=False,
                    archive_fallback=True,
                    archive_fallback_http_statuses=(403,),
                    strict_network=False,
                    dry_run=False,
                )

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result_first = backfill_initiative_documents_from_parl_initiatives(**kwargs)
                self.assertEqual(int(result_first.get("urls_to_fetch") or 0), 1)
                self.assertEqual(int(result_first.get("skipped_forbidden") or 0), 0)
                self.assertEqual(int(result_first.get("archive_first_urls") or 0), 1)
                self.assertEqual(int(result_first.get("selected_doc_status_used_for_forbidden_filter") or 0), 1)
                self.assertEqual(int(result_first.get("fetched_ok") or 0), 0)

                fetch_after_first = conn.execute(
                    "SELECT attempts, fetched_ok, last_http_status FROM document_fetches WHERE doc_url = ?",
                    (url_403,),
                ).fetchone()
                self.assertEqual(int(fetch_after_first["last_http_status"]), 403)

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result_second = backfill_initiative_documents_from_parl_initiatives(**kwargs)
                # DB status drifted to 404 after first run, but frozen snapshot status
                # keeps the URL in archive-first lane instead of skip_forbidden.
                self.assertEqual(int(result_second.get("urls_to_fetch") or 0), 1)
                self.assertEqual(int(result_second.get("skipped_forbidden") or 0), 0)
                self.assertEqual(int(result_second.get("archive_first_urls") or 0), 1)
                self.assertEqual(int(result_second.get("selected_doc_status_used_for_forbidden_filter") or 0), 1)
                self.assertEqual(int(result_second.get("fetched_ok") or 0), 0)
            finally:
                conn.close()

    def test_backfill_initiative_documents_retry_http_statuses_accepts_zero_snapshot_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-retry-zero-snapshot-status.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                url_unknown = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=610&numEx=000201"
                url_403 = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=610&numEx=000202"
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
                        "senado:ini:test:retry-zero-snapshot-status",
                        "15",
                        "610/000201",
                        json.dumps([url_unknown, url_403], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-28",
                        "{}",
                        now,
                        now,
                    ),
                )
                for url in (url_unknown, url_403):
                    conn.execute(
                        """
                        INSERT INTO document_fetches (
                          doc_url, source_id,
                          first_attempt_at, last_attempt_at,
                          attempts, fetched_ok,
                          last_http_status, last_error
                        ) VALUES (?, ?, ?, ?, 1, 0, 403, ?)
                        """,
                        (url, "parl_initiative_docs", now, now, "HTTP Error 403: Forbidden"),
                    )
                conn.commit()

                selected_urls = (url_unknown, url_403)
                selected_status = {url_unknown: 0, url_403: 403}

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == url_unknown:
                        return b"<html><body>ok retry unknown snapshot</body></html>", "text/html"
                    raise AssertionError(f"unexpected URL fetched: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-28",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        selected_doc_urls=selected_urls,
                        selected_doc_status_by_url=selected_status,
                        only_linked_to_votes=False,
                        only_missing=False,
                        retry_forbidden=True,
                        retry_http_statuses=(0,),
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(result.get("retry_http_statuses"), [0])
                self.assertEqual(int(result.get("selected_doc_urls_with_snapshot_status") or 0), 2)
                self.assertEqual(int(result.get("selected_doc_status_used_for_retry") or 0), 2)
                self.assertEqual(int(result.get("urls_to_fetch") or 0), 1)
                self.assertEqual(int(result.get("skipped_retry_http_statuses") or 0), 1)
                self.assertEqual(int(result.get("fetched_ok") or 0), 1)

                fetch_403 = conn.execute(
                    "SELECT attempts, fetched_ok, last_http_status FROM document_fetches WHERE doc_url = ?",
                    (url_403,),
                ).fetchone()
                self.assertEqual(int(fetch_403["attempts"]), 1)
                self.assertEqual(int(fetch_403["fetched_ok"]), 0)
                self.assertEqual(int(fetch_403["last_http_status"]), 403)
            finally:
                conn.close()

    def test_backfill_initiative_documents_selected_doc_urls_limits_mapping_upserts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-selected-doc-urls-mapping-scope.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                url_selected = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=621&numEx=000047"
                url_unselected = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=621&numEx=000048"
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
                        "senado:ini:test:selected-doc-scope",
                        "14",
                        "621/000047",
                        json.dumps([url_selected, url_unselected], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-28",
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.commit()

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == url_selected:
                        return b"<html><body>selected only</body></html>", "text/html"
                    raise AssertionError(f"unexpected URL fetched: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-28",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        selected_doc_urls=(url_selected,),
                        selected_doc_status_by_url={url_selected: 403},
                        only_linked_to_votes=False,
                        only_missing=False,
                        retry_forbidden=True,
                        retry_http_statuses=(403,),
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(int(result.get("doc_links_seen") or 0), 1)
                self.assertEqual(int(result.get("candidate_urls") or 0), 1)
                self.assertEqual(int(result.get("urls_filtered_by_selected_doc_urls") or 0), 1)
                self.assertEqual(int(result.get("doc_links_filtered_by_selected_doc_urls") or 0), 1)
                self.assertEqual(int(result.get("initiative_documents_upserted") or 0), 1)
                self.assertEqual(int(result.get("fetched_ok") or 0), 1)

                mapped_urls = conn.execute(
                    """
                    SELECT doc_url
                    FROM parl_initiative_documents
                    WHERE initiative_id = ?
                    ORDER BY doc_url ASC
                    """,
                    ("senado:ini:test:selected-doc-scope",),
                ).fetchall()
                self.assertEqual([str(r["doc_url"]) for r in mapped_urls], [url_selected])
            finally:
                conn.close()

    def test_backfill_initiative_documents_selected_doc_urls_ignore_max_docs_cap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-selected-doc-urls-ignore-max-docs-cap.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                url_first = "https://www.senado.es/web/actividadparlamentaria/iniciativas/enmiendas/index.html?id1=621&id2=000081&legis=14"
                url_selected = (
                    "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/"
                    "index.html?legis=14&id1=621&id2=000081"
                )
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
                        "senado:ini:test:selected-doc-cap",
                        "14",
                        "621/000081",
                        json.dumps([url_first, url_selected], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-03-01",
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.commit()

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == url_selected:
                        return b"<html><body>selected doc should pass cap</body></html>", "text/html"
                    raise AssertionError(f"unexpected URL fetched: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-03-01",
                        limit_initiatives=20,
                        max_docs_per_initiative=1,
                        selected_doc_urls=(url_selected,),
                        selected_doc_status_by_url={url_selected: 403},
                        only_linked_to_votes=False,
                        only_missing=False,
                        retry_forbidden=True,
                        retry_http_statuses=(403,),
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertTrue(bool(result.get("selected_scope_ignores_doc_cap")))
                self.assertEqual(int(result.get("selected_doc_urls_not_in_candidates") or 0), 0)
                self.assertEqual(int(result.get("candidate_urls") or 0), 1)
                self.assertEqual(int(result.get("doc_links_seen") or 0), 1)
                self.assertEqual(int(result.get("fetched_ok") or 0), 1)

                mapped = conn.execute(
                    """
                    SELECT doc_url
                    FROM parl_initiative_documents
                    WHERE initiative_id = ?
                    ORDER BY doc_url ASC
                    """,
                    ("senado:ini:test:selected-doc-cap",),
                ).fetchall()
                self.assertEqual([str(r["doc_url"]) for r in mapped], [url_selected])
            finally:
                conn.close()

    def test_backfill_initiative_documents_selected_doc_entry_keys_limit_shared_url_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-selected-entry-keys-shared-url.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                shared_url = "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=14&id1=621&id2=000006"
                initiatives = (
                    ("senado:ini:test:entry-key:1", "621/000006"),
                    ("senado:ini:test:entry-key:2", "621/000007"),
                )
                for initiative_id, expediente in initiatives:
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
                            initiative_id,
                            "14",
                            expediente,
                            json.dumps([shared_url], ensure_ascii=True),
                            "[]",
                            "senado_iniciativas",
                            "https://www.senado.es/",
                            "2026-02-28",
                            "{}",
                            now,
                            now,
                        ),
                    )
                conn.commit()

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == shared_url:
                        return b"<html><body>shared selected row only</body></html>", "text/html"
                    raise AssertionError(f"unexpected URL fetched: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-28",
                        limit_initiatives=20,
                        max_docs_per_initiative=3,
                        selected_doc_urls=(shared_url,),
                        selected_doc_entry_keys=((initiatives[0][0], "bocg", shared_url),),
                        selected_doc_status_by_url={shared_url: 403},
                        only_linked_to_votes=False,
                        only_missing=False,
                        retry_forbidden=True,
                        retry_http_statuses=(403,),
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertEqual(int(result.get("selected_doc_entry_keys_total") or 0), 1)
                self.assertEqual(int(result.get("selected_initiatives_total") or 0), 1)
                self.assertTrue(bool(result.get("selected_scope_no_limit")))
                self.assertEqual(int(result.get("doc_links_filtered_by_selected_doc_entry_keys") or 0), 0)
                self.assertEqual(int(result.get("doc_links_seen") or 0), 1)
                self.assertEqual(int(result.get("initiative_documents_upserted") or 0), 1)
                self.assertEqual(int(result.get("fetched_ok") or 0), 1)

                mapped = conn.execute(
                    """
                    SELECT initiative_id, doc_url
                    FROM parl_initiative_documents
                    ORDER BY initiative_id ASC
                    """
                ).fetchall()
                self.assertEqual(len(mapped), 1)
                self.assertEqual(str(mapped[0]["initiative_id"]), initiatives[0][0])
                self.assertEqual(str(mapped[0]["doc_url"]), shared_url)
            finally:
                conn.close()

    def test_backfill_initiative_documents_selected_scope_ignores_limit_initiatives(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-selected-scope-no-limit.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                url_a = "https://www.senado.es/web/actividadparlamentaria/iniciativas/enmiendas/index.html?id1=621&id2=000001&legis=14"
                url_b = "https://www.senado.es/web/actividadparlamentaria/iniciativas/enmiendas/index.html?id1=621&id2=000002&legis=14"

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
                        "senado:ini:test:selected-limit:a",
                        "14",
                        "621/000001",
                        json.dumps([url_a], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-28",
                        "{}",
                        now,
                        now,
                    ),
                )
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
                        "senado:ini:test:selected-limit:b",
                        "14",
                        "621/000002",
                        json.dumps([url_b], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-28",
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.commit()

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == url_b:
                        return b"<html><body>selected scope no-limit</body></html>", "text/html"
                    raise AssertionError(f"unexpected URL fetched: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-28",
                        limit_initiatives=1,
                        max_docs_per_initiative=1,
                        selected_doc_urls=(url_b,),
                        selected_doc_entry_keys=(("senado:ini:test:selected-limit:b", "bocg", url_b),),
                        selected_doc_status_by_url={url_b: 403},
                        only_linked_to_votes=False,
                        only_missing=False,
                        retry_forbidden=True,
                        retry_http_statuses=(403,),
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertTrue(bool(result.get("selected_scope_no_limit")))
                self.assertEqual(int(result.get("selected_initiatives_total") or 0), 1)
                self.assertEqual(int(result.get("initiatives_seen") or 0), 1)
                self.assertEqual(int(result.get("doc_links_seen") or 0), 1)
                self.assertEqual(int(result.get("fetched_ok") or 0), 1)

                mapped = conn.execute(
                    """
                    SELECT initiative_id, doc_url
                    FROM parl_initiative_documents
                    ORDER BY initiative_id ASC
                    """
                ).fetchall()
                self.assertEqual(len(mapped), 1)
                self.assertEqual(str(mapped[0]["initiative_id"]), "senado:ini:test:selected-limit:b")
                self.assertEqual(str(mapped[0]["doc_url"]), url_b)
            finally:
                conn.close()

    def test_backfill_initiative_documents_selected_scope_honors_missing_new_urls_even_with_existing_docs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-selected-missing-extra.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                initiative_id = "senado:ini:test:selected-missing-extra"
                existing_url = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000096"
                new_url = "https://www.senado.es/legis14/publicaciones/pdf/senado/bocg/BOCG_D_14_382_3389.PDF"

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
                        initiative_id,
                        "14",
                        "622/000096",
                        json.dumps([existing_url, new_url], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-03-12",
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_record_pk, source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        1,
                        "parl_initiative_docs",
                        existing_url,
                        "2026-03-12",
                        "{}",
                        "sha-existing",
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents (
                      initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        initiative_id,
                        "bocg",
                        existing_url,
                        1,
                        now,
                        now,
                    ),
                )
                conn.commit()

                def fake_http_get_bytes(url: str, timeout: int, headers: dict[str, str] | None = None, **kwargs):  # type: ignore[no-untyped-def]
                    if url == new_url:
                        return b"%PDF-1.4 selected missing extra", "application/pdf"
                    raise AssertionError(f"unexpected URL fetched: {url}")

                with patch("etl.parlamentario_es.text_documents.http_get_bytes", side_effect=fake_http_get_bytes):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-03-12",
                        limit_initiatives=10,
                        max_docs_per_initiative=4,
                        selected_doc_entry_keys=((initiative_id, "bocg", new_url),),
                        only_linked_to_votes=False,
                        only_missing=True,
                        retry_forbidden=False,
                        archive_fallback=False,
                        strict_network=True,
                        dry_run=False,
                    )

                self.assertTrue(bool(result.get("selected_scope_no_limit")))
                self.assertEqual(int(result.get("selected_initiatives_total") or 0), 1)
                self.assertEqual(int(result.get("initiatives_seen") or 0), 1)
                self.assertEqual(int(result.get("candidate_urls") or 0), 1)
                self.assertEqual(int(result.get("urls_to_fetch") or 0), 1)
                self.assertEqual(int(result.get("fetched_ok") or 0), 1)

                mapped = conn.execute(
                    """
                    SELECT doc_url
                    FROM parl_initiative_documents
                    WHERE initiative_id = ?
                    ORDER BY doc_url ASC
                    """,
                    (initiative_id,),
                ).fetchall()
                self.assertEqual([str(r["doc_url"]) for r in mapped], [new_url, existing_url])
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

    def test_backfill_initiative_documents_playwright_init_circuit_breaker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "initdocs-playwright-circuit.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                url_a = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000001"
                url_b = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000002"

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
                        "senado:leg15:exp:600/000001",
                        "15",
                        "600/000001",
                        json.dumps([url_a, url_b], ensure_ascii=True),
                        "[]",
                        "senado_iniciativas",
                        "https://www.senado.es/",
                        "2026-02-27",
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.commit()

                with patch(
                    "etl.parlamentario_es.text_documents._PlaywrightFetcher.__enter__",
                    side_effect=RuntimeError("boom-init"),
                ), patch(
                    "etl.parlamentario_es.text_documents.http_get_bytes",
                    side_effect=AssertionError("http_get_bytes should not be used for senado.es when playwright is configured"),
                ):
                    result = backfill_initiative_documents_from_parl_initiatives(
                        conn,
                        initiative_source_ids=("senado_iniciativas",),
                        raw_dir=raw_dir,
                        timeout=5,
                        snapshot_date="2026-02-27",
                        limit_initiatives=5,
                        max_docs_per_initiative=2,
                        only_linked_to_votes=False,
                        only_missing=True,
                        retry_forbidden=True,
                        playwright_user_data_dir=str(td_path / "fake-profile"),
                        playwright_headless=True,
                        strict_network=False,
                        dry_run=False,
                    )

                self.assertEqual(int(result.get("candidate_urls") or 0), 2)
                self.assertEqual(int(result.get("urls_to_fetch") or 0), 2)
                self.assertEqual(int(result.get("fetched_ok") or 0), 0)
                self.assertIn("boom-init", str(result.get("playwright_init_error") or ""))

                failures = [str(v) for v in (result.get("failures") or [])]
                self.assertGreaterEqual(len(failures), 2)
                self.assertTrue(any("boom-init" in f for f in failures))
                self.assertTrue(any("playwright init blocked" in f for f in failures))
                self.assertFalse(any("AssertionError" in f for f in failures))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
