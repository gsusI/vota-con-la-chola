from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_explainability_copy import main


class TestReportCitizenExplainabilityCopy(unittest.TestCase):
    def _write_html(self, path: Path, body: str) -> None:
        path.write_text(body, encoding="utf-8")

    def test_main_passes_valid_glossary_copy_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            html_path = td_path / "citizen.html"
            out_path = td_path / "out.json"
            self._write_html(
                html_path,
                """
                <html><body>
                  <details data-explainability-glossary="1">
                    <summary data-explainability-copy="1">Primero mira cobertura y luego abre evidencia.</summary>
                    <span data-explainability-term="unknown" data-explainability-tooltip="1" title="Unknown significa incierto mas sin senal." data-term-definition="Unknown significa incierto mas sin senal.">unknown</span>
                    <span data-explainability-term="cobertura" data-explainability-tooltip="1" title="Cobertura es casos con postura clara." data-term-definition="Cobertura es casos con postura clara.">cobertura</span>
                    <span data-explainability-term="confianza" data-explainability-tooltip="1" title="Confianza muestra respaldo de evidencia." data-term-definition="Confianza muestra respaldo de evidencia.">confianza</span>
                    <span data-explainability-term="evidencia" data-explainability-tooltip="1" title="Evidencia abre fuente para auditar." data-term-definition="Evidencia abre fuente para auditar.">evidencia</span>
                    <li data-explainability-copy="1">Unknown no implica apoyo ni rechazo.</li>
                  </details>
                </body></html>
                """,
            )
            rc = main(
                [
                    "--ui-html",
                    str(html_path),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)

            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "ok")
            self.assertTrue(bool(got["checks"]["contract_complete"]))
            self.assertEqual(int(got["metrics"]["glossary_terms_total"]), 4)
            self.assertEqual(int(got["metrics"]["jargon_hits_total"]), 0)

    def test_main_strict_fails_when_definition_is_too_long(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            html_path = td_path / "citizen_long_def.html"
            out_path = td_path / "out_failed.json"
            self._write_html(
                html_path,
                """
                <html><body>
                  <div data-explainability-glossary="1">
                    <div data-explainability-copy="1">Primero mira cobertura.</div>
                    <span data-explainability-term="unknown" data-explainability-tooltip="1" title="Unknown largo." data-term-definition="Unknown significa incierto mas sin senal y ademas repite muchas palabras para romper de forma intencional el limite de este test.">unknown</span>
                    <span data-explainability-term="cobertura" data-explainability-tooltip="1" title="Cobertura breve." data-term-definition="Cobertura breve.">cobertura</span>
                    <span data-explainability-term="confianza" data-explainability-tooltip="1" title="Confianza breve." data-term-definition="Confianza breve.">confianza</span>
                    <span data-explainability-term="evidencia" data-explainability-tooltip="1" title="Evidencia breve." data-term-definition="Evidencia breve.">evidencia</span>
                  </div>
                </body></html>
                """,
            )
            rc = main(
                [
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
            self.assertIn("definition_words_over_limit", set(got.get("failure_reasons") or []))

    def test_main_degraded_without_help_copy_fails_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            html_path = td_path / "citizen_degraded.html"
            out_path = td_path / "out_degraded.json"
            self._write_html(
                html_path,
                """
                <html><body>
                  <div data-explainability-glossary="1">
                    <span data-explainability-term="unknown" data-explainability-tooltip="1" title="Unknown significa incierto mas sin senal." data-term-definition="Unknown significa incierto mas sin senal.">unknown</span>
                    <span data-explainability-term="cobertura" data-explainability-tooltip="1" title="Cobertura es casos con postura clara." data-term-definition="Cobertura es casos con postura clara.">cobertura</span>
                    <span data-explainability-term="confianza" data-explainability-tooltip="1" title="Confianza muestra respaldo de evidencia." data-term-definition="Confianza muestra respaldo de evidencia.">confianza</span>
                    <span data-explainability-term="evidencia" data-explainability-tooltip="1" title="Evidencia abre fuente para auditar." data-term-definition="Evidencia abre fuente para auditar.">evidencia</span>
                  </div>
                </body></html>
                """,
            )
            rc = main(
                [
                    "--ui-html",
                    str(html_path),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "degraded")
            self.assertFalse(bool(got["checks"]["contract_complete"]))
            self.assertIn("help_copy_missing", set(got.get("degraded_reasons") or []))


if __name__ == "__main__":
    unittest.main()
