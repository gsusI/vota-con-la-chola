from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    name: str
    scope: str
    default_url: str
    format: str
    fallback_file: str
    min_records_loaded_strict: int | None = None
    license: str | None = None
    homepage_url: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, source_id: str, config: Mapping[str, Any]) -> "SourceDefinition":
        return cls(
            source_id=source_id,
            name=str(config["name"]),
            scope=str(config["scope"]),
            default_url=str(config["default_url"]),
            format=str(config["format"]),
            fallback_file=str(config["fallback_file"]),
            min_records_loaded_strict=_optional_int(config.get("min_records_loaded_strict")),
            license=_optional_str(config.get("license")),
            homepage_url=_optional_str(config.get("homepage_url")),
            metadata={
                str(k): v
                for k, v in config.items()
                if k
                not in {
                    "name",
                    "scope",
                    "default_url",
                    "format",
                    "fallback_file",
                    "min_records_loaded_strict",
                    "license",
                    "homepage_url",
                }
            },
        )

    def to_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "name": self.name,
            "scope": self.scope,
            "default_url": self.default_url,
            "format": self.format,
            "fallback_file": self.fallback_file,
        }
        if self.min_records_loaded_strict is not None:
            config["min_records_loaded_strict"] = self.min_records_loaded_strict
        if self.license is not None:
            config["license"] = self.license
        if self.homepage_url is not None:
            config["homepage_url"] = self.homepage_url
        config.update(dict(self.metadata))
        return config


def source_config_mapping(definitions: Iterable[SourceDefinition]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        if definition.source_id in out:
            raise ValueError(f"Duplicate source_id: {definition.source_id}")
        out[definition.source_id] = definition.to_config()
    return out


def source_definitions_from_config(source_config: Mapping[str, Mapping[str, Any]]) -> tuple[SourceDefinition, ...]:
    return tuple(SourceDefinition.from_config(source_id, config) for source_id, config in source_config.items())


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
