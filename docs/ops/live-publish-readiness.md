# Live publish readiness

Date checked: `2026-05-12`

Current state:

- `Live ETL Publish` is scheduled daily at `04:17 UTC`.
- Latest scheduled run checked here: `25715374667` on `2026-05-12`.
- Live workflow builds public static artifacts and runs the Hugging Face dry-run packager.
- Repository secret listing returned no configured publish secrets in this environment.

Tracker blocker:

- Run `25715374667` failed at `Enforce tracker truth` with `mismatches=1` and `done_zero_real=1`.
- Failing source: `asamblea_melilla_diputados`, marked `DONE` in the tracker but loaded only fallback records in GitHub Actions (`max_net=0`, `max_any=26`).
- Tracker fix: downgrade that row to `PARTIAL` until the next real-network run succeeds.

Publish blocker:

- Hugging Face publish skips unless `HF_TOKEN` is configured and either `HF_DATASET_REPO_ID` or `HF_USERNAME` identifies the target dataset repo.
- Cloudflare deploy skips unless `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are configured.

Required GitHub Actions secrets:

| Secret | Required for | Notes |
|---|---|---|
| `HF_TOKEN` | Hugging Face snapshot publish | Dataset write token. Do not commit it. |
| `HF_DATASET_REPO_ID` | Hugging Face snapshot publish | Preferred explicit repo id, for example `owner/dataset-name`. |
| `HF_USERNAME` | Hugging Face snapshot publish | Fallback target owner when `HF_DATASET_REPO_ID` is absent. |
| `CLOUDFLARE_API_TOKEN` | Cloudflare Pages deploy | Token with Pages deploy access. Do not commit it. |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Pages deploy | Cloudflare account id. |

Verification path after secrets are added:

```bash
gh workflow run "Live ETL Publish" --ref main -f publish=true
gh run watch --exit-status
```

Done when:

- `Run live ETL` passes.
- `Enforce tracker truth` passes.
- `Build public static artifacts` passes.
- `Publish Hugging Face snapshot` does not print a missing-secret skip.
- `Deploy Cloudflare Pages` does not print a missing-secret skip.
- Hugging Face `latest.json` points at the run snapshot date.
- The Cloudflare Pages URL serves `/explorer-sources/` with the same snapshot.
