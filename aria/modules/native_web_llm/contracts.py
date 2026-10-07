from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NativeWebCitation:
    url: str
    title: str = ""
    cited_text: str = ""
    source: str = ""


@dataclass(frozen=True, slots=True)
class NativeWebRequest:
    question: str
    language: str = "de"
    current_date: str = ""
    recent_history: tuple[tuple[str, str], ...] = ()
    prior_evidence: tuple[NativeWebCitation, ...] = ()
    allowed_domains: tuple[str, ...] = ()
    required_url_prefixes: tuple[str, ...] = ()
    authority_mode: str = "prefer_primary"
    search_context_size: str = "low"
    max_search_uses: int = 3
    max_output_tokens: int = 1200


@dataclass(frozen=True, slots=True)
class NativeWebResult:
    answer: str
    citations: tuple[NativeWebCitation, ...]
    model: str
    provider_shape: str
    native_search_uses: int
    usage: dict[str, int]
    duration_ms: int
    finish_reason: str = ""
    errors: tuple[str, ...] = ()
    provider_requests: int = 1
    main_llm_requests: int = 0
    retries: int = 0
    metered: bool = False
    cost_usd: float | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(
            self.answer.strip()
            and self.citations
            and 1 <= self.native_search_uses <= 3
            and self.provider_requests == 1
            and self.main_llm_requests == 0
            and self.retries == 0
            and not self.errors
        )
