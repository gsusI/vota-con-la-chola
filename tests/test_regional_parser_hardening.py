from __future__ import annotations

import unittest
from unittest.mock import patch

from etl.politicos_es.connectors.cortes_clm import parse_cclm_detail, parse_cclm_list_rows
from etl.politicos_es.connectors.parlamento_andalucia import parse_pa_list_ids
from etl.politicos_es.connectors.parlamento_vasco import (
    build_parlamento_vasco_records,
    parse_member_row,
    parse_vasco_detail_profile,
)


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

    @patch("etl.politicos_es.connectors.parlamento_vasco.http_get_bytes")
    def test_build_vasco_records_enriches_from_profile_page(self, fake_http_get_bytes) -> None:
        list_row = "<tr><td><a href=\"/fichas/c_21.html\">Kalea, Iñigo</a></td></tr>"
        list_html = f"<table>{list_row * 55}</table>"
        profile_payload = (b"<div>Parlamentario del Grupo Grupo Mixto-Sumar (21.05.2024 - )</div>", "text/html")

        def fake_get(*_args, **_kwargs):
            fake_get.calls += 1
            if fake_get.calls == 1:
                return list_html.encode("utf-8"), "text/html"
            return profile_payload

        fake_get.calls = 0
        fake_http_get_bytes.side_effect = fake_get

        records = build_parlamento_vasco_records(timeout=5)
        self.assertEqual(len(records), 55)
        self.assertEqual(records[0]["group_name"], "Mixto-Sumar")
        self.assertEqual(records[0]["start_date"], "2024-05-21")

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

    def test_parse_vasco_detail_profile_extracts_group_and_dates(self) -> None:
        html = """
        <html><body>
        <div>Parlamentario del Grupo Grupo Mixto-Sumar (21.05.2024 - )</div>
        <div>Otra mención Grupo Parlamentario PSOE (01.01.2020 - 31.12.2020)</div>
        </body></html>
        """
        parsed = parse_vasco_detail_profile(html)
        self.assertEqual(parsed["group_name"], "Mixto-Sumar")
        self.assertEqual(parsed["start_date"], "2024-05-21")
        self.assertNotIn("end_date", parsed)

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
