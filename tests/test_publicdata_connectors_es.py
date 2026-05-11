from __future__ import annotations

import unittest

from etl.parlamentario_es.connectors import congreso_iniciativas as vota_congreso_iniciativas
from etl.parlamentario_es.connectors import congreso_intervenciones as vota_congreso_intervenciones
from etl.parlamentario_es.connectors import congreso_votaciones as vota_congreso_votaciones
from etl.parlamentario_es.connectors import programas_partidos as vota_programas
from etl.parlamentario_es.connectors import senado_iniciativas as vota_senado_iniciativas
from etl.parlamentario_es.connectors import senado_votaciones as vota_senado_votaciones
from etl.politicos_es.connectors import aemet_indicators as vota_aemet
from etl.politicos_es.connectors import bde_series as vota_bde
from etl.politicos_es.connectors import boe_legal as vota_boe
from etl.politicos_es.connectors import bdns_subsidies as vota_bdns
from etl.politicos_es.connectors import dir3_org as vota_dir3
from etl.politicos_es.connectors import eurostat_indicators as vota_eurostat
from etl.politicos_es.connectors import moncloa_exec as vota_moncloa
from etl.politicos_es.connectors import placsp_contracts as vota_placsp
from etl.politicos_es.connectors import ree_esios_indicators as vota_ree
from publicdata_connectors_es.government import boe_legal, moncloa_exec
from publicdata_connectors_es.money import bdns_subsidies, placsp_contracts
from publicdata_connectors_es.org import dir3
from publicdata_connectors_es.outcomes import aemet_indicators, bde_series, eurostat_indicators, ree_esios_indicators
from publicdata_connectors_es.parliamentary import (
    congreso_iniciativas,
    congreso_intervenciones,
    congreso_votaciones,
    programas_partidos,
    senado_iniciativas,
    senado_votaciones,
)
from publicdata_connectors_es import representatives


class TestPublicdataConnectorsEs(unittest.TestCase):
    def test_dir3_vota_wrapper_reexports_package_connector(self) -> None:
        self.assertIs(vota_dir3.Dir3UnidadesAgeConnector, dir3.Dir3UnidadesAgeConnector)
        self.assertIs(vota_dir3.parse_dir3_xlsx, dir3.parse_dir3_xlsx)
        self.assertEqual(dir3.SOURCE_CONFIG["dir3_unidades_age"]["format"], "xlsx")

    def test_outcome_vota_wrappers_reexport_package_connectors(self) -> None:
        self.assertIs(vota_aemet.AemetOpenDataSeriesConnector, aemet_indicators.AemetOpenDataSeriesConnector)
        self.assertIs(vota_aemet.parse_aemet_records, aemet_indicators.parse_aemet_records)
        self.assertIs(vota_bde.BdeSeriesApiConnector, bde_series.BdeSeriesApiConnector)
        self.assertIs(vota_bde.parse_bde_records, bde_series.parse_bde_records)
        self.assertIs(vota_eurostat.EurostatSdmxConnector, eurostat_indicators.EurostatSdmxConnector)
        self.assertIs(vota_eurostat.parse_eurostat_records, eurostat_indicators.parse_eurostat_records)
        self.assertIs(vota_ree.ReeEsiosIndicatorsConnector, ree_esios_indicators.ReeEsiosIndicatorsConnector)
        self.assertIs(vota_ree.parse_ree_records, ree_esios_indicators.parse_ree_records)

    def test_government_vota_wrappers_reexport_package_connectors(self) -> None:
        self.assertIs(vota_boe.BoeApiLegalConnector, boe_legal.BoeApiLegalConnector)
        self.assertIs(vota_boe.parse_boe_rss_items, boe_legal.parse_boe_rss_items)
        self.assertIs(vota_moncloa.MoncloaReferenciasConnector, moncloa_exec.MoncloaReferenciasConnector)
        self.assertIs(vota_moncloa.MoncloaRssReferenciasConnector, moncloa_exec.MoncloaRssReferenciasConnector)
        self.assertEqual(boe_legal.SOURCE_CONFIG["boe_api_legal"]["format"], "xml")
        self.assertEqual(moncloa_exec.SOURCE_CONFIG["moncloa_referencias"]["format"], "html")

    def test_money_vota_wrappers_reexport_package_connectors(self) -> None:
        self.assertIs(vota_bdns.BdnsApiSubvencionesConnector, bdns_subsidies.BdnsApiSubvencionesConnector)
        self.assertIs(vota_bdns.BdnsAutonomicoConnector, bdns_subsidies.BdnsAutonomicoConnector)
        self.assertIs(vota_bdns.parse_bdns_records, bdns_subsidies.parse_bdns_records)
        self.assertIs(vota_placsp.PlacspSindicacionConnector, placsp_contracts.PlacspSindicacionConnector)
        self.assertIs(vota_placsp.PlacspAutonomicoConnector, placsp_contracts.PlacspAutonomicoConnector)
        self.assertIs(vota_placsp.parse_placsp_atom_entries, placsp_contracts.parse_placsp_atom_entries)
        self.assertEqual(bdns_subsidies.SOURCE_CONFIG["bdns_api_subvenciones"]["format"], "json")
        self.assertEqual(placsp_contracts.SOURCE_CONFIG["placsp_sindicacion"]["format"], "xml")

    def test_parliamentary_vota_wrappers_reexport_package_connectors(self) -> None:
        self.assertIs(vota_congreso_votaciones.CongresoVotacionesConnector, congreso_votaciones.CongresoVotacionesConnector)
        self.assertIs(
            vota_congreso_iniciativas.CongresoIniciativasConnector,
            congreso_iniciativas.CongresoIniciativasConnector,
        )
        self.assertIs(
            vota_congreso_intervenciones.CongresoIntervencionesConnector,
            congreso_intervenciones.CongresoIntervencionesConnector,
        )
        self.assertIs(vota_senado_votaciones.SenadoVotacionesConnector, senado_votaciones.SenadoVotacionesConnector)
        self.assertIs(
            vota_senado_iniciativas.SenadoIniciativasConnector,
            senado_iniciativas.SenadoIniciativasConnector,
        )
        self.assertIs(vota_programas.ProgramasPartidosConnector, programas_partidos.ProgramasPartidosConnector)
        self.assertEqual(congreso_votaciones.SOURCE_CONFIG["congreso_votaciones"]["format"], "html")
        self.assertEqual(programas_partidos.SOURCE_CONFIG["programas_partidos"]["format"], "csv")

    def test_representative_source_config_is_packaged(self) -> None:
        self.assertEqual(representatives.SOURCE_CONFIG["congreso_diputados"]["format"], "json")
        self.assertEqual(representatives.SOURCE_CONFIG["senado_senadores"]["format"], "xml")
        self.assertEqual(representatives.SOURCE_CONFIG["municipal_concejales"]["format"], "xlsx")


if __name__ == "__main__":
    unittest.main()
