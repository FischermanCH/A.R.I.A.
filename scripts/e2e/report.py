#!/usr/bin/env python3
"""Print the compact scenario table from pytest's JUnit artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("junit", type=Path)
    args = parser.parse_args()
    if not args.junit.exists():
        print("E2E RESULT: no JUnit report produced")
        return
    root = ET.parse(args.junit).getroot()
    rows: list[tuple[str, str, str]] = []
    for case in root.iter("testcase"):
        name = str(case.attrib.get("name") or "unknown")
        duration = f"{float(case.attrib.get('time') or 0.0):.2f}s"
        if case.find("failure") is not None:
            status = "FAIL"
        elif case.find("error") is not None:
            status = "ERROR"
        elif case.find("skipped") is not None:
            status = "SKIP"
        else:
            status = "PASS"
        rows.append((name, status, duration))
    print("\nARIA isolated E2E result")
    print("scenario                                                       status  time")
    print("-" * 78)
    for name, status, duration in rows:
        print(f"{name[:61]:61} {status:6} {duration:>8}")


if __name__ == "__main__":
    main()
