#!/usr/bin/env python3
"""Regression tests for valuation scoring gates."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "semiconductor_valuation", SKILL_ROOT / "scripts" / "valuation.py"
)
assert SPEC and SPEC.loader
valuation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = valuation
SPEC.loader.exec_module(valuation)


class ValuationGateTests(unittest.TestCase):
    def test_growth_score_does_not_fill_missing_with_three(self):
        self.assertIsNone(valuation.growth_score(None, None, None))
        self.assertEqual(valuation.growth_score(50, None, None), 5)
        self.assertEqual(valuation.growth_score(None, None, None, "turnaround_profit"), 5)
        self.assertEqual(valuation.growth_score(15, 15, None), 3)
        self.assertIsNone(valuation.growth_score(None, None, None, "missing"))

    def test_quality_requires_formal_or_provisional_state(self):
        states = valuation.parse_rating_states("FORMAL,PROVISIONAL", 2, [4.2, 3.1])
        self.assertEqual(states, ["FORMAL", "PROVISIONAL"])
        with self.assertRaises(SystemExit):
            valuation.parse_rating_states(None, 1, [4.2])
        with self.assertRaises(SystemExit):
            valuation.parse_rating_states("N/R", 1, [4.2])
        with self.assertRaises(SystemExit):
            valuation.parse_rating_states("QUARTERLY_DIAGNOSTIC", 1, [3.5])
        with self.assertRaises(SystemExit):
            valuation.parse_rating_states("FORMAL", 1, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
