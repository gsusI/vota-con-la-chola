# Plantilla de intervención (para impacto)

Version: `v1`

Objetivo: definir “intervenciones” (tratamientos) de forma **reproducible**, para que el sistema pueda:
- agrupar `policy_events` en paquetes tratables (`interventions`, `intervention_events`),
- enlazar outcomes (`indicator_series`),
- y registrar estimaciones (`causal_estimates`) con diagnósticos.

Regla: una intervención es una **definición** (qué cuenta y cuándo empieza), no un relato.

## Plantilla (YAML)

```yaml
canonical_key: vivienda_control_alquileres_ccaa_x_v1
label: "Control de alquileres (CCAA X)"
domain_canonical_key: vivienda_urbanismo

scope: autonomico   # municipal | autonomico | nacional | europeo
admin_level: ccaa   # municipio | ccaa | estado | ue
territory_code: "XX"  # código estable del territorio (según tu esquema/tabla territories)

start_date: "YYYY-MM-DD"
end_date: null

policy_event_ids:
  - "boe:BOE-A-...."
  - "bocm:...."
  - "placsp:exp:...."

outcome_indicator_series:
  - canonical_key: vivienda_precio_alquiler
    expected_direction: +1   # solo hipótesis operativa; no prueba
  - canonical_key: vivienda_oferta_visados
    expected_direction: -1

confounders_indicator_series:
  - canonical_key: tipos_interes
  - canonical_key: paro
  - canonical_key: inflacion

design:
  method: did  # did | event_study | synthetic_control | rd | iv | descriptive
  unit: "municipio"  # o "ccaa", "provincia", "pais", etc.
  treated_definition: "..."  # regla reproducible para treated vs control
  window:
    pre_period: 24    # meses (o unidades)
    post_period: 24

diagnostics_required:
  - "pre_trends"
  - "placebo"
  - "robustness_window"

evidence_links:
  - url: "https://..."
    note: "BOE consolidado / texto íntegro"
  - url: "https://..."
    note: "documento técnico / memoria"

notes: "Supuestos clave y límites (2-5 líneas)."
```

## Reglas (KISS)

- `canonical_key` estable y único (si cambia el tratamiento, nueva key).
- `policy_event_ids` debe ser una lista cerrada y auditable (si falta un evento clave, no se “asume”).
- `expected_direction` es una hipótesis (para chequear incoherencias), no una conclusión.
- `design.method=descriptive` es válido cuando no hay identificación defendible (se etiqueta como tal).

## Mapeo al SQLite (cuando se implemente)

- `interventions.canonical_key/label/description/domain_id/start_date/end_date/admin_level_id/territory_id`
- `intervention_events(intervention_id, policy_event_id)`
- `causal_estimates(…, method, estimate_json, diagnostics_json, credibility)`

