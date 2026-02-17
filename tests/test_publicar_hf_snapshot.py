from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.publicar_hf_snapshot import (
    build_explorer_schema_payload,
    collect_published_files,
    export_ingestion_runs_csv,
    load_dotenv,
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
            (published_dir / "proximas-elecciones-espana.json").write_text("{}", encoding="utf-8")
            (published_dir / "poblacion_municipios_es.json").write_text("{}", encoding="utf-8")

            files = collect_published_files(published_dir, "2026-02-12")
            names = [path.name for path in files]
            self.assertIn("votaciones-es-2026-02-12.json.gz", names)
            self.assertNotIn("votaciones-es-2026-02-12.json", names)
            self.assertIn("representantes-es-2026-02-12.json", names)
            self.assertIn("proximas-elecciones-espana.json", names)

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


if __name__ == "__main__":
    unittest.main()
