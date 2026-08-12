# Integrity signal publication policy

Status: `v1`

## Purpose

Project may detect unusual public spending, procurement, appointments, votes,
implementation gaps, or outcome patterns. These are review signals. They are
not findings of corruption, illegality, unethical intent, or personal guilt.

## Public state model

| State | Meaning | Public language |
|---|---|---|
| `observed_fact` | Direct value from primary evidence | State fact and source |
| `review_signal` | Deterministic rule found an unusual pattern | "Signal for review" |
| `corroborated_risk` | Two independent evidence paths support material concern | "Corroborated risk indicator" |
| `official_finding` | Court, audit, regulator, or control body issued a finding | Quote scope and status |
| `rejected` | Review found false positive, bad join, stale data, or missing context | Publish rejection reason |
| `superseded` | New evidence changed prior state | Link old and new snapshots |

Only an authoritative final source may support legal labels. Even then, product
must attribute the label to that source and preserve appeal or finality status.

## Required lineage

Every public signal must contain:

- stable `signal_id`, rule id, and rule version;
- snapshot date and generated timestamp;
- source ids, record ids, URLs, and content hashes;
- exact observed values and comparison baseline;
- jurisdiction, period, entity-resolution method, and confidence;
- counterevidence or missing-evidence fields;
- reviewer state, reviewer independence class, and review timestamps;
- correction or dispute URL;
- explicit `causal_impact_not_claimed` and `merit_blame_not_scored` flags unless
  a separately reviewed contract authorizes narrower wording.

## Publication gates

`review_signal` requires all of:

1. deterministic reproduction from a versioned snapshot;
2. primary-source lineage for every material value;
3. passed identity, date-window, currency or unit, deduplication, and jurisdiction checks;
4. minimum cohort or support size declared by rule;
5. uncertainty and alternative explanations rendered beside signal;
6. every personal field published by the authoritative public source is retained with provenance; secrets and non-public session/workstation data are excluded;
7. machine and human wording passes that avoid guilt, intent, merit, or blame.

`corroborated_risk` additionally requires:

1. two independent evidence paths, not mirrors of same upstream record;
2. two human reviews, including one reviewer independent from author or maintainer;
3. documented counterevidence search;
4. right-of-reply window for a named living person or small identifiable entity;
5. maintainer approval and a versioned publication decision.

No model-generated label can satisfy human-review gates. Models may triage,
cluster, summarize, or draft; their origin stays visible.

## High-risk failure checks

Block publication when any applies:

- person or entity match is ambiguous;
- evidence date falls outside actor mandate or responsibility window;
- nominal and inflation-adjusted amounts are mixed;
- award, tender, budget allocation, obligation, payment, and outcome are conflated;
- related notices or lots are double-counted;
- comparison cohort was selected after observing target;
- missing data is interpreted as zero or absence of action;
- source is stale, blocked, incomplete, or materially revised without warning;
- rule targets protected traits, political affiliation itself, or lawful speech;
- wording can reasonably be read as an allegation unsupported by official finding.

## Correction and appeal

- Public correction requests use `.github/ISSUE_TEMPLATE/data_correction.yml`.
- A plausible identity, source, provenance, publication-hygiene, or attribution defect suspends affected
  strong wording while reviewed.
- A correction produces a new immutable snapshot; old artifact remains linked as
  `superseded` or `rejected`, never silently rewritten.
- Decision records include request, evidence, reviewer, outcome, timestamps, and
  changed artifact hashes.
- Target response: acknowledge in 3 working days, triage in 7, update every 14.

## Review quality at scale

Track per rule and reviewer cohort:

- queue age p50 or p95 and review throughput;
- agreement and arbitration rate;
- false-positive and rejection rate;
- correction rate after publication;
- identity, date, unit, and dedup failure counts;
- share with independent review and counterevidence;
- share of named-party signals receiving right-of-reply handling;
- stale or open signal backlog.

Reviewer volume never overrides evidence quality. Sample at least 1 percent of
auto-triaged negatives and 100 percent of public positive signals. Recalibrate
rules when false-positive or correction thresholds breach their versioned SLO.

## Implementation contract

- Durable state and audit tables: `integrity_signals`, `integrity_signal_evidence`, `integrity_signal_reviews`, `integrity_signal_transitions`, `integrity_signal_responses`, and `integrity_signal_corrections`.
- State/publication gates: `publicdata_evidence/integrity_signals.py`.
- First bounded detector: `scripts/detect_procurement_integrity_signals.py`. It produces internal `review_signal` rows only and describes a configured analytical threshold, never a legal threshold or corruption finding.
- Public export: `scripts/export_public_integrity_signals.py`; it excludes internal, rejected, superseded, and unapproved signals.
- Fixture drill: `tests/test_integrity_signal_workflow.py` proves machine rejection, independent-source corroboration, right-of-reply, false-positive rejection, approval, correction, and withdrawal paths.

This contract does not satisfy the two-human-review rule by itself. Reviewer calibration, independence, adjudication, and a supervised real-data pilot remain required before any `corroborated_risk` publication.

## Safety boundary

Project exists to improve institutions through inspectable evidence. It must not
become a harassment list, partisan scoring engine, rumor amplifier, or automated
accusation system.
