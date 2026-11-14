"""Unit tests: validation, status rules, priority rules and the school-timezone clock in app.py."""
import importlib
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from base import AppTestCase


class ValidatorTests(AppTestCase):
    def V(self, data):
        return self.app_module.Validator(data)

    def test_text_trims_and_enforces_length(self):
        v = self.V({"a": "  hello  ", "b": "", "c": "x" * 101, "d": "short"})
        self.assertEqual(v.text("a", "A"), "hello")
        v.text("b", "B"); v.text("c", "C"); v.text("d", "D", min_len=10, max_len=50)
        self.assertEqual(set(v.errors), {"b", "c", "d"})

    def test_text_rejects_non_strings_and_missing_keys(self):
        v = self.V({"a": 123, "b": None})
        v.text("a", "A"); v.text("b", "B"); v.text("missing", "M")
        self.assertEqual(set(v.errors), {"a", "b", "missing"})

    def test_integer(self):
        cases = [(5, True), ("5", True), (" 5 ", True), (0, False), (101, False), (True, False), ("abc", False), (5.5, False), (None, False), (-1, False)]
        for value, ok in cases:
            with self.subTest(value=value):
                v = self.V({"n": value})
                result = v.integer("n", "Number", 1, 100)
                self.assertEqual(result is not None, ok)
                self.assertEqual(not v.errors, ok)

    def test_choice(self):
        v = self.V({"c": "Textbooks", "d": "Nonsense"})
        self.assertEqual(v.choice("c", "Category", ("Textbooks", "Other")), "Textbooks")
        v.choice("d", "Category", ("Textbooks", "Other"))
        self.assertEqual(list(v.errors), ["d"])

    def test_email(self):
        cases = [("a@b.co", True), ("teacher.one@school.example.com", True), ("no-at-sign", False), ("a@b", False), ("a b@c.com", False), ("", False)]
        for email, ok in cases:
            with self.subTest(email=email):
                v = self.V({"e": email})
                v.email("e", "Email")
                self.assertEqual(not v.errors, ok)

    def test_email_is_lower_cased(self):
        self.assertEqual(self.V({"e": "Ayesha@School.CO.za"}).email("e", "Email"), "ayesha@school.co.za")

    def test_day_rules(self):
        today = date(2026, 11, 11)
        v = self.V({"ok": "2026-11-11", "past": "2026-11-10", "future": "2026-11-12", "bad": "11/11/2026", "none": None})
        self.assertEqual(v.day("ok", "D", not_before=today, not_after=today), today)
        v.day("past", "D", not_before=today); v.day("future", "D", not_after=today); v.day("bad", "D"); v.day("none", "D")
        self.assertEqual(set(v.errors), {"past", "future", "bad", "none"})

    def test_clock(self):
        for value, ok in [("09:30", True), ("00:00", True), ("23:59", True), ("24:00", False), ("ab:cd", False), ("", False)]:
            with self.subTest(value=value):
                v = self.V({"t": value})
                v.clock("t", "Time")
                self.assertEqual(not v.errors, ok)

    def test_done_raises_one_400_listing_every_bad_field(self):
        v = self.V({})
        v.text("name", "Name"); v.integer("qty", "Quantity", 1, 5)
        with self.assertRaises(self.app_module.ApiError) as caught:
            v.done()
        self.assertEqual(caught.exception.status, 400)
        self.assertEqual(set(caught.exception.fields), {"name", "qty"})
        self.assertIn("Name", caught.exception.message)
        self.assertIn("Quantity", caught.exception.message)


class StatusRuleTests(AppTestCase):
    def test_availability(self):
        cases = [(0, 5, "Textbooks", ("Out of stock", "danger")), (4, 8, "Textbooks", ("Limited", "warning")),
                 (8, 8, "Textbooks", ("Limited", "warning")),   # at the reorder level counts as limited
                 (9, 8, "Textbooks", ("Available", "ok")), (2, 1, "Equipment", ("Bookable", "warning")), (0, 1, "Equipment", ("Out of stock", "danger"))]
        for stock, reorder, category, expected in cases:
            with self.subTest(stock=stock, reorder=reorder, category=category):
                self.assertEqual(self.app_module.availability({"stock": stock, "reorder_level": reorder, "category": category}), expected)

    def test_stock_status(self):
        cases = [(0, 10, ("Out of stock", "danger")), (5, 10, ("Low stock", "danger")),  # half the reorder level or less is critical
                 (6, 10, ("Low stock", "warning")), (10, 10, ("In stock", "ok")), (50, 10, ("In stock", "ok")), (0, 0, ("Out of stock", "danger"))]
        for stock, reorder, expected in cases:
            with self.subTest(stock=stock, reorder=reorder):
                self.assertEqual(self.app_module.stock_status({"stock": stock, "reorder_level": reorder}), expected)

    def test_loan_status_boundaries(self):
        status = lambda offset: self.app_module.loan_status({"due": self.day(offset)})[0]
        self.assertEqual([status(-1), status(0), status(3), status(4)], ["Overdue", "Due soon", "Due soon", "On loan"])

    def test_request_priority_depends_on_how_soon_it_is_needed(self):
        fixed = date(2026, 11, 11)
        with mock.patch.object(self.app_module, "today", lambda: fixed):
            priority = lambda days: self.app_module.request_priority({"needed_by": (fixed + timedelta(days=days)).isoformat()})[0]
            self.assertEqual([priority(0), priority(3), priority(4), priority(7), priority(8)], ["High", "High", "Medium", "Medium", "Normal"])
            self.assertEqual(self.app_module.request_priority({})[0], "Normal")

    def test_text_helpers(self):
        self.assertEqual(self.app_module.plural(1, "request"), "1 request")
        self.assertEqual(self.app_module.plural(2, "category", "categories"), "2 categories")
        self.assertEqual(self.app_module.join_phrases(["a"]), "a")
        self.assertEqual(self.app_module.join_phrases(["a", "b", "c"]), "a, b and c")


class ClockAndConfigTests(AppTestCase):
    def test_today_uses_the_school_timezone_not_the_server_clock(self):
        """23:30 UTC on 10 Nov is already 11 Nov in South Africa (UTC+2). A UTC server must not reject 11 Nov as 'in the future'."""
        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 10, 23, 30, tzinfo=timezone.utc).astimezone(tz)
        with mock.patch.object(self.app_module, "datetime", FakeDateTime):
            self.assertEqual(self.app_module.today(), date(2026, 11, 11))

    def test_production_refuses_to_start_without_a_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
        env["APP_ENV"] = "production"
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                importlib.reload(self.app_module)

    def test_production_cookies_are_secure_and_use_the_configured_secret(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "production", "SECRET_KEY": "x" * 32}):
            reloaded = importlib.reload(self.app_module)
            self.assertTrue(reloaded.app.config["SESSION_COOKIE_SECURE"])
            self.assertEqual(reloaded.app.secret_key, "x" * 32)


if __name__ == "__main__":
    unittest.main()
