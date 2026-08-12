# Durable object-origin contract

Status: implementation contract ready; production origin not configured.

Purpose: preserve millions of raw and derived documents independently from one workstation while keeping local files disposable and every byte checksum-verifiable.

## Object identity

- Logical identity: SHA-256 of exact bytes.
- Key: `<namespace>/sha256/<first-2>/<next-2>/<full-sha256>`.
- The key has no source filename or personal/workstation path.
- Metadata must include `sha256`; `ContentLength` must equal the manifest byte count.
- Content type is metadata. It does not participate in identity.
- Uploading the same checksum is an idempotent verification, not a new logical object.

## Production requirements

- S3-compatible API with bucket versioning enabled.
- Server-side encryption at rest.
- TLS only.
- Public-read disabled on the raw origin. Public release artifacts use a separate bucket/prefix and publisher.
- ETL writer can put/head/get only the evidence prefix; it cannot change bucket policy.
- Restore identity can read/list versions but cannot write production objects.
- Lifecycle: hot metadata/manifests; warm extracted text; cold originals only after restore/cost proof.
- Deletion/retention policy requires maintainer approval and an immutable manifest supersession record.
- Access logs and cost metrics retained outside the evidence bucket.

Credentials come from the runtime environment/AWS credential chain. Never put access keys, secret keys, tokens, endpoint credentials, or bucket policies in manifests, reports, commands committed to the repo, or public artifacts.

Configuration:
- `OBJECT_STORE_BACKEND=filesystem|s3`
- `OBJECT_STORE_BUCKET` for S3-compatible storage
- `OBJECT_STORE_ENDPOINT_URL` for non-AWS S3 endpoints
- `AWS_DEFAULT_REGION`
- standard runtime credential variables or workload identity
- `OBJECT_STORE_FILESYSTEM_ROOT` only for local rehearsal

## Runbook

Read-only planning:

```bash
OBJECT_STORE_BACKEND=s3 just etl-object-store-replicate-dry-run
```

Replication after bucket policy/credentials are reviewed:

```bash
OBJECT_STORE_BACKEND=s3 just etl-object-store-replicate
```

Checksum restore drill:

```bash
OBJECT_STORE_BACKEND=s3 OBJECT_STORE_RESTORE_SAMPLE_SIZE=100 \
  just etl-object-store-restore-drill
```

The manifest is streaming JSONL under the ignored local manifest directory. Public reports contain totals/status only. Local raw paths are never emitted.

## Local capacity guard

PLACSP archive and member workers enforce free-space floors before claiming work. Reserve includes the maximum next archive or claimed member batch, so a blocked preflight leaves queue state untouched and performs no network request.

```bash
PLACSP_HISTORY_MIN_FREE_BYTES=107374182400 \
  just etl-scale-placsp-history-archives-work
```

`blocked_storage` is an expected non-zero safety result. Resolve it by provisioning the reviewed remote origin or more local capacity; do not lower the floor merely to consume the workstation's remaining disk. Runtime evidence is `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-official-history-storage-preflight-20260811.json`.

## Promotion gate

Remote origin is not `DONE` until:

- a versioned real bucket is configured with least privilege and encryption,
- a representative upload completes with zero checksum/byte mismatches,
- a clean environment restores a deterministic sample,
- a full manifest reconciliation proves `manifest = present + explicitly failed`,
- RPO/RTO, storage/request cost, lifecycle, and credential rotation are recorded,
- a cache deletion/rebuild drill passes,
- privacy and secret gates pass on every report/manifest intended for publication.

Fixture filesystem/fake-S3 tests prove the adapter contract only. They do not prove remote durability.
