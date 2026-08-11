from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import pandas as pd


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("caiwu_validate_analysis", SKILL_DIR / "scripts" / "validate_analysis.py")
charts = load_module("caiwu_financial_charts", SKILL_DIR / "scripts" / "financial_charts.py")


class FactValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example = SKILL_DIR / "assets" / "example-facts.csv"

    def validate(self, path: Path):
        return validator.validate_facts(
            path,
            path.parent,
            True,
            Decimal("0.02"),
            Decimal("0.001"),
        )

    def test_example_ledger_passes(self) -> None:
        self.assertEqual(self.validate(self.example), [])

    def test_tolerances_must_be_finite_and_nonnegative(self) -> None:
        self.assertEqual(
            validator.parse_tolerances("0.02", "0.001"),
            (Decimal("0.02"), Decimal("0.001")),
        )
        for absolute, relative in (("NaN", "0"), ("0", "Infinity"), ("-1", "0")):
            with self.subTest(absolute=absolute, relative=relative):
                with self.assertRaises(ValueError):
                    validator.parse_tolerances(absolute, relative)

    def test_formula_tokens_do_not_replace_function_names(self) -> None:
        self.assertEqual(
            validator.safe_formula_value("abs(a)", {"a": Decimal("-10")}),
            Decimal("10.0"),
        )

    def test_malformed_extra_csv_field_is_reported(self) -> None:
        header = ",".join(validator.REQUIRED_FACT_COLUMNS)
        row = ",".join(
            [
                "f1",
                "Example",
                "revenue",
                "FY2025",
                "fy",
                "consolidated",
                "na",
                "100",
                "million",
                "CNY",
                "reported",
                "audited",
                "report.pdf",
                "pdf_page",
                "1",
                "营业收入",
                "",
                "",
                "",
                "EXTRA",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.csv"
            path.write_text(f"{header}\n{row}\n", encoding="utf-8")
            codes = {issue.code for issue in self.validate(path)}
        self.assertIn("MALFORMED_CSV_ROW", codes)

    def test_calculation_cannot_use_unavailable_fact(self) -> None:
        fields = validator.REQUIRED_FACT_COLUMNS
        template = {name: "" for name in fields}
        common = {
            "company": "Example",
            "period": "FY2025",
            "period_type": "fy",
            "scope": "consolidated",
            "attribution": "na",
            "unit": "units",
            "currency": "N/A",
            "audit_status": "unknown",
        }
        rows = [
            template | common | {
                "fact_id": "f_missing",
                "metric": "capacity",
                "status": "unavailable",
                "notes": "not disclosed",
            },
            template | common | {
                "fact_id": "f_zero",
                "metric": "derived_capacity",
                "value": "0",
                "status": "calculated",
                "formula": "f_missing*1",
                "input_fact_ids": "f_missing",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            codes = {issue.code for issue in self.validate(path)}
        self.assertIn("CALCULATION_USES_UNAVAILABLE", codes)

    def test_reconciliation_failure_is_detected(self) -> None:
        with self.example.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0])
        for row in rows:
            if row["fact_id"] == "f_gp":
                row["value"] = "450"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            codes = {issue.code for issue in self.validate(path)}
        self.assertIn("RECONCILIATION_FAILED", codes)
        self.assertIn("FORMULA_RESULT_MISMATCH", codes)

    def test_nonpositive_yoy_denominator_is_rejected(self) -> None:
        with self.example.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0])
        template = {name: "" for name in fieldnames}
        common = {
            "company": "示例公司",
            "period_type": "fy",
            "scope": "consolidated",
            "attribution": "na",
            "unit": "million",
            "currency": "CNY",
            "audit_status": "audited",
        }
        rows.extend(
            (
                template | common | {
                    "fact_id": "f_current",
                    "metric": "revenue",
                    "period": "FY2025",
                    "value": "10",
                    "status": "reported",
                    "source_file": "report.pdf",
                    "locator_type": "pdf_page",
                    "locator": "1",
                    "source_line_item": "营业收入",
                },
                template | common | {
                    "fact_id": "f_prior",
                    "metric": "revenue",
                    "period": "FY2024",
                    "value": "-5",
                    "status": "reported",
                    "source_file": "report.pdf",
                    "locator_type": "pdf_page",
                    "locator": "1",
                    "source_line_item": "营业收入",
                },
                template | common | {
                    "fact_id": "f_yoy",
                    "metric": "revenue_yoy",
                    "period": "FY2025",
                    "value": "-300",
                    "unit": "percent",
                    "currency": "N/A",
                    "status": "calculated",
                    "formula": "((f_current/f_prior)-1)*100",
                    "input_fact_ids": "f_current;f_prior",
                },
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            codes = {issue.code for issue in self.validate(path)}
        self.assertIn("YOY_DENOMINATOR_NOT_MEANINGFUL", codes)

    def test_overlapping_grant_views_are_rejected(self) -> None:
        with self.example.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0])
        template = {name: "" for name in fieldnames}
        common = {
            "company": "示例公司",
            "period": "FY2025",
            "period_type": "fy",
            "scope": "consolidated",
            "attribution": "na",
            "unit": "million",
            "currency": "CNY",
            "audit_status": "audited",
        }
        grant_other = template | common | {
            "fact_id": "f_grant_other",
            "metric": "government_grant_other_income",
            "value": "10",
            "status": "reported",
            "source_file": "report.pdf",
            "locator_type": "pdf_page",
            "locator": "20",
            "source_line_item": "计入其他收益的政府补助",
        }
        grant_nonrecurring = template | common | {
            "fact_id": "f_grant_nonrec",
            "metric": "government_grant_nonrecurring",
            "value": "10",
            "status": "reported",
            "source_file": "report.pdf",
            "locator_type": "pdf_page",
            "locator": "21",
            "source_line_item": "计入非经常性损益的政府补助",
        }
        grant_sum = template | common | {
            "fact_id": "f_grant_sum",
            "metric": "government_grant_total",
            "value": "20",
            "status": "calculated",
            "formula": "f_grant_other+f_grant_nonrec",
            "input_fact_ids": "f_grant_other;f_grant_nonrec",
        }
        rows.extend((grant_other, grant_nonrecurring, grant_sum))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            codes = {issue.code for issue in self.validate(path)}
        self.assertIn("OVERLAPPING_GRANT_VIEWS", codes)

    def test_pdf_page_range_and_source_label_are_checked(self) -> None:
        try:
            import fitz
        except ModuleNotFoundError:
            self.skipTest("PyMuPDF unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Revenue 100")
            document.save(pdf)
            document.close()
            row = {
                name: ""
                for name in validator.REQUIRED_FACT_COLUMNS
            } | {
                "fact_id": "f1",
                "company": "Example",
                "metric": "revenue",
                "period": "FY2025",
                "period_type": "fy",
                "scope": "consolidated",
                "attribution": "na",
                "value": "100",
                "unit": "million",
                "currency": "CNY",
                "status": "reported",
                "audit_status": "audited",
                "source_file": "report.pdf",
                "locator_type": "pdf_page",
                "locator": "2",
                "source_line_item": "Wrong label",
            }
            wrong_label_row = row | {
                "fact_id": "f2",
                "locator": "1",
            }
            ledger = root / "facts.csv"
            with ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=validator.REQUIRED_FACT_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
                writer.writerow(wrong_label_row)
            codes = {issue.code for issue in validator.validate_facts(
                ledger, root, False, Decimal("0.02"), Decimal("0.001")
            )}
        self.assertIn("PDF_PAGE_OUT_OF_RANGE", codes)
        self.assertIn("SOURCE_LABEL_NOT_ON_PAGE", codes)

    def test_text_line_source_label_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.txt").write_text("Revenue 2024 80\n", encoding="utf-8")
            row = {name: "" for name in validator.REQUIRED_FACT_COLUMNS} | {
                "fact_id": "f1",
                "company": "Example",
                "metric": "revenue",
                "period": "FY2025",
                "period_type": "fy",
                "scope": "consolidated",
                "attribution": "na",
                "value": "999",
                "unit": "million",
                "currency": "CNY",
                "status": "reported",
                "audit_status": "audited",
                "source_file": "source.txt",
                "locator_type": "text_line",
                "locator": "1",
                "source_line_item": "Completely Wrong Label",
            }
            ledger = root / "facts.csv"
            with ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=validator.REQUIRED_FACT_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            codes = {
                issue.code
                for issue in validator.validate_facts(
                    ledger, root, False, Decimal("0.02"), Decimal("0.001")
                )
            }
        self.assertIn("SOURCE_LABEL_NOT_ON_LINE", codes)


