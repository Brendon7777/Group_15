import os
import re
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from flask import current_app, g


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def database_name():
    name = os.getenv("DB_NAME")
    if not name:
        raise RuntimeError("Set DB_NAME in the environment or .env file.")
    if len(name) > 64 or re.fullmatch(r"[A-Za-z0-9_]+", name) is None:
        raise RuntimeError("DB_NAME must be 1-64 letters, numbers, or underscores.")
    return name


def connect(include_database=True):
    required = ("DB_HOST", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if os.getenv(name) is None]
    if include_database and not os.getenv("DB_NAME"):
        missing.append("DB_NAME")
    if missing:
        raise RuntimeError(
            "Set the required MySQL environment variables: " + ", ".join(missing)
        )

    options = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
        "connect_timeout": 15,
    }
    if include_database:
        options["database"] = database_name()

    ssl_enabled = os.getenv("DB_SSL", "required").lower() not in ("0", "false", "disabled")
    if ssl_enabled:
        ssl_options = {"check_hostname": True}
        ca_path = os.getenv("DB_SSL_CA")
        if ca_path:
            ssl_options["ca"] = ca_path
        options["ssl"] = ssl_options

    return pymysql.connect(**options)


def get_db():
    if "db" not in g:
        current_app.logger.debug("Opening database connection for request")
        g.db = connect()
    return g.db


def close_db(exception=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def query_all(sql, params=None):
    with get_db().cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchall()


def query_one(sql, params=None):
    with get_db().cursor() as cursor:
        cursor.execute(sql, params or ())
        return cursor.fetchone()


def execute(sql, params=None):
    database = get_db()
    try:
        with database.cursor() as cursor:
            cursor.execute(sql, params or ())
            new_id = cursor.lastrowid
        database.commit()
        return new_id
    except Exception:
        database.rollback()
        raise