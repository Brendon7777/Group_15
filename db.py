import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from flask import current_app, g


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def connect():
    options = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "avnadmin"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "ltsm_db"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
        "connect_timeout": 15,
    }

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