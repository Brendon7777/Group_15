"""Unit tests for the supply-chain calculations in inventory_model.py (expected values worked out by hand)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import inventory_model as m

PAPER = [10, 9, 20, 10, 15, 20]          # mean 14, population variance 130/6
SIGMA_PAPER = math.sqrt(130 / 6)          # 4.6547...


class MonthlyModelTests(unittest.TestCase):
    def test_average_and_standard_deviation(self):
        self.assertEqual(m.average_monthly_demand(PAPER), 14)
        self.assertAlmostEqual(m.demand_std_dev(PAPER), 4.6547, places=4)
        self.assertEqual(m.demand_std_dev([5, 5, 5]), 0)

    def test_stock_available_assumes_all_demand_was_met(self):
        self.assertEqual(m.stock_available(2, 100, PAPER), 18)
        self.assertEqual(m.stock_available(0, 0, [3, 4]), -7)   # negative = unmet demand; the model does not hide it

    def test_recommended_quantity_for_paper(self):
        SS, S, quantity = m.recommended_quantity(18, 14, SIGMA_PAPER, 1.65, 6, 1)
        self.assertAlmostEqual(SS, 1.65 * SIGMA_PAPER * math.sqrt(7))
        self.assertAlmostEqual(SS, 20.32, places=2)
        self.assertAlmostEqual(S, 118.32, places=2)
        self.assertEqual(quantity, 101)                          # ceil(118.32 - 18)

    def test_order_quantity_never_goes_negative(self):
        self.assertEqual(m.recommended_quantity(10_000, 14, SIGMA_PAPER, 1.65, 6, 1)[2], 0)
        self.assertEqual(m.annual_recommended_quantity(10_000, 140, 3.27, 1.65)[2], 0)

    def test_stockout_risk_thresholds(self):
        # average 5/month, lead time 2 months, safety stock 3  ->  remaining = on_hand - 10
        for on_hand, expected in [(10, ("red", "High risk")), (12, ("yellow", "Elevated risk")), (13, ("yellow", "Elevated risk")), (14, ("green", "Low risk"))]:
            with self.subTest(on_hand=on_hand):
                remaining, colour, risk = m.stockout_risk(on_hand, 5, 2, 3)
                self.assertEqual(remaining, on_hand - 10)
                self.assertEqual((colour, risk), expected)


class AnnualModelTests(unittest.TestCase):
    def test_annual_book_calculations(self):
        self.assertEqual(m.average_annual_demand([136, 140, 144]), 140)
        self.assertAlmostEqual(m.annual_demand_std_dev([136, 140, 144]), math.sqrt(32 / 3))
        self.assertEqual(m.annual_stock_available(2, 144, 144), 2)
        SS, S, quantity = m.annual_recommended_quantity(2, 140, math.sqrt(32 / 3), 1.65)
        self.assertAlmostEqual(SS, 5.389, places=3)
        self.assertAlmostEqual(S, 145.389, places=3)
        self.assertEqual(quantity, 144)


class SharedCalculationTests(unittest.TestCase):
    def test_supported_service_levels(self):
        for level, z in [(0.90, 1.28), (0.95, 1.65), (0.97, 1.88), (0.99, 2.33)]:
            with self.subTest(level=level):
                self.assertEqual(m.get_z_value(level), z)

    def test_unsupported_service_level_raises_key_error(self):
        for level in (0.5, 0.96, 1, 95):
            with self.subTest(level=level), self.assertRaises(KeyError):
                m.get_z_value(level)

    def test_order_cost_and_carry_over(self):
        self.assertEqual(m.order_cost(101, 140.0), 14140.0)
        self.assertEqual(m.order_cost(3, 19.999), 60.0)
        self.assertEqual(m.order_cost(0, 140.0), 0)
        self.assertEqual(m.carry_over(18, 101), (18, 101))

    def test_calculate_results_for_the_four_demo_products(self):
        results = m.calculate_results()
        self.assertEqual({n: r["quantity"] for n, r in results.items()}, {"Paper": 101, "Sellotape": 101, "Grade 2 activity books": 144, "Grade 3 activity books": 160})
        self.assertEqual({n: r["cost"] for n, r in results.items()}, {"Paper": 14140.0, "Sellotape": 2020.0, "Grade 2 activity books": 7200.0, "Grade 3 activity books": 8000.0})
        self.assertEqual(results["Paper"]["risk"], "Elevated risk")
        self.assertIsNone(results["Grade 2 activity books"]["risk"])

    def test_second_cycle_starts_from_the_previous_closing_stock_and_order(self):
        first = m.calculate_results()
        second = m.calculate_results(previous_results=first)
        for name, result in second.items():
            self.assertEqual(result["opening_stock"], first[name]["A"])
            self.assertEqual(result["stock_received"], first[name]["quantity"])

    def test_known_limitation_empty_history_raises_a_raw_zero_division_error(self):
        """BUG-06 (open, low): an empty demand list gives ZeroDivisionError instead of a readable message. See docs/TEST_REPORT.md."""
        with self.assertRaises(ZeroDivisionError):
            m.average_monthly_demand([])


if __name__ == "__main__":
    unittest.main()
