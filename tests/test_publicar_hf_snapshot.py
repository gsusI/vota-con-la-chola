from __future__ import annotations

import csv
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.publicar_hf_snapshot import (
    build_dataset_readme,
    build_explorer_schema_payload,
    collect_published_files,
    ensure_liberty_atlas_release_latest_for_publish,
    ensure_quality_report_for_publish,
    extract_quality_report_summary,
    export_source_legal_metadata,
    export_ingestion_runs_csv,
    load_dotenv,
    resolve_source_legal_profile,
    sanitize_url_for_public,
)


class PublicarHFSnapshotTests(unittest.TestCase):
    def test_load_dotenv_parses_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    (
                        "# comment",
                        "HF_TOKEN=abc123",
                        "export HF_USERNAME='jesus'",
                        "HF_DATASET_REPO_ID=\"org/data\"",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            values = load_dotenv(env_path)
            self.assertEqual(values["HF_TOKEN"], "abc123")
            self.assertEqual(values["HF_USERNAME"], "jesus")
            self.assertEqual(values["HF_DATASET_REPO_ID"], "org/data")

    def test_collect_published_files_prefers_gz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            published_dir = Path(tmp)
            (published_dir / "votaciones-es-2026-02-12.json").write_text("{}", encoding="utf-8")
            (published_dir / "votaciones-es-2026-02-12.json.gz").write_text("gz", encoding="utf-8")
            (published_dir / "representantes-es-2026-02-12.json").write_text("{}", encoding="utf-8")
            (published_dir / "liberty-restrictions-atlas-release-latest.json").write_text(
                json.dumps({"status": "ok", "snapshot_date": "2026-02-12"}, ensure_ascii=True),
                encoding="utf-8",
            )
            (published_dir / "proximas-elecciones-espana.json").write_text("{}", encoding="utf-8")
            (published_dir / "poblacion_municipios_es.json").write_text("{}", encoding="utf-8")

            files = collect_published_files(published_dir, "2026-02-12")
            names = [path.name for path in files]
            self.assertIn("votaciones-es-2026-02-12.json.gz", names)
            self.assertNotIn("votaciones-es-2026-02-12.json", names)
            self.assertIn("representantes-es-2026-02-12.json", names)
            self.assertIn("proximas-elecciones-espana.json", names)
            self.assertIn("liberty-restrictions-atlas-release-latest.json", names)

    def test_ensure_liberty_atlas_release_latest_for_publish_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            published_dir = Path(tmp)
            latest_path = published_dir / "liberty-restrictions-atlas-release-latest.json"
            latest_path.write_text(
                json.dumps({"status": "ok", "snapshot_date": "2026-02-12"}, ensure_ascii=True),
                encoding="utf-8",
            )

            summary = ensure_liberty_atlas_release_latest_for_publish(
                published_dir=published_dir,
                snapshot_date="2026-02-12",
                require_release_latest=True,
            )
            self.assertEqual(summary["file_name"], "liberty-restrictions-atlas-release-latest.json")
            self.assertEqual(summary["snapshot_date"], "2026-02-12")
            self.assertEqual(summary["status"], "ok")

    def test_ensure_liberty_atlas_release_latest_for_publish_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                ensure_liberty_atlas_release_latest_for_publish(
                    published_dir=Path(tmp),
                    snapshot_date="2026-02-12",
                    require_release_latest=True,
                )
        self.assertIn("liberty-restrictions-atlas-release-latest.json", str(ctx.exception))

    def test_ensure_liberty_atlas_release_latest_for_publish_snapshot_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            published_dir = Path(tmp)
            latest_path = published_dir / "liberty-restrictions-atlas-release-latest.json"
            latest_path.write_text(
                json.dumps({"status": "ok", "snapshot_date": "2026-02-11"}, ensure_ascii=True),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as ctx:
                ensure_liberty_atlas_release_latest_for_publish(
                    published_dir=published_dir,
                    snapshot_date="2026-02-12",
                    require_release_latest=True,
                )
        self.assertIn("no coincide", str(ctx.exception))

    def test_ensure_quality_report_for_publish_allows_empty_when_not_required(self) -> None:
        ensure_quality_report_for_publish(
            {},
            require_quality_report=False,
            snapshot_date="2026-02-12",
            published_dir=Path("etl/data/published"),
        )

    def test_ensure_quality_report_for_publish_fails_when_required_and_missing(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            ensure_quality_report_for_publish(
                {},
                require_quality_report=True,
                snapshot_date="2026-02-12",
                published_dir=Path("etl/data/published"),
            )
        self.assertIn("No se encontró quality_report", str(ctx.exception))

    def test_ensure_quality_report_for_publish_requires_vote_gate_key(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            ensure_quality_report_for_publish(
                {"file_name": "votaciones-kpis-es-2026-02-12.json"},
                require_quality_report=True,
                snapshot_date="2026-02-12",
                published_dir=Path("etl/data/published"),
            )
        self.assertIn("vote_gate_passed", str(ctx.exception))

    def test_extract_quality_report_summary_from_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            published_dir = Path(tmp)
            report_path = published_dir / "votaciones-kpis-es-2026-02-12.json"
            report_path.write_text(
                json.dumps(
                    {
                        "gate": {"passed": True},
                        "kpis": {
                            "events_total": 123,
                            "member_votes_with_person_id_pct": 0.98,
                        },
                        "initiatives": {
                            "gate": {"passed": True},
                            "kpis": {
                                "downloaded_doc_links": 44,
                                "missing_doc_links_actionable": 0,
                                "extraction_coverage_pct": 1.0,
                                "extraction_review_closed_pct": 1.0,
                            },
                        },
                    },
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            summary = extract_quality_report_summary([report_path], "2026-02-12")
            self.assertEqual(summary["file_name"], "votaciones-kpis-es-2026-02-12.json")
            self.assertTrue(summary["vote_gate_passed"])
            self.assertTrue(summary["initiative_gate_passed"])
            self.assertEqual(summary["events_total"], 123)
            self.assertEqual(summary["downloaded_doc_links"], 44)
            self.assertEqual(summary["missing_doc_links_actionable"], 0)
            self.assertEqual(summary["extraction_coverage_pct"], 1.0)
            self.assertEqual(summary["extraction_review_closed_pct"], 1.0)

    def test_extract_quality_report_summary_from_gz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            published_dir = Path(tmp)
            report_path = published_dir / "votaciones-kpis-es-2026-02-12.json.gz"
            with gzip.open(report_path, "wt", encoding="utf-8") as fh:
                json.dump(
                    {
                        "gate": {"passed": False},
                        "kpis": {"events_total": 7},
                    },
                    fh,
                    ensure_ascii=True,
                )
            summary = extract_quality_report_summary([report_path], "2026-02-12")
            self.assertEqual(summary["file_name"], "votaciones-kpis-es-2026-02-12.json.gz")
            self.assertFalse(summary["vote_gate_passed"])
            self.assertEqual(summary["events_total"], 7)

    def test_export_ingestion_runs_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sample.db"
            out_csv = Path(tmp) / "ingestion_runs.csv"
            conn = sqlite3.connect(str(db_path))
            try:
                conn.executescript(
                    """
                    CREATE TABLE ingestion_runs (
                      run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      source_id TEXT NOT NULL,
                      started_at TEXT NOT NULL,
                      finished_at TEXT,
                      status TEXT NOT NULL,
                      source_url TEXT NOT NULL,
                      records_seen INTEGER NOT NULL DEFAULT 0,
                      records_loaded INTEGER NOT NULL DEFAULT 0,
                      message TEXT
                    );
                    INSERT INTO ingestion_runs
                      (source_id, started_at, finished_at, status, source_url, records_seen, records_loaded, message)
                    VALUES
                      ('congreso_diputados', '2026-02-12T00:00:00Z', '2026-02-12T00:00:01Z', 'ok', 'https://x', 10, 10, '');
                    """
                )
                conn.commit()
            finally:
                conn.close()

            rows = export_ingestion_runs_csv(db_path, out_csv)
            self.assertEqual(rows, 1)
            with out_csv.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.reader(fh)
                data = list(reader)
            self.assertEqual(data[0][0], "run_id")
            self.assertEqual(data[1][1], "congreso_diputados")

    def test_export_ingestion_runs_csv_redacts_sensitive_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sample.db"
            out_csv = Path(tmp) / "ingestion_runs.csv"
            conn = sqlite3.connect(str(db_path))
            try:
                conn.executescript(
                    """
                    CREATE TABLE ingestion_runs (
                      run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      source_id TEXT NOT NULL,
                      started_at TEXT NOT NULL,
                      finished_at TEXT,
                      status TEXT NOT NULL,
                      source_url TEXT NOT NULL,
                      records_seen INTEGER NOT NULL DEFAULT 0,
                      records_loaded INTEGER NOT NULL DEFAULT 0,
                      message TEXT
                    );
                    INSERT INTO ingestion_runs
                      (source_id, started_at, finished_at, status, source_url, records_seen, records_loaded, message)
                    VALUES
                      (
                        'bdns_api_subvenciones',
                        '2026-02-12T00:00:00Z',
                        '2026-02-12T00:00:01Z',
                        'ok',
                        'https://api.example.com/data?api_key=abc123secret&public=1',
                        1,
                        1,
                        'Authorization: Bearer hf_abcdefghijklmnopqrstuvwxyz01234567'
                      );
                    """
                )
                conn.commit()
            finally:
                conn.close()

            rows = export_ingestion_runs_csv(db_path, out_csv)
            self.assertEqual(rows, 1)
            with out_csv.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.reader(fh)
                data = list(reader)
            self.assertEqual(data[1][5], "https://api.example.com/data?api_key=REDACTED&public=1")
            self.assertEqual(data[1][8], "Authorization: Bearer REDACTED")

    def test_sanitize_url_for_public_removes_credentials(self) -> None:
        safe = sanitize_url_for_public("https://user:pass@example.org/x?token=123&ok=1")
        self.assertEqual(safe, "https://example.org/x?token=REDACTED&ok=1")

    def test_sanitize_url_for_public_removes_local_file_scheme(self) -> None:
        safe = sanitize_url_for_public("file:///Users/alice/private/source.json")
        self.assertEqual(safe, "")

    def test_export_ingestion_runs_csv_redacts_local_path_and_email(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sample.db"
            out_csv = Path(tmp) / "ingestion_runs.csv"
            conn = sqlite3.connect(str(db_path))
            try:
                conn.executescript(
                    """
                    CREATE TABLE ingestion_runs (
                      run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      source_id TEXT NOT NULL,
                      started_at TEXT NOT NULL,
                      finished_at TEXT,
                      status TEXT NOT NULL,
                      source_url TEXT NOT NULL,
                      records_seen INTEGER NOT NULL DEFAULT 0,
                      records_loaded INTEGER NOT NULL DEFAULT 0,
                      message TEXT
                    );
                    INSERT INTO ingestion_runs
                      (source_id, started_at, finished_at, status, source_url, records_seen, records_loaded, message)
                    VALUES
                      (
                        'congreso_votaciones',
                        '2026-02-12T00:00:00Z',
                        '2026-02-12T00:00:01Z',
                        'ok',
                        'file:///Users/alice/Library/CloudStorage/GoogleDrive-alice@example.com/repo/vote.json',
                        1,
                        1,
                        'loaded from /Users/alice/private with contact alice@example.com'
                      );
                    """
                )
                conn.commit()
            finally:
                conn.close()

            rows = export_ingestion_runs_csv(db_path, out_csv)
            self.assertEqual(rows, 1)
            with out_csv.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.reader(fh)
                data = list(reader)
            self.assertEqual(data[1][5], "")
            self.assertNotIn("/Users/alice", data[1][8])
            self.assertNotIn("alice@example.com", data[1][8])

    def test_build_explorer_schema_payload_includes_fk_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "schema.db"
            conn = sqlite3.connect(str(db_path))
            try:
                conn.executescript(
                    """
                    CREATE TABLE institutions (
                      institution_id INTEGER PRIMARY KEY,
                      name TEXT
                    );
                    CREATE TABLE mandates (
                      mandate_id INTEGER PRIMARY KEY,
                      institution_id INTEGER NOT NULL,
                      role_title TEXT,
                      FOREIGN KEY (institution_id) REFERENCES institutions(institution_id)
                    );
                    """
                )
                conn.commit()
            finally:
                conn.close()

            payload = build_explorer_schema_payload(db_path)
            self.assertIn("tables", payload)
            tables = {row["name"]: row for row in payload["tables"]}
            self.assertIn("mandates", tables)
            self.assertIn("institutions", tables)
            self.assertEqual(tables["mandates"]["primary_key"], ["mandate_id"])
            self.assertEqual(tables["mandates"]["foreign_keys_out"][0]["to_table"], "institutions")
            self.assertEqual(tables["institutions"]["foreign_keys_in"][0]["from_table"], "mandates")

    def test_resolve_source_legal_profile_known_and_unknown(self) -> None:
        known = resolve_source_legal_profile(
            "senado_senadores",
            "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html",
        )
        self.assertEqual(known["verification_status"], "verified")
        self.assertIn("CC BY 4.0", known["reuse_basis"])

        unknown = resolve_source_legal_profile("fuente_no_catalogada", "https://example.org/data")
        self.assertEqual(unknown["verification_status"], "pending_review")
        self.assertEqual(unknown["terms_url"], "https://example.org/data")

    def test_export_source_legal_metadata_writes_per_source_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_dir = Path(tmp)
            rel_paths, rows = export_source_legal_metadata(
                snapshot_dir=snapshot_dir,
                snapshot_date="2026-02-12",
                source_records_counts={"senado_senadores": 12, "europarl_meps": 5},
                sources_catalog={
                    "senado_senadores": {
                        "name": "Senado - Senadores",
                        "scope": "nacional",
                        "default_url": "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html",
                    },
                    "europarl_meps": {
                        "name": "Parlamento Europeo - MEPs",
                        "scope": "europeo",
                        "default_url": "https://www.europarl.europa.eu/meps/es/full-list/xml",
                    },
                },
            )
            self.assertEqual(len(rel_paths), 2)
            self.assertEqual(len(rows), 2)
            senado_file = snapshot_dir / "sources" / "senado_senadores.json"
            self.assertTrue(senado_file.exists())
            payload = senado_file.read_text(encoding="utf-8")
            self.assertIn('"verification_status": "verified"', payload)
            self.assertIn('"records_in_snapshot": 12', payload)

    def test_build_dataset_readme_includes_legal_sections(self) -> None:
        readme = build_dataset_readme(
            dataset_repo="org/data",
            snapshot_date="2026-02-12",
            snapshot_rel_dir=Path("snapshots/2026-02-12"),
            parquet_tables=[],
            parquet_excluded_tables=["source_records"],
            source_legal_entries=[
                {
                    "source_id": "senado_senadores",
                    "records": 12,
                    "status": "verified",
                    "reuse_basis": "CC BY 4.0 (datos abiertos del Senado)",
                    "terms_url": "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html",
                }
            ],
            include_sqlite_gz=False,
            source_repo_url="https://github.com/example/repo",
        )
        self.assertIn("license: other", readme)
        self.assertIn("Contenido por snapshot (capas raw + processed)", readme)
        self.assertIn("Resumen legal por fuente", readme)
        self.assertIn("senado_senadores", readme)
        self.assertIn("Cautelas de cumplimiento", readme)

    def test_build_dataset_readme_includes_quality_summary(self) -> None:
        readme = build_dataset_readme(
            dataset_repo="org/data",
            snapshot_date="2026-02-12",
            snapshot_rel_dir=Path("snapshots/2026-02-12"),
            parquet_tables=[],
            parquet_excluded_tables=[],
            source_legal_entries=[],
            include_sqlite_gz=False,
            source_repo_url="https://github.com/example/repo",
            quality_summary={
                "file_name": "votaciones-kpis-es-2026-02-12.json",
                "vote_gate_passed": True,
                "initiative_gate_passed": True,
                "events_total": 321,
                "downloaded_doc_links": 55,
                "missing_doc_links_actionable": 0,
                "extraction_coverage_pct": 1.0,
                "extraction_review_closed_pct": 1.0,
            },
        )
        self.assertIn("published/votaciones-kpis-es-2026-02-12.json", readme)
        self.assertIn("Resumen de calidad del snapshot", readme)
        self.assertIn("Vote gate: PASS", readme)
        self.assertIn("Initiative gate: PASS", readme)
        self.assertIn("Eventos analizados: 321", readme)
        self.assertIn("Cobertura de extracción en docs descargados: 100.0%", readme)


if __name__ == "__main__":
    unittest.main()
