"""Privacy-first native-agent trace persistence and bounded retention."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any


def _encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _bounded_summary(row: dict[str, Any]) -> str:
    status = str(row.get("status") or row.get("outcome_status") or row.get("event") or "unknown")[:80]
    reason = str(row.get("reason") or row.get("error_code") or "")[:120]
    return f"status={status}" + (f" reason={reason}" if reason else "")


class NativeTraceStore:
    def __init__(
        self, root: Path, *, detail_level: str = "minimal", retention_days: int = 7,
        max_mebibytes: int = 50,
    ) -> None:
        self.root = Path(root)
        self.detail_level = "full" if str(detail_level).lower() == "full" else "minimal"
        self.retention_days = max(1, min(int(retention_days or 7), 365))
        self.max_bytes = max(1, int(max_mebibytes or 50)) * 1024 * 1024

    def _row(self, turn_id: str, row: dict[str, Any]) -> dict[str, Any]:
        if self.detail_level == "full":
            return {
                "turn_id": str(turn_id), "timestamp": time.time(),
                **json.loads(json.dumps(row, ensure_ascii=True, default=str)),
            }
        arguments = row.get("arguments", row.get("args", row.get("tool_arguments", {})))
        output = row.get("result", row.get("output", row.get("content", row.get("tool_result", ""))))
        argument_bytes = _encoded(arguments)
        output_bytes = _encoded(output)
        return {
            "turn_id": str(turn_id)[:128],
            "job_id": str(row.get("job_id") or "")[:128],
            "timestamp": time.time(),
            "step_index": max(0, int(row.get("step_index") or 0)),
            "tool_name": str(row.get("tool_name") or row.get("tool") or row.get("chosen_tool") or "")[:160],
            "effect": str(row.get("effect") or "")[:32],
            "outcome_status": str(row.get("status") or row.get("final_outcome") or row.get("event") or "unknown")[:80],
            "argument_bytes": len(argument_bytes),
            "argument_sha256": hashlib.sha256(argument_bytes).hexdigest(),
            "output_bytes": len(output_bytes),
            "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
            "summary": _bounded_summary(row)[:240],
        }

    def write(self, *, turn_id: str, row: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{str(turn_id or 'turn')[:120]}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(self._row(turn_id, row), ensure_ascii=True, separators=(",", ":")) + "\n")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return path

    def sweep(self, *, now: float | None = None) -> dict[str, int]:
        self.root.mkdir(parents=True, exist_ok=True)
        current = float(time.time() if now is None else now)
        stats = {"examined": 0, "removed_retention": 0, "removed_size": 0, "bytes_removed": 0}
        lock_path = self.root / ".sweep.lock"
        with lock_path.open("a+") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return stats
            files = sorted(
                (path for path in self.root.glob("*.jsonl") if path.is_file()),
                key=lambda path: (path.stat().st_mtime, path.name),
            )
            cutoff = current - self.retention_days * 86400
            kept: list[Path] = []
            for path in files:
                stats["examined"] += 1
                try:
                    size = path.stat().st_size
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        stats["removed_retention"] += 1
                        stats["bytes_removed"] += size
                    else:
                        kept.append(path)
                except OSError:
                    continue
            total = sum(path.stat().st_size for path in kept if path.exists())
            for path in kept:
                if total <= self.max_bytes:
                    break
                try:
                    size = path.stat().st_size
                    path.unlink()
                    total -= size
                    stats["removed_size"] += 1
                    stats["bytes_removed"] += size
                except OSError:
                    continue
        try:
            os.chmod(lock_path, 0o600)
        except OSError:
            pass
        return stats
