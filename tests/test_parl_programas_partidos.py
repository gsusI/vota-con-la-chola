from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.declared_positions import backfill_topic_positions_from_declared_evidence
from etl.parlamentario_es.declared_stance import backfill_declared_stance_from_topic_evidence
from etl.parlamentario_es.pipeline import (
    _extract_program_pdf_text,
    _is_programmatic_program_doc,
    _programa_keyword_excerpt_window,
    ingest_one_source as ingest_parl_source,
)
from etl.parlamentario_es.registry import get_connectors
from etl.politicos_es.db import seed_dimensions
from etl.politicos_es.util import normalize_key_part, now_utc_iso, sha256_bytes


def _seed_min_programas_prereqs(conn) -> None:  # type: ignore[no-untyped-def]
    now = now_utc_iso()
    seed_dimensions(conn)

    # Minimal territory anchor used by programas topic_set.
    conn.execute(
        """
        INSERT INTO territories (code, name, level, parent_territory_id, created_at, updated_at)
        VALUES ('ES', 'España', 'nacional', NULL, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          name=excluded.name,
          level=excluded.level,
          updated_at=excluded.updated_at
        """,
        (now, now),
    )

    # Minimal parties referenced by the sample manifest.
    for pid, name in ((1, "PSOE"), (2, "PP"), (29, "SUMAR")):
        conn.execute(
            """
            INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(party_id) DO UPDATE SET
              name=excluded.name,
              acronym=excluded.acronym,
              updated_at=excluded.updated_at
            """,
            (int(pid), str(name), str(name), now, now),
        )
    conn.commit()


