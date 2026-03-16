from __future__ import annotations

import unittest

from scripts.scrape_liberty_delegated_person_window_boe_candidates import (
    _extract_person_hint,
    _institution_tokens,
    build_query,
    build_query_variants,
    parse_boe_search_results,
)


SAMPLE_HTML = """
<ul>
  <li class="resultado-busqueda">
    <p class="linea-dem">Ministerio del Interior</p>
    <p class="linea-pub">BOE 301 de 17/12/2003 - II. Autoridades y personal</p>
    <p>Orden INT/3514/2003, de 5 de diciembre, por la que se dispone el nombramiento de don Mariano Fernández Fernández como Subdirector General de Normativa y Recursos de la Dirección General de Tráfico.</p>
    <a href="../buscar/doc.php?id=BOE-A-2003-23115" class="resultado-busqueda-link-defecto">Más...</a>
  </li>
  <li class="resultado-busqueda">
    <p class="linea-dem">Ministerio de Hacienda</p>
    <p class="linea-pub">BOE 140 de 14/06/2006 - II. Autoridades y personal</p>
    <p>Real Decreto 754/2006, de 13 de junio, por el que se dispone el nombramiento de doña Pilar Valiente Ayala como Directora General de la Agencia Estatal de Administración Tributaria.</p>
    <a href="../buscar/doc.php?id=BOE-A-2006-11416" class="resultado-busqueda-link-defecto">Más...</a>
  </li>
</ul>
"""


class TestScrapeLibertyDelegatedBoeCandidates(unittest.TestCase):
    def test_parse_boe_search_results(self) -> None:
        rows = parse_boe_search_results(SAMPLE_HTML)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].boe_id, "BOE-A-2003-23115")
        self.assertEqual(rows[0].publication_date, "17/12/2003")
        self.assertIn("Subdirector General", rows[0].title)
        self.assertEqual(rows[1].boe_id, "BOE-A-2006-11416")
        self.assertEqual(rows[1].publication_date, "14/06/2006")

    def test_extract_person_hint(self) -> None:
        title = (
            "Real Decreto 754/2006, de 13 de junio, por el que se dispone "
            "el nombramiento de doña Pilar Valiente Ayala como Directora General."
        )
        hint = _extract_person_hint(title)
        self.assertEqual(hint, "Pilar Valiente Ayala")

    def test_extract_person_hint_for_nombramiento_como_de_don(self) -> None:
        title = (
            "Resolución de 4 de junio de 2008, de la Presidencia de la Agencia Estatal "
            "de Administración Tributaria, por la que se dispone el nombramiento como "
            "Delegado Especial de la Agencia Estatal de Administración Tributaria de Galicia "
            "de don Luis Antonio Pazos Franco."
        )
        hint = _extract_person_hint(title)
        self.assertEqual(hint, "Luis Antonio Pazos Franco")

    def test_extract_person_hint_trims_trailing_punctuation(self) -> None:
        title = (
            "Resolución de 8 de febrero de 2006, de la Presidencia de la Agencia Estatal "
            "de Administración Tributaria, por la que se dispone el nombramiento de don "
            "Jesús Manuel Andradas Heranz, como Delegado de Planificación y Control."
        )
        hint = _extract_person_hint(title)
        self.assertEqual(hint, "Jesús Manuel Andradas Heranz")

    def test_build_query(self) -> None:
        query = build_query("Direccion General", "DGT")
        self.assertEqual(query, "nombramiento Direccion General DGT")

    def test_build_query_variants_includes_acronym_expansion(self) -> None:
        variants = build_query_variants("Direccion General", "DGT")
        self.assertIn("nombramiento Direccion General DGT", variants)
        self.assertIn("nombramiento Dirección General de Tráfico", variants)
        self.assertIn("nombramiento Director General de Tráfico", variants)
        self.assertIn('nombramiento "Director General de Tráfico"', variants)

    def test_build_query_variants_expands_aeat_role_phrase(self) -> None:
        variants = build_query_variants("Direccion General de la AEAT", "AEAT")
        self.assertIn(
            "nombramiento Director General de la Agencia Estatal de Administración Tributaria",
            variants,
        )
        self.assertIn(
            'nombramiento "Director General de la Agencia Estatal de Administración Tributaria"',
            variants,
        )

    def test_institution_tokens_include_acronym_expansion_terms(self) -> None:
        tokens = _institution_tokens("AEAT")
        self.assertIn("aeat", tokens)
        self.assertIn("agencia", tokens)
        self.assertIn("tributaria", tokens)


if __name__ == "__main__":
    unittest.main()
