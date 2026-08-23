# Time-aware actor graph and entity resolution v1

Status: implementation contract, 2026-08-20

## 1. Purpose

Answer “who did what, in which capacity, for whom, and when?” without collapsing
different people or organizations because their labels look alike.

The graph is an accountability index over real official evidence. It is not a
social network, a people-search product, or a license to guess identities.

This contract covers:

- people and candidate occurrences;
- parties, institutions, parliamentary groups, public bodies, companies and
  other organizations;
- offices and roles;
- mandates, candidacies, election outcomes, memberships and contextual actor
  roles in spending, agreements, meetings, promises and geopolitical actions;
- aliases and official identifiers;
- coalition membership;
- organization renames, mergers, splits and supersession;
- resolution decisions, conflicts, review and correction history.

All public-domain personal information in an official source remains visible and
traceable. Publication hygiene removes only secrets, credentials, private
session state, workstation traces and information not obtained from a public
source.

## 2. Non-negotiable truth rules

1. No synthetic, mock, placeholder, generated-person or fallback records.
2. A name is evidence of a label, not proof of identity equivalence.
3. Source-scoped occurrences remain separate unless an official identifier or a
   reviewed decision proves the link.
4. Party, parliamentary group, coalition and institution are different actor
   types.
5. Office, person and mandate are different entities or facts.
6. Candidate, elected representative and office holder are different states.
7. Supplier, beneficiary, contracting authority, signatory and lobbyist are
   contextual roles, not permanent identity classes.
8. Absence from a later snapshot is not deletion. It is an observed absence
   version.
9. Merge, split, conflict and correction events are append-only. Old public
   evidence remains reconstructable.
10. Every relationship version has source identity, observation time and an
    evidence state. Missing exact record evidence stays explicit.
11. Identity confidence is not political confidence, integrity risk or guilt.
12. No graph path implies causation, influence, merit, blame or corruption.

## 3. Identity layers

### 3.1 Source occurrence

Smallest safe identity. Keyed by source plus official record or stable semantic
ordinal. It never crosses a source boundary by name.

Examples:

- one BOE candidate row;
- one Senate member record;
- one PLACSP counterparty with its published NIF;
- one named agreement party;
- one organization appearing in a geopolitical action.

### 3.2 Source-scoped actor

Groups occurrences only inside the same source when the source contract supplies
a stable key. Existing normalized `person_id` values are projected as
source-scoped, not treated as externally adjudicated identity.

Stable public ID:

```text
urn:vclc:actor:<sha256(actor-kind | source-id | stable-source-key)>
```

The full unhashed key remains in `stable_source_key`; the hash does not hide the
official identifier or public label.

### 3.3 Resolved actor

Cross-source actor created only by:

- an exact official identifier with compatible namespace and actor type; or
- a completed reviewed match with immutable evidence and reviewer identity.

The current MVP creates no cross-source resolved actor. It preserves existing
registries as source-scoped inputs and reports this limitation.

### 3.4 Resolution decision

Append-only assertion from a source actor to a candidate canonical actor.

Allowed outcomes:

- `source_scoped`: no cross-source claim;
- `exact_identifier_match`: compatible official identifier match;
- `reviewed_match`: human-adjudicated match;
- `reviewed_no_match`: human-adjudicated separation;
- `conflict`: evidence disagrees;
- `unresolved`: insufficient evidence;
- `superseded`: a later decision replaces this version.

Every new decision may point to `supersedes_decision_id`. It never mutates the
previous decision.

## 4. Time model

Four clocks remain separate:

| Clock | Meaning | Example |
| --- | --- | --- |
| valid time | when a role or relationship applied in the world | mandate start/end |
| source time | when the source says the record applied or was published | election date |
| observation time | when this project captured it | snapshot date |
| system time | when this project materialized the graph version | release timestamp |

Rules:

- open `valid_to` means unknown or still open, not infinite certainty;
- actor-node validity describes the actor's own existence or legal identity. A
  mandate, candidacy, meeting, award or agreement date belongs only to that
  relationship and must never become the person's or organization's lifespan;
- `is_present=0` records an observed disappearance and preserves prior versions;
- date precision is explicit in attributes when only year/month is known;
- relationships that lack start/end remain temporally unknown;
- no current-office label is back-projected into historical events.

## 5. Graph entities

### 5.1 `actor_graph_nodes`

Stable actor identity shell.

Required fields:

- `actor_id`;
- `actor_kind`: `person`, `organization`, `office`, `collective`, `unknown`;
- `actor_subtype` such as `party`, `institution`, `parliamentary_group`,
  `public_body`, `company`, `state` or `international_organization`;
