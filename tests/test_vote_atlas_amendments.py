from __future__ import annotations

import unittest

from scripts import vote_atlas_amendments as am

DOC = """
ENMIENDA NÚM. 12

                                   Grupo Parlamentario Popular
                                   en el Congreso

    Al artículo 3
    De modificación.
    Texto que se propone: «Artículo 3. Se reduce el plazo a diez días.»
    JUSTIFICACIÓN
    Agilizar.
cve: BOCG-15-A-9-4
ENMIENDA NÚM. 13

                                   Sergio Sayas López
                                   (Grupo Parlamentario Mixto)

    ALTAS
    Sección: 17 MINISTERIO DE TRANSPORTES
    Observ.: Variante de Tudela
"""


class AmendmentMatchingTest(unittest.TestCase):
    def test_parse_amendments(self) -> None:
        parsed = am.parse_amendments(DOC)
        self.assertEqual(sorted(parsed), ["12", "13"])
        self.assertIn("Grupo Parlamentario Popular", parsed["12"]["firmante"])
        self.assertTrue(parsed["12"]["body"].startswith("Al artículo 3"))
        self.assertIn("Sayas", parsed["13"]["firmante"])

    def test_expand_numbers(self) -> None:
        self.assertEqual(am.expand_numbers("Enmienda 327."), ["327"])
        self.assertEqual(am.expand_numbers("Enmiendas 12, 15 y 35 a 37."), ["12", "15", "35", "36", "37"])
        # The transactional's own number is not an amendment number.
        self.assertEqual(
            am.expand_numbers("Enmienda transaccional número 2 a las enmiendas 36 del Grupo Mixto y 99 del Grupo Republicano."),
            ["36", "99"],
        )
        self.assertEqual(am.expand_numbers("Segunda votación de las enmiendas 25 y 35 a 37."), ["25", "35", "36", "37"])
        self.assertEqual(am.expand_numbers("Enmienda transaccional nº 20, a la enmienda 590 del Grupo Parlamentario Republicano."), ["590"])
        self.assertEqual(am.expand_numbers("Enmienda transaccional en Comisión nº 3 a la enmienda número 41."), ["41"])
        self.assertEqual(am.expand_numbers("Enmienda transaccional 7."), [])

    def test_persons_and_budget_scope(self) -> None:
        self.assertEqual(am.persons_in("Enmiendas del Grupo Parlamentario Mixto (Sres. Sayas López y García Adanero)."), ["sayas", "garcia"])
        self.assertEqual(am.persons_in("(Sra. Cañadell Salvia y Sr. Bel Accensi)"), ["canadell", "bel"])
        self.assertEqual(am.persons_in("Enmiendas del Grupo Parlamentario Popular"), [])
        in_17 = am.budget_scope("Sección 17 (Ministerio de Transportes) null")
        self.assertTrue(in_17("ALTAS Sección: 17 MINISTERIO"))
        self.assertFalse(in_17("ALTAS Sección: 23 MINISTERIO"))
        articulado = am.budget_scope("Título I null")
        self.assertTrue(articulado("Al artículo 5 De modificación"))
        self.assertFalse(articulado("ALTAS Sección: 17 MINISTERIO"))

    def test_resolve_resto_filters_group_person_and_separate_votes(self) -> None:
        amendments = {
            "1": {"firmante": "Sergio Sayas López (Grupo Parlamentario Mixto)", "body": "Al artículo 1"},
            "2": {"firmante": "Ana Oramas González-Moro (Grupo Parlamentario Mixto)", "body": "Al artículo 2"},
            "3": {"firmante": "Sergio Sayas López (Grupo Parlamentario Mixto)", "body": "Al artículo 3"},
        }
        ev = {"kind": "enmienda", "expediente_text": "Proyecto de Ley de algo.",
              "subgroup_title": "Enmiendas presentadas por el Grupo Parlamentario Mixto (Sres. Sayas López y García Adanero).",
              "subgroup_text": "Resto de las enmiendas."}
        r = am.resolve_vote(ev, amendments, "", "", separately={"3"})
        self.assertEqual(r, {"resolution": "resto", "numbers": ["1"]})
        ev2 = {**ev, "subgroup_text": "Enmienda 7."}
        self.assertEqual(am.resolve_vote(ev2, amendments, "", "", set())["resolution"], "sin_texto")


if __name__ == "__main__":
    unittest.main()
