"""Runtime assembly of owner-declared native tools from active module manifests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
import hashlib
from importlib import import_module
import logging
import math
import time
from typing import Any

from aria.modules.sdk import NativeToolBinding

_PROVIDER_SYMBOL = "native_tool_contributions"
NATIVE_TOOL_RELEVANCE_THRESHOLD = 40
NATIVE_TOOL_RELEVANCE_TOP_K = 16
NativeToolRelevanceSelector = Callable[[str, Sequence[NativeToolBinding], int], Awaitable[Sequence[str]]]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NativeToolSelectorTelemetry:
    active: bool = False
    selected: int = 0
    total: int = 0
    duration_ms: int = 0
    fallback: bool = False


class EmbeddingNativeToolRelevanceSelector:
    """Rank an already-authorized Native Tool catalog by semantic relevance."""

    def __init__(
        self, *, embedding_client: Any,
        descriptor_cache: MutableMapping[tuple[str, str], tuple[float, ...]],
    ) -> None:
        self.embedding_client = embedding_client
        self.descriptor_cache = descriptor_cache
        self.last_telemetry = NativeToolSelectorTelemetry()

    @staticmethod
    def _descriptor(binding: NativeToolBinding) -> tuple[tuple[str, str], str]:
        contract = binding.contract
        text = f"name: {contract.name}\ndescription: {contract.description}"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return (contract.name, digest), text

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(float(a) * float(b) for a, b in zip(left, right))
        left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
        right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
        if left_norm <= 0.0 or right_norm <= 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _fallback(
        self, tools: Sequence[NativeToolBinding], limit: int, *, start: float, reason: str,
    ) -> tuple[str, ...]:
        names = tuple(binding.contract.name for binding in tools[:limit])
        self.last_telemetry = NativeToolSelectorTelemetry(
            active=True,
            selected=len(names),
            total=len(tools),
            duration_ms=max(0, int((time.perf_counter() - start) * 1000)),
            fallback=True,
        )
        LOGGER.warning("Native Tool relevance selector fallback: %s", reason)
        return names

    async def __call__(
        self, message: str, tools: Sequence[NativeToolBinding], top_k: int,
    ) -> tuple[str, ...]:
        start = time.perf_counter()
        limit = min(len(tools), max(0, int(top_k)))
        if limit == 0:
            self.last_telemetry = NativeToolSelectorTelemetry(
                active=True, selected=0, total=len(tools), duration_ms=0, fallback=False,
            )
            return ()

        embed = getattr(self.embedding_client, "embed", None)
        if not callable(embed):
            return self._fallback(tools, limit, start=start, reason="embedding_client_unavailable")

        descriptors = [self._descriptor(binding) for binding in tools]
        missing = [(key, text) for key, text in descriptors if key not in self.descriptor_cache]
        try:
            response = await embed(
                [str(message or ""), *(text for _key, text in missing)],
                source="native_agent",
                operation="tool_relevance_selector",
            )
            vectors = tuple(getattr(response, "vectors", ()) or ())
            if len(vectors) != 1 + len(missing):
                raise ValueError("embedding_vector_count_mismatch")
            message_vector = tuple(float(value) for value in vectors[0])
            if not message_vector:
                raise ValueError("embedding_message_vector_empty")
            for (key, _text), vector in zip(missing, vectors[1:]):
                clean_vector = tuple(float(value) for value in vector)
                if not clean_vector or len(clean_vector) != len(message_vector):
                    raise ValueError("embedding_descriptor_vector_invalid")
                self.descriptor_cache[key] = clean_vector
            ranked = sorted(
                enumerate(tools),
                key=lambda item: (
                    -self._cosine(message_vector, self.descriptor_cache.get(descriptors[item[0]][0], ())),
                    item[0],
                ),
            )
            names = tuple(binding.contract.name for _index, binding in ranked[:limit])
        except Exception as exc:
            return self._fallback(
                tools, limit, start=start, reason=f"embedding_failed:{type(exc).__name__}",
            )

        self.last_telemetry = NativeToolSelectorTelemetry(
            active=True,
            selected=len(names),
            total=len(tools),
            duration_ms=max(0, int((time.perf_counter() - start) * 1000)),
            fallback=False,
        )
        return names


def _provider_paths(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    suffix = f"::{_PROVIDER_SYMBOL}"
    return tuple(str(item) for item in manifest.get("integration_points", ()) if str(item).endswith(suffix))


def _load_provider(path: str):  # noqa: ANN202
    file_path, symbol = path.split("::", 1)
    module_name = file_path.removesuffix(".py").replace("/", ".")
    return getattr(import_module(module_name), symbol)


def assemble_native_tools(
    active_manifests: Mapping[str, Mapping[str, Any]], *, runtime_owner: Any,
    enabled_rollout_flags: set[str],
) -> tuple[NativeToolBinding, ...]:
    bindings: list[NativeToolBinding] = []
    for module_id, manifest in sorted(active_manifests.items()):
        for provider_path in _provider_paths(manifest):
            for binding in _load_provider(provider_path)(runtime_owner):
                if binding.contract.owner_module_id != module_id:
                    raise ValueError("native_tool_owner_mismatch")
                if binding.contract.rollout_flag in enabled_rollout_flags:
                    bindings.append(binding)
    names = [binding.contract.name for binding in bindings]
    if len(names) != len(set(names)):
        raise ValueError("native_tool_name_duplicate")
    return tuple(sorted(bindings, key=lambda binding: (binding.contract.order, binding.contract.name)))


def filter_tools_by_configured_connections(
    tools: Sequence[NativeToolBinding], settings: Any,
) -> tuple[NativeToolBinding, ...]:
    connections = getattr(settings, "connections", None)
    return tuple(
        tool for tool in tools
        if not tool.contract.required_connection_kinds
        or any(
            isinstance(getattr(connections, kind, None), Mapping)
            and bool(getattr(connections, kind, None))
            for kind in tool.contract.required_connection_kinds
        )
    )


async def select_relevant_native_tools(
    message: str, tools: Sequence[NativeToolBinding], *,
    selector: NativeToolRelevanceSelector | None,
    threshold: int = NATIVE_TOOL_RELEVANCE_THRESHOLD,
    top_k: int = NATIVE_TOOL_RELEVANCE_TOP_K,
) -> tuple[NativeToolBinding, ...]:
    if len(tools) <= threshold:
        return tuple(tools)
    core_tools = tuple(tool for tool in tools if not tool.contract.name.startswith("mcp__"))
    extra_tools = tuple(tool for tool in tools if tool.contract.name.startswith("mcp__"))
    if not extra_tools:
        return tuple(tools)
    if selector is None:
        raise RuntimeError("native_tool_relevance_selector_unavailable")
    selected_names = tuple(dict.fromkeys(str(name) for name in await selector(message, extra_tools, top_k)))
    tools_by_name = {tool.contract.name: tool for tool in extra_tools}
    selected_extras = tuple(
        tools_by_name[name] for name in selected_names if name in tools_by_name
    )[:top_k]
    return (*core_tools, *selected_extras)
