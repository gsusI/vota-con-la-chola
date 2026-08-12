from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.publicar_hf_scale_snapshot import ScaleOriginError
from scripts.validate_restored_scale_origin import (
    corpus_result_summary,
    parse_csv_set,
    safe_child,
)


class ValidateRestoredScaleOriginTests(unittest.TestCase):
    def test_parse_csv_set_deduplicates_and_ignores_empty_items(self) -> None:
        self.assertEqual(parse_csv_set("votes, money, votes, "), {"votes", "money"})

    def test_safe_child_rejects_escape(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            self.assertRaises(ScaleOriginError),
        ):
            safe_child(Path(temp_dir), "../outside.json", "fixture")

    def test_vote_summary_reconciles_release_contract(self) -> None:
        summary, errors = corpus_result_summary(
            corpus={
                "id": "member_votes",
                "kind": "gzip_vote_shards",
                "rows": 10,
                "files": 2,
                "bytes": 300,
            },
            validation={
                "status": "ok",
                "totals": {
                    "member_votes": 10,
                    "entries": 2,
                    "bytes": 300,
                    "payloads_with_private_path_tokens": 0,
                },
            },
        )

        self.assertEqual(errors, [])
        self.assertEqual(summary["status"], "ok")
        self.assertTrue(all(summary["checks"].values()))

    def test_parquet_summary_fails_on_row_or_identity_hygiene_drift(self) -> None:
        summary, errors = corpus_result_summary(
            corpus={
                "id": "money",
                "kind": "parquet_manifest",
                "rows": 10,
                "files": 2,
                "bytes": 300,
            },
            validation={
                "status": "ok",
                "lane": "public_money_facts",
                "totals": {
                    "rows": 9,
                    "files": 2,
                    "parquet_bytes": 300,
                    "private_token_findings": 1,
                },
            },
        )

        self.assertEqual(summary["status"], "failed")
        self.assertIn("money: rows_match_release failed", errors)
        self.assertIn("money: no_private_tokens failed", errors)

    def test_unsupported_corpus_kind_fails_closed(self) -> None:
        with self.assertRaises(ScaleOriginError):
            corpus_result_summary(
                corpus={"id": "bad", "kind": "unknown"},
                validation={"status": "ok", "totals": {}},
            )


if __name__ == "__main__":
    unittest.main()
