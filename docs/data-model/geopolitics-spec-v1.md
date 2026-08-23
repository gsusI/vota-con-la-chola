# Geopolitics contract v1

Status: frozen for the first real-data vertical slice (`2026-08-19`).

Authority: this document defines domain semantics. `ROADMAP.md` defines sequence;
`etl/load/sqlite_schema.sql` defines the executable SQLite schema; the ETL tracker
records operational status.

## 1. Purpose

Represent foreign-policy actions and explicit positions as evidence-backed facts.
The model covers treaties, international resolutions, sanctions, aid commitments,
defence agreements, international votes, counterpart states or organizations, and
time-scoped positions. It must not turn co-occurrence, diplomacy, a meeting, a title,
or a topic classifier into a claim about alignment, motive, influence, success, or
causal impact.

Every public fact must answer:

1. what official source said;
2. which actor acted, was addressed, or was named;
3. what legal or procedural stage was observed;
4. when it happened, at the precision supplied by the source;
5. which captured bytes and exact passage support it;
6. what remains unknown.

## 2. Hard invariants

- Only captured real official sources may create public facts.
- Synthetic, mock, placeholder, fabricated, or implicit fallback rows are forbidden.
- Names, offices, identifiers, affiliations, counterparties, and other personal
  information published by an official source are retained exactly. Publication
  hygiene removes secrets and workstation/session traces, never public identity.
- A government authorization is not treaty signature, ratification, entry into
  force, implementation, compliance, success, or impact.
- A meeting is not influence. A relationship is not alignment. A vote is not a
  permanent position outside the voted text and date.
- A sanction announcement is not proof that a target was legally liable unless the
  cited instrument says so. A listed target is not a criminal conviction.
- An aid pledge is not a budget appropriation, disbursement, delivery, receipt, or
  outcome. Each stage requires separate evidence.
- A defence agreement is not deployment, procurement, military action, operational
  command, or battlefield effect.
- Unknown, not published, not observed, not applicable, and not assessed are distinct
  machine-readable states.
- Corrections and later observations supersede; they do not erase prior snapshots.

## 3. Fact, classification, inference

### 3.1 Verifiable source facts

These may publish when an exact evidence anchor supports them:

- source title, source identifier, URL, publication date, captured timestamp and hash;
- named action, instrument, resolution, treaty, agreement, sanction measure, aid
  commitment, defence arrangement, or international vote;
- actor names and roles stated by the source;
- counterpart state, territory, international organization, public body, legal
  entity, or named person;
- official amount, currency, unit, vote choice, resolution number, treaty stage,
  effective date, expiry date, or implementation state explicitly stated;
- procedural actions such as approval, proposal, signature, referral, authorization,
  ratification, publication, entry into force, amendment, suspension, or termination;
- an explicit time-scoped position stated in the source.

### 3.2 Transparent derived classifications

These may publish only with `assignment_kind=derived_rule`, method/version, matched
text, and review state:

- action kind;
- bilateral/multilateral/global scope;
- topic or policy area;
- actor role normalization;
- instrument family;
- geography code mapped from an exact official label.

Derived classifications are navigation metadata. They are not findings about motive,
ideology, influence, alliance, threat, corruption, merit, blame, or effect.

### 3.3 Later analytical inferences

These are outside the first connector and require their own versioned assertion,
evidence set, counterevidence, method, confidence, review and publication gates:

- ideological or geopolitical alignment;
- actor influence over a decision;
- strategic intent or hidden motive;
- treaty compliance or breach;
- sanction effectiveness or evasion;
- aid effectiveness, diversion, conditionality effects, or recipient outcome;
- defence readiness, escalation, deterrence, or operational consequence;
- causal connection between an action and an economic, social, diplomatic, security,
  electoral, or conflict outcome;
- corruption, illegality, unethical conduct, capture, conflict of interest, or blame.

The v1 public artifact contains zero such assertions.

## 4. Canonical action kinds

