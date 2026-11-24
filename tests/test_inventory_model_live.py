import unittest
from datetime import date

from inventory_model_live import (
    annual_stockout_risk,
    calculate_results,
    products_from_rows,
)


class InventoryModelLiveTests(unittest.TestCase):
    def test_annual_stockout_warning_compares_issue_coverage_and_safety_buffer(self):
        self.assertEqual(annual_stockout_risk(90, 100, 10), (-10, "red", "High risk"))
        self.assertEqual(annual_stockout_risk(105, 100, 10), (5, "yellow", "Elevated risk"))
        self.assertEqual(annual_stockout_risk(111, 100, 10), (11, "green", "Low risk"))

    def test_illustrative_history_source_is_preserved_in_forecast(self):
        row = {
            "resource_id": 1,
            "resource_name": "Grade 1 Mathematics textbook",
            "grade": "Grade 1",
            "review_policy": "annual",
            "unit_of_measure": "copies",
            "unit_price": 280,
            "A": 18,
            "history_start": date(2023, 1, 1),
            "history_end": date(2025, 12, 31),
            "demand_values": "[140, 148, 136]",
            "history_source": "illustrative",
        }
        inputs = products_from_rows([row])
        result = calculate_results(inputs)[1]

        self.assertEqual(result["history_source"], "illustrative")
        self.assertEqual(result["risk"], "High risk")
        self.assertEqual(result["colour"], "red")


if __name__ == "__main__":
    unittest.main()
