# DEMOCRACIA-PARTIDOS-20261111 · Conducta democrática por partido

Page: `/visualizaciones/democracia/partidos/` (slice 2 of the democracy program; the system side, «qué contrapesos
dependen de la buena voluntad», is `democracia-fracturas` in `ui/site/app/visualizaciones/democracia/`).

Question: how has each party in the Congress used power and treated democratic checks? Answered as a sourced ledger
plus a vote layer, with one profile per party. Not a ranking unless the ranking survives the sensitivity test below.

Files: seed `etl/data/seeds/democracy_conduct_v1.json` (+ part files in `etl/data/seeds/democracy_conduct_v1.d/`),
exporter `scripts/export_public_viz_democracy_parties.py`, output `ui/site/public/visualizaciones/data/democracia-partidos.{json,csv}`,
validator `scripts/validate_democracy_conduct.py`, test `tests/test_democracy_conduct.py`, page
`ui/site/app/visualizaciones/democracia/partidos/`.

## 1. Codebook (written 2026-11-11, before any event was collected)

### 1.1 References

- Levitsky, S. and Ziblatt, D. (2018), *How Democracies Die*, table 1: four behavioural indicators of authoritarian
  behaviour (rejection of the democratic rules of the game; denial of the legitimacy of opponents; toleration or
  encouragement of violence; readiness to curtail civil liberties of opponents, including the media).
- V-Dem, V-Party dataset, anti-pluralism index (`v2xpa_antiplural`) and its four items: commitment to political
  pluralism (`v2paplur`), demonization of opponents (`v2paopresp`), rejection of minority rights (`v2paminor`),
  encouragement of violence (`v2paviol`). Used twice: its items shape our indicators, and its scores are the external
  benchmark (section 4).
- European Commission, Rule of Law Report, four pillars: justice system, anti-corruption framework, media pluralism
  and media freedom, other institutional checks and balances.

### 1.2 Indicators

Each incident has exactly one primary indicator. The same definition applies to a party in government and in
opposition; `power` says how often the act needs office (the composite is tested with and without those acts).

| id | Indicator | Source family | Operational definition (what counts) | power |
|---|---|---|---|---|
| `reglas` | Rechaza las reglas del juego | L&Z 1, V-Party `v2paplur` | A binding finding (court, Constitutional Court, electoral board) that the party, its group or its office holders adopted or carried out an act outside the constitutional procedure for gaining or exercising power, or refused to comply with an order of a court or of the electoral administration. | mixed |
| `legitimidad` | Niega la legitimidad del adversario | L&Z 2, V-Party `v2paopresp` | A binding finding that the party sought to exclude a lawful rival from competition (ban, disqualification outside the law) or a firm conviction of a party office holder for slander/insult against a political rival in that capacity. Statements without an official finding do not count. | no |
| `violencia` | Tolera o alienta la violencia | L&Z 3, V-Party `v2paviol` | A firm criminal conviction of a party office holder for violence against persons, incitement to violence or glorification of terrorism in a political context (protest, campaign, political act), or a judicial finding that the party supports violence. | no |
| `libertades` | Restringe libertades de opositores o medios | L&Z 4 | A law, decree or act adopted by the party in office that a court or the Constitutional Court annulled for breaching freedom of expression, information, assembly, association or movement, or a non-binding finding by a named international or EU body that such an act restricts them. | mostly |
| `minorias` | Derechos de minorías | V-Party `v2paminor` | A law or act adopted by the party in office annulled for discrimination against a minority, or a firm conviction of a party office holder for a hate offence. | mostly |
| `justicia` | Independencia judicial | RoL pillar 1 | A finding by the Constitutional Court, the Venice Commission, GRECO or the Rule of Law Report that a specific act of the party (a law it proposed, a decision of its government) weakened the independence of judges, the CGPJ, the Constitutional Court or the prosecution service, or a binding finding that it obstructed their renewal. | mostly |
| `corrupcion` | Corrupción | RoL pillar 2 | A firm conviction (prison or not) of a party office holder for corruption offences (bribery, embezzlement, influence peddling, illegal party financing, prevaricación tied to public funds), a firm civil liability of the party itself (`partícipe a título lucrativo`) or a criminal conviction of the party as a legal person; a Tribunal de Cuentas finding of irregular party financing. | mostly (illegal financing: no) |
| `medios` | Pluralismo de medios | RoL pillar 3 | A finding by the Rule of Law Report, the Venice Commission, a court or the media regulator that a specific act of the party in office reduced the independence of public media or media pluralism. | mostly |
| `contrapesos` | Controles y contrapesos | RoL pillar 4 | The Constitutional Court annulling an act for exceeding the limits of decree-laws, of emergency powers or of parliamentary procedure, or for breaching the rights of members of parliament; a Venice Commission or Rule of Law Report finding that the legislative procedure of a specific act bypassed consultation or scrutiny; GRECO finding the government of the day failed to implement its recommendations. | mostly |

