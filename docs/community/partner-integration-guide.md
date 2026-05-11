# Partner integration guide

Purpose: help external teams add public datasets without needing private repo knowledge.

Before starting:

- read `docs/dev/quickstart.md`;
- read `CONTRIBUTING.md`;
- for new sources, follow `docs/etl/source-onboarding.md`;
- check `/explorer-sources/` for current `available`, `blocked`, `stale`, and `missing` state.

## Integration paths

### Add a source

Use this for a new public dataset.

```bash
just add-source <source_id> name="..." scope="..." url="..." format=json
```

Then edit only the generated sample, parser, test, and source doc. Default mode is `source_records_only`, so the first PR only needs traceable records. Domain normalization can follow later.

### Add a domain backfill

Use this when the raw source already lands and needs structured tables or public artifacts.

Expected contract:

- input rows link to `source_records`,
- output rows keep `source_id` and `source_record_pk`,
- no destructive migration,
- `PRAGMA foreign_key_check` clean,
- tracker or docs state where we are now, where we are going, and next step.

### Add a public surface

Use this when the dataset should become visible to citizens or analysts.

Expected contract:

- static JSON stays bounded,
- UI states show `unknown/no_signal` explicitly,
- every claim links to source or drill-down,
- `just privacy-check-public-artifacts` passes before publish.

## Required checks

Run before PR:

```bash
just etl-contributor-gates
```

If a gate cannot run, document exact command, error, and blocker in the PR.

## GitHub taxonomy

Use the existing project taxonomy instead of inventing new labels:

- data source connector: `area:etl`, `type:data-source`;
- docs or guide work: `area:docs`;
- public UI/catalog work: `area:ui`;
- legal/transparency blocker: `area:legal`;
- governance/steward process: `area:governance`;
- reproducibility missing: `status:needs-repro`;
- upstream or credential block: `status:blocked`;
- maintainer input needed: `status:needs-maintainer`;
- review-ready work: `status:ready-for-review`.

Default milestone for starter source work: `H2 - plataforma contributiva`.

## Publication contract

Public distribution is:

- Hugging Face dataset snapshots for data reuse,
- Cloudflare Pages static routes for public browsing,
- source catalog for coverage and blockers,
- tracker for operational truth.

No source is `DONE` until current live evidence supports it. Historical evidence can stay in notes, but tracker status must reflect current run truth.
