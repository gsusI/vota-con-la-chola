from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


class CanonicalStep(StrEnum):
    REGISTER = "register"
    ACQUIRE = "acquire"
    NORMALIZE = "normalize"
    ENRICH = "enrich"
    PUBLISH = "publish"


class RuntimeShape(StrEnum):
    NETWORK_STRICT = "network_strict"
    SAMPLE_REPLAY = "sample_replay"
    MANUAL_REPLAY = "manual_replay"
    BROWSER_ASSISTED = "browser_assisted"
    ARCHIVE_FALLBACK = "archive_fallback"
    QUEUE_RUNTIME = "queue_runtime"
    STATIC_PUBLISH = "static_publish"


CANONICAL_STEPS: tuple[CanonicalStep, ...] = (
    CanonicalStep.REGISTER,
    CanonicalStep.ACQUIRE,
    CanonicalStep.NORMALIZE,
    CanonicalStep.ENRICH,
    CanonicalStep.PUBLISH,
)


@dataclass(frozen=True)
class WorkflowPlan:
    workflow_id: str
    label: str
    steps: tuple[CanonicalStep, ...] = CANONICAL_STEPS
    runtime_shapes: tuple[RuntimeShape, ...] = (RuntimeShape.NETWORK_STRICT, RuntimeShape.SAMPLE_REPLAY)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_steps = tuple(CanonicalStep(step) for step in self.steps)
        if len(normalized_steps) > 5:
            raise ValueError("workflow steps must be <= 5")
        if len(set(normalized_steps)) != len(normalized_steps):
            raise ValueError("workflow steps must be unique")
        if not normalized_steps:
            raise ValueError("workflow must declare at least one step")
        object.__setattr__(self, "steps", normalized_steps)
        object.__setattr__(self, "runtime_shapes", tuple(RuntimeShape(shape) for shape in self.runtime_shapes))

    def as_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "label": self.label,
            "steps": [str(step.value) for step in self.steps],
            "runtime_shapes": [str(shape.value) for shape in self.runtime_shapes],
            "metadata": dict(self.metadata),
        }


def default_publicdata_workflows() -> tuple[WorkflowPlan, ...]:
    return (
        WorkflowPlan(
            workflow_id="representatives",
            label="Representatives",
            runtime_shapes=(
                RuntimeShape.NETWORK_STRICT,
                RuntimeShape.SAMPLE_REPLAY,
                RuntimeShape.MANUAL_REPLAY,
            ),
        ),
        WorkflowPlan(
            workflow_id="parliamentary_evidence",
            label="Parliamentary evidence",
            runtime_shapes=(
                RuntimeShape.NETWORK_STRICT,
                RuntimeShape.SAMPLE_REPLAY,
                RuntimeShape.ARCHIVE_FALLBACK,
                RuntimeShape.QUEUE_RUNTIME,
            ),
        ),
        WorkflowPlan(
            workflow_id="document_recovery",
            label="Document recovery",
            runtime_shapes=(
                RuntimeShape.NETWORK_STRICT,
                RuntimeShape.ARCHIVE_FALLBACK,
                RuntimeShape.BROWSER_ASSISTED,
                RuntimeShape.MANUAL_REPLAY,
            ),
        ),
        WorkflowPlan(
            workflow_id="snapshot_publish",
            label="Snapshot publish",
            runtime_shapes=(RuntimeShape.STATIC_PUBLISH,),
        ),
    )
