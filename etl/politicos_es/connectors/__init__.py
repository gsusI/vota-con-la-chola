from __future__ import annotations

from .aemet_indicators import AemetOpenDataSeriesConnector
from .asamblea_madrid import AsambleaMadridOcupacionesConnector
from .asamblea_extremadura import AsambleaExtremaduraDiputadosConnector
from .asamblea_ceuta import AsambleaCeutaDiputadosConnector
from .asamblea_melilla import AsambleaMelillaDiputadosConnector
from .asamblea_murcia import AsambleaMurciaDiputadosConnector
from .bdns_subsidies import BdnsApiSubvencionesConnector, BdnsAutonomicoConnector
from .bde_series import BdeSeriesApiConnector
from .boe_legal import BoeApiLegalConnector
from .congreso import CongresoDiputadosConnector
from .cortes_aragon import CortesAragonDiputadosConnector
from .cortes_clm import CortesClmDiputadosConnector
from .cortes_cyl import CortesCylProcuradoresConnector
from .corts_valencianes import CortsValencianesDiputatsConnector
from .eurostat_indicators import EurostatSdmxConnector
from .europarl import EuroparlMepsConnector
from .jgpa_asturias import JuntaGeneralAsturiasDiputadosConnector
from .municipal import MunicipalConcejalesConnector
from .moncloa_exec import MoncloaReferenciasConnector, MoncloaRssReferenciasConnector
from .parlament_balears import ParlamentBalearsDiputatsConnector
from .parlamento_canarias import ParlamentoCanariasDiputadosConnector
from .parlamento_cantabria import ParlamentoCantabriaDiputadosConnector
from .parlamento_galicia import ParlamentoGaliciaDeputadosConnector
from .parlamento_larioja import ParlamentoLaRiojaDiputadosConnector
from .parlamento_navarra import ParlamentoNavarraParlamentariosForalesConnector
from .parlament_catalunya import ParlamentCatalunyaDiputatsConnector
from .parlamento_andalucia import ParlamentoAndaluciaDiputadosConnector
from .parlamento_vasco import ParlamentoVascoParlamentariosConnector
from .placsp_contracts import PlacspAutonomicoConnector, PlacspSindicacionConnector
from .senado import SenadoSenadoresConnector

__all__ = [
    "AsambleaCeutaDiputadosConnector",
    "AsambleaMelillaDiputadosConnector",
    "AsambleaExtremaduraDiputadosConnector",
    "AsambleaMadridOcupacionesConnector",
    "AsambleaMurciaDiputadosConnector",
    "AemetOpenDataSeriesConnector",
    "BdnsApiSubvencionesConnector",
    "BdnsAutonomicoConnector",
    "BdeSeriesApiConnector",
    "BoeApiLegalConnector",
    "CongresoDiputadosConnector",
    "CortesAragonDiputadosConnector",
    "CortesClmDiputadosConnector",
    "CortesCylProcuradoresConnector",
    "CortsValencianesDiputatsConnector",
    "EurostatSdmxConnector",
    "EuroparlMepsConnector",
    "JuntaGeneralAsturiasDiputadosConnector",
    "MunicipalConcejalesConnector",
    "MoncloaReferenciasConnector",
    "MoncloaRssReferenciasConnector",
    "ParlamentBalearsDiputatsConnector",
    "ParlamentoCanariasDiputadosConnector",
    "ParlamentoCantabriaDiputadosConnector",
    "ParlamentoGaliciaDeputadosConnector",
    "ParlamentoLaRiojaDiputadosConnector",
    "ParlamentoNavarraParlamentariosForalesConnector",
    "ParlamentCatalunyaDiputatsConnector",
    "ParlamentoAndaluciaDiputadosConnector",
    "ParlamentoVascoParlamentariosConnector",
    "PlacspAutonomicoConnector",
    "PlacspSindicacionConnector",
    "SenadoSenadoresConnector",
]
