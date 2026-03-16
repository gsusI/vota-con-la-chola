from __future__ import annotations

import unittest

from scripts.build_programas_deeplink_manifest import (
    build_path_guess_candidates,
    extract_candidate_links,
    extract_candidate_links_scored,
    score_anchor_text,
    score_deeplink_url,
    score_programmatic_text,
)


class TestBuildProgramasDeeplinkManifest(unittest.TestCase):
    def test_score_deeplink_url_positive_vs_negative(self) -> None:
        pos = score_deeplink_url("https://example.org/programa-electoral-2027")
        neg = score_deeplink_url("https://example.org/politica-de-cookies")
        self.assertGreater(pos, 0)
        self.assertLess(neg, 0)
        self.assertGreater(pos, neg)

    def test_score_programmatic_text_detects_policy_language(self) -> None:
        policy = score_programmatic_text(
            "Nuestro programa electoral propone mejorar vivienda y empleo, y reducir impuestos."
        )
        legal = score_programmatic_text(
            "Este sitio web utiliza cookies. Politica de privacidad y aviso legal."
        )
        self.assertGreater(policy, 0)
        self.assertLess(legal, 0)
        self.assertGreater(policy, legal)

    def test_score_programmatic_text_penalizes_navigation_noise(self) -> None:
        noisy = score_programmatic_text(
            "Menu noticias actualidad siguenos facebook twitter instagram youtube contacto etiqueta etiqueta"
        )
        self.assertLess(noisy, 0)

    def test_score_deeplink_url_prefers_recent_program_docs_over_old_reports(self) -> None:
        recent_program = score_deeplink_url("https://example.org/wp-content/uploads/2025/10/programa-electoral.pdf")
        old_report = score_deeplink_url("https://example.org/dokumentuak/gardentasuna/2015_eleccionesjjggmayo.pdf")
        self.assertGreater(recent_program, old_report)

    def test_extract_candidate_links_resolves_and_filters_domain(self) -> None:
        html = """
        <html><body>
          <a href="/programa">Programa</a>
          <a href="https://example.org/propuestas">Propuestas</a>
          <a href="https://other.example.net/programa">Other domain</a>
          <a href="mailto:test@example.org">mail</a>
          <a href="#fragment">frag</a>
        </body></html>
        """
        links = extract_candidate_links("https://example.org/", html, same_domain_only=True)
        self.assertIn("https://example.org/programa", links)
        self.assertIn("https://example.org/propuestas", links)
        self.assertNotIn("https://other.example.net/programa", links)
        self.assertEqual(len(links), 2)

    def test_score_anchor_text_positive_vs_negative(self) -> None:
        pos = score_anchor_text("Consulta nuestro programa electoral")
        neg = score_anchor_text("Aviso legal y politica de privacidad")
        self.assertGreater(pos, 0)
        self.assertLess(neg, 0)

    def test_extract_candidate_links_scored_includes_anchor_signal(self) -> None:
        html = """
        <html><body>
          <a href="/documento">Programa electoral completo</a>
          <a href="/nota-prensa">Actualidad</a>
        </body></html>
        """
        candidates = extract_candidate_links_scored("https://example.org/", html, same_domain_only=True)
        by_url = {c["url"]: c for c in candidates}
        self.assertIn("https://example.org/documento", by_url)
        self.assertGreater(int(by_url["https://example.org/documento"]["anchor_score"]), 0)
        self.assertIn("https://example.org/nota-prensa", by_url)

    def test_build_path_guess_candidates_contains_programa_routes(self) -> None:
        guessed = build_path_guess_candidates("https://example.org/base/")
        urls = {item["url"] for item in guessed}
        self.assertIn("https://example.org/programa", urls)
        self.assertIn("https://example.org/programa-electoral", urls)
        self.assertIn("https://example.org/propuestas", urls)


if __name__ == "__main__":
    unittest.main()
