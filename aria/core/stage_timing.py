from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(slots=True)
class StageTimingLedger:
    enabled: bool = False
    _rows: list[tuple[str, int]] = field(default_factory=list)

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            if self.enabled:
                self.add(name, int((time.perf_counter() - start) * 1000))

    def add(self, name: str, duration_ms: int) -> None:
        clean_name = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(name or "").strip())
        if not clean_name:
            return
        self._rows.append((clean_name[:80], max(0, int(duration_ms or 0))))

    def debug_lines(self) -> list[str]:
        if not self.enabled or not self._rows:
            return []
        return [f"Routing Debug: stage_timing stage={name} ms={duration_ms}" for name, duration_ms in self._rows]
