# Spending API on Hetzner

Public endpoint: https://api.votaconlachola.org. The browser queries this API
directly; SQLite queries do not use Cloudflare Workers or D1.

The application reuses the existing `/v1/status`, `/v1/options`, `/v1/awards`
and `/v1/export` contract through a read-only SQLite adapter. One worker handles
queries with a five-second deadline and a queue capped at eight waiting requests.
The initial parallel page requests are queued; saturation returns JSON with 503, rather than spawning
unbounded workers on the shared server. Health/readiness remains on the HTTP
thread. Each blue/green container is limited to 0.5 CPU and 512 MiB by Ansible.

Build a reproducible bundle from a verified snapshot:

```sh
node scripts/build_hetzner_spending_bundle.mjs VERIFIED_DB NEW_BUNDLE_DIRECTORY
```

Deployment ownership: `first_hetzner/ansible/roles/vclc_spending`. Its target
wrapper and role are authoritative; do not duplicate SSH deployment logic here.
The first_hetzner Justfile provides the one-line deployment command:

```sh
just spending-api-deploy /path/to/bundle green
```

Choose the inactive slot. The recipe validates and applies candidate provisioning,
then validates and applies promotion. Both slots remain available for rollback.
A separate promote playbook can switch back to the healthy previous slot without
reimporting data or restarting Traefik. Read the role README before operating it.

The migration starts with the existing 47,397-result public snapshot, preserving
version, amounts and evidence. Expanding coverage remains separate work.
No ingestion, historical downloads, shared PostgreSQL/Redis changes or host cleanup
are part of this service. Immutable bundles contain only reviewed public data and
application files. Keep old snapshots until replacement and rollback are verified.

## Candidate date semantics (not yet promoted)

`date_scope=all` (default) returns dated results inside `start`/`end` plus
results with unresolved dates. `date_scope=dated` excludes unresolved dates.
`date_scope=unresolved` selects only unresolved dates; the calendar does not
restrict those results. Authority, supplier and text filters apply in every mode.
Responses expose `undated_count` for the selected result set. Pagination and CSV
use the same selection, and CSV retains `decision_date_source` and
`decision_date_status`. Unknown dates are JSON null, never guessed years.

Promotion requires the frontend to explain these modes and use the matching
immutable capture release. The minimum literal date is not a coverage claim;
the candidate contains a literal 1925 date in a 2025 contract source.
