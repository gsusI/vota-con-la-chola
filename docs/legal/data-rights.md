# Política de derechos de código, datos y fuentes

Este documento separa explícitamente el régimen legal del **código del proyecto**
del régimen legal de los **datos** y define un mapa operativo por `source_id`.

## 1) Ámbito legal por tipo de artefacto

- **Código y configuración del repositorio**
  - Cobertura: scripts ETL, UI, consultas SQL, documentación técnica y automatizaciones.
  - Régimen: `LICENSE` del repositorio (MIT).
  - Permite uso, copia, modificación y redistribución del código fuente con atribución.

- **Snapshots y artefactos publicados**
  - Cobertura: `etl/data/published`, `etl/data/published/snapshots/<fecha>/` y archivos
    derivados en el empaquetado (incluye parquet/JSON/checksums).
  - Régimen: **mixto** por fuente, no uniforme.
  - El metadato de licencia a nivel HF se expresa como `license: other`, y el detalle por
    fuente está en `sources/<source_id>.json` de cada snapshot.

- **Datos compilados/derivados en el proyecto**
  - Cobertura: tablas normalizadas, índices, etiquetas, agregaciones y material derivado.
  - Régimen: permitido según licencia/aviso de cada fuente con obligación de atribución y de indicar transformaciones cuando proceda.

- **Material fuente original**
  - Cobertura: contenidos que no pasan a formar parte de una capa derivada o que reproducen estructura original.
  - Régimen: conserva condiciones del portal/organismo de origen.
  - Nunca se publica en condiciones más permisivas que lo declarado por la fuente.

## 2) Matriz de derechos por `source_id` (v2)

Estado de revisión:

- `verificado`: evidencia documental disponible y aplicable.
- `parcial`: evidencia inicial fuerte pero con matices pendientes de cierre.
- `pendiente`: sin evidencia documental consolidada en snapshot.
- `no verificado`: falta revisión de licencia para reutilización comercial.

| source_id | Estado | Base legal / licencia | terms_url | Observación breve |
|---|---|---|---|---|
| `congreso_diputados` | verificado | Aviso legal del Congreso (reutilización autorizada con condiciones) | https://www.congreso.es/es/avisoLegal | Citar origen y condiciones de uso |
| `congreso_iniciativas` | verificado | Aviso legal del Congreso (reutilización autorizada con condiciones) | https://www.congreso.es/es/avisoLegal | Igual que por diputados |
| `congreso_intervenciones` | verificado | Aviso legal del Congreso (reutilización autorizada con condiciones) | https://www.congreso.es/es/avisoLegal | Igual que por diputados |
| `congreso_votaciones` | verificado | Aviso legal del Congreso (reutilización autorizada con condiciones) | https://www.congreso.es/es/avisoLegal | Igual que por diputados |
| `senado_iniciativas` | verificado | CC BY 4.0 (datos abiertos del Senado) | https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html | Mantener atribución CC BY |
| `senado_senadores` | verificado | CC BY 4.0 (datos abiertos del Senado) | https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html | Mantener atribución CC BY |
| `senado_votaciones` | verificado | CC BY 4.0 (datos abiertos del Senado) | https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html | Mantener atribución CC BY |
| `boe_api_legal` | verificado | Aviso legal BOE (autorizada con condiciones y excepciones de terceros) | https://www.boe.es | Excluir/segregar materiales restringidos |
| `moncloa_referencias` | verificado | Aviso legal La Moncloa (reproducción, modificación y distribución autorizadas) | https://www.lamoncloa.gob.es/Paginas/avisolegal.aspx | Atribución explícita |
| `moncloa_rss_referencias` | verificado | Aviso legal La Moncloa (reproducción, modificación y distribución autorizadas) | https://www.lamoncloa.gob.es/Paginas/avisolegal.aspx | Atribución explícita |
| `bdns_api_subvenciones` | verificado | Aviso legal tipo AGE/Hacienda (reutilización abierta con condiciones) | https://datos.gob.es/es/aviso-legal | Atención a minimización de datos personales |
| `bdns_autonomico` | verificado | Aviso legal tipo AGE/Hacienda (reutilización abierta con condiciones) | https://datos.gob.es/es/aviso-legal | Atención a minimización de datos personales |
| `placsp_sindicacion` | verificado | Reproducción autorizada con cita de origen; vinculada a datos abiertos de Hacienda | https://datos.gob.es/es/aviso-legal | Mezcla con datos de Hacienda, aplicar ambas condiciones |
| `placsp_autonomico` | verificado | Reproducción autorizada con cita de origen; vinculada a datos abiertos de Hacienda | https://datos.gob.es/es/aviso-legal | Mezcla con datos de Hacienda, aplicar ambas condiciones |
| `asamblea_madrid_ocupaciones` | verificado | CC BY 3.0 ES (salvo indicación en contrario) | https://www.asambleamadrid.es/datos-abiertos | Atribución explícita |
| `aemet_opendata_series` | verificado | CC BY 4.0 (catalogo datos.gob.es/AEMET) | https://datos.gob.es/es/aviso-legal | Series agregadas; citar origen |
| `bde_series_api` | verificado | Términos de uso estadísticos del BDE | https://www.bde.es | Mantener integridad y atribución |
| `eurostat_sdmx` | parcial | Política de reutilización de Eurostat | https://ec.europa.eu/eurostat/about/policies/copyright/ | Revisar excepciones de terceros |
| `infoelectoral_descargas` | parcial | Perfil de reutilización AGE por inferencia de catálogo | https://datos.gob.es/es/aviso-legal | Confirmación pendiente en revisión legal posterior |
| `infoelectoral_procesos` | parcial | Perfil de reutilización AGE por inferencia de catálogo | https://datos.gob.es/es/aviso-legal | Confirmación pendiente en revisión legal posterior |
| `europarl_meps` | no verificado | Falta revisión de licencia específica del recurso XML | https://www.europarl.europa.eu/legal-notice/es/ | Revisión legal completa requerida |

Fuentes sin ficha en `LEGAL_PROFILE_BY_SOURCE` se tratan como:
- `pendiente` por defecto
- requieren revisión manual antes de cualquier reutilización comercial sensible.

## 3) Reglas de cumplimiento aplicables

1. Mantener explícita la atribución de origen en derivados y visualizaciones.
2. Documentar transformaciones (normalización, agregaciones, criterios de deduplicación, filtros).
3. Mantener `published/*` (raw del snapshot) para conservar una capa trazable cuando la fuente lo exija.
4. Exponer metadatos de cumplimiento:
   - tabla `sources/<source_id>.json` por snapshot
   - `ingestion_runs`, `checksums.sha256` y metadatos de calidad asociados.
5. Aplicar minimización y no reidentificación sobre cualquier dato personal.

## 4) Señales de estado y revisión humana

- Marcar en cada `sources/<source_id>.json` el estado de revisión vigente.
- Los estados `parcial`, `pendiente` o `no verificado` requieren
  **revisión legal humana** antes de distribución comercial o usos de alto riesgo.
- Cualquier fuente con dudas de terceros o datos personales sensibles se clasifica con cautela y puede ser excluida de `parquet` público si aplica.

## 5) Cómo mantener esta matriz

Cuando cambie el contrato de una fuente:

1. Actualizar `LEGAL_PROFILE_BY_SOURCE` en `scripts/publicar_hf_snapshot.py`.
2. Actualizar esta matriz con la nueva base legal y evidencia.
3. Regenerar snapshot si aplica y dejar trazabilidad en `docs/etl/sprints/**/evidence`.
