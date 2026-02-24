from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_tailwind_md3_visual_drift_digest import main


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _contract_ok_payload(card: int, chip: int, button: int, tab: int) -> dict:
    return {
        "status": "ok",
        "checks": {
            "token_sections_present": True,
            "token_schema_version_valid": True,
            "generated_css_within_budget": True,
            "generated_css_markers_present": True,
            "ui_html_markers_present": True,
            "md3_card_markers_meet_minimum": True,
            "md3_chip_markers_meet_minimum": True,
            "md3_button_markers_meet_minimum": True,
            "md3_tab_markers_meet_minimum": True,
        },
        "failure_reasons": [],
        "metrics": {
            "md3_card_markers": card,
            "md3_chip_markers": chip,
            "md3_button_markers": button,
            "md3_tab_markers": tab,
        },
    }


class TestReportCitizenTailwindMd3VisualDriftDigest(unittest.TestCase):
    def test_main_passes_strict_when_source_and_published_are_in_parity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source_tokens = td_path / "ui" / "tailwind_md3.tokens.json"
            source_css = td_path / "ui" / "tailwind_md3.generated.css"
            source_html = td_path / "ui" / "index.html"
            pub_tokens = td_path / "pub" / "tailwind_md3.tokens.json"
            pub_data_tokens = td_path / "pub" / "data" / "tailwind_md3.tokens.json"
            pub_css = td_path / "pub" / "tailwind_md3.generated.css"
            pub_html = td_path / "pub" / "index.html"
            contract_json = td_path / "contract.json"
            out_path = td_path / "drift.json"

            tokens_text = "{\n  \"schema_version\": \"md3-tailwind-v1\"\n}\n"
            css_text = "/* generated_by=build_citizen_tailwind_md3_css.py */\n.md3-card{display:block;}\n"
            html_text = (
                "<html><head><link rel=\"stylesheet\" href=\"./tailwind_md3.generated.css\"></head>"
                "<body><div class=\"md3-card\"></div><div class=\"md3-chip\"></div>"
                "<button class=\"md3-button\"></button><button class=\"md3-tab\"></button></body></html>\n"
            )

            _write_text(source_tokens, tokens_text)
            _write_text(source_css, css_text)
            _write_text(source_html, html_text)
            _write_text(pub_tokens, tokens_text)
            _write_text(pub_data_tokens, tokens_text)
            _write_text(pub_css, css_text)
            _write_text(pub_html, html_text)
            _write_json(contract_json, _contract_ok_payload(card=1, chip=1, button=1, tab=1))

            rc = main(
                [
                    "--tailwind-contract-json",
                    str(contract_json),
                    "--source-tokens",
                    str(source_tokens),
                    "--source-css",
                    str(source_css),
                    "--source-ui-html",
                    str(source_html),
                    "--published-tokens",
                    str(pub_tokens),
                    "--published-data-tokens",
                    str(pub_data_tokens),
                    "--published-css",
                    str(pub_css),
                    "--published-ui-html",
                    str(pub_html),
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)
            got = _read_json(out_path)
            self.assertEqual(str(got.get("status") or ""), "ok")
            self.assertEqual(list(got.get("strict_fail_reasons") or []), [])
            self.assertEqual(bool(got["checks"]["css_parity_ok"]), True)
            self.assertEqual(bool(got["checks"]["source_published_marker_counts_match"]), True)

    def test_main_fails_strict_when_published_css_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source_tokens = td_path / "ui" / "tailwind_md3.tokens.json"
            source_css = td_path / "ui" / "tailwind_md3.generated.css"
            source_html = td_path / "ui" / "index.html"
            pub_tokens = td_path / "pub" / "tailwind_md3.tokens.json"
            pub_data_tokens = td_path / "pub" / "data" / "tailwind_md3.tokens.json"
            pub_css = td_path / "pub" / "tailwind_md3.generated.css"
            pub_html = td_path / "pub" / "index.html"
            contract_json = td_path / "contract.json"
            out_path = td_path / "drift_fail.json"

            tokens_text = "{\n  \"schema_version\": \"md3-tailwind-v1\"\n}\n"
            source_css_text = "/* generated_by=build_citizen_tailwind_md3_css.py */\n.md3-card{display:block;}\n"
            published_css_text = "/* generated_by=build_citizen_tailwind_md3_css.py */\n.md3-card{display:grid;}\n"
            html_text = (
                "<html><head><link rel=\"stylesheet\" href=\"./tailwind_md3.generated.css\"></head>"
                "<body><div class=\"md3-card\"></div><div class=\"md3-chip\"></div>"
                "<button class=\"md3-button\"></button><button class=\"md3-tab\"></button></body></html>\n"
            )

            _write_text(source_tokens, tokens_text)
            _write_text(source_css, source_css_text)
            _write_text(source_html, html_text)
            _write_text(pub_tokens, tokens_text)
            _write_text(pub_data_tokens, tokens_text)
            _write_text(pub_css, published_css_text)
            _write_text(pub_html, html_text)
            _write_json(contract_json, _contract_ok_payload(card=1, chip=1, button=1, tab=1))

            rc = main(
                [
                    "--tailwind-contract-json",
                    str(contract_json),
                    "--source-tokens",
                    str(source_tokens),
                    "--source-css",
                    str(source_css),
                    "--source-ui-html",
                    str(source_html),
                    "--published-tokens",
                    str(pub_tokens),
                    "--published-data-tokens",
                    str(pub_data_tokens),
                    "--published-css",
                    str(pub_css),
                    "--published-ui-html",
                    str(pub_html),
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)
            got = _read_json(out_path)
            self.assertEqual(str(got.get("status") or ""), "failed")
            self.assertIn("css_parity_mismatch", list(got.get("strict_fail_reasons") or []))


if __name__ == "__main__":
    unittest.main()
