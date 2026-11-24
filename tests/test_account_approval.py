import unittest
from unittest.mock import MagicMock, patch

import app
import init_db
import model


class AccountApprovalTests(unittest.TestCase):
    def test_public_registration_creates_a_pending_account_request(self):
        payload = {
            "full_name": "New Teacher",
            "account_type": "teacher",
            "school_id": "T-100",
            "email": "new.teacher@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }

        with patch("app.model.create_user") as create_user:
            response = app.app.test_client().post("/api/register", json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertIn("must approve", response.json["message"])
        create_user.assert_called_once_with(
            "New Teacher",
            "T-100",
            "new.teacher@example.com",
            "Password123!",
            "teacher",
            account_status="pending",
        )

    def test_ltsm_can_approve_a_pending_account(self):
        client = app.app.test_client()
        with client.session_transaction() as session:
            session["uid"] = 7

        with (
            patch("app.model.get_user_by_id", return_value={"id": 7, "role": "ltsm"}),
            patch("app.model.approve_user_account", return_value=True) as approve,
        ):
            response = client.post("/api/committee/users/42/approve")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["message"], "Account approved. The user can now sign in.")
        approve.assert_called_once_with(42)

    def test_pending_user_creation_inserts_inactive_account(self):
        with (
            patch("model.query_one", side_effect=[None, None]),
            patch("model.execute", return_value=19) as execute,
        ):
            user_id = model.create_user(
                "New Teacher",
                "T-101",
                "new.teacher@example.com",
                "Password123!",
                "teacher",
                account_status="pending",
            )

        self.assertEqual(user_id, 19)
        self.assertIn("account_status, is_active", execute.call_args.args[0])
        self.assertEqual(execute.call_args.args[1][-2:], ("pending", False))

    def test_approval_activates_a_pending_account_transactionally(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"account_status": "pending"}
        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        connection = MagicMock()
        connection.cursor.return_value = cursor_context

        with patch("model.get_db", return_value=connection):
            approved = model.approve_user_account(42)

        self.assertTrue(approved)
        update = cursor.execute.call_args_list[1]
        self.assertIn("SET account_status = 'approved', is_active = TRUE", update.args[0])
        self.assertEqual(update.args[1], (42,))
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()

    def test_approval_rejects_accounts_that_are_not_pending(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"account_status": "approved"}
        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        connection = MagicMock()
        connection.cursor.return_value = cursor_context

        with (
            patch("model.get_db", return_value=connection),
            self.assertRaises(model.UserManagementError),
        ):
            model.approve_user_account(42)

        connection.rollback.assert_called_once()

    def test_initializer_adds_approved_default_for_existing_accounts(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"column_count": 0}

        init_db.ensure_user_account_status_column(cursor)

        self.assertIn("ADD COLUMN `account_status`", cursor.execute.call_args.args[0])
        self.assertIn("DEFAULT 'approved'", cursor.execute.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
