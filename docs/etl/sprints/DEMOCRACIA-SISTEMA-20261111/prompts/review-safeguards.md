# Prompt: revisión independiente de salvaguardas

Eres revisor independiente. Recibes fichas JSON de salvaguardas de la separación de poderes en España y compruebas,
**solo con las URL citadas en cada ficha** (más el texto legal oficial al que remitan), que lo que dice es verdad.
No leas otros ficheros del repositorio ni informes de otros agentes. No edites las fichas.

Fichas a revisar: {FILES}

## Qué compruebas en cada ficha
1. **Texto legal** (`rule`): el artículo citado dice lo que la ficha resume; plazo y sanción correctos.
2. **Fechas**: cada fecha de `episodes`, `remedy`, `mandate_terms` y `budget_presentation` coincide con su fuente.
3. **Atribución** (`power_holder`): el Gobierno indicado gobernaba en esa fecha y era quien tenía el poder relevante;
   en mayorías reforzadas, que los partidos listados eran de verdad indispensables y no falta ninguno; que no se
   atribuyen motivos.
4. **Cifras**: todo número (días, votos, recuentos) se puede comprobar en la fuente o recalcular de sus fechas.
5. **Enlaces**: cada URL abre y respalda el hecho al que va pegada (una URL que abre pero no dice eso es un error).
6. **Pares**: el mecanismo descrito para DE/FR/IT/PT coincide con la norma o informe citado.
7. **Clase**: aplica bien el criterio (`tercero_a_tiempo` / `tercero_tarde` / `buena_voluntad`) escrito en la ficha
   del método: un tercero que obliga, anula o sustituye a tiempo; tarde; o nadie.

Usa `curl -s` + `grep`/`python3` con salida acotada. Si una web bloquea el acceso por script (403, desafío), anótalo como
`unverifiable` (no como error) y prueba otra fuente oficial que cite la ficha. Máximo {WEBSEARCH} WebSearch en total.

## Salida
Escribe un JSON por ficha en `{OUTDIR}/<id>.json`:
```json
{"id": "…", "verdict": "verified|errors",
 "checked": 0, "unverifiable": ["qué y por qué"],
 "errors": [{"field": "episodes[2].start", "category": "date|attribution|legal_text|figure|link|peer|classification",
             "found": "lo que dice la ficha", "source_says": "lo que dice la fuente", "url": "…", "severity": "major|minor"}]}
```
- `verified` solo si no hay ningún error `major`. Un error de atribución es siempre `major`. Una errata sin efecto en
  el sentido (p. ej. un día de diferencia entre publicación y firma explicado en la ficha) es `minor`.
- Informe final ≤ 6 líneas: veredicto por ficha y el error más grave.
