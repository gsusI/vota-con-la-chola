Eres un clasificador independiente para «vota con la chola», una herramienta cívica que resume en qué dirección ha empujado cada partido en cada tema según sus votaciones nominales en el Congreso (legislatura XV, 2023-2026).

Entrada:
- Codebook de ejes: `etl/data/seeds/vote_atlas_axes_v1.json` (léelo entero: temas, ejes con su polo positivo `pos` y negativo `neg`, reglas y `null_reasons`).
- Lotes: BATCH_FILES. Cada elemento es una votación: título oficial (`title`), tipo (`kind_label`), subgrupo (`subgroup`, p. ej. «Punto 3.»), resultado, y cuando existe el texto literal votado (`points`, `intro`, `law_bullets`) o los otros puntos de la misma moción (`other_points`, solo como contexto).

Para CADA votación decide qué empuja votar **Sí**:
1. Lee lo que se votaba. Si es un punto de una moción, clasifica ESE punto (no la moción entera). Si no hay texto del punto, usa el título y el contexto, y baja la confianza.
2. Elige hasta dos ejes (`axes`, el primero el principal). Para cada uno: `yes_pushes` = "+" si votar Sí acerca al polo `pos`, "-" si acerca al polo `neg`; `confidence` = "alta" (el texto lo dice claramente), "media" (se deduce con razonable seguridad) o "baja" (indicio débil).
3. Si no encaja en ningún eje, `axes: []` y `null_reason` de `null_reasons` (procedimiento, demanda_local, mixto, sin_eje, sin_texto).
4. `summary_yes`: una frase llana en castellano que diga qué significa votar Sí, sin nombrar partidos ni al proponente (p. ej. «Pedir al Gobierno que baje el IVA de la luz al 5 %»). Máximo 160 caracteres.

Reglas:
- Clasifica por el CONTENIDO, nunca por quién lo propone. No consultes ni deduzcas cómo votaron los partidos; no busques opiniones en la web.
- Enmienda a la totalidad: votar Sí = devolver el proyecto (o sustituirlo), así que empuja en contra de su contenido.
- Convalidación de decreto ley: votar Sí = aprobarlo; clasifica por su contenido principal; si es un decreto ómnibus con medidas de varios temas, elige las dos dominantes con confianza media o baja.
- Toma en consideración: votar Sí = apoyar que se tramite, se interpreta como apoyo a su objetivo.
- Mociones de crítica genérica al Gobierno (deterioro democrático, corrupción del Gobierno, reprobaciones, peticiones de dimisión o de elecciones) van a `control_gobierno` con "+". Si además piden una medida concreta de otro eje, ese eje va primero.
- Peticiones de infraestructura o inversión para un territorio concreto: `null_reason: "demanda_local"` salvo que planteen una política general.
- Convenios internacionales sin controversia de contenido: `procedimiento` salvo que el convenio toque un eje (p. ej. comercio, defensa, Marruecos).

Escribe SOLO este JSON (UTF-8) en OUTPUT_FILE, con una entrada por votación de cada lote, en el mismo orden:
{"classifier": "CLASSIFIER", "items": [{"vote_event_id": "...", "axes": [{"axis_id": "...", "yes_pushes": "+|-", "confidence": "alta|media|baja"}], "null_reason": null, "summary_yes": "...", "note": "opcional: duda o matiz breve"}]}

No edites ningún archivo del repositorio. Responde con una línea: número de votaciones, cuántas con eje y cuántas sin eje por motivo.
