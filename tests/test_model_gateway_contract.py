from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_provider_runtime_calls_stay_behind_metered_clients() -> None:
    allowed_runtime_call_files = {
        Path("aria/core/llm_client.py"),
        Path("aria/core/embedding_client.py"),
    }
    blocked_runtime_markers = (
        "from litellm import completion",
        "from litellm import acompletion",
        "from litellm import embedding",
        "from litellm import aembedding",
        "litellm.completion",
        "litellm.acompletion",
        "litellm.embedding",
        "litellm.aembedding",
        "from openai import OpenAI",
        "from openai import AsyncOpenAI",
        "import openai",
        "openai.OpenAI",
        "openai.AsyncOpenAI",
        "client.chat.completions.create",
        "client.embeddings.create",
        "from anthropic import Anthropic",
        "from anthropic import AsyncAnthropic",
        "import anthropic",
        "anthropic.Anthropic",
        "anthropic.AsyncAnthropic",
        "client.messages.create",
    )
    violations: list[str] = []

    for path in sorted((PROJECT_ROOT / "aria").rglob("*.py")):
        rel_path = path.relative_to(PROJECT_ROOT)
        text = path.read_text(encoding="utf-8")
        has_runtime_call = any(marker in text for marker in blocked_runtime_markers)
        if has_runtime_call and rel_path not in allowed_runtime_call_files:
            violations.append(str(rel_path))

    assert violations == []
