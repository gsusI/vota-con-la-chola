from __future__ import annotations

import gzip
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from publicdata_docs import (
    HTTPStatusError,
    build_text_extraction_queue_rows,
    canonical_url,
    dedupe_keep_order,
    exception_http_status,
    extract_from_xml_or_html,
    maybe_decompress_gzip_payload,
    normalize_text,
    normalize_archive_fallback_http_statuses,
    normalize_http_status_filter,
    sanitize_runtime_path_for_public,
)
from publicdata_docs.parliamentary_es import _senado_direct_variant_urls


class TestPublicDataDocs(unittest.TestCase):
    def test_status_helpers_normalize_retry_and_archive_sets(self) -> None:
        self.assertEqual(normalize_archive_fallback_http_statuses(None), (404,))
        self.assertEqual(normalize_archive_fallback_http_statuses([500, "500", 0, 999]), (500,))
        self.assertEqual(normalize_http_status_filter([0, "404", 700, "x", 404]), (0, 404))

    def test_runtime_path_sanitizer_removes_workstation_paths(self) -> None:
        self.assertEqual(sanitize_runtime_path_for_public("/tmp/driver/node"), "<abs>/node")
        self.assertEqual(sanitize_runtime_path_for_public("file:///tmp/driver/node"), "<uri>/node")
        self.assertEqual(sanitize_runtime_path_for_public("node"), "node")

    def test_url_and_error_helpers_are_generic(self) -> None:
        self.assertEqual(canonical_url(" https://example.test/a#page=3 "), "https://example.test/a")
        self.assertEqual(dedupe_keep_order(["a", " b ", "a", "", "b"]), ["a", "b"])
        payload = gzip.compress(b"ok")
        self.assertEqual(maybe_decompress_gzip_payload(payload), b"ok")

        err = HTTPError("https://example.test", 403, "Forbidden", hdrs=None, fp=None)
        self.assertEqual(exception_http_status(err), 403)
        self.assertEqual(HTTPStatusError(404, "missing").code, 404)

    def test_spanish_parliamentary_document_helpers_are_packaged(self) -> None:
        ini_url = "http://www.senado.es/legis9/expedientes/610/xml/INI-3-610000127.xml"
        variants = _senado_direct_variant_urls(ini_url)
        self.assertIn(
            "http://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=9&id1=610&id2=000127",
            variants,
        )

    def test_local_text_extraction_helpers_are_packaged(self) -> None:
        self.assertEqual(normalize_text("<p>Hola&nbsp; mundo</p>"), "Hola mundo")
        payload = b"<?xml version='1.0' encoding='iso-8859-1'?><root>Espa\xf1a</root>"
        self.assertEqual(extract_from_xml_or_html(payload), "España")

    def test_text_extraction_queue_builder_is_packaged(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "doc.html"
            raw_path.write_text("<p>x</p>", encoding="utf-8")
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            try:
                conn.execute(
                    """
                    CREATE TABLE text_documents (
                      source_id TEXT,
                      source_record_pk INTEGER,
                      source_url TEXT,
                      content_type TEXT,
                      content_sha256 TEXT,
                      bytes INTEGER,
                      raw_path TEXT,
                      fetched_at TEXT,
                      text_excerpt TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents
                    VALUES ('docs', 1, 'https://example.test/doc', 'text/html', 'abc', 7, ?, '2026-02-12T00:00:00Z', '')
                    """,
                    (str(raw_path),),
                )
                rows, summary = build_text_extraction_queue_rows(
                    conn,
                    source_ids={"docs"},
                    allowed_formats={"html"},
                    only_missing_excerpt=True,
                    dedupe_by="content_sha256",
                    limit=0,
                )
            finally:
                conn.close()
        self.assertEqual(summary["queue_items_total"], 1)
        self.assertEqual(rows[0]["queue_key"], "sha256:abc")


if __name__ == "__main__":
    unittest.main()
