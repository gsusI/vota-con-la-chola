# votaconlachola.org served from R2 — production verification (2026-10-12 UTC)

- Worker `votaconlachola-org` version `00d12a07-abf0-445b-8121-cc69ee6be59e` deployed at 100%; previous version `740eda54-fa99-456c-b54e-faf7f3838c4f` (GitHub raw proxy) kept as rollback target (`wrangler versions deploy 740eda54-fa99-456c-b54e-faf7f3838c4f@100`).
- R2 bucket `vclc-site`: release `20261012T064702Z-5879a6ef383e` from `gh-pages` commit `5879a6ef38`, `50,135` files / `1,120,744,730` bytes uploaded, ETag parity verified for all files (`site-origin-sync-1.json`).
- Public manifest: `https://votaconlachola.org/releases/latest.json` -> manifest sha256 `9d0426d78ed105181d64d919b58b6177817de0c90c8ff589783adb4dc6b0d312`.

| Check | Result |
| --- | --- |
| `/citizen/`, `/citizen/vota/`, `/people/`, `/accountability-dossiers/`, `/methods/`, `/citizen/data/voting_aid_pool_v1.json` | `200`, `x-vclc-origin: r2` |
| `/releases/latest.json` | `200`, `x-vclc-origin: r2` |
| `/graph/data/arena-mandates.json` with `Range: bytes=0-99` | `206`, 100 bytes |
| sha256-pinned `/spending/launch/<sha>/manifest.json` | `cache-control: public, max-age=31536000, immutable` |
| `/no-existe/` | `404` (site 404 page), `no-store` |
| `/vota-con-la-chola/citizen` | `308` redirect |
| Responses referencing `raw.githubusercontent.com` | `0` |
| Static shell `/` | `x-content-type-options: nosniff`, `referrer-policy: strict-origin-when-cross-origin` |

Propagation: for ~1 minute after deploy some edges still served the previous version; 6/6 consecutive probes returned `r2` afterwards.
