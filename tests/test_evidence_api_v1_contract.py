from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_evidence_api_v1 import (
    COLLECTIONS,
    DEFAULT_ATTESTATION,
    DEFAULT_EVIDENCE,
    DEFAULT_ORIGIN,
    DEFAULT_OUT,
    DEFAULT_SCHEMA,
    DEFAULT_SOURCE_HEALTH,
    decode_cursor,
    export_api,
    read_json,
)
from scripts.validate_evidence_api_v1 import validate


def collection_items(out_root: Path, release: dict, collection: str) -> list[dict]:
    entry = next(item for item in release["collections"] if item["id"] == collection)
    manifest = read_json(out_root / entry["manifest"].removeprefix("/api/v1/"))
    items: list[dict] = []
    for page in manifest["pages"]:
        payload = read_json(out_root / page["href"].removeprefix("/api/v1/"))
        items.extend(payload["items"])
    return items


class EvidenceApiV1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = read_json(DEFAULT_EVIDENCE)
        cls.health = read_json(DEFAULT_SOURCE_HEALTH)
        cls.pointer = read_json(DEFAULT_OUT / "index.json")
        release_href = cls.pointer["current_release"]["href"].removeprefix("/api/v1/")
        cls.release = read_json(DEFAULT_OUT / release_href)

    def test_current_real_export_passes_fail_closed_validator(self) -> None:
        report = validate(
            out_root=DEFAULT_OUT,
            evidence_path=DEFAULT_EVIDENCE,
            source_health_path=DEFAULT_SOURCE_HEALTH,
            schema_path=DEFAULT_SCHEMA,
            max_page_bytes=2_500_000,
            max_manifest_bytes=2_500_000,
        )

        self.assertEqual(report["status"], "ok", report["errors"])
        self.assertTrue(report["checks"]["official_real_records_only"])
        self.assertTrue(report["checks"]["public_identity_labels_retained"])
        self.assertEqual(
            report["checks"]["source_health_total"], len(self.health["sources"])
        )

    def test_four_collections_are_bounded_and_seek_paginated(self) -> None:
        self.assertEqual(
            {item["id"] for item in self.release["collections"]}, set(COLLECTIONS)
        )
        api_release_id = self.release["api_release_id"]
        for entry in self.release["collections"]:
            manifest = read_json(
                DEFAULT_OUT / entry["manifest"].removeprefix("/api/v1/")
            )
            self.assertLessEqual(manifest["page_size"], 500)
            self.assertNotIn("offset", json.dumps(manifest).lower())
            if manifest["pages"]:
                first_page = read_json(
                    DEFAULT_OUT / manifest["pages"][0]["href"].removeprefix("/api/v1/")
                )
                cursor = decode_cursor(first_page["page_info"]["end_cursor"])
                self.assertEqual(cursor["collection"], entry["id"])
                self.assertEqual(cursor["release"], api_release_id)

    def test_public_identity_labels_are_byte_for_byte_retained(self) -> None:
        entities = collection_items(DEFAULT_OUT, self.release, "entities")
        published = {item["id"]: item["label"] for item in entities}
        source = {
            item["answer_id"]: item["actor_label"]
            for item in self.evidence["actor_answers"]
        }
        source.update(
            {
                item["answer_id"]: item["issue_label"]
                for item in self.evidence["issue_answers"]
            }
        )

        self.assertEqual(published, source)
        self.assertGreater(len(published), 1_000)

    def test_real_export_is_deterministic_at_a_different_bounded_page_size(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "api/v1"
            first = export_api(
                evidence_path=DEFAULT_EVIDENCE,
                source_health_path=DEFAULT_SOURCE_HEALTH,
                origin_path=DEFAULT_ORIGIN,
                attestation_path=DEFAULT_ATTESTATION,
                schema_path=DEFAULT_SCHEMA,
                out_root=out_root,
                page_size=37,
            )
            second = export_api(
                evidence_path=DEFAULT_EVIDENCE,
                source_health_path=DEFAULT_SOURCE_HEALTH,
                origin_path=DEFAULT_ORIGIN,
                attestation_path=DEFAULT_ATTESTATION,
                schema_path=DEFAULT_SCHEMA,
                out_root=out_root,
                page_size=37,
            )
            report = validate(
                out_root=out_root,
                evidence_path=DEFAULT_EVIDENCE,
                source_health_path=DEFAULT_SOURCE_HEALTH,
                schema_path=DEFAULT_SCHEMA,
                max_page_bytes=2_500_000,
                max_manifest_bytes=2_500_000,
            )

        self.assertEqual(first["api_release_id"], second["api_release_id"])
        self.assertEqual(first["release_index_sha256"], second["release_index_sha256"])
        self.assertEqual(report["status"], "ok", report["errors"])
        self.assertEqual(report["checks"]["items_total"], 5_830)

    def test_missing_source_url_is_explicit_not_silently_imputed(self) -> None:
        chains = collection_items(DEFAULT_OUT, self.release, "evidence-chains")
        missing = [item for item in chains if item["evidence"]["source_url"] is None]

        self.assertGreater(len(missing), 0)
        self.assertTrue(
            all(
                item["evidence"]["source_url_state"]
                == "not_available_in_current_export"
                for item in missing
            )
        )
        self.assertTrue(all(item["evidence"]["source_locator"] for item in missing))


if __name__ == "__main__":
    unittest.main()
