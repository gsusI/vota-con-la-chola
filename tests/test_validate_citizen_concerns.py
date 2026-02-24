from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_citizen_concerns import validate_concerns_config


class TestValidateCitizenConcerns(unittest.TestCase):
    def test_validate_concerns_config_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "concerns.json"
            p.write_text(
                json.dumps(
                    {
                        "version": "v1",
                        "notes": "test",
                        "normalization": {"lowercase": True, "strip_diacritics": True},
                        "concerns": [
                            {
                                "id": "vivienda",
                                "label": "Vivienda",
                                "description": "Acceso a vivienda",
                                "keywords": ["vivienda", "alquiler"],
                            },
                            {
                                "id": "empleo",
                                "label": "Empleo",
                                "description": "Mercado laboral",
                                "keywords": ["empleo", "salario"],
                            },
                        ],
                        "packs": [
                            {
                                "id": "hogar_bolsillo",
                                "label": "Hogar y bolsillo",
                                "concern_ids": ["vivienda", "empleo"],
                                "tradeoff": "Puede dejar fuera otros temas.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            got = validate_concerns_config(p)
            self.assertTrue(bool(got["valid"]))
            self.assertEqual(int(got["errors_count"]), 0)
            self.assertEqual(int(got["concerns_total"]), 2)
            self.assertEqual(int(got["packs_total"]), 1)
            self.assertEqual(int(got["keywords_total"]), 4)

    def test_validate_concerns_config_detects_contract_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "concerns_invalid.json"
            p.write_text(
                json.dumps(
                    {
                        "version": "v1",
                        "normalization": {"lowercase": True, "strip_diacritics": True},
                        "concerns": [
                            {
                                "id": "vivienda",
                                "label": "Vivienda",
                                "description": "",
                                "keywords": ["vivienda", "Vivienda"],
                            },
                            {
                                "id": "vivienda",
                                "label": "Duplicado",
                                "description": "dup",
                                "keywords": ["dup"],
                            },
                            {
                                "id": "empleo",
                                "label": "Empleo",
                                "description": "Mercado laboral",
                                "keywords": ["empleo"],
                            },
                        ],
                        "packs": [
                            {
                                "id": "pack_bad",
                                "label": "Pack",
                                "concern_ids": ["vivienda", "fantasma"],
                                "tradeoff": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            got = validate_concerns_config(p)
            self.assertFalse(bool(got["valid"]))
            self.assertGreater(int(got["errors_count"]), 0)
            codes = {str(e.get("code")) for e in (got.get("errors") or [])}
            self.assertIn("missing_concern_description", codes)
            self.assertIn("duplicate_keyword", codes)
            self.assertIn("duplicate_concern_id", codes)
            self.assertIn("unknown_pack_concern_id", codes)
            self.assertIn("missing_pack_tradeoff", codes)
            self.assertIn("concerns_without_pack", codes)

    def test_repo_concerns_v1_is_valid(self) -> None:
        p = Path("ui/citizen/concerns_v1.json")
        got = validate_concerns_config(p)
        self.assertTrue(bool(got["valid"]), msg=f"errors={got.get('errors')}")
        self.assertGreaterEqual(int(got["concerns_total"]), 10)
        self.assertGreaterEqual(int(got["packs_total"]), 1)


if __name__ == "__main__":
    unittest.main()
