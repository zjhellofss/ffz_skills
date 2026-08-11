#!/usr/bin/env python3
"""Tests for the deterministic DuPont reconciliation tool."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("jibenmian_pingfen_dupont", SKILL_ROOT / "scripts" / "dupont.py")
assert SPEC and SPEC.loader
dupont = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dupont
SPEC.loader.exec_module(dupont)


class DupontTests(unittest.TestCase):
    def test_example_reconciles_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                input=SKILL_ROOT / "assets" / "example-dupont-input.csv",
                facts=SKILL_ROOT / "assets" / "example-dupont-facts.csv",
                source_root=SKILL_ROOT / "assets",
                out_dir=Path(tmp) / "out",
            )
            rows = dupont.run(args)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["status"], "OK")
            self.assertEqual(row["parent_net_margin_pct"], "10")
            self.assertEqual(row["dupont_parent_roe_pct"], "12.5")
            self.assertEqual(row["disclosed_weighted_parent_roe_pct"], "12.5")
            self.assertEqual(row["reconciliation_status"], "matched")
            self.assertEqual(row["major_nci_flag"], "false")
            self.assertTrue((args.out_dir / "dupont_manifest.json").exists())
            self.assertTrue((args.out_dir / "facts.snapshot.csv").exists())

    def test_major_nci_and_group_loss_flags_are_explicit(self):
        mapping = dupont.read_mapping(SKILL_ROOT / "assets" / "example-dupont-input.csv")[0]
        facts = dupont.load_facts(SKILL_ROOT / "assets" / "example-dupont-facts.csv")
        selected = dupont.verify_fact_set(mapping, facts)
        selected = deepcopy(selected)
        selected["net_profit_total_fact_id"]["value"] = "-10"
        selected["total_equity_open_fact_id"]["value"] = "1000"
        selected["total_equity_close_fact_id"]["value"] = "1000"
        row = dupont.calculate(mapping, selected)
        self.assertEqual(row["major_nci_flag"], "true")
        self.assertEqual(row["group_loss_parent_profit_flag"], "true")
        self.assertEqual(row["total_equity_roe_pct"], "-1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
