from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.shard_large_vote_snapshot import shard_snapshot
from scripts.validate_member_vote_shards import validate_shards


class TestValidateMemberVoteShards(unittest.TestCase):
    def test_validation_detects_complete_and_tampered_shards(self) -> None:
        source_payload = {
            "items": [
                {
                    "event": {"vote_event_id": "vote-1", "source_id": "source"},
                    "source": {
                        "source_id": "source",
                        "source_url": "https://official.example/vote-1",
                        "source_hash": "a" * 64,
                        "source_record_id": "vote-1",
                        "source_record_pk": 1,
                    },
                    "member_votes": [
                        {
                            "member_name": "One",
                            "vote_choice": "Sí",
                            "source": {
                                "source_id": "source",
                                "source_url": "https://official.example/vote-1",
                            },
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "votes.json"
            source.write_text(json.dumps(source_payload), encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest = shard_snapshot(
                source,
                shard_root=root / "shards",
                manifest_out=manifest_path,
                max_index_bytes=100_000,
                max_shard_bytes=100_000,
                max_members_per_shard=10,
            )
            valid = validate_shards(manifest_path, shard_root=root / "shards")
            self.assertEqual(valid["status"], "ok")

            shard = root / "shards" / manifest["entries"][0]["shard"]
            shard.write_bytes(b"tampered")
            invalid = validate_shards(manifest_path, shard_root=root / "shards")
            self.assertEqual(invalid["status"], "failed")
            self.assertFalse(invalid["checks"]["all_checksums_valid"])


if __name__ == "__main__":
    unittest.main()
