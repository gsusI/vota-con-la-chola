---
language:
- es
license: other
task_categories:
- tabular-classification
pretty_name: Vota Con La Chola snapshots
---

# Vota Con La Chola - Snapshots ETL

Dataset de snapshots públicos del proyecto `JesusIC/vota-con-la-chola-data`.

Repositorio fuente: [https://github.com/gsusI/vota-con-la-chola](https://github.com/gsusI/vota-con-la-chola)

Contenido por snapshot (capas raw + processed):
- `snapshots/2026-02-12/published/*`: capa raw reproducible (artefactos canónicos JSON/JSON.GZ).
- `snapshots/2026-02-12/parquet/<tabla>/part-*.parquet`: tablas navegables en Data Studio.
- `snapshots/2026-02-12/sources/<source_id>.json`: procedencia legal por fuente (licencia/aviso, obligaciones, terms_url, estado de verificación).
- Tablas excluidas por privacidad (default público): `lost_and_found`, `raw_fetches`, `run_fetches`, `source_records`. Usa `--allow-sensitive-parquet` solo en repos privados.
- `ingestion_runs.csv`: historial de corridas de ingesta.
- `source_records_by_source.csv`: conteos por fuente para la fecha del snapshot.
- `explorer_schema.json`: contrato de esquema (tablas/PK/FK) para exploración en navegador.
- `manifest.json` y `checksums.sha256`: trazabilidad e integridad.

Licencia del repo Hugging Face:
- `license: other` porque el snapshot mezcla múltiples licencias/avisos por fuente.
- La licencia/condiciones aplicables están detalladas por `source_id` en `sources/*.json`.
- `published/votaciones-kpis-es-2026-02-12.json`: reporte de calidad (votos/iniciativas) usado para gates del snapshot.

Resumen legal por fuente (snapshot actual):
| source_id | registros | verificación | base legal/licencia | terms_url |
|---|---:|---|---|---|
| `asamblea_ceuta_diputados` | 25 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.ceuta.es/gobiernodeceuta/index.php/el-gobierno/la-asamblea) |
| `asamblea_extremadura_diputados` | 65 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.asambleaex.es/dipslegis) |
| `asamblea_madrid_ocupaciones` | 9188 | verificado | CC BY 3.0 ES (Asamblea de Madrid, salvo indicación en contrario) | [link](https://www.asambleamadrid.es/datos-abiertos) |
| `asamblea_melilla_diputados` | 26 | pendiente | Sin verificación documental específica en este snapshot | [link](https://sede.melilla.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_MIEMBROS) |
| `asamblea_murcia_diputados` | 54 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.asambleamurcia.es/diputados) |
| `congreso_diputados` | 352 | verificado | Aviso legal del Congreso (reutilización autorizada con condiciones) | [link](https://www.congreso.es/es/avisoLegal) |
| `congreso_iniciativas` | 429 | verificado | Aviso legal del Congreso (reutilización autorizada con condiciones) | [link](https://www.congreso.es/es/avisoLegal) |
| `congreso_intervenciones` | 614 | verificado | Aviso legal del Congreso (reutilización autorizada con condiciones) | [link](https://www.congreso.es/es/avisoLegal) |
| `congreso_votaciones` | 2823 | verificado | Aviso legal del Congreso (reutilización autorizada con condiciones) | [link](https://www.congreso.es/es/avisoLegal) |
| `cortes_aragon_diputados` | 75 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.cortesaragon.es/Quienes-somos.2250.0.html?no_cache=1&tx_t3comunicacion_pi3%5Bnumleg%5D=11&tx_t3comunicacion_pi3%5Btipinf%5D=3&tx_t3comunicacion_pi3%5Buidcom%5D=-2) |
| `cortes_clm_diputados` | 33 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.cortesclm.es/web2/paginas/resul_diputados.php?legislatura=11) |
| `cortes_cyl_procuradores` | 81 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.ccyl.es/Organizacion/PlenoAlfabetico) |
| `europarl_meps` | 62 | no verificado | No verificado: falta evidencia documental específica del recurso XML de MEPs | [link](https://www.europarl.europa.eu/legal-notice/es/) |
| `infoelectoral_procesos` | 257 | parcial | Indicio fuerte de adopción de aviso legal tipo AGE (datos.gob.es/aviso-legal) | [link](https://datos.gob.es/es/aviso-legal) |
| `jgpa_diputados` | 45 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.jgpa.es/diputados-y-diputadas) |
| `municipal_concejales` | 66101 | verificado | Portal concejales.redsara: condiciones alineadas con aviso legal tipo AGE | [link](https://concejales.redsara.es) |
| `parl_initiative_docs` | 235 | pendiente | Sin verificación documental específica en este snapshot | `manifest://parl_initiative_docs` |
| `parlament_balears_diputats` | 59 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.parlamentib.es/Representants/Diputats.aspx?criteria=0) |
| `parlament_catalunya_diputats` | 135 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.parlament.cat/web/composicio/ple-parlament/composicio-actual/index.html) |
| `parlamento_andalucia_diputados` | 109 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/composicionyfuncionamiento/diputadosysenadores.do) |
| `parlamento_canarias_diputados` | 79 | pendiente | Sin verificación documental específica en este snapshot | [link](https://parcan.es/api/diputados/por_legislatura/11/?format=json) |
| `parlamento_cantabria_diputados` | 35 | pendiente | Sin verificación documental específica en este snapshot | [link](https://parlamento-cantabria.es/informacion-general/composicion/11l-pleno-del-parlamento-de-cantabria) |
| `parlamento_larioja_diputados` | 33 | pendiente | Sin verificación documental específica en este snapshot | [link](https://adminweb.parlamento-larioja.org/composicion-y-organos/diputados) |
| `parlamento_vasco_parlamentarios` | 75 | pendiente | Sin verificación documental específica en este snapshot | [link](https://www.legebiltzarra.eus/comparla/c_comparla_alf_ACT.html) |
| `senado_iniciativas` | 3607 | verificado | CC BY 4.0 (datos abiertos del Senado) | [link](https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html) |
| `senado_senadores` | 1793 | verificado | CC BY 4.0 (datos abiertos del Senado) | [link](https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html) |
| `senado_votaciones` | 5534 | verificado | CC BY 4.0 (datos abiertos del Senado) | [link](https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/index.html) |

Cautelas de cumplimiento:
- Este dataset no implica respaldo institucional de las fuentes.
- Cuando una fuente exige integridad/no alteración para mirror, mantener `published/*` como capa raw y declarar transformaciones en derivados.
- Si hay datos personales, aplicar minimización, evitar reidentificación y revisar compatibilidad de finalidad (GDPR).
- Fuentes con estado `parcial`, `pendiente` o `no verificado` requieren revisión legal adicional antes de reutilización comercial sensible.

Ruta del último snapshot publicado en este commit:
- `snapshots/2026-02-12` (snapshot_date=2026-02-12)

Actualización:
- `just etl-publish-hf-dry-run` para validar empaquetado.
- `just etl-publish-hf` para publicar actualización.

Resumen de calidad del snapshot:
- Vote gate: PASS
- Eventos analizados: 8357
