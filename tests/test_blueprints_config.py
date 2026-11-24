import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app
from config import (
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    config_for_environment,
)


class BlueprintAndConfigTests(unittest.TestCase):
    def test_domain_blueprints_are_registered(self):
        self.assertEqual(
            set(app.blueprints),
            {
                "pages",
                "auth",
                "notifications",
                "catalog",
                "requests",
                "bookings",
                "inventory",
                "circulation",
                "maintenance",
                "dashboard",
                "evidence",
                "reports",
                "health",
            },
        )

    def test_readme_endpoint_table_matches_registered_api_routes(self):
        documented = set()
        readme = Path(__file__).resolve().parents[1] / "README.md"
        for line in readme.read_text(encoding="utf-8").splitlines():
            cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
            if len(cells) == 3 and cells[0] in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                if cells[1].startswith("/api/"):
                    documented.add((cells[0], cells[1]))

        registered = set()
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith("/api/"):
                continue
            for method in rule.methods & {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                registered.add((method, rule.rule))

        self.assertEqual(len(registered), 46)
        self.assertEqual(documented, registered)

    def test_environment_profiles_are_available_and_production_requires_secret(self):
        self.assertIs(config_for_environment("development"), DevelopmentConfig)
        self.assertIs(config_for_environment("test"), TestingConfig)
        self.assertTrue(TestingConfig.TESTING)

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                config_for_environment("production")
        with patch.dict(os.environ, {"SECRET_KEY": "configured-for-test"}):
            self.assertIs(config_for_environment("production"), ProductionConfig)

    def test_login_page_uses_registered_blueprint_endpoints(self):
        response = app.test_client().get("/login")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
