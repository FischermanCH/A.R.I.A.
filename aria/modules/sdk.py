"""Versioned public SDK contracts for installable ARIA modules."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

SDK_API_VERSION = "1.0"


ModuleManifest = Mapping[str, Any]
ModuleManifestProvider = Callable[[], ModuleManifest]


class MetaCatalogProjectionProvider(Protocol):
    """Provider for existing MetaCatalogDocument-compatible payloads."""

    def documents(self) -> Iterable[Mapping[str, Any]]:
        """Yield projection documents; callers own validation and indexing."""


@dataclass(frozen=True, slots=True)
class OperationContract:
    module_id: str
    operation_id: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    effect: str = "read_only"
    confirmation_required: bool = False


@dataclass(frozen=True, slots=True)
class NativeToolContract:
    owner_module_id: str
    name: str
    description: str
    input_schema: Mapping[str, Any]
    effect: str
    confirmation_required: bool
    source_authority: str
    user_scoped: bool
    rollout_flag: str
    order: int = 100
    terminal: bool = False
    relay_result_content: bool = False
    required_connection_kinds: tuple[str, ...] = ()

    def provider_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
        }


@dataclass(frozen=True, slots=True)
class NativeToolContext:
    user_id: str
    auth_role: str = ""
    request_id: str = ""


@dataclass(frozen=True, slots=True)
class NativeToolResult:
    content: str
    intent: str
    actionable_arguments: Mapping[str, Any] | None = None
    actionable_outcome: str = ""
    activity: Mapping[str, Any] | None = None
    suggestion: Mapping[str, Any] | None = None
    images: tuple[tuple[str, str], ...] = ()


NativeToolHandler = Callable[[NativeToolContext, Mapping[str, Any]], Awaitable[NativeToolResult]]
NativeToolConfirmationPreview = Callable[[NativeToolContext, Mapping[str, Any]], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class NativeToolBinding:
    contract: NativeToolContract
    handler: NativeToolHandler
    confirmation_preview: NativeToolConfirmationPreview | None = None


@dataclass(frozen=True, slots=True)
class OperationPlan:
    module_id: str
    operation_id: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    source_authority: str = ""


@dataclass(frozen=True, slots=True)
class EffectDeclaration:
    effect: str
    targets: Sequence[str] = ()
    confirmation_required: bool = False


@dataclass(frozen=True, slots=True)
class Evidence:
    source: str
    summary: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModuleResult:
    module_id: str
    operation_id: str
    status: str
    evidence: Sequence[Evidence] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModuleError:
    module_id: str
    code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class ConfigContribution:
    namespace: str
    schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SecretContribution:
    namespace: str
    fields: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class StorageNamespace:
    namespace: str
    reversible: bool = True


@dataclass(frozen=True, slots=True)
class RouteContribution:
    path: str
    methods: Sequence[str] = ("GET",)


@dataclass(frozen=True, slots=True)
class UIContribution:
    nav_node_id: str = ""
    templates: Sequence[str] = ()
    static: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class RecipeStepContribution:
    step_type: str
    schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EventSubscription:
    topic: str
    handler: str


@dataclass(frozen=True, slots=True)
class JobContribution:
    job_id: str
    handler: str
    schedule: str = ""
