# Live ETL tracker truth check

Date: `2026-05-12`

GitHub Actions run:

- `https://github.com/gsusI/vota-con-la-chola/actions/runs/25715374667`
- Event: scheduled `Live ETL Publish`
- Head SHA: `7c4c80430d0c7abd43dc3ae37b83a107b0f9ccf0`

Run result:

- `Run live ETL`: passed.
- `Enforce tracker truth`: failed before static build, Hugging Face publish, or Cloudflare deploy.
- Total records loaded: `78621/78717`.

Tracker summary from the failed run:

```text
tracker_sources: 37
sources_in_db: 37
mismatches: 1
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 1
```

Failing row:

```text
asamblea_melilla_diputados | DONE | PARTIAL | runs_ok/total=1/1 | max_net=0 | max_any=26 | last_loaded=26 | net/fallback_fetches=0/1 | DONE_ZERO_REAL
```

Connector output in the same live run:

```text
asamblea_melilla_diputados: 26/26 registros validos [network-error-fallback: RuntimeError: No se encontró dataset_PTS2_MIEMBROS en la página]
```

Decision:

- Downgrade tracker row from `DONE` to `PARTIAL`.
- Keep the previous `2026-05-11` real-network proof as historical evidence only.
- Do not claim this source is live-clean again until a current strict/live run has `max_net > 0`.
