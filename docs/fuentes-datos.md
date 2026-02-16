# Fuentes de datos (KISS)

Este doc define:
- qué cuenta como “acción” (evento con efectos y trazabilidad),
- cómo clasificar fiabilidad,
- y qué familias de fuentes soporta el roadmap.

El inventario operativo y el estado viven en:
- `docs/etl/e2e-scrape-load-tracker.md` (conectores `DONE/PARTIAL/TODO`)
- `/explorer-sources` (dashboard local)

## 1) Qué es “acción política” (operativo)

Una acción útil en datos es un **evento** con:
- `actor` (persona/órgano/grupo) y `scope` (municipal/autonómico/nacional/UE)
- `instrumento` (voto, norma, presupuesto, contrato, subvención, nombramiento…)
- `objeto` (expediente/BOE-A-…/número de contrato/convocatoria…)
- `fecha_evento` y `fecha_publicacion` (si aplica)
- `resultado` (aprobado, importe, adjudicatario…)
- `evidencia_primaria` (URL/ID oficial) + `content_hash` + `fetched_at`

Regla: cuando exista un registro “con efectos”, ese es el **canónico** (boletín/registro). Comunicación (nota/RSS) sirve para detección, no para “efecto”.

## 2) Fiabilidad de fuente (0-5)

- `5/5` primaria con efectos: BOE, BDNS/SNPSAP, PLACSP, EUR-Lex…
- `4/5` oficial estructurado: OpenData (Congreso/Senado), APIs oficiales.
- `3/5` oficial comunicacional: notas, referencias, agendas, RSS (hecho comunicacional).
- `2/5` reutilizador fiable: deriva de 4-5 (verificar contra original para claims fuertes).
- `1/5` señal: prensa/redes (alerta, no evidencia).
- `0/5` sin trazabilidad.

## 3) Taxonomía (rol en el modelo)

- **Acción institucional primaria**: parlamento (votos/iniciativas), normativa (boletines), dinero público (contratos/subvenciones), presupuesto (aprobado/ejecución), ejecutivo (acuerdos/nombramientos).
- **Outcomes**: indicadores oficiales (INE/Eurostat/OCDE/BDE) y registros sectoriales (criminalidad, siniestralidad, calidad del aire…).
- **Confusores**: macro, demografía, shocks, clima, energía.
- **Fiscalización/control**: AIReF, Tribunal de Cuentas, auditorías.
- **Catálogos/metafuentes**: datos.gob.es, data.europa.eu (descubrir datasets; no confundir con “los datos”).

## 4) Fuentes ancla (para orientar el MVP)

Acción (P0/P1 típicos):
- Congreso/Senado (votos + iniciativas).
- BOE (normativa con efectos).
- BDNS/SNPSAP (subvenciones con efectos).
- PLACSP/OpenPLACSP (contratación con efectos).
- La Moncloa (referencias/RSS) y Transparencia (agendas/declaraciones): señal oficial, validar contra fuentes con efectos cuando proceda.

Outcomes/confusores (para capa de impacto, cuando toque):
- INE (series + metadatos).
- Eurostat / OCDE (SDMX).
- Banco de España (series).
- AEMET / ESIOS / CNMC (confusores y alta frecuencia cuando aplique).

Inventario ideal (north star, no operativo): `docs/ideal_sources_say_do.json`.

## 5) Regla de “doble entrada” (comunicación vs efecto)

Cuando haya correspondencia:
- Consejo de Ministros (referencia) -> validar contra BOE (publicación).
- Nota de adjudicación -> validar contra PLACSP (expediente).
- Anuncio de ayuda -> validar contra BDNS (registro).

Esto permite subir/bajar confianza de un evento sin inventar causalidad.

## 6) Escalado subnacional (CCAA/municipal) sin listar miles de URLs

Estrategia reproducible:
- Descubrimiento por catálogos (datos.gob.es / data.europa.eu) + patrones por administración.
- Adaptadores por familia (boletines, parlamentos, transparencia, presupuesto, contratación, subvenciones).
- Medir cobertura con contadores simples por dominio antes de “integrar todo”.
