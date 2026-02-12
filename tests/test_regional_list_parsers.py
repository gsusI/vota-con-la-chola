from __future__ import annotations

import unittest

from etl.politicos_es.connectors.cortes_cyl import parse_ccyl_procuradores_list
from etl.politicos_es.connectors.corts_valencianes import parse_corts_profile_urls


class TestCortsValencianesProfileUrls(unittest.TestCase):
    def test_parse_profile_urls_supports_relative_and_absolute(self) -> None:
        html = """
        <html>
          <a href="/es/composicion/diputados/xi/abad_soler_ramon/14e506aa72d70d597b755db69897d454">Abad</a>
          <a href='https://www.cortsvalencianes.es/es/composicion/diputados/XII/other/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'>Otro</a>
          <a href="/es/composicion/otros/xx">Nope</a>
        </html>
        """

        urls = parse_corts_profile_urls(html)
        self.assertEqual(len(urls), 2)
        self.assertIn(
            "https://www.cortsvalencianes.es/es/composicion/diputados/xi/abad_soler_ramon/14e506aa72d70d597b755db69897d454",
            urls,
        )
        self.assertIn(
            "https://www.cortsvalencianes.es/es/composicion/diputados/XII/other/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            urls,
        )


class TestCortesCylProcuradoresList(unittest.TestCase):
    def test_parse_list_uses_dom_and_fallback_fields(self) -> None:
        html = """
        <div class="item">
          <a href="/Organizacion/Procurador?Legislatura=11&amp;CodigoPersona=P11034">Juan Pérez</a>
          <span class="cc_org_Procurador">Juan Pérez</span>
          <span class="cc_org_ProcuradorGrupoParlamentario">PSOE</span>
          <span class="cc_org_ProcuradorGrupoProvincia">Zamora</span>
        </div>
        <div class="item">
          <a href='/Organizacion/Procurador?Legislatura=11&amp;CodigoPersona=P11035'>María Ruiz</a>
          <div>Grupo Parlamentario: PP</div>
          <div>Provincia: Lugo</div>
        </div>
        """

        rows = parse_ccyl_procuradores_list(html)
        self.assertEqual(len(rows), 2)

        first = rows[0]
        self.assertEqual(first["source_record_id"], "leg:11;persona:P11034")
        self.assertEqual(first["full_name"], "Juan Pérez")
        self.assertEqual(first["group_name"], "PSOE")
        self.assertEqual(first["province"], "Zamora")
        self.assertEqual(first["detail_url"], "https://www.ccyl.es/Organizacion/Procurador?Legislatura=11&CodigoPersona=P11034")

        second = rows[1]
        self.assertEqual(second["full_name"], "María Ruiz")
        self.assertEqual(second["group_name"], "PP")
        self.assertEqual(second["province"], "Lugo")

    def test_parse_skips_invalid_links(self) -> None:
        html = """
        <a href="/otra/ruta?a=1">Nope</a>
        <a href="/Organizacion/Procurador?Legislatura=XX&amp;CodigoPersona=BAD">Nope</a>
        """
        with self.assertRaisesRegex(RuntimeError, "No se encontraron procuradores"):
            parse_ccyl_procuradores_list(html)


if __name__ == "__main__":
    unittest.main()