### 1.3 Severity rule (fixed in advance; it grades the legal force of the official finding, not our view of the act)

- **3** · firm criminal conviction with a prison sentence of one year or more (of a party office holder or of the
  party), or a binding ruling that annuls an act **in full** (whole law, decree or resolution).
- **2** · firm conviction without prison or with less than one year, firm civil liability of the party, a binding
  ruling that annuls an act **in part** or declares a right violated (amparo), or a sanction imposed by the electoral
  board or the Tribunal de Cuentas. Pilot amendment (2026-11-11, before the review): a binding ruling in a conflict
  between constitutional bodies that declares one body breached another's power without annulling an act
  (`binding_declaration`) is graded like an amparo, 2; the original list had no type for it.
- **1** · non-binding critical finding that names the specific act: a Venice Commission opinion, a Rule of Law Report
  recommendation or concern, a GRECO conclusion that a recommendation was not implemented.

Clarifications after the pilot review, before scaling (2026-11-11): the unit of «full» is the whole norm or resolution
as published (annulling one provision of a decree-law is partial, even if that provision was all that was challenged);
one event per ruling, coded with the most severe finding attributable to each party (e.g. Gürtel: the PP treasurer's
prison sentence, 3, with the party's civil liability in the note); rulings that annul only for the State/region
distribution of competences are out of scope (they are not checks on power in the references used). Same for
rulings that annul only on equality grounds (art. 14 CE), which no indicator covers: STC 137/2025 on the amnesty law
(partial, art. 14) is excluded for that reason, like every other art.-14-only ruling; the Venice Commission opinion on
the same law stays in (`contrapesos`). Membership proof for `office_holder`: an official record from the office where
the facts happened; when none is reachable, the nearest later official record in an unbroken public career, said in
the item's note (José Antonio Viera, PSOE, 2011 list; Miguel Zerolo, CC, 2007 group while still mayor).

Pardons and amnesty extinguish the penalty or the criminal liability, not the firm finding, so they do not change
severity (STS 459/2019 keeps its code after the 2021 pardons and the 2024-2026 amnesty decisions, recorded in `status`).
If a later ruling annuls or narrows the finding (e.g. Constitutional Court amparo against a Supreme Court conviction),
severity is that of what survives, and the item keeps the history (`status`). Pending cases (not firm) never count;
this includes administrative sanctions (electoral board, Tribunal de Cuentas) that an official record shows under appeal.

### 1.4 Attribution rule

An incident is attributed to a party only when the official record ties it to the party:
- `government_act`: a decree, decision or bill of a government is attributed to the party or parties holding that
  government at the date of the act (national or regional), never to other parties that voted for it (we do not have
  roll-call data before 2019 for every case).
- `group_initiative`: a parliamentary bill or resolution is attributed to the group(s) that tabled it.
- `office_holder`: a conviction is attributed to the party the person was a member of at the date of the facts while
  holding a public or party office; for independents, the electoral list they were elected on. A person with no
  public or party office at the date of the facts does not count.
- `party`: the party as a legal person or civil liable.
- System findings that do not name a specific act of a party (e.g. «the CGPJ has not been renewed») go to the
  `system` list, unattributed; the sibling page covers them.

Lineage: Congress parties of legislature 15 are the units (`psoe`, `pp`, `vox`, `sumar`, `podemos`, `erc`, `junts`,
`bildu`, `pnv`, `bng`, `cc`, `upn`). An incident of an electoral list that the current party heads is attributed to it
with `lineage: "list"` (e.g. JxCat 2017-2020 → `junts`; Unidas Podemos 2016-2023 → `podemos`). Incidents of legally
distinct predecessor parties (CDC, PDeCAT, Batasuna) are recorded with `lineage: "predecessor"`, shown on the profile
as such and excluded from every count and from the composite, unless the convicted person holds a leadership post in
the current party at the retrieval date, documented by a source (`lineage: "person"`, counted).

Role at the time (`role`): `national_government`, `regional_government`, `local_government`, `opposition`,
`party_organization` (the party apparatus, not a public office).

Window: findings dated 2011-12-21 (start of the Rajoy government) to the retrieval date, so both large parties have
national-government years in it (PP 6.5, PSOE 8.4 by 2026-11). Act dates may be earlier (convictions arrive years
late); both are stored.

Sources allowed: Constitutional Court and Supreme Court/Audiencia/TSJ rulings (BOE, tribunalconstitucional.es,
poderjudicial.es), Venice Commission opinions, the Spain chapters of the Rule of Law Report 2020-2026, GRECO
evaluation and compliance reports, Junta Electoral Central resolutions, Tribunal de Cuentas reports. No opinion
columns, no motives. Each item: date, party, role, indicator, severity by the rule, source URL, retrieval date and a
literal quote of at most 15 words from the source.

### 1.5 Vote layer (our data)

From the published vote atlas (3,910 Congress votes of legislatures 14 and 15, `ui/site/public/citizen/data/vote_atlas_v1.json`),
votes whose axis is `justicia_independencia`, `instituciones_reglas` or `anticorrupcion` (structural candidates) or
`control_gobierno` (scrutiny), confidence `media`/`alta` as in the atlas scoring.
- **Estructural** = axis in the first three and not also `control_gobierno`: rules that would bind any future
  government. Split into **vinculante** (law-making: toma, totalidad, final, decree-law, amendments, Senate vetoes and
  amendments, votos particulares) and **declarativa** (PNL, mociones).
- **Escrutinio** = `control_gobierno`: inquiries, reprobations, demands on the current government.
- Party position per vote = the party's majority: +1 if it voted towards more checks (Sí on a `+` vote or No on a `−`
  vote), −1 the other way, 0 abstention; score = mean, with the count. Reported with the party's role in that
  legislature and with who tabled the initiative (Government, own group, others), so support for checks that bind
  oneself is visible.
