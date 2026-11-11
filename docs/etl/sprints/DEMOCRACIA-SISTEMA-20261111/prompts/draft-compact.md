# Brief compacto (ola 3): documentar salvaguardas

Rellenas fichas JSON de salvaguardas de la separación de poderes en España. Hechos con fecha y fuente primaria; nada
de motivos, intenciones ni previsiones. No leas otros ficheros del repo ni el brief largo.

**Todo lo que necesitas está en la hoja de trabajo** `worklists/wave3/<id>.md` (texto legal del BOE, búsquedas del BOE
ya hechas con referencias y títulos, pares). Léela una vez con `cat` (≤ 8 k caracteres). Fuera de ella, como mucho
3 consultas del kit por ficha y 4 WebSearch en total:
`python3 scripts/export_public_viz_democracy.py kit boe-search "<texto>" --section T|2 [--year-from A]` ·
`kit boe-doc <BOE-ref> --grep "<regex>"` · `kit grep <url> "<regex>"`. Salidas ≤ 2.000 caracteres.

**Escribe cada ficha de una vez** con un solo `python3 - <<'EOF'` que cargue el esqueleto, rellene los campos y lo
guarde (conserva `_hints`). Luego `python3 scripts/validate_democracy_safeguards.py --only <ids>` y corrige.

Campos: `rule{text, articles[], url, deadline}`, `obligated`, `enforcer{who, short≤60, power: obliga|anula|sustituye|
automatica|declara|nadie}`, `sanction`, `sanction_short≤70`, `remedy_delay{days|null, basis, sources[]}`,
`classification`, `classification_reason`, `episodes[]`, `peers{DEU,FRA,ITA,PRT}`, `limits`.
Episodio: `{id, start, end|null, kind: incumplimiento_declarado|plazo_vencido|tension|remedio|aval, summary,
power_holder{government: suarez|calvo_sotelo|gonzalez|aznar|zapatero|rajoy|sanchez|null, body, indispensable_parties:
null, note, majority?}, remedy{by, ruling, date, act_date}|null, sources[{label,url}]}`.

Reglas:
- Clase (fijada): `tercero_a_tiempo` (un tercero obliga, anula o sustituye, o hay consecuencia automática, antes de que
  el incumplimiento se consume o en ≤ 6 meses); `tercero_tarde` (el remedio llega cuando el acto ya produjo efectos o
  tarda > 6 meses); `buena_voluntad` (nadie puede obligar ni sustituir). Ante la duda, la más débil.
- Atribución: actos del Gobierno → `government` del día del acto (gobiernos en `kit govs`); actos de las Cortes, la Mesa
  o una mayoría → `government: null` y `body` (p. ej. «Mesa del Congreso»); mayorías de 3/5 o 2/3 →
  `majority: {"rule": "3/5"|"2/3", "chambers": [...]}` y nunca nombres a un partido como responsable. Gobiernos
  autonómicos: `government: null`, `body: "Gobierno de <comunidad>"`.
- Todos los periodos desde 1978 y todos los gobiernos; ≤ 12 episodios por ficha; registra también los avales.
- Pares: una frase con su fuente si la hoja la trae; si no, `{"mechanism": "no_signal", "classification": "no_signal",
  "sources": []}`. No investigues pares.
- Sentencias del TC: cita su página del BOE. Del Supremo: nota de prensa oficial (poderjudicial.es) si no hay BOE.
- Si no encuentras algo, déjalo fuera y dilo en `limits`. Nunca escribas de memoria.

Informe final ≤ 5 líneas, con «qué me habría ahorrado turnos».
