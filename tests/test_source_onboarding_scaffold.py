from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG
from etl.politicos_es.db import apply_schema, open_db, seed_sources
from etl.politicos_es.registry import get_connectors
from scripts.add_source import _sample_provenance

ROOT = Path(__file__).resolve().parents[1]
REAL_CAPTURE = ROOT / "etl/data/raw/samples/congreso_diputados_sample.json"
REAL_CAPTURE_PROVENANCE = (
    ROOT / "etl/data/raw/samples/congreso_diputados_sample.provenance.json"
)


class TestSourceOnboardingScaffold(unittest.TestCase):
    def test_add_source_dry_run_lists_expected_files(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/add_source.py",
                "congreso_reference_source",
                "--name",
                "Congreso official representatives reference",
                "--scope",
                "nacional",
                "--url",
                "https://www.congreso.es/es/opendata/diputados",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn(
            "publicdata_connectors_es/contrib/parsers/congreso_reference_source.py",
            proc.stdout,
        )
        self.assertIn(
            "etl/data/raw/samples/congreso_reference_source_sample.json", proc.stdout
        )
        self.assertIn("congreso_reference_source_sample.provenance.json", proc.stdout)
        self.assertIn("official-sample-origin-registry.json", proc.stdout)
        self.assertIn("docs/etl/sources/congreso_reference_source.md", proc.stdout)

    def test_real_sample_contract_copies_exact_bytes_and_identity_policy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = REAL_CAPTURE
            target = root / "sample.json"
            payload = source.read_bytes()
            source_provenance = json.loads(
                REAL_CAPTURE_PROVENANCE.read_text(encoding="utf-8")
            )
            args = argparse.Namespace(
                source_id="congreso_diputados",
                sample_file=str(source),
                sample_sha256=hashlib.sha256(payload).hexdigest(),
                rights_basis=source_provenance["rights_basis"],
                url=source_provenance["official_url"],
                captured_at=source_provenance["captured_at"],
            )
            provenance = _sample_provenance(args, target)
            self.assertEqual(target.read_bytes(), payload)
            self.assertFalse(provenance["synthetic_or_mock"])
            self.assertTrue(
                provenance["official_public_domain_personal_information_retained"]
            )
            self.assertTrue(provenance["public_domain_personal_information_retained"])

    def test_contrib_sources_are_seeded_and_registered(self) -> None:
        connectors = get_connectors()
        for source_id in SOURCE_CONFIG:
            sample = Path(str(SOURCE_CONFIG[source_id]["fallback_file"]))
            self.assertIn("fallback_file", SOURCE_CONFIG[source_id])
            self.assertTrue(str(sample), f"empty fallback_file for {source_id}")
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "sources.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                for source_id in connectors:
                    row = conn.execute(
                        "SELECT 1 FROM sources WHERE source_id = ?", (source_id,)
                    ).fetchone()
                    self.assertIsNotNone(
                        row, f"connector missing seeded source row: {source_id}"
                    )
            finally:
                conn.close()
