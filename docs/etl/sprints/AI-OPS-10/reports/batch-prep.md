# AI-OPS-10 T11 Batch Prep

Date:
- `2026-02-17`

Objective:
- Validate matrix headers and source coverage, run preflight checks (`db path`, `snapshot date`, `fallback fixtures`), and emit a validated matrix packet for execution.

## Output artifacts

- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- `docs/etl/sprints/AI-OPS-10/reports/batch-prep.md`

## Matrix validation results

Source matrix:
- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv`
- `sha256=178fb00cbc55f54f01e727032b16ab59be76b541d7dc0f9a96fddf5cf43085e3`

Validated matrix:
- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
- `sha256=5ca3e8b40cce71b460ab1d742d1e6e22c4e540e84c8cc6b81733d0a5c53f311d`

Validation checks:
1. Header contract: PASS (all required runner columns present).
2. Source coverage: PASS (`7` target `source_id` values present).
3. Mode coverage: PASS (`strict-network`, `from-file`, `replay` per source).
4. Required row fields: PASS (`ingest_command` and expected artifact paths non-empty for all `21` rows).
5. Command/source alignment: PASS (`--source` in command matches matrix `source_id`).
6. Mode flag alignment: PASS (`strict-network` rows include `--strict-network`; `from-file/replay` rows include `--from-file`).

## Preflight checks

1. DB path:
- `etl/data/staging/politicos-es.db` exists: `true`.

2. Snapshot date:
- unique matrix snapshot date: `2026-02-17` (ISO date, valid).

3. Fallback fixtures (`from-file` rows):
- missing count: `0` (all expected fallback fixtures present).

4. Replay inputs (advisory at T11; required before replay wave):
- missing count: `7`
- rows pending replay fixture capture:
  - `placsp_autonomico__replay`
  - `bdns_autonomico__replay`
  - `placsp_sindicacion__replay`
  - `bdns_api_subvenciones__replay`
  - `eurostat_sdmx__replay`
  - `bde_series_api__replay`
  - `aemet_opendata_series__replay`

Packet preflight status:
- `WARN` (no hard errors; replay fixtures still pending by design at this step).

Escalation rule check (`missing required command or artifact path`):
- Not triggered (`0` missing required command/path fields).

## Command hashes

Runner script:
- `scripts/run_source_probe_matrix.sh`
- `sha256=d59b7fa0d058a3a7f89b4d110b00a5b613520641737ba8233948420012907b32`

Per-row `ingest_command` hashes (also embedded in validated TSV as `command_sha256`):
- `placsp_autonomico__strict-network`: `eb729b3f184eafedfc4536dc02a193e3edd25487adcf94150e5c7792bb996a08`
- `placsp_autonomico__from-file`: `55b9f87c125ec0507913fe5d127b1da8a912e609b104b20e00cda27c91f53d73`
- `placsp_autonomico__replay`: `e80db4f4dc42c1f0288002e9ae4e8ccb27a29da983624806fbb66f1af9ef74fa`
- `bdns_autonomico__strict-network`: `32bded0dadbe62f9fabf9e615a2ddbc4f42b71e96a13fe885e912abab05ec878`
- `bdns_autonomico__from-file`: `a60ef536bfc9e030f57541cbdc4b6703e2e455a770674c91723085376f43c1c0`
- `bdns_autonomico__replay`: `0b783204087341b3ba92712b2ffa1d6b2f2531a0f125a80097745277c003a9ee`
- `placsp_sindicacion__strict-network`: `22ca37a226dbfa702dc8893da36be7bbdf50e2a983effda50c8ba35bfc364aff`
- `placsp_sindicacion__from-file`: `117cc73872c44c2c862379b97345c9dc366316c4521514dce2a51e5d5d605991`
- `placsp_sindicacion__replay`: `217b25145f6736d5326c1ced5da294713ca0c208082a32ac915032843fa07f25`
- `bdns_api_subvenciones__strict-network`: `920cb1838fc6691fc95e21c86628281ee714ae16c2ea06f0650b14cc40f26248`
- `bdns_api_subvenciones__from-file`: `f37afdc6a86a80ebed8f94198a336c14675851906bb2585499a2e1f56be11b8c`
- `bdns_api_subvenciones__replay`: `506bacad0301384158b93f2f76c1010059be50acadcdc1ff43e38b8b60ae21e8`
- `eurostat_sdmx__strict-network`: `f1d69202de7e195b92ad394608a80bbd272629a61773b35feaa7f414bb25fb65`
- `eurostat_sdmx__from-file`: `9afac6d5fc3c742bdc23b0a95badb07bd2961ee4fb1dd2fcb64208adb901808e`
- `eurostat_sdmx__replay`: `2b1b1203badda7bd0dad8f5f542acdc2eee7046ba4ce9bd17d18551a2c30e37a`
- `bde_series_api__strict-network`: `e2b89012141e40b293788ba9b0b6cf7c311b7b7426594370ab2ec07ee0ad1a54`
- `bde_series_api__from-file`: `b8197a15b866a290f4a540bf269344312cb0b65d96b867c0b18359beea55e124`
- `bde_series_api__replay`: `46ec91ca44d3ce99046bde793e1f59ad7962d4767d4a002857f09f3da7e97d85`
- `aemet_opendata_series__strict-network`: `f03cb8ab824b86d76a2cf3c0e928499492ffe126f93695043b354c4f6822e98a`
- `aemet_opendata_series__from-file`: `207093e9607390c8971d4ec19141504c5775b897b07644cdf4da23406bb2b8fe`
- `aemet_opendata_series__replay`: `743b2571ec3008b3821a00093fda0897cf397318f61ead91c08f6bf5b1aba9aa`

## Environment details

- `validated_at_utc=2026-02-17T10:27:02+00:00`
- `cwd=REPO_ROOT/vota-con-la-chola`
- `shell=/bin/zsh`
- `python=Python 3.11.14`
- `platform=macOS-26.3-arm64-arm-64bit`
- `user=jesus`

## Acceptance references

- `test -f docs/etl/sprints/AI-OPS-10/reports/batch-prep.md`
- `test -f docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.validated.tsv`
