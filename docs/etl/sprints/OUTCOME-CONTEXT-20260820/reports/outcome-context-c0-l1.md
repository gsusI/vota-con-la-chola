# Outcome context C0/L1 — local validation closeout

Status: `LOCAL VALIDATED — C1 PUBLIC V3 PACKAGE/BUILD PASS; C2A+C2B PHYSICAL PASS; REMOTE PUBLICATION/ORIGIN PENDING`

Date: `2026-08-23`

## Where we are

- one real preproduction candidate over `20` initiative-linked Senate votes;
- `25` exact Eurostat observations in the selected real series;
- `264` named public participants retained with raw locators and actor refs;
- `1` internal link/version, `3` observation refs and `7` evidence rows;
- `0` human reviews, releases, memberships, validated links or publications;
- `2,973` independent checks pass with zero failures;
- bundle semantic SHA-256 `2e04efb803623a5d96b6a2e7f6eb2464679e5014b02003cc1df175c16afcf16a`;
- artifact-set SHA-256 `22f43918a8a6e54a3a8549f2f809abfcf98c3d04ef82dc37f634cd0fd71a980a`;
- deterministic public projection of the `2,973`-check independent validation SHA-256 `8e97863250312acba99be9d8952febb5c5eae68993cc3fa036d6d30a4561bc8b`; the current raw operational validation report remains local because physical database hashes and run telemetry are not semantic release identity;
- actor lookup uses the physical composite release/source index;
- local publication-form status `policy_outcomes_public_status_v3` is `4,078` bytes, SHA-256 `226dfdf943434607b633dfebfaf8475f7546bf6a4e25ee5426ba34e6f4249f87`. It discloses one pending methodological candidate, zero validated links and zero association, effect, merit, blame, success/failure or corruption claims;
- content-addressed package `5ac0187857fd1436cca31616e4072bb13812281f01983b1c4fae6598a803be48` binds a `9,496`-byte manifest / SHA-256 `2bfe3f2d0850c6775349b763239300f50eb199a04167026798764bb20ff83d07` and `17` exact assets. The assets include the complete `20`-row action universe (`17,309` bytes / `1a986011...`), one eligible series (`483` bytes / `37be1a07...`), deterministic validation and materialization evidence projections, exact raw and semantic evidence, SQLite, and the pinned Ed25519 allowed-signers trust root;
- all `264` official participant names remain in byte-identical public semantic evidence. None is removed or pseudonymized. Candidate detail is absent from the small status because no association passed review, not because identity was stripped; the status links the complete evidence package;
- the page hashes all `17` assets in the browser and fails closed on absent, changed, redirected, extra, or unsafe-path evidence. The fresh full local build passes `1,435` pages; independent route audit passes `46` routes / `50` assets / `119` obstruction-evidence objects; real-only and publication-hygiene gates pass `124,679` and `17,072` files respectively;
- the package manifest is explicitly unsigned. Export performs a real Ed25519 verification of the separately signed scale origin against the pinned signer identity, fingerprint and public trust root; that signature explicitly does not attest this outcome package;
- `contract_date=2026-08-20T00:00:00Z` is deterministic contractual metadata, not materialization or validation time. Action snapshot is `2026-02-12`; Eurostat snapshot is `2026-08-11`, with upstream update `2026-02-10T11:00:00+0100` and baseline release state;
- C2A physically processes all `33,726` pinned real pairs and passes `111/111` independent checks with semantic root `0fc7c257...`;
- C2B physically processes all `2,865,602` pinned real pairs across `458` actions, `6,400` annual series, `89` geographies and `79,722` observations. Its `3,587,743,744`-byte SQLite shard has SHA-256 `04c8265154bf6659971b732db135f07fe6db0d45a0482d775bb30c15bde57680`; `107/107` checks pass with semantic root `e9fecdb8...`, zero retries/dead letters, committed interruption/resume, config-drift rejection, append-only enforcement, adversarial clone failures and byte-identical local restore;
- C2A/C2B rows are internal L0 discovery pairs with `publication_eligible_rows=0`; they create no association, effect, causal, merit, blame, ranking or corruption claim. Durable remote origin and public release remain false.

The vote-specific original XML bytes are absent from the current snapshot. The normalized official record remains hashed and traceable; the original-byte gap stays explicit.

Actor linkage has a second provenance gap: all `264` actor refs have `actor_source_content_sha256=null` and the same generic legislature-15 catalog URL. Exact names, seats, groups and ballots remain protected by the vote-record SHA and raw locators. The actor edge is release/closure-derived until a pinned actor-source capture or explicit derived-link state exists.

## Where we are going

The lane now has a bounded C1 candidate proof and accepted sparse, resumable, partitioned C2A/C2B physical planners. It must move those artifacts into durable multi-shard operation and a real review plane. Volume never substitutes for evidence authority. Candidate, human-review, validated and published counts remain separate at every scale. Human work moves to a generated candidate queue and small append-only decisions keyed to immutable version IDs; evidence packets stay bounded and resolve full official public identity by reference.

## What is next

1. Publish the passed v3 build and verify page, status, manifest, every evidence asset hash, source links, valid branch and desktop/mobile browser state live.
2. Recover the original vote XML bytes from a verifiable official capture, or preserve the gap as blocking evidence.
3. Pin actor-source capture by checksum or mark the actor edge derived; pass actor origin/restore and bounded vote/text provenance before L2.
4. Obtain an identified real human semantic/geographic review before any L2 release.
5. Add multi-shard/Parquet outputs and unchanged-partition reuse while preserving accepted semantic roots and fail-closed shard checks.
6. Add decision-only review tasks, leases, reviewer identity, calibration, dual review/adjudication, queue-age/throughput, appeals and correction SLA.
7. Move the accepted local C2A/C2B shards and manifests to an authorized immutable origin; prove isolated clean restore/rollback and revalidate exact roots before any promotion.

## Reproduction

```bash
just outcome-context-check
just outcome-context-pair-plan-check
just outcome-context-pair-plan-c2b-check
just cloudflare-pages-build
just outcome-context-built-check
node scripts/audit_public_routes.js --base-url https://votaconlachola.org
```

Evidence:

- `docs/method/outcome-linking-v1.md`
- `docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/outcome-context-materialization.json`
- `docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/outcome-context-validation.json`
- `tests/test_outcome_context_real_pipeline.py`
- `tests/test_export_policy_outcomes_snapshot.py`
- `tests/test_outcome_context_pair_plan_real_pipeline.py`
- `tests/test_outcome_context_pair_plan_c2b_real_pipeline.py`
- `etl/data/staging/outcome-context-pair-plan-v1-validation.json`
- `etl/data/staging/outcome-context-pair-plan-c2b-v1-validation.json`
