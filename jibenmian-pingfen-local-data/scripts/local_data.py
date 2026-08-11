#!/usr/bin/env python3
"""Prepare score inputs directly from /home/fss/data structured financial CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


D = Decimal
ZERO = D("0")
HUNDRED = D("100")
Q = D("0.00000001")
DEFAULT_DATA_ROOT = Path("/home/fss/data")
DATASET_DIR = "上市公司财务信息"

INCOME = "利润表数据"
BALANCE = "资产负债表数据"
CASHFLOW = "现金流量表数据"
INDICATORS = "财务指标数据"
AUDIT = "财务审计意见数据"

FACT_FIELDS = [
    "fact_id", "company", "metric", "period", "period_type", "scope",
    "attribution", "value", "unit", "currency", "status", "audit_status",
    "source_file", "locator_type", "locator", "source_line_item", "formula",
    "input_fact_ids", "notes",
]
SCORE_FIELDS = [
    "company", "entity_id", "subsector", "fy", "peer_group", "metric",
    "value", "unit", "status", "nm_reason", "fact_id", "input_fact_ids",
    "comparability_status", "business_scope_status",
    "semiconductor_revenue_share", "calibration_status", "source", "notes",
]
DUPONT_FIELDS = [
    "company", "entity_id", "fy", "scope",
    "revenue_fact_id", "net_profit_parent_fact_id", "net_profit_total_fact_id",
    "total_assets_open_fact_id", "total_assets_close_fact_id",
    "parent_equity_open_fact_id", "parent_equity_close_fact_id",
    "total_equity_open_fact_id", "total_equity_close_fact_id",
    "disclosed_roe_fact_id", "notes",
]


def _text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _q(value: Decimal) -> Decimal:
    return value.quantize(Q, rounding=ROUND_HALF_UP)


def _decimal(raw: str | None) -> Decimal | None:
    text = "" if raw is None else str(raw).strip()
    if not text:
        return None
    try:
        value = D(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _date_key(raw: str) -> str:
    return "".join(character for character in raw if character.isdigit())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_dataset_root(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    nested = candidate / DATASET_DIR
    if nested.is_dir():
        candidate = nested
    required = [INCOME, BALANCE, CASHFLOW, INDICATORS, AUDIT]
    missing = [name for name in required if not (candidate / name).is_dir()]
    if missing:
        raise ValueError(
            f"数据根目录缺少必需子目录: {','.join(missing)}; 当前目录={candidate}"
        )
    return candidate


@dataclass(frozen=True)
class SourceRow:
    table: str
    path: Path
    relative_path: str
    line_no: int
    values: dict[str, str]

    def value(self, column: str) -> Decimal | None:
        return _decimal(self.values.get(column))


class Dataset:
    def __init__(self, root: Path, ticker: str):
        self.root = resolve_dataset_root(root)
        self.ticker = ticker.upper()
        self._cache: dict[str, list[SourceRow]] = {}

    def rows(self, table: str) -> list[SourceRow]:
        if table in self._cache:
            return self._cache[table]
        path = self.root / table / f"{self.ticker}.csv"
        if not path.is_file():
            raise ValueError(f"找不到证券数据文件: {path}")
        rows: list[SourceRow] = []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"CSV没有表头: {path}")
            for line_no, raw in enumerate(reader, start=2):
                values = {
                    key: "" if value is None else str(value).strip()
                    for key, value in raw.items()
                    if key is not None
                }
                rows.append(
                    SourceRow(
                        table=table,
                        path=path,
                        relative_path=str(path.relative_to(self.root)),
                        line_no=line_no,
                        values=values,
                    )
                )
        self._cache[table] = rows
        return rows

    def audit_row(self, year: int) -> SourceRow | None:
        audit_path = self.root / AUDIT / f"{self.ticker}.csv"
        if not audit_path.is_file():
            return None
        period = f"{year}1231"
        candidates = [
            row for row in self.rows(AUDIT)
            if _date_key(row.values.get("报告期", "")) == period
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: (_date_key(row.values.get("公告日期", "")), row.line_no))

    def annual_row(
        self,
        table: str,
        year: int,
        relevant_columns: Iterable[str],
    ) -> SourceRow | None:
        period = f"{year}1231"
        candidates: list[SourceRow] = []
        for row in self.rows(table):
            values = row.values
            if _date_key(values.get("报告期", "")) != period:
                continue
            if values.get("报告期类型") and values["报告期类型"] != "年报":
                continue
            report_type = values.get("报告类型") or values.get("报表类型")
            if report_type and report_type != "合并报表":
                continue
            candidates.append(row)
        if not candidates:
            return None

        audit = self.audit_row(year)
        if audit:
            audit_date = _date_key(audit.values.get("公告日期", ""))
            aligned = [
                row for row in candidates
                if _date_key(row.values.get("公告日期", "")) == audit_date
                or _date_key(row.values.get("实际公告日期", "")) == audit_date
            ]
            if aligned:
                candidates = aligned

        latest_date = max(
            max(
                _date_key(row.values.get("公告日期", "")),
                _date_key(row.values.get("实际公告日期", "")),
            )
            for row in candidates
        )
        latest = [
            row for row in candidates
            if latest_date
            == max(
                _date_key(row.values.get("公告日期", "")),
                _date_key(row.values.get("实际公告日期", "")),
            )
        ]
        columns = list(relevant_columns)
        best_completeness = max(
            sum(bool(row.values.get(column, "")) for column in columns)
            for row in latest
        )
        best = [
            row for row in latest
            if sum(bool(row.values.get(column, "")) for column in columns)
            == best_completeness
        ]
        signatures = {
            tuple(row.values.get(column, "") for column in columns)
            for row in best
        }
        if len(signatures) > 1:
            locations = ",".join(str(row.line_no) for row in best)
            raise ValueError(
                f"{self.ticker}/{table}/FY{year}: 同一审计日期关键字段冲突，CSV行={locations}"
            )
        return max(best, key=lambda row: row.line_no)

    def quarter_row(
        self,
        table: str,
        year: int,
        quarter: int,
        relevant_columns: Iterable[str],
    ) -> SourceRow | None:
        if quarter not in {1, 2, 3}:
            raise ValueError("季度只支持Q1、Q2、Q3；Q4请使用完整FY")
        month_day = {1: "0331", 2: "0630", 3: "0930"}[quarter]
        report_name = {1: "一季报", 2: "半年报", 3: "三季报"}[quarter]
        period = f"{year}{month_day}"
        candidates: list[SourceRow] = []
        for row in self.rows(table):
            values = row.values
            if _date_key(values.get("报告期", "")) != period:
                continue
            if values.get("报告期类型") and values["报告期类型"] != report_name:
                continue
            report_type = values.get("报告类型") or values.get("报表类型")
            if report_type and report_type != "合并报表":
                continue
            candidates.append(row)
        if not candidates:
            return None

        latest_date = max(
            max(
                _date_key(row.values.get("公告日期", "")),
                _date_key(row.values.get("实际公告日期", "")),
            )
            for row in candidates
        )
        latest = [
            row for row in candidates
            if latest_date
            == max(
                _date_key(row.values.get("公告日期", "")),
                _date_key(row.values.get("实际公告日期", "")),
            )
        ]
        columns = list(relevant_columns)
        best_completeness = max(
            sum(bool(row.values.get(column, "")) for column in columns)
            for row in latest
        )
        best = [
            row for row in latest
            if sum(bool(row.values.get(column, "")) for column in columns)
            == best_completeness
        ]
        signatures = {
            tuple(row.values.get(column, "") for column in columns)
            for row in best
        }
        if len(signatures) > 1:
            locations = ",".join(str(row.line_no) for row in best)
            raise ValueError(
                f"{self.ticker}/{table}/{year}Q{quarter}: "
                f"同一公告日期关键字段冲突，CSV行={locations}"
            )
        return max(best, key=lambda row: row.line_no)

    def audit_status(self, year: int) -> str:
        return "audited" if self.audit_row(year) else "unaudited"

    def source_files(self) -> list[Path]:
        return sorted({rows[0].path for rows in self._cache.values() if rows})


class FactBook:
    def __init__(self, dataset: Dataset, company: str):
        self.dataset = dataset
        self.company = company
        self.facts: list[dict[str, str]] = []
        self.by_id: dict[str, dict[str, str]] = {}
        self._ticker_slug = dataset.ticker.lower().replace(".", "-")

    def _id(self, metric: str, period: str) -> str:
        slug = metric.lower().replace("_", "-").replace(":", "-")
        base = f"{self._ticker_slug}-{period.lower()}-{slug}"
        fact_id = base
        counter = 2
        while fact_id in self.by_id:
            fact_id = f"{base}-{counter}"
            counter += 1
        return fact_id

    def add_source(
        self,
        *,
        metric: str,
        year: int,
        row: SourceRow,
        column: str,
        attribution: str = "na",
        unit: str = "yuan",
        period_type: str = "fy",
        notes: str = "",
        formula: str = "",
        value_override: Decimal | None = None,
        period_override: str | None = None,
        audit_status_override: str | None = None,
    ) -> str | None:
        value = value_override if value_override is not None else row.value(column)
        if value is None:
            return None
        period = (
            period_override
            if period_override
            else (f"FY{year}" if period_type == "fy" else f"{year}-12-31")
        )
        fact_id = self._id(metric, period)
        fact = {
            "fact_id": fact_id,
            "company": self.company,
            "metric": metric,
            "period": period,
            "period_type": period_type,
            "scope": "consolidated",
            "attribution": attribution,
            "value": _text(value),
            "unit": unit,
            "currency": "CNY" if unit == "yuan" else "N/A",
            "status": "reported",
            "audit_status": audit_status_override or self.dataset.audit_status(year),
            "source_file": row.relative_path,
            "locator_type": "csv_row",
            "locator": str(row.line_no),
            "source_line_item": column,
            "formula": formula,
            "input_fact_ids": "",
            "notes": notes,
        }
        self.facts.append(fact)
        self.by_id[fact_id] = fact
        return fact_id

    def add_calculated(
        self,
        *,
        metric: str,
        year: int,
        value: Decimal,
        unit: str,
        attribution: str,
        formula: str,
        input_ids: Iterable[str],
        notes: str = "",
        period_override: str | None = None,
    ) -> str:
        dependencies = list(input_ids)
        audit_status = (
            "audited"
            if dependencies
            and all(self.by_id[item]["audit_status"] == "audited" for item in dependencies)
            else "unaudited"
        )
        period = period_override or f"FY{year}"
        fact_id = self._id(metric, period)
        fact = {
            "fact_id": fact_id,
            "company": self.company,
            "metric": metric,
            "period": period,
            "period_type": "quarter_ttm" if "Q" in period else "fy",
            "scope": "consolidated",
            "attribution": attribution,
            "value": _text(_q(value)),
            "unit": unit,
            "currency": "CNY" if unit == "yuan" else "N/A",
            "status": "calculated",
            "audit_status": audit_status,
            "source_file": "",
            "locator_type": "formula",
            "locator": "",
            "source_line_item": "",
            "formula": formula,
            "input_fact_ids": ";".join(dependencies),
            "notes": notes,
        }
        self.facts.append(fact)
        self.by_id[fact_id] = fact
        return fact_id

    def value(self, fact_id: str | None) -> Decimal | None:
        return D(self.by_id[fact_id]["value"]) if fact_id else None


@dataclass
class EntityConfig:
    ticker: str
    company: str
    subsector: str
    year: int
    entity_id: str
    peer_group: str
    comparability_status: str
    business_scope_status: str
    semiconductor_revenue_share: Decimal
    calibration_status: str
    period_label: str
    quarter: int = 0

    @property
    def latest_complete_fy(self) -> int:
        return self.year - 1 if self.quarter else self.year

    @property
    def quarterly(self) -> bool:
        return self.quarter in {1, 2, 3}


class Preparer:
    def __init__(self, dataset: Dataset, config: EntityConfig):
        self.dataset = dataset
        self.config = config
        self.book = FactBook(dataset, config.company)
        self.rows: list[dict[str, str]] = []
        self.ids: dict[tuple[str, int], str | None] = {}

    def _meta(self) -> dict[str, str]:
        return {
            "company": self.config.company,
            "entity_id": self.config.entity_id,
            "subsector": self.config.subsector,
            "fy": self.config.period_label,
            "peer_group": self.config.peer_group,
            "comparability_status": self.config.comparability_status,
            "business_scope_status": self.config.business_scope_status,
            "semiconductor_revenue_share": _text(self.config.semiconductor_revenue_share),
            "calibration_status": self.config.calibration_status,
        }

    def add_score(
        self,
        metric: str,
        unit: str,
        *,
        fact_id: str | None = None,
        status: str = "present",
        nm_reason: str = "",
        input_ids: Iterable[str] = (),
        notes: str = "",
    ) -> None:
        value = self.book.by_id[fact_id]["value"] if fact_id and status == "present" else ""
        source = "由/home/fss/data结构化CSV直接计算" if fact_id else ""
        self.rows.append(
            {
                **self._meta(),
                "metric": metric,
                "value": value,
                "unit": unit,
                "status": status,
                "nm_reason": nm_reason,
                "fact_id": fact_id or "",
                "input_fact_ids": ";".join(input_ids),
                "source": source,
                "notes": notes,
            }
        )

    def _raw(
        self,
        metric: str,
        year: int,
        table: str,
        row: SourceRow | None,
        column: str,
        *,
        attribution: str = "na",
        period_type: str = "fy",
        unit: str = "yuan",
        notes: str = "",
        period_override: str | None = None,
        audit_status_override: str | None = None,
    ) -> str | None:
        if row is None:
            return None
        fact_id = self.book.add_source(
            metric=metric,
            year=year,
            row=row,
            column=column,
            attribution=attribution,
            period_type=period_type,
            unit=unit,
            notes=notes,
            period_override=period_override,
            audit_status_override=audit_status_override,
        )
        self.ids[(metric, year)] = fact_id
        return fact_id

    def _calc(
        self,
        metric: str,
        value: Decimal,
        unit: str,
        attribution: str,
        formula: str,
        input_ids: Iterable[str],
        notes: str = "",
    ) -> str:
        return self.book.add_calculated(
            metric=metric,
            year=self.config.year,
            value=value,
            unit=unit,
            attribution=attribution,
            formula=formula,
            input_ids=input_ids,
            notes=notes,
            period_override=self.config.period_label,
        )

    def _annual_rows(self, year: int) -> dict[str, SourceRow | None]:
        return {
            INCOME: self.dataset.annual_row(
                INCOME,
                year,
                [
                    "营业收入", "减:营业成本", "净利润(含少数股东损益)",
                    "净利润(不含少数股东损益)", "利润总额", "研发费用",
                    "减:资产减值损失", "信用减值损失", "其他资产减值损失",
                ],
            ),
            BALANCE: self.dataset.annual_row(
                BALANCE,
                year,
                [
                    "资产总计", "负债合计", "流动资产合计", "流动负债合计",
                    "商誉", "股东权益合计(不含少数股东权益)",
                    "股东权益合计(含少数股东权益)",
                ],
            ),
            CASHFLOW: self.dataset.annual_row(
                CASHFLOW,
                year,
                [
                    "经营活动产生的现金流量净额",
                    "购建固定资产、无形资产和其他长期资产支付的现金",
                    "销售商品、提供劳务收到的现金",
                    "期末现金及现金等价物余额",
                ],
            ),
            INDICATORS: self.dataset.annual_row(
                INDICATORS,
                year,
                [
                    "扣非净利润", "加权平均净资产收益率", "带息债务",
                    "存货周转天数", "折旧与摊销",
                ],
            ),
        }

    def collect_raw_facts(self) -> None:
        for year in range(self.config.year - 3, self.config.year + 1):
            rows = self._annual_rows(year)
            self._raw("revenue", year, INCOME, rows[INCOME], "营业收入")
            self._raw(
                "net_profit_parent", year, INCOME, rows[INCOME],
                "净利润(不含少数股东损益)", attribution="parent",
            )
            self._raw(
                "net_profit_total", year, INCOME, rows[INCOME],
                "净利润(含少数股东损益)", attribution="total",
            )
            self._raw("profit_before_tax", year, INCOME, rows[INCOME], "利润总额")
            self._raw("operating_cost", year, INCOME, rows[INCOME], "减:营业成本")
            self._raw("rd_expense", year, INCOME, rows[INCOME], "研发费用")
            self._raw(
                "nps_parent", year, INDICATORS, rows[INDICATORS],
                "扣非净利润", attribution="parent",
            )
            self._raw(
                "roe_weighted_parent", year, INDICATORS, rows[INDICATORS],
                "加权平均净资产收益率", attribution="parent", unit="percent",
            )
            self._raw(
                "interest_bearing_debt", year, INDICATORS, rows[INDICATORS], "带息债务"
            )
            self._raw(
                "inventory_days", year, INDICATORS, rows[INDICATORS],
                "存货周转天数", unit="days",
            )
            self._raw(
                "depreciation_amortization", year, INDICATORS, rows[INDICATORS],
                "折旧与摊销",
            )
            self._raw(
                "operating_cash_flow_raw", year, CASHFLOW, rows[CASHFLOW],
                "经营活动产生的现金流量净额",
            )
            self._raw(
                "long_term_asset_capex", year, CASHFLOW, rows[CASHFLOW],
                "购建固定资产、无形资产和其他长期资产支付的现金",
            )
            self._raw(
                "cash_receipts", year, CASHFLOW, rows[CASHFLOW],
                "销售商品、提供劳务收到的现金",
            )
            self._raw(
                "cash_and_cash_equivalents", year, CASHFLOW, rows[CASHFLOW],
                "期末现金及现金等价物余额", period_type="point_in_time",
            )
            self._raw(
                "total_assets", year, BALANCE, rows[BALANCE],
                "资产总计", period_type="point_in_time",
            )
            self._raw(
                "total_liabilities", year, BALANCE, rows[BALANCE],
                "负债合计", period_type="point_in_time",
            )
            self._raw(
                "current_assets", year, BALANCE, rows[BALANCE],
                "流动资产合计", period_type="point_in_time",
            )
            self._raw(
                "current_liabilities", year, BALANCE, rows[BALANCE],
                "流动负债合计", period_type="point_in_time",
            )
            self._raw(
                "goodwill", year, BALANCE, rows[BALANCE],
                "商誉", period_type="point_in_time",
            )
            self._raw(
                "equity_parent", year, BALANCE, rows[BALANCE],
                "股东权益合计(不含少数股东权益)",
                attribution="parent", period_type="point_in_time",
            )
            self._raw(
                "equity_total", year, BALANCE, rows[BALANCE],
                "股东权益合计(含少数股东权益)",
                attribution="total", period_type="point_in_time",
            )

    def fact(self, metric: str, year: int | None = None) -> tuple[str | None, Decimal | None]:
        fact_id = self.ids.get((metric, year or self.config.year))
        return fact_id, self.book.value(fact_id)

    def score_growth(self) -> None:
        year = self.config.year
        current_id, current = self.fact("revenue")
        prior_id, prior = self.fact("revenue", year - 1)
        if current_id and prior_id and prior and prior > ZERO:
            fact_id = self._calc(
                "rev_growth", (current / prior - D("1")) * HUNDRED,
                "percent", "na", "(revenue_t/revenue_t_1-1)*100",
                [current_id, prior_id],
            )
            self.add_score("rev_growth", "percent", fact_id=fact_id)
        else:
            self.add_score("rev_growth", "percent", status="missing", nm_reason="source_unavailable")

        revenue_ids = [self.fact("revenue", item)[0] for item in range(year, year - 4, -1)]
        if all(revenue_ids):
            revenue_values = [self.book.value(item) for item in revenue_ids]
            if all(value is not None and value > ZERO for value in revenue_values):
                growth = ((revenue_values[0] / revenue_values[-1]).ln() / D("3")).exp() - D("1")
                fact_id = self._calc(
                    "rev_cagr_3y", growth * HUNDRED, "percent", "na",
                    "(revenue_t/revenue_t_3)^(1/3)-1",
                    revenue_ids,
                )
                self.add_score(
                    "rev_cagr_3y", "percent", fact_id=fact_id, input_ids=revenue_ids
                )
            else:
                self.add_score(
                    "rev_cagr_3y", "percent", status="not_meaningful",
                    nm_reason="sign_change", input_ids=revenue_ids,
                )
        else:
            self.add_score(
                "rev_cagr_3y", "percent", status="missing",
                nm_reason="insufficient_history",
            )

        current_nps_id, current_nps = self.fact("nps_parent")
        prior_nps_id, prior_nps = self.fact("nps_parent", year - 1)
        nps_pair = [item for item in [current_nps_id, prior_nps_id] if item]
        if current_nps_id and prior_nps_id and current_nps is not None and prior_nps is not None:
            if current_nps > ZERO and prior_nps <= ZERO:
                self.add_score(
                    "nps_growth", "percent", status="turnaround", input_ids=nps_pair
                )
            elif current_nps <= ZERO < prior_nps:
                self.add_score(
                    "nps_growth", "percent", status="turn_loss", input_ids=nps_pair
                )
            elif prior_nps > ZERO:
                fact_id = self._calc(
                    "nps_growth", (current_nps / prior_nps - D("1")) * HUNDRED,
                    "percent", "parent", "(nps_t/nps_t_1-1)*100", nps_pair,
                )
                self.add_score("nps_growth", "percent", fact_id=fact_id)
            else:
                reason = "zero_denominator" if prior_nps == ZERO else "negative_denominator"
                self.add_score(
                    "nps_growth", "percent", status="not_meaningful",
                    nm_reason=reason, input_ids=nps_pair,
                )
        else:
            self.add_score("nps_growth", "percent", status="missing", nm_reason="source_unavailable")

        nps_ids = [self.fact("nps_parent", item)[0] for item in range(year, year - 4, -1)]
        if all(nps_ids):
            values = [self.book.value(item) for item in nps_ids]
            if all(value is not None and value > ZERO for value in values):
                growth = ((values[0] / values[-1]).ln() / D("3")).exp() - D("1")
                fact_id = self._calc(
                    "nps_cagr_3y", growth * HUNDRED, "percent", "parent",
                    "(nps_t/nps_t_3)^(1/3)-1", nps_ids,
                )
                self.add_score(
                    "nps_cagr_3y", "percent", fact_id=fact_id, input_ids=nps_ids
                )
            else:
                reason = "turnaround_window" if any(value > ZERO for value in values) else "negative_denominator"
                self.add_score(
                    "nps_cagr_3y", "percent", status="not_meaningful",
                    nm_reason=reason, input_ids=nps_ids,
                )
        else:
            self.add_score(
                "nps_cagr_3y", "percent", status="missing",
                nm_reason="insufficient_history",
            )

    def score_profitability(self) -> None:
        revenue_id, revenue = self.fact("revenue")
        cost_id, cost = self.fact("operating_cost")
        parent_id, parent_profit = self.fact("net_profit_parent")
        roe_id, _ = self.fact("roe_weighted_parent")
        if revenue_id and cost_id and revenue and revenue != ZERO:
            fact_id = self._calc(
                "gross_margin_total", (revenue - cost) / revenue * HUNDRED,
                "percent", "na", "(revenue-operating_cost)/revenue*100",
                [revenue_id, cost_id],
            )
            self.add_score("gross_margin_total", "percent", fact_id=fact_id)
        else:
            self.add_score(
                "gross_margin_total", "percent", status="missing", nm_reason="source_unavailable"
            )
        if revenue_id and parent_id and revenue and revenue != ZERO:
            fact_id = self._calc(
                "net_margin_parent", parent_profit / revenue * HUNDRED,
                "percent", "parent", "net_profit_parent/revenue*100",
                [parent_id, revenue_id],
            )
            self.add_score("net_margin_parent", "percent", fact_id=fact_id)
        else:
            self.add_score(
                "net_margin_parent", "percent", status="missing", nm_reason="source_unavailable"
            )
        if roe_id:
            self.add_score("roe_weighted_parent", "percent", fact_id=roe_id)
        else:
            self.add_score(
                "roe_weighted_parent", "percent", status="missing", nm_reason="source_unavailable"
            )

    def score_cash_flow(self) -> None:
        year = self.config.year
        years = [year, year - 1, year - 2]
        ocf_ids = [self.fact("operating_cash_flow_raw", item)[0] for item in years]
        profit_ids = [self.fact("net_profit_parent", item)[0] for item in years]
        if all(ocf_ids) and all(profit_ids):
            ocf_sum = sum((self.book.value(item) for item in ocf_ids), ZERO)
            profit_sum = sum((self.book.value(item) for item in profit_ids), ZERO)
            sum_ocf_id = self._calc(
                "operating_cash_flow_3y_sum", ocf_sum, "yuan", "na",
                "sum(operating_cash_flow_t..t_2)", ocf_ids,
            )
            sum_profit_id = self._calc(
                "net_profit_parent_3y_sum", profit_sum, "yuan", "parent",
                "sum(net_profit_parent_t..t_2)", profit_ids,
            )
            if profit_sum > ZERO:
                conversion = ocf_sum / profit_sum
                if abs(conversion) > D("20"):
                    self.add_score(
                        "cash_conversion_parent_3y", "ratio",
                        status="not_meaningful",
                        nm_reason="near_zero_denominator",
                        input_ids=[sum_ocf_id, sum_profit_id],
                        notes="三年现金转换比率绝对值>20，异常分母效应，不参与评分",
                    )
                else:
                    fact_id = self._calc(
                        "cash_conversion_parent_3y", conversion,
                        "ratio", "parent", "ocf_3y_sum/net_profit_parent_3y_sum",
                        [sum_ocf_id, sum_profit_id],
                    )
                    self.add_score("cash_conversion_parent_3y", "ratio", fact_id=fact_id)
            else:
                reason = "zero_denominator" if profit_sum == ZERO else "negative_denominator"
                self.add_score(
                    "cash_conversion_parent_3y", "ratio", status="not_meaningful",
                    nm_reason=reason, input_ids=[sum_ocf_id, sum_profit_id],
                )
        else:
            self.add_score(
                "cash_conversion_parent_3y", "ratio", status="missing",
                nm_reason="insufficient_history",
            )
            ocf_id, ocf = self.fact("operating_cash_flow_raw")
            profit_id, profit = self.fact("net_profit_parent")
            if ocf_id and profit_id and profit and profit > ZERO:
                conversion = ocf / profit
                if abs(conversion) > D("20"):
                    self.add_score(
                        "cash_conversion_parent_fy", "ratio",
                        status="not_meaningful",
                        nm_reason="near_zero_denominator",
                        input_ids=[ocf_id, profit_id],
                        notes="单年现金转换比率绝对值>20，异常分母效应，不参与评分",
                    )
                else:
                    fact_id = self._calc(
                        "cash_conversion_parent_fy", conversion, "ratio", "parent",
                        "operating_cash_flow/net_profit_parent", [ocf_id, profit_id],
                    )
                    self.add_score("cash_conversion_parent_fy", "ratio", fact_id=fact_id)

        revenue_id, revenue = self.fact("revenue")
        ocf_id, ocf = self.fact("operating_cash_flow_raw")
        capex_id, capex = self.fact("long_term_asset_capex")
        receipts_id, receipts = self.fact("cash_receipts")
        if revenue_id and ocf_id and capex_id and revenue and revenue != ZERO:
            fact_id = self._calc(
                "fcf_long_term_assets_margin", (ocf - capex) / revenue * HUNDRED,
                "percent", "na",
                "(operating_cash_flow-long_term_asset_capex)/revenue*100",
                [ocf_id, capex_id, revenue_id],
                "长期资产现金支出口径，不是pure-PPE FCF",
            )
            self.add_score("fcf_long_term_assets_margin", "percent", fact_id=fact_id)
        else:
            self.add_score(
                "fcf_long_term_assets_margin", "percent",
                status="missing", nm_reason="source_unavailable",
            )
        if revenue_id and receipts_id and revenue and revenue != ZERO:
            fact_id = self._calc(
                "cash_receipts_to_revenue", receipts / revenue, "ratio", "na",
                "cash_receipts/revenue", [receipts_id, revenue_id],
            )
            self.add_score("cash_receipts_to_revenue", "ratio", fact_id=fact_id)
        else:
            self.add_score(
                "cash_receipts_to_revenue", "ratio",
                status="missing", nm_reason="source_unavailable",
            )

    def score_balance_sheet(self) -> None:
        assets_id, assets = self.fact("total_assets")
        liabilities_id, liabilities = self.fact("total_liabilities")
        current_assets_id, current_assets = self.fact("current_assets")
        current_liabilities_id, current_liabilities = self.fact("current_liabilities")
        cash_id, cash = self.fact("cash_and_cash_equivalents")
        debt_id, debt = self.fact("interest_bearing_debt")
        if assets_id and liabilities_id and assets and assets != ZERO:
            fact_id = self._calc(
                "debt_to_assets", liabilities / assets * HUNDRED,
                "percent", "na", "total_liabilities/total_assets*100",
                [liabilities_id, assets_id],
            )
            self.add_score("debt_to_assets", "percent", fact_id=fact_id)
        else:
            self.add_score("debt_to_assets", "percent", status="missing", nm_reason="source_unavailable")
        if (
            current_assets_id and current_liabilities_id
            and current_liabilities and current_liabilities > ZERO
        ):
            fact_id = self._calc(
                "current_ratio", current_assets / current_liabilities,
                "ratio", "na", "current_assets/current_liabilities",
                [current_assets_id, current_liabilities_id],
            )
            self.add_score("current_ratio", "ratio", fact_id=fact_id)
        else:
            self.add_score("current_ratio", "ratio", status="missing", nm_reason="source_unavailable")
        if assets_id and cash_id and debt_id and assets and assets != ZERO:
            fact_id = self._calc(
                "net_cash_to_assets", (cash - debt) / assets * HUNDRED,
                "percent", "na",
                "(cash_and_cash_equivalents-interest_bearing_debt)/total_assets*100",
                [cash_id, debt_id, assets_id],
                "现金等价物减财务指标数据中的带息债务",
            )
            self.add_score("net_cash_to_assets", "percent", fact_id=fact_id)
        else:
            self.add_score(
                "net_cash_to_assets", "percent", status="missing", nm_reason="source_unavailable"
            )

    def score_quality_and_innovation(self) -> None:
        revenue_id, revenue = self.fact("revenue")
        parent_id, parent_profit = self.fact("net_profit_parent")
        nps_id, nps = self.fact("nps_parent")
        rd_id, rd = self.fact("rd_expense")
        if parent_id and nps_id and parent_profit and parent_profit != ZERO:
            recurring_ratio = nps / parent_profit
            if abs(recurring_ratio) > D("10"):
                self.add_score(
                    "recurring_parent_profit_ratio", "ratio",
                    status="not_meaningful",
                    nm_reason="near_zero_denominator",
                    input_ids=[nps_id, parent_id],
                    notes="扣非/归母绝对值>10，异常分母效应，不参与评分",
                )
            else:
                fact_id = self._calc(
                    "recurring_parent_profit_ratio", recurring_ratio,
                    "ratio", "parent", "nps_parent/net_profit_parent",
                    [nps_id, parent_id],
                )
                self.add_score("recurring_parent_profit_ratio", "ratio", fact_id=fact_id)
        elif parent_id and nps_id:
            self.add_score(
                "recurring_parent_profit_ratio", "ratio",
                status="not_meaningful", nm_reason="zero_denominator",
                input_ids=[nps_id, parent_id],
            )
        else:
            self.add_score(
                "recurring_parent_profit_ratio", "ratio",
                status="missing", nm_reason="source_unavailable",
            )
        self.add_score(
            "government_grant_pnl_ratio", "percent",
            status="missing", nm_reason="not_extracted",
            notes="本地表没有可防重复的政府补助当期损益明细",
        )
        self.add_score(
            "rd_capitalization_rate", "percent",
            status="missing", nm_reason="not_extracted",
            notes="期末研发支出余额不能替代当期资本化研发投入",
        )
        if revenue_id and rd_id and revenue and revenue != ZERO:
            fact_id = self._calc(
                "rd_expense_intensity", rd / revenue * HUNDRED,
                "percent", "na", "rd_expense/revenue*100", [rd_id, revenue_id],
            )
            self.add_score("rd_expense_intensity", "percent", fact_id=fact_id)
        else:
            self.add_score(
                "rd_expense_intensity", "percent",
                status="missing", nm_reason="source_unavailable",
            )

    def score_structural_and_alerts(self) -> None:
        goodwill_id, goodwill = self.fact("goodwill")
        equity_id, equity = self.fact("equity_parent")
        if goodwill_id and equity_id and equity and equity > ZERO:
            fact_id = self._calc(
                "goodwill_to_parent_equity", goodwill / equity * HUNDRED,
                "percent", "parent", "goodwill/equity_parent*100",
                [goodwill_id, equity_id],
            )
            self.add_score("goodwill_to_parent_equity", "percent", fact_id=fact_id)
        elif equity_id and equity and equity > ZERO and goodwill_id is None:
            self.add_score(
                "goodwill_to_parent_equity", "percent",
                status="missing", nm_reason="source_unavailable",
                notes="空值不自动解释为零",
            )
        else:
            self.add_score(
                "goodwill_to_parent_equity", "percent",
                status="missing", nm_reason="source_unavailable",
            )

        for metric, note in [
            ("largest_billed_customer_revenue_ratio", "数据集没有最大直接客户收入占比"),
            ("largest_supplier_purchase_ratio", "数据集没有最大供应商采购占比"),
            ("performance_commitment_flag", "数据集没有业绩承诺履约核查"),
            ("debt_default", "数据集没有债务违约核查"),
        ]:
            unit = "boolean" if metric.endswith("_flag") or metric == "debt_default" else "percent"
            self.add_score(
                metric, unit, status="missing", nm_reason="source_unavailable", notes=note
            )

        self.add_audit_issue()

        ocf_id, _ = self.fact("operating_cash_flow_raw")
        if ocf_id:
            alert_id = self._calc(
                "operating_cash_flow", self.book.value(ocf_id),
                "yuan", "na", "identity(operating_cash_flow_raw)", [ocf_id],
            )
            self.add_score("operating_cash_flow", "yuan", fact_id=alert_id)
        else:
            self.add_score(
                "operating_cash_flow", "yuan", status="missing", nm_reason="source_unavailable"
            )

        inventory_id, inventory = self.fact("inventory_days")
        prior_inventory_id, prior_inventory = self.fact(
            "inventory_days", self.config.year - 1
        )
        if inventory_id and prior_inventory_id:
            fact_id = self._calc(
                "inventory_days_change", inventory - prior_inventory,
                "days", "na", "inventory_days_t-inventory_days_t_1",
                [inventory_id, prior_inventory_id],
            )
            self.add_score("inventory_days_change", "days", fact_id=fact_id)
        else:
            self.add_score(
                "inventory_days_change", "days",
                status="missing", nm_reason="source_unavailable",
            )

        self.add_score(
            "impairment_to_pbt", "percent", status="missing",
            nm_reason="not_extracted",
            notes="减值字段符号与列间重叠未统一，保守保持缺失",
        )
        da_id, da = self.fact("depreciation_amortization")
        revenue_id, revenue = self.fact("revenue")
        if da_id and revenue_id and revenue and revenue != ZERO:
            fact_id = self._calc(
                "da_to_revenue", da / revenue * HUNDRED,
                "percent", "na", "depreciation_amortization/revenue*100",
                [da_id, revenue_id],
            )
            self.add_score("da_to_revenue", "percent", fact_id=fact_id)
        else:
            self.add_score(
                "da_to_revenue", "percent", status="missing", nm_reason="source_unavailable"
            )
        self.add_score(
            "top5_billed_customer_revenue_ratio", "percent",
            status="missing", nm_reason="source_unavailable",
            notes="数据集没有前五大直接客户收入占比",
        )
        self.add_score(
            "top5_supplier_purchase_ratio", "percent",
            status="missing", nm_reason="source_unavailable",
            notes="数据集没有前五大供应商采购占比",
        )

    def add_audit_issue(self) -> None:
        audit = self.dataset.audit_row(self.config.latest_complete_fy)
        if audit:
            opinion = audit.values.get("审计结果", "")
            issue_value = ZERO if opinion == "标准无保留意见" else D("1")
            fact_id = self.book.add_source(
                metric="audit_issue",
                year=self.config.latest_complete_fy,
                row=audit,
                column="审计结果",
                attribution="na",
                unit="boolean",
                notes=f"审计意见={opinion}",
                formula="audit_opinion_to_issue_flag",
                value_override=issue_value,
                period_override=self.config.period_label,
            )
            if fact_id:
                self.book.by_id[fact_id]["status"] = "calculated"
                self.add_score(
                    "audit_issue", "boolean", fact_id=fact_id,
                    status="checked_clear" if issue_value == ZERO else "triggered",
                )
        else:
            self.add_score(
                "audit_issue", "boolean", status="missing",
                nm_reason="source_unavailable",
            )

    def dupont_row(self) -> dict[str, str] | None:
        year = self.config.year
        mapping = {
            "revenue_fact_id": self.fact("revenue")[0],
            "net_profit_parent_fact_id": self.fact("net_profit_parent")[0],
            "net_profit_total_fact_id": self.fact("net_profit_total")[0],
            "total_assets_open_fact_id": self.fact("total_assets", year - 1)[0],
            "total_assets_close_fact_id": self.fact("total_assets", year)[0],
            "parent_equity_open_fact_id": self.fact("equity_parent", year - 1)[0],
            "parent_equity_close_fact_id": self.fact("equity_parent", year)[0],
            "total_equity_open_fact_id": self.fact("equity_total", year - 1)[0],
            "total_equity_close_fact_id": self.fact("equity_total", year)[0],
            "disclosed_roe_fact_id": self.fact("roe_weighted_parent")[0],
        }
        if not all(mapping.values()):
            return None
        return {
            "company": self.config.company,
            "entity_id": self.config.entity_id,
            "fy": f"FY{year}",
            "scope": "consolidated",
            **mapping,
            "notes": "由本地结构化CSV直接生成fact-ID映射",
        }

    def prepare(self) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str] | None]:
        self.collect_raw_facts()
        self.score_growth()
        self.score_profitability()
        self.score_cash_flow()
        self.score_balance_sheet()
        self.score_quality_and_innovation()
        self.score_structural_and_alerts()
        return self.book.facts, self.rows, self.dupont_row()


class QuarterlyPreparer(Preparer):
    """Prepare a quarter-end diagnostic using TTM flows and quarter-end balances."""

    FLOW_SPECS = [
        ("revenue", "revenue_ytd", INCOME, "营业收入", "na"),
        ("operating_cost", "operating_cost_ytd", INCOME, "减:营业成本", "na"),
        (
            "net_profit_parent", "net_profit_parent_ytd", INCOME,
            "净利润(不含少数股东损益)", "parent",
        ),
        (
            "net_profit_total", "net_profit_total_ytd", INCOME,
            "净利润(含少数股东损益)", "total",
        ),
        ("profit_before_tax", "profit_before_tax_ytd", INCOME, "利润总额", "na"),
        ("rd_expense", "rd_expense_ytd", INCOME, "研发费用", "na"),
        ("nps_parent", "nps_parent_ytd", INDICATORS, "扣非净利润", "parent"),
        (
            "depreciation_amortization", "depreciation_amortization_ytd",
            INDICATORS, "折旧与摊销", "na",
        ),
        (
            "operating_cash_flow_raw", "operating_cash_flow_ytd",
            CASHFLOW, "经营活动产生的现金流量净额", "na",
        ),
        (
            "long_term_asset_capex", "long_term_asset_capex_ytd",
            CASHFLOW, "购建固定资产、无形资产和其他长期资产支付的现金", "na",
        ),
        (
            "cash_receipts", "cash_receipts_ytd",
            CASHFLOW, "销售商品、提供劳务收到的现金", "na",
        ),
    ]

    def _quarter_rows(self, year: int) -> dict[str, SourceRow | None]:
        quarter = self.config.quarter
        return {
            INCOME: self.dataset.quarter_row(
                INCOME,
                year,
                quarter,
                [
                    "营业收入", "减:营业成本", "净利润(含少数股东损益)",
                    "净利润(不含少数股东损益)", "利润总额", "研发费用",
                ],
            ),
            BALANCE: self.dataset.quarter_row(
                BALANCE,
                year,
                quarter,
                [
                    "资产总计", "负债合计", "流动资产合计", "流动负债合计",
                    "商誉", "股东权益合计(不含少数股东权益)",
                    "股东权益合计(含少数股东权益)",
                ],
            ),
            CASHFLOW: self.dataset.quarter_row(
                CASHFLOW,
                year,
                quarter,
                [
                    "经营活动产生的现金流量净额",
                    "购建固定资产、无形资产和其他长期资产支付的现金",
                    "销售商品、提供劳务收到的现金",
                    "期末现金及现金等价物余额",
                ],
            ),
            INDICATORS: self.dataset.quarter_row(
                INDICATORS,
                year,
                quarter,
                [
                    "扣非净利润", "带息债务", "存货周转天数",
                    "折旧与摊销",
                ],
            ),
        }

    def _quarter_period(self, year: int) -> str:
        return f"{year}Q{self.config.quarter}"

    def _collect_quarter_ytd(self, year: int) -> None:
        rows = self._quarter_rows(year)
        period = self._quarter_period(year)
        for _, ytd_metric, table, column, attribution in self.FLOW_SPECS:
            self._raw(
                ytd_metric,
                year,
                table,
                rows[table],
                column,
                attribution=attribution,
                period_type="quarter_ytd",
                period_override=period,
                audit_status_override="unaudited",
                notes=f"{period}年初至报告期累计值",
            )

    def _collect_quarter_point_facts(self) -> None:
        year = self.config.year
        rows = self._quarter_rows(year)
        period = self.config.period_label
        balance_specs = [
            ("total_assets", "资产总计", "na"),
            ("total_liabilities", "负债合计", "na"),
            ("current_assets", "流动资产合计", "na"),
            ("current_liabilities", "流动负债合计", "na"),
            ("goodwill", "商誉", "na"),
            ("equity_parent", "股东权益合计(不含少数股东权益)", "parent"),
            ("equity_total", "股东权益合计(含少数股东权益)", "total"),
        ]
        for metric, column, attribution in balance_specs:
            self._raw(
                metric,
                year,
                BALANCE,
                rows[BALANCE],
                column,
                attribution=attribution,
                period_type="point_in_time",
                period_override=period,
                audit_status_override="unaudited",
            )
        self._raw(
            "cash_and_cash_equivalents",
            year,
            CASHFLOW,
            rows[CASHFLOW],
            "期末现金及现金等价物余额",
            period_type="point_in_time",
            period_override=period,
            audit_status_override="unaudited",
        )
        self._raw(
            "interest_bearing_debt",
            year,
            INDICATORS,
            rows[INDICATORS],
            "带息债务",
            period_type="point_in_time",
            period_override=period,
            audit_status_override="unaudited",
        )
        self._raw(
            "inventory_days",
            year,
            INDICATORS,
            rows[INDICATORS],
            "存货周转天数",
            unit="days",
            period_type="quarter_ytd",
            period_override=period,
            audit_status_override="unaudited",
        )

        prior_year = year - 1
        prior_rows = self._quarter_rows(prior_year)
        self._raw(
            "inventory_days",
            prior_year,
            INDICATORS,
            prior_rows[INDICATORS],
            "存货周转天数",
            unit="days",
            period_type="quarter_ytd",
            period_override=self._quarter_period(prior_year),
            audit_status_override="unaudited",
        )

    def _build_ttm_fact(
        self,
        standard_metric: str,
        ytd_metric: str,
        attribution: str,
    ) -> None:
        latest_fy = self.config.latest_complete_fy
        annual_id = self.ids.get((standard_metric, latest_fy))
        current_ytd_id = self.ids.get((ytd_metric, self.config.year))
        prior_ytd_id = self.ids.get((ytd_metric, self.config.year - 1))
        if not (annual_id and current_ytd_id and prior_ytd_id):
            self.ids[(standard_metric, self.config.year)] = None
            return
        value = (
            self.book.value(annual_id)
            + self.book.value(current_ytd_id)
            - self.book.value(prior_ytd_id)
        )
        fact_id = self._calc(
            standard_metric,
            value,
            "yuan",
            attribution,
            "latest_complete_fy+current_ytd-prior_year_same_period_ytd",
            [annual_id, current_ytd_id, prior_ytd_id],
            "滚动十二个月(TTM)，包含未经年度审计的季度数据",
        )
        self.ids[(standard_metric, self.config.year)] = fact_id

    def collect_raw_facts(self) -> None:
        original_year = self.config.year
        current_rows = self._quarter_rows(original_year)
        missing_current = [
            table for table in (INCOME, BALANCE, CASHFLOW)
            if current_rows[table] is None
        ]
        if missing_current:
            raise ValueError(
                f"{self.config.period_label}尚无完整的当期结构化报表: "
                f"{','.join(missing_current)}"
            )
        self.config.year = self.config.latest_complete_fy
        try:
            super().collect_raw_facts()
        finally:
            self.config.year = original_year

        self._collect_quarter_ytd(original_year)
        self._collect_quarter_ytd(original_year - 1)
        self._collect_quarter_point_facts()
        for standard, ytd, _, _, attribution in self.FLOW_SPECS:
            self._build_ttm_fact(standard, ytd, attribution)

    def _score_cagr(
        self,
        score_metric: str,
        raw_metric: str,
        attribution: str,
    ) -> None:
        latest = self.config.latest_complete_fy
        ids = [self.fact(raw_metric, item)[0] for item in range(latest, latest - 4, -1)]
        if not all(ids):
            self.add_score(
                score_metric, "percent", status="missing",
                nm_reason="insufficient_history",
            )
            return
        values = [self.book.value(item) for item in ids]
        if all(value is not None and value > ZERO for value in values):
            growth = ((values[0] / values[-1]).ln() / D("3")).exp() - D("1")
            fact_id = self._calc(
                score_metric,
                growth * HUNDRED,
                "percent",
                attribution,
                f"FY{latest}/FY{latest - 3} three-year CAGR",
                ids,
                "季度诊断中的CAGR使用最近四个完整FY",
            )
            self.add_score(score_metric, "percent", fact_id=fact_id, input_ids=ids)
            return
        reason = (
            "turnaround_window"
            if raw_metric == "nps_parent" and any(value > ZERO for value in values)
            else ("negative_denominator" if raw_metric == "nps_parent" else "sign_change")
        )
        self.add_score(
            score_metric,
            "percent",
            status="not_meaningful",
            nm_reason=reason,
            input_ids=ids,
        )

    def score_growth(self) -> None:
        year = self.config.year
        current_rev_id = self.ids.get(("revenue_ytd", year))
        prior_rev_id = self.ids.get(("revenue_ytd", year - 1))
        current_rev = self.book.value(current_rev_id)
        prior_rev = self.book.value(prior_rev_id)
        if current_rev_id and prior_rev_id and prior_rev and prior_rev > ZERO:
            fact_id = self._calc(
                "rev_growth",
                (current_rev / prior_rev - D("1")) * HUNDRED,
                "percent",
                "na",
                "current_ytd/prior_year_same_period_ytd-1",
                [current_rev_id, prior_rev_id],
                "季度累计同比",
            )
            self.add_score("rev_growth", "percent", fact_id=fact_id)
        else:
            self.add_score(
                "rev_growth", "percent", status="missing", nm_reason="source_unavailable"
            )
        self._score_cagr("rev_cagr_3y", "revenue", "na")

        current_nps_id = self.ids.get(("nps_parent_ytd", year))
        prior_nps_id = self.ids.get(("nps_parent_ytd", year - 1))
        current_nps = self.book.value(current_nps_id)
        prior_nps = self.book.value(prior_nps_id)
        pair = [item for item in [current_nps_id, prior_nps_id] if item]
        if current_nps_id and prior_nps_id:
            if current_nps > ZERO and prior_nps <= ZERO:
                self.add_score("nps_growth", "percent", status="turnaround", input_ids=pair)
            elif current_nps <= ZERO < prior_nps:
                self.add_score("nps_growth", "percent", status="turn_loss", input_ids=pair)
            elif prior_nps > ZERO:
                fact_id = self._calc(
                    "nps_growth",
                    (current_nps / prior_nps - D("1")) * HUNDRED,
                    "percent",
                    "parent",
                    "current_ytd_nps/prior_year_same_period_ytd_nps-1",
                    pair,
                    "季度累计扣非归母净利润同比",
                )
                self.add_score("nps_growth", "percent", fact_id=fact_id)
            else:
                reason = "zero_denominator" if prior_nps == ZERO else "negative_denominator"
                self.add_score(
                    "nps_growth", "percent", status="not_meaningful",
                    nm_reason=reason, input_ids=pair,
                )
        else:
            self.add_score(
                "nps_growth", "percent", status="missing", nm_reason="source_unavailable",
                notes="当前或上年同期季度扣非净利润字段为空",
            )
        self._score_cagr("nps_cagr_3y", "nps_parent", "parent")

    def score_cash_flow(self) -> None:
        latest = self.config.latest_complete_fy
        years = [latest, latest - 1, latest - 2]
        ocf_ids = [self.fact("operating_cash_flow_raw", item)[0] for item in years]
        profit_ids = [self.fact("net_profit_parent", item)[0] for item in years]
        if all(ocf_ids) and all(profit_ids):
            ocf_sum = sum((self.book.value(item) for item in ocf_ids), ZERO)
            profit_sum = sum((self.book.value(item) for item in profit_ids), ZERO)
            sum_ocf_id = self._calc(
                "operating_cash_flow_3y_sum", ocf_sum, "yuan", "na",
                f"sum(FY{latest}..FY{latest - 2} operating_cash_flow)", ocf_ids,
            )
            sum_profit_id = self._calc(
                "net_profit_parent_3y_sum", profit_sum, "yuan", "parent",
                f"sum(FY{latest}..FY{latest - 2} net_profit_parent)", profit_ids,
            )
            if profit_sum > ZERO:
                conversion = ocf_sum / profit_sum
                if abs(conversion) > D("20"):
                    self.add_score(
                        "cash_conversion_parent_3y", "ratio",
                        status="not_meaningful",
                        nm_reason="near_zero_denominator",
                        input_ids=[sum_ocf_id, sum_profit_id],
                        notes=(
                            "三年现金转换比率绝对值>20，异常分母效应，不参与评分；"
                            "季度诊断使用最近三个完整FY"
                        ),
                    )
                else:
                    fact_id = self._calc(
                        "cash_conversion_parent_3y", conversion,
                        "ratio", "parent",
                        "three_complete_fy_ocf_sum/three_complete_fy_parent_profit_sum",
                        [sum_ocf_id, sum_profit_id],
                        "季度诊断中的三年现金转换使用最近三个完整FY",
                    )
                    self.add_score("cash_conversion_parent_3y", "ratio", fact_id=fact_id)
            else:
                reason = "zero_denominator" if profit_sum == ZERO else "negative_denominator"
                self.add_score(
                    "cash_conversion_parent_3y", "ratio",
                    status="not_meaningful", nm_reason=reason,
                    input_ids=[sum_ocf_id, sum_profit_id],
                )
        else:
            self.add_score(
                "cash_conversion_parent_3y", "ratio",
                status="missing", nm_reason="insufficient_history",
            )
            ocf_id, ocf = self.fact("operating_cash_flow_raw")
            profit_id, profit = self.fact("net_profit_parent")
            if ocf_id and profit_id and profit and profit > ZERO:
                conversion = ocf / profit
                if abs(conversion) > D("20"):
                    self.add_score(
                        "cash_conversion_parent_fy", "ratio",
                        status="not_meaningful",
                        nm_reason="near_zero_denominator",
                        input_ids=[ocf_id, profit_id],
                        notes="TTM现金转换比率绝对值>20，异常分母效应，不参与评分",
                    )
                else:
                    fact_id = self._calc(
                        "cash_conversion_parent_fy", conversion,
                        "ratio", "parent", "ttm_ocf/ttm_parent_profit",
                        [ocf_id, profit_id], "季度诊断回退TTM现金转换",
                    )
                    self.add_score("cash_conversion_parent_fy", "ratio", fact_id=fact_id)

        revenue_id, revenue = self.fact("revenue")
        ocf_id, ocf = self.fact("operating_cash_flow_raw")
        capex_id, capex = self.fact("long_term_asset_capex")
        receipts_id, receipts = self.fact("cash_receipts")
        if revenue_id and ocf_id and capex_id and revenue and revenue != ZERO:
            fact_id = self._calc(
                "fcf_long_term_assets_margin", (ocf - capex) / revenue * HUNDRED,
                "percent", "na",
                "(ttm_ocf-ttm_long_term_asset_capex)/ttm_revenue*100",
                [ocf_id, capex_id, revenue_id],
                "TTM长期资产现金支出口径",
            )
            self.add_score("fcf_long_term_assets_margin", "percent", fact_id=fact_id)
        else:
            self.add_score(
                "fcf_long_term_assets_margin", "percent",
                status="missing", nm_reason="source_unavailable",
            )
        if revenue_id and receipts_id and revenue and revenue != ZERO:
            fact_id = self._calc(
                "cash_receipts_to_revenue", receipts / revenue, "ratio", "na",
                "ttm_cash_receipts/ttm_revenue", [receipts_id, revenue_id],
            )
            self.add_score("cash_receipts_to_revenue", "ratio", fact_id=fact_id)
        else:
            self.add_score(
                "cash_receipts_to_revenue", "ratio",
                status="missing", nm_reason="source_unavailable",
            )

    def dupont_row(self) -> dict[str, str] | None:
        return None


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def prepare_local_inputs(args: argparse.Namespace) -> dict[str, Path | None]:
    raw_period = getattr(args, "period", None) or getattr(args, "fy", None)
    if not raw_period:
        raise ValueError("必须提供--fy或--period")
    normalized = str(raw_period).upper()
    if re.fullmatch(r"(?:FY)?\d{4}", normalized):
        year = int(normalized.removeprefix("FY"))
        quarter = 0
        period_label = f"FY{year}"
    else:
        match = re.fullmatch(r"(\d{4})Q([1-3])", normalized)
        if not match:
            raise ValueError("--period必须使用2026Q1、2026Q2或2026Q3形式；Q4请使用--fy")
        year = int(match.group(1))
        quarter = int(match.group(2))
        period_label = normalized
    ticker = args.ticker.upper()
    company = args.company or ticker
    share = D(str(args.semiconductor_revenue_share))
    if not ZERO <= share <= HUNDRED:
        raise ValueError("--semiconductor-revenue-share必须在0到100之间")
    if args.business_scope_status == "pure_play" and share < D("70"):
        raise ValueError("pure_play要求半导体主营收入占比至少70%")
    if args.business_scope_status == "diversified_unallocated" and share >= D("70"):
        raise ValueError("diversified_unallocated与半导体主营占比>=70%矛盾")

    dataset = Dataset(args.data_root, ticker)
    config = EntityConfig(
        ticker=ticker,
        company=company,
        subsector=args.subsector,
        year=year,
        entity_id=args.entity_id or ticker,
        peer_group=args.peer_group or f"{args.subsector}-cn-a",
        comparability_status=args.comparability_status,
        business_scope_status=args.business_scope_status,
        semiconductor_revenue_share=share,
        calibration_status=args.calibration_status,
        period_label=period_label,
        quarter=quarter,
    )
    preparer = QuarterlyPreparer(dataset, config) if config.quarterly else Preparer(dataset, config)
    facts, score_rows, dupont_row = preparer.prepare()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    facts_path = args.out_dir / "local-facts.csv"
    score_path = args.out_dir / "score-input.csv"
    dupont_path = args.out_dir / "dupont-input.csv" if dupont_row else None
    manifest_path = args.out_dir / "local-source-manifest.json"
    write_csv(facts_path, FACT_FIELDS, facts)
    write_csv(score_path, SCORE_FIELDS, score_rows)
    if dupont_path:
        write_csv(dupont_path, DUPONT_FIELDS, [dupont_row])
    manifest = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_root": str(dataset.root),
        "ticker": ticker,
        "company": company,
        "period": period_label,
        "period_mode": "quarter_ttm" if config.quarterly else "complete_fy",
        "latest_complete_fy": f"FY{config.latest_complete_fy}",
        "selection": (
            "quarter YTD + prior-year same-period YTD + latest complete FY => TTM; "
            "quarter-end consolidated balance"
            if config.quarterly
            else "complete FY + consolidated + audit announcement date"
        ),
        "source_files": [
            {
                "path": str(path.relative_to(dataset.root)),
                "sha256": _sha256(path),
            }
            for path in dataset.source_files()
        ],
        "outputs": {
            "facts": {"path": facts_path.name, "sha256": _sha256(facts_path)},
            "score_input": {"path": score_path.name, "sha256": _sha256(score_path)},
            "dupont_input": (
                {"path": dupont_path.name, "sha256": _sha256(dupont_path)}
                if dupont_path else None
            ),
        },
        "known_unavailable": [
            "government_grant_pnl_ratio",
            "rd_capitalization_rate",
            "largest_billed_customer_revenue_ratio",
            "largest_supplier_purchase_ratio",
            "performance_commitment_flag",
            "debt_default",
            "top5_billed_customer_revenue_ratio",
            "top5_supplier_purchase_ratio",
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "facts": facts_path,
        "score_input": score_path,
        "dupont_input": dupont_path,
        "manifest": manifest_path,
        "source_root": dataset.root,
        "period": period_label,
        "quarterly": config.quarterly,
    }


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ticker", required=True, help="证券代码，例如688981.SH")
    parser.add_argument("--subsector", required=True, choices=(
        "equipment", "materials", "foundry", "idm", "osat", "fabless", "eda", "ip",
    ))
    period_group = parser.add_mutually_exclusive_group(required=True)
    period_group.add_argument("--fy", help="完整年度，例如2025或FY2025")
    period_group.add_argument(
        "--period",
        help="季度诊断期间，例如2026Q1、2026Q2或2026Q3",
    )
    parser.add_argument("--company", help="公司名称；省略时使用证券代码")
    parser.add_argument("--entity-id", help="评分实体ID；省略时使用证券代码")
    parser.add_argument("--peer-group", help="同业池ID")
    parser.add_argument(
        "--comparability-status",
        choices=("comparable", "limited", "not_comparable", "unknown"),
        default="unknown",
    )
    parser.add_argument(
        "--business-scope-status",
        choices=("pure_play", "diversified_unallocated", "unknown"),
        default="unknown",
    )
    parser.add_argument("--semiconductor-revenue-share", type=D, default=D("0"))
    parser.add_argument(
        "--calibration-status",
        choices=("calibrated", "uncalibrated"),
        default="uncalibrated",
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--out-dir", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        paths = prepare_local_inputs(args)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"score_input={paths['score_input']}")
    print(f"facts={paths['facts']}")
    print(f"source_manifest={paths['manifest']}")
    if paths["dupont_input"]:
        print(f"dupont_input={paths['dupont_input']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
