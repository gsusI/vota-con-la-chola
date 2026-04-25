from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import export_vote_explainer_snapshot as vote_explainer


class TestExportVoteExplainerSnapshot(unittest.TestCase):
    def test_build_public_vote_id_is_stable_and_path_safe(self) -> None:
        public_vote_id = vote_explainer.build_public_vote_id(
            "senado_votaciones",
            "2024-05-08",
            "url:https://www.senado.es/legis15/votaciones/ses_19_179.xml",
        )
        self.assertEqual(public_vote_id, "senado_votaciones--20240508--f84b689b50")

    def test_derive_freshness_matches_truth_contract_thresholds(self) -> None:
        fresh = vote_explainer.derive_freshness("2026-04-01", "2026-04-04T12:00:00+00:00")
        aging = vote_explainer.derive_freshness("2026-03-20", "2026-04-04T12:00:00+00:00")
        stale = vote_explainer.derive_freshness("2026-02-10", "2026-04-04T12:00:00+00:00")

        self.assertEqual(fresh["tier"], "fresh")
        self.assertEqual(aging["tier"], "aging")
        self.assertEqual(stale["tier"], "stale")

    def test_export_writes_manifest_and_detail_contract(self) -> None:
        source_payload = {
            "meta": {"total": 1, "returned": 1},
            "events": [
                {
                    "vote_event_id": "url:https://www.senado.es/legis15/votaciones/ses_19_179.xml",
                    "source_id": "senado_votaciones",
                    "source_name": "Senado - Votaciones (OpenData)",
                    "source_url": "",
                    "vote_date": "2024-05-08",
                    "title": "Resto del proyecto de ley",
                    "expediente_text": "Proyecto de Ley de ejemplo.",
                    "subgroup_title": "",
                    "subgroup_text": "",
                    "assentimiento": "",
                    "initiative": None,
                    "totals": {
                        "present": 261,
                        "yes": 238,
                        "no": 7,
                        "abstain": 12,
                        "no_vote": 4,
                    },
                    "group_breakdown": [
                        {"group_code": "A", "yes": 100, "no": 0, "abstain": 0, "no_vote": 0, "other": 0, "total": 100},
                        {"group_code": "B", "yes": 90, "no": 1, "abstain": 0, "no_vote": 0, "other": 0, "total": 91},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_json = tmp_path / "votes-preview.json"
            out_dir = tmp_path / "vote-explainer"
            source_json.write_text(json.dumps(source_payload), encoding="utf-8")

            manifest, payloads = vote_explainer.export_vote_explainer_snapshot(
                source_json_path=source_json,
                out_dir=out_dir,
                snapshot_as_of_date="2026-04-02",
                generated_at="2026-04-04T12:00:00+00:00",
                source_snapshot_path="/explorer-votaciones/data/votes-preview.json",
                site_origin="https://gsusI.github.io",
                site_base_path="/vota-con-la-chola",
            )

            self.assertEqual(len(payloads), 1)
            detail = payloads[0]
            public_vote_id = detail["meta"]["public_vote_id"]
            detail_path = out_dir / f"{public_vote_id}.json"

            self.assertTrue((out_dir / "manifest.json").exists())
            self.assertTrue(detail_path.exists())

            self.assertEqual(detail["meta"]["canonical_path"], f"/vote-explainer/{public_vote_id}/")
            self.assertEqual(detail["result"]["status"], "approved")
            self.assertEqual(detail["result"]["confidence"], "medium")
            self.assertEqual(detail["social"]["canonical_url"], f"https://gsusI.github.io/vota-con-la-chola/vote-explainer/{public_vote_id}/")
            self.assertEqual(manifest["votes"][0]["canonical_path"], f"/vote-explainer/{public_vote_id}/")
            self.assertEqual(manifest["votes"][0]["top_caveat"]["code"], "initiative_missing")
            self.assertEqual(manifest["votes"][0]["top_caveat"]["label"], "Iniciativa oficial no enlazada")

            caveat_codes = {item["code"] for item in detail["caveats"]}
            self.assertIn("initiative_missing", caveat_codes)
            self.assertIn("event_source_url_missing", caveat_codes)
            self.assertIn("derived_result", caveat_codes)
            self.assertIn("subvote_not_whole_file", caveat_codes)
            self.assertIn("group_breakdown_partial", caveat_codes)


if __name__ == "__main__":
    unittest.main()
