#!/usr/bin/env python3
"""半导体产业链基本面评分器（规则 v2）。

兼容模式可读取旧长表并复算诊断分；严格模式要求 v2 输入引用通过
``caiwu-fenxi`` 校验的事实账本，才允许发布正式/暂定评级和同业排名。

示例::

    python3 score.py ../assets/example-input.csv
    python3 score.py ../assets/example-input.csv --mode strict \
      --facts ../assets/example-facts.csv --out-dir /tmp/score-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = SKILL_ROOT / "references" / "rules-v2.json"
RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))

SCHEMA_VERSION = RULES["schema_version"]
RULES_VERSION = RULES["rules_version"]
D = Decimal
Q_SCORE = D("0.01")
Q_COVERAGE = D("0.1")
ZERO = D("0")
ONE = D("1")

SUBSECTORS = {"equipment", "materials", "foundry", "idm", "osat", "fabless", "eda", "ip"}
HEAVY = set(RULES["heavy_subsectors"])
DIM_ORDER = list(RULES["dimensions"])
CORE_SLOTS = [
    metric
    for dim in DIM_ORDER
    for metric in RULES["dimensions"][dim]["metrics"]
]
CORE_SLOT_SET = set(CORE_SLOTS)

CASH_3Y = "cash_conversion_parent_3y"
CASH_FY = "cash_conversion_parent_fy"
CASH_SLOT = "cash_conversion_parent"

STRUCTURAL_METRICS = set(RULES["structural"])
ALERT_METRICS = set(RULES["alerts"])
SCORE_INPUT_METRICS = (CORE_SLOT_SET - {CASH_SLOT}) | {CASH_3Y, CASH_FY}
CANONICAL_INPUT_METRICS = SCORE_INPUT_METRICS | STRUCTURAL_METRICS | ALERT_METRICS

LEGACY_ALIASES = {
    "gross_margin": "gross_margin_total",
    "net_margin": "net_margin_parent",
    "roe": "roe_weighted_parent",
    "cash_conv_3y": CASH_3Y,
    "cash_conv": CASH_FY,
    "fcf_margin": "fcf_long_term_assets_margin",
    "cash_ratio": "cash_receipts_to_revenue",
    "debt_ratio": "debt_to_assets",
    "net_cash_ratio": "net_cash_to_assets",
    "recurring": "recurring_parent_profit_ratio",
    "subsidy_dep": "government_grant_pnl_ratio",
    "rd_cap_rate": "rd_capitalization_rate",
    "rd_intensity": "rd_expense_intensity",
    "cust_conc": "top5_billed_customer_revenue_ratio",
    "supp_conc": "top5_supplier_purchase_ratio",
    "goodwill_ratio": "goodwill_to_parent_equity",
    "max_customer_conc": "largest_billed_customer_revenue_ratio",
    "max_supplier_conc": "largest_supplier_purchase_ratio",
    "ocf": "operating_cash_flow",
    "impairment_ratio": "impairment_to_pbt",
    "da_ratio": "da_to_revenue",
}

CORE_STATUSES = {
    "present", "missing", "not_applicable", "not_meaningful",
    "turnaround", "turn_loss",
}
FLAG_STATUSES = {"checked_clear", "triggered", "missing", "not_applicable"}
OTHER_STATUSES = {"present", "missing", "not_applicable", "not_meaningful"}
STATUS_ALIASES = {"nm": "not_meaningful", "n/m": "not_meaningful", "unavailable": "missing"}

NOT_MEANINGFUL_REASONS = {
    "negative_denominator", "zero_denominator", "near_zero_denominator",
    "sign_change", "turnaround_window", "scope_break", "acquisition_break",
    "not_comparable",
}
NOT_APPLICABLE_REASONS = {"business_not_applicable", "rule_exempt"}
MISSING_REASONS = {
    "not_disclosed", "not_extracted", "source_unavailable",
    "insufficient_history", "scope_break", "acquisition_break",
    "source_conflict", "not_comparable",
}

STRICT_EXTRA_FIELDS = {
    "entity_id", "fy", "peer_group", "unit", "status", "nm_reason",
    "fact_id", "input_fact_ids", "comparability_status",
    "business_scope_status", "semiconductor_revenue_share",
    "calibration_status", "source", "notes",
}
BASE_FIELDS = {"company", "subsector", "metric", "value"}
ALLOWED_FIELDS = BASE_FIELDS | STRICT_EXTRA_FIELDS

COMPARABILITY = {"comparable", "limited", "not_comparable", "unknown"}
BUSINESS_SCOPE = {"pure_play", "segment_scored", "diversified_unallocated", "unknown"}
CALIBRATION = {"calibrated", "uncalibrated"}

CURRENCY_UNITS = {
    "yuan", "thousand_yuan", "ten_thousand_yuan", "million",
    "hundred_million",
}
BOUNDED_PERCENT_METRICS = {
    "rd_capitalization_rate", "top5_billed_customer_revenue_ratio",
    "top5_supplier_purchase_ratio", "largest_billed_customer_revenue_ratio",
    "largest_supplier_purchase_ratio",
}
NONNEGATIVE_METRICS = {
    "current_ratio", "cash_receipts_to_revenue", "rd_expense_intensity",
    "goodwill_to_parent_equity", "inventory_days_change", "da_to_revenue",
}

EXPECTED_ATTRIBUTION = {
    "nps_growth": "parent",
    "nps_cagr_3y": "parent",
    "net_margin_parent": "parent",
    "roe_weighted_parent": "parent",
    CASH_3Y: "parent",
    CASH_FY: "parent",
    "recurring_parent_profit_ratio": "parent",
}


def _metric_units() -> dict[str, str]:
    units = {name: spec["unit"] for name, spec in RULES["metrics"].items()}
    units.pop(CASH_SLOT)
    units[CASH_3Y] = "ratio"
    units[CASH_FY] = "ratio"
    units.update({name: spec["unit"] for name, spec in RULES["structural"].items()})
    units.update({name: spec["unit"] for name, spec in RULES["alerts"].items()})
    return units


METRIC_UNITS = _metric_units()


@dataclass
class Observation:
    metric: str
    input_metric: str
    status: str
    value: Decimal | None
    unit: str
    nm_reason: str
    fact_id: str
    input_fact_ids: tuple[str, ...]
    source: str
    notes: str
    line_no: int
    evidence_status: str = "not_checked"
    evidence_message: str = ""
    fact: dict[str, str] | None = None
    source_trace: str = ""


@dataclass
class EntityInput:
    company: str
    entity_id: str
    subsector: str
    fy: str
    peer_group: str
    comparability_status: str
    business_scope_status: str
    semiconductor_revenue_share: Decimal | None
    calibration_status: str
    observations: dict[str, Observation] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreHit:
    score: int
    band: str


def as_decimal(raw: str, where: str) -> Decimal:
    try:
        value = D(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{where}: value不是有效数字: {raw!r}") from exc
    if not value.is_finite():
        raise ValueError(f"{where}: value必须是有限数，不能使用NaN或Infinity")
    return value


def q(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def decimal_text(value: Decimal | None, places: int | None = None) -> str:
    if value is None:
        return ""
    if places is not None:
        value = q(value, D("1").scaleb(-places))
        return f"{value:.{places}f}"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def cell(row: dict[str | None, Any], key: str) -> str:
    value = row.get(key, "")
    return "" if value is None else str(value).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rules_digest() -> str:
    return sha256_file(RULES_PATH)


def units_match(expected: str, actual: str) -> bool:
    if expected == "currency":
        return actual in CURRENCY_UNITS
    if expected == "boolean":
        return actual in {"boolean", "ratio"}
    return expected == actual


def validate_numeric(metric: str, value: Decimal, mode: str, where: str) -> list[str]:
    warnings: list[str] = []
    if metric in BOUNDED_PERCENT_METRICS and not ZERO <= value <= D("100"):
        raise ValueError(f"{where}: {metric} 应在0到100之间")
    if metric in NONNEGATIVE_METRICS and value < ZERO:
        raise ValueError(f"{where}: {metric} 不应为负数")
    if metric in {"performance_commitment_flag", "audit_issue", "debt_default"} and value not in {ZERO, ONE}:
        raise ValueError(f"{where}: {metric} 只能为0或1")

    suspicious = None
    if metric == "cash_receipts_to_revenue" and value > D("10"):
        suspicious = "收现比应使用ratio（例如78.43%输入0.7843），当前值疑似放大100倍"
    elif metric in {CASH_3Y, CASH_FY} and abs(value) > D("20"):
        suspicious = "现金转换比率绝对值>20，需核对ratio单位和异常分母"
    elif metric == "recurring_parent_profit_ratio" and abs(value) > D("10"):
        suspicious = "扣非/归母绝对值>10，需核对ratio单位和异常分母"
    elif metric == "current_ratio" and value > D("100"):
        suspicious = "流动比率>100，需核对是否误用了百分数"
    if suspicious:
        if mode == "strict":
            raise ValueError(f"{where}: {suspicious}")
        warnings.append(f"{where}: {suspicious}")
    return warnings


def reason_code(text: str) -> str:
    return text.split(":", 1)[0].strip().lower()


def validate_reason(status: str, reason: str, where: str, strict: bool) -> None:
    if not strict:
        return
    code = reason_code(reason)
    if status == "not_meaningful" and code not in NOT_MEANINGFUL_REASONS:
        raise ValueError(f"{where}: not_meaningful需要受控nm_reason，当前为{reason!r}")
    if status == "not_applicable" and code not in NOT_APPLICABLE_REASONS:
        raise ValueError(f"{where}: not_applicable需要business_not_applicable或rule_exempt")
    if status == "missing" and code not in MISSING_REASONS:
        raise ValueError(f"{where}: missing需要受控nm_reason，当前为{reason!r}")


def canonical_metric(raw_metric: str, mode: str, where: str) -> tuple[str, str | None]:
    mapped = LEGACY_ALIASES.get(raw_metric, raw_metric)
    if mapped not in CANONICAL_INPUT_METRICS:
        raise ValueError(f"{where}: 未知metric={raw_metric}")
    if mode == "strict" and mapped != raw_metric:
        raise ValueError(
            f"{where}: strict v2不接受旧指标名{raw_metric!r}，请改为{mapped!r}"
        )
    warning = None
    if mapped != raw_metric:
        warning = f"{where}: 旧指标名{raw_metric}已映射为{mapped}，仅作诊断兼容"
    return mapped, warning


def expected_statuses(metric: str) -> set[str]:
    if metric in {"performance_commitment_flag", "audit_issue", "debt_default"}:
        return FLAG_STATUSES | {"present"}
    if metric in SCORE_INPUT_METRICS:
        return CORE_STATUSES
    return OTHER_STATUSES


def parse_status(raw: str, has_value: bool, mode: str, where: str) -> tuple[str, str | None]:
    if not raw:
        if mode == "strict":
            raise ValueError(f"{where}: strict v2要求显式status")
        return ("present" if has_value else "missing"), f"{where}: 空status已按兼容规则推断"
    normalized = STATUS_ALIASES.get(raw.lower(), raw.lower())
    warning = None
    if normalized != raw.lower():
        if mode == "strict":
            raise ValueError(f"{where}: strict v2不接受status={raw}，请使用{normalized}")
        warning = f"{where}: status={raw}已归一化为{normalized}"
    return normalized, warning


def parse_input(path: Path, mode: str) -> tuple[list[EntityInput], list[str]]:
    warnings: list[str] = []
    entities: dict[tuple[str, str, str], EntityInput] = {}
    seen: set[tuple[tuple[str, str, str], str]] = set()

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if not fields:
            raise ValueError("CSV没有表头")
        duplicates = sorted(name for name, count in Counter(fields).items() if count > 1)
        if duplicates:
            raise ValueError(f"CSV存在重复表头: {','.join(duplicates)}")
        missing = BASE_FIELDS - set(fields)
        if missing:
            raise ValueError(f"CSV缺少必需列: {','.join(sorted(missing))}")
        if mode == "strict":
            missing_v2 = STRICT_EXTRA_FIELDS - set(fields)
            if missing_v2:
                raise ValueError(f"strict v2缺少列: {','.join(sorted(missing_v2))}")
        unknown = sorted(set(fields) - ALLOWED_FIELDS)
        if unknown:
            message = f"CSV包含未知列: {','.join(unknown)}"
            if mode == "strict":
                raise ValueError(message)
            warnings.append(message)

        for line_no, row in enumerate(reader, start=2):
            if None in row and row[None]:
                raise ValueError(f"第{line_no}行字段数量超过表头")
            company = cell(row, "company")
            raw_metric = cell(row, "metric")
            where = f"第{line_no}行{company or '<空公司>'}/{raw_metric or '<空指标>'}"
            if not company:
                raise ValueError(f"第{line_no}行: company为空")
            if not raw_metric:
                raise ValueError(f"第{line_no}行: metric为空")
            subsector = cell(row, "subsector").lower()
            if subsector not in SUBSECTORS:
                raise ValueError(f"{where}: 不支持的subsector={subsector}")

            metric, alias_warning = canonical_metric(raw_metric, mode, where)
            if alias_warning:
                warnings.append(alias_warning)

            entity_id = cell(row, "entity_id") or company
            fy = cell(row, "fy")
            peer_group = cell(row, "peer_group") or subsector
            comparability = cell(row, "comparability_status").lower() or "unknown"
            business_scope = cell(row, "business_scope_status").lower() or "unknown"
            calibration = cell(row, "calibration_status").lower() or RULES["calibration_status"]
            share_raw = cell(row, "semiconductor_revenue_share")
            share = as_decimal(share_raw, f"{where}/semiconductor_revenue_share") if share_raw else None

            if comparability not in COMPARABILITY:
                raise ValueError(f"{where}: comparability_status={comparability}无效")
            if business_scope not in BUSINESS_SCOPE:
                raise ValueError(f"{where}: business_scope_status={business_scope}无效")
            if calibration not in CALIBRATION:
                raise ValueError(f"{where}: calibration_status={calibration}无效")
            if share is not None and not ZERO <= share <= D("100"):
                raise ValueError(f"{where}: semiconductor_revenue_share应在0到100之间")

            if mode == "strict":
                for name, value in {
                    "entity_id": cell(row, "entity_id"), "fy": fy,
                    "peer_group": cell(row, "peer_group"),
                    "comparability_status": cell(row, "comparability_status"),
                    "business_scope_status": cell(row, "business_scope_status"),
                    "semiconductor_revenue_share": share_raw,
                    "calibration_status": cell(row, "calibration_status"),
                }.items():
                    if not value:
                        raise ValueError(f"{where}: strict v2要求{name}非空")
                if not fy.startswith("FY"):
                    raise ValueError(f"{where}: fy应使用FY2025形式")
                if business_scope == "pure_play" and share is not None and share < D("70"):
                    raise ValueError(f"{where}: 主营占比<70%不能标记为pure_play")
                if business_scope == "diversified_unallocated" and share is not None and share >= D("70"):
                    raise ValueError(f"{where}: diversified_unallocated与主营占比>=70%矛盾")

            key = (company, entity_id, fy)
            if key not in entities:
                entities[key] = EntityInput(
                    company=company,
                    entity_id=entity_id,
                    subsector=subsector,
                    fy=fy,
                    peer_group=peer_group,
                    comparability_status=comparability,
                    business_scope_status=business_scope,
                    semiconductor_revenue_share=share,
                    calibration_status=calibration,
                )
            entity = entities[key]
            for name, prior, current in [
                ("subsector", entity.subsector, subsector),
                ("peer_group", entity.peer_group, peer_group),
                ("comparability_status", entity.comparability_status, comparability),
                ("business_scope_status", entity.business_scope_status, business_scope),
                ("calibration_status", entity.calibration_status, calibration),
                ("semiconductor_revenue_share", entity.semiconductor_revenue_share, share),
            ]:
                if prior != current:
                    raise ValueError(f"{where}: 同一评分实体的{name}不一致")

            duplicate_key = (key, metric)
            if duplicate_key in seen:
                raise ValueError(f"{where}: metric={metric}重复（所有status均参与唯一性检查）")
            seen.add(duplicate_key)

            raw_value = cell(row, "value")
            status, status_warning = parse_status(cell(row, "status"), bool(raw_value), mode, where)
            if status_warning:
                warnings.append(status_warning)
            if status not in expected_statuses(metric):
                raise ValueError(f"{where}: metric={metric}不允许status={status}")
            if (
                mode == "strict"
                and metric in {"performance_commitment_flag", "audit_issue", "debt_default"}
                and status == "present"
            ):
                raise ValueError(f"{where}: strict v2布尔筛查必须使用checked_clear或triggered")
            if status in {"turnaround", "turn_loss"} and metric != "nps_growth":
                raise ValueError(f"{where}: {status}只适用于nps_growth")

            nm_reason = cell(row, "nm_reason")
            validate_reason(status, nm_reason, where, mode == "strict")
            unit = cell(row, "unit").lower()
            expected_unit = METRIC_UNITS[metric]
            if mode == "strict" and not unit:
                raise ValueError(f"{where}: strict v2要求显式unit={expected_unit}")
            if unit and not units_match(expected_unit, unit):
                raise ValueError(f"{where}: {metric}要求unit={expected_unit}，实际为{unit}")

            value: Decimal | None = None
            if status == "present":
                if not raw_value:
                    if mode == "strict":
                        raise ValueError(f"{where}: status=present时value不能为空")
                    status = "missing"
                    warnings.append(f"{where}: present空值已按missing处理")
                else:
                    value = as_decimal(raw_value, where)
            elif status in {"checked_clear", "triggered"}:
                expected = ZERO if status == "checked_clear" else ONE
                if raw_value:
                    value = as_decimal(raw_value, where)
                    if value != expected:
                        raise ValueError(f"{where}: status={status}与value={raw_value}矛盾")
                else:
                    value = expected
            elif status in {"missing", "not_applicable", "not_meaningful", "turnaround", "turn_loss"}:
                if raw_value:
                    if mode == "strict":
                        raise ValueError(f"{where}: status={status}时value必须为空")
                    warnings.append(f"{where}: status={status}携带的value已忽略")

            if value is not None:
                warnings.extend(validate_numeric(metric, value, mode, where))

            effective_unit = unit or expected_unit
            notes = cell(row, "notes")
            if (
                mode == "compat" and raw_metric == "ocf" and not unit
                and value in {D("-1"), D("1")}
            ):
                effective_unit = "sign"
                notes = (notes + ";" if notes else "") + "legacy_sign_only"
                warnings.append(f"{where}: ocf=±1且无单位，按正负号哨兵解释，不展示为金额")

            input_fact_ids = tuple(
                item.strip() for item in cell(row, "input_fact_ids").split(";") if item.strip()
            )
            observation = Observation(
                metric=metric,
                input_metric=raw_metric,
                status=status,
                value=value,
                unit=effective_unit,
                nm_reason=nm_reason,
                fact_id=cell(row, "fact_id"),
                input_fact_ids=input_fact_ids,
                source=cell(row, "source"),
                notes=notes,
                line_no=line_no,
            )
            entity.observations[metric] = observation

    if not entities:
        raise ValueError("CSV没有数据行")

    for entity in entities.values():
        _validate_cash_inputs(entity, mode)
        if mode == "strict":
            missing_slots = sorted(
                metric for metric in SCORE_INPUT_METRICS - {CASH_FY}
                if metric not in entity.observations
            )
            if missing_slots:
                raise ValueError(
                    f"{entity.entity_id}: strict v2必须显式列出全部核心槽位，缺少{','.join(missing_slots)}"
                )
        warnings.extend(entity.warnings)
    return list(entities.values()), warnings


def _validate_cash_inputs(entity: EntityInput, mode: str) -> None:
    three = entity.observations.get(CASH_3Y)
    current = entity.observations.get(CASH_FY)
    if three and current and three.status == "present" and current.status == "present":
        if mode == "strict":
            raise ValueError(f"{entity.entity_id}: 三年与单年现金转换不能同时为present")
        entity.warnings.append(f"{entity.entity_id}: 同时提供两种现金转换，兼容模式优先三年值")
    if mode == "strict" and current and current.status == "present":
        if not three:
            raise ValueError(f"{entity.entity_id}: 使用单年现金转换前必须显式提供三年项及insufficient_history原因")
        if not (three.status == "missing" and reason_code(three.nm_reason) == "insufficient_history"):
            raise ValueError(f"{entity.entity_id}: 单年现金转换只允许在三年历史不足时回退")


def run_fact_validator(facts_path: Path, source_root: Path | None, skip_source_check: bool) -> dict[str, Any]:
    validator = SKILL_ROOT.parent / "caiwu-fenxi" / "scripts" / "validate_analysis.py"
    if not validator.exists():
        raise ValueError(f"找不到上游事实校验器: {validator}")
    command = [
        sys.executable, str(validator), "facts", str(facts_path), "--strict", "--json",
    ]
    if source_root:
        command.extend(["--source-root", str(source_root)])
    if skip_source_check:
        command.append("--skip-source-check")
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    try:
        payload = json.loads(process.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"事实校验器未返回有效JSON: {process.stdout or process.stderr}") from exc
    if process.returncode != 0:
        issues = payload.get("issues", [])
        preview = "; ".join(
            f"{item.get('code', 'ISSUE')}@{item.get('location', '')}: {item.get('message', '')}"
            for item in issues[:8]
        )
        raise ValueError(f"facts.csv严格校验失败: {preview or process.stderr.strip()}")
    return payload


def load_facts(path: Path) -> dict[str, dict[str, str]]:
    facts: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        duplicates = sorted(name for name, count in Counter(fields).items() if count > 1)
        if duplicates:
            raise ValueError(f"facts.csv存在重复表头: {','.join(duplicates)}")
        required = {
            "fact_id", "company", "metric", "period", "period_type", "scope",
            "attribution", "value", "unit", "currency", "status", "audit_status",
            "source_file", "locator_type", "locator", "source_line_item", "formula",
            "input_fact_ids", "notes",
        }
        missing = required - set(fields)
        if missing:
            raise ValueError(f"facts.csv缺少列: {','.join(sorted(missing))}")
        for line_no, row in enumerate(reader, start=2):
            fact_id = cell(row, "fact_id")
            if fact_id in facts:
                raise ValueError(f"facts.csv第{line_no}行: fact_id={fact_id}重复")
            facts[fact_id] = {key: cell(row, key) for key in fields}
    return facts


def fact_value(fact: dict[str, str], fact_id: str) -> Decimal:
    if fact.get("status") == "unavailable" or not fact.get("value"):
        raise ValueError(f"fact_id={fact_id}不可用")
    return as_decimal(fact["value"], f"fact_id={fact_id}")


def fact_period_matches(period: str, fy: str) -> bool:
    if not fy:
        return False
    return period == fy or period.split("/")[-1] == fy


def trace_fact(fact_id: str, facts: dict[str, dict[str, str]]) -> str:
    fact = facts[fact_id]
    if fact.get("source_file") and fact.get("locator"):
        return f"{fact_id}:{fact['source_file']}#{fact['locator_type']}={fact['locator']}"
    traces: list[str] = []
    for input_id in fact.get("input_fact_ids", "").split(";"):
        input_id = input_id.strip()
        if not input_id or input_id not in facts:
            continue
        input_fact = facts[input_id]
        if input_fact.get("source_file") and input_fact.get("locator"):
            traces.append(
                f"{input_id}:{input_fact['source_file']}#{input_fact['locator_type']}={input_fact['locator']}"
            )
    return ";".join(traces)


def evidence_ids(observation: Observation) -> tuple[str, ...]:
    if observation.status in {"turnaround", "turn_loss", "not_meaningful", "not_applicable"}:
        return observation.input_fact_ids or ((observation.fact_id,) if observation.fact_id else ())
    return (observation.fact_id,) if observation.fact_id else ()


def verify_evidence(entity: EntityInput, facts: dict[str, dict[str, str]]) -> None:
    for observation in entity.observations.values():
        status = observation.status
        if status == "missing":
            observation.evidence_status = "not_required"
            continue
        ids = evidence_ids(observation)
        where = f"{entity.entity_id}/{observation.metric}"
        if not ids:
            raise ValueError(f"{where}: strict v2要求fact_id或input_fact_ids")
        for fact_id in ids:
            if fact_id not in facts:
                raise ValueError(f"{where}: 引用了不存在的fact_id={fact_id}")
            fact = facts[fact_id]
            if fact.get("company") != entity.company:
                raise ValueError(f"{where}: fact_id={fact_id}属于其他公司")
            if fact.get("status") == "unavailable":
                raise ValueError(f"{where}: fact_id={fact_id}不可用")

        verified = True
        messages: list[str] = []
        if status in {"present", "checked_clear", "triggered"}:
            fact = facts[observation.fact_id]
            if fact.get("metric") != observation.metric:
                raise ValueError(
                    f"{where}: fact metric={fact.get('metric')}与评分metric不一致"
                )
            if observation.value is None or fact_value(fact, observation.fact_id) != observation.value:
                raise ValueError(f"{where}: score value与fact value不一致")
            if not units_match(METRIC_UNITS[observation.metric], fact.get("unit", "")):
                raise ValueError(
                    f"{where}: fact unit={fact.get('unit')}与要求{METRIC_UNITS[observation.metric]}不一致"
                )
            observation.fact = fact

        if status in {"turnaround", "turn_loss"}:
            if len(ids) < 2:
                raise ValueError(f"{where}: {status}至少需要当前期和上期两个fact ID")
            current = fact_value(facts[ids[0]], ids[0])
            prior = fact_value(facts[ids[-1]], ids[-1])
            if status == "turnaround" and not (current > ZERO and prior <= ZERO):
                raise ValueError(f"{where}: fact符号不支持turnaround")
            if status == "turn_loss" and not (current <= ZERO and prior > ZERO):
                raise ValueError(f"{where}: fact符号不支持turn_loss")

        if status == "not_meaningful":
            values = [fact_value(facts[fact_id], fact_id) for fact_id in ids]
            code = reason_code(observation.nm_reason)
            denominator = values[-1]
            if code == "negative_denominator" and denominator >= ZERO:
                raise ValueError(f"{where}: 证据不支持negative_denominator")
            if code == "zero_denominator" and denominator != ZERO:
                raise ValueError(f"{where}: 证据不支持zero_denominator")
            if code == "sign_change" and not (any(value <= ZERO for value in values) and any(value > ZERO for value in values)):
                raise ValueError(f"{where}: 证据不支持sign_change")
            if code == "turnaround_window" and not (any(value <= ZERO for value in values) and any(value > ZERO for value in values)):
                raise ValueError(f"{where}: 证据不支持turnaround_window")

        if observation.metric in {"rev_cagr_3y", "nps_cagr_3y"} and status == "present":
            if len(observation.input_fact_ids) != 4:
                raise ValueError(f"{where}: 三年CAGR必须引用四个完整FY端点（3个年度间隔）")
            values = [fact_value(facts[fact_id], fact_id) for fact_id in observation.input_fact_ids]
            if any(value <= ZERO for value in values):
                raise ValueError(f"{where}: CAGR窗口存在非正值，应使用not_meaningful")
            if observation.fact and observation.fact.get("status") != "calculated":
                raise ValueError(f"{where}: CAGR必须是可重算的calculated fact")

        for fact_id in ids:
            fact = facts[fact_id]
            if fact.get("audit_status") != "audited":
                verified = False
                messages.append(f"{fact_id}非audited")
            if not fact_period_matches(fact.get("period", ""), entity.fy):
                verified = False
                messages.append(f"{fact_id}期间不匹配{entity.fy}")
            scope = fact.get("scope", "")
            if entity.business_scope_status == "pure_play" and scope != "consolidated":
                verified = False
                messages.append(f"{fact_id}不是consolidated口径")
            if entity.business_scope_status == "segment_scored":
                if observation.metric in SCORE_INPUT_METRICS and not scope.startswith("segment:"):
                    verified = False
                    messages.append(f"{fact_id}不是segment评分口径")
                elif observation.metric not in SCORE_INPUT_METRICS and not (
                    scope.startswith("segment:") or scope == "consolidated"
                ):
                    verified = False
                    messages.append(f"{fact_id}结构/预警scope不可用")
            expected_attr = EXPECTED_ATTRIBUTION.get(observation.metric)
            if expected_attr and fact.get("attribution") != expected_attr:
                verified = False
                messages.append(f"{fact_id}归属应为{expected_attr}")

        observation.evidence_status = "verified" if verified else "unverified"
        observation.evidence_message = ";".join(messages)
        observation.source_trace = ";".join(trace_fact(fact_id, facts) for fact_id in ids if trace_fact(fact_id, facts))


def _cuts(spec: dict[str, Any], subsector: str) -> list[list[Any]]:
    if "cuts" in spec:
        return spec["cuts"]
    groups = spec["groups"]
    if subsector in groups:
        return groups[subsector]
    return groups["heavy" if subsector in HEAVY else "other"]


def hit_high(value: Decimal, cuts: Iterable[Iterable[Any]]) -> ScoreHit:
    parsed = [(D(str(bound)), int(score)) for bound, score in cuts]
    for index, (lower, score) in enumerate(parsed):
        if value >= lower:
            if index == 0:
                band = f">={decimal_text(lower)}"
            else:
                upper = parsed[index - 1][0]
                band = f"[{decimal_text(lower)},{decimal_text(upper)})"
            return ScoreHit(score, band)
    return ScoreHit(1, f"<{decimal_text(parsed[-1][0])}")


def hit_low(value: Decimal, cuts: Iterable[Iterable[Any]]) -> ScoreHit:
    parsed = [(D(str(bound)), int(score)) for bound, score in cuts]
    for index, (upper, score) in enumerate(parsed):
        if value <= upper:
            if index == 0:
                band = f"<={decimal_text(upper)}"
            else:
                lower = parsed[index - 1][0]
                band = f"({decimal_text(lower)},{decimal_text(upper)}]"
            return ScoreHit(score, band)
    return ScoreHit(1, f">{decimal_text(parsed[-1][0])}")


def _bands(spec: dict[str, Any], subsector: str) -> list[dict[str, Any]]:
    band_groups = spec.get("band_groups")
    if band_groups and subsector in band_groups:
        return band_groups[subsector]
    return spec["bands"]


def hit_ranges(value: Decimal, spec: dict[str, Any], subsector: str) -> ScoreHit:
    for band in _bands(spec, subsector):
        for lower_raw, lower_inc, upper_raw, upper_inc in band["ranges"]:
            lower = D(lower_raw)
            upper = D(upper_raw) if upper_raw is not None else None
            lower_ok = value >= lower if lower_inc else value > lower
            upper_ok = True if upper is None else (value <= upper if upper_inc else value < upper)
            if lower_ok and upper_ok:
                left = "[" if lower_inc else "("
                right = "]" if upper_inc else ")"
                upper_text = "+inf" if upper is None else decimal_text(upper)
                return ScoreHit(int(band["score"]), f"{left}{decimal_text(lower)},{upper_text}{right}")
    return ScoreHit(int(spec["default_score"]), "default")


def score_metric(metric: str, value: Decimal, subsector: str) -> ScoreHit:
    spec = RULES["metrics"][metric]
    method = spec["method"]
    if method == "high":
        return hit_high(value, _cuts(spec, subsector))
    if method == "low":
        return hit_low(value, _cuts(spec, subsector))
    if method == "zero_then_low":
        if value == ZERO:
            return ScoreHit(int(spec["zero_score"]), "=0")
        return hit_low(value, spec["cuts"])
    if method == "ranges":
        return hit_ranges(value, spec, subsector)
    raise ValueError(f"未知评分method={method}")


def select_observation(entity: EntityInput, slot: str, mode: str) -> Observation | None:
    if slot != CASH_SLOT:
        return entity.observations.get(slot)
    three = entity.observations.get(CASH_3Y)
    current = entity.observations.get(CASH_FY)
    chosen: Observation | None = None
    if three and three.status == "present":
        chosen = three
    elif mode == "compat" and current and current.status == "present":
        chosen = current
    elif current and current.status == "present" and three and three.status == "missing" and reason_code(three.nm_reason) == "insufficient_history":
        chosen = current
    elif three:
        chosen = three
    elif current:
        chosen = current
    if chosen is None:
        return None
    return replace(chosen, metric=CASH_SLOT)


def weight_group(subsector: str) -> str:
    return "heavy" if subsector in HEAVY else subsector


GRADE_ORDER = [band[1] for band in RULES["grade_bands"]]


def base_grade(total: Decimal) -> str:
    for lower_raw, grade in RULES["grade_bands"]:
        if total >= D(lower_raw):
            return grade
    return "D"


def apply_grade_cap(grade: str, caps: Iterable[str]) -> str:
    positions = [GRADE_ORDER.index(grade)]
    positions.extend(GRADE_ORDER.index(cap) for cap in caps if cap)
    return GRADE_ORDER[max(positions)]


def evidence_columns(observation: Observation | None) -> dict[str, str]:
    fact = observation.fact if observation else None
    return {
        "fact_id": observation.fact_id if observation else "",
        "input_fact_ids": ";".join(observation.input_fact_ids) if observation else "",
        "fact_status": fact.get("status", "") if fact else "",
        "period": fact.get("period", "") if fact else "",
        "period_type": fact.get("period_type", "") if fact else "",
        "scope": fact.get("scope", "") if fact else "",
        "attribution": fact.get("attribution", "") if fact else "",
        "audit_status": fact.get("audit_status", "") if fact else "",
        "formula": fact.get("formula", "") if fact else "",
        "source_file": fact.get("source_file", "") if fact else "",
        "locator_type": fact.get("locator_type", "") if fact else "",
        "locator": fact.get("locator", "") if fact else "",
        "source_line_item": fact.get("source_line_item", "") if fact else "",
        "source_trace": observation.source_trace if observation else "",
        "legacy_source": observation.source if observation else "",
        "input_line": str(observation.line_no) if observation else "",
        "input_notes": observation.notes if observation else "",
    }


def core_details(entity: EntityInput, mode: str) -> tuple[list[dict[str, Any]], dict[str, Decimal | None], dict[str, int]]:
    details: list[dict[str, Any]] = []
    dim_scores: dict[str, Decimal | None] = {}
    dim_counts: dict[str, int] = {}
    for dim in DIM_ORDER:
        scores: list[Decimal] = []
        for slot in RULES["dimensions"][dim]["metrics"]:
            observation = select_observation(entity, slot, mode)
            status = observation.status if observation else "missing"
            score: int | None = None
            band = ""
            value = observation.value if observation else None
            if observation and status == "present" and value is not None:
                hit = score_metric(slot, value, entity.subsector)
                score, band = hit.score, hit.band
            elif observation and status == "turnaround":
                score, band = 4, "turnaround-fixed"
            elif observation and status == "turn_loss":
                score, band = 1, "turn-loss-fixed"
            if score is not None:
                scores.append(D(score))
            detail = {
                "record_type": "core_score",
                "dimension": dim,
                "metric": slot,
                "input_metric": observation.input_metric if observation else "",
                "input_status": status,
                "evaluation_state": "scored" if score is not None else status,
                "value": decimal_text(value),
                "unit": observation.unit if observation else RULES["metrics"][slot]["unit"],
                "score": "" if score is None else str(score),
                "matched_band": band,
                "nm_reason": observation.nm_reason if observation else "",
                "evidence_status": observation.evidence_status if observation else "missing",
                "evidence_message": observation.evidence_message if observation else "",
                "nominal_deduction": "",
                "grade_cap": "",
                "message": "",
            }
            detail.update(evidence_columns(observation))
            details.append(detail)
        dim_counts[dim] = len(scores)
        dim_scores[dim] = q(sum(scores) / D(len(scores)), Q_SCORE) if scores else None
    return details, dim_scores, dim_counts


def structural_details(entity: EntityInput) -> tuple[list[dict[str, Any]], Decimal, Decimal, list[str], list[str], int]:
    details: list[dict[str, Any]] = []
    nominal = ZERO
    caps: list[str] = []
    deduction_labels: list[str] = []
    complete = 0
    for metric, spec in RULES["structural"].items():
        observation = entity.observations.get(metric)
        state = "unknown"
        triggered = False
        value = observation.value if observation else None
        if observation and observation.status in {"present", "checked_clear", "triggered"}:
            complete += 1
            if spec["kind"] == "numeric" and value is not None:
                triggered = value > D(spec["threshold"])
            elif spec["kind"] == "boolean":
                triggered = observation.status == "triggered" or value == ONE
            state = "triggered" if triggered else "cleared"
        elif observation and observation.status == "not_applicable" and observation.evidence_status == "verified":
            complete += 1
            state = "cleared_not_applicable"

        amount = D(spec["deduction"]) if triggered else ZERO
        if triggered:
            nominal += amount
            trace = observation.source_trace or observation.source or "source-unavailable"
            deduction_labels.append(
                f"{spec['label']}:value={decimal_text(value)} {observation.unit};"
                f"fact={observation.fact_id or 'unverified'};source={trace};"
                f"nominal=-{decimal_text(amount, 2)}"
            )
            if spec.get("grade_cap"):
                caps.append(spec["grade_cap"])
        detail = {
            "record_type": "structural_flag",
            "dimension": "",
            "metric": metric,
            "input_metric": observation.input_metric if observation else "",
            "input_status": observation.status if observation else "missing",
            "evaluation_state": state,
            "value": decimal_text(value),
            "unit": observation.unit if observation else spec["unit"],
            "score": "",
            "matched_band": f">{spec['threshold']}" if spec["kind"] == "numeric" else "=1",
            "nm_reason": observation.nm_reason if observation else "",
            "evidence_status": observation.evidence_status if observation else "missing",
            "evidence_message": observation.evidence_message if observation else "",
            "nominal_deduction": decimal_text(amount, 2) if triggered else "",
            "grade_cap": spec.get("grade_cap") or "",
            "message": spec["label"] if triggered else "",
        }
        detail.update(evidence_columns(observation))
        details.append(detail)
    applied = min(nominal, D(RULES["deduction_cap"]))
    if nominal > applied:
        deduction_labels.append(f"名义扣分{decimal_text(nominal, 2)}，按规则封顶{decimal_text(applied, 2)}")
    return details, nominal, applied, caps, deduction_labels, complete


def alert_details(entity: EntityInput) -> tuple[list[dict[str, Any]], list[str], int]:
    details: list[dict[str, Any]] = []
    triggered_labels: list[str] = []
    checked = 0
    for metric, spec in RULES["alerts"].items():
        observation = entity.observations.get(metric)
        state = "unknown"
        value = observation.value if observation else None
        triggered = False
        if observation and observation.status == "present" and value is not None:
            checked += 1
            threshold = D(spec["threshold"])
            direction = spec["direction"]
            if direction == "below":
                triggered = value < threshold
            elif direction == "above":
                triggered = value > threshold
            elif direction == "above_heavy":
                triggered = entity.subsector in HEAVY and value > threshold
            state = "triggered" if triggered else "cleared"
        if triggered:
            triggered_labels.append(spec["label"])
        detail = {
            "record_type": "alert",
            "dimension": "",
            "metric": metric,
            "input_metric": observation.input_metric if observation else "",
            "input_status": observation.status if observation else "missing",
            "evaluation_state": state,
            "value": decimal_text(value),
            "unit": observation.unit if observation else spec["unit"],
            "score": "",
            "matched_band": f"{spec['direction']} {spec['threshold']}",
            "nm_reason": observation.nm_reason if observation else "",
            "evidence_status": observation.evidence_status if observation else "missing",
            "evidence_message": observation.evidence_message if observation else "",
            "nominal_deduction": "",
            "grade_cap": "",
            "message": spec["label"] if triggered else "",
        }
        detail.update(evidence_columns(observation))
        details.append(detail)

    subsidy = entity.observations.get("government_grant_pnl_ratio")
    if subsidy and subsidy.value is not None and subsidy.value > D("55"):
        triggered_labels.append("政府补助/利润总额>55%")
    return details, triggered_labels, checked


def percent(numerator: int, denominator: int) -> Decimal:
    return (D(numerator) * D("100") / D(denominator)) if denominator else ZERO


def evaluate_entity(entity: EntityInput, mode: str) -> dict[str, Any]:
    core, dims, dim_counts = core_details(entity, mode)
    structural, nominal_deduction, applied_deduction, caps, deduction_labels, structural_checked = structural_details(entity)
    alerts, alert_labels, alert_checked = alert_details(entity)

    scored_rows = [row for row in core if row["evaluation_state"] == "scored"]
    scored_count = len(scored_rows)
    explicit_na = sum(
        row["input_status"] == "not_applicable" and row["evidence_status"] == "verified"
        for row in core
    )
    nm_count = sum(row["input_status"] == "not_meaningful" for row in core)
    applicable_count = len(CORE_SLOTS) - explicit_na
    evidence_count = sum(row["evidence_status"] == "verified" for row in scored_rows)
    audited_count = sum(row["audit_status"] == "audited" and row["evidence_status"] == "verified" for row in scored_rows)
    raw_coverage = percent(scored_count, len(CORE_SLOTS))
    applicable_coverage = percent(scored_count, applicable_count)
    evidence_coverage = percent(evidence_count, len(CORE_SLOTS))
    scored_evidence_coverage = percent(evidence_count, scored_count)
    audited_coverage = percent(audited_count, scored_count)
    structural_coverage = percent(structural_checked, len(STRUCTURAL_METRICS))
    alert_coverage = percent(alert_checked, len(ALERT_METRICS))

    weights = RULES["weights"][weight_group(entity.subsector)]
    numerator = ZERO
    denominator = ZERO
    for dim in DIM_ORDER:
        if dims[dim] is not None:
            weight = D(weights[dim])
            numerator += dims[dim] * weight
            denominator += weight
    raw_total = q(numerator / denominator, Q_SCORE) if denominator else None
    if raw_total is None:
        total = None
        diagnostic_grade = ""
    else:
        total = q(max(ONE, min(D("5"), raw_total - applied_deduction)), Q_SCORE)
        diagnostic_grade = apply_grade_cap(base_grade(total), caps)

    formal_dimensions = all(
        dim_counts[dim] >= int(RULES["dimensions"][dim]["formal_minimum"])
        and all(
            any(row["metric"] == required and row["evaluation_state"] == "scored" for row in core)
            for required in RULES["dimensions"][dim]["required"]
        )
        for dim in DIM_ORDER
    )
    provisional_dimensions = all(
        dim_counts[dim] >= int(RULES["dimensions"][dim]["provisional_minimum"])
        and all(
            any(row["metric"] == required and row["evaluation_state"] == "scored" for row in core)
            for required in RULES["dimensions"][dim]["required"]
        )
        for dim in DIM_ORDER
    )
    all_scored_evidence = scored_count > 0 and evidence_count == scored_count and audited_count == scored_count
    exemptions_verified = all(
        row["input_status"] not in {"not_applicable", "not_meaningful"}
        or row["evidence_status"] == "verified"
        for row in core
    )
    structural_complete = structural_checked == len(STRUCTURAL_METRICS) and all(
        row["evaluation_state"] != "unknown" and row["evidence_status"] == "verified"
        for row in structural
    )
    business_ok = entity.business_scope_status in {"pure_play", "segment_scored"}
    comparable = entity.comparability_status == "comparable"
    limited = entity.comparability_status == "limited"

    reasons: list[str] = []
    if mode != "strict":
        reasons.append("legacy_input_no_fact_contract")
    if raw_coverage < D("85"):
        reasons.append("raw_coverage_below_85")
    if not formal_dimensions:
        reasons.append("formal_dimension_minimum_not_met")
    if not all_scored_evidence:
        reasons.append("scored_evidence_or_audit_incomplete")
    if not exemptions_verified:
        reasons.append("exemption_evidence_incomplete")
    if not structural_complete:
        reasons.append("structural_screen_incomplete")
    if not business_ok:
        reasons.append("business_scope_not_eligible")
    if not comparable:
        reasons.append("comparability_not_full")

    if mode != "strict":
        rating_state = "LEGACY_DIAGNOSTIC"
        confidence = "低"
        rating = "N/R"
        formal = False
    elif (
        raw_coverage >= D("85") and formal_dimensions and all_scored_evidence
        and exemptions_verified and structural_complete and business_ok and comparable
        and total is not None
    ):
        rating_state = "FORMAL"
        confidence = "高"
        rating = diagnostic_grade
        formal = True
    elif (
        raw_coverage >= D("70") and provisional_dimensions and all_scored_evidence
        and exemptions_verified and structural_complete and business_ok
        and entity.comparability_status in {"comparable", "limited"}
        and total is not None
    ):
        rating_state = "PROVISIONAL"
        confidence = "中"
        rating = diagnostic_grade + "*"
        formal = False
    else:
        rating_state = "N_R"
        confidence = "低"
        rating = "N/R"
        formal = False

    ranking_eligible = (
        formal and comparable and business_ok and bool(entity.fy) and bool(entity.peer_group)
    )
    for row in core + structural + alerts:
        row.update({
            "company": entity.company,
            "entity_id": entity.entity_id,
            "subsector": entity.subsector,
            "fy": entity.fy,
            "peer_group": entity.peer_group,
            "rules_version": RULES_VERSION,
        })

    return {
        "entity": entity,
        "details": core + structural + alerts,
        "dims": dims,
        "dim_counts": dim_counts,
        "core_scored": scored_count,
        "core_applicable": applicable_count,
        "not_meaningful_count": nm_count,
        "raw_coverage": q(raw_coverage, Q_COVERAGE),
        "applicable_coverage": q(applicable_coverage, Q_COVERAGE),
        "evidence_coverage": q(evidence_coverage, Q_COVERAGE),
        "scored_evidence_coverage": q(scored_evidence_coverage, Q_COVERAGE),
        "audited_coverage": q(audited_coverage, Q_COVERAGE),
        "structural_coverage": q(structural_coverage, Q_COVERAGE),
        "alert_coverage": q(alert_coverage, Q_COVERAGE),
        "raw_total": raw_total,
        "nominal_deduction": nominal_deduction,
        "applied_deduction": applied_deduction,
        "total": total,
        "diagnostic_grade": diagnostic_grade,
        "rating_state": rating_state,
        "rating": rating,
        "confidence": confidence,
        "formal": formal,
        "ranking_eligible": ranking_eligible,
        "eligibility_reasons": reasons,
        "deduction_labels": deduction_labels,
        "alerts": alert_labels,
        "peer_rank": "",
        "peer_tier": "",
        "peer_sample_size": 0,
    }


def assign_rankings(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        entity = result["entity"]
        if result["ranking_eligible"]:
            groups[(entity.subsector, entity.fy, entity.peer_group, entity.calibration_status)].append(result)

    ranking_rows: list[dict[str, Any]] = []
    tolerance = D(RULES["tie_tolerance"])
    for (subsector, fy, peer_group, calibration_status), members in sorted(groups.items()):
        members.sort(key=lambda item: (-item["total"], item["entity"].entity_id))
        size = len(members)
        for member in members:
            member["peer_sample_size"] = size
        if size < 2:
            continue
        index = 0
        tier = 1
        while index < size:
            anchor = members[index]["total"]
            end = index + 1
            while end < size and anchor - members[end]["total"] < tolerance:
                end += 1
            rank_text = str(index + 1) if end - index == 1 else f"{index + 1}-{end}"
            for member in members[index:end]:
                member["peer_rank"] = rank_text
                member["peer_tier"] = str(tier)
                ranking_rows.append({
                    "subsector": subsector,
                    "fy": fy,
                    "peer_group": peer_group,
                    "calibration_status": calibration_status,
                    "peer_rank": rank_text,
                    "peer_tier": tier,
                    "peer_sample_size": size,
                    "company": member["entity"].company,
                    "entity_id": member["entity"].entity_id,
                    "total": decimal_text(member["total"], 2),
                    "rating": member["rating"],
                    "rules_version": RULES_VERSION,
                    "tie_rule": f"anchor difference < {RULES['tie_tolerance']}",
                })
            index = end
            tier += 1
    return ranking_rows


SUMMARY_FIELDS = [
    "company", "entity_id", "subsector", "fy", "peer_group",
    "D1", "D2", "D3", "D4", "D5", "D6",
    "D1_count", "D2_count", "D3_count", "D4_count", "D5_count", "D6_count",
    "core_scored", "core_applicable", "not_meaningful_count",
    "raw_coverage_pct", "applicable_coverage_pct", "evidence_coverage_pct",
    "scored_evidence_coverage_pct", "audited_scored_coverage_pct",
    "structural_screen_coverage_pct", "alert_screen_coverage_pct",
    "raw_total", "nominal_deduction", "applied_deduction", "total",
    "diagnostic_grade", "rating_state", "rating", "confidence", "formal",
    "ranking_eligible", "peer_rank", "peer_tier", "peer_sample_size",
    "comparability_status", "business_scope_status", "semiconductor_revenue_share",
    "calibration_status", "eligibility_reasons", "deductions", "alerts", "rules_version",
]

DETAIL_FIELDS = [
    "company", "entity_id", "subsector", "fy", "peer_group", "record_type",
    "dimension", "metric", "input_metric", "input_status", "evaluation_state",
    "value", "unit", "score", "matched_band", "nm_reason", "evidence_status",
    "evidence_message", "fact_id", "input_fact_ids", "fact_status", "period",
    "period_type", "scope", "attribution", "audit_status", "formula",
    "source_file", "locator_type", "locator", "source_line_item", "source_trace",
    "legacy_source", "input_line", "input_notes", "nominal_deduction", "grade_cap",
    "message", "rules_version",
]

RANKING_FIELDS = [
    "subsector", "fy", "peer_group", "calibration_status", "peer_rank", "peer_tier",
    "peer_sample_size", "company", "entity_id", "total", "rating",
    "rules_version", "tie_rule",
]


def summary_row(result: dict[str, Any]) -> dict[str, Any]:
    entity = result["entity"]
    row: dict[str, Any] = {
        "company": entity.company,
        "entity_id": entity.entity_id,
        "subsector": entity.subsector,
        "fy": entity.fy,
        "peer_group": entity.peer_group,
        "core_scored": result["core_scored"],
        "core_applicable": result["core_applicable"],
        "not_meaningful_count": result["not_meaningful_count"],
        "raw_coverage_pct": decimal_text(result["raw_coverage"], 1),
        "applicable_coverage_pct": decimal_text(result["applicable_coverage"], 1),
        "evidence_coverage_pct": decimal_text(result["evidence_coverage"], 1),
        "scored_evidence_coverage_pct": decimal_text(result["scored_evidence_coverage"], 1),
        "audited_scored_coverage_pct": decimal_text(result["audited_coverage"], 1),
        "structural_screen_coverage_pct": decimal_text(result["structural_coverage"], 1),
        "alert_screen_coverage_pct": decimal_text(result["alert_coverage"], 1),
        "raw_total": decimal_text(result["raw_total"], 2),
        "nominal_deduction": decimal_text(result["nominal_deduction"], 2),
        "applied_deduction": decimal_text(result["applied_deduction"], 2),
        "total": decimal_text(result["total"], 2),
        "diagnostic_grade": result["diagnostic_grade"],
        "rating_state": result["rating_state"],
        "rating": result["rating"],
        "confidence": result["confidence"],
        "formal": str(result["formal"]).lower(),
        "ranking_eligible": str(result["ranking_eligible"]).lower(),
        "peer_rank": result["peer_rank"],
        "peer_tier": result["peer_tier"],
        "peer_sample_size": result["peer_sample_size"],
        "comparability_status": entity.comparability_status,
        "business_scope_status": entity.business_scope_status,
        "semiconductor_revenue_share": decimal_text(entity.semiconductor_revenue_share),
        "calibration_status": entity.calibration_status,
        "eligibility_reasons": ";".join(result["eligibility_reasons"]),
        "deductions": ";".join(result["deduction_labels"]),
        "alerts": ";".join(result["alerts"]),
        "rules_version": RULES_VERSION,
    }
    for dim in DIM_ORDER:
        row[dim] = decimal_text(result["dims"][dim], 2)
        row[f"{dim}_count"] = result["dim_counts"][dim]
    return row


LEGACY_HEADER = [
    "公司", "子行业", "D1成长持续性", "D2盈利能力", "D3现金流质量",
    "D4资产负债", "D5盈利质量", "D6创新投入", "覆盖率%", "置信度",
    "原始分", "结构性扣分", "总分", "评级", "扣分明细", "不扣分预警",
]


def legacy_row(result: dict[str, Any]) -> list[str]:
    entity = result["entity"]
    return [
        entity.company,
        entity.subsector,
        *[decimal_text(result["dims"][dim], 2) for dim in DIM_ORDER],
        decimal_text(result["raw_coverage"], 1),
        result["confidence"],
        decimal_text(result["raw_total"], 2),
        decimal_text(result["applied_deduction"], 2),
        decimal_text(result["total"], 2),
        result["rating"],
        ";".join(result["deduction_labels"]),
        ";".join(result["alerts"]),
    ]


def write_dict_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_legacy_csv(path: Path, results: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(LEGACY_HEADER)
        for result in results:
            writer.writerow(legacy_row(result))


def output_manifest(
    out_dir: Path,
    input_path: Path,
    facts_path: Path | None,
    source_root: Path | None,
    mode: str,
    results: list[dict[str, Any]],
    warnings: list[str],
    fact_validation: dict[str, Any] | None,
    output_paths: list[Path],
) -> None:
    state_counts = Counter(result["rating_state"] for result in results)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "rules_version": RULES_VERSION,
        "rules_sha256": rules_digest(),
        "engine_sha256": sha256_file(Path(__file__)),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "rounding": "Decimal ROUND_HALF_UP; dimensions and totals shown to 2 decimals",
        "coverage_contract": {
            "raw": f"scored core slots / {len(CORE_SLOTS)}; governs rating eligibility",
            "applicable": f"scored / ({len(CORE_SLOTS)} - verified not_applicable); informational",
            "evidence": f"verified scored core slots / {len(CORE_SLOTS)}",
        },
        "ranking_contract": {
            "cohort": "FORMAL only; same subsector, FY, peer_group and calibration_status",
            "tie_rule": f"anchor score difference < {RULES['tie_tolerance']}",
        },
        "input": {"path": str(input_path.resolve()), "sha256": sha256_file(input_path)},
        "facts": (
            {"path": str(facts_path.resolve()), "sha256": sha256_file(facts_path), "source_root": str(source_root.resolve()) if source_root else "", "validation": fact_validation}
            if facts_path else None
        ),
        "entity_count": len(results),
        "rating_state_counts": dict(sorted(state_counts.items())),
        "warning_count": len(warnings),
        "warnings": warnings,
        "outputs": [
            {"path": path.name, "sha256": sha256_file(path)} for path in output_paths
        ],
    }
    (out_dir / "score_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_output_package(
    out_dir: Path,
    input_path: Path,
    facts_path: Path | None,
    source_root: Path | None,
    mode: str,
    results: list[dict[str, Any]],
    ranking_rows: list[dict[str, Any]],
    warnings: list[str],
    fact_validation: dict[str, Any] | None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "score_summary.csv"
    detail_path = out_dir / "score_detail.csv"
    ranking_path = out_dir / "ranking.csv"
    write_dict_csv(summary_path, SUMMARY_FIELDS, (summary_row(result) for result in results))
    write_dict_csv(detail_path, DETAIL_FIELDS, (row for result in results for row in result["details"]))
    write_dict_csv(ranking_path, RANKING_FIELDS, ranking_rows)
    shutil.copyfile(input_path, out_dir / "score_inputs.snapshot.csv")
    output_paths = [summary_path, detail_path, ranking_path, out_dir / "score_inputs.snapshot.csv"]
    if facts_path:
        shutil.copyfile(facts_path, out_dir / "facts.snapshot.csv")
        output_paths.append(out_dir / "facts.snapshot.csv")
    output_manifest(
        out_dir, input_path, facts_path, source_root, mode, results, warnings,
        fact_validation, output_paths,
    )


def print_summary(results: list[dict[str, Any]]) -> None:
    header = ["公司/实体", "子行业", "FY", "原始覆盖", "证据覆盖", "总分", "诊断档位", "发布评级", "状态", "同业名次"]
    rows = []
    for result in results:
        entity = result["entity"]
        rows.append([
            entity.entity_id,
            entity.subsector,
            entity.fy or "-",
            decimal_text(result["raw_coverage"], 1) + "%",
            decimal_text(result["evidence_coverage"], 1) + "%",
            decimal_text(result["total"], 2) or "-",
            result["diagnostic_grade"] or "-",
            result["rating"],
            result["rating_state"],
            result["peer_rank"] or "-",
        ])
    widths = [max(len(str(header[index])), *(len(str(row[index])) for row in rows)) for index in range(len(header))]
    fmt = "  ".join("{:<%d}" % width for width in widths)
    print(fmt.format(*header))
    for row in rows:
        print(fmt.format(*row))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="评分长表CSV")
    parser.add_argument("--mode", choices=("compat", "strict"), default="compat", help="compat只给诊断分；strict可给正式评级")
    parser.add_argument("--facts", type=Path, help="caiwu-fenxi事实账本；strict必需")
    parser.add_argument("--source-root", type=Path, help="事实来源文件根目录")
    parser.add_argument("--skip-source-check", action="store_true", help="仅兼容诊断可跳过来源文件检查")
    parser.add_argument("--out", type=Path, help="写出兼容中文汇总CSV")
    parser.add_argument("--out-dir", type=Path, help="写出summary/detail/ranking/manifest及输入快照")
    parser.add_argument("--quiet", action="store_true", help="不打印终端汇总")
    return parser


def run(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str]]:
    input_path: Path = args.csv
    if not input_path.exists():
        raise ValueError(f"输入文件不存在: {input_path}")
    if args.mode == "strict" and not args.facts:
        raise ValueError("strict模式必须提供--facts")
    if args.mode == "strict" and args.skip_source_check:
        raise ValueError("strict模式不允许--skip-source-check")
    if args.facts and not args.facts.exists():
        raise ValueError(f"facts文件不存在: {args.facts}")

    entities, warnings = parse_input(input_path, args.mode)
    fact_validation = None
    facts: dict[str, dict[str, str]] = {}
    if args.facts:
        fact_validation = run_fact_validator(args.facts, args.source_root, args.skip_source_check)
        facts = load_facts(args.facts)
    if args.mode == "strict":
        for entity in entities:
            verify_evidence(entity, facts)

    results = [evaluate_entity(entity, args.mode) for entity in entities]
    ranking_rows = assign_rankings(results)
    results.sort(key=lambda item: (item["entity"].subsector, item["entity"].fy, item["entity"].peer_group, item["entity"].entity_id))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        write_legacy_csv(args.out, results)
    if args.out_dir:
        write_output_package(
            args.out_dir, input_path, args.facts, args.source_root, args.mode,
            results, ranking_rows, warnings, fact_validation,
        )
    if not args.quiet:
        print_summary(results)
        for warning in warnings[:20]:
            print(f"WARNING: {warning}", file=sys.stderr)
        if len(warnings) > 20:
            suffix = "完整列表见manifest" if args.out_dir else "使用--out-dir保存完整manifest"
            print(f"WARNING: 另有{len(warnings) - 20}条兼容诊断，{suffix}", file=sys.stderr)
        if args.out:
            print(f"\n兼容汇总已写入 {args.out}")
        if args.out_dir:
            print(f"输出包已写入 {args.out_dir}")
    return results, warnings


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run(args)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
