# Reproducibilidad y snapshots firmados

Estado: `implementado; release real firmado y verificado en TODO 16`

Fecha: `2026-08-19`

## Objetivo

Un tercero debe poder demostrar cuatro cosas sin confiar en la máquina que publicó:

1. qué manifest exacto describe el snapshot;
2. qué schema y contrato de artifacts usó;
3. qué cambió frente al snapshot anterior;
4. qué identidad de release firmó ese manifest.

La firma no prueba que un hecho político sea verdadero ni que exista corrupción.
Prueba que una identidad autorizada firmó exactamente un manifest, y ese manifest
compromete por SHA-256 los artifacts reales, sus tamaños, procedencia y políticas.

## Ahora

El origin durable ya usa una ruta inmutable dirigida por el SHA-256 del manifest:

`scale/snapshots/<snapshot_date>/<manifest_sha256>/`

El manifest `real-scale-origin-bundle-v2` incluye:

- versión de schema;
- un `real-scale-artifact-contract-v1` hasheado;
- registry y readiness exactos;
- corpora, filas, ficheros y bytes;
- URL/host oficial y cobertura de procedencia;
- SHA-256 y tamaño de cada fichero;
- política real-only y retención de información personal oficial pública.

TODO 16 añade:

- `vclc_snapshot_attestation_v1`, serializado canónicamente;
- firma SSH `ed25519` con namespace separado
  `vota-con-la-chola-snapshot-v1`;
- trust root local `allowed_signers`, que nunca se acepta desde el propio bundle;
- puntero de attestation en `scale/latest.json`;
- verificación live de manifest, firma, hashes y política;
- diff exacto y bounded entre manifests reales.

Release live actual:

- snapshot `2026-08-19`;
- manifest/release `5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd`;
- artifact contract `d7de5544cc277c85fb2a4ae6d1e4e2bb1867ddc35857502b73c3780834aef565`;
- `7` corpus, `5,414,326` filas, `8,597` data files, `500,714,815` bytes;
- signer `vclc-snapshot-release-2026`, fingerprint `SHA256:R2B1jFbkLoigmKxObr+ExlBLrKENkaUDp0C3ip0Lj7A`;
- verificaciones live de firma y paridad sin errores ni warnings.

## Contrato de firma

Archivos publicados bajo la ruta inmutable:

- `attestation/attestation.json`;
- `attestation/attestation.json.sig`;
- `attestation/signing-key.pub` para descubrimiento.

El trust root está fuera del dataset:

- `docs/ops/keys/vclc-snapshot-release-2026.allowed_signers`.

Un verificador debe aportar ese fichero desde una copia confiable del repositorio o
su propia policy. Nunca debe confiar automáticamente en la clave que viaja al lado de
la firma.

La attestation firma:

- URL HTTPS y SHA-256 del manifest;
- snapshot date y ruta content-addressed;
- versiones del manifest y artifact contract;
- SHA-256 del artifact contract;
- corpora, filas, ficheros, bytes y lanes de millón;
- política de datos oficiales reales, cero synthetic/mock y conservación de
  identidad personal oficial pública.

La clave privada no aparece en manifests, reports, Git, GH Pages ni Hugging Face.

## Publicar

El publish de scale origin falla si no existe `SNAPSHOT_SIGNING_KEY`:

```bash
SNAPSHOT_DATE=2026-08-19 \
SNAPSHOT_SIGNING_KEY=etl/data/manifests/signing/vclc-snapshot-release.key \
SNAPSHOT_SIGNER_IDENTITY=vclc-snapshot-release-2026 \
just etl-scale-origin-hf-publish
```

Orden del publish:

1. reconstruir registry/readiness desde corpora reales;
2. verificar todos los bytes y SHA-256 declarados;
3. construir manifest y ruta inmutable;
4. firmar y verificar localmente la attestation;
5. subir data + manifest + attestation;
6. mover `scale/latest.json` al final;
7. verificar la firma desde el origin público usando el trust root local.

Para firmar un snapshot ya publicado sin re-subir data:

```bash
SNAPSHOT_SIGNING_KEY=etl/data/manifests/signing/vclc-snapshot-release.key \
just etl-scale-origin-hf-attest-current
```

## Verificar desde cero

No necesita token ni clave privada:

```bash
just etl-scale-origin-hf-verify-attestation
```

La implementación descarga `scale/latest.json`, el manifest, la attestation, la
firma y la clave pública de descubrimiento. La decisión de confianza usa únicamente
el `allowed_signers` local. Después exige:

- firma válida para identidad y namespace exactos;
- hash de attestation igual al puntero latest;
- hash de firma igual al puntero latest;
- hash del manifest igual a latest y al subject firmado;
- artifact contract igual entre manifest y attestation;
- las cuatro políticas obligatorias en `true`.

## Diff entre releases reales

```bash
python3 scripts/diff_scale_snapshot_manifests.py \
  --before path/to/previous/manifest.json \
  --after path/to/current/manifest.json \
  --out path/to/diff.json
```

El diff usa merge ordenado por path. Produce conteos exactos de added, removed,
changed y unchanged, delta de bytes, cambios de corpora/contracts y solo una muestra
bounded de paths. No carga bytes de datasets ni emite registros personales: compara
metadatos content-addressed. Las identidades dentro de los datos siguen intactas.

El diff publicado actual contra el release `5872efaf...` contiene `6` ficheros
añadidos, `2` cambiados, `0` eliminados y `8,617` intactos. Añade
`candidate_occurrences` con `10,820` filas oficiales efectivas; no crea ni elimina
identidades para producir el diff.

## Gate de evidencia completo

```bash
just snapshot-reproducibility-check
```

El gate verifica tests criptográficos y de origin, recalcula el diff y reconcilia
manifest, reporte de publicación, firma live, paridad live y diff mediante
`vclc_snapshot_reproducibility_validation_v1`. Cualquier hash, policy, total,
metadata o ruta inmutable divergente falla el release.

## Escala

- Firmar y verificar es O(1) respecto a los datos: opera sobre el manifest raíz.
- Hashear artifacts es streaming en bloques de 1 MiB.
- El diff no crea un mapa adicional por cada fichero; fusiona inventarios ordenados.
- La publicación sube la ruta inmutable antes de mover latest.
- Para un millón de documentos, cada corpus conserva manifests JSONL/Parquet
  particionados y el manifest raíz firma sus hashes. No se publican millones de filas
  en un JSON de navegador.
- El upload actual usa lotes de `250` ficheros y el restore workers bounded. El número
  de workers cambia rendimiento, no identidad ni firma.

## Rotación y custodia

- Guardar la clave privada como secret file de CI o secret manager, nunca en Git.
- Permisos `0600`; job de firma aislado de scraping y parsing.
- El publisher solo necesita write sobre el dataset; verificadores son públicos.
- Añadir una nueva clave al trust root mediante revisión de dos mantenedores.
- Mantener la clave anterior para verificar historia; no borrar firmas viejas.
- Si hay exposición, revocar para releases futuras, registrar incidente, crear nueva
  identidad y volver a firmar solo manifests cuyos hashes sigan verificando.

## Limitación honesta

Esta slice entrega firma técnica y release real verificable. `W9-009` sigue abierto
hasta que un mantenedor externo reconstruya el release y publique una segunda
attestation independiente. Una sola firma del proyecto no demuestra reproducción
independiente.
