import json
import unittest
from pathlib import Path

from scripts.prepare_hf_scale_rollback import (
    PLAN_SCHEMA_VERSION,
    validate_plan_artifact,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / (
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "hf-scale-origin-rollback-plan-20260812.json"
)


class PrepareHfScaleRollbackTests(unittest.TestCase):
    def test_real_rollback_plan_is_bound_to_verified_evidence(self) -> None:
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

        self.assertEqual(plan["schema_version"], PLAN_SCHEMA_VERSION)
        self.assertEqual(validate_plan_artifact(plan, REPO_ROOT), [])
        self.assertEqual(plan["delta"]["rows"], 0)
        self.assertEqual(plan["delta"]["data_files"], 0)
        self.assertEqual(plan["delta"]["data_bytes"], 0)
        self.assertFalse(plan["operation"]["mutation_performed"])
        self.assertFalse(plan["activation"]["authorized"])
        self.assertFalse(plan["supersession"]["immutable_deletion_allowed"])
        self.assertTrue(plan["supersession"]["preserve_both_immutable_releases"])
        self.assertTrue(plan["public_domain_personal_information_retained"])


if __name__ == "__main__":
    unittest.main()