- `identity_scope`: `source_scoped` or `resolved`;
- `source_scope_id`;
- `stable_source_key`;
- first release and creation time.

### 5.2 `actor_graph_node_versions`

Append-only labels and states. Preserve exact official labels. Normalized labels
may assist search but never replace source text.

### 5.3 Identifier and alias versions

Identifiers store namespace and exact public value. Aliases store exact text and
normalized search form. Both include valid/observation time and provenance.

Identifier matching is namespace-specific. `NIF:A...` must never match a
parliamentary ID with the same bytes.

### 5.4 Relationship identities and versions

`actor_graph_relationships` is the stable shell.
`actor_graph_relationship_versions` records time, presence, role and evidence.

Initial relationship types:

- `holds_role_at`;
- `affiliated_with_party`;
- `candidate_for`;
- `effective_candidate_for`;
- `elected_in`;
- `member_of_parliamentary_group`;
- `member_of_organization`;
- `acts_in_spending_item`;
- `party_to_agreement`;
- `participates_in_meeting`;
- `acts_in_geopolitical_action`;
- `publishes_manifesto`;
- `member_of_coalition`;
- `predecessor_of`;
- `successor_of`.

Context objects such as a mandate, election, spending item or agreement stay in
`context_kind` + `context_id`. They are not silently converted into actors.

### 5.5 Organization change events

Append-only event types:

- `renamed`;
- `merged_into`;
- `split_into`;
- `absorbed_by`;
- `superseded_by`;
- `founded`;
- `dissolved`.

An event requires effective date or explicit unknown, all subject/object actors,
source evidence and observation time. The first MVP emits zero such events
because no reviewed official change evidence is in its selected inputs.

## 6. Evidence contract

Each relationship version receives one or more evidence rows:

- `source_id` and source record ID when present;
- exact public source URL;
- content SHA-256 when captured;
- locator: table + official/stable row identity or document paragraph;
- exact quote where source text exists and is needed;
- retrieval/observation time;
- evidence state: `exact_record`, `exact_document`, `source_default`,
  `normalized_registry`, or `missing`.

`source_default` is weaker than `exact_record` and remains visible. It is still a
real official source, but not a record-specific permalink.

## 7. Current real projection

The first implementation reads the existing real SQLite registry and the
checksum-pinned public vertical slices produced by promises, spending,
agreements and geopolitics. Indicators are read as release context but create no
actor relationship because an outcome series does not identify a responsible
actor.

Main-registry facts projected:

- mandates;
- mandate-time party affiliations;
- BOE base candidate occurrences;
- reviewed effective BOE candidate state;
- Infoelectoral elected outcomes;
- parliamentary-group memberships;
- organization memberships;
- source-scoped identifiers and aliases;
- parties, institutions, parliamentary groups and available office records.

Vertical-slice facts projected:

- PLACSP actor roles;
- Moncloa agreement parties;
- Moncloa meeting participant roles, including explicit `not_claimed`
  attendance state;
- Moncloa geopolitical action actors;
- manifesto publisher party.

The release must reconcile exact selected-row counts with its source databases,
run twice without changing IDs/counts, pass SQLite FK/integrity checks and retain
every selected official public label.

## 8. Resolution decision matrix

| Evidence | Automatic action | Public state |
| --- | --- | --- |
| same source + same stable official record key | group | `source_scoped` |
| same source + same compatible official identifier | group | `source_scoped` |
| different sources + same official identifier, compatible types | propose; merge only under enabled exact-ID policy | `exact_identifier_match` |
| exact name only | never merge | `unresolved` |
| normalized name + same party/territory | never merge | `unresolved` |
| shared birth date without identifier | never merge | `unresolved` |
| reviewed evidence supports same actor | append decision | `reviewed_match` |
| reviewed evidence rejects match | append decision | `reviewed_no_match` |
| identifiers disagree | never merge; queue | `conflict` |

No fuzzy threshold may publish a merge by itself.

## 9. Failure modes

### Homonyms

Same name, different people. Mitigation: source scoping; no name-only merge.

### Name changes and spelling variation

Aliases may indicate one actor, but do not prove it. Preserve exact aliases and
route ambiguous cross-source links to review.

### Party vs parliamentary group

Similar labels often refer to different legal/political entities. Keep distinct
types and connect only with time-scoped evidence.

### Coalitions

A coalition is not a permanent alias for every member party. Model coalition and
membership intervals explicitly.

### Organization succession

Rename, merger and split are events, not destructive updates. Keep predecessor
and successor nodes plus event evidence.

### Reused official identifiers

Namespace, issuer, validity dates and actor type must be compatible. Otherwise
record conflict.

