# Prompt: fichas del catálogo, corte 3 (empleo, inmigración y capacidad sanitaria)

Plantilla para los agentes que rellenan fichas del simulador (`/visualizaciones/sistema/`). `{AGENT}` y `{IDS}` se
sustituyen al lanzar. Bucle de `AGENTS.md`: piloto de un agente, medir, arreglar la herramienta, después olas.

---

You fill causal-relation cards for a policy simulator of Spain (reduced-form model, annual steps, deviations from an
official baseline). Each card is one number the engine uses, with its source, range and what contradicts it.

**Your file**: `etl/data/manual/system_model/drafts/part_labour_{AGENT}.json` (already has a skeleton with every key
for your cards: {IDS}). Edit it; do not create other files in the repo. Your briefs (what each card needs and where to
look) are the items with `"agent": "{AGENT}"` in `etl/data/manual/system_model/worklist_labour.json`: read only those
items (e.g. `python3 -c "import json;[print(json.dumps(i,ensure_ascii=False)) for i in json.load(open('etl/data/manual/system_model/worklist_labour.json'))['items'] if i['agent']=='{AGENT}']"`).

**Do NOT read**: other part files, the exporter, the engine, the page, seeds, guides or other agents' outputs.

**Tools**
- `python3 -m scripts.voting_aid_impacts_kit fetch URL -g REGEX [-C 2] [--max 40]`: downloads once into a shared cache,
  PDF to text with `=== pág. N ===` markers, prints only matching lines. Use it instead of WebFetch for PDFs.
- From python, in ONE call: `from scripts.voting_aid_impacts_kit import text, ine_series, eurostat_values`
  (`text(url)` = cached plain text; slice it yourself, e.g. find a phrase and print 600 characters around it).
- `python3 -m scripts.voting_aid_impacts_kit ine TABLE -g REGEX` (INE tempus) and `eurostat DATASET "geo=ES&..."`.
- WebSearch at most 4 times in total (shared quota). Prefer known URLs from the brief.
- Never `cat` whole files, never Read PDFs or images; keep every tool output short (grep, --max).
- If a host fails twice (403, TLS, timeout), stop trying it: use another official source or say in `derivation` that the
  figure could not be verified, and lower the grade.

**Card contract** (validator: `python3 scripts/system_model_kit.py validate etl/data/manual/system_model/drafts/part_labour_{AGENT}.json`)
- `parameter`: `low <= central <= high`, numbers, in EXACTLY the unit written in the skeleton (do not change `name` or
  `unit`). A debate card's `central` is your judgement; `low`/`high` span the schools.
- `lag_years`: a number or `[min, max]`.
- `grade`: A (accounting, law or Spanish data), B (solid study from another country or meta-analysis), C (institutional
  consensus without own estimate, or a derivation with stated assumptions), D (assumption). A requires
  `spain_evidence: "si"`. `extra_parameters[].grade` may differ from the card's when one number is solid and another is not.
- `sources[]`: every field filled: `url` (the document you actually read), `title`, `authors_year`, `country`, `period`,
  `method`, `locator` (page, table, row), `quote` (≤ 40 words, verbatim from the source, in its language),
  `value_in_source` (the number as the source gives it, with its unit).
- `contrary_evidence[]`: `url`, `title`, `finding` (what points the other way). Empty list only if you looked and found
  nothing; say so in `derivation`.
- `debate`: `null`, or for a contested parameter `{"id": "<param name>", "schools": [{"label": "...", "central": n,
  "source_index": i}, ...]}` with ≥ 2 schools (≥ 3 when the brief asks), each pointing to its entry in `sources`.
- `derivation`: how each number was obtained from the sources (arithmetic shown, normalisations, what is an
  approximation). This is what a reviewer will check against the source.
- `note_es`: ≤ 400 characters, plain Spanish for a citizen, starting with «Según …». No causal verbs the source does
  not support («gracias a», «por culpa de»). Name what is uncertain.

Example of a finished card (another slice):
```json
{EXAMPLE}
```

**Budget**: fill all your cards in one edit at the end (draft numbers in your head or in python, not in many edits),
validate once, fix, validate again. Report in ≤ 6 lines: card ids with central value and grade, anything you could
not verify, and one line «what tool or data would have saved me turns».
