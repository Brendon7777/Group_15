import os
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import db
import init_db
from werkzeug.security import check_password_hash


ROOT = Path(__file__).resolve().parents[1]


class DatabaseSetupTests(unittest.TestCase):
    def test_seed_script_inserts_sample_data_into_every_schema_table(self):
        schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
        seed = (ROOT / "seed.sql").read_text(encoding="utf-8")
        schema_tables = set(
            re.findall(r"CREATE TABLE IF NOT EXISTS\s+`([^`]+)`", schema, re.I)
        )
        seed_tables = set(
            re.findall(r"INSERT(?: IGNORE)? INTO\s+`([^`]+)`", seed, re.I)
        )

        self.assertEqual(schema_tables, seed_tables)

    def test_seeded_demo_logins_match_the_documented_password(self):
        seed = (ROOT / "seed.sql").read_text(encoding="utf-8")
        for email in ("g2.teacher1@example.com", "ltsm01@example.com"):
            match = re.search(
                re.escape(email) + r"'\s*,\s*'([^']+)'",
                seed,
            )
            self.assertIsNotNone(match, email)
            self.assertTrue(check_password_hash(match.group(1), "Password123!"), email)

    def test_initializer_migrates_only_the_unchanged_legacy_demo_hash(self):
        cursor = MagicMock()
        cursor.rowcount = 2

        updated_count = init_db.migrate_legacy_demo_password_hash(cursor)

        self.assertEqual(updated_count, 2)
        self.assertIn("WHERE `password_hash` = %s", cursor.execute.call_args.args[0])
        self.assertEqual(
            cursor.execute.call_args.args[1],
            (init_db.DEMO_PASSWORD_HASH, init_db.LEGACY_DEMO_PASSWORD_HASH),
        )

    def test_initializer_adds_demo_evidence_examples_idempotently(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"user_id": 7}, None, None]
        cursor.rowcount = 1

        inserted_count = init_db.ensure_demo_evidence_examples(cursor)

        self.assertEqual(inserted_count, 4)
        statements = [call.args[0] for call in cursor.execute.call_args_list[1:]]
        self.assertEqual(len(statements), 6)
        self.assertEqual(
            sum("INSERT IGNORE INTO `evidence_baseline`" in sql for sql in statements),
            2,
        )
        self.assertEqual(
            sum("INSERT INTO `operational_measurement`" in sql for sql in statements),
            2,
        )
        self.assertEqual(
            sum("SELECT `measurement_id` FROM `operational_measurement`" in sql for sql in statements),
            2,
        )

    def test_database_name_rejects_sql_identifiers_that_need_quoting(self):
        with patch.dict(os.environ, {"DB_NAME": "test; DROP DATABASE mysql"}):
            with self.assertRaisesRegex(RuntimeError, "letters, numbers, or underscores"):
                db.database_name()

    def test_connect_uses_required_environment_and_can_skip_database_selection(self):
        values = {
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "3307",
            "DB_USER": "test_user",
            "DB_PASSWORD": "",
            "DB_NAME": "test_database",
            "DB_SSL": "disabled",
        }
        with patch.dict(os.environ, values):
            with patch.object(db.pymysql, "connect") as connect:
                db.connect(include_database=False)

        options = connect.call_args.kwargs
        self.assertEqual(options["host"], values["DB_HOST"])
        self.assertEqual(options["user"], values["DB_USER"])
        self.assertNotIn("database", options)

    def test_initializer_creates_the_configured_database_before_schema_setup(self):
        cursor = MagicMock()
        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        connection = MagicMock()
        connection.cursor.return_value = cursor_context

        with patch.object(init_db, "database_name", return_value="fresh_ltsm_db"):
            with patch.object(init_db, "connect", return_value=connection) as connect:
                init_db.ensure_database_exists()

        connect.assert_called_once_with(include_database=False)
        statement = cursor.execute.call_args.args[0]
        self.assertIn("CREATE DATABASE IF NOT EXISTS `fresh_ltsm_db`", statement)
        connection.commit.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
