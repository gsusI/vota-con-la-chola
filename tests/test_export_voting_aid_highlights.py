from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import export_voting_aid_highlights as hl

REPO = Path(__file__).resolve().parent.parent
PUBLISHED = REPO / "ui/site/public/citizen/data/voting_aid_highlights_v1.json"

BOE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<documento><metadatos><identificador>BOE-A-2024-1</identificador></metadatos><texto>
<p class="parrafo">Exposición de motivos.</p>
<p class="titulo_num">TÍTULO I</p><p class="titulo_tit">Medidas en materia de vivienda</p>
<p class="articulo">Artículo 1. Prórroga de la suspensión de desahucios.</p>
<p class="articulo">Artículo 2. Modificación de la Ley 12/2023, de 24 de mayo, por el derecho a la vivienda.</p>
<p class="articulo">«Artículo 5. Texto citado que no cuenta.</p>
<p class="titulo_num">TÍTULO II</p><p class="titulo_tit">Medidas de transporte</p>
<p class="capitulo_num">CAPÍTULO I</p><p class="capitulo_tit">Ayudas al transporte público</p>
<p class="articulo">Artículo 3. Objeto.</p>
<p class="capitulo_num">CAPÍTULO II</p><p class="capitulo_tit">Pensiones y Seguridad Social</p>
<p class="articulo">Disposición final primera. Modificación de la Ley 34/2002, de 11 de julio, de servicios de la sociedad de la información.</p>
<p class="articulo">Disposición final segunda. Entrada en vigor.</p>
</texto></documento>"""

BOCG_TEXT = """BOLETÍN OFICIAL DE LAS CORTES GENERALES
CONGRESO DE LOS DIPUTADOS
Exposición de motivos
El artículo 1 de la ley vigente dice algo. Por ello se propone la siguiente reforma.
Artículo único. Modificación de la Ley 29/1994, de 24 de noviembre, de Arrendamientos
Urbanos.
Uno. Se modifica el artículo 2, que queda redactado como sigue:
«Artículo 2. Arrendamiento de vivienda.
1. Texto.»
Dos. Se añade una disposición adicional décima, con la siguiente redacción:
«Disposición adicional décima. Índice de precios.
Texto.»
cve: BOCG-15-B-1-1
Disposición final única. Entrada en vigor.
La presente ley entrará en vigor al día siguiente."""


class TestParsers(unittest.TestCase):
    def test_boe_blocks_norms_and_riders(self) -> None:
        r = hl.parse_boe_xml(BOE_XML.encode("utf-8"))
        self.assertEqual(r["bullets"], ["Medidas en materia de vivienda", "Ayudas al transporte público", "Pensiones y Seguridad Social"])
        self.assertEqual(r["bullets_basis"], "bloques")
        self.assertEqual(r["modified_norms_total"], 2)
        self.assertEqual(r["riders"], ["Ley 34/2002, de 11 de julio, de servicios de la sociedad de la información"])
        scoped = hl.classify_scope(r, "Real Decreto-ley 1/2024, de medidas urgentes en materia de vivienda")
        self.assertTrue(scoped["omnibus"], scoped["themes"])
        self.assertEqual(scoped["offtopic_riders"], [])  # "sociedad de la información" maps to no theme

    def test_bocg_changes_skip_memorandum_and_quotes(self) -> None:
        r = hl.parse_bocg_text(BOCG_TEXT)
        self.assertEqual(r["bullets_basis"], "cambios")
        self.assertEqual(
            r["bullets"],
            [
                "Se modifica el artículo 2 (Artículo 2: Arrendamiento de vivienda)",
                "Se añade una disposición adicional décima (Disposición adicional décima: Índice de precios)",
            ],
        )
        self.assertEqual(r["modified_norms"], ["Ley 29/1994, de 24 de noviembre, de Arrendamientos Urbanos"])
        self.assertFalse(hl.classify_scope(r, "Proposición de ley de alquiler")["omnibus"])

    def test_single_theme_law_with_riders_is_not_omnibus_but_flags_offtopic(self) -> None:
        parsed = hl.finalize(
            ["Registro de grupos de interés", "Régimen sancionador"], [], [], ["Ley de transparencia", "Real Decreto de descarbonización del transporte"],
            ["Real Decreto de descarbonización del transporte"],
        )
        scoped = hl.classify_scope(parsed, "Real Decreto-ley de transparencia de los grupos de interés")
        self.assertFalse(scoped["omnibus"])
        self.assertEqual(scoped["offtopic_riders"], ["Real Decreto de descarbonización del transporte"])

    def test_rdl_eli_url(self) -> None:
        self.assertEqual(
            hl.rdl_eli_url("Real Decreto-ley 9/2024, de 23 de diciembre, por el que se adoptan medidas"),
            "https://www.boe.es/eli/es/rdl/2024/12/23/9/dof/spa/xml",
        )
        self.assertIsNone(hl.rdl_eli_url("Proposición de ley sobre algo"))


class TestPublishedHighlights(unittest.TestCase):
    def test_published_highlights_are_traceable(self) -> None:
        data = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        self.assertGreaterEqual(data["meta"]["documents"], 80)
        self.assertEqual(set(data["by_vote"].values()) - set(data["docs"]), set())
        for doc in data["docs"].values():
            self.assertRegex(doc["url"], r"^https://www\.(boe|congreso)\.es/")
            self.assertRegex(doc["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(doc["source"], {"BOE", "BOCG"})
            self.assertLessEqual(len(doc["bullets"]), hl.MAX_ITEMS)


if __name__ == "__main__":
    unittest.main()
