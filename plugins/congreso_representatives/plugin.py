from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from publicdata_connectors_es.representatives.congreso import CongresoDiputadosConnector
from publicdata_connectors_es.representatives.parsers import parse_json_source
from publicdata_core.plugins import (
    AcquiredArtifact,
    FactBatch,
    OfficialCaptureConnectorAdapter,
    PluginContext,
    PluginContractError,
    SourceRecordEnvelope,
    WorkItemRef,
)
from publicdata_core.util import pick_value, sha256_bytes, stable_json

PLUGIN_ID = "org.votaconlachola.congreso-representatives"
SOURCE_ID = "congreso_diputados"
OFFICIAL_URL = (
    "https://www.congreso.es/webpublica/opendata/diputados/"
    "DiputadosActivos__20260212050007.json"
)
CAPTURE_RELATIVE_PATH = Path("etl/data/raw/samples/congreso_diputados_sample.json")
CAPTURE_SHA256 = "6cb85d7fb70dd807c9a5a85e91fa3e4a20d1b19edb4f981a5c63c0d113444ef4"
PLUGIN_NAMESPACE = uuid.UUID("3e4ec58b-0383-54f4-b4cf-60b44cab16ee")


def _public_id(kind: str, source_record_id: str) -> str:
    value = uuid.uuid5(PLUGIN_NAMESPACE, f"{kind}:{SOURCE_ID}:{source_record_id}")
    return f"urn:vclc:{kind}:{value}"


