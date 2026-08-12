from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.shard_large_vote_snapshot import shard_snapshot


class TestShardLargeVoteSnapshot(unittest.TestCase):
    def test_event_shards_are_bounded_deterministic_and_complete(self) -> None:
        items = []
        for event_index in range(2):
            items.append(
                {
                    "event": {
                        "vote_event_id": f"vote-{event_index}",
                        "source_id": "official-votes",
                        "vote_date": "2026-08-10",
                        "title": f"Vote {event_index}",
                    },
                    "source": {
                        "source_id": "official-votes",
                        "source_url": f"https://official.example/vote-{event_index}",
                        "source_hash": "a" * 64,
                        "source_record_id": f"vote-{event_index}",
                        "source_record_pk": event_index + 1,
                    },
                    "member_votes": [
                        {
                            "member_name": "One",
                            "vote_choice": "Sí",
                            "source": {
                                "source_id": "official-votes",
                                "source_url": f"https://official.example/vote-{event_index}",
                            },
                        },
                        {
                            "member_name": "Two",
                            "vote_choice": "No",
                            "source": {
                                "source_id": "official-votes",
                                "source_url": f"https://official.example/vote-{event_index}",
                            },
                        },
                    ],
                }
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "votes.json"
            source.write_text(json.dumps({"items": items}), encoding="utf-8")
            manifest_path = root / "manifest.json"
            first = shard_snapshot(
                source,
                shard_root=root / "shards",
                manifest_out=manifest_path,
                max_index_bytes=100_000,
                max_shard_bytes=10_000,
                max_members_per_shard=10,
            )
            second = shard_snapshot(
                source,
                shard_root=root / "shards",
                manifest_out=manifest_path,
                max_index_bytes=100_000,
                max_shard_bytes=10_000,
                max_members_per_shard=10,
            )
            self.assertTrue(first["bounded_delivery_gate_passed"])
            self.assertEqual(first["member_votes_total"], 4)
            self.assertEqual(first["events_total"], 2)
            self.assertEqual(first["entries"], second["entries"])
            for entry in first["entries"]:
                shard = root / "shards" / entry["shard"]
                with gzip.open(shard, "rt", encoding="utf-8") as handle:
                    item = json.load(handle)
                self.assertEqual(len(item["member_votes"]), 2)
                self.assertTrue(
                    all(
                        member["source"]["source_record_scope"]
                        == "parent_vote_event"
                        for member in item["member_votes"]
                    )
                )


if __name__ == "__main__":
    unittest.main()
