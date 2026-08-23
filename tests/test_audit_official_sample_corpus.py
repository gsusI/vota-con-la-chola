from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.audit_official_sample_corpus import audit_official_samples


class TestAuditOfficialSampleCorpus(unittest.TestCase):
    def test_repository_official_sample_registry_passes(self) -> None:
        report = audit_official_samples(source_config=__import__(
            "etl.politicos_es.config", fromlist=["SOURCE_CONFIG"]
        ).SOURCE_CONFIG)
        self.assertEqual(report["status"], "pass")
        self.assertGreater(report["configured_sources"], 20)
        self.assertEqual(report["synthetic_or_mock_records"], 0)
        self.assertTrue(report["public_domain_personal_information_retained"])

    def test_tampered_sample_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sample = root / "sample.json"
            sample.write_text('[{"name":"Real Person"}]', encoding="utf-8")
            registry = root / "registry.json"
            registry.write_text(json.dumps({
                "schema_version": "official_sample_origin_registry_v1",
                "policy": {
                    "configured_fallbacks_must_be_real_official_public_data": True,
                    "synthetic_or_mock_forbidden": True,
                    "public_domain_personal_information_retained": True,
                },
                "sources": [{
                    "source_id": "source",
                    "sample_path": "sample.json",
                    "sample_bytes": sample.stat().st_size,
                    "sample_sha256": "0" * 64,
                    "official_url": "https://official.example.org/data",
                    "origin_class": "official_public_capture_or_exact_derived_subset",
                    "public_domain_personal_information_retained": True,
                    "synthetic_or_mock": False,
                    "detailed_provenance_sidecar": None,
                }],
            }), encoding="utf-8")
            config = {"source": {"fallback_file": "sample.json", "default_url": "https://official.example.org/data"}}
            with patch("scripts.audit_official_sample_corpus.REPO_ROOT", root):
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    audit_official_samples(source_config=config, registry_path=registry)


if __name__ == "__main__":
    unittest.main()
