from __future__ import annotations

import hashlib
import importlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, runtime_checkable

from .connectors import BaseConnector
from .types import Extracted

PLUGIN_API_VERSION = "1.0.0"
PLUGIN_MANIFEST_SCHEMA_VERSION = "plugin_manifest_v1"
PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
ENTRY_POINT_RE = re.compile(
    r"^(?P<module>[A-Za-z_][A-Za-z0-9_.]*):(?P<object>[A-Za-z_][A-Za-z0-9_.]*)$"
)


class PluginContractError(ValueError):
    """Raised when a plugin fails before its code is imported or executed."""


class PluginType(StrEnum):
    CONNECTOR = "connector"
    PARSER = "parser"
    NORMALIZER = "normalizer"
    EXTRACTOR = "extractor"
    LINKER = "linker"
    SCORER = "scorer"
    PUBLISHER = "publisher"


class LifecycleHook(StrEnum):
    REGISTER = "register"
    VALIDATE_CONFIG = "validate_config"
    PLAN = "plan"
    DISCOVER = "discover"
    ACQUIRE = "acquire"
    PARSE = "parse"
    NORMALIZE = "normalize"
    EXTRACT = "extract"
    LINK = "link"
    SCORE = "score"
    VALIDATE = "validate"
    PUBLISH = "publish"
    CHECKPOINT = "checkpoint"
    CLEANUP = "cleanup"


@dataclass(frozen=True)
class PluginContext:
    repo_root: Path
    raw_dir: Path
    snapshot_date: str
    timeout_seconds: int = 30
    strict_network: bool = True
    network_enabled: bool = False
    partition_key: str = ""


@dataclass(frozen=True)
class WorkItemRef:
    plugin_id: str
    pipeline_id: str
    item_key: str
    partition_key: str
    source_id: str
    source_url: str
    idempotency_key: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AcquiredArtifact:
    source_id: str
    source_url: str
    resolved_url: str
    fetched_at: str
    raw_path: Path
    content_sha256: str
    content_type: str | None
    bytes: int
    cas_key: str
    note: str
    payload: bytes


@dataclass(frozen=True)
class SourceRecordEnvelope:
    source_id: str
    source_record_id: str
    source_snapshot_date: str
    artifact_sha256: str
    record_ordinal: int
    record_sha256: str
    raw_record: Mapping[str, Any]


@dataclass(frozen=True)
class FactBatch:
    contract: str
    schema_version: str
    ontology_concept: str
    partition_key: str
    rows: tuple[Mapping[str, Any], ...]
    source_records_seen: int
    source_records_loaded: int
    logical_sha256: str


@dataclass(frozen=True)
class LoadedPlugin:
    manifest_path: Path
    manifest: Mapping[str, Any]
    instance: Any


@runtime_checkable
class ConnectorPlugin(Protocol):
    def plan(self, ctx: PluginContext) -> Iterable[WorkItemRef]: ...

    def acquire(self, item: WorkItemRef, ctx: PluginContext) -> AcquiredArtifact: ...


@runtime_checkable
class ParserPlugin(Protocol):
    def parse(
        self, artifact: AcquiredArtifact, ctx: PluginContext
    ) -> Iterable[SourceRecordEnvelope]: ...