class ReportLintTests(unittest.TestCase):
    def test_example_report_passes(self) -> None:
        with (SKILL_DIR / "assets" / "example-facts.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            fact_ids = {row["fact_id"] for row in csv.DictReader(handle)}
        issues = validator.lint_report(
            SKILL_DIR / "assets" / "example-report.md", True, fact_ids
        )
        self.assertEqual(issues, [])

    def test_unknown_fact_and_claim_class_change_are_detected(self) -> None:
        report = """# 示例报告

## 来源范围
来源：S1 p.10

2026Q1 收入 10，利润 2。[F:missing] [C:growth|inference]
同一增长结论。[C:growth|source-stated]
季度 EPS 简单年化为 1.0。
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text(report, encoding="utf-8")
            codes = {issue.code for issue in validator.lint_report(path, False, {"known"})}
        self.assertIn("UNKNOWN_FACT_REFERENCE", codes)
        self.assertIn("CLAIM_CLASS_CHANGED", codes)
        self.assertIn("ANNUALIZATION_REVIEW", codes)

    def test_html_comments_and_code_fences_do_not_count_as_evidence(self) -> None:
        report = """# 来源 业务 产品 技术 财务 盈利 现金流 资产负债 附注 基本面 预期 风险 附录 证据

Revenue was 999 versus 888. <!-- [F:f_rev] -->

<!-- source.txt p.999 -->

```text
[F:f_rev]
source.txt p.1
```
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text(report, encoding="utf-8")
            codes = {
                issue.code
                for issue in validator.lint_report(path, False, {"f_rev"})
            }
        self.assertIn("NO_SOURCE_CITATIONS", codes)
        self.assertIn("NO_FACT_REFERENCES", codes)
        self.assertIn("NUMERIC_PARAGRAPH_UNSOURCED", codes)

    def test_false_direction_and_monotonic_claim_are_detected(self) -> None:
        report = """# 报告

## 来源
来源：S1 p.1

| 指标 | Q1 | Q2 | Q3 |
|---|---:|---:|---:|
| 营业收入 | 100 | 90 | 120 |

收入逐季上升；应收增长 31.78%，低于收入增长 30.85%。
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text(report, encoding="utf-8")
            codes = {issue.code for issue in validator.lint_report(path, False)}
        self.assertIn("COMPARISON_DIRECTION_ERROR", codes)
        self.assertIn("MONOTONIC_CLAIM_CONTRADICTED", codes)

    def test_organic_and_price_volume_language_are_flagged(self) -> None:
        report = """# 报告

## 来源
来源：S1 p.1

剔除三月才并表的标的完整一季度收入后，有机增速约 5%。
产品实现量价齐升。
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text(report, encoding="utf-8")
            codes = {issue.code for issue in validator.lint_report(path, False)}
        self.assertIn("ORGANIC_GROWTH_REVIEW", codes)
        self.assertIn("PRICE_VOLUME_REVIEW", codes)


class ChartValidationTests(unittest.TestCase):
    @staticmethod
    def fact(
        fact_id: str,
        metric: str,
        period: str,
        value: str,
        unit: str = "million",
        currency: str = "CNY",
    ) -> dict[str, str]:
        return {
            "fact_id": fact_id,
            "metric": metric,
            "period": period,
            "value": value,
            "unit": unit,
            "currency": currency,
            "status": "reported",
            "source_file": "report.pdf",
            "locator_type": "pdf_page",
            "locator": "1",
            "input_fact_ids": "",
            "notes": "",
        }

    def test_axis_label_includes_currency(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "axis_norm": "primary",
                    "unit": "million",
                    "currency": "CNY",
                }
            ]
        )
        self.assertEqual(charts._axis_label(frame, "primary"), "million (CNY)")

    def test_nonnegative_axis_is_anchored_at_zero(self) -> None:
        figure, axis = charts.plt.subplots()
        try:
            axis.plot([0, 1], [270, 320])
            charts._anchor_axis_at_zero(axis, pd.Series([270, 320]))
            self.assertEqual(axis.get_ylim()[0], 0)
        finally:
            charts.plt.close(figure)

    def test_example_fact_linked_chart_passes_strict_validation(self) -> None:
        facts, fact_issues = charts._load_facts(SKILL_DIR / "assets" / "example-facts.csv")
        frame, read_issues = charts._load_chart_csv(SKILL_DIR / "assets" / "example-chart-spec.csv")
        self.assertFalse(fact_issues or read_issues)
        assert frame is not None
        data, hydrate_issues = charts._hydrate_from_facts(frame, facts, True)
        _, validation_issues = charts._normalize_and_validate(data, True)
        errors = [issue for issue in hydrate_issues + validation_issues if issue.severity == "ERROR"]
        self.assertEqual(errors, [])

    def test_metric_label_and_large_value_mismatches_are_rejected(self) -> None:
        facts = {
            "f_big": self.fact(
                "f_big",
                "revenue",
                "FY2025",
                "9007199254740993",
                unit="units",
                currency="N/A",
            )
        }
        frame = pd.DataFrame(
            [
                {
                    "chart_id": "c",
                    "title": "T",
                    "fact_id": "f_big",
                    "metric": "Net profit",
                    "value": "9007199254740992",
                    "render": "bar",
                    "axis": "primary",
                    "period_order": "1",
                    "missing_policy": "gap",
                }
            ]
        )
        _, issues = charts._hydrate_from_facts(frame, facts, True)
        codes = {issue.code for issue in issues}
        self.assertIn("FACT_METRIC_MISMATCH", codes)
        self.assertIn("FACT_VALUE_MISMATCH", codes)

    def test_partial_stacked_series_is_rejected(self) -> None:
        facts = {
            "a24": self.fact("a24", "segment_revenue:A", "FY2024", "60"),
            "b24": self.fact("b24", "segment_revenue:B", "FY2024", "20"),
            "a25": self.fact("a25", "segment_revenue:A", "FY2025", "100"),
        }
        frame = pd.DataFrame(
            [
                {
                    "chart_id": "segments",
                    "title": "Segments",
                    "fact_id": fact_id,
                    "display_label": label,
                    "render": "stacked_bar",
                    "axis": "primary",
                    "period_order": order,
                    "missing_policy": "gap",
                }
                for fact_id, label, order in (
                    ("a24", "Segment A", "1"),
                    ("b24", "Segment B", "1"),
                    ("a25", "Segment A", "2"),
                )
            ]
        )
        hydrated, hydrate_issues = charts._hydrate_from_facts(frame, facts, True)
        _, validation_issues = charts._normalize_and_validate(hydrated, True)
        self.assertEqual(hydrate_issues, [])
        self.assertIn(
            "STACKED_SERIES_INCOMPLETE",
            {issue.code for issue in validation_issues},
        )

    def test_validate_only_rules_cover_period_order_and_legacy_schema(self) -> None:
        facts = {
            "r24": self.fact("r24", "revenue", "FY2024", "80"),
            "r25": self.fact("r25", "revenue", "FY2025", "100"),
        }
        bad_order = pd.DataFrame(
            [
                {
                    "chart_id": "trend",
                    "title": "Revenue",
                    "fact_id": "r24",
                    "display_label": "Revenue",
                    "render": "bar",
                    "axis": "primary",
                    "period_order": "",
                    "missing_policy": "gap",
                },
                {
                    "chart_id": "trend",
                    "title": "Revenue",
                    "fact_id": "r25",
                    "display_label": "Revenue",
                    "render": "bar",
                    "axis": "primary",
                    "period_order": "2",
                    "missing_policy": "gap",
                },
            ]
        )
        hydrated, _ = charts._hydrate_from_facts(bad_order, facts, True)
        _, issues = charts._normalize_and_validate(hydrated, True)
        self.assertIn("INVALID_PERIOD_ORDER", {issue.code for issue in issues})

        legacy = pd.DataFrame(
            [
                {
                    "chart_id": "legacy",
                    "title": "Revenue",
                    "fact_id": "r25",
                    "kind": "bar",
                    "metric": "revenue",
                    "period": "FY2025",
                    "value": "100",
                    "unit": "million",
                    "source": "report.pdf p.1",
                }
            ]
        )
        hydrated, _ = charts._hydrate_from_facts(legacy, facts, True)
        _, issues = charts._normalize_and_validate(hydrated, True)
        codes = {issue.code for issue in issues}
        self.assertIn("STRICT_REQUIRES_RENDER", codes)
        self.assertIn("STRICT_REQUIRES_AXIS", codes)
        self.assertIn("STRICT_REJECTS_LEGACY_KIND", codes)

    def test_malformed_fact_row_is_reported_without_crashing(self) -> None:
        required = [
            "fact_id",
            "metric",
            "period",
            "value",
            "unit",
            "currency",
            "status",
            "source_file",
            "locator_type",
            "locator",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.csv"
            path.write_text(
                ",".join(required)
                + "\nf1,revenue,FY2025,100,million,CNY,reported,report.pdf,pdf_page,1,EXTRA\n",
                encoding="utf-8",
            )
            _, issues = charts._load_facts(path)
        self.assertIn("MALFORMED_FACTS_ROW", {issue.code for issue in issues})

    def test_malformed_chart_row_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chart.csv"
            path.write_text(
                "chart_id,title,fact_id,display_label,render,axis,period_order,missing_policy\n"
                "c,T,f1,Revenue,bar,primary,1,gap,EXTRA\n",
                encoding="utf-8",
            )
            frame, issues = charts._load_chart_csv(path)
        self.assertIsNone(frame)
        self.assertIn("CHART_MALFORMED_ROW", {issue.code for issue in issues})

    def test_legacy_row_level_bar_and_line_are_honored(self) -> None:
        frame = pd.DataFrame(
            [
                {"chart_id": "c", "title": "T", "kind": "bar", "period": "2025", "metric": "Revenue", "value": "10", "unit": "CNYm", "source": "S1 p.1"},
                {"chart_id": "c", "title": "T", "kind": "line", "period": "2025", "metric": "Profit", "value": "2", "unit": "CNYm", "source": "S1 p.1"},
            ]
        )
        data, _ = charts._hydrate_from_facts(frame, None, False)
        normalized, issues = charts._normalize_and_validate(data, False)
        errors = [issue for issue in issues if issue.severity == "ERROR"]
        self.assertEqual(errors, [])
        self.assertEqual(normalized["render_norm"].tolist(), ["bar", "line"])

    def test_ambiguous_bar_line_is_rejected(self) -> None:
        frame = pd.DataFrame(
            [
                {"chart_id": "c", "title": "T", "kind": "bar_line", "period": "2025", "metric": "Revenue", "value": "10", "unit": "CNYm", "source": "S1 p.1"},
            ]
        )
        data, _ = charts._hydrate_from_facts(frame, None, False)
        _, issues = charts._normalize_and_validate(data, False)
        self.assertIn("AMBIGUOUS_BAR_LINE", {issue.code for issue in issues})

    def test_unavailable_fact_cannot_be_encoded_as_zero(self) -> None:
        facts = {
            "missing": {
                "fact_id": "missing",
                "metric": "capacity",
                "period": "FY2025",
                "value": "",
                "unit": "units",
                "currency": "N/A",
                "status": "unavailable",
                "source_file": "report.pdf",
                "locator_type": "section",
                "locator": "capacity",
                "input_fact_ids": "",
            }
        }
        frame = pd.DataFrame(
            [
                {
                    "chart_id": "c",
                    "title": "T",
                    "fact_id": "missing",
                    "display_label": "Capacity",
                    "render": "line",
                    "axis": "primary",
                    "value": "0",
                    "missing_policy": "gap",
                }
            ]
        )
        _, issues = charts._hydrate_from_facts(frame, facts, True)
        self.assertIn("UNAVAILABLE_ENCODED_AS_VALUE", {issue.code for issue in issues})

    def test_unavailable_fact_without_locator_keeps_reason_as_source(self) -> None:
        facts = {
            "missing": {
                "fact_id": "missing",
                "metric": "capacity",
                "period": "FY2025",
                "value": "",
                "unit": "units",
                "currency": "N/A",
                "status": "unavailable",
                "source_file": "",
                "locator_type": "",
                "locator": "",
                "input_fact_ids": "",
                "notes": "the filing does not quantify capacity",
            }
        }
        frame = pd.DataFrame(
            [
                {
                    "chart_id": "c",
                    "title": "T",
                    "fact_id": "missing",
                    "display_label": "Capacity",
                    "render": "line",
                    "axis": "primary",
                    "missing_policy": "gap",
                }
            ]
        )
        hydrated, issues = charts._hydrate_from_facts(frame, facts, True)
        self.assertEqual(issues, [])
        self.assertEqual(
            hydrated.iloc[0]["source"],
            "unavailable in filing: the filing does not quantify capacity",
        )


if __name__ == "__main__":
    unittest.main()