| `action_kind` | Meaning | Minimum evidence |
| --- | --- | --- |
| `treaty_process` | step in making, changing, applying, suspending, or ending an international agreement | named instrument/parties plus explicit procedural verb |
| `international_resolution` | adoption, sponsorship, support, rejection, or implementation of a resolution | issuing forum, resolution identity or exact source passage, action date |
| `sanction_measure` | official imposition, amendment, renewal, suspension, lifting, or implementation of sanctions | legal instrument or official decision, target role, stage |
| `aid_commitment` | pledge, allocation, agreement, disbursement, delivery, receipt, or cancellation of aid | stage, provider, recipient/beneficiary when stated, amount/unit when stated |
| `defence_agreement` | official defence or security cooperation instrument/process | parties, procedural stage, exact source passage |
| `international_vote` | actor vote in an international body | body, event/resolution, choice and date |
| `diplomatic_action` | recognition, appointment, recall, formal protest, communique, or other explicit diplomatic act | actor, action, counterpart/subject and date |
| `other_foreign_policy_action` | source-backed foreign-policy action not covered above | exact evidence plus review-required subtype |

The action kind describes the observed event. It does not imply that the event had
legal effect beyond the explicit source wording.

## 5. Procedural and legal state

`action_status` is a closed vocabulary:

- `announced`
- `proposed`
- `approved`
- `authorized`
- `referred`
- `signed`
- `ratified`
- `published`
- `entered_into_force`
- `implemented`
- `amended`
- `renewed`
- `suspended`
- `terminated`
- `rejected`
- `abstained`
- `not_assessed`
- `unknown`

When one source sentence contains multiple observed steps, v1 may use a precise
compound `procedure_stage` while retaining a conservative `action_status`. The first
Moncloa slice uses `domestic_referral_and_authorization_to_consent`; it does not mark
the international agreement signed, ratified, in force, or implemented.

Separate fields prevent semantic collapse:

- `binding_state`: whether legal binding effect is explicitly established;
- `entry_into_force_state`: whether entry into force is explicitly established;
- `implementation_state`: whether implementation is explicitly established;
- `outcome_state`: whether a real-world outcome is observed;
- `position_state`: whether an actor position is explicit, derived, disputed, absent,
  or not assessed.

Default for an unobserved later stage: `not_assessed`, never `false`.

## 6. Actor roles and identity

Allowed action roles include:

- `acting_state`
- `approving_body`
- `authorizing_body`
- `publishing_body`
- `parliamentary_recipient`
- `counterparty_state`
- `counterparty_organization`
- `issuing_organization`
- `voting_actor`
- `sanctioning_actor`
- `sanction_target`
- `aid_provider`
- `aid_recipient`
- `implementing_body`
- `beneficiary`
- `named_official`
- `other_named_party`

`actor_kind` supports `person`, `state`, `territory`, `international_organization`,
`public_body`, `organization`, `legal_entity`, and `unknown`.

Identity rules:

1. Preserve `source_label` exactly.
2. A normalized actor link is optional and never replaces the source label.
3. Cross-source identity requires an official identifier or reviewed evidence.
4. Name similarity alone never merges states, organizations, offices, or people.
5. Historical state names and offices are time-scoped.
6. Officially published personal identity is retained in public output.
7. Missing actor identity is explicit; it does not suppress the action.

## 7. Time model

Store separately when available:

- `action_date`
- `published_at`
- `valid_from`
- `valid_to`
- `effective_from`
- `effective_to`
- `observed_at`
- `captured_at`

Every date carries precision: `instant`, `day`, `month`, `year`, `interval`, or
`unknown`. The date of a press reference must not be copied into treaty entry into
force, sanction effect, aid delivery, or a position validity interval.

Time-scoped positions require an explicit source date and subject. `valid_to` remains
null until a later source supersedes or closes the position.

## 8. Evidence and provenance

Minimum action evidence:

- `source_record_pk` and `source_id`;
- official `source_url`;
- captured object path, byte size, capture SHA-256 and capture time;
- source-record content SHA-256;
- exact quote and quote SHA-256;
- selector/page/section locator;
- evidence role and evidence state;
- extractor/classifier method and version.

