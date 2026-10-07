"""Process-local compatibility for model parameters rejected by providers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from threading import RLock
from typing import Any


Completion = Callable[..., Awaitable[Any]]
TemperatureOmittedCallback = Callable[[str], None]

_TEMPERATURE_OMITTED_MODELS: set[str] = set()
_COMPAT_LOCK = RLock()
_TEMPERATURE_REJECTION_MARKERS = (
    "deprecated",
    "not supported",
    "unsupported",
    "not allowed",
)


def _model_key(model: object) -> str:
    return str(model or "").strip()


def temperature_omitted_for_model(model: object) -> bool:
    key = _model_key(model)
    if not key:
        return False
    with _COMPAT_LOCK:
        return key in _TEMPERATURE_OMITTED_MODELS


def reset_model_parameter_compatibility() -> None:
    """Reset process-local evidence; intended for isolated tests only."""

    with _COMPAT_LOCK:
        _TEMPERATURE_OMITTED_MODELS.clear()


def _remember_temperature_omission(model: str) -> None:
    if not model:
        return
    with _COMPAT_LOCK:
        _TEMPERATURE_OMITTED_MODELS.add(model)


def _is_bad_request(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    try:
        if int(status) == 400:
            return True
    except (TypeError, ValueError):
        pass
    names = " ".join(cls.__name__.casefold() for cls in type(exc).__mro__)
    return "badrequest" in names or "invalidrequest" in names or "invalid_request" in names


def is_temperature_parameter_rejection(exc: BaseException) -> bool:
    if not _is_bad_request(exc):
        return False
    message = str(exc or "").casefold()
    return "temperature" in message and any(marker in message for marker in _TEMPERATURE_REJECTION_MARKERS)


async def call_with_model_parameter_compat(
    completion: Completion,
    kwargs: Mapping[str, Any],
    *,
    on_temperature_omitted: TemperatureOmittedCallback | None = None,
) -> Any:
    """Call once, retrying one rejected numeric temperature as ``None``.

    LiteLLM omits optional parameters whose value is ``None``. An exact
    provider rejection becomes process-local evidence for the exact model
    string, so later calls omit temperature from their first request.
    """

    request = dict(kwargs)
    model = _model_key(request.get("model"))
    if temperature_omitted_for_model(model):
        request["temperature"] = None
    sent_temperature = request.get("temperature")
    try:
        return await completion(**request)
    except Exception as exc:
        if sent_temperature is None or not is_temperature_parameter_rejection(exc):
            raise
        _remember_temperature_omission(model)
        if on_temperature_omitted is not None:
            on_temperature_omitted(model)
        retry = dict(request)
        retry["temperature"] = None
        return await completion(**retry)
