from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from aria.core.release_meta import read_release_meta
from aria.core.update_check import get_update_status


def _base_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _version_snapshot(*, check_updates: bool = False) -> dict[str, object]:
    base_dir = _base_dir()
    release_meta = read_release_meta(base_dir)
    snapshot: dict[str, object] = {
        "version": release_meta["version"],
        "label": release_meta["label"],
    }
    if check_updates:
        update_status = get_update_status(base_dir, current_label=release_meta["label"], ttl_seconds=0)
        snapshot["update_status"] = {
            "latest_label": str(update_status.get("latest_label", "") or release_meta["label"]),
            "update_available": bool(update_status.get("update_available")),
            "checked_at": str(update_status.get("checked_at", "") or ""),
            "source": str(update_status.get("source", "") or ""),
        }
    return snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ARIA CLI")
    parser.add_argument("--version", action="store_true", help="Show the installed ARIA release label and exit.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON for version output.")

    subparsers = parser.add_subparsers(dest="command")
    version_check = subparsers.add_parser(
        "version-check",
        help="Show installed version and the latest public release status.",
    )
    version_check.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    wants_json = bool(getattr(args, "json", False))
    if args.command == "version-check":
        snapshot = _version_snapshot(check_updates=True)
        if wants_json:
            print(json.dumps(snapshot, ensure_ascii=False))
            return 0
        update_status = dict(snapshot.get("update_status", {}) or {})
        latest_label = str(update_status.get("latest_label", "") or snapshot["label"])
        status_text = "update-available" if bool(update_status.get("update_available")) else "up-to-date"
        checked_at = str(update_status.get("checked_at", "") or "-")
        source = str(update_status.get("source", "") or "-")
        print(f"installed={snapshot['label']}")
        print(f"latest={latest_label}")
        print(f"status={status_text}")
        print(f"checked_at={checked_at}")
        print(f"source={source}")
        return 0

    if args.version:
        snapshot = _version_snapshot(check_updates=False)
        if wants_json:
            print(json.dumps(snapshot, ensure_ascii=False))
        else:
            print(snapshot["label"])
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
