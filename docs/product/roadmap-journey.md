# Roadmap de recorrido: el recibo del agua de Andalucía 2026

Estado: `recomendación derivada`, no nueva fuente de verdad. Este documento estrecha `P1. Public Product Wedge` y `P2. State Policy Ledger And Responsibility Chain V1` de `ROADMAP.md` hasta cerrar un recorrido ciudadano; `ROADMAP.md` conserva la autoridad sobre dirección y `docs/etl/e2e-scrape-load-tracker.md` sobre estado operativo.

Loop que se cierra: **duda concreta → compromiso exacto → actuación oficial → responsable → evidencia → desconocidos → cambio posterior compartible**. El primer corte ya cierra la secuencia para agua; el siguiente hueco es probar retorno real con un segundo snapshot.

Estado actual (`2026-07-25`):
- primer corte público e inmutable publicado;
- exportador conserva snapshots fechados y calcula diff semántico por compromiso;
- gate de frescura bloquea CI/publicación cuando el recibo supera `8` días sin revisión;
- el workflow vivo admite publicación `site` desde el commit limpio sin fingir que un ETL bloqueado está sano;
- sigue pendiente un segundo corte real, la auditoría con cinco usuarios y cualquier prueba de retorno.

## Arreglar primero el cuello de botella

- [x] **Fijar el baseline político actual.** Incorporar resultados oficiales, constitución de la XIII legislatura, investidura del `2026-07-02` y fecha de corte. Hecho cuando el artefacto ya no diga `convocada` y ninguna prueba preelectoral se presente como avance posterior.
- [x] **Revisar manualmente tres compromisos sobre agua del discurso de investidura.** Guardar texto exacto, página, actor, institución competente y acto futuro verificable. Hecho cuando ninguna tarjeta dependa de las `120` medidas extraídas automáticamente, cuyo contador de revisión actual es `0`.
- [x] **Definir `andalucia_water_commitment_receipt_v1`.** Campos mínimos: `commitment_id`, texto, fuente/localizador, fecha, responsable, competencia, checkpoint, estado, evidencia posterior, límites, snapshot y frescura. Hecho cuando un validador rechace recibos sin fuente, fecha, estado o límites.
- [x] **Separar baseline de progreso.** Votos, BOJA, presupuesto y contratos anteriores a investidura quedan como `historical_context`; solo actos posteriores pueden cambiar estado. Hecho cuando el test de corte temporal bloquee cualquier falso avance.
- [x] **Reducir la superficie pública a una respuesta.** Mover métricas de scrape, colas, lotes y censo completo a método/datos. Hecho cuando la página inicial muestre tres compromisos, no un muro de KPIs.
- [x] **Publicar la ruta real.** Hecho cuando `https://votaconlachola.org/elecciones/andalucia-2026/` devuelva `200`, muestre el snapshot vigente y pase auditoría móvil, privacidad y enlaces oficiales.

## Transición 1 — Ruido ajeno → Duda concreta

- [x] Cambiar la entrada principal a una pregunta: «¿Qué prometió el nuevo Gobierno andaluz sobre agua y qué ha hecho ya?». Hecho cuando la respuesta inicial aparezca sin explicar antes la plataforma.
- [x] Crear una tarjeta de entrada con los tres compromisos, fecha del último control y conteo de cambios posteriores. Hecho cuando el usuario elija uno en un clic.
- [x] Generar una ruta estática estable para el issue y otra por compromiso. Hecho cuando recargar o copiar el enlace conserve exactamente el mismo recibo y snapshot.
- [ ] Probar la entrada con cinco usuarios. Gate: al menos cuatro identifican el propósito y abren un compromiso en menos de `30 s`.
- [ ] Medir `water_receipt_open / landing_view`; antes de telemetría agregada, conservar un registro manual anónimo del test.

## Transición 2 — Duda concreta → Prueba visible

- [x] Renderizar cada compromiso en cinco bloques: declarado, actuación posterior, responsable/competencia, dinero/ejecución, desconocidos. Hecho cuando cada bloque tenga evidencia o un estado vacío explícito.
- [x] Enlazar fuente primaria y localizador desde la tarjeta. Hecho cuando la fuente se abra en un clic y el recorrido completo no supere dos.
- [x] Aplicar estados conservadores: `declarado`, `acto_oficial`, `financiado`, `contratado`, `entrega_observada`, `resultado_observado`, `sin_evidencia` e `incierto`; ningún estado implica mérito, culpa o causalidad.
- [ ] Mostrar competencia autonómica, estatal o compartida. Hecho cuando el caso de la presa de Alcolea no pueda atribuirse a la Junta sin explicar la competencia estatal citada.
- [x] Añadir revisión manual obligatoria para texto, tema y atribución. Hecho cuando ninguna extracción automática no revisada pueda entrar al recibo público.
- [ ] Medir `primary_source_open / commitment_open`. Gate inicial: `>=60%` en las cinco sesiones observadas.

## Transición 3 — Prueba visible → Utilidad repetida

