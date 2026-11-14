"""Shared helpers for the test suite (standard library only: run with  python -m unittest discover -s tests -v )."""
import importlib
import logging
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CREDENTIALS = {"teacher": "g2.teacher1@example.com", "learner": "learner01@example.com", "ltsm": "ltsm01@example.com"}
PASSWORD = "Password123!"


class AppTestCase(unittest.TestCase):
    """Every test gets a freshly reloaded app, so the in-memory sample data always starts clean."""

    def setUp(self):
        import app as module
        self.app_module = importlib.reload(module)
        self.app_module.app.config["TESTING"] = True
        self.client = self.app_module.app.test_client()

    def sign_in(self, role):
        """A new test client (its own browser session) already signed in as `role`: teacher, learner or ltsm."""
        client = self.app_module.app.test_client()
        response = client.post("/api/login", json={"role": role, "username": CREDENTIALS[role], "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.get_json())
        return client

    def json(self, response, status=200):
        self.assertEqual(response.status_code, status, response.get_data(as_text=True))
        return response.get_json()

    def day(self, offset):
        return self.app_module.days_from_today(offset)


class BrowserTestCase(AppTestCase):
    """Runs the real pages in headless Chromium against a live Flask server. Skipped when Playwright/Chromium is missing."""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("Playwright is not installed (pip install -r requirements-dev.txt)")
        cls._playwright = sync_playwright().start()
        try:
            cls.browser = cls._playwright.chromium.launch()
        except Exception as error:
            cls._playwright.stop()
            raise unittest.SkipTest(f"Chromium is not available ({type(error).__name__}). Run: playwright install chromium")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._playwright.stop()

    def setUp(self):
        super().setUp()
        from werkzeug.serving import make_server
        logging.getLogger("werkzeug").setLevel(logging.ERROR)   # keep the test output readable
        server = make_server("127.0.0.1", 0, self.app_module.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        self.base_url = f"http://127.0.0.1:{server.server_port}"
        self.js_errors = []
        self.page = self.new_page()

    def new_page(self, width=1280, height=900):
        """A page in its own browser context (own cookies), so two people can use the portal at once."""
        context = self.browser.new_context(viewport={"width": width, "height": height})
        self.addCleanup(context.close)
        page = context.new_page()
        page.on("pageerror", lambda error: self.js_errors.append(str(error)))
        return page

    def sign_in_browser(self, page, role):
        page.goto(self.base_url + "/login")
        page.select_option("#role", role)
        page.fill("#username", CREDENTIALS[role])
        page.fill("#password", PASSWORD)
        page.click("#login-form button[type=submit]")
        page.wait_for_url("**/*-dashboard.html")
        return page

    def assert_no_js_errors(self):
        self.assertEqual(self.js_errors, [], "JavaScript errors were thrown in the browser")
