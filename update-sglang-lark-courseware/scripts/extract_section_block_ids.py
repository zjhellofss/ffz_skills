#!/usr/bin/env python3
"""Extract block IDs strictly between two boundary blocks in docs +fetch JSON."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-id", required=True)
    parser.add_argument("--end-id", required=True)
    parser.add_argument("--format", choices=("csv", "lines", "json"), default="csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.load(sys.stdin)
    try:
        content = payload["data"]["document"]["content"]
    except (KeyError, TypeError) as exc:
        raise SystemExit(f"missing data.document.content: {exc}")

    root = ET.fromstring(content)
    ids: list[str] = []
    active = False
    found_start = False
    found_end = False

    for block in root:
        block_id = block.attrib.get("id")
        if block_id == args.start_id:
            active = True
            found_start = True
            continue
        if block_id == args.end_id:
            found_end = True
            break
        if active:
            ids.extend(
                element.attrib["id"]
                for element in block.iter()
                if "id" in element.attrib
            )

    if not found_start:
        raise SystemExit(f"start block not found: {args.start_id}")
    if not found_end:
        raise SystemExit(f"end block not found after start: {args.end_id}")

    if args.format == "csv":
        print(",".join(ids))
    elif args.format == "lines":
        print("\n".join(ids))
    else:
        json.dump(ids, sys.stdout, ensure_ascii=False)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
