import unittest
from unittest.mock import patch

import app


class FoundationPhaseScopeTests(unittest.TestCase):
    def test_only_grade_one_to_three_books_are_in_catalog_scope(self):
        for grade in ("Grade 1", "Grade 2", "Grade 3", "3"):
            with self.subTest(grade=grade):
                self.assertTrue(app.resource_in_foundation_scope("Textbooks", grade))

        for grade in ("Grade 4", "Grade 8", None, "Primary"):
            with self.subTest(grade=grade):
                self.assertFalse(app.resource_in_foundation_scope("Textbooks", grade))

    def test_non_book_items_are_not_limited_by_book_grade(self):
        self.assertTrue(app.resource_in_foundation_scope("Stationery", "Grade 8"))

    def test_grade_is_parsed_from_free_text_book_name(self):
        self.assertEqual(app.grade_number_in_name("Grade 2 reading book"), 2)
        self.assertEqual(app.grade_number_in_name("Grade 8 workbook"), 8)
        self.assertIsNone(app.grade_number_in_name("Reading workbook"))

    def test_login_rejects_learner_role_without_authentication_attempt(self):
        with patch("app.model.authenticate_user") as authenticate:
            response = app.app.test_client().post(
                "/api/login",
                json={"username": "learner@example.com", "password": "password", "role": "learner"},
            )

        self.assertEqual(response.status_code, 401)
        authenticate.assert_not_called()

    def test_registration_rejects_learner_role(self):
        with patch("app.model.create_user") as create_user:
            response = app.app.test_client().post(
                "/api/register",
                json={
                    "full_name": "Foundation Learner",
                    "account_type": "learner",
                    "school_id": "L-100",
                    "email": "learner@example.com",
                    "password": "Password123!",
                    "confirm_password": "Password123!",
                },
            )

        self.assertEqual(response.status_code, 400)
        create_user.assert_not_called()

    def test_existing_learner_session_is_not_authenticated(self):
        client = app.app.test_client()
        with client.session_transaction() as session:
            session["uid"] = 12

        with patch(
            "app.model.get_user_by_id",
            return_value={"id": 12, "role": "learner"},
        ):
            response = client.get("/api/resources")

        self.assertEqual(response.status_code, 401)

    def test_resource_catalog_hides_books_outside_foundation_grades(self):
        client = app.app.test_client()
        with client.session_transaction() as session:
            session["uid"] = 20
        items = [
            {"id": 1, "name": "Grade 1 reader", "description": "", "category": "Textbooks", "grade": "Grade 1", "stock": 4, "unit": "books", "reorder_level": 1},
            {"id": 2, "name": "Grade 8 reader", "description": "", "category": "Textbooks", "grade": "Grade 8", "stock": 4, "unit": "books", "reorder_level": 1},
            {"id": 3, "name": "Geometry set", "description": "", "category": "Stationery", "grade": "Grade 8", "stock": 4, "unit": "sets", "reorder_level": 1},
        ]
        with (
            patch("app.model.get_user_by_id", return_value={"id": 20, "role": "teacher"}),
            patch("app.resource_rows", return_value=items),
            patch("app.availability", return_value=("Available", "ok")),
        ):
            response = client.get("/api/resources")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.json["items"]], ["Grade 1 reader", "Geometry set"])

    def test_inventory_api_rejects_textbooks_outside_foundation_grades(self):
        client = app.app.test_client()
        with client.session_transaction() as session:
            session["uid"] = 21
        payload = {
            "item_name": "Grade 8 textbook",
            "category": "Textbooks",
            "grade": "Grade 8",
            "inventory_type": "non_consumable",
            "quantity": 0,
            "reorder_level": 0,
            "description": "",
            "unit": "books",
            "storage_location": "",
            "unit_price": 10,
        }
        with (
            patch("app.model.get_user_by_id", return_value={"id": 21, "role": "ltsm"}),
            patch("app.db.get_db") as get_db,
        ):
            response = client.post("/api/inventory", json=payload)

        self.assertEqual(response.status_code, 400)
        get_db.assert_not_called()

    def test_free_text_book_request_rejects_out_of_scope_grade(self):
        client = app.app.test_client()
        with client.session_transaction() as session:
            session["uid"] = 22
        payload = {
            "resource_name": "Grade 8 natural sciences textbook",
            "category": "Other",
            "quantity": 1,
            "needed_by": (app.today() + app.timedelta(days=1)).isoformat(),
            "purpose": "For a classroom learning activity.",
        }
        with (
            patch("app.model.get_user_by_id", return_value={"id": 22, "role": "teacher"}),
            patch("app.db.query_one", return_value=None),
            patch("app.db.get_db") as get_db,
        ):
            response = client.post("/api/requests", json=payload)

        self.assertEqual(response.status_code, 400)
        get_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
