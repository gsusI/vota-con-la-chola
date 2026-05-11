from __future__ import annotations

import unittest
from pathlib import Path

from publicdata_ops import normalize_command, pre_commands, prerequisite_source_ids, sort_items_by_dependencies


class TestPublicDataOps(unittest.TestCase):
    def test_normalize_command_sets_db_and_snapshot_date_for_ingest(self) -> None:
        tokens = normalize_command(
            "python3 scripts/ingest.py ingest --db old.db --snapshot-date old --source a",
            db_path=Path("new.db"),
            snapshot_date="2026-02-12",
        )

        self.assertEqual(tokens[tokens.index("--db") + 1], "new.db")
        self.assertEqual(tokens[tokens.index("--snapshot-date") + 1], "2026-02-12")

    def test_queue_helpers_dedupe_and_sort_dependencies(self) -> None:
        item = {
            "execution": {
                "prerequisite_source_ids": ["base", "base", "", None, "other"],
                "pre_commands": [" echo ready ", "", None],
            }
        }
        self.assertEqual(prerequisite_source_ids(item), ["base", "other"])
        self.assertEqual(pre_commands(item), ["echo ready"])

        ordered = sort_items_by_dependencies(
            [
                {"source_id": "child", "execution": {"prerequisite_source_ids": ["base"]}},
                {"source_id": "base", "execution": {}},
            ]
        )
        self.assertEqual([row["source_id"] for row in ordered], ["base", "child"])


if __name__ == "__main__":
    unittest.main()