### Missing dates

Unknown time stays null/unknown. Never infer a term from the crawl date.

### Stale snapshots

A later absence creates a new presence version. Never delete the earlier actor or
relationship.

### Legacy normalized identities

Existing `person_id` and `party_id` mappings are useful input but do not prove
cross-source precision/recall. The MVP re-scopes them by source and does not call
them externally resolved.

### Derived vertical slices

Geopolitics may be derived from an agreement source. Shared labels do not justify
new merges. Lineage to the originating record remains explicit.

### Reused source IDs with different metadata

Two input databases may reuse one `source_id` for different upstream contracts.
The graph must never keep whichever definition happened to load first. It
reconstructs the full source catalog before writing rows:

- identical definitions keep the original source ID;
- conflicting definitions are all retained under deterministic
  `<source-id>@<input-database-key>` graph IDs;
- `actor_graph_source_mappings` records every upstream-to-graph mapping, its
  canonical metadata hash and the reason for the mapping;
- every actor, identifier, alias, relationship and evidence row uses the mapped
  graph source ID.

This namespacing disambiguates provenance. It is not an actor merge or a rewrite
of the upstream source.

### Relationship identity before cross-source actor resolution

The MVP has only source-scoped actors, so the source is already embedded in the
subject/object actor IDs. Before enabling cross-source resolved actors, the
stable relationship-shell rule must be promoted and tested with corroborating
and conflicting multi-source evidence. A second source must append evidence or
an explicitly separate version; it must never collide silently or create a
duplicate merely because an optional object is null. This is a hard gate for
the reviewed cross-source phase, not an inferred behavior of this MVP.

## 10. Million-scale physical design

Target: `10M` actor nodes/versions, `100M+` relationship versions and `1B`
evidence edges without ontology rewrite.

- content-addressed raw capture outside row storage;
- immutable release manifest before publication;
- integer/hashed partition keys, never full-label partitions;
- partitions by release, source, actor kind, relationship type and bounded time;
- Parquet Zstandard with row groups near `25k` and files below `100k` rows;
- SQLite batch size `5k..25k`, WAL bounded and explicit checkpoints;
- keyset scans, never deep offsets;
- deduplicated source URLs and content hashes;
- append-only versions; no mass rewrite for a new snapshot;
- sibling temporary files plus atomic replacement for standalone snapshot
  builds, so interruption cannot destroy the last validated artifact;
- unchanged partition reuse by verified hardlink/copy;
- review queues partitioned by source, conflict type and deterministic task ID;
- bounded browser JSON under `5 MB`; full graph via paginated/sharded API or
  Parquet, not one giant JSON;
- indices on actor/source key, identifier namespace/value, relationship
  subject/object/type/time, release and supersession;
- clean-room restore, source/output reconciliation and correction workflow before
  promotion.

## 11. Quality gates

Release fails closed when any condition fails:

- source semantic hash mismatch;
- input release/hash mismatch;
- selected source count differs from graph count;
- duplicate stable actor or relationship ID;
- missing, incomplete or precedence-selected source mapping when input source
  metadata conflicts;
- contextual relationship dates copied into actor-node lifespan;
- dangling actor, relationship, release or supersession FK;
- invalid interval with known `valid_to < valid_from`;
- missing source ID or observation time;
- name-only cross-source merge;
- official identifier or label removed from selected public evidence;
- synthetic/mock/fallback marker;
- output/public byte mismatch;
- second replay changes IDs, counts or release identity;
- unbounded public artifact;
- secret, session or workstation trace in public output.

## 12. Promotion ladder

1. `MVP`: current real projection, source-scoped, full reconciliation.
2. `R0`: reviewed exact-identifier policy and conflict queue.
3. `R1`: representative `100k` actor facts across national, regional,
   municipal and European scopes; adjudicated gold set.
4. `R2`: `1M+` actor/candidate/mandate/appointment facts; measured precision,
   recall and unresolved rates; durable origin and clean restore.
5. `R3`: `100M+` relationship versions; bounded API, independent replica,
   correction SLO and two-person review for identity policy changes.

The first release does not claim R0-R3.

## 13. Next gates

1. Publish the reconciled source-scoped graph MVP and public evidence view.
2. Build a stratified real adjudication packet; no blank decisions are filled.
3. Measure precision/recall by source and name/identifier pattern.
4. Add official coalition formation/dissolution evidence.
5. Add official appointments/dismissals and office succession.
6. Append a second snapshot and prove present/absent/superseded behavior.
7. Partition and publish the full graph to durable origin.
8. Reach one million representative actor facts and clean-room restore.
