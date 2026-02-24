from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_liberty_person_identity_resolution_seed import validate_seed


class TestValidateLibertyPersonIdentityResolutionSeed(unittest.TestCase):
    def _valid_doc(self) -> dict:
        return {
            "schema_version": "liberty_person_identity_resolution_seed_v1",
            "generated_at": "2026-02-23T00:00:00Z",
            "methodology": {
                "method_version": "identity_resolution_v1",
                "method_label": "Resolucion manual persona-cargo v1",
            },
            "mappings": [
                {
                    "actor_person_name": "Persona Seed A",
                    "person_full_name": "Alicia Martin Gomez",
                    "source_kind": "manual_seed",
                    "person_canonical_key": "demo:alicia_martin_gomez",
                    "confidence": 0.95,
                },
                {
                    "actor_person_name": "Persona Seed B",
                    "person_full_name": "Carlos Rivas Soto",
                    "source_kind": "official_nombramiento",
                    "source_id": "boe_api_legal",
                    "source_record_id": "boe:A-2024-00001",
                    "person_canonical_key": "demo:carlos_rivas_soto",
                    "confidence": 0.8,
                    "source_url": "https://example.org/persona-b",
                    "evidence_date": "2026-02-23",
                    "evidence_quote": "Nombramiento oficial publicado.",
                },
            ],
        }

    def test_valid_seed(self) -> None:
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed.json"
            seed_path.write_text(json.dumps(self._valid_doc()), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertTrue(bool(got["valid"]))
        self.assertEqual(int(got["mappings_total"]), 2)
        self.assertEqual(int(got["errors_count"]), 0)

    def test_invalid_seed_detects_duplicate_actor_alias(self) -> None:
        bad = self._valid_doc()
        bad["mappings"][1]["actor_person_name"] = "persona seed a"
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_bad_alias.json"
            seed_path.write_text(json.dumps(bad), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertFalse(bool(got["valid"]))
        self.assertGreater(int(got["errors_count"]), 0)

    def test_invalid_seed_detects_bad_confidence_and_url(self) -> None:
        bad = self._valid_doc()
        bad["mappings"][0]["confidence"] = 1.5
        bad["mappings"][0]["source_url"] = "ftp://example.org/not-http"
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_bad_confidence.json"
            seed_path.write_text(json.dumps(bad), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertFalse(bool(got["valid"]))
        self.assertGreater(int(got["errors_count"]), 0)

    def test_invalid_seed_requires_evidence_fields_for_official_source_kind(self) -> None:
        bad = self._valid_doc()
        bad["mappings"][1].pop("source_url", None)
        bad["mappings"][1].pop("evidence_date", None)
        bad["mappings"][1].pop("evidence_quote", None)
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_bad_official_mapping.json"
            seed_path.write_text(json.dumps(bad), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertFalse(bool(got["valid"]))
        self.assertGreaterEqual(int(got["errors_count"]), 1)

    def test_invalid_seed_requires_source_id_when_source_record_id_is_present(self) -> None:
        bad = self._valid_doc()
        bad["mappings"][1].pop("source_id", None)
        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_bad_source_record_ref.json"
            seed_path.write_text(json.dumps(bad), encoding="utf-8")
            got = validate_seed(seed_path)
        self.assertFalse(bool(got["valid"]))
        self.assertGreaterEqual(int(got["errors_count"]), 1)


if __name__ == "__main__":
    unittest.main()
