# Census of one official list (one part file per agent)

The ledger must say, per family of findings, whether its counts are a CENSUS (every item of an enumerable official list
inside the window 2011-12-21..2026-11-11) or a selection. You build one census.

Output: `etl/data/seeds/democracy_conduct_v1.d/events_census_{FAMILY}.json` with
```
{"part": "census_{FAMILY}",
 "census": {"family": "{FAMILY}", "scope": "<one sentence: exactly what the list covers>",
            "list_source": {"url": "...", "title": "...", "retrieved": "2026-11-11"},
            "rows": [ {"ref": "<official id/number>", "date": "YYYY-MM-DD", "subject": "<party or person + office>",
                       "outcome": "<what the body decided, ≤100 chars>", "in_scope": true|false,
                       "reason": "<why in/out of scope, ≤100 chars>", "event_id": "<id if it became an event, else null>"} ],
            "n_listed": N, "n_in_scope": M},
 "events": [ ...one ledger event per in-scope row that is attributable to a Congress party and firm... ],
 "pending": [ ...in-scope rows attributable to a party but under appeal (same shape as below)... ]}
```
Every row of the official list inside the window goes in `rows` (in or out), so «M de N» is checkable.
Events use the ledger schema exactly as in `prompts/events-draft.md` (read it: fields, attribution rules, quote ≤15 words
checked with the kit) plus `"coverage": {"type": "census", "family": "{FAMILY}"}`. Parties: psoe, pp, vox, sumar,
podemos, erc, junts, bildu, pnv, bng, cc, upn. Mapping: EH Bildu coalition/federation → bildu; EAJ-PNV → pnv;
Junts per Catalunya → junts; CDC/PDeCAT → junts with lineage "predecessor"; Unidas Podemos list → podemos (list);
IU, Comuns, En Marea, Compromís, Ciudadanos and others are not Congress units today: keep them in `rows` with
`event_id: null` and reason «no es una unidad del Congreso actual».
Pending shape: {"pending_id", "party_id", "role", "person", "body", "date", "finding", "indicator", "appeal",
"source": {url,title,retrieved,quote,quote_lang}}.

Already in the ledger (reuse: put their id in the row's event_id, do NOT create a duplicate event): {ALREADY}.

Kit: `python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py --help` (`text URL --grep`, `quote`). For PDF
tables run `pdftotext -layout` on the cached file (kit prints its sha256; files are in /tmp/vclc-democracy-kit) in your
own scratch folder. Validate: `python3 scripts/validate_democracy_conduct.py <your file>` (0 errors). ≤4 WebSearch.
Report ≤6 lines: N listed, M in scope, events, pending, and «what would have saved turns».