An official web page reachable today is origin evidence. The checksum-pinned captured
bytes are replay evidence. Both are required for a release that claims reproducibility.

Evidence roles include `official_action`, `instrument_text`, `actor_identity`,
`procedure_stage`, `amount`, `vote_choice`, `position_statement`, `implementation`,
`correction`, and `counterevidence`.

## 9. Domain-specific requirements

### 9.1 Treaties and international agreements

Capture instrument name, parties, subject, procedure stage, official identifiers,
signature/ratification/publication/entry-into-force dates only when explicit, and links
between domestic authorization and later treaty observations. A domestic approval to
consent is not entry into force.

### 9.2 International resolutions and votes

Capture forum, resolution/event identifier, title, date, actor, vote choice, vote
meaning, roll-call source and corrections. `absent`, `not_voting`, `abstain`, and
`unknown` are distinct. A vote supports/rejects the exact proposition at that time;
it does not establish a permanent general position.

### 9.3 Sanctions

Capture legal instrument, sanctioning actor, target as source-labelled, measure kind,
scope, start/end dates, status and explicit basis. Do not publish guilt, criminality,
ownership, control, evasion or effectiveness without separate qualified evidence.

### 9.4 Aid commitments

Capture provider, recipient/beneficiary when stated, amount, currency/unit, purpose,
channel and stage. Keep `pledged`, `appropriated`, `contracted`, `disbursed`,
`delivered`, `received`, `spent`, `verified`, and `outcome_observed` separate.

### 9.5 Defence agreements

Capture parties, instrument, cooperation area, procedural stage, duration and official
text. Do not infer force posture, deployment, procurement, command, capability,
readiness, escalation, deterrence, or operational effect.

### 9.6 Time-scoped positions

Capture actor, exact subject, explicit position kind, quote, source date, valid interval
and supersession. Allowed kinds include `support`, `oppose`, `abstain`, `recognize`,
`not_recognize`, `condemn`, `endorse`, `reserve`, `commit`, and `other_explicit`.
The first connector emits no position rows because its source proves domestic
procedural actions, not a reusable position on a broader issue.

## 10. SQLite mapping

The additive v1 tables are:

- `geopolitical_actions`: one observed foreign-policy action;
- `geopolitical_action_actors`: source-labelled actor roles;
- `geopolitical_action_evidence`: exact evidence anchors and capture lineage;
- `geopolitical_action_topics`: transparent derived/source topics;
- `geopolitical_positions`: explicit time-scoped positions only;
- `geopolitical_position_evidence`: evidence for each position;
- `geopolitical_action_links`: typed links to agreements, votes, spending,
  implementation or later observations;
- `geopolitical_observations`: append-only observations of legal/implementation/
  outcome state over time.

All navigable tables have a single-column text primary key. FKs are declared. Source
labels remain alongside optional normalized IDs.

## 11. Stable identity and idempotence

Public IDs derive from canonical natural keys, not load order:

- action: source + source record + action kind + procedure stage + action date;
- actor edge: action + exact source label + role + ordinal;
- evidence: action/position + source record + selector + quote hash + ordinal;
- topic: action + topic key + method/version;
- position: source + actor label + subject + position kind + source date;
- observation: subject action/position + observation kind + observed time + source.

Replay of identical captured bytes must converge to identical IDs, rows, release ID,
and public artifact hash.

## 12. Corrections and conflicts

- Never overwrite a prior source claim silently.
- Store later observations append-only.
- Link `corrects`, `supersedes`, `implements`, `amends`, `renews`, `suspends`, or
  `terminates` with source evidence.
- Conflicting official sources remain visible with their timestamps and provenance.
- A current-state reducer must be deterministic, versioned, and reversible.
- Human review records decision, reviewer role, timestamp, rationale and evidence; it
  cannot alter captured bytes.

## 13. Million-scale physical contract

