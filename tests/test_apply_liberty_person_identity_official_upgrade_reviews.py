from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.apply_liberty_person_identity_official_upgrade_reviews import apply_review_decisions
from scripts.validate_liberty_person_identity_resolution_seed import validate_seed


class TestApplyLibertyPersonIdentityOfficialUpgradeReviews(unittest.TestCase):
    def test_apply_approved_upgrades_mapping_to_official(self) -> None:
        root = Path(__file__).resolve().parents[1]
        seed_doc = json.loads(
            (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8")
        )
        actor_person_name = str(seed_doc["mappings"][0]["actor_person_name"])
        updated_seed, meta = apply_review_decisions(
            seed_doc,
            rows=[
                {
                    "actor_person_name": actor_person_name,
                    "person_full_name": "Persona Seed Empleo Nombramientos",
                    "decision": "approved",
                    "proposed_source_kind": "official_nombramiento",
                    "source_url": "https://www.boe.es/boe/dias/2024/01/02/",
                    "evidence_date": "2024-01-02",
                    "evidence_quote": "Nombramiento oficial publicado en BOE.",
                    "source_id": "boe_api_legal",
                    "source_record_id": "BOE-A-2024-12345",
                    "source_record_pk": "12345",
                    "confidence": "1.0",
                    "review_note": "capturado en sprint AI-OPS-150",
                }
            ],
        )
        counts = meta["counts"]
        self.assertEqual(int(counts["rows_with_decision"]), 1)
        self.assertEqual(int(counts["approved_rows"]), 1)
        self.assertEqual(int(counts["updated_rows"]), 1)
        mapping = next(m for m in updated_seed["mappings"] if str(m.get("actor_person_name")) == actor_person_name)
        self.assertEqual(str(mapping["source_kind"]), "official_nombramiento")
        self.assertEqual(str(mapping["source_url"]), "https://www.boe.es/boe/dias/2024/01/02/")
        self.assertEqual(str(mapping["evidence_date"]), "2024-01-02")
        self.assertEqual(str(mapping["evidence_quote"]), "Nombramiento oficial publicado en BOE.")
        self.assertEqual(str(mapping["source_id"]), "boe_api_legal")
        self.assertEqual(str(mapping["source_record_id"]), "BOE-A-2024-12345")
        self.assertEqual(str(mapping["source_record_pk"]), "12345")

        with TemporaryDirectory() as td:
            seed_path = Path(td) / "seed_candidate.json"
            seed_path.write_text(json.dumps(updated_seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            validation = validate_seed(seed_path)
        self.assertTrue(bool(validation["valid"]))

    def test_apply_prevents_downgrade_to_manual_seed(self) -> None:
        root = Path(__file__).resolve().parents[1]
        seed_doc = json.loads(
            (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8")
        )
        actor_person_name = str(seed_doc["mappings"][0]["actor_person_name"])
        seed_doc["mappings"][0]["source_kind"] = "official_nombramiento"
        seed_doc["mappings"][0]["source_url"] = "https://www.boe.es/boe/dias/2024/01/02/"
        seed_doc["mappings"][0]["evidence_date"] = "2024-01-02"
        seed_doc["mappings"][0]["evidence_quote"] = "Nombramiento oficial publicado en BOE."

        updated_seed, meta = apply_review_decisions(
            seed_doc,
            rows=[
                {
                    "actor_person_name": actor_person_name,
                    "decision": "approved",
                    "proposed_source_kind": "manual_seed",
                    "review_note": "attempt downgrade should be blocked",
                }
            ],
        )
        counts = meta["counts"]
        self.assertEqual(int(counts["approved_rows"]), 1)
        self.assertEqual(int(counts["skipped_downgrade_prevented"]), 1)
        self.assertEqual(int(counts["updated_rows"]), 0)
        mapping = next(m for m in updated_seed["mappings"] if str(m.get("actor_person_name")) == actor_person_name)
        self.assertEqual(str(mapping["source_kind"]), "official_nombramiento")

    def test_apply_auto_resolves_source_record_pk_from_lookup(self) -> None:
        root = Path(__file__).resolve().parents[1]
        seed_doc = json.loads(
            (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8")
        )
        actor_person_name = str(seed_doc["mappings"][0]["actor_person_name"])

        updated_seed, meta = apply_review_decisions(
            seed_doc,
            rows=[
                {
                    "actor_person_name": actor_person_name,
                    "decision": "approved",
                    "proposed_source_kind": "official_nombramiento",
                    "source_url": "https://www.boe.es/boe/dias/2024/01/02/",
                    "evidence_date": "2024-01-02",
                    "evidence_quote": "Nombramiento oficial publicado en BOE.",
                    "source_id": "boe_api_legal",
                    "source_record_id": "BOE-A-2024-15000",
                }
            ],
            source_record_lookup={("boe_api_legal", "boe-a-2024-15000"): "76543"},
        )
        counts = meta["counts"]
        self.assertEqual(int(counts["approved_rows"]), 1)
        self.assertEqual(int(counts["source_record_pk_auto_resolved"]), 1)
        mapping = next(m for m in updated_seed["mappings"] if str(m.get("actor_person_name")) == actor_person_name)
        self.assertEqual(str(mapping["source_record_pk"]), "76543")


if __name__ == "__main__":
    unittest.main()
