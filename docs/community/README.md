# Community operating pack

This folder is the contributor operating pack for public-data coverage.

Start here:

- Source onboarding: `docs/etl/source-onboarding.md`
- Dev quickstart: `docs/dev/quickstart.md`
- Contributor rules: `CONTRIBUTING.md`
- Source catalog UI: `/explorer-sources/`
- Starter tasks: `docs/community/contributor-challenges-v1.md`
- Steward map: `docs/community/steward-map.md`
- Partner guide: `docs/community/partner-integration-guide.md`
- Conduct: `CODE_OF_CONDUCT.md`
- Security and sensitive reporting: `SECURITY.md`
- Data correction template: `.github/ISSUE_TEMPLATE/data_correction.yml`
- Integrity signal review: `docs/method/integrity-signal-policy.md`
- Citation metadata: `CITATION.cff`

GitHub operations created:

- Milestone: `H2 - plataforma contributiva`
- Starter issues: `#1` through `#10`
- Core labels: `area:etl`, `area:docs`, `area:governance`, `type:data-source`, `type:release`, `status:needs-repro`, `status:blocked`, `status:ready-for-review`, `status:needs-maintainer`, `priority:low`, `priority:medium`, `priority:high`

Operating rule:

- no source is marked `DONE` without current live evidence;
- blocked public data access is recorded as a blocker, not hidden;
- first contributor PR should land traceable raw records before deeper normalization;
- publish-facing artifacts must pass `just privacy-check-public-artifacts`.
