# Signed reproducible scale snapshot

Fecha: `2026-08-19T19:00:00+00:00`

Estado: `published_live_verified`

## Cambio público

El origin durable publica un snapshot inmutable firmado que cualquier tercero puede
verificar sin token ni clave privada. El release
`5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd`
contiene `7` corpus oficiales reales, `5,414,326` filas, `8,597` data files y
`500,714,815` bytes de datos. Conserva nombres e información personal tal como la
publican las fuentes oficiales.

La firma SSH Ed25519 usa identidad `vclc-snapshot-release-2026`, namespace
`vota-con-la-chola-snapshot-v1` y fingerprint
`SHA256:R2B1jFbkLoigmKxObr+ExlBLrKENkaUDp0C3ip0Lj7A`. El verificador confía en el
`allowed_signers` del repositorio, no en la clave de descubrimiento incluida dentro
del mismo dataset.

## Qué cambió frente al release anterior

- nuevo corpus real `candidate_occurrences`: `10,820` filas;
- `6` bundle files añadidos;
- `2` ficheros de metadata cambiados;
- `0` eliminados;
- `8,617` intactos.

## Rutas

- `/transparency/`
- `/transparency/data/transparency.json`
- [manifest firmado](https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/resolve/main/scale/snapshots/2026-08-19/5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd/manifest.json)
- [attestation](https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/resolve/main/scale/snapshots/2026-08-19/5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd/attestation/attestation.json)

## Verificación

```bash
just etl-scale-origin-hf-verify-attestation
just etl-scale-origin-hf-verify
just snapshot-reproducibility-check
```

## Límite honesto

La firma prueba identidad y exactitud de bytes, no la verdad sustantiva de cada
hecho político ni una reproducción independiente. `W9-009` sigue abierto hasta que
un mantenedor externo reconstruya y firme una segunda attestation.

## Evidencia

- `docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/signed-scale-publish-report.json`
- `docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/live-signed-snapshot-verification.json`
- `docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/live-scale-origin-parity.json`
- `docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/published-scale-manifest-diff.json`
- `docs/etl/sprints/REPRODUCIBILITY-20260819/evidence/snapshot-reproducibility-validation.json`