@runtime_checkable
class NormalizerPlugin(Protocol):
    def normalize(
        self, records: Sequence[SourceRecordEnvelope], ctx: PluginContext
    ) -> FactBatch | Sequence[FactBatch]: ...


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _required_mapping(value: Any, label: str, errors: list[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be an object")
        return {}
    return value


def _required_sequence(value: Any, label: str, errors: list[str]) -> Sequence[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return []
    return value


def validate_plugin_manifest(
    manifest: Mapping[str, Any],
    *,
    repo_root: Path,
    ontology_concepts: set[str],
    verify_capture_bytes: bool = True,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != PLUGIN_MANIFEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PLUGIN_MANIFEST_SCHEMA_VERSION}")

    plugin_id = str(manifest.get("plugin_id") or "")
    if not PLUGIN_ID_RE.fullmatch(plugin_id):
        errors.append("plugin_id must be stable reverse-DNS lowercase syntax")
    version = str(manifest.get("version") or "")
    if not SEMVER_RE.fullmatch(version):
        errors.append("version must be SemVer")
    entry_point = str(manifest.get("entry_point") or "")
    if not ENTRY_POINT_RE.fullmatch(entry_point):
        errors.append("entry_point must be module:object")

    plugin_types_raw = _required_sequence(
        manifest.get("plugin_types"), "plugin_types", errors
    )
    plugin_types = {str(value) for value in plugin_types_raw}
    allowed_plugin_types = {value.value for value in PluginType}
    if not plugin_types or plugin_types - allowed_plugin_types:
        errors.append("plugin_types contains missing or unknown values")

    hooks_raw = _required_sequence(manifest.get("hooks"), "hooks", errors)
    hooks = {str(value) for value in hooks_raw}
    allowed_hooks = {value.value for value in LifecycleHook}
    if not hooks or hooks - allowed_hooks:
        errors.append("hooks contains missing or unknown values")
    if "validate" not in hooks:
        errors.append("hooks must include validate")
    if "connector" in plugin_types and not {"discover", "acquire"}.issubset(hooks):
        errors.append("connector plugins must declare discover and acquire")
    if "publisher" in plugin_types and "publish" not in hooks:
        errors.append("publisher plugins must declare publish")

    compatibility = _required_mapping(
        manifest.get("compatibility"), "compatibility", errors
    )
    if compatibility.get("core_ontology") != "core_ontology_v1":
        errors.append("compatibility.core_ontology must be core_ontology_v1")
    plugin_api = str(compatibility.get("plugin_api") or "")
    if "1" not in plugin_api:
        errors.append("compatibility.plugin_api must accept v1")

    outputs = _required_sequence(manifest.get("outputs"), "outputs", errors)
    if not outputs:
        errors.append("outputs must not be empty")
    for index, output_raw in enumerate(outputs):
        output = _required_mapping(output_raw, f"outputs[{index}]", errors)
        concept = str(output.get("ontology_concept") or "")
        if concept not in ontology_concepts:
            errors.append(f"outputs[{index}].ontology_concept is unknown: {concept}")
        public_id_field = str(output.get("public_id_field") or "")
        if not public_id_field.endswith("_id"):
            errors.append(f"outputs[{index}].public_id_field must end with _id")
        natural_keys = output.get("natural_key_fields")
        if not isinstance(natural_keys, list) or not natural_keys:
            errors.append(f"outputs[{index}].natural_key_fields must be non-empty")

    publication = _required_mapping(manifest.get("publication"), "publication", errors)
    for key in (
        "official_records_only",
        "synthetic_or_mock_data_forbidden",
        "placeholder_data_forbidden",
        "implicit_fallback_forbidden",
        "official_public_domain_personal_information_retained",
        "publication_hygiene_required",
        "validation_before_publish_required",
    ):
        if publication.get(key) is not True:
            errors.append(f"publication.{key} must be true")

    security = _required_mapping(manifest.get("security"), "security", errors)
    for key in (
        "credentials_embedded",
        "remote_code_execution",
        "auto_install_dependencies",
        "manifest_contains_secrets",
    ):
        if security.get(key) is not False:
            errors.append(f"security.{key} must be false")
    if security.get("runtime_capability_enforcement") is not True:
        errors.append("security.runtime_capability_enforcement must be true")

    sources = _required_sequence(manifest.get("sources"), "sources", errors)
    if "connector" in plugin_types and not sources:
        errors.append("connector plugins must declare at least one source")
    for source_index, source_raw in enumerate(sources):
        source = _required_mapping(source_raw, f"sources[{source_index}]", errors)
        source_id = str(source.get("source_id") or "")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", source_id):
            errors.append(f"sources[{source_index}].source_id is invalid")
        if source.get("synthetic_or_mock_data") is not False:
            errors.append(
                f"sources[{source_index}].synthetic_or_mock_data must be false"
            )
        if source.get("implicit_fallback") is not False:
            errors.append(f"sources[{source_index}].implicit_fallback must be false")
        if (
            source.get("official_public_domain_personal_information_retained")
            is not True
        ):
            errors.append(
                f"sources[{source_index}].official_public_domain_personal_information_retained must be true"
            )
        base_urls = _required_sequence(
            source.get("official_base_urls"),
            f"sources[{source_index}].official_base_urls",
            errors,
        )
        for url in base_urls:
            text = str(url)
            if not text.startswith(("https://", "manifest://")):
                errors.append(
                    f"sources[{source_index}] has non-official URL scheme: {text}"
                )
            if any(marker in text for marker in ("example.", "localhost", "127.0.0.1")):
                errors.append(
                    f"sources[{source_index}] has forbidden placeholder URL: {text}"
                )
        captures = _required_sequence(
            source.get("official_capture_contracts"),
            f"sources[{source_index}].official_capture_contracts",
            errors,
        )
        if not captures:
            errors.append(
                f"sources[{source_index}] requires an official capture contract"
            )
        for capture_index, capture_raw in enumerate(captures):
            capture = _required_mapping(
                capture_raw,
                f"sources[{source_index}].official_capture_contracts[{capture_index}]",
                errors,
            )
            capture_path = repo_root / str(capture.get("path") or "")
            provenance_path = repo_root / str(capture.get("provenance_path") or "")
            if not capture_path.is_file():
                errors.append(
                    f"official capture missing: {capture_path.relative_to(repo_root)}"
                )
                continue
            if not provenance_path.is_file():
                errors.append(
                    f"official capture provenance missing: {provenance_path.relative_to(repo_root)}"
                )
                continue
            if verify_capture_bytes:
                expected_sha = str(capture.get("sha256") or "")
                observed_sha = _sha256_path(capture_path)
                if observed_sha != expected_sha:
                    errors.append(
                        f"official capture SHA mismatch: {capture_path.relative_to(repo_root)}"
                    )
                if capture_path.stat().st_size != int(capture.get("bytes") or 0):
                    errors.append(
                        f"official capture byte count mismatch: {capture_path.relative_to(repo_root)}"
                    )
            try:
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"invalid official capture provenance: {exc}")
                continue
            if provenance.get("synthetic_or_mock") is not False:
                errors.append(
                    "official capture provenance must declare synthetic_or_mock=false"
                )
            if (
                provenance.get("public_domain_personal_information_retained")
                is not True
            ):
                errors.append(
                    "official capture provenance must retain public-domain identity"
                )

    test_hooks = _required_sequence(manifest.get("test_hooks"), "test_hooks", errors)
    for index, test_hook_raw in enumerate(test_hooks):
        test_hook = _required_mapping(test_hook_raw, f"test_hooks[{index}]", errors)
        if test_hook.get("uses_official_real_data") is not True:
            errors.append(f"test_hooks[{index}].uses_official_real_data must be true")

    return errors


def load_plugin_manifest(
    manifest_path: Path,
    *,
    repo_root: Path,
    ontology_path: Path,
    verify_capture_bytes: bool = True,
) -> Mapping[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ontology = json.loads(ontology_path.read_text(encoding="utf-8"))
    concepts = {
        str(item.get("code") or "")
        for item in ontology.get("concepts") or []
        if isinstance(item, Mapping)
    }
    errors = validate_plugin_manifest(
        manifest,
        repo_root=repo_root,
        ontology_concepts=concepts,
        verify_capture_bytes=verify_capture_bytes,
    )
    if errors:
        raise PluginContractError("; ".join(errors))
    return manifest


def _resolve_entry_point(value: str) -> Any:
    match = ENTRY_POINT_RE.fullmatch(value)
    if not match:
        raise PluginContractError("invalid entry point")
    module: ModuleType = importlib.import_module(match.group("module"))
    obj: Any = module
    for token in match.group("object").split("."):
        obj = getattr(obj, token)
    return obj


def load_plugin(
    manifest_path: Path,
    *,
    repo_root: Path,
    ontology_path: Path,
    verify_capture_bytes: bool = True,
) -> LoadedPlugin:
    manifest = load_plugin_manifest(
        manifest_path,
        repo_root=repo_root,
        ontology_path=ontology_path,
        verify_capture_bytes=verify_capture_bytes,
    )
    instance = _resolve_entry_point(str(manifest["entry_point"]))
    for hook in manifest.get("hooks") or []:
        if not callable(getattr(instance, str(hook), None)):
            raise PluginContractError(f"declared hook is not callable: {hook}")
    if str(getattr(instance, "plugin_id", "")) != manifest["plugin_id"]:
        raise PluginContractError("entry point plugin_id does not match manifest")
    return LoadedPlugin(
        manifest_path=manifest_path,
        manifest=manifest,
        instance=instance,
    )


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, LoadedPlugin] = {}

    def load_paths(
        self,
        manifest_paths: Iterable[Path],
        *,
        repo_root: Path,
        ontology_path: Path,
    ) -> None:
        for manifest_path in sorted(manifest_paths, key=lambda path: str(path)):
            loaded = load_plugin(
                manifest_path,
                repo_root=repo_root,
                ontology_path=ontology_path,
            )
            plugin_id = str(loaded.manifest["plugin_id"])
            if plugin_id in self._plugins:
                raise PluginContractError(f"duplicate plugin_id: {plugin_id}")
            self._plugins[plugin_id] = loaded

    def get(self, plugin_id: str) -> LoadedPlugin:
        try:
            return self._plugins[plugin_id]
        except KeyError as exc:
            raise PluginContractError(f"unknown plugin_id: {plugin_id}") from exc

    def plugin_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._plugins))


