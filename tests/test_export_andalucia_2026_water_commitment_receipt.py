import importlib.util
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/export_andalucia_2026_water_commitment_receipt.py"
SPEC = importlib.util.spec_from_file_location("water_receipt_exporter", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def advanced_seed(seed: dict, *, days: int = 7) -> dict:
    current = json.loads(json.dumps(seed))
    snapshot = date.fromisoformat(seed["snapshot_date"]) + timedelta(days=days)
    next_check = snapshot + timedelta(days=7)
    current["snapshot_date"] = snapshot.isoformat()
    current["scope"]["evidence_window_end"] = snapshot.isoformat()
    current["evidence_check"]["checked_at"] = snapshot.isoformat()
    current["method"]["next_check"] = next_check.isoformat()
    return current


class AndaluciaWaterReceiptExporterTest(unittest.TestCase):
    def setUp(self):
        self.seed = json.loads(MODULE.DEFAULT_SEED.read_text(encoding="utf-8"))

    def test_builds_three_conservative_commitments(self):
        payload = MODULE.build_receipt(self.seed)

        self.assertEqual(
            payload["schema_version"],
            "andalucia_water_commitment_receipt_v1",
        )
        self.assertEqual(payload["summary"]["commitments_total"], 3)
        self.assertEqual(payload["summary"]["declared_only_total"], 3)
        self.assertEqual(payload["summary"]["post_investiture_actions_total"], 0)
        self.assertEqual(
            {item["status"] for item in payload["commitments"]},
            {"declarado"},
        )
        self.assertEqual(payload["history"]["status"], "first_snapshot")
        self.assertIsNone(payload["history"]["previous_snapshot_date"])

    def test_reiteration_does_not_count_as_progress(self):
        payload = MODULE.build_receipt(self.seed)
        irrigation = payload["commitments"][0]

        self.assertEqual(irrigation["status"], "declarado")
        self.assertEqual(
            irrigation["post_investiture_evidence"][0]["evidence_kind"],
            "reiteration",
        )
        self.assertIs(
            irrigation["post_investiture_evidence"][0]["counts_as_progress"],
            False,
        )

    def test_rejects_non_official_source(self):
        self.seed["sources"][0]["url"] = "https://example.com/promise"

        with self.assertRaisesRegex(ValueError, "official Andalucía host"):
            MODULE.build_receipt(self.seed)

    def test_rejects_advanced_status_without_progress_evidence(self):
        self.seed["commitments"][1]["status"] = "acto_oficial"

        with self.assertRaisesRegex(ValueError, "needs evidence"):
            MODULE.build_receipt(self.seed)

    def test_rejects_next_check_that_does_not_follow_snapshot(self):
        self.seed["method"]["next_check"] = self.seed["snapshot_date"]

        with self.assertRaisesRegex(ValueError, "next_check"):
            MODULE.build_receipt(self.seed)

    def test_semantic_diff_reports_added_evidence_and_status_change(self):
        previous = MODULE.build_receipt(self.seed)
        current = advanced_seed(self.seed)
        evidence_date = current["snapshot_date"]
        current["sources"].append(
            {
                "source_id": f"irrigation-law-filing-{evidence_date}",
                "label": "Registro del proyecto de ley de regadíos",
                "publisher": "Parlamento de Andalucía",
                "published_date": evidence_date,
                "locator": "Expediente de la XIII legislatura",
                "url": "https://www.parlamentodeandalucia.es/expediente/ley-regadios",
                "source_role": "formal_action",
            }
        )
        current["commitments"][0]["status"] = "acto_oficial"
        current["commitments"][0]["status_label"] = "Acto oficial"
        current["commitments"][0]["status_detail"] = "Proyecto registrado."
        current["commitments"][0]["post_investiture_evidence"].append(
            {
                "evidence_kind": "formal_action",
                "date": evidence_date,
                "label": "Proyecto registrado en el Parlamento.",
                "source_id": f"irrigation-law-filing-{evidence_date}",
                "counts_as_progress": True,
            }
        )

        payload = MODULE.build_receipt(current, previous=previous)

        self.assertEqual(payload["history"]["status"], "changed")
        self.assertEqual(
            payload["history"]["previous_snapshot_date"],
            self.seed["snapshot_date"],
        )
        self.assertEqual(payload["history"]["commitments_changed_total"], 1)
        change = payload["history"]["commitments"][0]
        self.assertEqual(change["commitment_id"], "ley-andaluza-regadios")
        self.assertIn("status_changed", change["change_kinds"])
        self.assertIn("evidence_added", change["change_kinds"])
        self.assertEqual(len(change["evidence_added"]), 1)

    def test_semantic_diff_reports_explicit_no_change(self):
        previous = MODULE.build_receipt(self.seed)
        current = advanced_seed(self.seed)

        payload = MODULE.build_receipt(current, previous=previous)

        self.assertEqual(payload["history"]["status"], "no_change")
        self.assertEqual(payload["history"]["commitments_changed_total"], 0)
        self.assertEqual(
            payload["summary"]["changed_since_previous_snapshot"],
            f"sin_cambios_desde_{self.seed['snapshot_date']}",
        )

    def test_semantic_diff_reports_removed_commitment(self):
        previous = MODULE.build_receipt(self.seed)
        current = advanced_seed(self.seed)
        removed = current["commitments"].pop()
        replacement = json.loads(json.dumps(current["commitments"][0]))
        replacement["commitment_id"] = "nuevo-compromiso"
        replacement["number"] = "04"
        replacement["title"] = "Nuevo compromiso"
        current["commitments"].append(replacement)

        payload = MODULE.build_receipt(current, previous=previous)

        change = next(
            item
            for item in payload["history"]["commitments"]
            if item["commitment_id"] == removed["commitment_id"]
        )
        self.assertEqual(change["commitment_id"], removed["commitment_id"])
        self.assertEqual(change["change_kinds"], ["commitment_removed"])
        self.assertIsNone(change["status_after"])

    def test_freshness_gate_accepts_current_and_rejects_stale(self):
        payload = MODULE.build_receipt(self.seed)
        snapshot = date.fromisoformat(self.seed["snapshot_date"])

        current = MODULE.check_freshness(
            payload,
            as_of_date=(snapshot + timedelta(days=7)).isoformat(),
            max_age_days=8,
        )
        self.assertEqual(current["age_days"], 7)

        with self.assertRaisesRegex(ValueError, "water receipt is stale"):
            MODULE.check_freshness(
                payload,
                as_of_date=(snapshot + timedelta(days=9)).isoformat(),
                max_age_days=8,
            )

    def test_exports_identical_bounded_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "published.json"
            second = Path(temp_dir) / "public.json"

            MODULE.export_receipt(MODULE.DEFAULT_SEED, [first, second])

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertLess(first.stat().st_size, MODULE.MAX_PUBLIC_BYTES)

    def test_exports_immutable_archive_and_uses_it_for_next_diff(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            seed_path = temp / "seed.json"
            first = temp / "latest.json"
            archive = temp / "archive"
            seed_path.write_text(
                json.dumps(self.seed, ensure_ascii=False),
                encoding="utf-8",
            )

            MODULE.export_receipt(
                seed_path,
                [first],
                archive_dirs=[archive],
                as_of_date=self.seed["snapshot_date"],
            )
            archived_first = archive / f"{self.seed['snapshot_date']}.json"
            self.assertTrue(archived_first.exists())

            next_seed = advanced_seed(self.seed)
            seed_path.write_text(
                json.dumps(next_seed, ensure_ascii=False),
                encoding="utf-8",
            )

            payload = MODULE.export_receipt(
                seed_path,
                [first],
                archive_dirs=[archive],
                as_of_date=next_seed["snapshot_date"],
            )

            self.assertEqual(payload["history"]["status"], "no_change")
            self.assertEqual(
                payload["history"]["previous_snapshot_date"],
                self.seed["snapshot_date"],
            )
            self.assertTrue((archive / f"{next_seed['snapshot_date']}.json").exists())

    def test_archive_rejects_rewriting_a_snapshot_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            seed_path = temp / "seed.json"
            archive = temp / "archive"
            seed_path.write_text(
                json.dumps(self.seed, ensure_ascii=False),
                encoding="utf-8",
            )
            MODULE.export_receipt(
                seed_path,
                [temp / "latest.json"],
                archive_dirs=[archive],
                as_of_date=self.seed["snapshot_date"],
            )

            changed_seed = json.loads(json.dumps(self.seed))
            changed_seed["question"] = "Contenido cambiado sin nuevo corte"
            seed_path.write_text(
                json.dumps(changed_seed, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "immutable receipt snapshot"):
                MODULE.export_receipt(
                    seed_path,
                    [temp / "latest.json"],
                    archive_dirs=[archive],
                    as_of_date=self.seed["snapshot_date"],
                )


if __name__ == "__main__":
    unittest.main()
