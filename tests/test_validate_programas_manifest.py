from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_programas_manifest import validate_manifest


class TestValidateProgramasManifest(unittest.TestCase):
    def test_validate_manifest_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            doc = td_path / "programa.html"
            doc.write_text("<html><body>Programa</body></html>", encoding="utf-8")
            manifest = td_path / "manifest.csv"
            manifest.write_text(
                "\n".join(
                    [
                        "party_id,party_name,election_cycle,kind,source_url,format_hint,snapshot_date,local_path",
                        f"1,PSOE,es_generales_2023,programa,https://example.org/psoe.html,html,2026-02-17,{doc}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            got = validate_manifest(manifest, require_local_path=True)
            self.assertTrue(bool(got["valid"]))
            self.assertEqual(int(got["rows_total"]), 1)
            self.assertEqual(int(got["rows_valid"]), 1)
            self.assertEqual(int(got["errors_count"]), 0)
            self.assertEqual(int(got["duplicate_key_count"]), 0)
            self.assertEqual(int(got["party_ids_distinct"]), 1)
            self.assertEqual(got["election_cycles"], ["es_generales_2023"])

    def test_validate_manifest_detects_duplicate_and_missing_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            doc = td_path / "programa.html"
            doc.write_text("ok", encoding="utf-8")
            missing = td_path / "missing.html"
            manifest = td_path / "manifest.csv"
            manifest.write_text(
                "\n".join(
                    [
                        "party_id,party_name,election_cycle,kind,source_url,format_hint,snapshot_date,local_path",
                        f"1,PSOE,es_generales_2023,programa,https://example.org/psoe.html,html,2026-02-17,{doc}",
                        f"1,PSOE,es_generales_2023,programa,https://example.org/psoe_dup.html,html,2026-02-17,{missing}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            got = validate_manifest(manifest, require_local_path=True)
            self.assertFalse(bool(got["valid"]))
            self.assertEqual(int(got["rows_total"]), 2)
            self.assertGreaterEqual(int(got["errors_count"]), 2)
            self.assertEqual(int(got["duplicate_key_count"]), 1)
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("duplicate_key", codes)
            self.assertIn("local_path_not_found", codes)

    def test_validate_manifest_requires_source_or_local_and_valid_types(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            manifest = td_path / "manifest.csv"
            manifest.write_text(
                "\n".join(
                    [
                        "party_id,party_name,election_cycle,kind,source_url,format_hint,snapshot_date,local_path",
                        "x,,es_generales_2023,programa,notaurl,doc,2026-99-99,",
                        "2,PP,es_generales_2023,programa,,,2026-02-17,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            got = validate_manifest(manifest)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("invalid_party_id", codes)
            self.assertIn("missing_party_name", codes)
            self.assertIn("missing_source_and_local_path", codes)
            self.assertIn("invalid_source_url", codes)
            self.assertIn("invalid_snapshot_date", codes)
            self.assertIn("invalid_format_hint", codes)


if __name__ == "__main__":
    unittest.main()
