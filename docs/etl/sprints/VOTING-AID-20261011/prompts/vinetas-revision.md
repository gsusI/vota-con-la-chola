# Revisión de viñetas «Qué se votaba» — preguntas curadas

Eres el revisor (segunda mano) de unas viñetas ya redactadas. Cada viñeta resume, en lenguaje llano, lo que contenía el texto
oficial votado en el Congreso; se muestra al ciudadano ANTES de responder a una pregunta de la ayuda al voto. Tu trabajo es
comprobar cada viñeta contra el texto oficial y dejar una versión final correcta.

## Entrada (lista JSON, un elemento por documento)
- `doc_key`, `url`, `sha256`: identifican el documento. Cópialos tal cual.
- `text_path`: texto plano del documento oficial. Si `text_chars` > 60000 no lo leas entero: usa
  `grep -n` sobre el localizador de cada viñeta (p. ej. `grep -n "Artículo 9 bis" <text_path>`) y lee el tramo con Read (offset/limit).
- `text_status_label`: qué versión del texto es (texto inicial, aprobado, BOE…).
- `bullets`: viñetas actuales `{text, locator}`. `drafter_notes`: avisos del redactor.
- `votes`: votaciones que usan el documento, con la afirmación curada (`statement`) y su contexto. El título puede nombrar al grupo
  proponente: eso NO puede aparecer en las viñetas.

## Qué comprobar en CADA viñeta
1. **Fundamentada**: lo que dice está en el texto, en la parte dispositiva/articulado (no en la exposición de motivos ni el preámbulo).
2. **Localizador correcto**: existe en el texto y apunta a donde está lo que dice la viñeta. Corrígelo si no.
3. **Exacta**: cifras, plazos, porcentajes, fechas, sujetos y alcance idénticos al texto. Nada añadido ni exagerado; sin
   generalizar («todos», «prohíbe») si el texto es más limitado; respeta condiciones y excepciones relevantes.
4. **Neutral**: sin partidos ni grupos, sin quién lo propuso, sin resultado de la votación, sin adjetivos valorativos.
5. **Llana y breve**: ≤ ~180 caracteres, entendible sin saber derecho.
6. **Modo verbal coherente**: describe lo que el texto haría/pide (no lo presentes como ley vigente si es una proposición).

## Y en el conjunto del documento
- **Cobertura**: ¿faltan medidas principales que un votante querría saber (sobre todo las relacionadas con la afirmación curada)?
  ¿Sobra una viñeta menor? Máximo 6 viñetas; ordénalas de más a menos importante.
- **Ómnibus**: si el texto mezcla temas, los bloques principales deben estar cubiertos.
- **Documento correcto**: si el texto no corresponde a lo votado o es solo una versión parcial, dilo en `issues`.

## Salida
Escribe con la herramienta Write el fichero indicado: lista JSON, un elemento por documento, en el mismo orden:

```json
[
  {
    "doc_key": "…", "url": "…", "sha256": "…",
    "verdict": "ok | corregido",
    "bullets": [{"text": "…", "locator": "…"}],
    "changes": ["viñeta 2: la cifra era 6 meses, no 9 (Artículo 9 bis)", "añadida viñeta sobre …"],
    "issues": ["opcional: problemas que no se pueden arreglar con viñetas (versión del texto, documento dudoso…)"]
  }
]
```

`bullets` es SIEMPRE la lista final completa (aunque no cambie nada). `changes` vacía si `verdict` es `ok`.
Valida el JSON al final (`python3 -c "import json,sys; json.load(open(sys.argv[1]))" <fichero>`). No uses la red. No toques el
repositorio. Responde al final con una línea: documentos revisados, cuántos corregidos y cualquier incidencia grave.
