from datetime import date, datetime
import unittest
from unittest.mock import patch

from app import (
    app as flask_app,
    annual_usage_value,
    annual_usage_quantity,
    annual_usage_abc_value,
    classify_abc_values,
    automatic_evidence_change,
    evidence_daily_trend,
    evidence_change,
    illustrative_demo_comparisons,
    manual_period_value,
    average_or_none,
    percentage,
    potential_excess_stock_value,
)


class EvidenceMetricTests(unittest.TestCase):
    def test_average_and_percentage_handle_empty_samples(self):
        self.assertEqual(average_or_none([10, 20, 60]), 30)
        self.assertIsNone(average_or_none([]))
        self.assertEqual(percentage(2, 8), 25)
        self.assertIsNone(percentage(2, 0))

    def test_change_respects_whether_lower_or_higher_is_better(self):
        self.assertEqual(evidence_change(20, 15, "lower"), 25)
        self.assertEqual(evidence_change(80, 90, "higher"), 12.5)
        self.assertEqual(evidence_change(20, 20, "lower"), 0)

    def test_zero_baseline_and_missing_values_are_not_misreported(self):
        self.assertIsNone(evidence_change(0, 5, "lower"))
        self.assertEqual(evidence_change(0, 0, "lower"), 0)
        self.assertIsNone(evidence_change(None, 5, "lower"))
        self.assertIsNone(evidence_change(5, None, "lower"))

    def test_automatic_change_uses_count_differences_and_period_percentages(self):
        self.assertEqual(automatic_evidence_change(4, 7, "count"), 3)
        self.assertEqual(automatic_evidence_change(20, 15, "duration"), -25)
        self.assertEqual(automatic_evidence_change(0, 0, "rate"), 0)
        self.assertIsNone(automatic_evidence_change(0, 5, "rate"))
        self.assertIsNone(automatic_evidence_change(None, 5, "duration"))

    def test_automatic_daily_timing_trend_keeps_observation_counts(self):
        day = date(2026, 11, 24)
        with patch("app.db.query_all", return_value=[
            {"event_date": day, "value": 12.345, "sample_count": 2},
        ]) as query:
            points = evidence_daily_trend(
                "request_waiting", date(2026, 11, 1), date(2026, 11, 30)
            )

        self.assertEqual(
            points,
            [{"date": "2026-11-24", "value": 12.35, "sample_count": 2}],
        )
        self.assertIn("AVG(TIMESTAMPDIFF", query.call_args.args[0])

    def test_automatic_summary_compares_equal_adjacent_periods(self):
        client = flask_app.test_client()
        with client.session_transaction() as session:
            session["uid"] = 1
        current = {
            "requests_submitted": (8, 8),
            "request_waiting": (15, 2),
            "collection_waiting": (10, 2),
            "request_fulfillment": (25, 2),
            "bookings_requested": (3, 3),
            "booking_conflicts": (25, 4),
        }
        previous = {
            "requests_submitted": (5, 5),
            "request_waiting": (20, 2),
            "collection_waiting": (12, 2),
            "request_fulfillment": (32, 2),
            "bookings_requested": (2, 2),
            "booking_conflicts": (50, 2),
        }
        with patch("app.model.get_user_by_id", return_value={"id": 1, "role": "ltsm"}):
            with patch("app.evidence_period_values", side_effect=[current, previous]) as values:
                response = client.get(
                    "/api/evidence/automatic?from=2026-03-10&to=2026-03-19"
                )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["previous_period_start"], "2026-02-28")
        self.assertEqual(payload["previous_period_end"], "2026-03-09")
        self.assertEqual(values.call_args_list[0].args, (date(2026, 3, 10), date(2026, 3, 19)))
        self.assertEqual(values.call_args_list[1].args, (date(2026, 2, 28), date(2026, 3, 9)))
        rows = {item["key"]: item for item in payload["items"]}
        self.assertEqual(rows["requests_submitted"]["change"], 3)
        self.assertEqual(rows["request_waiting"]["change"], -25)

    def test_unconfirmed_empty_manual_period_is_not_reported_as_zero(self):
        self.assertIsNone(manual_period_value(0, complete=False, has_observations=False))
        self.assertEqual(manual_period_value(0, complete=True, has_observations=False), 0)
        self.assertEqual(manual_period_value(2, complete=False, has_observations=True), 2)

    def test_seeded_demo_comparisons_are_derived_and_keep_their_sample_sizes(self):
        baselines = [
            {
                "metric_key": "inventory_accuracy",
                "period_start": date(2025, 9, 1),
                "period_end": date(2025, 9, 30),
                "measure_value": 92,
                "sample_count": 25,
            },
            {
                "metric_key": "report_preparation",
                "period_start": date(2025, 9, 1),
                "period_end": date(2025, 9, 30),
                "measure_value": 24,
                "sample_count": 4,
            },
        ]
        events = [
            {
                "metric_key": "inventory_count",
                "occurred_at": datetime(2026, 9, 25),
                "expected_quantity": 18,
                "actual_quantity": 18,
                "duration_minutes": None,
            },
            {
                "metric_key": "report_preparation",
                "occurred_at": datetime(2026, 9, 25),
                "expected_quantity": None,
                "actual_quantity": None,
                "duration_minutes": 24,
            },
        ]

        comparisons = {
            item["key"]: item
            for item in illustrative_demo_comparisons(baselines, events)
        }

        self.assertEqual(comparisons["inventory_accuracy"]["current_value"], 100)
        self.assertEqual(comparisons["inventory_accuracy"]["baseline_sample_count"], 25)
        self.assertEqual(comparisons["inventory_accuracy"]["sample_count"], 1)
        self.assertEqual(comparisons["report_preparation"]["current_value"], 24)
        self.assertEqual(comparisons["report_preparation"]["baseline_value"], 24)
        self.assertTrue(comparisons["report_preparation"]["illustrative"])

    def test_abc_bands_are_ranked_independently_for_each_item_type(self):
        items = [
            {"id": 1, "inventory_type": "consumable", "abc_value": 80},
            {"id": 2, "inventory_type": "consumable", "abc_value": 15},
            {"id": 3, "inventory_type": "consumable", "abc_value": 5},
            {"id": 4, "inventory_type": "non_consumable", "abc_value": 80},
            {"id": 5, "inventory_type": "non_consumable", "abc_value": 20},
            {"id": 6, "inventory_type": None, "abc_value": None},
        ]
        self.assertEqual(
            classify_abc_values(items),
            {1: "A", 2: "B", 3: "C", 4: "A", 5: "B", 6: "Unclassified"},
        )

    def test_annual_consumable_value_uses_the_existing_forecast_period(self):
        self.assertEqual(
            annual_usage_value({"average": 10, "policy": "six_month", "unit_price": 3.5}),
            420,
        )
        self.assertEqual(
            annual_usage_value({"average": 120, "policy": "annual", "unit_price": 3.5}),
            420,
        )

    def test_annual_usage_quantity_uses_the_existing_forecast_period(self):
        self.assertEqual(
            annual_usage_quantity({"average": 10, "policy": "six_month"}),
            120,
        )
        self.assertEqual(
            annual_usage_quantity({"average": 120, "policy": "annual"}),
            120,
        )

    def test_usage_based_abc_uses_forecast_for_consumables_and_issue_history_for_reusable_items(self):
        forecast = {"average": 10, "policy": "six_month"}
        self.assertEqual(
            annual_usage_abc_value("consumable", forecast, None),
            120,
        )
        self.assertEqual(
            annual_usage_abc_value("non_consumable", None, 7),
            7,
        )
        self.assertIsNone(
            annual_usage_abc_value("non_consumable", None, None),
        )

    def test_potential_excess_stock_uses_rounded_up_live_targets_and_reports_coverage(self):
        resources = [
            {"id": 1, "inventory_type": "consumable", "on_hand": 15},
            {"id": 2, "inventory_type": "consumable", "on_hand": 4},
            {"id": 3, "inventory_type": "consumable", "on_hand": 20},
            {"id": 4, "inventory_type": "non_consumable", "on_hand": 20},
        ]
        forecast = {
            1: {"S": 10.1, "unit_price": 3},
            2: {"S": 4, "unit_price": 2},
            4: {"S": 1, "unit_price": 100},
        }

        self.assertEqual(
            potential_excess_stock_value(resources, forecast),
            (12, 2, 3),
        )


if __name__ == "__main__":
    unittest.main()