class OfficialCaptureConnectorAdapter(BaseConnector):
    """Replay exact official bytes through an existing connector without fake fallback."""

    def __init__(
        self,
        delegate: BaseConnector,
        *,
        official_url: str,
        capture_path: Path,
        capture_sha256: str,
    ) -> None:
        self.delegate = delegate
        self.source_id = delegate.source_id
        self.ingest_mode = getattr(delegate, "ingest_mode", "mandates")
        self.official_url = official_url
        self.capture_path = capture_path
        self.capture_sha256 = capture_sha256

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        del timeout
        return url_override or self.official_url

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
        options: dict[str, Any] | None = None,
    ) -> Extracted:
        del from_file, options
        observed_sha = _sha256_path(self.capture_path)
        if observed_sha != self.capture_sha256:
            raise PluginContractError(
                f"official capture SHA mismatch for {self.capture_path}"
            )
        extracted = self.delegate.extract(
            raw_dir=raw_dir,
            timeout=timeout,
            from_file=self.capture_path,
            url_override=url_override,
            strict_network=strict_network,
        )
        return replace(
            extracted,
            source_url=self.official_url,
            resolved_url=self.official_url,
            note=f"official-capture-replay:{self.capture_sha256}",
        )

    def normalize(
        self, record: dict[str, Any], snapshot_date: str | None
    ) -> dict[str, Any] | None:
        normalize = getattr(self.delegate, "normalize", None)
        if not callable(normalize):
            raise PluginContractError("delegate connector has no normalize hook")
        return normalize(record, snapshot_date)


__all__ = [
    "PLUGIN_API_VERSION",
    "PLUGIN_MANIFEST_SCHEMA_VERSION",
    "AcquiredArtifact",
    "ConnectorPlugin",
    "FactBatch",
    "LifecycleHook",
    "LoadedPlugin",
    "NormalizerPlugin",
    "OfficialCaptureConnectorAdapter",
    "ParserPlugin",
    "PluginContext",
    "PluginContractError",
    "PluginRegistry",
    "PluginType",
    "SourceRecordEnvelope",
    "WorkItemRef",
    "load_plugin",
    "load_plugin_manifest",
    "validate_plugin_manifest",
]