class TestParlProgramasPartidos(unittest.TestCase):
    def test_is_programmatic_program_doc_heuristics(self) -> None:
        ok_url, ok_url_reason = _is_programmatic_program_doc(
            source_url="https://partido.example/programa-electoral-2027",
            text_for_matching="Portada del programa.",
            concern_keywords_norm=["vivienda", "empleo"],
        )
        ok_pair, ok_pair_reason = _is_programmatic_program_doc(
            source_url="https://partido.example/actualidad",
            text_for_matching="Proponemos mejorar la vivienda asequible y el empleo juvenil.",
            concern_keywords_norm=["vivienda", "empleo"],
        )
        ok_pair_ca, ok_pair_ca_reason = _is_programmatic_program_doc(
            source_url="https://partido.example/actualitat",
            text_for_matching="Proposem canviar el model energetic i lluita contra la corrupcio.",
            concern_keywords_norm=["energia", "corrupcio"],
        )
        noisy_listing, noisy_listing_reason = _is_programmatic_program_doc(
            source_url="https://partido.example/programas-electorales",
            text_for_matching=(
                "Menu noticias actualidad siguenos facebook twitter instagram youtube "
                "boletin afiliate contacto etiqueta etiqueta"
            ),
            concern_keywords_norm=["vivienda", "empleo"],
        )
        not_ok, not_ok_reason = _is_programmatic_program_doc(
            source_url="https://partido.example/politica-de-cookies",
            text_for_matching="Este sitio web utiliza cookies y tiene politica de privacidad.",
            concern_keywords_norm=["vivienda", "empleo"],
        )

        self.assertTrue(ok_url)
        self.assertEqual(ok_url_reason, "url_program_hint")
        self.assertTrue(ok_pair)
        self.assertEqual(ok_pair_reason, "policy_pair_hit")
        self.assertTrue(ok_pair_ca)
        self.assertEqual(ok_pair_ca_reason, "policy_pair_hit")
        self.assertFalse(noisy_listing)
        self.assertEqual(noisy_listing_reason, "url_program_but_noisy_listing")
        self.assertFalse(not_ok)
        self.assertIn(not_ok_reason, ("url_non_program_hint", "legal_or_cookie_text"))

    def test_extract_program_pdf_text_falls_back_to_pdftotext(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw_path = Path(td) / "doc.pdf"
            raw_path.write_bytes(b"%PDF-1.4 fake")

            cp = subprocess.CompletedProcess(
                args=["pdftotext", "-enc", "UTF-8", str(raw_path), "-"],
                returncode=0,
                stdout=b"Programa de vivienda y empleo para todos",
                stderr=b"",
            )
            with (
                mock.patch("etl.parlamentario_es.pipeline.subprocess.run", return_value=cp),
                mock.patch.dict("sys.modules", {"pypdf": None, "PyPDF2": None}),
            ):
                out = _extract_program_pdf_text(b"%PDF-1.4 fake", raw_path)
            self.assertIn("vivienda", out)
            self.assertIn("empleo", out)

    def test_programa_keyword_excerpt_window_prefers_policy_verb_near_concern(self) -> None:
        full_norm = (
            "pagina inicio cookies navegacion "
            "proponemos construir vivienda asequible para jovenes y mejorar empleo juvenil "
            "mas texto sin senal"
        )
        excerpt = _programa_keyword_excerpt_window(full_norm, ["vivienda", "empleo"])
        self.assertIn("proponemos", excerpt)
        self.assertIn("vivienda", excerpt)

    def test_programa_keyword_excerpt_window_accepts_multilingual_policy_verbs(self) -> None:
        full_norm = (
            "menu portada avis legal "
            "proposem canviar el model energetic i lluita contra la corrupcio institucional "
            "mes contingut"
        )
        excerpt = _programa_keyword_excerpt_window(full_norm, ["energia", "corrupcio"])
        self.assertIn("canviar", excerpt)
        self.assertIn("corrupcio", excerpt)

    def test_programa_keyword_excerpt_window_drops_numeric_noise_only_blocks(self) -> None:
        full_norm = (
            "programa economico y de vivienda 60000 millones de euros "
            "m 01 20 14 m 01 20 13 m 01 20 12 "
            "solo se dedico a educacion y sanidad en el ultimo ejercicio"
        )
        excerpt = _programa_keyword_excerpt_window(full_norm, ["vivienda", "sanidad"])
        self.assertEqual(excerpt, "")

    def test_programa_keyword_excerpt_window_keeps_actionable_window_with_numbers(self) -> None:
        full_norm = (
            "en 2025 impulsaremos un plan nacional del agua para reforzar la agricultura "
            "y mejorar la vivienda rural"
        )
        excerpt = _programa_keyword_excerpt_window(full_norm, ["agua", "agricultura", "vivienda"])
        self.assertIn("impulsaremos", excerpt)
        self.assertIn("agua", excerpt)

    def test_programa_keyword_excerpt_window_can_avoid_repeated_excerpt(self) -> None:
        filler = " ".join(["contexto"] * 120)
        full_norm = (
            "proponemos construir vivienda asequible para jovenes. "
            f"{filler} "
            "despues proponemos mejorar empleo juvenil con formacion profesional. "
            f"{filler} "
            "tambien proponemos reforzar sanidad publica de proximidad."
        )
        first = _programa_keyword_excerpt_window(full_norm, ["vivienda", "empleo", "sanidad"])
        self.assertIn("proponemos", first)
        first_sig = normalize_key_part(first)[:320]
        self.assertTrue(first_sig)

        second = _programa_keyword_excerpt_window(
            full_norm,
            ["vivienda", "empleo", "sanidad"],
            used_signatures={first_sig},
        )
        second_sig = normalize_key_part(second)[:320]
        self.assertTrue(second_sig)
        self.assertNotEqual(first_sig, second_sig)

    def test_programas_partidos_sample_ingest_is_idempotent_and_traceable(self) -> None:
        connectors = get_connectors()
        connector = connectors["programas_partidos"]
        snapshot_date = "2026-02-17"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "parl-programas.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            server: ThreadingHTTPServer | None = None
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                _seed_min_programas_prereqs(conn)

                manifest_path = Path(PARL_SOURCE_CONFIG["programas_partidos"]["fallback_file"])
                self.assertTrue(manifest_path.exists(), f"Missing sample manifest: {manifest_path}")

                seen1, loaded1, _msg1 = ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )
                self.assertEqual(int(seen1), 3)
                self.assertEqual(int(loaded1), 3)

                # Basic storage counts.
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM source_records WHERE source_id = 'programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    3,
                )
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM text_documents WHERE source_id = 'programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    3,
                )
                evidence_total_1 = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(evidence_total_1, 11)

                # topic_set created exactly once for the election_cycle.
                ts = conn.execute(
                    """
                    SELECT topic_set_id
                    FROM topic_sets
                    WHERE name = 'Programas de partidos'
                      AND legislature = 'es_generales_2023'
                    ORDER BY topic_set_id DESC
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(ts)
                topic_set_id = int(ts["topic_set_id"])
                ts_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_sets
                        WHERE name = 'Programas de partidos'
                          AND legislature = 'es_generales_2023'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(ts_count, 1)

                # Full topic_set_topics list derived from concerns config (stable size).
                concerns = json.loads(Path("ui/citizen/concerns_v1.json").read_text(encoding="utf-8"))["concerns"]
                expected_topics = len(concerns)
                self.assertGreaterEqual(expected_topics, 10)
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM topic_set_topics WHERE topic_set_id = ?",
                            (topic_set_id,),
                        ).fetchone()["c"]
                    ),
                    expected_topics,
                )

                # source_record_id and content_sha256 match the referenced doc bytes.
                rows = conn.execute(
                    """
                    SELECT source_record_id, content_sha256, source_record_pk
                    FROM source_records
                    WHERE source_id = 'programas_partidos'
                    ORDER BY source_record_id ASC
                    """
                ).fetchall()
                self.assertEqual(len(rows), 3)
                pk_by_id = {str(r["source_record_id"]): int(r["source_record_pk"]) for r in rows}

                for party_id, local_path in (
                    (1, "etl/data/raw/samples/programas_partidos/psoe_programa_sample.html"),
                    (2, "etl/data/raw/samples/programas_partidos/pp_programa_sample.html"),
                    (29, "etl/data/raw/samples/programas_partidos/sumar_programa_sample.html"),
                ):
                    srid = f"programas_partidos:es_generales_2023:{int(party_id)}:programa"
                    expected_sha = sha256_bytes(Path(local_path).read_bytes())
                    row = conn.execute(
                        """
                        SELECT content_sha256
                        FROM source_records
                        WHERE source_id = 'programas_partidos' AND source_record_id = ?
                        """,
                        (srid,),
                    ).fetchone()
                    self.assertIsNotNone(row)
                    self.assertEqual(str(row["content_sha256"]), expected_sha)

                # text_documents raw bytes were persisted under the passed raw_dir.
                td = conn.execute(
                    """
                    SELECT raw_path
                    FROM text_documents
                    WHERE source_id = 'programas_partidos'
                    ORDER BY source_record_pk ASC
                    """
                ).fetchall()
                self.assertEqual(len(td), 3)
                for r in td:
                    p = Path(str(r["raw_path"] or ""))
                    self.assertTrue(p.exists(), f"Missing raw bytes file: {p}")
                    self.assertTrue(str(p).startswith(str(raw_dir)), f"raw_path not under raw_dir: {p}")

                # Capture key set for evidence rows (ignore evidence_id autoincrement).
                ev_keys_1 = {
                    (
                        int(r["topic_id"]),
                        int(r["person_id"]),
                        str(r["title"] or ""),
                        int(r["source_record_pk"]),
                    )
                    for r in conn.execute(
                        """
                        SELECT topic_id, person_id, title, source_record_pk
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchall()
                }
                self.assertEqual(len(ev_keys_1), evidence_total_1)
                ev_id_map_1 = {
                    (
                        int(r["topic_id"]),
                        int(r["person_id"]),
                        str(r["title"] or ""),
                        int(r["source_record_pk"]),
                    ): int(r["evidence_id"])
                    for r in conn.execute(
                        """
                        SELECT evidence_id, topic_id, person_id, title, source_record_pk
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchall()
                }

                # Re-run ingest: counts and key sets remain stable; no duplicated topic_sets/institutions.
                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )

                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM source_records WHERE source_id = 'programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    3,
                )
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM text_documents WHERE source_id = 'programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    3,
                )
                evidence_total_2 = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(evidence_total_2, evidence_total_1)

                ev_keys_2 = {
                    (
                        int(r["topic_id"]),
                        int(r["person_id"]),
                        str(r["title"] or ""),
                        int(r["source_record_pk"]),
                    )
                    for r in conn.execute(
                        """
                        SELECT topic_id, person_id, title, source_record_pk
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchall()
                }
                self.assertEqual(ev_keys_1, ev_keys_2)
                ev_id_map_2 = {
                    (
                        int(r["topic_id"]),
                        int(r["person_id"]),
                        str(r["title"] or ""),
                        int(r["source_record_pk"]),
                    ): int(r["evidence_id"])
                    for r in conn.execute(
                        """
                        SELECT evidence_id, topic_id, person_id, title, source_record_pk
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchall()
                }
                self.assertEqual(ev_id_map_1, ev_id_map_2)

                rows2 = conn.execute(
                    """
                    SELECT source_record_id, source_record_pk
                    FROM source_records
                    WHERE source_id = 'programas_partidos'
                    ORDER BY source_record_id ASC
                    """
                ).fetchall()
                pk_by_id_2 = {str(r["source_record_id"]): int(r["source_record_pk"]) for r in rows2}
                self.assertEqual(pk_by_id, pk_by_id_2)

                inst_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM institutions
                        WHERE name = 'Programas de partidos'
                          AND level = 'editorial'
                          AND territory_code = ''
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(inst_count, 1)

                # Declared stance signal should exist for the sample (support + oppose).
                stance_res = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="programas_partidos",
                    limit=0,
                    min_auto_confidence=0.62,
                    enable_review_queue=True,
                    dry_run=False,
                )
                self.assertGreaterEqual(int(stance_res.get("support", 0)), 1)
                self.assertGreaterEqual(int(stance_res.get("oppose", 0)), 1)
                self.assertGreaterEqual(int(stance_res.get("review_pending", 0)), 1)

                # Mark pending rows as ignored to emulate manual closeout.
                conn.execute(
                    """
                    UPDATE topic_evidence_reviews
                    SET status = 'ignored',
                        updated_at = ?
                    WHERE source_id = 'programas_partidos'
                      AND status = 'pending'
                    """,
                    (now_utc_iso(),),
                )
                conn.commit()
                ignored_before = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_evidence_reviews
                        WHERE source_id = 'programas_partidos'
                          AND status = 'ignored'
                        """
                    ).fetchone()["c"]
                )
                self.assertGreaterEqual(ignored_before, 1)

                # Re-run ingest + declared stance: ignored decisions must persist.
                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )
                stance_res_rerun = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="programas_partidos",
                    limit=0,
                    min_auto_confidence=0.62,
                    enable_review_queue=True,
                    dry_run=False,
                )
                self.assertEqual(int(stance_res_rerun.get("review_pending", 0)), 0)
                ignored_after = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_evidence_reviews
                        WHERE source_id = 'programas_partidos'
                          AND status = 'ignored'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(ignored_after, ignored_before)

                # Declared positions should be computable from the signaled rows.
                pos_res = backfill_topic_positions_from_declared_evidence(
                    conn,
                    source_id="programas_partidos",
                    as_of_date=snapshot_date,
                    computed_method="declared",
                    computed_version="v1",
                    dry_run=False,
                )
                self.assertGreaterEqual(int(pos_res.get("positions_total", 0)), 1)

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()

    def test_programas_partidos_keeps_traceability_but_skips_non_program_evidence(self) -> None:
        connectors = get_connectors()
        connector = connectors["programas_partidos"]
        snapshot_date = "2026-02-28"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "parl-programas-non-program-filter.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            program_html = td_path / "programa.html"
            program_html.write_text(
                "<html><body><h1>Programa</h1><p>Proponemos mejorar vivienda y empleo juvenil.</p></body></html>",
                encoding="utf-8",
            )
            non_program_html = td_path / "cookies.html"
            non_program_html.write_text(
                "<html><body><h1>Politica de cookies</h1><p>Este sitio web utiliza cookies.</p></body></html>",
                encoding="utf-8",
            )
            manifest_path = td_path / "programas_filter_manifest.csv"
            manifest_path.write_text(
                "\n".join(
                    [
                        "party_id,party_name,election_cycle,kind,source_url,format_hint,language,scope,snapshot_date,local_path,notes",
                        f"1,PSOE,es_generales_2023,programa,https://example.invalid/programa,html,es,nacional,{snapshot_date},{program_html},test",
                        f"2,PP,es_generales_2023,programa,https://example.invalid/politica-de-cookies,html,es,nacional,{snapshot_date},{non_program_html},test",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                _seed_min_programas_prereqs(conn)

                seen, loaded, msg = ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )
                self.assertEqual(int(seen), 2)
                self.assertEqual(int(loaded), 2)
                msg_obj = json.loads(str(msg or "{}"))
                skipped = (((msg_obj.get("out") or {}).get("info") or {}).get("skipped") or {})
                non_program_skips = int(skipped.get("non_program_doc", 0))
                self.assertEqual(
                    non_program_skips,
                    1,
                )

                sr_count = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM source_records WHERE source_id = 'programas_partidos'"
                    ).fetchone()["c"]
                )
                td_count = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM text_documents WHERE source_id = 'programas_partidos'"
                    ).fetchone()["c"]
                )
                ev_total = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchone()["c"]
                )
                ev_for_party_2 = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_evidence e
                        JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
                        WHERE e.source_id = 'programas_partidos'
                          AND sr.source_record_id = 'programas_partidos:es_generales_2023:2:programa'
                        """
                    ).fetchone()["c"]
                )

                self.assertEqual(sr_count, 2)
                self.assertEqual(td_count, 2)
                self.assertGreaterEqual(ev_total, 1)
                self.assertEqual(ev_for_party_2, 0)
            finally:
                conn.close()


    def test_programas_partidos_network_docs_promote_run_fetch_url_to_http(self) -> None:
        connectors = get_connectors()
        connector = connectors["programas_partidos"]
        snapshot_date = "2026-02-28"

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                _ = (format, args)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "parl-programas-network.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                _seed_min_programas_prereqs(conn)

                server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
                server.RequestHandlerClass.directory = str(Path('.').resolve())
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                port = int(server.server_port)

                manifest_path = td_path / "programas_manifest_http.csv"
                manifest_path.write_text(
                    "\n".join(
                        [
                            "party_id,party_name,election_cycle,kind,source_url,format_hint,language,scope,snapshot_date,local_path,notes",
                            f"1,PSOE,es_generales_2023,programa,http://127.0.0.1:{port}/etl/data/raw/samples/programas_partidos/psoe_programa_sample.html,html,es,nacional,{snapshot_date},,test",
                            f"2,PP,es_generales_2023,programa,http://127.0.0.1:{port}/etl/data/raw/samples/programas_partidos/pp_programa_sample.html,html,es,nacional,{snapshot_date},,test",
                            f"29,SUMAR,es_generales_2023,programa,http://127.0.0.1:{port}/etl/data/raw/samples/programas_partidos/sumar_programa_sample.html,html,es,nacional,{snapshot_date},,test",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )

                seen, loaded, _msg = ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=10,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )
                self.assertEqual(int(seen), 3)
                self.assertEqual(int(loaded), 3)

                row = conn.execute(
                    """
                    SELECT rf.source_url
                    FROM run_fetches rf
                    JOIN ingestion_runs ir ON ir.run_id = rf.run_id
                    WHERE ir.source_id = 'programas_partidos'
                    ORDER BY ir.run_id DESC
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertTrue(str(row["source_url"]).startswith("http://127.0.0.1:"))
            finally:
                try:
                    if server is not None:
                        server.shutdown()
                        server.server_close()
                except Exception:
                    pass
                conn.close()


if __name__ == "__main__":
    unittest.main()
