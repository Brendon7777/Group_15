import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

from db import execute, get_db, query_all, query_one


class UserAlreadyExistsError(Exception):
    def __init__(self, field):
        self.field = field
        super().__init__(f"An account with that {field.replace('_', ' ')} already exists.")


class UserManagementError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _app_user(row):
    if row is None:
        return None
    return {
        "id": row["user_id"],
        "name": row["full_name"],
        "email": row["email"],
        "school_id": row["school_id"],
        "role": "teacher" if row["role"] == "staff" else row["role"],
        "hash": row["password_hash"],
        "is_active": bool(row["is_active"]),
    }


def authenticate_user(username, password, requested_role):
    row = query_one(
        """
        SELECT user_id, full_name, school_id, email, password_hash, role, is_active
        FROM users
        WHERE (email = %s OR school_id = %s) AND is_active = TRUE
        LIMIT 1
        """,
        (username, username),
    )
    user = _app_user(row)
    if (
        user is None
        or user["role"] != requested_role
        or not check_password_hash(user["hash"], password)
    ):
        return None
    return user


def get_user_by_id(user_id):
    row = query_one(
        """
        SELECT user_id, full_name, school_id, email, password_hash, role, is_active
        FROM users
        WHERE user_id = %s AND is_active = TRUE
        """,
        (user_id,),
    )
    return _app_user(row)


def create_user(full_name, school_id, email, password, account_type):
    existing_email = query_one(
        "SELECT user_id FROM users WHERE email = %s",
        (email,),
    )
    if existing_email:
        raise UserAlreadyExistsError("email")

    existing_school_id = query_one(
        "SELECT user_id FROM users WHERE school_id = %s",
        (school_id,),
    )
    if existing_school_id:
        raise UserAlreadyExistsError("school_id")

    role = "staff" if account_type == "teacher" else account_type
    password_hash = generate_password_hash(password)
    try:
        return execute(
            """
            INSERT INTO users (full_name, school_id, email, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (full_name, school_id, email, password_hash, role),
        )
    except pymysql.err.IntegrityError as error:
        if error.args and error.args[0] == 1062:
            existing_email = query_one(
                "SELECT user_id FROM users WHERE email = %s",
                (email,),
            )
            if existing_email:
                raise UserAlreadyExistsError("email") from error

            existing_school_id = query_one(
                "SELECT user_id FROM users WHERE school_id = %s",
                (school_id,),
            )
            if existing_school_id:
                raise UserAlreadyExistsError("school_id") from error
        raise


def list_users():
    return query_all(
        """
        SELECT user_id, full_name, school_id, email, role, is_active, created_at
        FROM users
        ORDER BY full_name, user_id
        """
    )


def set_user_active(user_id, is_active, actor_id):
    if is_active:
        existing = query_one(
            "SELECT user_id FROM users WHERE user_id = %s",
            (user_id,),
        )
        if not existing:
            return False
        execute(
            "UPDATE users SET is_active = TRUE WHERE user_id = %s",
            (user_id,),
        )
        return True

    if user_id == actor_id:
        raise UserManagementError("self_deactivation", "You cannot deactivate your own account.")

    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id
                FROM users
                WHERE role = 'ltsm' AND is_active = TRUE
                ORDER BY user_id
                FOR UPDATE
                """
            )
            active_ltsm_ids = {row["user_id"] for row in cursor.fetchall()}
            cursor.execute(
                "SELECT role, is_active FROM users WHERE user_id = %s FOR UPDATE",
                (user_id,),
            )
            target = cursor.fetchone()
            if target is None:
                connection.commit()
                return False
            if target["role"] == "ltsm" and target["is_active"] and len(active_ltsm_ids) <= 1:
                raise UserManagementError(
                    "last_ltsm",
                    "The last active LTSM account cannot be deactivated.",
                )
            cursor.execute(
                "UPDATE users SET is_active = FALSE WHERE user_id = %s",
                (user_id,),
            )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise