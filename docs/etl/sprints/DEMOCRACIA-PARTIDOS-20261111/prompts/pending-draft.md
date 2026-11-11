# «Pendiente, no contado»: official findings excluded only because they are not firm

Goal: so that an empty or short profile is not read as a clean one, list for EVERY party (psoe, pp, vox, sumar, podemos,
erc, junts, bildu, pnv, bng, cc, upn) the official findings dated 2011-12-21..2026-11-11 that the ledger does not count
only because they are not firm:
- first-instance criminal convictions (Audiencia Provincial, Audiencia Nacional, TSJ) of a party office holder that are
  under appeal; same office-holder rule as the ledger: member of the party (or elected on its list) holding public or
  party office at the facts, for corruption, offences against the constitutional order, disobedience, political
  violence or hate offences;
- administrative sanctions by the Junta Electoral Central or the Tribunal de Cuentas on a party or office holder that an
  official record shows under appeal.
NOT included: investigations, indictments (autos de procesamiento / apertura de juicio oral), acquittals, archived cases.

Write into `etl/data/seeds/democracy_conduct_v1.d/pending_findings.json`, key `pending`, one object per finding:
{"pending_id": "kebab-case", "party_id": "...", "role": "national_government|regional_government|local_government|opposition|party_organization",
 "person": "name and office at the facts (or the party)", "body": "court/body", "date": "YYYY-MM-DD (date of the first-instance ruling or sanction)",
 "finding": "≤140 chars, neutral: what was decided (offence, sentence)", "indicator": "corrupcion|reglas|violencia|minorias|...",
 "appeal": "who appealed where, and current state if an official record says so",
 "source": {"url": "https://official host", "title": "...", "retrieved": "2026-11-11", "quote": "literal ≤15 words", "quote_lang": "es"},
 "membership_source": {"url": "...", "quote": "literal ≤15 words"} }
Known starting point: Vox, Tribunal de Cuentas sanction of 28-07-2025 (50.000 €, 2020 accounts), under appeal at the
Supreme Court — tcu.es register «Procedimientos sancionadores». Search every other party with the same effort and
report which parties you searched with no result. Do not invent symmetry; do not omit a party's case either.

Official hosts: poderjudicial.es (CGPJ press notes on first-instance rulings), boe.es, tcu.es, juntaelectoralcentral.es,
congreso.es / senado.es / regional parliaments (membership), party websites only for party posts. No newspapers.
Kit (one call per check): `python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py --help`
(`text URL --grep`, `quote URL "…"`). ≤6 WebSearch. Validate quotes with `kit.py quote`. Report ≤6 lines plus «what would
have saved turns».
