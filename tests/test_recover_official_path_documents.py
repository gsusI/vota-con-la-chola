from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.recover_official_path_documents import (
    REPO_ROOT,
    senate_session_source_url,
    sha256_file,
    source_url_capture_path,
)


class TestRecoverOfficialPathDocuments(unittest.TestCase):
    def test_maps_real_senate_capture_path_and_official_url_bijectively(self) -> None:
        capture_path = "manual/senado_votaciones_ses/legis14/ses_16.xml"
        source_url = "https://www.senado.es/legis14/votaciones/ses_16.xml"

        self.assertEqual(senate_session_source_url(capture_path), source_url)
        self.assertEqual(source_url_capture_path(source_url), capture_path)

    def test_manifest_matches_real_preserved_captures(self) -> None:
        manifest = (
            REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
            "official-path-document-lineage.jsonl"
        )
        inventory_root = REPO_ROOT / "etl/data/raw"
        if not manifest.is_file():
            self.skipTest("real official-path evidence is excluded from this context")
        rows = [json.loads(line) for line in manifest.read_text().splitlines() if line]
        if not rows or not all(
            Path(str(item["capture"]["path"])).is_absolute()
            or (REPO_ROOT / str(item["capture"]["path"])).is_file()
            for item in rows
        ):
            self.skipTest("real preserved XML corpus is excluded from this context")

        self.assertEqual(len(rows), 56)
        for item in rows:
            relative = str(item["capture"]["path"]).removeprefix("etl/data/raw/")
            capture = inventory_root / relative
            self.assertEqual(source_url_capture_path(item["source_url"]), relative)
            self.assertEqual(capture.stat().st_size, item["capture"]["bytes"])
            self.assertEqual(sha256_file(capture), item["capture"]["sha256"])


if __name__ == "__main__":
    unittest.main()
