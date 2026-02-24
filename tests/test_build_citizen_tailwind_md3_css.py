from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_citizen_tailwind_md3_css import main


TOKENS_FIXTURE = {
    "schema_version": "md3-tailwind-v1",
    "colors": {
        "primary": "#0b57d0",
        "on_primary": "#ffffff",
        "secondary": "#146c94",
        "on_secondary": "#ffffff",
        "surface": "#fefbff",
        "surface_container": "#f3edf7",
        "surface_variant": "#e7e0ec",
        "on_surface": "#1d1b20",
        "on_surface_variant": "#49454f",
        "outline": "#79747e",
        "error": "#b3261e",
        "on_error": "#ffffff",
        "success": "#0f766e",
        "warning": "#b45309",
        "info": "#1d4ed8",
    },
    "radii": {"sm": "10px", "md": "14px", "lg": "18px", "full": "999px"},
    "shadows": {"sm": "0 1px 2px rgba(0,0,0,0.1)", "md": "0 4px 12px rgba(0,0,0,0.15)"},
    "spacing": {"1": "4px", "2": "8px", "3": "12px"},
    "typography": {"sans": "sans-serif", "mono": "monospace"},
}


class TestBuildCitizenTailwindMd3Css(unittest.TestCase):
    def test_main_builds_css_with_md3_markers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tokens_path = td_path / "tokens.json"
            out_path = td_path / "generated.css"
            tokens_path.write_text(json.dumps(TOKENS_FIXTURE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            rc = main(["--tokens", str(tokens_path), "--out", str(out_path)])
            self.assertEqual(rc, 0)
            self.assertTrue(out_path.exists())
            css = out_path.read_text(encoding="utf-8")
            self.assertIn("generated_by=build_citizen_tailwind_md3_css.py", css)
            self.assertIn("--md3-color-primary:", css)
            self.assertIn(".md3-card", css)
            self.assertIn(".md3-button", css)
            self.assertIn(".md3-button-primary", css)
            self.assertIn(".md3-tab", css)
            self.assertIn(".tw-bg-surface", css)

    def test_main_check_mode_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tokens_path = td_path / "tokens.json"
            out_path = td_path / "generated.css"
            tokens_path.write_text(json.dumps(TOKENS_FIXTURE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            rc_build = main(["--tokens", str(tokens_path), "--out", str(out_path)])
            self.assertEqual(rc_build, 0)
            out_path.write_text("/* drift */\n", encoding="utf-8")

            rc_check = main(["--tokens", str(tokens_path), "--out", str(out_path), "--check"])
            self.assertEqual(rc_check, 4)


if __name__ == "__main__":
    unittest.main()
