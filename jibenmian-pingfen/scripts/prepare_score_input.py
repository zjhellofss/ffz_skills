#!/usr/bin/env python3
"""从 caiwu-fenxi facts.csv 生成 v2 score-input.csv，并补齐可重算的评分槽位事实。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from score import (  # noqa: E402
    ALERT_METRICS,
    CASH_3Y,
    CASH_FY,
    SCORE_INPUT_METRICS,
    STRUCTURAL_METRICS,
    load_facts,
    run_fact_validator,
)


D = Decimal
ZERO = D("0")
ONE = D("1")
HUNDRED = D("100")
Q = D("0.00000001")
SUBSECTORS = {"equipment", "materials", "foundry", "idm", "osat", "fabless", "eda", "ip"}
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
METRIC_UNITS = {
    "rev_growth": "percent",
    "rev_cagr_3y": "percent",
    "nps_growth": "percent",
    "nps_cagr_3y": "percent",
    "gross_margin_total": "percent",
    "net_margin_parent": "percent",
    "roe_weighted_parent": "percent",
    CASH_3Y: "ratio",
    CASH_FY: "ratio",
    "fcf_long_term_assets_margin": "percent",
    "cash_receipts_to_revenue": "ratio",
    "debt_to_assets": "percent",
    "current_ratio": "ratio",
    "net_cash_to_assets": "percent",
    "recurring_parent_profit_ratio": "ratio",
    "government_grant_pnl_ratio": "percent",
    "rd_capitalization_rate": "percent",
    "rd_expense_intensity": "percent",
    "goodwill_to_parent_equity": "percent",
    "largest_billed_customer_revenue_ratio": "percent",
    "largest_supplier_purchase_ratio": "percent",
    "performance_commitment_flag": "boolean",
    "audit_issue": "boolean",
    "debt_default": "boolean",
    "operating_cash_flow": "currency",
    "inventory_days_change": "days",
    "impairment_to_pbt": "percent",
    "da_to_revenue": "percent",
    "top5_billed_customer_revenue_ratio": "percent",
    "top5_supplier_purchase_ratio": "percent",
}
ALIASES = {
    "revenue": ("revenue",),
    "operating_cost": ("operating_cost", "cost_of_revenue"),
    "net_profit_parent": ("net_profit_parent",),
    "nps_parent": ("nps_parent", "net_profit_parent_ex_nonrecurring"),
    "roe_weighted_parent": ("roe_weighted_parent",),
    "operating_cash_flow": ("operating_cash_flow",),
    "long_term_capex": (
        "cash_paid_for_ppe_intangibles_and_other_long_term_assets",
        "long_term_asset_capex",
    ),
    "fcf_long_term": ("free_cash_flow_long_term_assets",),
    "cash_receipts": ("cash_receipts", "cash_received_from_sales_of_goods_and_services"),
    "total_assets": ("total_assets", "assets"),
    "total_liabilities": ("total_liabilities", "liabilities"),
    "current_assets": ("current_assets",),
    "current_liabilities": ("current_liabilities",),
    "cash": ("cash_and_cash_equivalents",),
    "interest_bearing_debt": ("interest_bearing_debt",),
    "goodwill": ("goodwill",),
    "equity_parent": ("equity_parent",),
    "rd_expense": ("rd_expense", "research_and_development_expense"),
    "profit_before_tax": ("profit_before_tax",),
    "inventory_days": ("inventory_days",),
    "depreciation_amortization": ("depreciation_amortization",),
    "impairment": ("impairment_loss", "asset_impairment_loss"),
    "rd_capitalized": ("rd_capitalized_current", "capitalized_development_cost"),
    "rd_total_investment": ("rd_total_investment",),
    "government_grant_pnl": ("government_grant_pnl_reconciled",),
}
BOOLEAN_METRICS = {"performance_commitment_flag", "audit_issue", "debt_default"}
POINT_ALIASES = {
    "total_assets", "total_liabilities", "current_assets", "current_liabilities",
    "cash", "interest_bearing_debt", "goodwill", "equity_parent",
}
CORE_REQUIRED = sorted(SCORE_INPUT_METRICS - {CASH_FY})
ALL_REQUIRED = CORE_REQUIRED + sorted(STRUCTURAL_METRICS) + sorted(ALERT_METRICS)


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


def _year_of(period: str) -> int | None:
    match = re.search(r"(?:FY)?(\d{4})", period)
    return int(match.group(1)) if match else None


def _usable(fact: dict[str, str]) -> bool:
    return fact.get("status") in {"reported", "calculated"} and bool(fact.get("value"))


class FactIndex:
    def __init__(self, facts: dict[str, dict[str, str]]):
        self.facts = dict(facts)
        self.order = list(facts)
        self.by_id = facts
        self.lookup: dict[tuple[str, str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
        self.instant_lookup: dict[tuple[str, int, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
        for fact in facts.values():
            if not _usable(fact):
                continue
            key = (fact["company"], fact["period"], fact["scope"], fact["metric"])
            self.lookup[key][fact["fact_id"]] = fact
            year = _year_of(fact.get("period", ""))
            if year is not None and fact.get("period_type") == "instant":
                instant_key = (fact["company"], year, fact["scope"], fact["metric"])
                self.instant_lookup[instant_key][fact["fact_id"]] = fact

    def _pick(
        self,
        bucket: dict[str, dict[str, str]],
        attribution: str | None,
    ) -> dict[str, str] | None:
        for fact in bucket.values():
            if attribution and fact.get("attribution") not in {attribution, "na"}:
                continue
            return fact
        return None

    def get(
        self,
        company: str,
        period: str,
        scope: str,
        names: Iterable[str],
        attribution: str | None = None,
        allow_instant: bool = False,
    ) -> dict[str, str] | None:
        year = _year_of(period)
        for name in names:
            found = self._pick(self.lookup.get((company, period, scope, name), {}), attribution)
            if found:
                return found
            if allow_instant and year is not None:
                found = self._pick(
                    self.instant_lookup.get((company, year, scope, name), {}),
                    attribution,
                )
                if found:
                    return found
        return None

    def add_calculated(
        self,
        *,
        company: str,
        metric: str,
        period: str,
        scope: str,
        attribution: str,
        value: Decimal,
        unit: str,
        formula: str,
        input_ids: list[str],
        notes: str = "",
        period_type: str = "fy",
    ) -> dict[str, str]:
        existing = self.get(
            company, period, scope, (metric,),
            attribution if attribution != "na" else None,
            allow_instant=True,
        )
        if existing:
            return existing
        slug = metric.lower().replace("_", "-")
        fact_id = f"{company}-{period}-{slug}".replace(" ", "")
        counter = 2
        while fact_id in self.facts:
            fact_id = f"{company}-{period}-{slug}-{counter}".replace(" ", "")
            counter += 1
        audits = [self.facts[item]["audit_status"] for item in input_ids if item in self.facts]
        audit_status = "audited" if audits and all(item == "audited" for item in audits) else (
            audits[0] if audits else "unknown"
        )
        currencies = {self.facts[item].get("currency", "N/A") for item in input_ids if item in self.facts}
        currency = "N/A" if unit in {"percent", "ratio", "days", "boolean"} else next(iter(currencies), "N/A")
        fact = {
            "fact_id": fact_id,
            "company": company,
            "metric": metric,
            "period": period,
            "period_type": period_type,
            "scope": scope,
            "attribution": attribution,
            "value": _text(_q(value)),
            "unit": unit,
            "currency": currency,
            "status": "calculated",
            "audit_status": audit_status,
            "source_file": "",
            "locator_type": "",
            "locator": "",
            "source_line_item": "",
            "formula": formula,
            "input_fact_ids": ";".join(input_ids),
            "notes": notes,
        }
        self.facts[fact_id] = fact
        self.order.append(fact_id)
        self.lookup[(company, period, scope, metric)][fact_id] = fact
        return fact


class EntityBuilder:
    def __init__(self, index: FactIndex, args: argparse.Namespace, company: str):
        self.index = index
        self.args = args
        self.company = company
        self.fy = args.fy if args.fy.startswith("FY") else f"FY{args.fy}"
        self.year = int(self.fy[2:])
        self.scope = "consolidated" if args.business_scope_status != "segment_scored" else args.segment_scope
        self.rows: dict[str, dict[str, str]] = {}

    def _meta(self) -> dict[str, str]:
        return {
            "company": self.company,
            "entity_id": self.args.entity_id or self.company,
            "subsector": self.args.subsector,
            "fy": self.fy,
            "peer_group": self.args.peer_group or f"{self.args.subsector}-cn-a",
            "comparability_status": self.args.comparability_status,
            "business_scope_status": self.args.business_scope_status,
            "semiconductor_revenue_share": str(self.args.semiconductor_revenue_share),
            "calibration_status": self.args.calibration_status,
            "source": "由caiwu-fenxi facts.csv生成",
        }

    def fact(self, alias: str, year: int | None = None, attribution: str | None = None) -> dict[str, str] | None:
        period = self.fy if year is None else f"FY{year}"
        names = ALIASES.get(alias, (alias,))
        return self.index.get(
            self.company, period, self.scope, names, attribution,
            allow_instant=alias in POINT_ALIASES,
        )

    def add(
        self,
        metric: str,
        *,
        status: str,
        fact: dict[str, str] | None = None,
        nm_reason: str = "",
        input_ids: Iterable[str] = (),
        notes: str = "",
        value: str = "",
    ) -> None:
        ids = [item for item in input_ids if item]
        unit = METRIC_UNITS[metric]
        if unit == "currency" and fact and fact.get("unit"):
            unit = fact["unit"]
        self.rows[metric] = {
            **self._meta(),
            "metric": metric,
            "value": value if status == "present" else (fact["value"] if fact and status in {"present", "checked_clear", "triggered"} else ""),
            "unit": unit,
            "status": status,
            "nm_reason": nm_reason,
            "fact_id": fact["fact_id"] if fact else "",
            "input_fact_ids": ";".join(ids),
            "notes": notes,
        }
        if status == "present" and fact:
            self.rows[metric]["value"] = fact["value"]
        if status in {"checked_clear", "triggered"} and fact:
            self.rows[metric]["value"] = fact["value"]

    def missing(self, metric: str, reason: str, notes: str = "") -> None:
        self.add(metric, status="missing", nm_reason=reason, notes=notes)

    def calc(
        self,
        metric: str,
        value: Decimal,
        unit: str,
        attribution: str,
        formula: str,
        inputs: list[dict[str, str]],
        notes: str = "",
        period_type: str = "fy",
    ) -> dict[str, str]:
        return self.index.add_calculated(
            company=self.company,
            metric=metric,
            period=self.fy,
            scope=self.scope,
            attribution=attribution,
            value=value,
            unit=unit,
            formula=formula,
            input_ids=[item["fact_id"] for item in inputs],
            notes=notes,
            period_type=period_type,
        )

    def yoy(self, metric: str, alias: str, attribution: str, formula_name: str) -> None:
        current = self.fact(alias, self.year, attribution if attribution != "na" else None)
        prior = self.fact(alias, self.year - 1, attribution if attribution != "na" else None)
        if not current or not prior:
            self.missing(metric, "insufficient_history" if not prior else "source_unavailable")
            return
        current_v = _decimal(current["value"])
        prior_v = _decimal(prior["value"])
        if current_v is None or prior_v is None:
            self.missing(metric, "source_unavailable")
            return
        if metric == "nps_growth":
            if current_v > ZERO and prior_v <= ZERO:
                self.add(metric, status="turnaround", input_ids=[current["fact_id"], prior["fact_id"]])
                return
            if current_v <= ZERO < prior_v:
                self.add(metric, status="turn_loss", input_ids=[current["fact_id"], prior["fact_id"]])
                return
        if prior_v <= ZERO:
            reason = "zero_denominator" if prior_v == ZERO else "negative_denominator"
            self.add(
                metric, status="not_meaningful", nm_reason=reason,
                input_ids=[current["fact_id"], prior["fact_id"]],
            )
            return
        fact = self.calc(
            metric, (current_v / prior_v - ONE) * HUNDRED, "percent", attribution,
            f"({current['fact_id']}/{prior['fact_id']}-1)*100", [current, prior],
        )
        self.add(metric, status="present", fact=fact, input_ids=[current["fact_id"], prior["fact_id"]])

    def cagr(self, metric: str, alias: str, attribution: str) -> None:
        years = [self.year, self.year - 1, self.year - 2, self.year - 3]
        facts = [self.fact(alias, year, attribution if attribution != "na" else None) for year in years]
        if any(item is None for item in facts):
            self.missing(metric, "insufficient_history", "缺少四个完整FY端点")
            return
        values = [_decimal(item["value"]) for item in facts]  # type: ignore[union-attr]
        ids = [item["fact_id"] for item in facts]  # type: ignore[union-attr]
        if any(value is None or value <= ZERO for value in values):
            reason = "turnaround_window" if any(value and value > ZERO for value in values) else "negative_denominator"
            self.add(metric, status="not_meaningful", nm_reason=reason, input_ids=ids)
            return
        growth = (values[0] / values[-1]) ** (D("1") / D("3")) - ONE
        fact = self.calc(
            metric, growth * HUNDRED, "percent", attribution,
            f"(({ids[0]}/{ids[3]})**(1/3)-1)*100 + 0*{ids[1]} + 0*{ids[2]}",
            facts,  # type: ignore[arg-type]
        )
        self.add(metric, status="present", fact=fact, input_ids=ids)

    def ratio(
        self,
        metric: str,
        numerator: dict[str, str] | None,
        denominator: dict[str, str] | None,
        unit: str,
        attribution: str,
        formula: str,
        scale: Decimal = ONE,
        notes: str = "",
    ) -> None:
        if not numerator or not denominator:
            self.missing(metric, "source_unavailable")
            return
        top = _decimal(numerator["value"])
        bottom = _decimal(denominator["value"])
        if top is None or bottom is None:
            self.missing(metric, "source_unavailable")
            return
        if bottom == ZERO:
            self.add(
                metric, status="not_meaningful", nm_reason="zero_denominator",
                input_ids=[numerator["fact_id"], denominator["fact_id"]],
            )
            return
        value = top / bottom * scale
        if metric in {CASH_3Y, CASH_FY, "recurring_parent_profit_ratio"} and abs(value) > D("20" if metric != "recurring_parent_profit_ratio" else "10"):
            self.add(
                metric, status="not_meaningful", nm_reason="near_zero_denominator",
                input_ids=[numerator["fact_id"], denominator["fact_id"]],
                notes="异常分母效应，不参与评分",
            )
            return
        if scale == HUNDRED:
            rendered = f"({numerator['fact_id']}/{denominator['fact_id']})*100"
        else:
            rendered = f"{numerator['fact_id']}/{denominator['fact_id']}"
        fact = self.calc(metric, value, unit, attribution, rendered, [numerator, denominator], notes)
        self.add(metric, status="present", fact=fact, input_ids=[numerator["fact_id"], denominator["fact_id"]])

    def passthrough(self, metric: str, alias: str | None = None, attribution: str | None = None) -> None:
        fact = self.fact(alias or metric, attribution=attribution)
        if not fact:
            self.missing(metric, "not_extracted" if metric in {
                "government_grant_pnl_ratio", "rd_capitalization_rate",
                "largest_billed_customer_revenue_ratio", "largest_supplier_purchase_ratio",
                "top5_billed_customer_revenue_ratio", "top5_supplier_purchase_ratio",
                "performance_commitment_flag", "debt_default", "impairment_to_pbt",
            } else "source_unavailable")
            return
        if metric in BOOLEAN_METRICS:
            value = _decimal(fact["value"])
            status = "checked_clear" if value == ZERO else "triggered"
            self.add(metric, status=status, fact=fact)
            return
        self.add(metric, status="present", fact=fact)

    def cash_conversion(self) -> None:
        years = [self.year, self.year - 1, self.year - 2]
        ocfs = [self.fact("operating_cash_flow", year) for year in years]
        profits = [self.fact("net_profit_parent", year, "parent") for year in years]
        if all(ocfs) and all(profits):
            ocf_sum = sum((_decimal(item["value"]) or ZERO) for item in ocfs)  # type: ignore[index]
            profit_sum = sum((_decimal(item["value"]) or ZERO) for item in profits)  # type: ignore[index]
            ocf_fact = self.calc(
                "operating_cash_flow_3y_sum", ocf_sum, ocfs[0]["unit"], "na",  # type: ignore[index]
                "+".join(item["fact_id"] for item in ocfs), ocfs,  # type: ignore[union-attr]
            )
            profit_fact = self.calc(
                "net_profit_parent_3y_sum", profit_sum, profits[0]["unit"], "parent",  # type: ignore[index]
                "+".join(item["fact_id"] for item in profits), profits,  # type: ignore[union-attr]
            )
            self.ratio(CASH_3Y, ocf_fact, profit_fact, "ratio", "parent", "")
            return
        self.missing(CASH_3Y, "insufficient_history", "三年历史不足，回退当前FY")
        self.ratio(
            CASH_FY,
            self.fact("operating_cash_flow"),
            self.fact("net_profit_parent", attribution="parent"),
            "ratio", "parent", "",
        )

    def fcf_margin(self) -> None:
        revenue = self.fact("revenue")
        fcf = self.fact("fcf_long_term")
        ocf = self.fact("operating_cash_flow")
        capex = self.fact("long_term_capex")
        if fcf and revenue:
            self.ratio(
                "fcf_long_term_assets_margin", fcf, revenue, "percent", "na",
                "", HUNDRED, "长期资产现金支出口径",
            )
            return
        if ocf and capex and revenue:
            ocf_v = _decimal(ocf["value"])
            capex_v = _decimal(capex["value"])
            rev_v = _decimal(revenue["value"])
            if None not in (ocf_v, capex_v, rev_v) and rev_v != ZERO:
                fact = self.calc(
                    "fcf_long_term_assets_margin",
                    (ocf_v - capex_v) / rev_v * HUNDRED,
                    "percent", "na",
                    f"({ocf['fact_id']}-{capex['fact_id']})/{revenue['fact_id']}*100",
                    [ocf, capex, revenue],
                    "长期资产现金支出口径，不是pure-PPE FCF",
                )
                self.add("fcf_long_term_assets_margin", status="present", fact=fact)
                return
        self.missing("fcf_long_term_assets_margin", "source_unavailable")

    def net_cash(self) -> None:
        cash = self.fact("cash")
        debt = self.fact("interest_bearing_debt")
        assets = self.fact("total_assets")
        if cash and debt and assets:
            cash_v = _decimal(cash["value"])
            debt_v = _decimal(debt["value"])
            assets_v = _decimal(assets["value"])
            if None not in (cash_v, debt_v, assets_v) and assets_v != ZERO:
                fact = self.calc(
                    "net_cash_to_assets", (cash_v - debt_v) / assets_v * HUNDRED,
                    "percent", "na",
                    f"({cash['fact_id']}-{debt['fact_id']})/{assets['fact_id']}*100",
                    [cash, debt, assets],
                    "现金等价物减有息负债，不含理财",
                )
                self.add("net_cash_to_assets", status="present", fact=fact)
                return
        self.missing("net_cash_to_assets", "source_unavailable")

    def inventory_change(self) -> None:
        current = self.fact("inventory_days", self.year)
        prior = self.fact("inventory_days", self.year - 1)
        if current and prior:
            current_v = _decimal(current["value"])
            prior_v = _decimal(prior["value"])
            if current_v is not None and prior_v is not None:
                fact = self.calc(
                    "inventory_days_change", current_v - prior_v, "days", "na",
                    f"{current['fact_id']}-{prior['fact_id']}", [current, prior],
                    period_type="fy",
                )
                self.add("inventory_days_change", status="present", fact=fact)
                return
        self.missing("inventory_days_change", "source_unavailable")

    def use_existing(self, metric: str) -> bool:
        fact = self.index.get(self.company, self.fy, self.scope, (metric,), allow_instant=True)
        if not fact:
            return False
        if metric in BOOLEAN_METRICS:
            value = _decimal(fact["value"])
            status = "checked_clear" if value == ZERO else "triggered"
            self.add(metric, status=status, fact=fact)
            return True
        self.add(metric, status="present", fact=fact)
        return True

    def build(self) -> list[dict[str, str]]:
        if not self.use_existing("rev_growth"):
            self.yoy("rev_growth", "revenue", "na", "rev")
        if not self.use_existing("rev_cagr_3y"):
            self.cagr("rev_cagr_3y", "revenue", "na")
        if not self.use_existing("nps_growth"):
            self.yoy("nps_growth", "nps_parent", "parent", "nps")
        if not self.use_existing("nps_cagr_3y"):
            self.cagr("nps_cagr_3y", "nps_parent", "parent")
        if not self.use_existing("gross_margin_total"):
            revenue = self.fact("revenue")
            cost = self.fact("operating_cost")
            if revenue and cost:
                rev_v = _decimal(revenue["value"])
                cost_v = _decimal(cost["value"])
                if rev_v and rev_v != ZERO and cost_v is not None:
                    fact = self.calc(
                        "gross_margin_total", (rev_v - cost_v) / rev_v * HUNDRED,
                        "percent", "na",
                        f"({revenue['fact_id']}-{cost['fact_id']})/{revenue['fact_id']}*100",
                        [revenue, cost],
                    )
                    self.add("gross_margin_total", status="present", fact=fact)
                else:
                    self.missing("gross_margin_total", "source_unavailable")
            else:
                self.missing("gross_margin_total", "source_unavailable")
        if not self.use_existing("net_margin_parent"):
            self.ratio(
                "net_margin_parent",
                self.fact("net_profit_parent", attribution="parent"),
                self.fact("revenue"),
                "percent", "parent", "", HUNDRED,
            )
        self.passthrough("roe_weighted_parent", attribution="parent")
        if self.use_existing(CASH_3Y):
            pass
        elif self.use_existing(CASH_FY):
            if CASH_3Y not in self.rows:
                self.missing(CASH_3Y, "insufficient_history", "三年历史不足，回退当前FY")
        else:
            self.cash_conversion()
        if not self.use_existing("fcf_long_term_assets_margin"):
            self.fcf_margin()
        if not self.use_existing("cash_receipts_to_revenue"):
            self.ratio(
                "cash_receipts_to_revenue",
                self.fact("cash_receipts"),
                self.fact("revenue"),
                "ratio", "na", "",
            )
        if not self.use_existing("debt_to_assets"):
            self.ratio(
                "debt_to_assets",
                self.fact("total_liabilities"),
                self.fact("total_assets"),
                "percent", "na", "", HUNDRED,
            )
        if not self.use_existing("current_ratio"):
            self.ratio(
                "current_ratio",
                self.fact("current_assets"),
                self.fact("current_liabilities"),
                "ratio", "na", "",
            )
        if not self.use_existing("net_cash_to_assets"):
            self.net_cash()
        if not self.use_existing("recurring_parent_profit_ratio"):
            self.ratio(
                "recurring_parent_profit_ratio",
                self.fact("nps_parent", attribution="parent"),
                self.fact("net_profit_parent", attribution="parent"),
                "ratio", "parent", "",
            )
        if not self.use_existing("government_grant_pnl_ratio"):
            grant = self.fact("government_grant_pnl")
            pbt = self.fact("profit_before_tax")
            if grant and pbt:
                self.ratio(
                    "government_grant_pnl_ratio", grant, pbt, "percent", "na",
                    "", HUNDRED, "仅含已对账且互斥的当期损益影响",
                )
            else:
                self.missing("government_grant_pnl_ratio", "not_extracted", "缺少已对账政府补助当期损益")
        if not self.use_existing("rd_capitalization_rate"):
            capitalized = self.fact("rd_capitalized")
            total = self.fact("rd_total_investment")
            if capitalized and total:
                self.ratio(
                    "rd_capitalization_rate", capitalized, total, "percent", "na", "", HUNDRED,
                )
            else:
                self.missing("rd_capitalization_rate", "not_extracted", "缺少当期资本化研发投入")
        if not self.use_existing("rd_expense_intensity"):
            self.ratio(
                "rd_expense_intensity",
                self.fact("rd_expense"),
                self.fact("revenue"),
                "percent", "na", "", HUNDRED,
            )
        if not self.use_existing("goodwill_to_parent_equity"):
            self.ratio(
                "goodwill_to_parent_equity",
                self.fact("goodwill"),
                self.fact("equity_parent", attribution="parent"),
                "percent", "parent", "", HUNDRED,
            )
        for metric in (
            "largest_billed_customer_revenue_ratio",
            "largest_supplier_purchase_ratio",
            "top5_billed_customer_revenue_ratio",
            "top5_supplier_purchase_ratio",
            "performance_commitment_flag",
            "audit_issue",
            "debt_default",
        ):
            self.passthrough(metric)
        if not self.use_existing("operating_cash_flow"):
            ocf = self.fact("operating_cash_flow")
            if ocf:
                self.add("operating_cash_flow", status="present", fact=ocf)
            else:
                self.missing("operating_cash_flow", "source_unavailable")
        if not self.use_existing("inventory_days_change"):
            self.inventory_change()
        if not self.use_existing("impairment_to_pbt"):
            impairment = self.fact("impairment")
            pbt = self.fact("profit_before_tax")
            if impairment and pbt:
                self.ratio(
                    "impairment_to_pbt", impairment, pbt, "percent", "na", "", HUNDRED,
                )
            else:
                self.missing("impairment_to_pbt", "not_extracted")
        if not self.use_existing("da_to_revenue"):
            self.ratio(
                "da_to_revenue",
                self.fact("depreciation_amortization"),
                self.fact("revenue"),
                "percent", "na", "", HUNDRED,
            )
        missing = [metric for metric in ALL_REQUIRED if metric not in self.rows]
        if CASH_FY not in self.rows and self.rows.get(CASH_3Y, {}).get("status") != "missing":
            missing = [item for item in missing if item != CASH_FY]
        if missing:
            raise ValueError(f"{self.company}: 未生成全部评分槽位: {','.join(missing)}")
        ordered = []
        for metric in ALL_REQUIRED:
            if metric in self.rows:
                ordered.append(self.rows[metric])
        if CASH_FY in self.rows:
            insert_at = next(i for i, row in enumerate(ordered) if row["metric"] == CASH_3Y) + 1
            ordered.insert(insert_at, self.rows[CASH_FY])
        return ordered


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def companies_in(facts: dict[str, dict[str, str]]) -> list[str]:
    return sorted({fact["company"] for fact in facts.values() if fact.get("company")})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--company")
    parser.add_argument("--entity-id")
    parser.add_argument("--subsector", required=True, choices=sorted(SUBSECTORS))
    parser.add_argument("--fy", required=True, help="FY2025 或 2025")
    parser.add_argument("--peer-group")
    parser.add_argument(
        "--comparability-status",
        choices=("comparable", "limited", "not_comparable", "unknown"),
        default="unknown",
    )
    parser.add_argument(
        "--business-scope-status",
        choices=("pure_play", "segment_scored", "diversified_unallocated", "unknown"),
        default="unknown",
    )
    parser.add_argument("--semiconductor-revenue-share", default="0")
    parser.add_argument(
        "--calibration-status",
        choices=("calibrated", "uncalibrated"),
        default="uncalibrated",
    )
    parser.add_argument("--segment-scope", default="consolidated")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--skip-source-check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    share = _decimal(str(args.semiconductor_revenue_share))
    if share is None or not ZERO <= share <= HUNDRED:
        raise SystemExit("--semiconductor-revenue-share必须在0到100之间")
    args.semiconductor_revenue_share = _text(share)
    if args.business_scope_status == "pure_play" and share < D("70"):
        raise SystemExit("pure_play要求半导体主营收入占比至少70%")
    if args.business_scope_status == "segment_scored" and not str(args.segment_scope).startswith("segment:"):
        raise SystemExit("--segment-scope必须形如 segment:<reported name>")
    run_fact_validator(args.facts, args.source_root, args.skip_source_check, "caiwu")
    facts = load_facts(args.facts)
    names = [args.company] if args.company else companies_in(facts)
    if not names:
        raise SystemExit("facts.csv没有公司")
    if args.company is None and len(names) != 1 and not args.entity_id:
        pass
    index = FactIndex(facts)
    all_rows: list[dict[str, str]] = []
    for company in names:
        builder = EntityBuilder(index, args, company)
        if args.entity_id and len(names) > 1:
            builder.args.entity_id = f"{args.entity_id}-{company}"
        all_rows.extend(builder.build())
    facts_out = args.out_dir / "facts.scored.csv"
    score_out = args.out_dir / "score-input.csv"
    write_csv(facts_out, FACT_FIELDS, [index.facts[item] for item in index.order])
    write_csv(score_out, SCORE_FIELDS, all_rows)
    manifest = {
        "schema_version": "1.0",
        "source_facts": str(args.facts.resolve()),
        "companies": names,
        "fy": args.fy if str(args.fy).startswith("FY") else f"FY{args.fy}",
        "subsector": args.subsector,
        "peer_group": args.peer_group or f"{args.subsector}-cn-a",
        "outputs": {
            "facts": facts_out.name,
            "score_input": score_out.name,
        },
        "route": "caiwu-fenxi-facts-to-jibenmian-pingfen",
    }
    (args.out_dir / "prepare_score_input.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"score_input={score_out}")
    print(f"facts={facts_out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
