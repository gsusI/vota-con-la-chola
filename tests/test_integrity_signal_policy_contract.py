from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class TestIntegritySignalPolicyContract(unittest.TestCase):
    def test_policy_contains_publication_and_correction_safety_gates(self) -> None:
        policy = (ROOT / "docs/method/integrity-signal-policy.md").read_text(encoding="utf-8")
        required = {
            "review_signal",
            "corroborated_risk",
            "official_finding",
            "causal_impact_not_claimed",
            "merit_blame_not_scored",
            "counterevidence",
            "right-of-reply",
            "No model-generated label can satisfy human-review gates",
            "never silently rewritten",
            "false-positive",
        }
        missing = sorted(token for token in required if token not in policy)
        self.assertEqual(missing, [])

    def test_community_templates_are_valid_and_collect_primary_evidence(self) -> None:
        for relative_path in (
            ".github/ISSUE_TEMPLATE/data_correction.yml",
            ".github/ISSUE_TEMPLATE/integrity_signal_review.yml",
        ):
            payload = yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))
            self.assertIsInstance(payload, dict)
            body = payload.get("body") or []
            ids = [item.get("id") for item in body if isinstance(item, dict) and item.get("id")]
            self.assertEqual(len(ids), len(set(ids)))
            rendered = str(payload).lower()
            self.assertIn("primary evidence", rendered)
            self.assertNotIn("/users/", rendered)

    def test_security_conduct_and_citation_entrypoints_exist(self) -> None:
        for relative_path in ("CODE_OF_CONDUCT.md", "SECURITY.md", "CITATION.cff"):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)
        citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
        self.assertEqual(citation["repository-code"], "https://github.com/gsusI/vota-con-la-chola")
        self.assertEqual(citation["license"], "MIT")


if __name__ == "__main__":
    unittest.main()
