from __future__ import annotations

import unittest
from unittest.mock import patch

from etl.politicos_es.connectors.cortes_clm import parse_cclm_detail, parse_cclm_list_rows
from etl.politicos_es.connectors.parlamento_andalucia import parse_pa_list_ids
from etl.politicos_es.connectors.parlamento_vasco import parse_member_row


class TestRegionalParserHardening(unittest.TestCase):
    def test_parse_pa_list_ids_accepts_single_quotes_and_skips_renuncias(self) -> None:
        html = """
        <div>
          <a href='/webdinamica/portal-web-parlamento/composicionyfuncionamiento/diputadosysenadores.do?accion=Ver Diputados&codmie=111&nlegis=15'>A</a>
          <a href="/webdinamica/portal-web-parlamento/composicionyfuncionamiento/diputadosysenadores.do?accion=Ver%20Diputados&codmie=222&nlegis=16">B</a>
          Listado de renuncias
          <a href='...accion=Ver Diputados&codmie=333&nlegis=17'>C</a>
        </div>
        """
        ids = parse_pa_list_ids(html)
        self.assertEqual(ids, [("111", "15"), ("222", "16")])

    def test_parse_vasco_member_row_handles_single_quotes_and_dash_dates(self) -> None:
        tr_html = """
        <tr>
          <td><a href='/fichas/c_42.html'>Barea Barea, Nerea</a> GP EA-NV (14-05-2024 - 16-06-2024)</td>
        </tr>
        """
        row = parse_member_row(tr_html)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["member_id"], "42")
        self.assertEqual(row["full_name"], "Nerea Barea Barea")
        self.assertEqual(row["group_name"], "EA-NV")
        self.assertEqual(row["start_date"], "2024-05-14")
        self.assertEqual(row["end_date"], "2024-06-16")

    def test_parse_vasco_member_row_handles_mixed_case_group(self) -> None:
        tr_html = """
        <tr>
          <td><a href='/fichas/c_21.html'>Kalea, Iñigo</a> GP Mixto-Sumar (01.11.2024 - )</td>
        </tr>
        """
        row = parse_member_row(tr_html)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["group_name"], "Mixto-Sumar")

    def test_parse_cclm_rows_fallback_without_pristine_p_tags(self) -> None:
        html = """
        <table>
          <tr>
            <td><a href='javascript:abrirventana(789, 11);'>Marí, Pepa</a></td>
            <td>Granada</td>
            <td>11</td>
            <td>PSOE</td>
          </tr>
        </table>
        """
        rows = parse_cclm_list_rows(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "789")
        self.assertEqual(rows[0]["full_name"], "Marí, Pepa")
        self.assertEqual(rows[0]["provincia"], "Granada")
        self.assertEqual(rows[0]["group_acronym"], "PSOE")

    @patch("etl.politicos_es.connectors.cortes_clm.http_get_bytes")
    def test_parse_cclm_detail_falls_back_to_gp_pattern(self, fake_http_get) -> None:
        fake_http_get.return_value = (
            """
            <html><h1>Marí, Pepa</h1><div>GRUPO PARLAMENTARIO PSOE</div></html>
            """.encode(),
            "text/html",
        )
        rec = parse_cclm_detail("789", timeout=5)
        self.assertEqual(rec["group_name"], "PSOE")


if __name__ == "__main__":
    unittest.main()