class CongresoRepresentativesPlugin:
    plugin_id = PLUGIN_ID
    plugin_version = "1.0.0"

    def __init__(self) -> None:
        self._delegate = CongresoDiputadosConnector()

    def register(self) -> Mapping[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "version": self.plugin_version,
            "source_ids": (SOURCE_ID,),
            "output_contracts": ("representative_role_assignment_v1",),
        }

    def validate_config(self, ctx: PluginContext) -> Mapping[str, Any]:
        capture_path = ctx.repo_root / CAPTURE_RELATIVE_PATH
        errors: list[str] = []
        if not ctx.snapshot_date:
            errors.append("snapshot_date is required")
        if not ctx.network_enabled and not capture_path.is_file():
            errors.append(f"official capture missing: {CAPTURE_RELATIVE_PATH}")
        if errors:
            raise PluginContractError("; ".join(errors))
        return {
            "status": "ok",
            "network_enabled": ctx.network_enabled,
            "source_id": SOURCE_ID,
            "snapshot_date": ctx.snapshot_date,
        }

    def plan(self, ctx: PluginContext) -> Iterable[WorkItemRef]:
        self.validate_config(ctx)
        partition_key = ctx.partition_key or f"{SOURCE_ID}/{ctx.snapshot_date}"
        item_key = f"{SOURCE_ID}:{ctx.snapshot_date}:active-roster"
        yield WorkItemRef(
            plugin_id=self.plugin_id,
            pipeline_id=f"{self.plugin_id}:{ctx.snapshot_date}",
            item_key=item_key,
            partition_key=partition_key,
            source_id=SOURCE_ID,
            source_url=OFFICIAL_URL,
            idempotency_key=item_key,
            payload={
                "source_snapshot_date": ctx.snapshot_date,
                "capture_path": str(CAPTURE_RELATIVE_PATH),
                "network_enabled": ctx.network_enabled,
            },
        )

    def discover(self, ctx: PluginContext) -> Iterable[WorkItemRef]:
        return self.plan(ctx)

    def build_connector(self, ctx: PluginContext):
        self.validate_config(ctx)
        if ctx.network_enabled:
            return self._delegate
        return OfficialCaptureConnectorAdapter(
            self._delegate,
            official_url=OFFICIAL_URL,
            capture_path=ctx.repo_root / CAPTURE_RELATIVE_PATH,
            capture_sha256=CAPTURE_SHA256,
        )

    def acquire(self, item: WorkItemRef, ctx: PluginContext) -> AcquiredArtifact:
        if item.source_id != SOURCE_ID:
            raise PluginContractError(f"unexpected source_id: {item.source_id}")
        connector = self.build_connector(ctx)
        extracted = connector.extract(
            raw_dir=ctx.raw_dir,
            timeout=ctx.timeout_seconds,
            from_file=None,
            url_override=None,
            strict_network=ctx.strict_network,
        )
        return AcquiredArtifact(
            source_id=extracted.source_id,
            source_url=extracted.source_url,
            resolved_url=extracted.resolved_url,
            fetched_at=extracted.fetched_at,
            raw_path=extracted.raw_path,
            content_sha256=extracted.content_sha256,
            content_type=extracted.content_type,
            bytes=extracted.bytes,
            cas_key=f"sha256/{extracted.content_sha256[:2]}/{extracted.content_sha256}",
            note=extracted.note,
            payload=extracted.payload,
        )

    def parse(
        self, artifact: AcquiredArtifact, ctx: PluginContext
    ) -> Iterable[SourceRecordEnvelope]:
        if artifact.source_id != SOURCE_ID:
            raise PluginContractError(
                f"unexpected artifact source_id: {artifact.source_id}"
            )
        records = parse_json_source(artifact.payload)
        for ordinal, record in enumerate(records):
            source_record_id = pick_value(
                record,
                ("CODDIPUTADO", "ID", "id", "codParlamentario"),
            )
            if not source_record_id:
                normalized = self._delegate.normalize(record, ctx.snapshot_date)
                if normalized is None or not normalized.get("source_record_id"):
                    raise PluginContractError(
                        f"official Congreso record at ordinal {ordinal} cannot form a source-scoped ID"
                    )
                source_record_id = str(normalized["source_record_id"])
            raw_record = stable_json(record)
            yield SourceRecordEnvelope(
                source_id=SOURCE_ID,
                source_record_id=source_record_id,
                source_snapshot_date=ctx.snapshot_date,
                artifact_sha256=artifact.content_sha256,
                record_ordinal=ordinal,
                record_sha256=sha256_bytes(raw_record.encode("utf-8")),
                raw_record=record,
            )

    def normalize(
        self,
        records: Sequence[SourceRecordEnvelope],
        ctx: PluginContext,
    ) -> FactBatch:
        rows: list[Mapping[str, Any]] = []
        for envelope in records:
            normalized = self._delegate.normalize(
                dict(envelope.raw_record),
                ctx.snapshot_date,
            )
            if normalized is None:
                continue
            source_record_id = str(normalized["source_record_id"])
            rows.append(
                {
                    **normalized,
                    "actor_id": _public_id("actor", source_record_id),
                    "role_assignment_id": _public_id(
                        "role-assignment", source_record_id
                    ),
                    "source_id": SOURCE_ID,
                    "source_url": OFFICIAL_URL,
                    "artifact_sha256": envelope.artifact_sha256,
                    "record_sha256": envelope.record_sha256,
                    "record_ordinal": envelope.record_ordinal,
                }
            )
        logical_payload = stable_json(rows).encode("utf-8")
        return FactBatch(
            contract="representative_role_assignment",
            schema_version="1",
            ontology_concept="role",
            partition_key=ctx.partition_key or f"{SOURCE_ID}/{ctx.snapshot_date}",
            rows=tuple(rows),
            source_records_seen=len(records),
            source_records_loaded=len(rows),
            logical_sha256=hashlib.sha256(logical_payload).hexdigest(),
        )

    def validate(self, batch: FactBatch) -> Mapping[str, Any]:
        errors: list[str] = []
        if batch.source_records_seen <= 0:
            errors.append("official capture produced zero source records")
        if batch.source_records_loaded != batch.source_records_seen:
            errors.append("normalized rows do not reconcile with source records")
        for row in batch.rows:
            if not str(row.get("source_record_id") or ""):
                errors.append("normalized row missing source_record_id")
            if not str(row.get("actor_id") or "").startswith("urn:vclc:actor:"):
                errors.append("normalized row missing stable actor_id")
            if row.get("source_url") != OFFICIAL_URL:
                errors.append("normalized row missing exact official source URL")
        if errors:
            raise PluginContractError("; ".join(errors))
        return {
            "status": "ok",
            "records_seen": batch.source_records_seen,
            "records_loaded": batch.source_records_loaded,
            "logical_sha256": batch.logical_sha256,
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock": False,
        }

    def checkpoint(self, item: WorkItemRef, batch: FactBatch) -> Mapping[str, Any]:
        return {
            "item_key": item.item_key,
            "partition_key": batch.partition_key,
            "logical_sha256": batch.logical_sha256,
            "records_loaded": batch.source_records_loaded,
        }

    def cleanup(self, ctx: PluginContext) -> Mapping[str, Any]:
        return {
            "status": "ok",
            "temporary_files_removed": 0,
            "snapshot_date": ctx.snapshot_date,
        }


PLUGIN = CongresoRepresentativesPlugin()
