# Dinero nacional: reconciliación inicial y defecto de selección

Fecha: 2026-09-07. Estado: ejecución en curso; no North Star cumplida.

Ahora: `coverage.json` reconcilia 330.577 versiones de 121.555 identificadores de expediente y 262.558 resultados de todas las versiones. Seis archivos mensuales de 2025 adquiridos; 22 trabajos históricos anteriores siguen pendientes. El catálogo oficial actualizado (`placsp-catalog.json`) selecciona 23 contenedores anuales/mensuales desde 2012 hasta septiembre de 2026. Esto no mide número de contratos nacionales ni completitud del contenido.

La selección congelada contiene 141.747 hechos clasificados como `contract_award`. Balance publicado: 47.397 seleccionados + 11 sin fecha + 12.898 sin identidad/importe EUR + 80.819 descartados por estado/borrado + 622 discrepancias semánticas = 141.747. El balance es exacto; la política de estados era incompleta.

El publicador aceptaba exclusivamente `TenderResult/ResultCode=8`. La [documentación oficial de PLACSP, contratos menores, sección del mensaje ContractAwardNotice](https://contrataciondelestado.es/b2b/DGPE_PLACE_PublicacionB2B_ContratosMenoresv2.5.pdf) identifica 8 como adjudicación y 9 como formalización. La [especificación de agregación](https://contrataciondelestado.es/wps/wcm/connect/a7a7426d-dead-48b1-8be5-fb653c0176b6/DGPE_PLACSP_EspecificacionTecnicaMecanismoAgregacion_cambios2.3.pdf?MOD=AJPERES) muestra adjudicatarios e importes bajo código 9. No confundir este código con ContractFolderStatusCode, cuyo vocabulario es distinto.

La última versión unívoca por expediente tiene 48.027 resultados código 8 y 80.820 código 9; 80.817 de estos últimos tienen campos básicos. No son todavía filas publicables: faltan gates de importe, identidad, borrado, paridad y reproducción XML. Las formalizaciones deben retener su estado, sin presentarse como pagos ni sumarse de nuevo a versiones anteriores.

Cambio en preparación: `scripts/build_placsp_launch.py` admite 8/9, retiene `result_code` y `result_stage` y publica desglose por estado; conserva las exclusiones por fallo/borrado. Tres pruebas de política pasan. Reconstrucción completa desde corpus congelado y archivos XML originales en curso. La release pública anterior permanece inmutable.

Siguiente: finalizar reconstrucción, clasificar las 622 discrepancias, evaluar importación/publicación escalonada bajo cuota gratuita y ampliar adquisición histórica. No reimportar toda la base remota al llegar a un límite diario.

Reproducir cobertura:

```sh
python3 scripts/report_spending_coverage.py --db etl/data/staging/placsp-contracts-real-s1-20260811.db --catalog docs/etl/sprints/DINERO-NACIONAL-20260907/evidence/placsp-catalog.json --out docs/etl/sprints/DINERO-NACIONAL-20260907/evidence/coverage.json
python3 -m unittest tests.test_spending_result_stages -v
```

El primer intento de consulta del catálogo falló por resolución DNS del entorno restringido. La ejecución con acceso de red autorizado funcionó con TLS verificado; no se atribuye ese fallo local a Hacienda ni se abre incidente de obstrucción.

## Ampliación actual y corrección de identificadores

La captura oficial de septiembre de 2026 se descargó en un intento con TLS verificado, en base separada `placsp-national-20260907.db`: 17 miembros procesados, 8.235 versiones y 7.625 identificadores de expediente, 82 tombstones. Todos los gates analíticos del reporte pasan; `PRAGMA foreign_key_check` devuelve cero incidencias. Estado explícito: `local_normalized_not_published`; mes abierto, no cobertura mensual completa.

La auditoría de discrepancias encontró 2.036 resultados exitosos (códigos 8/9) que diferían exclusivamente en `counterparty_identifier`. El exportador de dinero aplica `strip().upper()`; el comparador de lanzamiento exigía igualdad literal. Se alinea la comparación con esa transformación y se conserva el identificador literal en la fila de salida y el XML. La selección corregida alcanza 128.837 candidatos; recuperación y replay de XML todavía en curso. Cuatro pruebas de política pasan.

El generador de backend incorpora `--plan-only` y `--public-root=` para medir otra release sin cambiar la configuración activa ni producir un import completo. El límite de importación diaria sigue bloqueando la vía normal; el modo de planificación no autoriza ejecutar SQL remoto ni cambia la cuota.

## Candidato corregido verificado

Reconstrucción final completada: 128.837 resultados (48.019 adjudicados y 80.818 formalizados), 86.933 capturas XML reproducidas, seis ZIP y 667 miembros originales rehasheados. Las discrepancias semánticas se reducen a cero tras respetar la normalización de identificadores del exportador. Balance: 128.837 + 11 sin fecha + 12.898 sin identidad/importe EUR + 1 resultado no elegible = 141.747 hechos congelados.

Paridad con la release anterior: se conservan sus 47.397 claves, importes, fechas originales, identificadores de proveedor, expediente/lote y hashes de evidencia; 81.440 resultados adicionales y cero claves duplicadas. GALASA pasa a 11 resultados y 572.335.676 céntimos en el candidato; no se afirma cobertura exhaustiva de la empresa.

Plan de capacidad final: 389.038.080 bytes en SQLite; 190.521 escrituras estimadas, por encima del presupuesto diario. Cabe en el presupuesto local de 450 MB por base pero no habilita una carga remota única. `--plan-only` preserva la configuración activa. `scripts/plan_spending_import_batches.mjs` genera lotes ordenados con checksum y presupuesto conservador; el verificador independiente reconstruye todas las tablas y compara hashes fila a fila. No hay ejecución remota ni reintento automático de un lote incierto.

Publicación sigue PENDIENTE. Próximo paso: sellar el candidato, preparar despliegue aislado y ejecutar lotes tras comprobar cuota real compartida; verificar API/UI/CSV y evidencia antes de promover. La cohorte septiembre de 2026 permanece separada, normalizada y sin publicar. DN-01/DN-02 avanzan; no hay declaración de North Star conseguida.

## Reanudación de cargas y acceso remoto

Los lotes v2 toleran repetición del mismo candidato: DDL condicional, inserciones que conservan claves existentes y append condicionado a longitud Unicode ya escrita. Una tabla de control con CHECK impide mezclar versiones candidatas. La verificación ejecutó dos veces cada uno de los 19 lotes y comparó todas las filas de las cuatro tablas con la base fuente: 128.837 adjudicaciones, 40.356 entidades, 5.286 términos y metadatos idénticos. Probó además el rechazo de otra versión. No reutilizar los lotes v1 para reintentos.

La consulta nativa `wrangler d1 info vclc-spending --config wrangler.jsonc --json` falló con `Authentication error [code: 10000]`. No se ejecutaron escrituras remotas. El acceso del navegador aparece en pantalla de login; se solicitó restablecer sesión mientras continúa trabajo local. El error no demuestra cambio de cuota ni pérdida de la base.

Sellado de release inmutable en curso mediante `scripts/package_placsp_launch.py`. Las mediciones y planes previos usan una identidad provisional de planificación; deben regenerarse contra la release sellada antes de cualquier importación/promoción. No presentar un hash provisional como release publicada.

## Release sellada y candidata remota

El proceso de empaquetado terminó y el verificador independiente comprobó 86.946 archivos originales, sus transportes completos/fraccionados y ZIP. Release definitiva: `82e44fce99c656795d622ac60fd3a76fe2f236e1b2e1186de529c08082373dc3`; ZIP SHA-256 `46e1b3ef2bff83528f3a312da30ae0ef40f91805248a1c0c0cdea2628b5c16e3`. Conteo 128.837 e importe 8.908.050.904.021 céntimos coinciden con auditoría; estados 48.019 adjudicados y 80.818 formalizados. No es una publicación remota.

El generador del backend se corrigió para reconstruir y verificar los fragmentos de `awards.json` de la release grande. Capacidad y lotes se regeneraron sobre la identidad definitiva: versión API `9fd6e3a6c5149328beae23aafd82ab3abc3865b0a05123465bb5f1ceaf4ee034`. Los lotes definitivos pasan replay repetido; usar `sealed-import-manifest.json`, no manifiestos provisionales anteriores.

Corrección del diagnóstico de acceso: `wrangler d1 execute` con SELECT funcionó, con una fila leída y cero escrituras. El fallo de `d1 info` no acreditaba pérdida general de autenticación. Se retiró la petición de iniciar sesión mediante aviso al mantenedor. La operación nativa de creación también funcionó: base candidata `vclc-spending-national-20260907`, UUID `c0229128-382b-4a12-9d52-845683ea41d3`, región WEUR. Configuración separada en `infra/cloudflare/spending-api/candidates/national-20260907.jsonc`, sin entry point de Worker ni ruta pública; configuración activa intacta.

Pendiente: verificar cuota restante compartida antes de cargar filas; publicación de los artefactos y promoción final con pruebas públicas. No se ha ejecutado ninguna carga SQL de datos en la candidata.

## Ejecutor de importación y cuota de cuenta

Se añadió `scripts/run_spending_import_batch.mjs`: una invocación ejecuta como máximo un lote, con identidad y checksum fijados, bloqueo local y ledger de intención/recibo. Exige evidencia de cuota total reciente, mismo día UTC, plan gratuito y 2.000 escrituras de reserva además del presupuesto del lote. Resultado incierto bloquea continuación; consumo superior al presupuesto detiene el plan conservando el recibo. No hay promoción automática ni reintentos.

Tres pruebas pasan: límites/frescura/cuenta de cuota, confirmación por bookmark y consumo real, y rechazo de checksum alterado/base activa/intento pendiente. El dry-run probado no crea ledger ni ejecuta red. La prueba usa datos sintéticos de cuota, no acredita disponibilidad real de Cloudflare.

Una pestaña nueva dirigida exclusivamente al panel D1 redirige a inicio de sesión. Se solicitó al mantenedor restablecer la sesión del panel para leer consumo de cuenta; esto no afecta a la autenticación SQL de Wrangler ya verificada. El inventario general del navegador fue rechazado por privacidad y no se utilizó como vía alternativa. La candidata remota continúa vacía; carga y publicación pendientes. Siguiente: observación real de cuota, primer lote con recibo, verificación remota y continuación escalonada.

## Nueva brecha de calidad: cuatro fechas oficiales dudosas

La prueba de API contra una copia aislada del Worker con la versión candidata encontró fechas `0205-01-24`, `0205-02-13`, `0225-01-24` y `0225-02-20`. Las versiones disponibles de los cuatro expedientes conservan esas fechas: no existe una fecha correcta corroborada en ese histórico local. No se corrigen a 2025 por conjetura. Evidencia: `candidate-date-quality.json`.

El recorrido funcional completo de la candidata pasa: 128.837 claves únicas paginadas, 8.908.050.904.021 céntimos, GALASA 11 resultados/572.335.676 céntimos, filtros, CSV, errores y 15 correcciones de fechas previamente definidas. La primera respuesta pesa 15.769 bytes. Esto acredita funcionalidad local, no calidad completa de fechas ni rendimiento remoto.

**La candidata no puede importarse ni promoverse todavía.** Se añadió un gate de fechas al generador normal y al planificador; el ejecutor rechaza planes sin `date_quality_passed: true`. Los planes sellados previos carecen de este gate y quedan como evidencia de replay, no como planes ejecutables. La prueba negativa verifica rechazo antes de emitir SQL y configuración activa intacta. La release original conserva fielmente el dato fuente; el problema está en su tratamiento para consulta/calendario.

Siguiente prioritario: representar las fechas no resueltas sin ocultar sus registros ni inventar años, con contador/aviso y acceso desde filtros. Después regenerar backend/planes, verificar todos los recorridos y cargar con cuota de cuenta confirmada. La sesión del panel sigue siendo necesaria para la carga posterior, pero no es el único requisito pendiente. Control público de privacidad y datos reales pasa, cero hallazgos; no hay nueva publicación remota.

## Sesión de Cloudflare restablecida

El mantenedor inició sesión. Lectura autenticada del panel D1 y de Workers plans: Free vigente, coste facturable mostrado $0.00, escrituras 79.21k / 100k y almacenamiento total 146.22 MB. Son cifras redondeadas de interfaz, no recibo exacto de cuota. La candidata muestra cero tablas y 12.29 kB. Evidencia: `cloudflare-account-usage.json`.

Acceso al panel resuelto. No se importó: el lote de 20.000 más reserva de 2.000 supera las aproximadamente 20.790 escrituras restantes; además sigue pendiente el tratamiento de cuatro fechas dudosas. Continuar con calidad de fechas y regeneración antes de volver a medir cuota para ejecutar.
