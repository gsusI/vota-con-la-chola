from __future__ import annotations

from .connectors import (
    AsambleaCeutaDiputadosConnector,
    AsambleaExtremaduraDiputadosConnector,
    AsambleaMelillaDiputadosConnector,
    AsambleaMadridOcupacionesConnector,
    AsambleaMurciaDiputadosConnector,
    CongresoDiputadosConnector,
    CortesAragonDiputadosConnector,
    CortesClmDiputadosConnector,
    CortesCylProcuradoresConnector,
    CortsValencianesDiputatsConnector,
    EuroparlMepsConnector,
    JuntaGeneralAsturiasDiputadosConnector,
    MunicipalConcejalesConnector,
    ParlamentBalearsDiputatsConnector,
    ParlamentoCanariasDiputadosConnector,
    ParlamentoCantabriaDiputadosConnector,
    ParlamentoGaliciaDeputadosConnector,
    ParlamentoLaRiojaDiputadosConnector,
    ParlamentoNavarraParlamentariosForalesConnector,
    ParlamentCatalunyaDiputatsConnector,
    ParlamentoAndaluciaDiputadosConnector,
    ParlamentoVascoParlamentariosConnector,
    SenadoSenadoresConnector,
)
from .connectors.base import BaseConnector


def get_connectors() -> dict[str, BaseConnector]:
    connectors: list[BaseConnector] = [
        CongresoDiputadosConnector(),
        SenadoSenadoresConnector(),
        EuroparlMepsConnector(),
        MunicipalConcejalesConnector(),
        AsambleaMadridOcupacionesConnector(),
        AsambleaCeutaDiputadosConnector(),
        AsambleaMelillaDiputadosConnector(),
        AsambleaExtremaduraDiputadosConnector(),
        AsambleaMurciaDiputadosConnector(),
        JuntaGeneralAsturiasDiputadosConnector(),
        CortesAragonDiputadosConnector(),
        ParlamentBalearsDiputatsConnector(),
        ParlamentoCanariasDiputadosConnector(),
        ParlamentoCantabriaDiputadosConnector(),
        ParlamentoGaliciaDeputadosConnector(),
        ParlamentoLaRiojaDiputadosConnector(),
        ParlamentCatalunyaDiputatsConnector(),
        CortsValencianesDiputatsConnector(),
        CortesClmDiputadosConnector(),
        CortesCylProcuradoresConnector(),
        ParlamentoAndaluciaDiputadosConnector(),
        ParlamentoNavarraParlamentariosForalesConnector(),
        ParlamentoVascoParlamentariosConnector(),
    ]
    return {c.source_id: c for c in connectors}
