# Obstruction tracker MVP

Date: `2026-08-19`

Status: `published and live-verified`

## Where we are now

The static route `/obstruction-tracker/` and the versioned feed `/obstruction-tracker/data/obstructions.json` publish the complete current obstruction register from the canonical Name & Shame log and source-status snapshot.

Current real cut:

- `27` open incidents across `14` desired sources and `10` institutions;
- `116` incident evidence references expanded into `119` concrete source files;
- `1,107` currently unfilled target records across affected desired sources;
- `7` validated real corpora, including `3` lanes above one million real rows;
- `4` explicit scale/promotion gaps;
- `0` synthetic, mock, placeholder, or invented records.

The page distinguishes current source health from historical or still-reproducible obstruction. A source may be healthy now while its append-only incident remains open. An incident proves an observed technical access failure; it does not by itself prove illegality, intent, corruption, or motive.

## Public evidence contract

The exporter creates a bounded JSON feed plus a public evidence bundle:

- every local evidence reference resolves to an internal static URL;
- every bundled file records repo-relative source path, original bytes and SHA-256, public bytes and SHA-256, and whether sanitation occurred;
- `112` files are byte-equivalent public copies;
- `7` files redact only credentials/private-session/workstation traces;
- official public information, including public-domain personal information, is retained;
- bundle output uses inert `.txt` files, preventing captured HTML from executing in the public origin;
- the feed is atomic, validates under a `5 MB` budget, and currently weighs `411,620` bytes.

Machine-readable policy:

- `data_origin=official_real_records_only`;
- `synthetic_or_mock_records=forbidden`;
- `public_domain_personal_information=retained`.

## Verification

Commands:

```bash
just obstruction-tracker-export
python3 -m unittest tests.test_obstruction_tracker_snapshot
node --test tests/test_obstruction_tracker_ui_contract.js
just site-build
node scripts/audit_public_routes.js --base-url http://127.0.0.1:8765
node scripts/audit_public_routes.js --base-url https://votaconlachola.org --json-out docs/etl/sprints/OBSTRUCTION-TRACKER-20260819/evidence/live-route-audit.json
```

Results:

- feed and evidence validator: `status=ok`, `0` errors;
- obstruction tests: `6/6` pass;
- static build: `1,427/1,427` pages generated;
- current live public route audit: `43` routes, `47` critical assets and `119` evidence files checked; `0` failures;
- real-only gate: `124,539` files scanned, `0` findings;
- publication hygiene: `16,699` files scanned, `0` findings;
- desktop and `390x844` browser inspection: route, navigation, responsive grid and evidence hierarchy render correctly.

Publication:

- live route: `https://votaconlachola.org/obstruction-tracker/`;
- `gh-pages` commit: `bd42c16ece`;
- one first-deploy CRLF/hash mismatch was detected by the live audit, corrected in the exporter through canonical LF bytes, rebuilt, republished and verified with `119/119` evidence hashes passing.
- a later data-only sync used deletion semantics against a directory that also contains generated route HTML; the commit summary exposed the removal immediately, a full gated build restored the route, and the final live audit passes. Future obstruction publication uses the full build/publish workflow recorded in the project knowledge base.

Evidence:

- `docs/etl/sprints/OBSTRUCTION-TRACKER-20260819/evidence/obstruction-tracker-validation.json`;
- `docs/etl/sprints/OBSTRUCTION-TRACKER-20260819/evidence/local-route-audit.json`;
- `docs/etl/sprints/OBSTRUCTION-TRACKER-20260819/evidence/live-route-audit.json`;
- `ui/site/public/obstruction-tracker/evidence/manifest.json`.

## Where we are going

This closes the controlled MVP for roadmap item `W9-001`. It does not close access incidents, source completeness, scale promotion, or institution-level escalation. The next product layer is the transparency dashboard: combine this obstruction feed with snapshot version, latest release, freshness, recent changes and correction history without duplicating the canonical tracker.

## What is next

1. Build the transparency dashboard from this feed and existing release manifests.
2. Add resolved-incident examples only when the canonical append-only log records real resolution evidence.
3. Add institution-level official escalation/contact state to the canonical log, then expose it without inferring motive.
4. Measure incident age, response latency, source recovery time and recurring-obstruction rate from real history.
