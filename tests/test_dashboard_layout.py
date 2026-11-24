import unittest
from unittest.mock import patch

import app


class DashboardLayoutTests(unittest.TestCase):
    def render_dashboard(self, page, user):
        client = app.app.test_client()
        with client.session_transaction() as session:
            session["uid"] = user["id"]
        with patch("app.model.get_user_by_id", return_value=user):
            return client.get(f"/{page}.html")

    def test_user_dashboard_exposes_account_scoped_reorderable_groups(self):
        response = self.render_dashboard(
            "user-dashboard",
            {"id": 31, "name": "Teacher", "role": "teacher"},
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-dashboard-user="31"', html)
        self.assertIn('data-reorderable-grid="user-summary"', html)
        self.assertIn('data-reorderable-grid="user-categories"', html)
        self.assertIn('data-layout-toggle', html)

    def test_committee_dashboard_exposes_account_scoped_reorderable_tiles(self):
        response = self.render_dashboard(
            "ltsm-dashboard",
            {"id": 32, "name": "Committee member", "role": "ltsm"},
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-dashboard-user="32"', html)
        self.assertIn('data-reorderable-grid="committee-summary"', html)
        self.assertIn('data-dashboard-tile="low-stock"', html)
        self.assertIn('data-layout-toggle', html)
        self.assertLess(html.index("Upcoming equipment bookings"), html.index("ABC classification"))
        self.assertIn('data-abc-basis="value" aria-pressed="true"', html)
        self.assertIn('data-abc-basis="usage" aria-pressed="false"', html)
        self.assertNotIn('<select id="abc-basis"', html)


if __name__ == "__main__":
    unittest.main()
