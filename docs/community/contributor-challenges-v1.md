# Contributor challenges v1

Objetivo: convertir fuentes públicas faltantes o débiles en PRs pequeños, revisables y publicables.

Ruta estándar:

1. Abrir issue `Data Source`.
2. Ejecutar `just add-source <source_id> name="..." scope="..." url="..." format=json`.
3. Sustituir muestra por payload pequeño y representativo.
4. Implementar parser.
5. Ejecutar `just etl-contributor-gates`.
6. Abrir PR con evidencia, bloqueo o contrato de reutilización.

## Starter challenges

| ID | Challenge | Source hint | Files | Done when |
|---|---|---|---|---|
| C01 | JEC convocatorias | Junta Electoral Central | `publicdata_connectors_es/contrib/`, `etl/data/raw/samples/`, `docs/etl/sources/` | Sample test ingests at least 1 convocatoria and catalog shows source as traceable |
| C02 | JEC acuerdos | Junta Electoral Central | same | Parser extracts stable record id, title/date/url, and blocker/legal notes are explicit |
| C03 | BOCM normas | Boletín Oficial Comunidad de Madrid | same | Source lands as `source_records_only`; follow-up issue names normalization target |
| C04 | DOGC normas | Diari Oficial Generalitat Catalunya | same | Source lands with sample, parser, strict test, and reuse notes |
| C05 | BOJA normas | Boletín Oficial Junta de Andalucía | same | Source lands with title/date/department/url fields in raw payload |
| C06 | AEMET observations | AEMET OpenData | existing `aemet_opendata_series` or contrib source | Token/blocker handling documented; no fake `DONE` without real loaded rows |
| C07 | Moncloa references refresh | La Moncloa RSS/reference pages | existing Moncloa connector | Current run loads non-zero records and tracker can return live-clean |
| C08 | Infoelectoral procesos | Infoelectoral API | existing Infoelectoral connector | `infoelectoral_procesos` gets real network run or documented blocker |
| C09 | Navarra parliament refresh | Parlamento de Navarra | existing Navarra connector | Replace manual-only replay with strict-network evidence or blocker entry |
| C10 | PLACSP live refresh | PLACSP syndication | existing PLACSP connector | `placsp_sindicacion` and `placsp_autonomico` both have network rows or blocker notes |

## Priority rule

Prefer sources that make public answers more traceable:

- actor/office history,
- votes and initiatives,
- laws and appointments,
- money, contracts, subsidies,
- implementation and enforcement.

Do not open unrelated broad rewrites. One source, one PR.
