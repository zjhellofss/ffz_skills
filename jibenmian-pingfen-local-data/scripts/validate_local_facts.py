#!/usr/bin/env python3
"""Validate facts generated directly from the local structured CSV dataset."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "fact_id", "company", "metric", "period", "period_type", "scope",
    "attribution", "value", "unit", "currency", "status", "audit_status",
    "source_file", "locator_type", "locator", "source_line_item", "formula",
    "input_fact_ids", "notes",
}
VALID_STATUSES = {"reported", "calculated"}
VALID_AUDIT_STATUSES = {"audited", "unaudited"}


def _cell(row: dict[str | None, Any], key: str) -> str:
    value = row.get(key, "")
    return "" if value is None else str(value).strip()


def _decimal(raw: str, where: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{where}: invalid decimal {raw!r}") from exc
    if not value.is_finite():
        raise ValueError(f"{where}: value must be finite")
    return value


def _read_source_row(path: Path, line_no: int) -> tuple[list[str], dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        for current, row in enumerate(reader, start=2):
            if current == line_no:
                return fields, {key: _cell(row, key) for key in fields}
    raise ValueError(f"{path}: CSV row {line_no} does not exist")


def validate_file(facts_path: Path, source_root: Path | None) -> dict[str, Any]:
    """Validate schema, lineage, local CSV locators, and calculation dependencies."""
    issues: list[dict[str, str]] = []

    def issue(code: str, location: str, message: str) -> None:
        issues.append({"code": code, "location": location, "message": message})

    if source_root is None:
        issue("SOURCE_ROOT_REQUIRED", str(facts_path), "local fact validation requires source_root")
        return {"ok": False, "issues": issues, "fact_count": 0, "source_fact_count": 0}
    root = source_root.resolve()
    if not root.exists():
        issue("SOURCE_ROOT_MISSING", str(root), "source_root does not exist")
        return {"ok": False, "issues": issues, "fact_count": 0, "source_fact_count": 0}

    facts: dict[str, dict[str, str]] = {}
    with facts_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        duplicates = sorted(name for name, count in Counter(fields).items() if count > 1)
        for name in duplicates:
            issue("DUPLICATE_HEADER", str(facts_path), f"duplicate header: {name}")
        for name in sorted(REQUIRED_FIELDS - set(fields)):
            issue("MISSING_HEADER", str(facts_path), f"missing header: {name}")
        if issues:
            return {"ok": False, "issues": issues, "fact_count": 0, "source_fact_count": 0}

        for line_no, raw_row in enumerate(reader, start=2):
            row = {key: _cell(raw_row, key) for key in fields}
            fact_id = row["fact_id"]
            where = f"{facts_path}:{line_no}"
            if not fact_id:
                issue("EMPTY_FACT_ID", where, "fact_id is empty")
                continue
            if fact_id in facts:
                issue("DUPLICATE_FACT_ID", where, f"duplicate fact_id: {fact_id}")
                continue
            facts[fact_id] = row
            if row["status"] not in VALID_STATUSES:
                issue("BAD_STATUS", fact_id, f"invalid status: {row['status']}")
            if row["audit_status"] not in VALID_AUDIT_STATUSES:
                issue("BAD_AUDIT_STATUS", fact_id, f"invalid audit_status: {row['audit_status']}")
            try:
                _decimal(row["value"], fact_id)
            except ValueError as exc:
                issue("BAD_VALUE", fact_id, str(exc))

    source_cache: dict[tuple[Path, int], tuple[list[str], dict[str, str]]] = {}
    source_fact_count = 0
    for fact_id, fact in facts.items():
        dependency_ids = [
            item.strip() for item in fact["input_fact_ids"].split(";") if item.strip()
        ]
        for dependency_id in dependency_ids:
            if dependency_id not in facts:
                issue("MISSING_DEPENDENCY", fact_id, f"unknown input_fact_id: {dependency_id}")

        if fact["status"] == "calculated":
            if not fact["formula"]:
                issue("MISSING_FORMULA", fact_id, "calculated fact has no formula")
            if not dependency_ids and fact["formula"] != "audit_opinion_to_issue_flag":
                issue("MISSING_DEPENDENCY", fact_id, "calculated fact has no dependencies")
            for dependency_id in dependency_ids:
                dependency = facts.get(dependency_id)
                if (
                    dependency
                    and fact["audit_status"] == "audited"
                    and dependency["audit_status"] != "audited"
                ):
                    issue(
                        "AUDIT_LINEAGE_MISMATCH",
                        fact_id,
                        f"audited calculation depends on unaudited fact {dependency_id}",
                    )

        if not fact["source_file"]:
            if fact["status"] == "reported":
                issue("MISSING_SOURCE", fact_id, "reported fact has no source_file")
            continue

        source_fact_count += 1
        relative = Path(fact["source_file"])
        source_path = (root / relative).resolve()
        try:
            source_path.relative_to(root)
        except ValueError:
            issue("SOURCE_ESCAPE", fact_id, f"source_file escapes source_root: {relative}")
            continue
        if not source_path.is_file():
            issue("SOURCE_MISSING", fact_id, f"source file does not exist: {relative}")
            continue
        if fact["locator_type"] != "csv_row":
            issue("BAD_LOCATOR_TYPE", fact_id, "source-backed fact must use csv_row")
            continue
        try:
            line_no = int(fact["locator"])
        except ValueError:
            issue("BAD_LOCATOR", fact_id, f"invalid CSV row locator: {fact['locator']!r}")
            continue
        try:
            key = (source_path, line_no)
            if key not in source_cache:
                source_cache[key] = _read_source_row(source_path, line_no)
            fields, source_row = source_cache[key]
        except ValueError as exc:
            issue("BAD_LOCATOR", fact_id, str(exc))
            continue
        line_item = fact["source_line_item"]
        if line_item not in fields:
            issue("SOURCE_COLUMN_MISSING", fact_id, f"source column does not exist: {line_item}")
            continue

        source_value = source_row[line_item]
        if fact["formula"] == "audit_opinion_to_issue_flag":
            expected = Decimal("0") if source_value == "标准无保留意见" else Decimal("1")
            try:
                if _decimal(fact["value"], fact_id) != expected:
                    issue(
                        "SOURCE_VALUE_MISMATCH",
                        fact_id,
                        f"audit issue flag does not match opinion {source_value!r}",
                    )
            except ValueError:
                pass
            continue
        try:
            if _decimal(source_value, f"{fact_id}/source") != _decimal(fact["value"], fact_id):
                issue(
                    "SOURCE_VALUE_MISMATCH",
                    fact_id,
                    f"fact value {fact['value']} differs from source value {source_value}",
                )
        except ValueError as exc:
            issue("SOURCE_VALUE_INVALID", fact_id, str(exc))

    return {
        "ok": not issues,
        "validator": "local-structured-csv-v1",
        "fact_count": len(facts),
        "source_fact_count": source_fact_count,
        "source_root": str(root),
        "issues": issues,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("facts", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = validate_file(args.facts, args.source_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload["ok"]:
        print(
            f"OK: {payload['fact_count']} facts, "
            f"{payload['source_fact_count']} source-backed facts"
        )
    else:
        for item in payload["issues"]:
            print(f"{item['code']}@{item['location']}: {item['message']}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
