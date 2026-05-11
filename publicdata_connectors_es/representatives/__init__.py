from __future__ import annotations

from .asamblea_ceuta import AsambleaCeutaDiputadosConnector
from .asamblea_extremadura import AsambleaExtremaduraDiputadosConnector
from .asamblea_madrid import AsambleaMadridOcupacionesConnector
from .asamblea_melilla import AsambleaMelillaDiputadosConnector
from .asamblea_murcia import AsambleaMurciaDiputadosConnector
from .config import SOURCE_CONFIG, SOURCE_DEFINITIONS
from .congreso import CongresoDiputadosConnector
from .cortes_aragon import CortesAragonDiputadosConnector
from .cortes_clm import CortesClmDiputadosConnector
from .cortes_cyl import CortesCylProcuradoresConnector
from .corts_valencianes import CortsValencianesDiputatsConnector
from .europarl import EuroparlMepsConnector
from .jgpa_asturias import JuntaGeneralAsturiasDiputadosConnector
from .municipal import MunicipalConcejalesConnector
from .parlament_balears import ParlamentBalearsDiputatsConnector
from .parlament_catalunya import ParlamentCatalunyaDiputatsConnector
from .parlamento_andalucia import ParlamentoAndaluciaDiputadosConnector
from .parlamento_canarias import ParlamentoCanariasDiputadosConnector
from .parlamento_cantabria import ParlamentoCantabriaDiputadosConnector
from .parlamento_galicia import ParlamentoGaliciaDeputadosConnector
from .parlamento_larioja import ParlamentoLaRiojaDiputadosConnector
from .parlamento_navarra import ParlamentoNavarraParlamentariosForalesConnector
from .parlamento_vasco import ParlamentoVascoParlamentariosConnector
from .senado import SenadoSenadoresConnector

__all__ = [
    "SOURCE_CONFIG",
    "SOURCE_DEFINITIONS",
    "AsambleaCeutaDiputadosConnector",
    "AsambleaExtremaduraDiputadosConnector",
    "AsambleaMadridOcupacionesConnector",
    "AsambleaMelillaDiputadosConnector",
    "AsambleaMurciaDiputadosConnector",
    "CongresoDiputadosConnector",
    "CortesAragonDiputadosConnector",
    "CortesClmDiputadosConnector",
    "CortesCylProcuradoresConnector",
    "CortsValencianesDiputatsConnector",
    "EuroparlMepsConnector",
    "JuntaGeneralAsturiasDiputadosConnector",
    "MunicipalConcejalesConnector",
    "ParlamentBalearsDiputatsConnector",
    "ParlamentCatalunyaDiputatsConnector",
    "ParlamentoAndaluciaDiputadosConnector",
    "ParlamentoCanariasDiputadosConnector",
    "ParlamentoCantabriaDiputadosConnector",
    "ParlamentoGaliciaDeputadosConnector",
    "ParlamentoLaRiojaDiputadosConnector",
    "ParlamentoNavarraParlamentariosForalesConnector",
    "ParlamentoVascoParlamentariosConnector",
    "SenadoSenadoresConnector",
]
