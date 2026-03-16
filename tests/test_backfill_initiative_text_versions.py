from __future__ import annotations

import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backfill_initiative_text_versions import backfill_versions
from scripts.export_initiative_measure_review_queue import write_evidence_bundle


class TestBackfillInitiativeTextVersions(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE sources (source_id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              source_id TEXT,
              source_record_id TEXT
            );
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT,
              title TEXT
            );
            CREATE TABLE parl_initiative_documents (
              initiative_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              initiative_id TEXT,
              doc_kind TEXT,
              doc_url TEXT,
              source_record_pk INTEGER
            );
            CREATE TABLE text_documents (
              text_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT,
              source_url TEXT,
              source_record_pk INTEGER,
              content_type TEXT,
              raw_path TEXT,
              text_excerpt TEXT,
              text_chars INTEGER
            );
            CREATE TABLE parl_vote_events (
              vote_event_id TEXT PRIMARY KEY,
              vote_date TEXT,
              source_id TEXT,
              title TEXT,
              subgroup_title TEXT,
              subgroup_text TEXT,
              expediente_text TEXT,
              totals_yes INTEGER,
              totals_no INTEGER,
              totals_abstain INTEGER
            );
            CREATE TABLE parl_vote_event_initiatives (
              parl_vote_event_initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
              vote_event_id TEXT,
              initiative_id TEXT
            );
            CREATE TABLE parl_initiative_text_versions (
              initiative_text_version_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL,
              chamber TEXT NOT NULL,
              doc_kind TEXT NOT NULL,
              document_code TEXT,
              doc_series TEXT,
              doc_number TEXT,
              version_order INTEGER,
              published_date TEXT,
              stage_kind TEXT NOT NULL,
              stage_label TEXT,
              source_id TEXT NOT NULL,
              source_url TEXT,
              source_record_pk INTEGER,
              raw_payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (initiative_id, source_record_pk),
              UNIQUE (initiative_id, source_url)
            );
            CREATE TABLE parl_vote_event_text_versions (
              parl_vote_event_text_version_id INTEGER PRIMARY KEY AUTOINCREMENT,
              vote_event_id TEXT NOT NULL,
              initiative_id TEXT NOT NULL,
              initiative_text_version_id TEXT NOT NULL,
              link_method TEXT NOT NULL,
              confidence REAL,
              is_primary INTEGER NOT NULL DEFAULT 1,
              raw_payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (vote_event_id, initiative_id, is_primary)
            );
            """
        )
        conn.executemany(
            "INSERT INTO sources(source_id, name) VALUES (?, ?)",
            [
                ("congreso_iniciativas", "Congreso iniciativas"),
                ("congreso_votaciones", "Congreso votaciones"),
                ("parl_initiative_docs", "Docs"),
            ],
        )
        return conn

    def test_backfill_and_bundle_expose_time_aware_versions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "versions.db"
            doc1 = Path(td) / "doc1.xml"
            doc2 = Path(td) / "doc2.xml"
            doc1.write_text(
                "<root><p>14 de junio de 2024. PROYECTO DE LEY. Texto inicial del proyecto.</p></root>",
                encoding="utf-8",
            )
            doc2.write_text(
                "<root><p>10 de diciembre de 2024. ENMIENDAS DEL SENADO. Texto con cambios del Senado.</p></root>",
                encoding="utf-8",
            )

            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (?, 'parl_initiative_docs', ?)",
                    [(1, "doc-1"), (2, "doc-2")],
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES ('i1', 'congreso_iniciativas', 'Proyecto de Ley de prueba.')
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('i1', 'bocg', ?, ?)
                    """,
                    [
                        ("https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BOCG-15-A-23-1.PDF", 1),
                        ("https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BOCG-15-A-23-2.PDF", 2),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, raw_path, text_excerpt, text_chars)
                    VALUES ('parl_initiative_docs', ?, ?, 'text/xml', ?, ?, ?)
                    """,
                    [
                        (
                            "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BOCG-15-A-23-1.PDF",
                            1,
                            str(doc1),
                            "14 de junio de 2024. PROYECTO DE LEY. Texto inicial del proyecto.",
                            80,
                        ),
                        (
                            "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BOCG-15-A-23-2.PDF",
                            2,
                            str(doc2),
                            "10 de diciembre de 2024. ENMIENDAS DEL SENADO. Texto con cambios del Senado.",
                            90,
                        ),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, vote_date, source_id, title, subgroup_title, subgroup_text,
                      expediente_text, totals_yes, totals_no, totals_abstain
                    )
                    VALUES (?, ?, 'congreso_votaciones', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "v_intro",
                            "2024-09-26",
                            "Debates de totalidad de iniciativas legislativas.",
                            "Enmienda a la totalidad",
                            "",
                            "Proyecto de Ley de prueba.",
                            171,
                            179,
                            0,
                        ),
                        (
                            "v_senado",
                            "2024-12-19",
                            "Enmiendas del Senado.",
                            "Votación separada de las enmiendas",
                            "",
                            "Proyecto de Ley de prueba.",
                            177,
                            168,
                            0,
                        ),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, 'i1')",
                    [("v_intro",), ("v_senado",)],
                )
                conn.commit()

                summary = backfill_versions(
                    conn,
                    initiative_source_ids=("congreso_iniciativas",),
                    doc_source_id="parl_initiative_docs",
                    doc_kind="bocg",
                    only_vote_linked=True,
                    limit_initiatives=0,
                    dry_run=False,
                )
                self.assertEqual(summary["versions_upserted"], 2)
                self.assertEqual(summary["vote_links_upserted"], 2)

                versions = conn.execute(
                    """
                    SELECT document_code, version_order, published_date, stage_kind
                    FROM parl_initiative_text_versions
                    WHERE initiative_id = 'i1'
                    ORDER BY version_order ASC
                    """
                ).fetchall()
                self.assertEqual([row["stage_kind"] for row in versions], ["initial_text", "senate_amendments"])
                self.assertEqual([row["published_date"] for row in versions], ["2024-06-14", "2024-12-10"])

                links = conn.execute(
                    """
                    SELECT vt.vote_event_id, vt.link_method, tv.version_order, tv.stage_kind
                    FROM parl_vote_event_text_versions vt
                    JOIN parl_initiative_text_versions tv
                      ON tv.initiative_text_version_id = vt.initiative_text_version_id
                    WHERE vt.initiative_id = 'i1'
                    ORDER BY vt.vote_event_id ASC
                    """
                ).fetchall()
                by_vote = {row["vote_event_id"]: row for row in links}
                self.assertEqual(by_vote["v_intro"]["link_method"], "initial_version_for_intro_vote")
                self.assertEqual(by_vote["v_intro"]["version_order"], 1)
                self.assertEqual(by_vote["v_senado"]["link_method"], "latest_prior_stage_match")
                self.assertEqual(by_vote["v_senado"]["version_order"], 2)

                bundle = write_evidence_bundle(
                    conn,
                    {
                        "task_id": "i1",
                        "initiative_id": "i1",
                        "source_id": "congreso_iniciativas",
                        "expediente": "121/000023/0000",
                        "initiative_title": "Proyecto de Ley de prueba.",
                        "initiative_type": "Proyecto de ley",
                        "supertype": "Función legislativa",
                        "procedure_type": "Urgente",
                        "current_status": "Cerrado",
                        "initiative_source_url": "https://example.org/i1",
                    },
                    doc_source_id="parl_initiative_docs",
                    evidence_root=Path(td) / "evidence",
                    max_bocg_docs=1,
                )
                payload = json.loads((Path(bundle) / "task.json").read_text(encoding="utf-8"))
                self.assertEqual(len(payload["text_versions"]), 2)
                self.assertEqual(len(payload["vote_text_versions"]), 2)
                self.assertEqual(len(payload["materialized_docs"]), 1)
                self.assertEqual(payload["materialized_docs"][0]["stage_kind"], "senate_amendments")
                key_votes = {row["vote_event_id"]: row for row in payload["key_vote_candidates"]}
                self.assertEqual(key_votes["v_intro"]["recommended_text_stage_kind"], "initial_text")
                self.assertEqual(key_votes["v_senado"]["recommended_text_stage_kind"], "senate_amendments")
            finally:
                conn.close()

    def test_senado_versions_use_url_families_and_skip_shell_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "senado_versions.db"
            ini_doc = Path(td) / "senado_ini.xml"
            amendments_doc = Path(td) / "senado_enmiendas.xml"
            shell_doc = Path(td) / "senado_shell.html"
            ini_doc.write_text(
                "<root><p>Proyecto de Ley de prueba del Senado. 25/03/24 02/04/24 15 621/000001.</p></root>",
                encoding="utf-8",
            )
            amendments_doc.write_text(
                "<root><p>Propuestas de veto. Total de enmiendas 147. Grupo Parlamentario Popular.</p></root>",
                encoding="utf-8",
            )
            shell_doc.write_text(
                "<html><title>Iniciativas parlamentarias | Senado de España</title><script>!function(){var x='boomerang';}</script></html>",
                encoding="utf-8",
            )

            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (?, 'parl_initiative_docs', ?)",
                    [(11, "sen-ini"), (12, "sen-enm"), (13, "sen-shell")],
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES ('s1', 'senado_iniciativas', 'Proyecto de Ley de prueba del Senado.')
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('s1', 'bocg', ?, ?)
                    """,
                    [
                        ("https://www.senado.es/legis15/expedientes/621/xml/INI-3-621000001.xml", 11),
                        ("https://www.senado.es/legis15/expedientes/621/enmiendas/global_enmiendas_vetos_15_621000001.xml", 12),
                        ("https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=621&numEx=000001", 13),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, raw_path, text_excerpt, text_chars)
                    VALUES ('parl_initiative_docs', ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "https://www.senado.es/legis15/expedientes/621/xml/INI-3-621000001.xml",
                            11,
                            "text/xml",
                            str(ini_doc),
                            "Proyecto de Ley de prueba del Senado. 25/03/24 02/04/24 15 621/000001.",
                            90,
                        ),
                        (
                            "https://www.senado.es/legis15/expedientes/621/enmiendas/global_enmiendas_vetos_15_621000001.xml",
                            12,
                            "text/xml",
                            str(amendments_doc),
                            "Propuestas de veto. Total de enmiendas 147. Grupo Parlamentario Popular.",
                            95,
                        ),
                        (
                            "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=621&numEx=000001",
                            13,
                            "text/html;charset=UTF-8",
                            str(shell_doc),
                            "Iniciativas parlamentarias | Senado de España !function(){var x='boomerang';}",
                            120,
                        ),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, vote_date, source_id, title, subgroup_title, subgroup_text,
                      expediente_text, totals_yes, totals_no, totals_abstain
                    )
                    VALUES (?, ?, 'senado_votaciones', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "v_enm",
                            "2024-05-08",
                            "Enmienda número 50. Autor/es: GRUPO PARLAMENTARIO X",
                            "",
                            "",
                            "Proyecto de Ley de prueba del Senado.",
                            140,
                            120,
                            3,
                        ),
                        (
                            "v_final",
                            "2024-05-27",
                            "Votación final sobre el conjunto",
                            "",
                            "",
                            "Proyecto de Ley de prueba del Senado.",
                            150,
                            110,
                            1,
                        ),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, 's1')",
                    [("v_enm",), ("v_final",)],
                )
                conn.commit()

                summary = backfill_versions(
                    conn,
                    initiative_source_ids=("senado_iniciativas",),
                    doc_source_id="parl_initiative_docs",
                    doc_kind="bocg",
                    only_vote_linked=True,
                    limit_initiatives=0,
                    dry_run=False,
                )
                self.assertEqual(summary["versions_upserted"], 2)
                self.assertEqual(summary["docs_skipped"], 1)
                self.assertEqual(summary["vote_links_upserted"], 2)

                versions = conn.execute(
                    """
                    SELECT document_code, version_order, published_date, stage_kind
                    FROM parl_initiative_text_versions
                    WHERE initiative_id = 's1'
                    ORDER BY version_order ASC
                    """
                ).fetchall()
                self.assertEqual([row["stage_kind"] for row in versions], ["initial_text", "senate_amendments"])
                self.assertEqual(str(versions[0]["document_code"]), "SENADO-INI-3-15-621-621000001")
                self.assertEqual(str(versions[0]["published_date"]), "2024-03-25")
                self.assertEqual(str(versions[1]["document_code"]), "SENADO-ENMIENDAS-15-621-621000001")

                links = conn.execute(
                    """
                    SELECT vt.vote_event_id, vt.link_method, tv.version_order, tv.stage_kind
                    FROM parl_vote_event_text_versions vt
                    JOIN parl_initiative_text_versions tv
                      ON tv.initiative_text_version_id = vt.initiative_text_version_id
                    WHERE vt.initiative_id = 's1'
                    ORDER BY vt.vote_event_id ASC
                    """
                ).fetchall()
                by_vote = {row["vote_event_id"]: row for row in links}
                self.assertEqual(by_vote["v_enm"]["link_method"], "latest_prior_stage_match")
                self.assertEqual(by_vote["v_enm"]["version_order"], 2)
                self.assertEqual(by_vote["v_final"]["link_method"], "latest_prior_stage_match")
                self.assertEqual(by_vote["v_final"]["stage_kind"], "senate_amendments")
            finally:
                conn.close()

    def test_senado_tipo_fich_html_with_gzipped_raw_and_detail_content_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "senado_gzip_detail.db"
            detail_doc = Path(td) / "senado_detail.html"
            detail_html = (
                "<html><head><title>Iniciativas parlamentarias | Senado de España</title></head>"
                "<body><script>!function(){var x='boomerang';}</script>"
                "<h1>Proposición de Ley por la que se modifica el apartado Uno, punto 2, del artículo 91"
                " de la Ley 37/1992, de 28 de diciembre, del Impuesto sobre el Valor Añadido.</h1>"
                "<div>Datos abiertos</div>"
                "<div>Autor: GRUPO PARLAMENTARIO POPULAR EN EL SENADO.</div>"
                "<div>Situación: Tomado en consideración.</div>"
                "<div>Fecha de presentación: 21/09/23</div>"
                "<div>Procedimiento: Ordinario.</div>"
                "<div>Tramitación seguida: Tomado en consideración.</div>"
                "</body></html>"
            )
            detail_doc.write_bytes(gzip.compress(detail_html.encode("utf-8")))

            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (21, 'parl_initiative_docs', 'sen-gzip-detail')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      's2',
                      'senado_iniciativas',
                      'Proposición de Ley por la que se modifica el apartado Uno, punto 2, del artículo 91 de la Ley 37/1992, de 28 de diciembre, del Impuesto sobre el Valor Añadido.'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (
                      's2',
                      'bocg',
                      'https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=622&numEx=000006',
                      21
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, raw_path, text_excerpt, text_chars)
                    VALUES (
                      'parl_initiative_docs',
                      'https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=622&numEx=000006',
                      21,
                      'text/html;charset=UTF-8',
                      ?,
                      '�^H',
                      4
                    )
                    """,
                    (str(detail_doc),),
                )
                conn.commit()

                summary = backfill_versions(
                    conn,
                    initiative_source_ids=("senado_iniciativas",),
                    doc_source_id="parl_initiative_docs",
                    doc_kind="bocg",
                    only_vote_linked=False,
                    limit_initiatives=0,
                    dry_run=False,
                )
                self.assertEqual(summary["versions_upserted"], 1)
                self.assertEqual(summary["docs_skipped"], 0)

                version = conn.execute(
                    """
                    SELECT document_code, version_order, published_date, stage_kind
                    FROM parl_initiative_text_versions
                    WHERE initiative_id = 's2'
                    """
                ).fetchone()
                self.assertIsNotNone(version)
                self.assertEqual(str(version["document_code"]), "SENADO-INI-3-15-622-000006")
                self.assertEqual(int(version["version_order"]), 1)
                self.assertEqual(str(version["published_date"]), "2023-09-21")
                self.assertEqual(str(version["stage_kind"]), "initial_text")
            finally:
                conn.close()

    def test_backfill_can_filter_specific_initiative_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "filter_versions.db"
            doc1 = Path(td) / "doc1.xml"
            doc2 = Path(td) / "doc2.xml"
            doc1.write_text("<root><p>14 de junio de 2024. PROYECTO DE LEY.</p></root>", encoding="utf-8")
            doc2.write_text("<root><p>15 de junio de 2024. PROYECTO DE LEY.</p></root>", encoding="utf-8")

            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (?, 'parl_initiative_docs', ?)",
                    [(1, "doc-1"), (2, "doc-2")],
                )
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id, title) VALUES (?, 'congreso_iniciativas', ?)",
                    [("i1", "Proyecto de Ley A"), ("i2", "Proyecto de Ley B")],
                )
                conn.executemany(
                    "INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk) VALUES (?, 'bocg', ?, ?)",
                    [
                        ("i1", "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BOCG-15-A-10-1.PDF", 1),
                        ("i2", "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BOCG-15-A-11-1.PDF", 2),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, raw_path, text_excerpt, text_chars)
                    VALUES ('parl_initiative_docs', ?, ?, 'text/xml', ?, ?, ?)
                    """,
                    [
                        (
                            "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BOCG-15-A-10-1.PDF",
                            1,
                            str(doc1),
                            "14 de junio de 2024. PROYECTO DE LEY.",
                            40,
                        ),
                        (
                            "https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BOCG-15-A-11-1.PDF",
                            2,
                            str(doc2),
                            "15 de junio de 2024. PROYECTO DE LEY.",
                            40,
                        ),
                    ],
                )
                conn.commit()

                summary = backfill_versions(
                    conn,
                    initiative_source_ids=("congreso_iniciativas",),
                    initiative_ids=("i2",),
                    doc_source_id="parl_initiative_docs",
                    doc_kind="bocg",
                    only_vote_linked=False,
                    limit_initiatives=0,
                    dry_run=False,
                )
                self.assertEqual(summary["initiatives_seen"], 1)
                self.assertEqual(summary["versions_upserted"], 1)
                versions = conn.execute(
                    "SELECT initiative_id FROM parl_initiative_text_versions ORDER BY initiative_id ASC"
                ).fetchall()
                self.assertEqual([str(row["initiative_id"]) for row in versions], ["i2"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
