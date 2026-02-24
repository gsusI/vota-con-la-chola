from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_citizen_tailwind_md3_css import main as build_main
from scripts.report_citizen_tailwind_md3_contract import main


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


class TestReportCitizenTailwindMd3Contract(unittest.TestCase):
    def test_main_passes_strict_when_tokens_css_and_ui_markers_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tokens_path = td_path / "tokens.json"
            css_path = td_path / "tailwind_md3.generated.css"
            html_path = td_path / "index.html"
            out_path = td_path / "report.json"

            tokens_path.write_text(json.dumps(TOKENS_FIXTURE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(build_main(["--tokens", str(tokens_path), "--out", str(css_path)]), 0)
            html_path.write_text(
                "\n".join(
                    [
                        "<!doctype html>",
                        "<html><head><link rel=\"stylesheet\" href=\"./tailwind_md3.generated.css\"></head>",
                        (
                            "<body>"
                            "<div class=\"md3-card\"><span class=\"md3-chip\">x</span>"
                            "<button class=\"md3-button\">ok</button>"
                            "<button class=\"md3-tab active\">tab</button>"
                            "</div></body></html>"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rc = main(
                [
                    "--tokens",
                    str(tokens_path),
                    "--generated-css",
                    str(css_path),
                    "--ui-html",
                    str(html_path),
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)

            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "ok")
            self.assertEqual(got["failure_reasons"], [])
            self.assertTrue(got["checks"]["ui_html_markers_present"])

    def test_main_fails_strict_when_ui_markers_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tokens_path = td_path / "tokens.json"
            css_path = td_path / "tailwind_md3.generated.css"
            html_path = td_path / "index.html"
            out_path = td_path / "report.json"

            tokens_path.write_text(json.dumps(TOKENS_FIXTURE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(build_main(["--tokens", str(tokens_path), "--out", str(css_path)]), 0)
            html_path.write_text("<!doctype html><html><body>no markers</body></html>\n", encoding="utf-8")

            rc = main(
                [
                    "--tokens",
                    str(tokens_path),
                    "--generated-css",
                    str(css_path),
                    "--ui-html",
                    str(html_path),
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("ui_html_markers_missing", got["failure_reasons"])


if __name__ == "__main__":
    unittest.main()
