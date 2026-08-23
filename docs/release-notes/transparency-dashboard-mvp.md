# Transparency dashboard MVP

Fecha: `2026-08-19`

Estado: `mvp`

## Qué se entrega

La ruta `/transparency/` y el feed versionado `/transparency/data/transparency.json` reúnen el estado comprobable del proyecto sin duplicar sus fuentes canónicas.

El corte muestra:

- último refresco del estado de fuentes;
- `28` fuentes `ok`, `1` degradada y `19` no ejecutadas sobre `48` presentes;
- `27` obstrucciones abiertas, `14` fuentes afectadas y `119` ficheros públicos de evidencia;
- readiness local de `7` corpus reales validados, `3` lanes por encima de un millón y `0` lanes promovidas;
- último origen durable verificado: release `5872efaf918430c0c9e2b3b5b01fd9efe4ba03ff586da75419e28dfdb0b2e139`, `6` corpus, `5,403,506` filas y `8,595` ficheros;
- metadata drift explícito entre el origen remoto y el registry/readiness local posterior;
- tres cambios públicos reales registrados, cada uno con nota, SHA-256, rutas y evidencia.

## Contrato

- schema: `transparency_dashboard_v1`;
- tamaño actual: `14,252` bytes, bajo presupuesto de `1 MB`;
- `10` métricas, todas con `source_path` y `source_url`;
- notas y evidencias registradas verificadas por existencia y SHA-256;
- frescura según `docs/method/truth-contract.md`;
- releases sintéticas, mock, placeholder o inventadas prohibidas;
- información personal oficial de dominio público retenida.

## Límites visibles

- El snapshot remoto durable contiene seis corpus; readiness local ya registra siete.
- Cero lanes están promovidas aunque tres superen un millón de filas.
- La salud `ok` de una fuente no cierra automáticamente una obstrucción histórica o reproducible.
- El dashboard muestra estado y trazabilidad; no prueba por sí mismo corrupción, ilegalidad, intención o motivo.
- El registro de cambios empieza con las releases públicas documentadas. No reconstruye cambios históricos sin nota verificable.

## Verificación

```bash
just transparency-dashboard-export
python3 -m unittest tests.test_transparency_dashboard_snapshot
node --test tests/test_transparency_dashboard_ui_contract.js
just cloudflare-pages-build
node scripts/audit_public_routes.js --base-url http://127.0.0.1:8765
node scripts/audit_public_routes.js --base-url https://votaconlachola.org
```

Resultados locales del release candidate:

- exporter/validator: `status=ok`, `0` errores;
- tests: `7/7` pass;
- build: `1,428/1,428` páginas;
- audit live actual: `40` rutas, `44` assets críticos y `119` evidencias, `0` fallos;
- real-only: `124,540` ficheros, `0` findings;
- publication hygiene: `16,711` ficheros, `0` findings;
- inspección desktop y `390x844`: jerarquía, enlaces, snapshot, release cards y layout responsive correctos.

Evidencia:

- `docs/etl/sprints/TRANSPARENCY-DASHBOARD-20260819/evidence/transparency-validation.json`;
- `docs/etl/sprints/TRANSPARENCY-DASHBOARD-20260819/evidence/local-route-audit.json`.

## Siguiente

- incorporar diffs solo cuando dos manifests reales sean comparables;
- añadir métricas históricas de respuesta/recuperación cuando existan resoluciones reales;
- añadir scorecard comunitario cuando haya volumen suficiente para medir tiempos y retención.
