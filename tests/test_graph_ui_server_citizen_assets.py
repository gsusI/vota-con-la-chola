from __future__ import annotations

import unittest
from pathlib import Path


class TestGraphUiServerCitizenAssets(unittest.TestCase):
    def test_citizen_asset_routes_include_onboarding_first_answer_and_unknown_modules(self) -> None:
        src = Path("scripts/graph_ui_server.py").read_text(encoding="utf-8")
        self.assertIn('"/citizen/onboarding_funnel.js"', src)
        self.assertIn('"/citizen/first_answer_accelerator.js"', src)
        self.assertIn('"/citizen/unknown_explainability.js"', src)
        self.assertIn('"/citizen/cross_method_stability.js"', src)
        self.assertIn('"/citizen/evidence_trust_panel.js"', src)
        self.assertIn('"/citizen/tailwind_md3.generated.css"', src)
        self.assertIn('"/citizen/tailwind_md3.tokens.json"', src)
        self.assertIn('"/citizen/data/tailwind_md3.tokens.json"', src)
        self.assertIn("UI_CITIZEN_ONBOARDING_FUNNEL", src)
        self.assertIn("UI_CITIZEN_FIRST_ANSWER_ACCELERATOR", src)
        self.assertIn("UI_CITIZEN_UNKNOWN_EXPLAINABILITY", src)
        self.assertIn("UI_CITIZEN_CROSS_METHOD_STABILITY", src)
        self.assertIn("UI_CITIZEN_EVIDENCE_TRUST_PANEL", src)
        self.assertIn("UI_CITIZEN_TAILWIND_MD3_CSS", src)
        self.assertIn("UI_CITIZEN_TAILWIND_MD3_TOKENS", src)

    def test_citizen_data_routes_include_concern_pack_quality_snapshot(self) -> None:
        src = Path("scripts/graph_ui_server.py").read_text(encoding="utf-8")
        self.assertIn('"/citizen/data/concern_pack_quality.json"', src)


if __name__ == "__main__":
    unittest.main()
