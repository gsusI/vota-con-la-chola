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

## Steps 2–4 (2026-10-12 UTC)

- Worker version `3e683cf7-c264-4c61-9d39-852da2f642ad`: fixed `content-range` (`bytes 0-15/2674405`, `bytes 2674400-2674404/2674405`, `bytes 2674397-2674404/2674405` for `0-15`, `2674400-`, `-8`); `stale-while-revalidate=86400` for browsers.
- Brotli: `/graph/data/arena-mandates.json` 23,804,221 B served as 2,582,364 B.
- `/datasets/latest.json` + `snapshots/2026-08-12` (163 files, 62,395,936 B) mirrored from HF; 162 verified against `checksums.sha256`, parity verified in R2.
- `/downloads/0e55b07120bcb42731b45a78fd682813cd6a51793232faee805ddce46be32a90/placsp-launch.zip`: `200`, 182,758,699 B, `immutable`, downloaded sha256 `ce490104c5bd41ba9c23205c45395d6edf20b80b745cfac73212b4a32601606c` = `archive_sha256`.
- Explorer (`/legacy/explorer/`, Chrome): table list in <10 s, `mandates` rows with FK labels, 0 requests to huggingface.co, no console errors. Single-table bind from the browser: 0.56 s origin vs 2.49 s HF.
- Before the fix the static explorer failed in both origin and `?source=hf` modes with `Cannot read properties of null (reading 'conn')`.
