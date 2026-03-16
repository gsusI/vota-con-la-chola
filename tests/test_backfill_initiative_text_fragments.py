from __future__ import annotations

import gzip
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backfill_initiative_text_fragments import backfill_fragments


class TestBackfillInitiativeTextFragments(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL
            );
            CREATE TABLE parl_initiative_text_versions (
              initiative_text_version_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER,
              source_url TEXT,
              published_date TEXT,
              version_order INTEGER
            );
            CREATE TABLE parl_initiative_doc_extractions (
              source_record_pk INTEGER PRIMARY KEY,
              full_text_path TEXT
            );
            CREATE TABLE text_documents (
              text_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT,
              source_record_pk INTEGER,
              source_url TEXT,
              raw_path TEXT,
              content_type TEXT,
              text_excerpt TEXT
            );
            CREATE TABLE parl_vote_event_initiatives (
              parl_vote_event_initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
              vote_event_id TEXT,
              initiative_id TEXT
            );
            CREATE TABLE parl_text_fragments (
              fragment_id TEXT PRIMARY KEY,
              initiative_text_version_id TEXT NOT NULL,
              initiative_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER,
              fragment_order INTEGER NOT NULL,
              fragment_kind TEXT NOT NULL,
              fragment_label TEXT,
              char_start INTEGER,
              char_end INTEGER,
              fragment_text TEXT NOT NULL,
              text_hash TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        return conn

    def test_backfill_fragments_uses_headers_and_chunk_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragments.db"
            text_with_headers = Path(td) / "v1.txt"
            text_without_headers = Path(td) / "v2.txt"
            text_with_headers.write_text(
                (
                    "Exposición de motivos. Esta ley prepara cambios de movilidad urbana con objetivos ambientales "
                    "y justificación suficiente para generar un preámbulo largo. "
                    "Artículo 1. Los ayuntamientos podrán restringir el acceso de vehículos contaminantes. "
                    "Artículo 2. Se fijan excepciones para residentes y servicios esenciales. "
                    "Disposición final primera. La entrada en vigor será a los seis meses."
                ),
                encoding="utf-8",
            )
            text_without_headers.write_text(
                (
                    "La norma crea una ayuda directa para transporte público. También fija la gestión administrativa. "
                    "Se prevén pagos trimestrales a las comunidades autónomas. "
                    "La vigencia es anual y la evaluación será posterior."
                ),
                encoding="utf-8",
            )

            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, 'congreso_iniciativas')",
                    [("i1",), ("i2",)],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_text_versions(
                      initiative_text_version_id, initiative_id, source_id, source_record_pk, source_url,
                      published_date, version_order
                    ) VALUES (?, ?, 'congreso_iniciativas', ?, ?, ?, ?)
                    """,
                    [
                        ("v1", "i1", 1, "https://example.org/v1", "2026-01-01", 1),
                        ("v2", "i2", 2, "https://example.org/v2", "2026-01-02", 1),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_doc_extractions(source_record_pk, full_text_path)
                    VALUES (?, ?)
                    """,
                    [(1, str(text_with_headers)), (2, str(text_without_headers))],
                )
                conn.commit()

                result = backfill_fragments(
                    conn,
                    initiative_source_ids=("congreso_iniciativas",),
                    doc_source_id="parl_initiative_docs",
                    only_vote_linked=False,
                    limit_initiatives=0,
                    dry_run=False,
                )
                self.assertEqual(result["versions_seen"], 2)
                self.assertEqual(result["versions_with_text"], 2)
                self.assertGreaterEqual(result["fragments_upserted"], 4)

                header_rows = conn.execute(
                    """
                    SELECT fragment_kind, fragment_label
                    FROM parl_text_fragments
                    WHERE initiative_text_version_id='v1'
                    ORDER BY fragment_order ASC
                    """
                ).fetchall()
                labels = [str(row["fragment_label"] or "") for row in header_rows]
                kinds = [str(row["fragment_kind"]) for row in header_rows]
                self.assertEqual(kinds[0], "paragraph")
                self.assertTrue(any(kind == "article" and "Artículo 1" in label for kind, label in zip(kinds, labels)))
                self.assertTrue(any(kind == "article" and "Artículo 2" in label for kind, label in zip(kinds, labels)))
                self.assertTrue(any(kind == "disposition" for kind in kinds))

                fallback_rows = conn.execute(
                    """
                    SELECT fragment_kind, fragment_label, fragment_text
                    FROM parl_text_fragments
                    WHERE initiative_text_version_id='v2'
                    ORDER BY fragment_order ASC
                    """
                ).fetchall()
                self.assertEqual(len(fallback_rows), 1)
                self.assertEqual(str(fallback_rows[0]["fragment_kind"]), "chunk")
                self.assertIn("ayuda directa", str(fallback_rows[0]["fragment_text"]).lower())
            finally:
                conn.close()

    def test_backfill_fragments_can_filter_specific_initiative_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragments_filter.db"
            text_a = Path(td) / "a.txt"
            text_b = Path(td) / "b.txt"
            text_a.write_text("Artículo 1. Texto de A.", encoding="utf-8")
            text_b.write_text("Artículo 1. Texto de B.", encoding="utf-8")

            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, 'senado_iniciativas')",
                    [("ia",), ("ib",)],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_text_versions(
                      initiative_text_version_id, initiative_id, source_id, source_record_pk, source_url,
                      published_date, version_order
                    ) VALUES (?, ?, 'senado_iniciativas', ?, ?, ?, ?)
                    """,
                    [
                        ("va", "ia", 1, "https://example.org/a", "2026-01-01", 1),
                        ("vb", "ib", 2, "https://example.org/b", "2026-01-02", 1),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_initiative_doc_extractions(source_record_pk, full_text_path) VALUES (?, ?)",
                    [(1, str(text_a)), (2, str(text_b))],
                )
                conn.commit()

                result = backfill_fragments(
                    conn,
                    initiative_source_ids=("senado_iniciativas",),
                    initiative_ids=("ib",),
                    doc_source_id="parl_initiative_docs",
                    only_vote_linked=False,
                    limit_initiatives=0,
                    dry_run=False,
                )
                self.assertEqual(result["initiatives_seen"], 1)
                rows = conn.execute(
                    "SELECT DISTINCT initiative_id FROM parl_text_fragments ORDER BY initiative_id ASC"
                ).fetchall()
                self.assertEqual([str(row["initiative_id"]) for row in rows], ["ib"])
            finally:
                conn.close()

    def test_backfill_fragments_prefers_raw_html_over_stale_materialized_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragments_raw_html.db"
            stale_text = Path(td) / "stale.txt"
            raw_html = Path(td) / "detail.html"
            stale_text.write_text("�^H", encoding="utf-8")
            raw_html.write_bytes(
                gzip.compress(
                    (
                        "<html><body>"
                        "<div>Proposición de Ley por la que se modifica el apartado Uno, punto 2, del artículo 91"
                        " de la Ley 37/1992, de 28 de diciembre, del Impuesto sobre el Valor Añadido.</div>"
                        "<div>Autor: GRUPO PARLAMENTARIO POPULAR EN EL SENADO.</div>"
                        "<div>Situación: Tomado en consideración.</div>"
                        "<div>Fecha de presentación: 21/09/23</div>"
                        "</body></html>"
                    ).encode("utf-8")
                )
            )

            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES ('s-html', 'senado_iniciativas')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_text_versions(
                      initiative_text_version_id, initiative_id, source_id, source_record_pk, source_url,
                      published_date, version_order
                    ) VALUES (
                      'v-html',
                      's-html',
                      'senado_iniciativas',
                      10,
                      'https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=622&numEx=000006',
                      '2023-09-21',
                      1
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO parl_initiative_doc_extractions(source_record_pk, full_text_path) VALUES (10, ?)",
                    (str(stale_text),),
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_record_pk, source_url, raw_path, content_type, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      10,
                      'https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=622&numEx=000006',
                      ?,
                      'text/html;charset=UTF-8',
                      '�^H'
                    )
                    """,
                    (str(raw_html),),
                )
                conn.commit()

                result = backfill_fragments(
                    conn,
                    initiative_source_ids=("senado_iniciativas",),
                    initiative_ids=("s-html",),
                    doc_source_id="parl_initiative_docs",
                    only_vote_linked=False,
                    limit_initiatives=0,
                    dry_run=False,
                )
                self.assertEqual(result["versions_with_text"], 1)
                rows = conn.execute(
                    """
                    SELECT fragment_text
                    FROM parl_text_fragments
                    WHERE initiative_text_version_id = 'v-html'
                    ORDER BY fragment_order ASC
                    """
                ).fetchall()
                joined = " ".join(str(row["fragment_text"] or "") for row in rows)
                self.assertIn("artículo 91", joined.lower())
                self.assertIn("tomado en consideración", joined.lower())
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