- [x] Conservar cada recibo en una ruta inmutable y calcular diff semántico: evidencia añadida, estado, checkpoint, responsable o evaluación cambiados. El primer corte vive en `water-receipt/snapshots/2026-07-25.json`; el segundo reutilizará ese baseline automáticamente.
- [ ] Publicar el segundo corte real. Hecho cuando exista un snapshot posterior que muestre `changed` o `no_change` contra `2026-07-25`, sin editar el archivo histórico.
- [x] Mostrar fecha del último control, próximo control y freshness. CI y publicación fallan cuando el corte supera `8` días sin revisión.
- [ ] Permitir guardar «Agua» solo en `localStorage`. Hecho cuando la preferencia no viaje en query params ni se envíe al servidor.
- [ ] Ejecutar un control manual semanal de BOPA, BOJA, presupuesto y contratación para los tres compromisos. Automatizar solo después de que dos ciclos manuales prueben el contrato.
- [ ] Publicar «sin evidencia nueva» cuando corresponda. Hecho cuando ausencia de cambio sea verificable por fecha y fuentes revisadas.
- [ ] Medir `commitment_snapshot_revisit`. Gate de hipótesis: al menos tres de diez usuarios distribuidos abren un segundo snapshot dentro de `30` días.

## Transición 4 — Utilidad repetida → Prueba compartida

- [x] Añadir compartir explícito por fragmento, sin incluir preferencias automáticamente. Hecho cuando el receptor vea el mismo compromiso y snapshot.
- [ ] Generar metadatos sociales por compromiso con lenguaje factual y sin score. Hecho cuando la previsualización muestre compromiso, estado y fecha de corte.
- [x] Añadir bloque «Cita este recibo» con título, snapshot, fecha, URL y fuentes. Hecho cuando Óscar pueda copiarlo sin reconstrucción manual.
- [x] Mantener visible el límite principal al compartir. Hecho cuando ningún recorte social elimine `sin evidencia`, `incierto` o la distinción baseline/progreso.
- [ ] Medir `receipt_share / returning_viewer`; fallback manual: contar enlaces de prueba enviados y reaperturas confirmadas.

## Tareas mínimas para personas secundarias

- [ ] **Alba:** ofrecer arriba un resumen de tres frases y un botón «Ver prueba»; no obligarla a leer metodología.
- [x] **Óscar:** incluir historial/diff, localizador de fuente, snapshot inmutable y cita reproducible; no construir alertas hasta validar retorno.
- [x] **Irene:** ofrecer descarga JSON compacta del recibo y referencias; no exponer el snapshot andaluz completo como payload de página.
- [x] **Nadia/Tomás:** conservar colas, drafts, comandos y gates en superficies operativas separadas. La ruta ciudadana solo consume artefactos validados.

## Probar la hipótesis Aha

- [ ] Definir sesión y retorno sin identidad personal: `commitment_id`, `snapshot_id`, evento y marca temporal local/agregada.
- [ ] Instrumentar `commitment_open`, `primary_source_open`, `commitment_snapshot_revisit` y `receipt_share` después del test manual.
- [ ] Crear reporte mínimo que calcule aperturas, fuente abierta, retorno a 30 días y share; no usar fixtures sintéticos como evidencia de adopción.
- [ ] Mantener fallback manual hasta reunir `>=30` aperturas reales: diez enlaces distribuidos, cinco sesiones observadas y registro anónimo de retorno.
- [ ] Aceptar o rechazar la hipótesis tras dos snapshots públicos. Aceptar solo si el retorno se concentra en quienes abrieron una fuente primaria.

## Desbloquear producción — solo lo que necesita el loop

- [x] Resolver la discrepancia de publicación: la ruta se publica en Cloudflare Pages y en `gh-pages`, origen que todavía sirve el dominio canónico.
- [x] Añadir presupuesto de salida: HTML inicial `<=250 KB` y JSON del recibo `<=250 KB` sin comprimir. El snapshot técnico de `14,4 MB` queda como descarga separada.
- [x] Ejecutar `just privacy-check-public-artifacts` y el build público canónico. Hecho cuando ambos pasen sobre el mismo artefacto.
- [x] Ampliar auditoría de rutas para validar esta ruta, título, tres compromisos, una fuente primaria, estado vacío y límite visible; un simple HTTP `200` no basta.
- [x] Añadir freshness gate que falle si el recibo supera `8` días sin un nuevo control. El gate corre en PR/push y antes del publish vivo.

## Diferido hasta completar un recorrido entero

- Todas las `120` medidas programáticas y los `10` issues; primero tres compromisos revisados de un issue.
- Censo completo de `2.215` candidatos, comparador de `27` partidos y colas públicas de revisión.
- Recomendación de voto, rankings, mérito/culpa y causalidad de outcomes.
- Calendario electoral como wedge principal; queda como utilidad secundaria después de corregir fechas pasadas.
- Nuevas jurisdicciones, municipios y dominios no necesarios para agua andaluza.
- Plugin SDK, ecosistema de colaboradores y nuevas superficies genéricas.
- Q&A libre, dossiers adicionales y automatización amplia de review hasta que el recibo pruebe retorno real.
- Más backfills o scrapers sin efecto directo en uno de los tres compromisos.
