#!/usr/bin/env python3
"""Regression and adversarial tests for the v2 scoring engine."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jibenmian_pingfen_score", SKILL_ROOT / "scripts" / "score.py"
)
assert SPEC and SPEC.loader
score = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = score
SPEC.loader.exec_module(score)


class ScoreTests(unittest.TestCase):
    maxDiff = None

    @property
    def example_input(self) -> Path:
        return SKILL_ROOT / "assets" / "example-input.csv"

    @property
    def example_facts(self) -> Path:
        return SKILL_ROOT / "assets" / "example-facts.csv"

    def args(self, input_path: Path, mode: str, out_dir: Path | None = None, facts: Path | None = None, source_root: Path | None = None):
        return argparse.Namespace(
            csv=input_path,
            mode=mode,
            facts=facts,
            source_root=source_root if source_root is not None else (SKILL_ROOT / "assets" if facts else None),
            evidence_validator="caiwu",
            skip_source_check=False,
            out=None,
            out_dir=out_dir,
            quiet=True,
        )

    def write_rows(self, directory: Path, fields: list[str], rows: list[dict[str, str]], name: str = "input.csv") -> Path:
        path = directory / name
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def mutate_example(self, directory: Path, mutator) -> Path:
        with self.example_input.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        rows = mutator(rows)
        return self.write_rows(directory, fields, rows)

    def test_strict_example_is_formal_a_and_writes_reproducible_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            results, warnings = score.run(
                self.args(self.example_input, "strict", out_dir, self.example_facts)
            )
            self.assertEqual(warnings, [])
            self.assertEqual(len(results), 1)
            result = results[0]
            self.assertEqual(result["raw_total"], Decimal("4.40"))
            self.assertEqual(result["total"], Decimal("4.40"))
            self.assertEqual(result["raw_coverage"], Decimal("88.2"))
            self.assertEqual(result["scored_evidence_coverage"], Decimal("100.0"))
            self.assertEqual(result["structural_coverage"], Decimal("100.0"))
            self.assertEqual(result["rating_state"], "FORMAL")
            self.assertEqual(result["rating"], "A")
            for name in (
                "score_summary.csv", "score_detail.csv", "ranking.csv",
                "score_manifest.json", "score_inputs.snapshot.csv", "facts.snapshot.csv",
            ):
                self.assertTrue((out_dir / name).exists(), name)
            manifest = json.loads((out_dir / "score_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["rules_version"], "2.2.0")
            self.assertEqual(manifest["rating_state_counts"], {"FORMAL": 1})
            self.assertEqual(manifest["warning_count"], 0)

    def test_compat_mode_keeps_score_but_never_publishes_grade(self):
        results, _ = score.run(self.args(self.example_input, "compat"))
        result = results[0]
        self.assertEqual(result["total"], Decimal("4.40"))
        self.assertEqual(result["diagnostic_grade"], "A")
        self.assertEqual(result["rating_state"], "LEGACY_DIAGNOSTIC")
        self.assertEqual(result["rating"], "N/R")
        self.assertFalse(result["formal"])
        self.assertFalse(result["ranking_eligible"])

    def test_nonfinite_values_are_rejected_in_all_modes(self):
        fields = ["company", "subsector", "metric", "value", "status"]
        for raw in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                path = self.write_rows(
                    Path(tmp), fields,
                    [{"company": "X", "subsector": "equipment", "metric": "rev_growth", "value": raw, "status": "present"}],
                )
                with self.assertRaisesRegex(ValueError, "有限数"):
                    score.parse_input(path, "compat")

    def test_duplicate_is_rejected_before_status_branches(self):
        fields = ["company", "subsector", "metric", "value", "status"]
        rows = [
            {"company": "X", "subsector": "equipment", "metric": "gross_margin", "value": "", "status": "not_applicable"},
            {"company": "X", "subsector": "equipment", "metric": "gross_margin", "value": "50", "status": "present"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_rows(Path(tmp), fields, rows)
            with self.assertRaisesRegex(ValueError, "所有status均参与唯一性"):
                score.parse_input(path, "compat")

    def test_status_value_contradiction_is_rejected_in_strict_mode(self):
        def mutate(rows):
            rows[0]["status"] = "missing"
            rows[0]["nm_reason"] = "not_disclosed"
            return rows

        with tempfile.TemporaryDirectory() as tmp:
            path = self.mutate_example(Path(tmp), mutate)
            with self.assertRaisesRegex(ValueError, "value必须为空"):
                score.parse_input(path, "strict")

    def test_strict_mode_requires_every_core_slot_and_missing_reason(self):
        def remove_slot(rows):
            return [row for row in rows if row["metric"] != "rev_cagr_3y"]

        def blank_reason(rows):
            for row in rows:
                if row["metric"] == "rev_cagr_3y":
                    row["nm_reason"] = ""
            return rows

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            missing_path = self.mutate_example(directory, remove_slot)
            with self.assertRaisesRegex(ValueError, "显式列出全部核心槽位"):
                score.parse_input(missing_path, "strict")
            reason_path = self.mutate_example(directory, blank_reason)
            with self.assertRaisesRegex(ValueError, "missing需要受控nm_reason"):
                score.parse_input(reason_path, "strict")

    def test_ratio_scale_error_is_not_auto_corrected(self):
        def mutate(rows):
            for row in rows:
                if row["metric"] == "cash_receipts_to_revenue":
                    row["value"] = "72.6"
            return rows

        with tempfile.TemporaryDirectory() as tmp:
            path = self.mutate_example(Path(tmp), mutate)
            with self.assertRaisesRegex(ValueError, "放大100倍"):
                score.parse_input(path, "strict")

    def test_goodwill_ratio_above_100_is_valid_and_triggers(self):
        fields = ["company", "subsector", "metric", "value", "status"]
        rows = [{"company": "X", "subsector": "equipment", "metric": "goodwill_ratio", "value": "150", "status": "present"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_rows(Path(tmp), fields, rows)
            entities, _ = score.parse_input(path, "compat")
            result = score.evaluate_entity(entities[0], "compat")
            self.assertEqual(result["nominal_deduction"], Decimal("0.20"))
            self.assertTrue(any(label.startswith("商誉/归母净资产>30%") for label in result["deduction_labels"]))

    def test_nm_cannot_inflate_raw_or_applicable_coverage_without_evidence(self):
        fields = ["company", "subsector", "metric", "value", "status"]
        scored = {
            "rev_growth": "40", "nps_growth": "20", "gross_margin_total": "40",
            "fcf_long_term_assets_margin": "5", "debt_to_assets": "30",
            "recurring_parent_profit_ratio": "0.8", "rd_expense_intensity": "10",
        }
        input_metrics = [metric for metric in score.CORE_SLOTS if metric != score.CASH_SLOT] + [score.CASH_3Y]
        rows = []
        for metric in input_metrics:
            if metric in scored:
                rows.append({"company": "Sparse", "subsector": "equipment", "metric": metric, "value": scored[metric], "status": "present"})
            else:
                rows.append({"company": "Sparse", "subsector": "equipment", "metric": metric, "value": "", "status": "not_applicable"})
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_rows(Path(tmp), fields, rows)
            entities, _ = score.parse_input(path, "compat")
            result = score.evaluate_entity(entities[0], "compat")
            self.assertEqual(result["core_scored"], 7)
            self.assertEqual(result["raw_coverage"], Decimal("41.2"))
            self.assertEqual(result["applicable_coverage"], Decimal("41.2"))
            self.assertEqual(result["rating"], "N/R")

    def test_single_year_cash_fallback_requires_insufficient_history(self):
        def mutate(rows):
            for row in rows:
                if row["metric"] == score.CASH_3Y:
                    row["status"] = "not_meaningful"
                    row["nm_reason"] = "negative_denominator"
                    row["input_fact_ids"] = "ex_cashconv"
            return rows

        with tempfile.TemporaryDirectory() as tmp:
            path = self.mutate_example(Path(tmp), mutate)
            with self.assertRaisesRegex(ValueError, "只允许在三年历史不足时回退"):
                score.parse_input(path, "strict")

    def test_missing_structural_check_blocks_rating(self):
        def mutate(rows):
            return [row for row in rows if row["metric"] != "audit_issue"]

        with tempfile.TemporaryDirectory() as tmp:
            path = self.mutate_example(Path(tmp), mutate)
            results, _ = score.run(self.args(path, "strict", facts=self.example_facts))
            result = results[0]
            self.assertEqual(result["structural_coverage"], Decimal("83.3"))
            self.assertEqual(result["rating_state"], "N_R")
            self.assertIn("structural_screen_incomplete", result["eligibility_reasons"])

    def test_detail_preserves_fact_locator_and_source_trace(self):
        results, _ = score.run(self.args(self.example_input, "strict", facts=self.example_facts))
        row = next(item for item in results[0]["details"] if item["metric"] == "gross_margin_total")
        self.assertEqual(row["fact_id"], "ex_gm")
        self.assertEqual(row["source_file"], "example-source.txt")
        self.assertEqual(row["locator_type"], "text_line")
        self.assertEqual(row["locator"], "3")
        self.assertIn("ex_gm:example-source.txt#text_line=3", row["source_trace"])

    def test_score_value_must_equal_linked_fact_value(self):
        def mutate(rows):
            for row in rows:
                if row["metric"] == "gross_margin_total":
                    row["value"] = "51.00"
            return rows

        with tempfile.TemporaryDirectory() as tmp:
            path = self.mutate_example(Path(tmp), mutate)
            with self.assertRaisesRegex(ValueError, "score value与fact value不一致"):
                score.run(self.args(path, "strict", facts=self.example_facts))

    def test_nominal_and_applied_deductions_reconcile(self):
        fields = ["company", "subsector", "metric", "value", "status"]
        rows = [
            {"company": "X", "subsector": "equipment", "metric": "goodwill_ratio", "value": "40", "status": "present"},
            {"company": "X", "subsector": "equipment", "metric": "max_customer_conc", "value": "50", "status": "present"},
            {"company": "X", "subsector": "equipment", "metric": "max_supplier_conc", "value": "50", "status": "present"},
            {"company": "X", "subsector": "equipment", "metric": "performance_commitment_flag", "value": "1", "status": "present"},
            {"company": "X", "subsector": "equipment", "metric": "audit_issue", "value": "1", "status": "present"},
            {"company": "X", "subsector": "equipment", "metric": "debt_default", "value": "1", "status": "present"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_rows(Path(tmp), fields, rows)
            entities, _ = score.parse_input(path, "compat")
            result = score.evaluate_entity(entities[0], "compat")
            self.assertEqual(result["nominal_deduction"], Decimal("1.70"))
            self.assertEqual(result["applied_deduction"], Decimal("0.80"))
            self.assertTrue(any("封顶0.80" in label for label in result["deduction_labels"]))

    def test_ranking_uses_formal_same_cohort_and_anchor_ties(self):
        def item(name: str, total: str, formal: bool = True, subsector: str = "equipment"):
            entity = score.EntityInput(
                company=name,
                entity_id=name,
                subsector=subsector,
                fy="FY2025",
                peer_group="peer-a",
                comparability_status="comparable",
                business_scope_status="pure_play",
                semiconductor_revenue_share=Decimal("100"),
                calibration_status="uncalibrated",
            )
            return {
                "entity": entity,
                "ranking_eligible": formal,
                "total": Decimal(total),
                "rating": "A" if formal else "N/R",
                "peer_rank": "",
                "peer_tier": "",
                "peer_sample_size": 0,
            }

        a = item("A", "4.50")
        b = item("B", "4.41")
        c = item("C", "4.40")
        excluded = item("Excluded", "5.00", formal=False)
        other = item("Other", "4.90", subsector="materials")
        rows = score.assign_rankings([a, b, c, excluded, other])
        self.assertEqual(a["peer_rank"], "1-2")
        self.assertEqual(b["peer_rank"], "1-2")
        self.assertEqual(c["peer_rank"], "3")
        self.assertEqual(excluded["peer_rank"], "")
        self.assertNotIn("Excluded", {row["entity_id"] for row in rows})
        self.assertNotIn("Other", {row["entity_id"] for row in rows})

    def test_v2_1_d6_holds_only_rd_intensity_and_top5_moved_to_alerts(self):
        # 规则 v2.1：D6 收缩为单一“创新投入”，前五客户/供应商集中度从正分维度
        # 移入 alerts（提示不扣分），与 structural 的 largest_* 扣分口径分离，
        # 消除对同一集中风险的双重计量。核心槽位随之由 19 降为 17。
        self.assertEqual(score.RULES["dimensions"]["D6"]["metrics"], ["rd_expense_intensity"])
        self.assertEqual(score.RULES["dimensions"]["D6"]["formal_minimum"], 1)
        self.assertEqual(len(score.CORE_SLOTS), 17)
        self.assertNotIn("top5_billed_customer_revenue_ratio", score.CORE_SLOT_SET)
        self.assertNotIn("top5_supplier_purchase_ratio", score.CORE_SLOT_SET)
        # 仍是合法 canonical 指标（否则 strict 输入列出会被判未知 metric）
        self.assertIn("top5_billed_customer_revenue_ratio", score.ALERT_METRICS)
        self.assertIn("top5_supplier_purchase_ratio", score.ALERT_METRICS)
        # largest_* 仍在 structural 扣分层，二者共存但口径不同
        self.assertIn("largest_billed_customer_revenue_ratio", score.STRUCTURAL_METRICS)
        self.assertIn("largest_supplier_purchase_ratio", score.STRUCTURAL_METRICS)
        # 校准机制已就位但未校准，禁止在无样本时宣称统计意义
        self.assertEqual(score.RULES["calibration"]["status"], "uncalibrated")

    def test_v2_2_adds_eda_ip_subsectors_and_rebalances_d6(self):
        # 规则 v2.2：新增 eda/ip 两个子行业（独立权重+定制阈值），并对全部子行业
        # 执行 D6 降权（单指标不再扛旧版三指标的权重）。阈值仍为专家先验、未校准。
        self.assertEqual(score.RULES["rules_version"], "2.2.0")
        # eda/ip 已成为合法子行业
        self.assertIn("eda", score.SUBSECTORS)
        self.assertIn("ip", score.SUBSECTORS)
        # eda/ip 有独立权重且每列合计 100
        for sub in ("eda", "ip"):
            self.assertIn(sub, score.RULES["weights"])
            self.assertEqual(sum(int(v) for v in score.RULES["weights"][sub].values()), 100)
        # eda/ip 非重资产，weight_group 返回自身而非 heavy
        self.assertEqual(score.weight_group("eda"), "eda")
        self.assertEqual(score.weight_group("ip"), "ip")
        # D6 降权：各子行业权重下调（设备 12→7、heavy 9→5、fabless 12→8）
        self.assertEqual(score.RULES["weights"]["equipment"]["D6"], "7")
        self.assertEqual(score.RULES["weights"]["heavy"]["D6"], "5")
        self.assertEqual(score.RULES["weights"]["fabless"]["D6"], "8")

    def test_eda_ip_custom_thresholds_do_not_penalize_high_rd_and_margin(self):
        # 回归防护：EDA 高研发强度是优点，不应被旧通用档惩罚为 2 分。
        # eda/ip 研发强度峰值上移到 [25,45]；毛利走各自定制档。
        for sub in ("eda", "ip"):
            self.assertEqual(score.score_metric("rd_expense_intensity", Decimal("35"), sub).score, 5)
            self.assertEqual(score.score_metric("rd_expense_intensity", Decimal("40"), sub).score, 5)
        # eda 纯工具毛利 90% 得满分，35% 落到 2 分档
        self.assertEqual(score.score_metric("gross_margin_total", Decimal("90"), "eda").score, 5)
        self.assertEqual(score.score_metric("gross_margin_total", Decimal("35"), "eda").score, 2)
        # ip 混服务，毛利档更低：50% 即满分
        self.assertEqual(score.score_metric("gross_margin_total", Decimal("50"), "ip").score, 5)
        # eda/ip 营收增速门槛低于 other：30% 即满分
        self.assertEqual(score.score_metric("rev_growth", Decimal("30"), "eda").score, 5)

    def test_ranges_default_bands_still_apply_to_non_eda_ip(self):
        # 向后兼容：band_groups 只对 eda/ip 生效，其余子行业仍用默认 bands。
        self.assertEqual(score.score_metric("rd_expense_intensity", Decimal("35"), "equipment").score, 3)
        self.assertEqual(score.score_metric("rd_expense_intensity", Decimal("15"), "equipment").score, 5)
        self.assertEqual(score.score_metric("rd_expense_intensity", Decimal("40"), "fabless").score, 2)

    def test_all_machine_rule_cut_points_are_left_or_right_closed_as_documented(self):
        for metric, spec in score.RULES["metrics"].items():
            method = spec["method"]
            if method in {"high", "low"}:
                if "cuts" in spec:
                    cases = [("equipment", spec["cuts"])]
                else:
                    cases = []
                    for group, cuts in spec["groups"].items():
                        subsector = "foundry" if group == "heavy" else ("equipment" if group == "other" else group)
                        cases.append((subsector, cuts))
                for subsector, cuts in cases:
                    for boundary, expected in cuts:
                        with self.subTest(metric=metric, subsector=subsector, boundary=boundary):
                            self.assertEqual(score.score_metric(metric, Decimal(boundary), subsector).score, expected)
            elif method == "zero_then_low":
                self.assertEqual(score.score_metric(metric, Decimal("0"), "equipment").score, 5)
                for boundary, expected in spec["cuts"]:
                    self.assertEqual(score.score_metric(metric, Decimal(boundary), "equipment").score, expected)

        rd_cases = {
            "12": 5, "25": 5, "8": 4, "30": 4,
            "5": 3, "35": 3, "3": 2, "2.99": 1,
        }
        for value, expected in rd_cases.items():
            self.assertEqual(
                score.score_metric("rd_expense_intensity", Decimal(value), "equipment").score,
                expected,
            )

    def test_prepare_score_input_round_trips_example_slots(self):
        spec = importlib.util.spec_from_file_location(
            "prepare_score_input", SKILL_ROOT / "scripts" / "prepare_score_input.py"
        )
        assert spec and spec.loader
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            self.assertEqual(
                prepare.main([
                    "--facts", str(self.example_facts),
                    "--source-root", str(SKILL_ROOT / "assets"),
                    "--company", "示例设备公司",
                    "--entity-id", "example-equipment",
                    "--subsector", "equipment",
                    "--fy", "FY2025",
                    "--peer-group", "equipment-cn",
                    "--comparability-status", "comparable",
                    "--business-scope-status", "pure_play",
                    "--semiconductor-revenue-share", "100",
                    "--out-dir", str(out_dir),
                ]),
                0,
            )
            with (out_dir / "score-input.csv").open(newline="", encoding="utf-8-sig") as handle:
                generated = list(csv.DictReader(handle))
            with self.example_input.open(newline="", encoding="utf-8-sig") as handle:
                original = list(csv.DictReader(handle))
            by_metric = {row["metric"]: row for row in generated}
            for row in original:
                self.assertIn(row["metric"], by_metric)
                got = by_metric[row["metric"]]
                self.assertEqual(got["status"], row["status"], row["metric"])
                if row["status"] == "present":
                    self.assertEqual(Decimal(got["value"]), Decimal(row["value"]), row["metric"])
            results, warnings = score.run(
                self.args(out_dir / "score-input.csv", "strict", out_dir / "score", out_dir / "facts.scored.csv")
            )
            self.assertEqual(warnings, [])
            self.assertEqual(results[0]["rating_state"], "FORMAL")
            self.assertEqual(results[0]["total"], Decimal("4.40"))

    def test_prepare_score_input_maps_raw_ledger_and_keeps_gaps_missing(self):
        spec = importlib.util.spec_from_file_location(
            "prepare_score_input", SKILL_ROOT / "scripts" / "prepare_score_input.py"
        )
        assert spec and spec.loader
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        fields = [
            "fact_id", "company", "metric", "period", "period_type", "scope",
            "attribution", "value", "unit", "currency", "status", "audit_status",
            "source_file", "locator_type", "locator", "source_line_item", "formula",
            "input_fact_ids", "notes",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_text(
                "\n".join([
                    "营业收入2025=200",
                    "营业收入2024=100",
                    "营业成本2025=80",
                    "归母净利润2025=40",
                    "扣非归母净利润2025=36",
                    "扣非归母净利润2024=30",
                    "经营现金流2025=50",
                    "资产总计2025=1000",
                    "负债合计2025=400",
                ]) + "\n",
                encoding="utf-8",
            )
            facts_path = root / "facts.csv"
            rows = [
                ["f_rev_25", "示例材料", "revenue", "FY2025", "fy", "consolidated", "na", "200", "million", "CNY", "reported", "audited", "source.txt", "text_line", "1", "营业收入", "", "", ""],
                ["f_rev_24", "示例材料", "revenue", "FY2024", "fy", "consolidated", "na", "100", "million", "CNY", "reported", "audited", "source.txt", "text_line", "2", "营业收入", "", "", ""],
                ["f_cost_25", "示例材料", "operating_cost", "FY2025", "fy", "consolidated", "na", "80", "million", "CNY", "reported", "audited", "source.txt", "text_line", "3", "营业成本", "", "", ""],
                ["f_np_25", "示例材料", "net_profit_parent", "FY2025", "fy", "consolidated", "parent", "40", "million", "CNY", "reported", "audited", "source.txt", "text_line", "4", "归母净利润", "", "", ""],
                ["f_nps_25", "示例材料", "nps_parent", "FY2025", "fy", "consolidated", "parent", "36", "million", "CNY", "reported", "audited", "source.txt", "text_line", "5", "扣非归母净利润", "", "", ""],
                ["f_nps_24", "示例材料", "nps_parent", "FY2024", "fy", "consolidated", "parent", "30", "million", "CNY", "reported", "audited", "source.txt", "text_line", "6", "扣非归母净利润", "", "", ""],
                ["f_ocf_25", "示例材料", "operating_cash_flow", "FY2025", "fy", "consolidated", "na", "50", "million", "CNY", "reported", "audited", "source.txt", "text_line", "7", "经营现金流", "", "", ""],
                ["f_assets_25", "示例材料", "total_assets", "2025-12-31", "instant", "consolidated", "na", "1000", "million", "CNY", "reported", "audited", "source.txt", "text_line", "8", "资产总计", "", "", ""],
                ["f_liab_25", "示例材料", "total_liabilities", "2025-12-31", "instant", "consolidated", "na", "400", "million", "CNY", "reported", "audited", "source.txt", "text_line", "9", "负债合计", "", "", ""],
            ]
            with facts_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(fields)
                writer.writerows(rows)
            out_dir = root / "prepared"
            self.assertEqual(
                prepare.main([
                    "--facts", str(facts_path),
                    "--source-root", str(root),
                    "--company", "示例材料",
                    "--subsector", "materials",
                    "--fy", "2025",
                    "--out-dir", str(out_dir),
                ]),
                0,
            )
            with (out_dir / "score-input.csv").open(newline="", encoding="utf-8-sig") as handle:
                generated = {row["metric"]: row for row in csv.DictReader(handle)}
            self.assertEqual(generated["rev_growth"]["status"], "present")
            self.assertEqual(Decimal(generated["rev_growth"]["value"]), Decimal("100"))
            self.assertEqual(generated["gross_margin_total"]["status"], "present")
            self.assertEqual(Decimal(generated["gross_margin_total"]["value"]), Decimal("60"))
            self.assertEqual(generated["nps_growth"]["status"], "present")
            self.assertEqual(generated["rev_cagr_3y"]["status"], "missing")
            self.assertEqual(generated["government_grant_pnl_ratio"]["status"], "missing")
            self.assertEqual(generated["debt_to_assets"]["status"], "present")
            self.assertEqual(Decimal(generated["debt_to_assets"]["value"]), Decimal("40"))
            self.assertEqual(generated["rev_growth"]["peer_group"], "materials-cn-a")
            results, _ = score.run(
                self.args(
                    out_dir / "score-input.csv",
                    "strict",
                    out_dir / "score",
                    out_dir / "facts.scored.csv",
                    root,
                )
            )
            self.assertEqual(results[0]["rating"], "N/R")
            self.assertIn("structural_screen_incomplete", results[0]["eligibility_reasons"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
