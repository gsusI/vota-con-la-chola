from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_sanction_norms_seed import validate_seed


def _seed_doc() -> dict:
    return {
        "schema_version": "sanction_norms_seed_v1",
        "generated_at": "2026-02-23T00:00:00Z",
        "norms": [
            {
                "norm_id": "es:boe-a-2015-11722",
                "boe_id": "BOE-A-2015-11722",
                "title": "Ley trafico",
                "scope": "nacional",
                "organismo_competente": "DGT",
                "incidence_hypothesis": "Alta incidencia",
                "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                "evidence_required": ["base_legal_fragment", "organo_competente"],
                "key_fragments": [
                    {
                        "fragment_type": "articulo",
                        "fragment_label": "Bloque principal",
                        "conducta_sancionada": "Incumplimientos",
                        "organo_competente": "DGT",
                        "via_recurso": "Reposicion",
                        "importe_min_eur": 100,
                        "importe_max_eur": 200,
                    }
                ],
                "responsibility_hints": [
                    {
                        "role": "propose",
                        "actor_label": "Gobierno",
                        "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                        "evidence_date": "2015-10-31",
                        "evidence_quote": "Fuente BOE del marco normativo publicado.",
                        "evidence_items": [
                            {
                                "evidence_type": "boe_publicacion",
                                "source_id": "boe_api_legal",
                                "source_record_id": "BOE-A-2015-11722",
                                "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                                "evidence_date": "2015-10-31",
                                "evidence_quote": "Publicacion oficial en BOE del texto normativo.",
                            }
                        ],
                    },
                    {
                        "role": "approve",
                        "actor_label": "Cortes Generales",
                        "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                        "evidence_date": "2015-10-31",
                        "evidence_quote": "Fuente BOE del marco normativo publicado.",
                    },
                ],
                "lineage_hints": [
                    {
                        "relation_type": "desarrolla",
                        "relation_scope": "parcial",
                        "target_boe_id": "BOE-A-1990-6396",
                        "target_title": "Texto articulado previo de trafico.",
                        "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                        "evidence_date": "2015-10-31",
                        "evidence_quote": "Fuente BOE del texto refundido y su encaje con la norma previa.",
                    }
                ],
            }
        ],
    }


class TestValidateSanctionNormsSeed(unittest.TestCase):
    def test_validate_seed_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "seed.json"
            p.write_text(json.dumps(_seed_doc(), ensure_ascii=False), encoding="utf-8")

            got = validate_seed(p)
            self.assertTrue(bool(got["valid"]))
            self.assertEqual(int(got["errors_count"]), 0)
            self.assertEqual(int(got["norms_total"]), 1)
            self.assertEqual(int(got["fragments_total"]), 1)
            self.assertEqual(int(got["responsibility_hints_total"]), 2)
            self.assertEqual(int(got["responsibility_evidence_items_total"]), 1)
            self.assertEqual(int(got["lineage_hints_total"]), 1)

    def test_validate_seed_detects_duplicate_and_invalid_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            bad["norms"].append(
                {
                    "norm_id": "es:boe-a-2015-11722",
                    "boe_id": "BAD-ID",
                    "title": "Dup",
                    "scope": "nacional",
                    "organismo_competente": "X",
                    "incidence_hypothesis": "Y",
                    "source_url": "ftp://bad",
                    "evidence_required": [],
                    "key_fragments": [{"fragment_type": "invalid"}],
                }
            )
            p = Path(td) / "seed_bad.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")

            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("duplicate_norm_id", codes)
            self.assertIn("invalid_boe_id", codes)
            self.assertIn("invalid_fragment_type", codes)
            self.assertIn("invalid_source_url", codes)

    def test_validate_seed_detects_missing_responsibility_primary_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            hints = bad["norms"][0]["responsibility_hints"]
            hints[0].pop("source_url", None)
            hints[0]["evidence_date"] = "2026/02/23"
            hints[0]["evidence_quote"] = ""
            p = Path(td) / "seed_bad_resp.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")

            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("missing_responsibility_source_url", codes)
            self.assertIn("invalid_responsibility_evidence_date", codes)
            self.assertIn("missing_responsibility_evidence_quote", codes)

    def test_validate_seed_detects_invalid_responsibility_evidence_item(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            item = bad["norms"][0]["responsibility_hints"][0]["evidence_items"][0]
            item["evidence_type"] = "invalid"
            item["source_url"] = "ftp://bad"
            item["evidence_date"] = "2026/02/23"
            item["evidence_quote"] = ""
            p = Path(td) / "seed_bad_resp_evidence.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")

            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("invalid_responsibility_evidence_type", codes)
            self.assertIn("invalid_responsibility_evidence_source_url", codes)
            self.assertIn("invalid_responsibility_evidence_date", codes)
            self.assertIn("missing_responsibility_evidence_quote", codes)

    def test_validate_seed_detects_invalid_responsibility_source_record_refs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            item = bad["norms"][0]["responsibility_hints"][0]["evidence_items"][0]
            item["source_id"] = ""
            item["source_record_id"] = ""
            item["source_record_pk"] = "abc"
            p = Path(td) / "seed_bad_resp_source_record_refs.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")

            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("invalid_responsibility_evidence_source_record_id", codes)
            self.assertIn("missing_responsibility_evidence_source_id_for_source_record_id", codes)
            self.assertIn("invalid_responsibility_evidence_source_record_pk", codes)

    def test_validate_seed_detects_invalid_lineage_hint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = _seed_doc()
            hint = bad["norms"][0]["lineage_hints"][0]
            hint["relation_type"] = "replace"
            hint["target_boe_id"] = "BAD-ID"
            hint["source_url"] = ""
            hint["evidence_date"] = "2026/02/23"
            hint["evidence_quote"] = ""
            p = Path(td) / "seed_bad_lineage.json"
            p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")

            got = validate_seed(p)
            self.assertFalse(bool(got["valid"]))
            codes = {str(e.get("code")) for e in got["errors"]}
            self.assertIn("invalid_lineage_relation_type", codes)
            self.assertIn("invalid_lineage_target_boe_id", codes)
            self.assertIn("missing_lineage_source_url", codes)
            self.assertIn("invalid_lineage_evidence_date", codes)
            self.assertIn("missing_lineage_evidence_quote", codes)


if __name__ == "__main__":
    unittest.main()