- Role problem, stated openly: in both legislatures the PSOE governed and every other party was in opposition, so
  no party changed role inside the data. The vote layer cannot separate conviction from role; it is published as
  «cómo votó en el papel que tenía», never compared as if roles were equal. Legislature 14 positions exist only for
  groups that map to one party (PSOE, PP, Vox, ERC, EH Bildu, PNV).
- `seguridad_penal` is not used: it measures penal policy (punitive vs garantista), not checks on power.

Decree-laws: count of Reales Decretos-leyes per government (per 12 months in office) and as a share of primary
legislation (RDL / (RDL + Ley + Ley Orgánica)), 1979-2026, from BOE ELI listings (`/eli/es/rdl/<year>`), with the
sibling seed `democracy_safeguards_v1.json` used instead if it carries the series. Volume is not abuse by itself; the
abuse signal is the Constitutional Court annulments in the ledger.

### 1.6 Composite «riesgo» and the sensitivity test (rule fixed in advance)

Party score = Σ severity × indicator weight over attributed incidents (lineage `same`/`list`). Weightings:
`W1` equal weights, severity 1-2-3; `W2` severity squared (1-4-9); `W3` Levitsky-Ziblatt + minorías only; `W4` Rule
of Law pillars only; `W5` W1 without power-only acts; `W6` W1 per year in office (national + regional); `W7` W1 plus the
vote layer (share of structural binding votes against checks × 3).
Publication rule: the composite is published only if **no pair of parties reverses its order** between any two
weightings (ties allowed). Otherwise the page publishes profiles without a composite, says so, and shows the test.

### 1.7 Quality gates and decision rules (written before the review)

- Pilot: 10 events across ≥4 parties including PSOE and PP + the vote layer for one axis. An independent reviewer
  agent gets only each item and its URL and checks date, attribution, coding (indicator + severity by the rule) and
  quote. **Pass = ≥9 of 10 fully verified and no attribution error.** Fail → stop and report, no scaling.
- After scaling: random sample of 15 events, same review and the same threshold (≥13/15, no attribution error), plus a
  symmetry check: pairs of comparable acts by different parties must get the same indicator and severity; the pairs
  compared are listed here.
- Mechanical validator: schema, URL and quote present (≤15 words), party/role/indicator/severity valid, severity
  consistent with `finding_type`, window respected.

## 2. What it cannot say

