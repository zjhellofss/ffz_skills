from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_ROOT / "scripts"
DATA_ROOT = Path("/home/fss/data/上市公司财务信息")
sys.path.insert(0, str(SCRIPT_DIR))

from local_data import prepare_local_inputs  # noqa: E402
from validate_local_facts import validate_file  # noqa: E402


@unittest.skipUnless(DATA_ROOT.is_dir(), "local financial dataset is not installed")
class LocalPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="local-score-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def args(self) -> argparse.Namespace:
        return argparse.Namespace(
            ticker="688981.SH",
            company="中芯国际",
            subsector="foundry",
            fy="2025",
            period=None,
            entity_id=None,
            peer_group=None,
            comparability_status="comparable",
            business_scope_status="pure_play",
            semiconductor_revenue_share=Decimal("100"),
            calibration_status="uncalibrated",
            data_root=Path("/home/fss/data"),
            out_dir=self.temp_dir,
        )

    def test_prepare_validate_and_score(self) -> None:
        paths = prepare_local_inputs(self.args())
        validation = validate_file(paths["facts"], paths["source_root"])
        self.assertTrue(validation["ok"], validation["issues"])

        with paths["score_input"].open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(29, len(rows))
        by_metric = {row["metric"]: row for row in rows}
        self.assertEqual("present", by_metric["rev_growth"]["status"])
        self.assertEqual("missing", by_metric["government_grant_pnl_ratio"]["status"])
        self.assertEqual("checked_clear", by_metric["audit_issue"]["status"])
        self.assertEqual("missing", by_metric["debt_default"]["status"])

        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "score.py"),
                str(paths["score_input"]),
                "--mode", "strict",
                "--facts", str(paths["facts"]),
                "--source-root", str(paths["source_root"]),
                "--evidence-validator", "local",
                "--out-dir", str(self.temp_dir),
                "--quiet",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        with (self.temp_dir / "score_summary.csv").open(
            newline="", encoding="utf-8-sig"
        ) as handle:
            summary = next(csv.DictReader(handle))
        self.assertEqual("N_R", summary["rating_state"])
        self.assertIn("structural_screen_incomplete", summary["eligibility_reasons"])

    def test_source_tampering_is_rejected(self) -> None:
        paths = prepare_local_inputs(self.args())
        facts_path = paths["facts"]
        with facts_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        source_row = next(row for row in rows if row["source_file"] and not row["formula"])
        source_row["value"] = str(Decimal(source_row["value"]) + Decimal("1"))
        with facts_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        validation = validate_file(facts_path, paths["source_root"])
        self.assertFalse(validation["ok"])
        self.assertIn(
            "SOURCE_VALUE_MISMATCH",
            {item["code"] for item in validation["issues"]},
        )

    def test_negative_inventory_days_change_is_valid(self) -> None:
        args = self.args()
        args.ticker = "002371.SZ"
        args.company = "北方华创"
        args.subsector = "equipment"
        paths = prepare_local_inputs(args)
        with paths["score_input"].open(newline="", encoding="utf-8-sig") as handle:
            rows = {row["metric"]: row for row in csv.DictReader(handle)}
        self.assertLess(Decimal(rows["inventory_days_change"]["value"]), Decimal("0"))
        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "score.py"),
                str(paths["score_input"]),
                "--mode", "strict",
                "--facts", str(paths["facts"]),
                "--source-root", str(paths["source_root"]),
                "--evidence-validator", "local",
                "--out-dir", str(self.temp_dir),
                "--quiet",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stderr)

    def test_quarterly_ttm_is_diagnostic_only(self) -> None:
        args = self.args()
        args.fy = None
        args.period = "2026Q1"
        paths = prepare_local_inputs(args)
        self.assertTrue(paths["quarterly"])
        self.assertEqual("2026Q1", paths["period"])
        self.assertIsNone(paths["dupont_input"])
        validation = validate_file(paths["facts"], paths["source_root"])
        self.assertTrue(validation["ok"], validation["issues"])

        with paths["score_input"].open(newline="", encoding="utf-8-sig") as handle:
            rows = {row["metric"]: row for row in csv.DictReader(handle)}
        self.assertEqual("8.07389815", rows["rev_growth"]["value"])
        self.assertEqual("present", rows["gross_margin_total"]["status"])
        self.assertEqual("missing", rows["roe_weighted_parent"]["status"])

        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "score.py"),
                str(paths["score_input"]),
                "--mode", "strict",
                "--facts", str(paths["facts"]),
                "--source-root", str(paths["source_root"]),
                "--evidence-validator", "local",
                "--out-dir", str(self.temp_dir),
                "--quiet",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        with (self.temp_dir / "score_summary.csv").open(
            newline="", encoding="utf-8-sig"
        ) as handle:
            summary = next(csv.DictReader(handle))
        self.assertEqual("2026Q1", summary["fy"])
        self.assertEqual("QUARTERLY_DIAGNOSTIC", summary["rating_state"])
        self.assertEqual("N/R", summary["rating"])
        self.assertEqual("false", summary["ranking_eligible"])
        self.assertIn("quarterly_diagnostic_only", summary["eligibility_reasons"])

    def test_extreme_quarterly_ratios_are_not_meaningful(self) -> None:
        args = self.args()
        args.fy = None
        args.period = "2026Q1"

        args.ticker = "688661.SH"
        args.company = "和林微纳"
        args.subsector = "materials"
        paths = prepare_local_inputs(args)
        with paths["score_input"].open(newline="", encoding="utf-8-sig") as handle:
            rows = {row["metric"]: row for row in csv.DictReader(handle)}
        cash_conversion = rows["cash_conversion_parent_3y"]
        self.assertEqual("not_meaningful", cash_conversion["status"])
        self.assertEqual("near_zero_denominator", cash_conversion["nm_reason"])

        args.ticker = "688361.SH"
        args.company = "中科飞测"
        args.subsector = "equipment"
        args.out_dir = self.temp_dir / "recurring"
        paths = prepare_local_inputs(args)
        with paths["score_input"].open(newline="", encoding="utf-8-sig") as handle:
            rows = {row["metric"]: row for row in csv.DictReader(handle)}
        recurring = rows["recurring_parent_profit_ratio"]
        self.assertEqual("not_meaningful", recurring["status"])
        self.assertEqual("near_zero_denominator", recurring["nm_reason"])

    def test_quarterly_missing_audit_file_remains_unknown(self) -> None:
        args = self.args()
        args.ticker = "688797.SH"
        args.company = "臻宝科技"
        args.subsector = "equipment"
        args.fy = None
        args.period = "2026Q1"
        paths = prepare_local_inputs(args)
        with paths["score_input"].open(newline="", encoding="utf-8-sig") as handle:
            rows = {row["metric"]: row for row in csv.DictReader(handle)}
        self.assertEqual("missing", rows["audit_issue"]["status"])
        self.assertEqual("source_unavailable", rows["audit_issue"]["nm_reason"])


if __name__ == "__main__":
    unittest.main()
