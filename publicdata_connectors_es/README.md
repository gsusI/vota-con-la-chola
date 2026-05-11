# publicdata_connectors_es

Reusable connectors for official Spanish public-data sources.

Current extracted family:
- `publicdata_connectors_es.infoelectoral`
- `publicdata_connectors_es.government` for BOE legal and Moncloa executive feeds
- `publicdata_connectors_es.money` for PLACSP contracts and BDNS subsidies
- `publicdata_connectors_es.org` for DIR3 organisation units
- `publicdata_connectors_es.outcomes` for Eurostat, BDE, AEMET and REE/ESIOS indicator series
- `publicdata_connectors_es.parliamentary` for Congreso/Senado voting, initiatives, interventions and party-program manifests
- `publicdata_connectors_es.representatives` for national, European, regional and municipal representative rosters

Package boundary:
- connectors depend on `publicdata_core`
- source registries expose typed `SourceDefinition` entries plus legacy `SOURCE_CONFIG` mappings
- project-specific DB loading and UI stay in Vota con La Chola
- legacy Vota modules re-export these classes to keep existing CLI paths stable