- Absence of incidents for a party that never governed is not evidence of good conduct: most indicators need office.
- Convictions arrive years after the facts; recent conduct is under-represented.
- The ledger only contains what official bodies chose to examine and what was brought before them.
- Severity grades the legal force of the finding, not the harm of the act.

## 3. Review results

### Pilot (2026-11-11)
- Drafting: 1 agent, 10 events across PP, PSOE, Podemos, ERC and Junts (prompt `prompts/events-draft.md`), 82 turns,
  9.4 M input tokens (≈0.94 M per event). Three `_problem` flags raised by the drafter and fixed before review:
  STC 13/2021 annulled nothing (replaced by STC 172/2020, which annulled «no autorizado»); a conflict ruling had no
  finding type (`binding_declaration` added, severity 2); Torra's list proved with the JEC results in the BOE
  (BOE-A-2018-426).
- Independent review (`prompts/events-review.md`, verdicts in `evidence/review-pilot/`): **9/10 verified, 0
  attribution errors → pass** (rule: ≥9/10 and no attribution error). The failure (STC 73/2017 coded partial, the
  reviewer read it as full because the appeal challenged only that provision) is resolved by the rule text, now made
  explicit above: the unit is the whole decree-law, so it stays partial. Reviewer caveats: the BOE rulings name the
  «Gobierno», not the party (the government-party link is the seed's government table, source La Moncloa); the TS
  PDF for Torra has a blank date (date from the official file name and press release); the 2021 Rule of Law chapter
  was verified on the Austrian Parliament's copy (commission.europa.eu answered 429/503).
- Vote layer pilot (`justicia_independencia`): 29/29 comparable party-vote pairs match the Congreso roll-call JSON
  (`evidence/vote-layer-spotcheck.md`).
- Fixes before scaling: one-call fetch/grep/quote helper `tools/kit.py` (STC→BOE id, fallo extraction, PDF grep,
  accent-insensitive quote finder), known traps added to the drafting prompt, parts batched by source family.

### Scaling (2026-11-11)
- Waves: wave 2 (3 agents: national TC rulings, Catalonia, PP/PSOE corruption) and wave 3 (6 agents: other parties'
  corruption, European bodies, electoral board and Tribunal de Cuentas, rights at regional level, RTVE/Telemadrid,
  ERE/Matas follow-up). Cost per event fell from ≈0.94 M input tokens (pilot) to ≈0.4-0.75 M with the kit.
- Coordinator decisions recorded in the part files (`_exclude` with reason): 2 duplicates of pilot items; STC
  137/2025 (art. 14 only); the 2021 Rule of Law description of LO 4/2021 and the 2025 description of RDL 5/2024
  (descriptive, no concern of the Commission's own); Vox's 2025 Tribunal de Cuentas sanction (under appeal at the
  Supreme Court); STC 48/2026 kept as a distinct act. ERC's role on STC 259/2015 set to «fuera del Gobierno» (it was
  not in the acting Govern). Not added after search: no firm conviction found for ERC, Bildu, BNG, UPN, Vox, Podemos
  or Sumar office holders for corruption; no firm political-violence or hate conviction of an office holder of any
  party (Isa Serra and Alberto Rodríguez held no office at the 2014 facts; Laura Borràs was not a member or on a list
  at the facts).
- Ledger after both reviews: 43 events (42 attributed to a current party; Palau/CDC shown as predecessor), 50
  counted attributions, 9 of 12 parties with at least one item; no item in `legitimidad`, `violencia`, `minorias`, `medios`.

### Post-scale review (decision rule fixed in 1.7: ≥13/15 verified, no attribution error)
- Random sample of 15 non-pilot events (seed 20261111, `evidence/review-scale/worklist_{a,b}.json`), two independent
  reviewers given only each item and its URLs: **13/15 verified, 0 attribution errors → pass.**
- The 2 failures were a coding error in the European-bodies brief: GRECO non-implementation findings were coded
  `justicia`, but the codebook puts «GRECO finds the government of the day did not implement its recommendations»
  under `contrapesos`. All three GRECO items (PSOE 2021, PSOE-Sumar 2024 and the unsampled PP 2017) were recoded to
  `contrapesos`; the 2024 item no longer describes the CGPJ deadlock as a government act (GRECO blames no one).
- Caveats from the reviewers, kept in the items: the PP's liability in the «caja B» ruling is subsidiary civil
  liability (art. 120 CP), within the `civil_liability_party` type; press-note dates are used where CENDOJ does not
  load; JEC sanctions are for breaching neutrality (art. 50.2 LOREG), coded `reglas` as use of public office in a
  campaign; the junts attribution of Junts pel Sí acts is `predecessor` and is not counted.
- Targeted review of three high-stakes items chosen by the coordinator (outside the random sample,
  `evidence/review-scale/targeted/`): Ábalos (TS, 22-6-2026, firm, ejecutoria opened 4-11-2026) **verified**; the UN
  communication OL ESP 3/2026 on «prioridad nacional» **failed** (its party attribution rested only on the Spanish
  Government's reply, and a concern about pacts not yet turned into policy is not an act under `minorias`), and STC
  138/2012 on Sortu **failed** (the amparo finds insufficient evidence, not a government attempt to exclude a rival).
  Both excluded. Keeping the UN item before the review was the coordinator's error; the review caught it.

### Symmetry check (same rule, comparable acts, different parties)

| Comparable acts | Item A | Item B | Result |
|---|---|---|---|
| Law or decree annulled for liberties (PP vs PSOE-UP government) | `stc-172-2020-seguridad-ciudadana` (libertades, 2) | `stc-148-2021-estado-alarma-1` (libertades, 2) | same |
| Demonstration banned by the Government delegation (PP vs PSOE-UP) | `stc-24-2015-subdelegacion-jaen-reunion` (libertades, 2) | `stc-164-2023-delegacion-madrid-8m` (libertades, 2) | same |
| Decree-law annulled under art. 86 CE (PP vs PSOE) | `stc-73-2017-amnistia-fiscal` (contrapesos, 2) | `stc-110-2021-cni-decreto-ley` (contrapesos, 2) | same |
| Decree-law annulled under art. 86 CE (PP vs PSOE) | `stc-61-2018-rdl-5-2013` (contrapesos, 2) | `stc-14-2020-rdl-7-2019` (contrapesos, 2) | same |
| Decree-law on the RTVE board (PP vs PSOE) | `stc-150-2017-rtve-rdl-15-2012` (contrapesos, 2) | `stc-134-2021-rtve-rdl-4-2018` (contrapesos, 2) | same |
| GRECO, recommendations not implemented (PP vs PSOE) | `greco-4-ronda-pp` (contrapesos, 1) | `greco-4-ronda-psoe` (contrapesos, 1) | same (after recoding) |
| Venice Commission on a bill of the governing group (PP vs PSOE) | `venice-2017-ley-tc` (removed in the full review: no finding that the law weakened the Constitutional Court) | `venice-2024-amnistia` (contrapesos, 1) | pair no longer comparable; the PP side has `venice-2021-ley-seguridad-ciudadana` (libertades, 1) |
| Electoral-board sanction of a head of government (PSOE vs PP) | `jec-2023-575-sanchez-rueda-prensa-consejo-europeo` (reglas, 2) | `jec-2021-390-ayuso-campana-logros` (reglas, 2) | same |
| Electoral-board sanction of a regional president (ERC vs Junts) | `jec-2023-576-aragones-movilidad-maresme` (reglas, 2) | `jec-2019-500-torra-lazos-amarillos` (reglas, 2) | same |
| Firm prison conviction of an office holder for corruption (PP vs PSOE) | `sts-507-2020-gurtel` (corrupcion, 3) | `sts-erea-749-2022` (corrupcion, 3) | same |
| Firm prison conviction of an office holder for corruption (PSOE vs PNV) | `sts-abalos-koldo` (corrupcion, 3) | `sts-de-miguel-pnv` (corrupcion, 3) | same |
| Firm Tribunal de Cuentas sanction of a party (PNV vs EH Bildu) | `tcu-2024-pnv-deber-colaboracion` (corrupcion, 2) | `tcu-2024-bildu-juntas-generales-2023-gasto-electoral` (corrupcion, 2) | same |
| Parliamentary procedure or control breached (PP Madrid amparo vs PP acting government) | `stc-22-2026-telemadrid-lectura-unica` (contrapesos, 2) | `stc-124-2018-gobierno-en-funciones` (contrapesos, 2) | same |

### Composite «riesgo»
Sensitivity test (7 weightings, rule in 1.6): 92 pairwise order reversals, so **no composite is published**; the page shows the test table and per-party profiles.

## 5. Census or selection (coordinator review, 2026-11-11)

Counts are comparable between parties only when they come from an official list read end to end. Each item now carries
`coverage` (`census` + family, or `selection`); the matrix numbers, the profiles' counts and the sensitivity test use
census items only; selection items are listed in the profiles and marked with a ring in the matrix, never counted; the
CSV carries `coverage` and `coverage_family`.

| Family | What | Listed | In scope | Events | Attributed (counted lineages) |
|---|---|---|---|---|---|
| `greco` | Informes de cumplimiento de GRECO sobre España | 11 | 9 | 9 | psoe 7 · podemos 3 · sumar 3 · pp 2 |
| `jec_sancion` | Sanciones de la Junta Electoral Central a partidos y miembros de Gobiernos | 92 | 28 | 28 | psoe 13 · pp 7 · erc 3 · junts 3 · bildu 1 · vox 1 |
| `rolr` | Capítulos de España del Informe sobre el Estado de Derecho | 12 | 2 | 2 | psoe 2 · podemos 2 |
| `tc_decreto_ley` | Decretos-leyes anulados por el Tribunal Constitucional (art. 86) | 91 | 22 | 22 | pp 14 · psoe 8 · podemos 3 |
| `tc_estado_alarma` | Estados de alarma ante el Tribunal Constitucional | 3 | 3 | 2 | psoe 2 · podemos 2 |
| `tcu_sancion` | Sanciones del Tribunal de Cuentas a partidos | 687 | 541 | 4 | bildu 1 · psoe 1 |
| `venecia` | Dictámenes de la Comisión de Venecia sobre España | 4 | 3 | 2 | psoe 1 · pp 1 |

| Family | What | Type | Items |
|---|---|---|---|
| `condenas_firmes` | Condenas firmes de cargos o del propio partido | selección, no censo | 10 listed, not counted |
| `tc_otras` | Otras sentencias del Tribunal Constitucional (leyes, actos autonómicos, amparos, conflictos) | selección, no censo | 11 listed, not counted |
| `otros_organos` | Otras conclusiones de órganos oficiales o internacionales | selección, no censo | 1 listed, not counted |

How each list was built (deterministic listing first, agents only to code):
- `tc_decreto_ley`: `tools/census_tc_decreto_ley.py` (BOE search, TC section, titles with «Real Decreto-ley», 2012-2026:
  267 documents → 91 rulings citing decree-law limits → fallo read → 22 annul on art. 86 grounds; the 8 annulments on
  competence or other grounds are out, each with its reason in `evidence/census-tc-decreto-ley.json`). Attribution by
  the decree-law's date. Rulings before 2012 are outside the window, so the Zapatero governments are only partly covered;
  recent decree-laws may still be pending (lag), stated on the page with annulments per decree-laws issued.
- `tc_estado_alarma`: same BOE search with «estado de alarma» (11 documents, 3 rulings on declarations, 2 annul).
- `jec_sancion`: JEC search (199 acuerdos; 92 in sanction cases on parties or members of national/regional governments;
  28 sanctions imposed by the JEC; 107 on mayors, councillors, officials, media out of scope). Fines imposed by lower
  boards and only upheld by the JEC are out by the scope wording. Two consellers who were independents in the
  single-party ERC Govern are attributed as acts of that Govern, not by membership.
- `tcu_sancion`: the four Tribunal de Cuentas sanction registers (687 resolutions, 541 sanctions, mostly local lists;
  5 attributable; CDC/PDeCAT/CiU as predecessors; PSC as PSOE «list»; Vox 2025 under appeal → pending; sanctions the
  Supreme Court annulled are out).
- `venecia`, `greco`: the official list pages answered 403/502 to scripted access; lists rebuilt from the documents
  themselves (GRECO from the history paragraphs of its 2024 and 2025 reports). Every GRECO compliance report is one event
  attributed to the government of the day by the codebook rule (GRECO addresses «the authorities»).
- `rolr`: 7 of 7 Spain chapters (2020-2026) read; 12 specific acts examined, 3 with the Commission's own concern and an
  attributable act; 31 system findings.

Lineage (coordinator point 2): STS 459/2019 now carries ERC (Junqueras, same) and Junts (Turull, «person»: PDeCAT
consejero at the facts, Junts secretary general today per junts.cat). Rull, Forn, Vila and Meritxell Borràs: PDeCAT
membership at the facts not proven by an official record, noted, not counted; Jordi Sànchez and Cuixart held no
public or party office. Pardons (2021) and the amnesty decisions (2024-2026) are in `status`; by rule 1.3 they do not
undo the finding. Other multi-defendant rulings in the ledger (Gürtel, «caja B», ERE, De Miguel, Palau, Ábalos) convict
office holders of a single party, so the gap does not recur.

Pending, not counted (coordinator point 3): 5 findings excluded only because not firm, same rule for every party
(`pending_findings.json` and the census files' `pending`); every other party searched with no result. Local-government
coverage is not exhaustive (CGPJ notes rarely name the party).

Review of what is new (rule: no attribution error): random 10 of 58 new items (52 events, 5 pending, the reworked
procés item; seed 20261112; `evidence/review-census/`): **10/10 verified, 0 attribution errors.** Caveats kept in the
verdicts: JEC acuerdos name the office, not the person or party (party from public record or parliament member pages);
the Venice 2021 opinion recommends changes to LO 4/2015 without finding a breach (coded `libertades`, severity 1,
borderline); one act_date is the date the act stopped.

Decree-law framing (coordinator point 5): tile and section now give decree-laws and laws per month by government
(1.99 and 1.72 a month since 2018; 0.80-1.79 and 2.40-5.85 before) and a counterfactual split: with only decree-laws at
today's pace the share would be 34 %, with only laws at today's pace 40 %; the fall in laws moves it more.

## 6. Full review coverage (coordinator, 2026-11-11, before deploy)

Every published event and pending item has been checked by an independent reviewer agent given only the item and its
URLs (date, attribution, coding, quote, firmeness). Items edited after an earlier review were checked again; only the
latest verdict counts (`REVIEW_ROUNDS` and `CHANGED_AFTER` in the exporter). Each item carries `review` in the JSON
(status, round, verdict file) and the CSV has a `review` column. Rounds: pilot, scale, targeted, census sample, full
(9 batches of about 8, `evidence/review-full/`), fix (`evidence/review-fix/`).

Full round, 69 items: 61 verified, 8 failed, 0 attribution errors. What was done with each failure:
- removed: `stc-156-2021-decreto-ley-1-2017` (annulled on equality and judicial-protection grounds, art. 86 met: out of
  the decree-law census, now 22), `venice-2017-ley-tc` (no finding that the law weakened the Constitutional Court),
  `rolr-2021-ley-seguridad-ciudadana` (concern on journalists, not a `medios` finding), `tcu-2024-pnv-deber-colaboracion`
  (fine for not cooperating with the audit, not irregular financing); pending `pp-granados-punica-pieza-7-2026` and
  `psoe-gallardo-diputacion-badajoz-2026` (no official record that they are not firm);
- corrected and re-checked: `greco-4-ronda-pp` (recommendation v «partly implemented», not «not implemented»),
  `jec-2020-12-sanchez-exhumacion-entrevista` (the fine covers only the 25-10-2019 interview);
- corrected without changing the checked facts: statuses of six electoral-board sanctions now record the Supreme
  Court's dismissals; STC 125/2016 title says the whole decree-law was annulled; Sumar lineage `same` everywhere.

Result: **reviewed 94 of 94** published items (91 events, 3 pending), 0 unreviewed, 0 failed, 0 attribution errors in the final state; enforced by `test_every_published_item_verified`. Sensitivity test on 69 census items: 85 reversals, no composite.

## 4. Status

- **Where we are:** `/visualizaciones/democracia/partidos/` built and checked locally (desktop and 390 px, console
  clean): consolidated matrix (parties × 9 indicators × governing / not governing, with exposure), 43-event ledger
  with a profile per party, vote layer (217 Congress votes, structural vs scrutiny, by role), decree-law series
  1979-2026 from BOE ELI (parity with the sibling crawl: 2,716 vs 2,714 norms), V-Party v2 benchmark, sensitivity
  test. Validator and 14 tests pass. Not deployed.
- **Where we are going:** a ledger that can be audited item by item and extended without changing the rules;
  roles that change inside the vote data (a legislature with a different governing party) so conviction can be
  separated from role.
- **What is next:** (1) vote layer for legislatures 10-12 (Rajoy governments) from Congreso open data, the only way
  to compare the same party in government and in opposition; (2) regional coverage beyond Catalonia, Madrid, Murcia
  and Andalusia (Constitutional Court rulings on regional laws, regional electoral boards); (3) urgency procedures
  per year (not done: no clean open series found in this sprint); (4) refresh V-Party when v3 is released.