The ontology must work without redesign at `10M` actions, `100M` actor/evidence/link
rows, and `1M` source documents.

Ingest:

- immutable raw object store keyed by content hash;
- manifest-first capture inventory;
- bounded discovery and fetch queues;
- URL and content-hash deduplication before dispatch;
- host-aware concurrency, backoff and rate limits;
- at-least-once workers with deterministic exactly-once logical upserts;
- checkpoint by source partition and cursor;
- retry/dead-letter queues with explicit terminal reason;
- no per-row database lookups in the hot path.

Storage:

- partition analytical output by source, action kind and event year/month;
- target bounded Parquet files, normally 64-256 MiB compressed;
- keep SQLite as reproducible navigation/control artifact, not the only analytical
  serving format;
- maintain indexes on source/date/kind/status, action actor, evidence source record,
  counterpart label, topic and supersession link;
- publish manifests, row/file/byte counts, hashes and partition stats.

Publication:

- never ship million-row monolithic JSON;
- publish bounded pages or partitions with stable seek cursors;
- content-address immutable releases and expose a small latest pointer;
- preserve all official public identity fields;
- require durable origin, clean restore, checksum, row reconciliation, FK, integrity,
  real-only and publication-hygiene gates before scale promotion;
- expose completeness, freshness, observed stages and unknown-stage counts.

## 14. First real connector contract

Source: official La Moncloa Council of Ministers reference capture already stored at:

`etl/data/raw/moncloa_referencias/2026/02/16/moncloa_referencias_20260216T141256Z.json`

Pinned capture:

- bytes: `21,234`;
- SHA-256: `ab08b7dc09a46c890f055e95fdeac5e7d716a5023f8792f19ce440a239271ddf`;
- source records: `20`;
- qualifying foreign-policy records: exactly `2`, selected because exact official
  text names international counterparties and an international agreement procedure.

The two observed actions are:

1. `2026-01-13`: referral/authorization concerning the EU/Euratom/Spain agreement
   for the European Commission Joint Research Centre in Seville;
2. `2026-01-27`: referral/authorization concerning the Spain/Oman reciprocal visa
   exemption agreement for diplomatic, special and service passports.

Public claims allowed:

- the Council of Ministers approved the stated referral/authorization action;
- the exact counterpart labels and parliamentary recipient present in the source;
- the action date, source URL, exact quote and captured hashes.

Public claims forbidden without later evidence:

- signature, ratification, entry into force, implementation, usage or impact;
- broader diplomatic alignment or relationship quality;
- attendance, lobbying, influence, motive, corruption, legality or success;
- any position beyond the exact procedural action.

## 15. Quality gates

The first release fails closed unless:

1. capture bytes and SHA-256 match the pinned source;
2. exactly two source records qualify by deterministic source-text rules;
3. every action has one exact quote, official URL and source-record hash;
4. all named actors are substrings of source evidence, except the official publisher
   label which is explicitly source metadata;
5. no signed/ratified/in-force/implemented/outcome claim is emitted;
6. no geopolitical inference or position row is emitted;
7. public artifact and published artifact are byte-identical;
8. replay yields identical IDs, release ID and artifact hash;
9. `PRAGMA integrity_check=ok` and `PRAGMA foreign_key_check` has zero rows;
10. real-only, public-identity retention and publication-hygiene checks pass;
11. every public source URL is reachable or the obstruction is recorded with evidence;
12. UI caveats expose what the source proves and what remains unknown.

## 16. Current, target, next

Current: the agreements slice already contains two exact international-agreement
records, but there is no dedicated foreign-policy action contract or public view.

Target: an evidence graph linking source -> action -> actor -> procedure stage -> later
legal/implementation/outcome observations across treaties, resolutions, sanctions,
aid, defence and international votes at million-row scale.

Next after the first connector: add a second official source that supplies later legal
stage evidence (for example BOE treaty publication/entry-into-force metadata), then an
official international roll-call or sanctions source. Link only by reviewed identifiers
or exact instrument evidence; do not infer cross-source equivalence from title alone.
