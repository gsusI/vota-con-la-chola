from __future__ import annotations

import unittest

from etl.politicos_es.connectors.senado import normalize_senado_party_name


class TestSenadoPartyNameNormalization(unittest.TestCase):
    def test_normalize_keeps_standard_siglas(self) -> None:
        self.assertEqual(normalize_senado_party_name("PSOE"), "PSOE")

    def test_normalize_expands_minor_aliases(self) -> None:
        self.assertEqual(normalize_senado_party_name("INDEP"), "Independientes")
        self.assertEqual(normalize_senado_party_name("ccpv"), "CCPV")


if __name__ == "__main__":
    unittest.main()
