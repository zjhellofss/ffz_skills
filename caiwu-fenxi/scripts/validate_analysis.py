#!/usr/bin/env python3
"""Validate a financial-analysis fact ledger or lint a Markdown report.

The checks are intentionally conservative. Errors identify deterministic
contract violations. Warnings identify items that require human review and can
be promoted to a failing exit status with ``--strict``.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence


REQUIRED_FACT_COLUMNS = [
    "fact_id",
    "company",
    "metric",
    "period",
    "period_type",
    "scope",
    "attribution",
    "value",
    "unit",
    "currency",
    "status",
    "audit_status",
    "source_file",
    "locator_type",
    "locator",
    "source_line_item",
    "formula",
    "input_fact_ids",
    "notes",
]

ENUMS = {
    "period_type": {
        "instant",
        "quarter",
        "ytd",
        "half_year",
        "nine_month",
        "fy",
        "ttm",
        "other",
    },
    "attribution": {"total", "parent", "nci", "na"},
    "status": {"reported", "calculated", "unavailable"},
    "audit_status": {"audited", "reviewed", "unaudited", "mixed", "unknown"},
    "locator_type": {"pdf_page", "printed_page", "text_line", "section", "note"},
}

SOURCE_MARKER_RE = re.compile(r"(?i)(?:\[?\s*(?:来源|source)\s*[:：]|数据来源|data source)")
FACT_MARKER_RE = re.compile(r"\[F:([A-Za-z0-9_.:-]+)\]")
CLAIM_MARKER_RE = re.compile(
    r"\[C:([A-Za-z0-9_.:-]+)\|(source-stated|calculated|inference)\]",
    re.IGNORECASE,
)
FILE_RE = re.compile(r"(?i)(?:[\w\u3400-\u9fff ._()（）-]+\.(?:pdf|txt|html?|csv|xlsx?))|(?:\bS\d+\b)")
LOCATOR_RE = re.compile(
    r"(?i)(?:\bp{1,2}\.\s*\d+|\bpages?\s*\d+|第\s*\d+(?:\s*[-—–]\s*\d+)?\s*页|"
    r"(?:行|lines?)\s*\d+|(?:附注|note|section|章节|§|表)\s*[^\]\s;,，；]+)"
)
INVALID_PAGE_RE = re.compile(r"(?i)\bp\.(?!\s*\d)")
NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?%?")
FINANCE_TERMS_RE = re.compile(
    r"收入|营收|利润|毛利|现金流|资产|负债|权益|存货|应收|应付|研发|资本开支|"
    r"折旧|减值|补助|客户|供应商|产能|利用率|订单|收入确认|revenue|profit|margin|"
    r"cash flow|assets?|liabilit|inventory|receivable|capex|depreciation",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    location: str = ""


def add_issue(
    issues: list[Issue], severity: str, code: str, message: str, location: str = ""
) -> None:
    issues.append(Issue(severity=severity, code=code, message=message, location=location))


def parse_decimal(raw: str) -> Decimal | None:
    value = raw.strip()
    if not value:
        return None
    if "," in value:
        raise InvalidOperation("thousands separators are not allowed")
    number = Decimal(value)
    if not math.isfinite(float(number)):
        raise InvalidOperation("non-finite value")
    return number


def parse_tolerances(absolute: str, relative: str) -> tuple[Decimal, Decimal]:
    try:
        abs_tol = Decimal(absolute)
        rel_tol = Decimal(relative)
    except InvalidOperation as exc:
        raise ValueError("Tolerances must be valid decimal numbers") from exc
    if (
        not abs_tol.is_finite()
        or not rel_tol.is_finite()
        or abs_tol < 0
        or rel_tol < 0
    ):
        raise ValueError("Tolerances must be finite, non-negative decimal numbers")
    return abs_tol, rel_tol


def parse_numeric_ranges(raw: str) -> list[int] | None:
    text = raw.strip()
    if not re.fullmatch(r"\d+(?:\s*-\s*\d+)?(?:\s*,\s*\d+(?:\s*-\s*\d+)?)*", text):
        return None
    values: list[int] = []
    for part in text.split(","):
        bounds = [int(x.strip()) for x in part.split("-")]
        if len(bounds) == 1:
            values.append(bounds[0])
        elif bounds[0] <= bounds[1]:
            if bounds[1] - bounds[0] > 10000:
                return None
            values.extend(range(bounds[0], bounds[1] + 1))
        else:
            return None
    return values


def resolve_source(source_root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else source_root / path


def _pdf_page_count(path: Path, cache: dict[Path, int | None]) -> int | None:
    if path in cache:
        return cache[path]
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError:
        cache[path] = None
        return None
    try:
        with fitz.open(path) as document:
            count = document.page_count
    except Exception:
        count = -1
    cache[path] = count
    return count


def _text_lines(path: Path, cache: dict[Path, list[str]]) -> list[str]:
    if path not in cache:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            cache[path] = handle.read().splitlines()
    return cache[path]


def _pdf_page_text(path: Path, page: int, cache: dict[tuple[Path, int], str]) -> str:
    key = (path, page)
    if key in cache:
        return cache[key]
    import fitz  # type: ignore

    with fitz.open(path) as document:
        text = document.load_page(page - 1).get_text("text")
    cache[key] = text
    return text


def _normalize_lookup(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", text).lower()


def close_enough(actual: Decimal, expected: Decimal, abs_tol: Decimal, rel_tol: Decimal) -> bool:
    limit = abs_tol + rel_tol * max(abs(actual), abs(expected), Decimal("1"))
    return abs(actual - expected) <= limit


def safe_formula_value(formula: str, input_values: dict[str, Decimal]) -> Decimal:
    """Evaluate arithmetic only after replacing declared fact IDs with variables."""
    if len(formula) > 500:
        raise ValueError("formula is too long")
    if not input_values:
        raise ValueError("formula has no declared inputs")
    environment: dict[str, float] = {}
    variables: dict[str, str] = {}
    for index, fact_id in enumerate(sorted(input_values, key=len, reverse=True)):
        variable = f"__fact_{index}"
        variables[fact_id] = variable
        environment[variable] = float(input_values[fact_id])
    token_pattern = re.compile(
        r"(?<![A-Za-z0-9_.:])(?:"
        + "|".join(re.escape(fact_id) for fact_id in variables)
        + r")(?![A-Za-z0-9_.:])"
    )
    used: set[str] = set()

    def replace_fact(match: re.Match[str]) -> str:
        fact_id = match.group(0)
        used.add(fact_id)
        return variables[fact_id]

    expression = token_pattern.sub(replace_fact, formula)
    unused = sorted(set(input_values) - used)
    if unused:
        raise ValueError(f"formula does not reference declared input(s): {', '.join(unused)}")
    tree = ast.parse(expression, mode="eval")

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in environment:
            return environment[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                if abs(right) > 10:
                    raise ValueError("formula exponent is outside the safe range")
                return left**right
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "abs"
            and len(node.args) == 1
            and not node.keywords
        ):
            return abs(evaluate(node.args[0]))
        raise ValueError(f"unsupported formula element: {ast.dump(node, include_attributes=False)}")

    result = evaluate(tree)
    if not math.isfinite(result):
        raise ValueError("formula result is not finite")
    return Decimal(str(result))


def validate_facts(
    ledger: Path,
    source_root: Path,
    skip_source_check: bool,
    abs_tol: Decimal,
    rel_tol: Decimal,
) -> list[Issue]:
    issues: list[Issue] = []
    try:
        with ledger.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            if len(fieldnames) != len(set(fieldnames)):
                duplicates = sorted(
                    {name for name in fieldnames if fieldnames.count(name) > 1}
                )
                add_issue(
                    issues,
                    "ERROR",
                    "DUPLICATE_COLUMNS",
                    f"Duplicate CSV columns: {', '.join(duplicates)}",
                    str(ledger),
                )
                return issues
            missing = [name for name in REQUIRED_FACT_COLUMNS if name not in fieldnames]
            if missing:
                add_issue(
                    issues,
                    "ERROR",
                    "MISSING_COLUMNS",
                    f"Missing required columns: {', '.join(missing)}",
                    str(ledger),
                )
                return issues
            rows = []
            for row_number, raw in enumerate(reader, start=2):
                if None in raw:
                    add_issue(
                        issues,
                        "ERROR",
                        "MALFORMED_CSV_ROW",
                        "Row has more fields than the header",
                        f"{ledger}:{row_number}",
                    )
                    continue
                rows.append(
                    {
                        key: (raw.get(key) or "").strip()
                        for key in fieldnames
                    }
                )
    except OSError as exc:
        add_issue(issues, "ERROR", "READ_FAILED", str(exc), str(ledger))
        return issues

    if not rows:
        add_issue(issues, "ERROR", "EMPTY_LEDGER", "The fact ledger has no data rows", str(ledger))
        return issues

    by_id: dict[str, tuple[int, dict[str, str]]] = {}
    values: dict[str, Decimal] = {}
    page_cache: dict[Path, int | None] = {}
    page_text_cache: dict[tuple[Path, int], str] = {}
    line_cache: dict[Path, list[str]] = {}
    semantic_rows: defaultdict[tuple[str, ...], list[tuple[int, str, str]]] = defaultdict(list)

    for index, row in enumerate(rows, start=2):
        location = f"{ledger}:{index}"
        fact_id = row["fact_id"]
        if not fact_id:
            add_issue(issues, "ERROR", "MISSING_FACT_ID", "fact_id is required", location)
        elif fact_id in by_id:
            add_issue(
                issues,
                "ERROR",
                "DUPLICATE_FACT_ID",
                f"Duplicate fact_id {fact_id!r}; first seen on row {by_id[fact_id][0]}",
                location,
            )
        else:
            by_id[fact_id] = (index, row)

        for field in ("company", "metric", "period", "period_type", "scope", "attribution", "status", "audit_status"):
            if not row[field]:
                add_issue(issues, "ERROR", "MISSING_FIELD", f"{field} is required", location)

        for field, allowed in ENUMS.items():
            value = row[field]
            if value and value not in allowed:
                add_issue(
                    issues,
                    "ERROR",
                    "INVALID_ENUM",
                    f"{field}={value!r}; expected one of {', '.join(sorted(allowed))}",
                    location,
                )

        if row["scope"] and not (
            row["scope"] in {"consolidated", "parent", "other"}
            or row["scope"].startswith("segment:")
        ):
            add_issue(
                issues,
                "ERROR",
                "INVALID_SCOPE",
                "scope must be consolidated, parent, segment:<reported name>, or other",
                location,
            )

        status = row["status"]
        numeric: Decimal | None = None
        if status == "unavailable":
            if row["value"]:
                add_issue(issues, "ERROR", "UNAVAILABLE_HAS_VALUE", "Unavailable facts must have a blank value", location)
            if not row["notes"]:
                add_issue(issues, "ERROR", "UNAVAILABLE_NO_REASON", "Unavailable facts need a reason in notes", location)
        elif status in {"reported", "calculated"}:
            if not row["value"]:
                add_issue(issues, "ERROR", "MISSING_VALUE", f"{status} facts require value", location)
            else:
                try:
                    numeric = parse_decimal(row["value"])
                except InvalidOperation as exc:
                    add_issue(issues, "ERROR", "INVALID_VALUE", f"Invalid normalized value: {exc}", location)
            for field in ("unit", "currency"):
                if not row[field]:
                    add_issue(issues, "ERROR", "MISSING_FIELD", f"{field} is required for numeric facts", location)

        if fact_id and numeric is not None:
            values[fact_id] = numeric

        if status == "reported":
            for field in ("source_file", "locator_type", "locator", "source_line_item"):
                if not row[field]:
                    add_issue(issues, "ERROR", "MISSING_SOURCE_FIELD", f"Reported facts require {field}", location)
            if row["formula"] or row["input_fact_ids"]:
                add_issue(
                    issues,
                    "WARN",
                    "REPORTED_WITH_FORMULA",
                    "A reported fact should not also be represented as a calculated fact",
                    location,
                )
        elif status == "calculated":
            if not row["formula"]:
                add_issue(issues, "ERROR", "MISSING_FORMULA", "Calculated facts require formula", location)
            if not row["input_fact_ids"]:
                add_issue(issues, "ERROR", "MISSING_INPUTS", "Calculated facts require input_fact_ids", location)

        locator_type = row["locator_type"]
        locator = row["locator"]
        source_path: Path | None = None
        if row["source_file"] and not skip_source_check:
            source_path = resolve_source(source_root, row["source_file"])
            if not source_path.is_file():
                add_issue(
                    issues,
                    "ERROR",
                    "SOURCE_NOT_FOUND",
                    f"Source file does not exist: {source_path}",
                    location,
                )
                source_path = None

        if locator_type in {"pdf_page", "printed_page", "text_line"} and locator:
            points = parse_numeric_ranges(locator)
            if points is None or min(points, default=0) < 1:
                add_issue(
                    issues,
                    "ERROR",
                    "INVALID_LOCATOR",
                    f"{locator_type} locator must be a positive number, range, or comma-separated list",
                    location,
                )
            elif source_path is not None and locator_type == "pdf_page":
                count = _pdf_page_count(source_path, page_cache)
                if count == -1:
                    add_issue(issues, "ERROR", "PDF_OPEN_FAILED", f"Could not open PDF {source_path}", location)
                elif count is None:
                    add_issue(
                        issues,
                        "WARN",
                        "PDF_PAGE_UNCHECKED",
                        "PyMuPDF is unavailable; PDF page range was not checked",
                        location,
                    )
                elif max(points) > count:
                    add_issue(
                        issues,
                        "ERROR",
                        "PDF_PAGE_OUT_OF_RANGE",
                        f"Cited PDF page {max(points)} exceeds page count {count}",
                        location,
                    )
                elif row["source_line_item"]:
                    try:
                        cited_text = "\n".join(_pdf_page_text(source_path, page, page_text_cache) for page in points)
                    except Exception as exc:
                        add_issue(
                            issues,
                            "WARN",
                            "PDF_TEXT_CHECK_FAILED",
                            f"Could not check source line item on cited page(s): {exc}",
                            location,
                        )
                    else:
                        needle = _normalize_lookup(row["source_line_item"])
                        if len(needle) >= 4 and needle not in _normalize_lookup(cited_text):
                            add_issue(
                                issues,
                                "WARN",
                                "SOURCE_LABEL_NOT_ON_PAGE",
                                f"Exact source_line_item {row['source_line_item']!r} was not found on cited PDF page(s)",
                                location,
                            )
            elif source_path is not None and locator_type == "text_line":
                try:
                    source_lines = _text_lines(source_path, line_cache)
                except OSError as exc:
                    add_issue(issues, "ERROR", "TEXT_OPEN_FAILED", str(exc), location)
                else:
                    count = len(source_lines)
                    if max(points) > count:
                        add_issue(
                            issues,
                            "ERROR",
                            "TEXT_LINE_OUT_OF_RANGE",
                            f"Cited text line {max(points)} exceeds line count {count}",
                            location,
                        )
                    elif row["source_line_item"]:
                        cited_text = "\n".join(source_lines[point - 1] for point in points)
                        needle = _normalize_lookup(row["source_line_item"])
                        if len(needle) >= 4 and needle not in _normalize_lookup(cited_text):
                            add_issue(
                                issues,
                                "WARN",
                                "SOURCE_LABEL_NOT_ON_LINE",
                                f"Exact source_line_item {row['source_line_item']!r} was not found on cited text line(s)",
                                location,
                            )
        elif locator_type in {"section", "note"} and not locator:
            add_issue(issues, "ERROR", "EMPTY_LOCATOR", f"{locator_type} locator cannot be blank", location)

        if status != "unavailable":
            semantic_key = tuple(
                row[name]
                for name in (
                    "company",
                    "metric",
                    "period",
                    "period_type",
                    "scope",
                    "attribution",
                    "unit",
                    "currency",
                )
            )
            semantic_rows[semantic_key].append((index, row["value"], fact_id))

    for key, occurrences in semantic_rows.items():
        distinct = {value for _, value, _ in occurrences}
        if len(distinct) > 1:
            rows_text = ", ".join(str(row_number) for row_number, _, _ in occurrences)
            add_issue(
                issues,
                "WARN",
                "CONFLICTING_FACTS",
                f"Same metric identity has conflicting values on rows {rows_text}: {key}",
                str(ledger),
            )
        elif len(occurrences) > 1:
            rows_text = ", ".join(str(row_number) for row_number, _, _ in occurrences)
            add_issue(
                issues,
                "WARN",
                "DUPLICATE_FACT",
                f"Duplicate metric identity on rows {rows_text}: {key}",
                str(ledger),
            )

    graph: dict[str, list[str]] = {}
    for index, row in enumerate(rows, start=2):
        if row["status"] != "calculated":
            continue
        inputs = [item.strip() for item in row["input_fact_ids"].split(";") if item.strip()]
        graph[row["fact_id"]] = inputs
        input_metrics = [by_id[item][1]["metric"] for item in inputs if item in by_id]
        grant_views = {
            metric
            for metric in input_metrics
            if metric
            in {
                "government_grant_other_income",
                "government_grant_nonoperating_income",
                "government_grant_cost_offset",
                "government_grant_nonrecurring",
                "government_grant_deferred_balance",
                "government_grant_cash_receipt",
            }
        }
        if len(grant_views) > 1 and not re.search(
            r"(?i)mutually exclusive|reconciled non.overlap|不重叠|已对账", row["notes"]
        ):
            add_issue(
                issues,
                "ERROR",
                "OVERLAPPING_GRANT_VIEWS",
                "Calculation combines government-support views that may overlap; reconcile and prove they are mutually exclusive",
                f"{ledger}:{index}",
            )
        for input_id in inputs:
            if input_id not in by_id:
                add_issue(
                    issues,
                    "ERROR",
                    "UNKNOWN_INPUT",
                    f"input_fact_ids references unknown fact {input_id!r}",
                    f"{ledger}:{index}",
                )
            elif input_id == row["fact_id"]:
                add_issue(issues, "ERROR", "SELF_REFERENCE", "A fact cannot reference itself", f"{ledger}:{index}")
            else:
                input_row = by_id[input_id][1]
                if input_row["status"] == "unavailable":
                    add_issue(
                        issues,
                        "ERROR",
                        "CALCULATION_USES_UNAVAILABLE",
                        f"Calculated fact uses unavailable input {input_id!r}; keep the result unavailable",
                        f"{ledger}:{index}",
                    )
                elif input_id not in values:
                    add_issue(
                        issues,
                        "ERROR",
                        "CALCULATION_INPUT_NO_VALUE",
                        f"Calculated fact input {input_id!r} has no valid numeric value",
                        f"{ledger}:{index}",
                    )
                if input_row["company"] != row["company"] and not re.search(
                    r"(?i)peer|currency|fx|conversion|同业|汇率|换算", row["notes"]
                ):
                    add_issue(
                        issues,
                        "WARN",
                        "CROSS_COMPANY_CALC",
                        f"Calculation uses {input_id} from another company without a conversion/peer note",
                        f"{ledger}:{index}",
                    )

        if inputs and all(input_id in values for input_id in inputs) and row["fact_id"] in values:
            try:
                expected = safe_formula_value(
                    row["formula"], {input_id: values[input_id] for input_id in inputs}
                )
            except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as exc:
                add_issue(
                    issues,
                    "WARN",
                    "FORMULA_NOT_EVALUATED",
                    f"Formula could not be checked: {exc}",
                    f"{ledger}:{index}",
                )
            else:
                actual = values[row["fact_id"]]
                if not close_enough(actual, expected, abs_tol, rel_tol):
                    add_issue(
                        issues,
                        "ERROR",
                        "FORMULA_RESULT_MISMATCH",
                        f"Calculated value {actual} does not match formula result {expected}",
                        f"{ledger}:{index}",
                    )

        if (
            row["unit"] == "percent"
            and re.search(r"(?i)yoy|growth|同比", row["metric"])
            and len(inputs) >= 2
            and inputs[-1] in values
            and values[inputs[-1]] <= 0
        ):
            add_issue(
                issues,
                "ERROR",
                "YOY_DENOMINATOR_NOT_MEANINGFUL",
                "YoY/growth percentage uses a non-positive prior-period denominator; use N/M and show absolute change",
                f"{ledger}:{index}",
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            add_issue(
                issues,
                "ERROR",
                "CALCULATION_CYCLE",
                f"Calculation dependency cycle: {' -> '.join(trail + [node])}",
                str(ledger),
            )
            return
        visiting.add(node)
        for child in graph.get(node, []):
            if child in graph:
                visit(child, trail + [node])
        visiting.remove(node)
        visited.add(node)

    for fact_id in graph:
        visit(fact_id, [])

    selected: dict[tuple[str, str, str, str, str, str], dict[str, Decimal]] = defaultdict(dict)
    for row in rows:
        fact_id = row["fact_id"]
        if fact_id not in values:
            continue
        group = (
            row["company"],
            row["period"],
            row["period_type"],
            row["scope"],
            row["unit"],
            row["currency"],
        )
        selected[group].setdefault(row["metric"], values[fact_id])

    reconciliations = [
        ("balance_sheet", "assets", ("liabilities", "equity_total"), lambda a, b: a + b),
        ("gross_profit", "gross_profit", ("revenue", "cost_of_revenue"), lambda a, b: a - b),
        (
            "net_profit_attribution",
            "net_profit_total",
            ("net_profit_parent", "net_profit_nci"),
            lambda a, b: a + b,
        ),
        (
            "fcf_long_term_assets",
            "free_cash_flow_long_term_assets",
            ("operating_cash_flow", "cash_paid_for_ppe_intangibles_and_other_long_term_assets"),
            lambda a, b: a - b,
        ),
        (
            "fcf_ppe",
            "free_cash_flow_ppe",
            ("operating_cash_flow", "cash_paid_for_ppe"),
            lambda a, b: a - b,
        ),
        (
            "cash_flow_bridge",
            "net_change_in_cash_and_equivalents",
            (
                "operating_cash_flow",
                "investing_cash_flow",
                "financing_cash_flow",
                "fx_effect_on_cash_and_equivalents",
            ),
            lambda a, b, c, d: a + b + c + d,
        ),
    ]
    for group, metrics in selected.items():
        for code, target, inputs, operation in reconciliations:
            if target in metrics and all(name in metrics for name in inputs):
                expected = operation(*(metrics[name] for name in inputs))
                actual = metrics[target]
                if not close_enough(actual, expected, abs_tol, rel_tol):
                    add_issue(
                        issues,
                        "ERROR",
                        "RECONCILIATION_FAILED",
                        f"{code}: {target}={actual} but inputs imply {expected}; identity={group}",
                        str(ledger),
                    )
        fcf_values = [
            metrics[name]
            for name in ("free_cash_flow_long_term_assets", "free_cash_flow_ppe")
            if name in metrics
        ]
        if any(value < 0 for value in fcf_values):
            required_bridge = {"financing_cash_flow", "net_change_in_cash_and_equivalents"}
            missing_bridge = sorted(required_bridge - set(metrics))
            if missing_bridge:
                add_issue(
                    issues,
                    "WARN",
                    "FUNDING_BRIDGE_INCOMPLETE",
                    "Negative FCF is present but the funding/cash bridge lacks: " + ", ".join(missing_bridge),
                    str(ledger),
                )

    return issues


def _paragraphs(lines: Sequence[str]) -> Iterable[tuple[int, str]]:
    start = 0
    buffer: list[str] = []
    fenced = False
    for index, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if fenced or line.startswith("|") or line.lstrip().startswith("#"):
            if buffer:
                yield start, "\n".join(buffer)
                buffer = []
            continue
        if line.strip():
            if not buffer:
                start = index
            buffer.append(line)
        elif buffer:
            yield start, "\n".join(buffer)
            buffer = []
    if buffer:
        yield start, "\n".join(buffer)


def _strip_non_evidence_markdown(text: str) -> str:
    """Blank comments and fenced code while preserving line numbers."""
    text = re.sub(
        r"<!--.*?-->",
        lambda match: "\n" * match.group(0).count("\n"),
        text,
        flags=re.DOTALL,
    )
    output: list[str] = []
    fenced = False
    fence_marker = ""
    for line in text.splitlines(keepends=True):
        marker_match = re.match(r"\s*(```|~~~)", line)
        if marker_match:
            marker = marker_match.group(1)
            if not fenced:
                fenced = True
                fence_marker = marker
            elif marker == fence_marker:
                fenced = False
                fence_marker = ""
            output.append("\n" if line.endswith("\n") else "")
        elif fenced:
            output.append("\n" if line.endswith("\n") else "")
        else:
            output.append(line)
    return "".join(output)


def _table_blocks(lines: Sequence[str]) -> Iterable[tuple[int, int, str]]:
    start: int | None = None
    buffer: list[str] = []
    for index, line in enumerate(lines, start=1):
        if line.lstrip().startswith("|"):
            if start is None:
                start = index
            buffer.append(line)
        elif buffer:
            assert start is not None
            yield start, index - 1, "\n".join(buffer)
            start = None
            buffer = []
    if buffer:
        assert start is not None
        yield start, len(lines), "\n".join(buffer)


def _nearest_table_row(lines: Sequence[str], before_line: int, keyword: str) -> tuple[str | None, str] | None:
    """Return a nearby preceding Markdown table header and row containing keyword."""
    start = max(0, before_line - 12)
    candidate: str | None = None
    header: str | None = None
    for line in lines[start : before_line - 1]:
        if line.lstrip().startswith("|"):
            if re.search(r"20\d{2}Q[1-4]", line):
                header = line
            if keyword in line and not re.search(r"^-+$", line.strip("| -")):
                candidate = line
        elif line.strip() and not line.lstrip().startswith("|"):
            candidate = None
            header = None
    return (header, candidate) if candidate else None


def lint_report(report: Path, semiconductor: bool, fact_ids: set[str] | None = None) -> list[Issue]:
    issues: list[Issue] = []
    try:
        text = report.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        add_issue(issues, "ERROR", "READ_FAILED", str(exc), str(report))
        return issues
    text = _strip_non_evidence_markdown(text)
    lines = text.splitlines()

    if not SOURCE_MARKER_RE.search(text) and not FACT_MARKER_RE.search(text):
        add_issue(issues, "ERROR", "NO_SOURCE_CITATIONS", "No source citation markers were found", str(report))
    if not FILE_RE.search(text):
        add_issue(
            issues,
            "WARN",
            "NO_EXACT_SOURCE_FILE",
            "No exact source filename or source-manifest ID (for example S1) was found",
            str(report),
        )

    referenced_fact_ids: set[str] = set()
    claim_classes: defaultdict[str, set[str]] = defaultdict(set)
    for index, line in enumerate(lines, start=1):
        location = f"{report}:{index}"
        for fact_id in FACT_MARKER_RE.findall(line):
            referenced_fact_ids.add(fact_id)
            if fact_ids is not None and fact_id not in fact_ids:
                add_issue(
                    issues,
                    "ERROR",
                    "UNKNOWN_FACT_REFERENCE",
                    f"Report references fact_id {fact_id!r}, which is absent from the ledger",
                    location,
                )
        for claim_id, classification in CLAIM_MARKER_RE.findall(line):
            claim_classes[claim_id].add(classification.lower())
        if INVALID_PAGE_RE.search(line):
            add_issue(
                issues,
                "WARN",
                "UNTYPED_LOCATOR",
                "A p. locator is not followed by a numeric page; use section, note, or text_line explicitly",
                location,
            )
        if SOURCE_MARKER_RE.search(line) and not FACT_MARKER_RE.search(line) and not line.lstrip().startswith("#"):
            if not LOCATOR_RE.search(line) and NUMBER_RE.search(line):
                add_issue(
                    issues,
                    "WARN",
                    "SOURCE_WITHOUT_LOCATOR",
                    "Numeric source citation has no stable page/line/section/note locator",
                    location,
                )
            if NUMBER_RE.search(line) and not FILE_RE.search(line):
                add_issue(
                    issues,
                    "WARN",
                    "SOURCE_WITHOUT_FILE_ID",
                    "Numeric source citation has no exact filename or source-manifest ID",
                    location,
                )
        if re.search(r"年化|annuali[sz](?:e|ed|ation)", line, re.IGNORECASE):
            add_issue(
                issues,
                "WARN",
                "ANNUALIZATION_REVIEW",
                "Quarter annualization/run-rate calculations require an explicit user request and prominent limits",
                location,
            )
        if re.search(r"有机增速|organic growth|like-for-like", line, re.IGNORECASE):
            add_issue(
                issues,
                "WARN",
                "ORGANIC_GROWTH_REVIEW",
                "Verify exact consolidation period, disclosed contribution, and eliminations before using an organic measure",
                location,
            )
        if re.search(r"量价齐升|以价换量|价格(?:上涨|下降)|ASP(?:上涨|下降)|price.for.volume", line, re.IGNORECASE):
            if not re.search(r"隐含(?:单位收入|ASP)|implied reported revenue per unit|公司披露|source-stated", line, re.IGNORECASE):
                add_issue(
                    issues,
                    "WARN",
                    "PRICE_VOLUME_REVIEW",
                    "Price/ASP language needs a same-product, same-unit, same-scope bridge or must be labeled implied revenue per unit",
                    location,
                )
        if re.search(r"推算|反推|估算", line) and not re.search(r"计算|calculated|用户要求", line, re.IGNORECASE):
            add_issue(
                issues,
                "WARN",
                "UNLABELED_ESTIMATE",
                "Estimate/reconstruction language is not labeled as a calculation or user-requested scenario",
                location,
            )
        if "净现金" in line and "交易性金融资产" in line:
            add_issue(
                issues,
                "WARN",
                "NET_CASH_SCOPE_REVIEW",
                "Trading financial assets are included in net cash; verify liquidity or rename the measure net liquidity",
                location,
            )
        if re.search(r"(?:OCF|经营(?:活动)?现金流)\s*/\s*(?:净利润|利润)", line, re.IGNORECASE):
            if not re.search(r"归母|合并|total|parent|owners", line, re.IGNORECASE):
                add_issue(
                    issues,
                    "WARN",
                    "CASH_CONVERSION_DENOMINATOR",
                    "Cash conversion names a generic net-profit denominator; specify total or parent-attributable profit",
                    location,
                )
        for pattern, relation in (
            (r"(?<![\d.])(-?\d+(?:\.\d+)?)%[^%。；;]{0,30}?低于[^%。；;]{0,20}?(?<![\d.])(-?\d+(?:\.\d+)?)%", "lower"),
            (r"(?<![\d.])(-?\d+(?:\.\d+)?)%[^%。；;]{0,30}?高于[^%。；;]{0,20}?(?<![\d.])(-?\d+(?:\.\d+)?)%", "higher"),
        ):
            match = re.search(pattern, line)
            if match:
                left, right = (float(match.group(1)), float(match.group(2)))
                contradicted = (relation == "lower" and left >= right) or (relation == "higher" and left <= right)
                if contradicted:
                    add_issue(
                        issues,
                        "ERROR",
                        "COMPARISON_DIRECTION_ERROR",
                        f"Text says {left}% is {relation} than {right}%, but the arithmetic relation is false",
                        location,
                    )
        monotonic_match = re.search(r"(收入|营收|利润|现金流)[^。；;]{0,10}逐季(?:上升|增长|爬升)", line)
        if monotonic_match:
            keyword = monotonic_match.group(1)
            table_match = _nearest_table_row(lines, index, keyword)
            if table_match:
                header, row = table_match
                numbers = [float(item.replace(",", "")) for item in re.findall(r"-?\d[\d,]*(?:\.\d+)?", row)]
                periods = re.findall(r"20\d{2}Q[1-4]", header or "")
                if periods and len(periods) == len(numbers):
                    first_year = periods[0][:4]
                    numbers = [value for period, value in zip(periods, numbers) if period.startswith(first_year)]
                if len(numbers) >= 2 and any(current < previous for previous, current in zip(numbers, numbers[1:])):
                    add_issue(
                        issues,
                        "ERROR",
                        "MONOTONIC_CLAIM_CONTRADICTED",
                        f"Nearby {keyword} table is not monotonically increasing: {numbers}",
                        location,
                    )
        if "转正" in line:
            signed = [item.replace(",", "") for item in NUMBER_RE.findall(line)]
            numeric = [float(item.rstrip("%")) for item in signed if re.fullmatch(r"[-+]?\d+(?:\.\d+)?%?", item)]
            if len(numeric) >= 2 and numeric[0] > 0 and numeric[1] > 0:
                add_issue(
                    issues,
                    "WARN",
                    "TURN_POSITIVE_REVIEW",
                    "The first two visible comparison values are already positive; verify the claimed turn-positive period",
                    location,
                )

        for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", line):
            target = match.group(1).strip().split()[0].strip("<>")
            if re.match(r"(?i)https?://|data:", target):
                continue
            image_path = (report.parent / target).resolve()
            if not image_path.is_file():
                add_issue(
                    issues,
                    "ERROR",
                    "MISSING_IMAGE",
                    f"Referenced image does not exist: {target}",
                    location,
                )

    for start, paragraph in _paragraphs(lines):
        numeric_text = FACT_MARKER_RE.sub("", CLAIM_MARKER_RE.sub("", paragraph))
        numbers = NUMBER_RE.findall(numeric_text)
        has_evidence = SOURCE_MARKER_RE.search(paragraph) or FACT_MARKER_RE.search(paragraph)
        if len(numbers) >= 2 and FINANCE_TERMS_RE.search(paragraph) and not has_evidence:
            add_issue(
                issues,
                "WARN",
                "NUMERIC_PARAGRAPH_UNSOURCED",
                "A material numeric paragraph has no source/calculation marker",
                f"{report}:{start}",
            )

    for start, end, table in _table_blocks(lines):
        if len(NUMBER_RE.findall(table)) < 3 or not FINANCE_TERMS_RE.search(table):
            continue
        nearby_start = max(0, start - 4)
        nearby_end = min(len(lines), end + 3)
        nearby = "\n".join(lines[nearby_start:nearby_end])
        if (
            not SOURCE_MARKER_RE.search(nearby)
            and not FACT_MARKER_RE.search(nearby)
            and not re.search(r"fact[_ ]?id|事实ID", table, re.IGNORECASE)
        ):
            add_issue(
                issues,
                "WARN",
                "NUMERIC_TABLE_UNSOURCED",
                "A material numeric table has no nearby source note or fact ID",
                f"{report}:{start}-{end}",
            )

    if fact_ids is not None and not referenced_fact_ids:
        add_issue(
            issues,
            "ERROR",
            "NO_FACT_REFERENCES",
            "A facts ledger was supplied but the report contains no [F:fact_id] references",
            str(report),
        )
    for claim_id, classifications in claim_classes.items():
        if len(classifications) > 1:
            add_issue(
                issues,
                "ERROR",
                "CLAIM_CLASS_CHANGED",
                f"Claim {claim_id!r} uses inconsistent classifications: {', '.join(sorted(classifications))}",
                str(report),
            )

    headings = "\n".join(line for line in lines if line.lstrip().startswith("#"))
    required_heading_groups = {
        "source scope": r"来源|资料|source|scope",
        "business/products": r"公司概况|业务|产品|技术|business|product|technology",
        "financial snapshot": r"财务|financial|数据提取|snapshot",
        "profitability": r"盈利|利润|毛利|profit|margin",
        "cash flow/balance sheet": r"现金流|资产负债|cash flow|balance sheet",
        "footnotes": r"附注|会计政策|footnote|accounting polic",
        "fundamentals/expectations/risks": r"基本面|预期|风险|fundamental|expectation|risk",
        "appendix/evidence": r"附录|数据提取|证据|appendix|evidence|ledger",
    }
    for label, pattern in required_heading_groups.items():
        if not re.search(pattern, headings, re.IGNORECASE):
            add_issue(
                issues,
                "WARN",
                "MISSING_REPORT_AREA",
                f"No heading found for {label}; confirm the user requested a narrower output",
                str(report),
            )

    if semiconductor:
        semiconductor_groups = {
            "value-chain classification": r"产业链|子行业|价值链|value.chain|subsector",
            "commercialization map": r"商业化|验证|量产|技术路线|commerciali|qualification",
            "cycle/inventory/capacity": r"周期|库存|存货|产能|cycle|inventory|capacity",
            "orders/acceptance/revenue recognition": r"订单|验收|收入确认|order|acceptance|revenue recognition",
            "capex/CIP/depreciation": r"资本开支|在建工程|转固|折旧|capex|construction|depreciation",
            "supply chain/concentration/policy": r"供应链|集中度|政策|出口管制|supply chain|concentration|policy|export control",
        }
        for label, pattern in semiconductor_groups.items():
            if not re.search(pattern, headings, re.IGNORECASE):
                add_issue(
                    issues,
                    "WARN",
                    "MISSING_SEMICONDUCTOR_AREA",
                    f"No semiconductor heading found for {label}; mark unavailable if not disclosed",
                    str(report),
                )

    return issues


def print_issues(issues: Sequence[Issue], as_json: bool, max_issues: int) -> None:
    errors = sum(issue.severity == "ERROR" for issue in issues)
    warnings = sum(issue.severity == "WARN" for issue in issues)
    if as_json:
        payload = {
            "errors": errors,
            "warnings": warnings,
            "issues": [asdict(issue) for issue in issues[:max_issues]],
            "truncated": len(issues) > max_issues,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for issue in issues[:max_issues]:
        location = f" {issue.location}" if issue.location else ""
        print(f"{issue.severity} [{issue.code}]{location}: {issue.message}")
    if len(issues) > max_issues:
        print(f"... {len(issues) - max_issues} additional issue(s) omitted")
    print(f"SUMMARY errors={errors} warnings={warnings}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    facts = subparsers.add_parser("facts", help="Validate a fact-ledger CSV")
    facts.add_argument("ledger", type=Path)
    facts.add_argument(
        "--source-root",
        type=Path,
        help="Root for relative source_file paths (defaults to the ledger directory)",
    )
    facts.add_argument("--skip-source-check", action="store_true", help="Skip source existence and range checks")
    facts.add_argument("--absolute-tolerance", default="0.02", help="Absolute reconciliation tolerance")
    facts.add_argument("--relative-tolerance", default="0.001", help="Relative reconciliation tolerance")
    facts.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors")
    facts.add_argument("--json", action="store_true", help="Emit JSON")
    facts.add_argument("--max-issues", type=int, default=100)

    report = subparsers.add_parser("report", help="Lint a Markdown financial report")
    report.add_argument("report", type=Path)
    report.add_argument("--facts", type=Path, help="Fact-ledger CSV used by [F:fact_id] references")
    report.add_argument("--semiconductor", action="store_true")
    report.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors")
    report.add_argument("--json", action="store_true", help="Emit JSON")
    report.add_argument("--max-issues", type=int, default=100)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "facts":
        try:
            abs_tol, rel_tol = parse_tolerances(
                args.absolute_tolerance, args.relative_tolerance
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        source_root = (args.source_root or args.ledger.parent).expanduser().resolve()
        issues = validate_facts(
            args.ledger.expanduser().resolve(),
            source_root,
            args.skip_source_check,
            abs_tol,
            rel_tol,
        )
    else:
        fact_ids: set[str] | None = None
        if args.facts:
            facts_path = args.facts.expanduser().resolve()
            try:
                with facts_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    if "fact_id" not in (reader.fieldnames or []):
                        raise ValueError("facts ledger is missing fact_id")
                    fact_ids = {(row.get("fact_id") or "").strip() for row in reader}
                    fact_ids.discard("")
            except (OSError, ValueError) as exc:
                issues = [Issue("ERROR", "FACT_LEDGER_READ_FAILED", str(exc), str(facts_path))]
            else:
                issues = lint_report(args.report.expanduser().resolve(), args.semiconductor, fact_ids)
        else:
            issues = lint_report(args.report.expanduser().resolve(), args.semiconductor)

    print_issues(issues, args.json, max(1, args.max_issues))
    has_errors = any(issue.severity == "ERROR" for issue in issues)
    has_warnings = any(issue.severity == "WARN" for issue in issues)
    return 1 if has_errors or (args.strict and has_warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
