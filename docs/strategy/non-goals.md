# No Objetivos

Este documento define límites explícitos para evitar sobre-promesas y mantener trazabilidad.

## No prometemos

- No prometemos un veredicto único o “voto correcto” por partido o por electorado.
- No prometemos cobertura completa de actores, territorios o fuentes desde el primer tramo.
- No prometemos “ciencia causal” para todo indicador; solo señalaremos impacto con diseño metodológico defendible.
- No prometemos tiempo real en primera entrega: el producto funciona por snapshots reproducibles con fecha de corte.
- No prometemos cero incertidumbre; `unknown` y `no_signal` son estados válidos y necesarios.
- No prometemos neutralidad absoluta en interpretación de temas sin reglas de codebook y revisión humana cuando sea necesaria.

## No hacemos (todavía)

- No automatizamos la recomendación sin trazabilidad explícita de evidencia y sin contrato de incertidumbre.
- No ocultamos vacíos de datos mediante imputación silenciosa.
- No sustituimos fuentes oficiales por agregaciones opacas de terceros.
- No ejecutamos análisis de impacto fuera de lo metodológicamente defendible.
- No recopilamos ni persistimos preferencias sensibles en servidor por defecto.
- No vendemos un “ranking de verdad” permanente; los rankings se recalculan con supuestos y pesos configurables.

## Criterio de diseño

- Si una promesa requiere datos no disponibles, reglas de juicio no trazables o supuestos no defendibles, pasa a backlog operacional y no al producto público como hecho.
- Un ítem fuera de alcance pasa a `non-goal` si no puede cumplir el contrato mínimo de:
  - trazabilidad por fila,
  - reproducibilidad por snapshot,
  - auditoría por evidencia primaria,
  - incertidumbre explícita cuando falte señal.

Cuando un área deje de ser no objetivo, debe entrar primero como objetivo controlado con una entrega pública y verificable en `docs/etl/e2e-scrape-load-tracker.md` y roadmap operativo.
