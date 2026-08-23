from __future__ import annotations

import unittest

from scripts.recover_official_document_identifiers import (
    REPO_ROOT,
    load_inventory,
    load_seeds,
    official_diary_url_identifier,
    verify_local_captures,
)


class TestRecoverOfficialDocumentIdentifiers(unittest.TestCase):
    def test_parses_real_official_senate_diary_urls(self) -> None:
        self.assertEqual(
            official_diary_url_identifier(
                "https://www.congreso.es/public_oficiales/L15/SEN/DS/PL/DS_P_15_49.PDF"
            ),
            "DS_P_15_49",
        )
        self.assertEqual(
            official_diary_url_identifier(
                "https://www.congreso.es/public_oficiales/L14/SEN/DS/CO/DS_C_14_356.PDF"
            ),
            "DS_C_14_356",
        )

    def test_recovery_seeds_match_real_preserved_captures(self) -> None:
        inventory_root = REPO_ROOT / "etl/data/raw"
        inventory_manifest = (
            REPO_ROOT / "etl/data/manifests/real-document-format-inventory.jsonl"
        )
        seeds_path = (
            REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "official-document-identifier-recovery-seeds.json"
        )
        if not inventory_manifest.is_file() or not seeds_path.is_file():
            self.skipTest("real document evidence is excluded from this test context")
        seeds = load_seeds(seeds_path)
        if not all((inventory_root / seed["path"]).is_file() for seed in seeds):
            self.skipTest(
                "real preserved PDF corpus is excluded from this test context"
            )

        verified = verify_local_captures(
            seeds,
            inventory=load_inventory(inventory_manifest),
            inventory_root=inventory_root,
        )

        self.assertEqual(len(verified), 14)
        self.assertEqual(
            sum(bool(item["internal_identifiers"]) for item in verified),
            13,
        )
        self.assertEqual(
            sum(not item["internal_identifiers"] for item in verified),
            1,
        )


if __name__ == "__main__":
    unittest.main()
